"""Per-model context for the Neufert families: unit scales, a shape cache in
world coordinates, space footprints, storey resolution.

Units (verified on ifcopenshell 0.8.5): `calculate_unit_scale`
is metres per project LENGTH unit only, so areas, volumes and plane angles
each carry their own scale. Lengths go through `ifc_units.length_scale` like
every other coordinate in src/ (docs/detectors.md rule 13).

Geometry: a fresh `ifcopenshell.geom.settings()` with
`settings.set("use-world-coords", True)`; the shared
`extraction.model_loader.configure_settings` still assigns the attribute
form, which 0.8.5 ignores, and is not reused here. The shape OBJECT is
cached, never a bare `.geometry` (a dangling geometry gave garbage
vertices in the check). Space footprints come from the shared door graph's
`polygons` when a graph is passed, so spaces are not triangulated twice;
otherwise from `access_graph.space_polygons`.

Storeys: `storeys.get_storey(element, parent_container=True)` resolves a
space (aggregated), a door (contained) and a stair flight (aggregated into
a contained stair) alike.
"""

import ifcopenshell.geom
import ifcopenshell.util.element
import ifcopenshell.util.shape
import ifcopenshell.util.unit
import shapely

from ifc_units import length_scale

from extraction.geometry_iteration import iterate_shapes

from .. import vocabulary
from ..session import ModelSession
from ..storeys import get_storey


# The median distance from the door graph's door points to its nearest footprint
# above which the graph is in another frame than its doors (geometry.py's
# WINDOW_FRAME_SUSPECT_M is the same test for windows).
GRAPH_FRAME_SUSPECT_M = 2.0
# The median centroid shift between the graph's footprint of a space and the context's
# world-frame footprint of the same space above which the graph is in the wrong frame
# even where its door points sit in that same wrong frame (2026-10-20: 6 of the
# 17 frame-broken corpus models passed the door-point test with a median of 0.0 m; the
# shift is 8.1–138.5 m on all 17 and about 0 on the other 352).
GRAPH_FRAME_SHIFT_M = 0.5


def _unit_scale(model, unit_type):
    try:
        return float(ifcopenshell.util.unit.calculate_unit_scale(model, unit_type=unit_type))
    except Exception:  # noqa: BLE001 - no project, no unit of that type: 1.0 like length_scale
        return 1.0


