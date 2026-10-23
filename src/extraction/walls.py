"""Wall raw extraction, st/ns/ct classification, and post-processing.

Ordering contract: `post_process_walls()` reads `info_curtainwalls`, so
`extract_curtainwalls()` (curtainwalls.py) must have already run before this is
called - enforced by the facade in extractor.py, not by this module.
"""

import math
from collections import Counter

import ifcopenshell.util.element

from toolsSpatialGlue import spatial_process_lines

from .geometry_iteration import iterate_shapes
from .geometry_math import calc_element_orientation, shape2_location_verts, vertices2dimensions
from .model_loader import add_marks


def calc_wall_is_int_ext(wall):
    psets = ifcopenshell.util.element.get_psets(wall)
    return psets.get("Pset_WallCommon", {}).get("IsExternal")


def calc_wall_loadbearing(wall):
    psets = ifcopenshell.util.element.get_psets(wall)
    return psets.get("Pset_WallCommon", {}).get("LoadBearing")


def get_wall_dimensions(settings, model, walls, type_geo):

    info_walls = []
    for shape in iterate_shapes(settings, model, walls, type_geo):
        wall_location_p1, grouped_verts = shape2_location_verts(shape)
        wall_dimensions = vertices2dimensions(grouped_verts)
        wall_location_p1 = wall_location_p1.tolist()

        dict_of_a_wall = {
            "id": shape.guid,
            "elevation": round(wall_location_p1[-1], 4),
            "location": [wall_location_p1],
        }
        dict_of_a_wall.update(wall_dimensions)
        info_walls.append(dict_of_a_wall)

    return info_walls


def _update_wall_info(wall, info_w):

    orientation_deg = calc_element_orientation(wall)
    wall_location_p1 = info_w["location"][0]
    wall_location_p2 = (
        wall_location_p1[0] + info_w["length"] * math.cos(math.radians(orientation_deg)),
        wall_location_p1[1] + info_w["length"] * math.sin(math.radians(orientation_deg)),
        wall_location_p1[2],
    )

    info_w.update({
        "location": [wall_location_p1, wall_location_p2],
        "orientation": calc_element_orientation(wall, deg_range=180),
    })

    return info_w


def enrich_wall_information(model, walls, info_walls):
    id_to_wall = {w.GlobalId: w for w in walls}
    return [
        _update_wall_info(id_to_wall[info["id"]], info)
        for info in info_walls
        if info["id"] in id_to_wall
        and calc_element_orientation(id_to_wall[info["id"]]) is not None
        and info["length"] is not None
    ]


def extract_walls(settings, model, walls, type_geo):
    """Raw wall extraction + enrichment. Returns info_walls."""
    info_walls = get_wall_dimensions(settings, model, walls, type_geo)
    return enrich_wall_information(model, walls, info_walls)


def remove_wall_outliers(info_walls, min_height=1.0):
    """Generic threshold filter (not project-specific calibration data)."""
    return [w for w in info_walls if w["height"] > min_height]


def get_all_wall_int_ext(model, info_walls, info_curtainwalls):
    """Tag each wall/curtainwall dict with external=0/1."""

    for info in info_walls:
        element = model.by_guid(info["id"])
        info["external"] = 1 if calc_wall_is_int_ext(element) else 0

    # Curtain walls are assumed always external.
    for info in info_curtainwalls:
        info["external"] = 1

    return info_walls, info_curtainwalls


def split_st_ns_ct_wall_information(model, walls, curtainwalls, info_walls):
    """Classify walls into structural/non-structural, and split info_walls accordingly."""

    id_st_walls = [w.GlobalId for w in walls if calc_wall_loadbearing(w)]
    id_ns_walls = [w.GlobalId for w in walls if not calc_wall_loadbearing(w)]
    id_ct_walls = [w.GlobalId for w in curtainwalls] if curtainwalls else []

    info_st_walls, info_ns_walls = [], []
    for info_w in info_walls:
        value_to_check = info_w.get("id", None)
        if value_to_check in id_st_walls:
            info_st_walls.append(info_w)
        elif value_to_check in id_ns_walls:
            info_ns_walls.append(info_w)

    return id_st_walls, id_ns_walls, id_ct_walls, info_st_walls, info_ns_walls


