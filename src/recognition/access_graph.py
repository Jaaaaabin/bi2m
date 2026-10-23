"""Shared door/space access graph - the one piece of recognition
infrastructure in this package that more than one detector builds on.

Factored out of space_access.py when unit_typology.py needed the same
structure. It was the first exception to the per-detector duplication
convention the package followed until 2026-10-09, when the small helpers
were shared as well (storeys.py, chains.py, components.py, properties.py,
footprints.py, spaces.py, census.py; the four verified detectors keep their
own copies). Here sharing was never optional: building this graph means a
full ifcopenshell triangulation pass over every IfcSpace in the model -
302 of them in data/test_5.ifc - and duplicating that would double the cost
of a recognition run for no benefit.

See space_access.py's module docstring for the measured evidence behind
DEFAULT_DOOR_MARGIN_M and for why the association is geometric rather than
read from IfcRelSpaceBoundary (that relation exists in only 1 of the 6
corpus models).
"""

from collections import Counter, defaultdict

from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from extraction.geometry_iteration import iterate_shapes
from extraction.model_loader import configure_settings
from ifc_units import length_scale, placement_xy, placement_xyz, to_metres

from .storeys import get_storey

# The measured plateau at which a door's reach crosses exactly one wall -
# see space_access.py's docstring for the full sweep across 4 models.
DEFAULT_DOOR_MARGIN_M = 0.4
MIN_TRIANGLE_AREA = 1e-6
# A space whose floor sits this far from its container storey's elevation,
# while another storey's elevation is within STOREY_SNAP_M of it, is treated
# as attached to the wrong storey object (private-corpus model 0007: spaces on "Level 1"
# with their floor 3.2 m below it, at "Level 0"). Conservative on purpose:
# a correctly attached space never moves.
STOREY_MISATTACH_M = 1.0
STOREY_SNAP_M = 0.6
# A shape-anchored door is accepted only when it meets one or two rooms - the
# physically possible answers. Models whose space geometry sits in a local
# frame (private-corpus models 0017, 0211: every floor at z=0, footprints stacked in
# plan) make a shape centre "reach" 59 rooms at once; that is not a fix.
SHAPE_ANCHOR_MAX_REACH = 2
# Revit exports Areas and Zones as IfcSpace next to the Rooms they contain, and
# some files carry the same room twice. In private-corpus model 0180 76 of 77 spaces on a
# storey overlap another by more than 30 % of their area. A space whose
# footprint is covered >= CONTAINER_COVER by >= 2 other spaces it encloses is
# a container, not a room; two footprints overlapping >= DUPLICATE_OVERLAP of
# both areas are one room. Both stay in `polygons`/`space_by_guid` but leave
# the graph. No corpus model has either (checked 2026-09-23).
CONTAINER_COVER = 0.6
CONTAINER_MIN_CHILDREN = 2
CONTAINED_FRACTION = 0.8
DUPLICATE_OVERLAP = 0.9
# When more than this share of a storey's spaces would count as containers the
# footprints themselves are degenerate (private-corpus model 0180: 295 of 385 spaces
# "contain" others), and thinning them would only hide that. The storey is
# left as it is and recorded in `degenerate_storeys`.
DEGENERATE_CONTAINER_SHARE = 0.3


def space_label(space):
    parts = [part for part in (space.Name, space.LongName) if part]
    return " ".join(parts) or space.GlobalId


def space_polygons(model, spaces):
    """One unioned 2D footprint per space, from its triangulated shape.

    Triangles are unioned rather than convex-hulled: an L-shaped room's hull
    would swallow the corridor in its notch and invent adjacencies that do
    not exist."""
    return {guid: entry["polygon"] for guid, entry in space_footprints(model, spaces).items()}