class Context:
    def __init__(self, model, graph=None):
        self.model = model
        self.graph = graph
        self.length_scale = length_scale(model)
        self.area_scale = _unit_scale(model, "AREAUNIT")
        self.volume_scale = _unit_scale(model, "VOLUMEUNIT")
        self.angle_scale = _unit_scale(model, "PLANEANGLEUNIT")  # radians per project angle unit
        self._settings = None
        self._local_settings = None
        self._shapes = {}
        self._polygons = None
        self._z_extent = {}
        # Property sets live on the model session (session.py) since
        # 2026-10-22: one memo for the detectors, preflight and this Context.
        # A fresh Context drops the implicit session of its model, so a verify
        # fixture mutated after a read is read again (today's empty-cache
        # semantics); the CLI's explicit session is unaffected.
        ModelSession.forget_implicit(model)
        self._texts = {}
        self._storey_cache = {}
        self._storeys_sorted = None
        self._facts = {}
        self._graph_usable = None
        self.graph_frame_median_m = None
        self.graph_frame_shift_m = None

    def graph_usable(self):
        """The shared door graph is usable AND its footprints sit where its
        doors are. A corpus probe (2026-10-20): on 17 corpus models and on
        FZK-Haus every AccessGraph footprint is in the space's LOCAL frame
        (model_loader's world-coordinate flag, flagged for review) while
        usable() says True, the median door-to-footprint distance is 28.8 m
        and 15 of the 16 door links are wrong; on 6 of the 17 the door points
        sit in the same wrong frame, so a second test compares the graph's
        footprints with this context's world-frame ones. Every Neufert
        consumer of the graph asks here, so such a model reads as "no graph"
        (nodata) rather than as garbage. Memoised; both medians are kept."""
        if self._graph_usable is None:
            graph = self.graph
            usable = graph is not None and graph.usable()
            polygons = getattr(graph, "polygons", None) or {}
            points = list((getattr(graph, "door_points", None) or {}).values())
            if usable and polygons and points:
                tree = shapely.STRtree(list(polygons.values()))
                distances = sorted(tree.query_nearest(shapely.points(points), return_distance=True)[1].tolist())
                self.graph_frame_median_m = distances[len(distances) // 2]
                usable = self.graph_frame_median_m <= GRAPH_FRAME_SUSPECT_M
            if usable and polygons:
                # Second test: the graph's footprints against this context's world-frame
                # footprints of the same spaces (those read from their own shapes, not the
                # ones that fell back to the graph's).
                shifts = sorted(polygons[guid].centroid.distance(own.centroid)
                                for guid, own in self.polygons.items() if guid in polygons and own is not polygons[guid])
                if shifts:
                    self.graph_frame_shift_m = shifts[len(shifts) // 2]
                    usable = self.graph_frame_shift_m <= GRAPH_FRAME_SHIFT_M
            self._graph_usable = usable
        return self._graph_usable

    # ---- geometry ----
    @property
    def settings(self):
        if self._settings is None:
            settings = ifcopenshell.geom.settings()
            settings.set("use-world-coords", True)
            self._settings = settings
        return self._settings

    @property
    def local_settings(self):
        """Element-frame settings: a wall's length runs along its local X and
        its faces look along local Y, whatever its rotation in the world, so
        extents and side areas read in this frame are the element's own."""
        if self._local_settings is None:
            self._local_settings = ifcopenshell.geom.settings()
        return self._local_settings

    def shape(self, element, local=False):
        """The cached shape object (world frame, or the element's own frame
        with `local`), or None for an element without usable geometry."""
        key = (element.id(), local)
        if key not in self._shapes:
            try:
                self._shapes[key] = ifcopenshell.geom.create_shape(self.local_settings if local else self.settings, element)
            except Exception:  # noqa: BLE001 - no or broken representation
                self._shapes[key] = None
        return self._shapes[key]

    @property
    def polygons(self):
        """space GUID -> shapely footprint in the context's WORLD frame: the
        plan projection of each space's own triangulated shape (use-world-
        coords set), so a window or door placement, which is world, lands on
        it. The shared door graph's footprints come from the extraction
        settings whose world-coordinate flag 0.8.5 ignores (local frame
        wherever a space's placement is not identity) and are only the
        fallback for a space whose shape fails here."""
        if self._polygons is None:
            polygons = {}
            spaces = self.model.by_type("IfcSpace")
            # One multi-threaded iterator pass over every space (the shared
            # helper streams shapes; each is consumed before next()), in
            # place of one create_shape per space: 1,384 spaces cost 1.8 s
            # that way on corpus model 0101 (profiled 2026-10-18).
            try:
                for shape in iterate_shapes(self.settings, self.model, spaces, "triangle"):
                    guid = shape.guid
                    try:
                        vertices = ifcopenshell.util.shape.get_vertices(shape.geometry)
                    except Exception:  # noqa: BLE001
                        continue
                    if len(vertices):
                        self._z_extent[guid] = float(vertices[:, 2].max() - vertices[:, 2].min())
                    polygon = self._footprint_of(vertices, ifcopenshell.util.shape.get_faces(shape.geometry))
                    if polygon is not None:
                        polygons[guid] = polygon
            except Exception:  # noqa: BLE001 - the iterator itself failed: fall back per space below
                pass
            for space in spaces:
                if space.GlobalId not in polygons:
                    polygon = self._footprint(space)
                    if polygon is not None:
                        polygons[space.GlobalId] = polygon
            fallback = self.graph.polygons if self.graph is not None and getattr(self.graph, "polygons", None) else {}
            for guid, polygon in fallback.items():
                polygons.setdefault(guid, polygon)
            self._polygons = polygons
        return self._polygons

    def space_z_extent(self, space):
        """Height of the space's own shape, from the same iterator pass as
        the footprints; None when the shape was not read."""
        self.polygons  # noqa: B018 - ensures the pass ran
        if space.GlobalId not in self._z_extent:
            shape = self.shape(space)
            if shape is None:
                return None
            try:
                vertices = ifcopenshell.util.shape.get_vertices(shape.geometry)
                self._z_extent[space.GlobalId] = float(vertices[:, 2].max() - vertices[:, 2].min()) if len(vertices) else None
            except Exception:  # noqa: BLE001
                self._z_extent[space.GlobalId] = None
        return self._z_extent[space.GlobalId]

    def _footprint(self, space):
        shape = self.shape(space)
        if shape is None:
            return None
        try:
            return self._footprint_of(ifcopenshell.util.shape.get_vertices(shape.geometry),
                                      ifcopenshell.util.shape.get_faces(shape.geometry))
        except Exception:  # noqa: BLE001 - degenerate mesh
            return None

    @staticmethod
    def _footprint_of(vertices, faces):
        """Plan union of the mesh's triangles, built in one vectorised
        shapely call (47,792 one-at-a-time Polygon() calls cost 1.5 s on
        corpus model 0101)."""
        try:
            xy = vertices[:, :2]
            triangles = shapely.polygons(xy[faces])
            union = shapely.union_all(triangles[shapely.is_valid(triangles) & (shapely.area(triangles) > 1e-9)])
        except Exception:  # noqa: BLE001 - degenerate mesh
            return None
        if union.is_empty:
            return None
        if union.geom_type == "MultiPolygon":
            union = max(union.geoms, key=lambda g: g.area)
        return union if union.area > 0 else None

    # ---- properties, memoised per element ----
    def qtos(self, element):
        """get_psets(element, qtos_only=True) once per element, through the model session."""
        try:
            return ModelSession.current(self.model).psets(element, qtos_only=True)
        except Exception:  # noqa: BLE001 - as before: a failing element reads as no quantities
            return {}

    def text(self, element):
        """The lowercased name text the vocabulary matches, once per element:
        vocabulary.space_text for a space, the Neufert selector's full-segment
        element text for anything else (42 selector runs over 692 rooms
        rebuilt it 22,391 times on corpus model 0101, 0.8 s)."""
        key = element.id()
        if key not in self._texts:
            if element.is_a("IfcSpace"):
                self._texts[key] = vocabulary.space_text(element)
            else:
                from .select import element_text  # lazy: select imports measures
                self._texts[key] = element_text(element)
        return self._texts[key]

    def psets(self, element):
        """get_psets(element) once per element, through the model session: the
        gates, the measures, the facts AND the detectors all read the same
        doors and spaces several times."""
        try:
            return ModelSession.current(self.model).psets(element)
        except Exception:  # noqa: BLE001 - as before: a failing element reads as no property sets
            return {}

    def property_value(self, element, names):
        """properties.property_value through the cache: the first non-None
        value of any of `names` across every property set."""
        for pset in self.psets(element).values():
            for key, value in pset.items():
                if key in names and value is not None:
                    return value
        return None

    def pset_value(self, element, pset_name, prop):
        return (self.psets(element).get(pset_name) or {}).get(prop)

    # ---- storeys ----
    def storey_of(self, element):
        key = element.id()
        if key not in self._storey_cache:
            try:
                self._storey_cache[key] = get_storey(element, parent_container=True)
            except Exception:  # noqa: BLE001 - an entity without Decomposes
                self._storey_cache[key] = None
        return self._storey_cache[key]

    @property
    def storeys_sorted(self):
        if self._storeys_sorted is None:
            storeys = [s for s in self.model.by_type("IfcBuildingStorey") if s.Elevation is not None]
            self._storeys_sorted = sorted(storeys, key=lambda s: (s.Elevation, s.GlobalId))
        return self._storeys_sorted

    def storey_elevation_m(self, storey):
        return None if storey.Elevation is None else float(storey.Elevation) * self.length_scale

    def storey_name(self, storey):
        return storey.Name if storey is not None and storey.Name else (storey.GlobalId if storey else "?")

    # ---- facts ----
    def fact(self, name, build):
        if name not in self._facts:
            self._facts[name] = build(self)
        return self._facts[name]