def glue_wall_connections(info_st_walls, info_ns_walls, info_curtainwalls,
                           id_st_walls, id_ns_walls, id_ct_walls, out_fig_path):
    """Extend/snap wall endpoints at near-intersections via toolsSpatialGlue.

    Note: spatial_process_lines(plot_adjustments=True) saves a PNG per elevation as
    a side effect of the external toolsSpatialGlue module - left as-is, that module
    is out of scope for this reorg.
    """

    all_wall_data = info_st_walls + info_ns_walls + info_curtainwalls
    glued_wall_data = spatial_process_lines(
        all_wall_data, plot_adjustments=True, output_figure_folder=out_fig_path)

    new_info_st_walls, new_info_ns_walls, new_info_curtainwalls = [], [], []

    for info_w in glued_wall_data:
        wall_id = info_w.get("id", None)
        if wall_id in id_st_walls:
            new_info_st_walls.append(info_w)
        elif wall_id in id_ns_walls:
            new_info_ns_walls.append(info_w)
        elif wall_id in id_ct_walls:
            new_info_curtainwalls.append(info_w)

    return new_info_st_walls, new_info_ns_walls, new_info_curtainwalls


def get_main_directions_from_walls(info_ns_walls, info_st_walls, info_curtainwalls, num_directions=4):
    """Dominant wall orientations + bounding-corner values (used later for 3D display)."""

    info_all_walls = info_ns_walls + info_st_walls + info_curtainwalls

    wall_orientations = [w["orientation"] for w in info_all_walls if "orientation" in w]
    wall_orientations = [(v - 180) if v >= 180 else v for v in wall_orientations]
    main_directions = Counter(wall_orientations).most_common(num_directions)
    main_directions = [main_direct[0] for main_direct in main_directions]

    wall_x_values = [w["location"][0][0] for w in info_all_walls if "location" in w]
    wall_y_values = [w["location"][0][1] for w in info_all_walls if "location" in w]

    corner_x_value = (max(wall_x_values) + min(wall_x_values)) * 0.5
    corner_y_value = (max(wall_y_values) + min(wall_y_values)) * 0.5
    corner_z_value = max([w["location"][0][-1] for w in info_all_walls if "location" in w]) * 1.1

    return {
        "main_directions": main_directions,
        "wall_x_values": wall_x_values,
        "wall_y_values": wall_y_values,
        "corner_x_value": corner_x_value,
        "corner_y_value": corner_y_value,
        "corner_z_value": corner_z_value,
    }


def post_process_walls(model, info_walls, info_st_walls, info_ns_walls, info_curtainwalls,
                        walls, curtainwalls, out_fig_path):
    """Full wall post-processing pipeline (everything except writing to disk).

    Requires info_curtainwalls to already be populated by curtainwalls.extract_curtainwalls().
    """

    info_walls, info_curtainwalls = get_all_wall_int_ext(model, info_walls, info_curtainwalls)
    info_walls = remove_wall_outliers(info_walls)

    id_st_walls, id_ns_walls, id_ct_walls, info_st_walls, info_ns_walls = \
        split_st_ns_ct_wall_information(model, walls, curtainwalls, info_walls)

    info_st_walls, info_ns_walls, info_curtainwalls = glue_wall_connections(
        info_st_walls, info_ns_walls, info_curtainwalls,
        id_st_walls, id_ns_walls, id_ct_walls, out_fig_path)

    direction_info = get_main_directions_from_walls(info_ns_walls, info_st_walls, info_curtainwalls)

    info_st_walls = add_marks(model, info_st_walls)
    info_ns_walls = add_marks(model, info_ns_walls)

    return {
        "info_walls": info_walls,
        "info_st_walls": info_st_walls,
        "info_ns_walls": info_ns_walls,
        "info_curtainwalls": info_curtainwalls,
        "id_st_walls": id_st_walls,
        "id_ns_walls": id_ns_walls,
        "id_ct_walls": id_ct_walls,
        **direction_info,
    }