def space_footprints(model, spaces):
    """{guid: {"polygon", "z_min"}} - the footprint plus the floor level of
    the shape in metres (ifcopenshell.geom output is metres whatever the
    file's unit). `z_min` is what lets a space be assigned to the storey its
    geometry is actually on (see AccessGraph._storey_for_space)."""
    settings = configure_settings("triangle")
    footprints = {}
    for shape in iterate_shapes(settings, model, spaces, "triangle"):
        geometry = shape.geometry
        verts, faces = geometry.verts, geometry.faces
        z_min = min(verts[2::3]) if len(verts) >= 3 else None
        triangles = []
        for index in range(0, len(faces), 3):
            corners = []
            for offset in range(3):
                vertex = faces[index + offset]
                corners.append((verts[3 * vertex], verts[3 * vertex + 1]))
            try:
                triangle = Polygon(corners)
            except Exception:
                continue
            if triangle.is_valid and triangle.area > MIN_TRIANGLE_AREA:
                triangles.append(triangle)
        if not triangles:
            continue
        try:
            footprints[shape.guid] = {"polygon": unary_union(triangles).buffer(0), "z_min": z_min}
        except Exception:
            continue
    return footprints


def shape_centres(model, elements):
    """{guid: (x, y)} - the plan centre of each element's triangulated shape,
    in metres. The anchor of last resort for a door whose placement chain
    resolves somewhere else (private-corpus models 0017, 0113, 0211: placements 16-80 m
    from every room, shapes at 0.0 m from one)."""
    if not elements:
        return {}
    settings = configure_settings("triangle")
    centres = {}
    for shape in iterate_shapes(settings, model, elements, "triangle"):
        verts = shape.geometry.verts
        if len(verts) < 3:
            continue
        xs, ys = verts[0::3], verts[1::3]
        centres[shape.guid] = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
    return centres


def connected_groups(nodes, edges):
    """Union-find over door edges - the same mechanism structural.py/
    envelope.py/window_alignment.py use, here over a room graph rather than
    a vertical stack."""
    parent = {node: node for node in nodes}

    def find(node):
        root = node
        while parent[root] != root:
            root = parent[root]
        while parent[node] != root:
            parent[node], node = root, parent[node]
        return root

    for left, right in edges:
        if left in parent and right in parent:
            a, b = find(left), find(right)
            if a != b:
                parent[a] = b

    groups = defaultdict(list)
    for node in nodes:
        groups[find(node)].append(node)
    return list(groups.values())


