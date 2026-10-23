"""Thin IfcDataExtractor facade.

Preserves the public call pattern (extract_all_floors(), extract_all_walls(),
etc.) of the prior project's ifc_geometry_processing.py, removed 2026-10-09 and
kept in git history at commit 2f8acf2, while delegating all actual work
to the pure functions in this package. This is the only place that chains
extract -> write -> (optional) plot, and the only place that enforces the
walls-after-curtainwalls ordering contract (post_processing_walls() requires
info_curtainwalls to already be populated).
"""

import os

import ifcopenshell

from toolsQuickUtils import time_decorator

from . import columns, curtainwalls, floor_refinement, floors, model_loader, viz, walls, writers
from .model_loader import get_file_prefix_code


class IfcDataExtractor:

    def __init__(self, model_path, figure_path, read="triangle"):

        try:
            self.type_geo = read
            self.settings = model_loader.configure_settings(self.type_geo)

            self.model = ifcopenshell.open(model_path)

            self.ifc_file_name = os.path.basename(model_path)
            self.authoring_tool = "non-ar" if "-AR-" not in self.ifc_file_name else "ar"

            self.out_fig_path = figure_path
            os.makedirs(figure_path, exist_ok=True)

            self.version = self.model.schema

            elements = model_loader.extract_all_ifc_elements(self.model)
            self.storeys = elements.get("storeys", [])
            self.slabs = elements.get("slabs", [])
            self.roofs = elements.get("roofs", [])
            self.st_columns = elements.get("st_columns", [])
            self.walls = elements.get("walls", [])
            self.curtainwalls = elements.get("curtainwalls", [])
            self.plates = elements.get("plates", [])
            self.members = elements.get("members", [])
            self.floors = []
            self.doors = []
            self.windows = []

            # Camera angles (elevation/azimuth, degrees) for the 3D plots.
            self.elev, self.azim = 25, 50

            print(f"=====================IfcExtractor=====================\n"
                  f"{self.ifc_file_name}\n"
                  f"=====================IfcExtractor=====================")

        except Exception as e:
            print(f"An error occurred: {e}")

    @time_decorator
    def extract_all_floors(self):
        self.floors = self.slabs
        self.info_floors = floors.extract_floors(
            self.settings, self.model, self.floors, self.type_geo, self.authoring_tool)
        writers.write_dict_floors(self.info_floors, self.out_fig_path)

    def post_processing_floors_to_slabs(self):
        self.info_floor_slabs, self.info_unique_floor_slabs = floor_refinement.refine_floor_slabs(
            self.info_floors)
        writers.write_dict_floor_slabs(self.info_unique_floor_slabs, self.out_fig_path)
        viz.refined_floor_slabs_display(self.info_floor_slabs, self.out_fig_path, self.ifc_file_name)

    @time_decorator
    def extract_all_columns(self):
        self.info_st_columns = columns.extract_columns(
            self.settings, self.model, self.st_columns, self.type_geo)
        self.info_st_columns = model_loader.add_marks(self.model, self.info_st_columns)
        writers.write_dict_columns(self.info_st_columns, self.out_fig_path)

    @time_decorator
    def extract_all_walls(self):
        self.info_walls = walls.extract_walls(self.settings, self.model, self.walls, self.type_geo)
        # populated in full by post_processing_walls(); placeholders until then.
        self.info_st_walls, self.info_ns_walls = [], []

    @time_decorator
    def extract_structural_walls_only(self):
        """Lightweight load-bearing-wall extraction: raw dimensions + axis-line
        enrichment only - skips post_processing_walls()'s glue/curtainwall/
        floor-outlier steps, which are display-oriented cleanup a recognition
        detector (src/recognition/detectors/structural.py) doesn't need, just
        raw axis-line geometry per wall. Sets self.info_st_walls directly,
        independent of extract_all_walls()/post_processing_walls()."""
        st_walls = [w for w in self.walls if walls.calc_wall_loadbearing(w)]
        info = walls.get_wall_dimensions(self.settings, self.model, st_walls, self.type_geo)
        self.info_st_walls = walls.enrich_wall_information(self.model, st_walls, info)
        writers.write_dict_walls(self.info_st_walls, [], [], self.out_fig_path)

    @time_decorator
    def extract_envelope_shapes(self):
        """Slab + roof footprint extraction for the envelope continuity
        detector (src/recognition/detectors/envelope.py). Skips
        post_processing_floors_to_slabs()'s own per-storey merging (that
        groups by raw float shape elevation, keyed by exact dict equality -
        fine for slabs alone, but a pitched roof commonly resolves to a
        different-enough elevation reading via a different code path -
        see floors.extract_roofs) - the detector instead groups by each
        shape's own IfcBuildingStorey container, the same native relation
        every other detector in src/recognition/ already keys off, and
        does its own closed-loop/footprint reasoning per group."""
        info_slabs = floors.extract_floors(self.settings, self.model, self.slabs, self.type_geo, self.authoring_tool)
        for info in info_slabs:
            info["source"] = "IfcSlab"
        info_roofs = floors.extract_roofs(self.settings, self.model, self.roofs, self.type_geo)
        for info in info_roofs:
            info["source"] = "IfcRoof"
        self.info_envelope_shapes = [
            info for info in info_slabs + info_roofs
            if info.get("location") is not None
        ]

    @time_decorator
    def extract_all_curtainwalls(self):
        self.info_curtainwalls = curtainwalls.extract_curtainwalls(
            self.settings, self.model, self.curtainwalls, self.plates, self.members, self.type_geo)

    def post_processing_walls(self):
        # Ordering contract: requires extract_all_curtainwalls() to have already run.
        if not hasattr(self, "info_curtainwalls"):
            raise RuntimeError(
                "post_processing_walls() requires extract_all_curtainwalls() to run first "
                "(it reads info_curtainwalls).")

        result = walls.post_process_walls(
            self.model, self.info_walls, self.info_st_walls, self.info_ns_walls,
            self.info_curtainwalls, self.walls, self.curtainwalls, self.out_fig_path)

        self.info_walls = result["info_walls"]
        self.info_st_walls = result["info_st_walls"]
        self.info_ns_walls = result["info_ns_walls"]
        self.info_curtainwalls = result["info_curtainwalls"]
        self.id_st_walls = result["id_st_walls"]
        self.id_ns_walls = result["id_ns_walls"]
        self.id_ct_walls = result["id_ct_walls"]
        self.main_directions = result["main_directions"]
        self.wall_x_values = result["wall_x_values"]
        self.wall_y_values = result["wall_y_values"]
        self.corner_x_value = result["corner_x_value"]
        self.corner_y_value = result["corner_y_value"]
        self.corner_z_value = result["corner_z_value"]

        writers.write_dict_walls(self.info_st_walls, self.info_ns_walls, self.info_curtainwalls, self.out_fig_path)

    @time_decorator
    def wall_display(self):
        viz.wall_display(self.info_walls, self.info_curtainwalls, self.out_fig_path)

    @time_decorator
    def wall_column_floor_location_display(
        self, view_elev=None, view_azim=None,
        plot_main_plane_directions=False, plot_main_plane=False, plane_vector_length=1,
    ):
        viz.wall_column_floor_location_display(
            self.ifc_file_name, self.out_fig_path,
            self.info_st_walls, self.info_ns_walls, self.info_curtainwalls,
            self.id_st_walls, self.id_ns_walls, self.id_ct_walls,
            self.info_st_columns, self.info_floors, self.wall_x_values, self.wall_y_values,
            self.corner_x_value, self.corner_y_value, self.corner_z_value, self.main_directions,
            default_elev=self.elev, default_azim=self.azim,
            view_elev=view_elev, view_azim=view_azim,
            plot_main_plane_directions=plot_main_plane_directions,
            plot_main_plane=plot_main_plane, plane_vector_length=plane_vector_length,
        )

    def export_triangle_geometry(self, id=None, x_box=1, y_box=1, z_box=1):
        viz.export_triangle_geometry(self.settings, self.model, id=id, x_box=x_box, y_box=y_box, z_box=z_box)

    def tempo_export_triangle_geometry_single_wall(self, ids=None, x_box=1, y_box=1, z_box=1, elev=30, azim=45):
        viz.tempo_export_triangle_geometry_single_wall(
            self.settings, self.model, self.out_fig_path, ids=ids,
            x_box=x_box, y_box=y_box, z_box=z_box, elev=elev, azim=azim)

    def export_triangle_geometry_of_all_walls(self, x_box=1, y_box=1, z_box=1, elev=45, azim=50):
        viz.export_triangle_geometry_of_all_walls(
            self.settings, self.model, self.id_ns_walls, self.plates, self.out_fig_path,
            x_box=x_box, y_box=y_box, z_box=z_box, elev=elev, azim=azim)

    def export_triangle_geometry_of_a_curtainwall(self, x_box=1, y_box=1, z_box=1, elev=45, azim=50):
        viz.export_triangle_geometry_of_a_curtainwall(
            self.settings, self.model, self.plates, self.out_fig_path,
            x_box=x_box, y_box=y_box, z_box=z_box, elev=elev, azim=azim)

    def _get_file_prefix_code(self, filename):
        return get_file_prefix_code(filename)
