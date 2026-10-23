"""Rooms per storey and the nearest room to a point, shared since 2026-10-09
by `daylight_rooms`, `furniture_occupancy` and `sanitary_provision`.

The footprints themselves come from `access_graph.space_polygons`; this
module only indexes and searches them.

`index_by_storey(spaces, polygons)` keeps a space only when it has a
storey and a footprint, in the order `spaces` lists them. It returns the
defaultdict the three copies built, so a caller that indexes a missing
storey behaves as before.

`nearest_space(point, space_guids, polygons)` returns (guid, distance) of
the closest footprint, the first one on a tie, or (None, None) when there
are no candidates. It stops at the first footprint that contains the point:
nothing can be strictly nearer than 0, so the answer is the same as a full
scan, and `daylight_rooms`, whose copy scanned everything, gets identical
results.
"""

from collections import defaultdict

from .storeys import get_storey


def index_by_storey(spaces, polygons):
    by_storey = defaultdict(list)
    for space in spaces:
        storey = get_storey(space)
        if storey is not None and space.GlobalId in polygons:
            by_storey[storey.GlobalId].append(space.GlobalId)
    return by_storey


def nearest_space(point, space_guids, polygons):
    nearest, nearest_distance = None, None
    for guid in space_guids:
        distance = polygons[guid].distance(point)
        if nearest_distance is None or distance < nearest_distance:
            nearest, nearest_distance = guid, distance
        if nearest_distance == 0:
            break
    return nearest, nearest_distance