class AccessGraph:
    """Door/space adjacency for one model.

    `spaces_by_storey`   storey guid -> [space guid] (only spaces with a
                         usable footprint)
    `door_links`         door guid -> (storey guid, [space guids reached])
    `door_points`        door guid -> its (x, y) placement IN METRES (the
                         file's own unit goes through ifc_units.placement_xy;
                         before 2026-09-22 a millimetre model put every door
                         a thousand times too far from every room), kept so a
                         path through a doorway can be given a real length
    `unit_scale`         metres per project unit (1.0, 0.001, 0.01, 0.3048)
    `door_reach`         Counter: how many rooms each door touched -> doors.
                         A healthy model is dominated by 2. All-zero means
                         doors and rooms do not share a frame (units, or a
                         placement chain the footprints do not follow).
    `median_door_to_room_m`  median distance from a door to its nearest
                         same-storey footprint; None when nothing could be
                         measured. The sanity figure behind `door_reach`.
    `doors_by_pair`      (space guid, space guid) -> [door guid]
    `space_by_guid`      guid -> the IfcSpace entity
    `polygons`           guid -> the space's unioned 2D footprint. Retained
                         rather than discarded after construction because
                         egress_reachability.py needs room centroids to put
                         a metric length on a path; building them is the
                         expensive part and there is no reason to do it
                         twice.
    `door_anchor_source` door guid -> "placement" | "shape". A door is
                         anchored on its placement; when that meets no room
                         on its storey and the centre of its own shape does,
                         the shape wins (the Revit exports whose door
                         placement chain resolves tens of metres away).
    `reassigned_spaces`  space guid -> (from storey guid, to storey guid) for
                         spaces whose floor geometry sits on another storey
                         than their container says (STOREY_MISATTACH_M).
    `doors_by_storey`    storey guid -> [door guid], every door with a
                         placement, including storeys without any room -
                         space_access reports those storeys as a whole.
    `container_spaces`   space guid -> [enclosed space guids]: Area/Zone-like
                         spaces excluded from the graph (CONTAINER_COVER).
    `duplicate_spaces`   space guid -> the guid it duplicates and yields to.
    `degenerate_storeys` storey guids whose room footprints overlap so much
                         that no room can be told from another - nothing built
                         on them should be trusted (DEGENERATE_CONTAINER_SHARE).
    """

    def __init__(self, model, door_margin_m=DEFAULT_DOOR_MARGIN_M):
        self.model = model
        self.door_margin_m = door_margin_m
        self.spaces_by_storey = defaultdict(list)
        self.door_links = {}
        self.door_points = {}
        self.doors_by_pair = defaultdict(list)
        self.space_by_guid = {}
        self.polygons = {}
        self.unit_scale = length_scale(model)
        self.door_reach = Counter()
        self.median_door_to_room_m = None
        self.door_anchor_source = {}
        self.reassigned_spaces = {}
        self.doors_by_storey = defaultdict(list)
        self.container_spaces = {}
        self.duplicate_spaces = {}
        self.degenerate_storeys = set()
        self._build()

    def _leaf_rooms(self, storey_guid, guids, polygons):
        """The rooms of one storey without Area/Zone-like containers and
        without duplicates (see CONTAINER_COVER / DUPLICATE_OVERLAP). A storey
        where that would remove most rooms is degenerate and left untouched."""
        items = [(guid, polygons[guid]) for guid in guids if polygons[guid].area > 0]
        keep = []
        containers = {}
        duplicates = {}
        for guid, poly in sorted(items, key=lambda item: item[0]):
            enclosed = [
                other for other, q in items
                if other != guid and poly.intersection(q).area >= CONTAINED_FRACTION * q.area and q.area < poly.area
            ]
            if len(enclosed) >= CONTAINER_MIN_CHILDREN:
                covered = unary_union([polygons[other] for other in enclosed]).intersection(poly).area
                if covered >= CONTAINER_COVER * poly.area:
                    containers[guid] = sorted(enclosed)
                    continue
            twin = next(
                (kept for kept in keep
                 if poly.intersection(polygons[kept]).area >= DUPLICATE_OVERLAP * max(poly.area, polygons[kept].area)),
                None,
            )
            if twin is not None:
                duplicates[guid] = twin
                continue
            keep.append(guid)
        if items and len(containers) > DEGENERATE_CONTAINER_SHARE * len(items):
            self.degenerate_storeys.add(storey_guid)
            return list(guids)
        self.container_spaces.update(containers)
        self.duplicate_spaces.update(duplicates)
        return keep

    def _storey_elevations(self):
        """[(storey guid, elevation in metres)] for storeys with an elevation."""
        out = []
        for storey in self.model.by_type("IfcBuildingStorey"):
            if storey.Elevation is not None:
                out.append((storey.GlobalId, to_metres(storey.Elevation, self.unit_scale)))
        return out

    def _storey_for_space(self, space, z_min, elevations):
        """The container storey, unless the space's own floor is clearly on
        another storey's level (see STOREY_MISATTACH_M). The floor level is
        trusted only when the space's placement agrees with its geometry: a
        model whose space shapes are in a local frame (floor at z=0 on every
        storey) would otherwise have every space moved to the lowest storey."""
        storey = get_storey(space)
        if storey is None or z_min is None or not elevations:
            return storey
        placement = placement_xyz(space, self.unit_scale)
        if placement is None or abs(placement[2] - z_min) > STOREY_SNAP_M:
            return storey
        by_guid = dict(elevations)
        own = by_guid.get(storey.GlobalId)
        if own is None or abs(own - z_min) <= STOREY_MISATTACH_M:
            return storey
        nearest_guid, nearest_elevation = min(elevations, key=lambda item: abs(item[1] - z_min))
        if nearest_guid != storey.GlobalId and abs(nearest_elevation - z_min) <= STOREY_SNAP_M:
            self.reassigned_spaces[space.GlobalId] = (storey.GlobalId, nearest_guid)
            return self.model.by_guid(nearest_guid)
        return storey

    def _build(self):
        spaces = self.model.by_type("IfcSpace")
        doors = self.model.by_type("IfcDoor")
        if not spaces or not doors:
            return

        footprints = space_footprints(self.model, spaces)
        if not footprints:
            return
        polygons = {guid: entry["polygon"] for guid, entry in footprints.items()}
        self.polygons = polygons

        elevations = self._storey_elevations()
        self.space_by_guid = {space.GlobalId: space for space in spaces}
        for space in spaces:
            if space.GlobalId not in footprints:
                continue
            storey = self._storey_for_space(space, footprints[space.GlobalId]["z_min"], elevations)
            if storey is not None:
                self.spaces_by_storey[storey.GlobalId].append(space.GlobalId)
        # Leaf rooms only: containers and duplicates leave the graph (kept in
        # `polygons` and `space_by_guid` for anything that wants them).
        for storey_guid, guids in list(self.spaces_by_storey.items()):
            self.spaces_by_storey[storey_guid] = self._leaf_rooms(storey_guid, guids, polygons)

        # Pass 1: placement anchors. Pass 2: for every door that met no room,
        # try the centre of its own shape (one geometry pass over just those
        # doors) and keep it only if it does meet one - so a door whose
        # placement already worked is untouched, and a degenerate shape
        # (test_3: door shapes at a local origin) changes nothing.
        placed = []
        for door in doors:
            storey = get_storey(door)
            if storey is None:
                continue
            xy = placement_xy(door, self.unit_scale)
            if xy is None:
                continue
            placed.append((door, storey.GlobalId, xy))
            self.doors_by_storey[storey.GlobalId].append(door.GlobalId)

        def reach_of(storey_guid, xy):
            point = Point(*xy)
            distances = [(polygons[guid].distance(point), guid) for guid in self.spaces_by_storey.get(storey_guid, [])]
            reached = [guid for distance, guid in distances if distance <= self.door_margin_m]
            return reached, (min(distance for distance, _ in distances) if distances else None)

        first = {door.GlobalId: (storey_guid, xy, *reach_of(storey_guid, xy)) for door, storey_guid, xy in placed}
        retry = [door for door, storey_guid, _ in placed if not first[door.GlobalId][2] and self.spaces_by_storey.get(storey_guid)]
        centres = shape_centres(self.model, retry) if retry else {}

        nearest = []
        for door, storey_guid, xy in placed:
            _, _, reached, nearest_distance = first[door.GlobalId]
            source = "placement"
            centre = centres.get(door.GlobalId)
            if not reached and centre is not None:
                reached_by_shape, nearest_by_shape = reach_of(storey_guid, centre)
                if 1 <= len(reached_by_shape) <= SHAPE_ANCHOR_MAX_REACH:
                    xy, reached, nearest_distance, source = centre, reached_by_shape, nearest_by_shape, "shape"
            self.door_points[door.GlobalId] = xy
            self.door_anchor_source[door.GlobalId] = source
            if nearest_distance is not None:
                nearest.append(nearest_distance)
            self.door_reach[len(reached)] += 1
            self.door_links[door.GlobalId] = (storey_guid, reached)
            if len(reached) >= 2:
                for i in range(len(reached)):
                    for j in range(i + 1, len(reached)):
                        pair = tuple(sorted((reached[i], reached[j])))
                        self.doors_by_pair[pair].append(door.GlobalId)
        if nearest:
            nearest.sort()
            self.median_door_to_room_m = nearest[len(nearest) // 2]

    def centroid(self, space_guid):
        """A point guaranteed to lie INSIDE the room (shapely's
        representative_point, not the centroid proper - an L-shaped room's
        true centroid can fall outside it)."""
        polygon = self.polygons.get(space_guid)
        if polygon is None:
            return None
        point = polygon.representative_point()
        return (point.x, point.y)

    def usable(self):
        return bool(self.spaces_by_storey) and bool(self.door_links)

    def storey_name(self, storey_guid):
        storey = self.model.by_guid(storey_guid)
        return storey.Name if storey and storey.Name else storey_guid

    def groups_for_storey(self, storey_guid):
        """Connected components of this storey's room graph, plus the set of
        spaces that any door actually touched."""
        storey_spaces = self.spaces_by_storey.get(storey_guid, [])
        edges = []
        touched = set()
        for door_guid, (door_storey, reached) in self.door_links.items():
            if door_storey != storey_guid or len(reached) < 2:
                continue
            touched.update(reached)
            for i in range(len(reached)):
                for j in range(i + 1, len(reached)):
                    edges.append(tuple(sorted((reached[i], reached[j]))))
        return connected_groups(storey_spaces, edges), touched

    def doors_within(self, group):
        group_set = set(group)
        return sorted({
            door_guid
            for pair, door_guids in self.doors_by_pair.items()
            if pair[0] in group_set and pair[1] in group_set
            for door_guid in door_guids
        })
