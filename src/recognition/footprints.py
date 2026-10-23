"""One slab or roof shape's plan footprint, shared since 2026-10-09 by
`envelope` and `lighting_clusters`, which carried identical copies.

`info_polygon(info)` builds the footprint from ONE element's own edges,
which always form a single ring (an element's side faces wrap around it
once). Pooling several elements' edges into one graph was the old
single-footprint-per-level approach. Z is ignored: plan view only, like
every footprint in this package. Returns None when no valid closed loop
exists.

`find_closed_loops` enumerates every simple cycle of the edge graph
(networkx `simple_cycles`), which is exponential in the mesh size. A
tessellated slab in tumgni_all/0233.ifc (now 0154) has 1,096 edges, and one
call ran past 20 minutes, stalling a whole library run. Corpus slabs have at
most 182 edges and stay on the exact path.
Beyond CLOSED_LOOP_EDGE_LIMIT the footprint comes from shapely's planar
`polygonize` instead, which is near-linear and gives the same outline. The
limit sits just above the corpus maximum because the blow-up starts well
below 400 edges (tumgni_all/0469: 27 s per detector at 200 to 400).
"""

from shapely.geometry import LineString, Polygon
from shapely.ops import polygonize, unary_union

from toolsQuickUtils import find_closed_loops

CLOSED_LOOP_EDGE_LIMIT = 200


def polygonized_footprint(xy_segments):
    """Largest face of the planar graph formed by the segments (shapely
    polygonize), for meshes too large for find_closed_loops."""
    try:
        lines = unary_union([LineString([tuple(a), tuple(b)]) for a, b in xy_segments if tuple(a) != tuple(b)])
        faces = [face for face in polygonize(lines) if face.is_valid and face.area > 0]
    except Exception:
        return None
    return max(faces, key=lambda face: face.area) if faces else None


def info_polygon(info):
    xy_segments = [(p1[:2], p2[:2]) for p1, p2 in info["location"]]
    if len(xy_segments) > CLOSED_LOOP_EDGE_LIMIT:
        return polygonized_footprint(xy_segments)
    loops = find_closed_loops(xy_segments)
    polygons = []
    for loop in loops:
        try:
            polygon = Polygon(loop)
            if not polygon.is_valid:
                polygon = polygon.buffer(0)
            if polygon.area > 0:
                polygons.append(polygon)
        except Exception:
            continue
    return max(polygons, key=lambda p: p.area) if polygons else None
