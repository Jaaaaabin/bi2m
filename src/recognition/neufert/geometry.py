"""Geometry primitives of the Neufert measures: fn(ctx, element) -> float
or None, each one SI (metres, m2, m3, degrees) from the context's cached
shapes, world frame (ctx.shape) or the element's own frame
(ctx.shape(local=True)). measures.GEOMETRY maps the chain-step names to
them; a card reaches one through a primitive's chain, never directly.
Split out of measures.py on 2026-10-19 when the flight width brought the
module past 650 lines (codebase-refactoring pass).

Window-to-space assignment for `space.glazed_area` is nearest-wins within
WINDOW_REACH_M, the reach daylight_rooms.py measured (0.6 m covers 100 % of
windows on both corpus models it was tuned on with 0.15 m to spare).
"""

import math

import ifcopenshell.util.element
import ifcopenshell.util.placement
import ifcopenshell.util.representation
import ifcopenshell.util.shape
import numpy as np
import shapely
from shapely.geometry import Point

from ifc_units import placement_xy, placement_xyz

from ..spaces import index_by_storey, nearest_space

WINDOW_REACH_M = 0.6  # daylight_rooms.DEFAULT_WINDOW_REACH_M, measured there
# A model whose windows sit this far from every room footprint (median over
# its windows) has a placement chain the footprints do not follow; on 26 of
# 335 corpus models the median was above 2 m while doors landed at 0 m on
# six of them. Glazing is not judged there.
WINDOW_FRAME_SUSPECT_M = 2.0
# Flight run width (geom_flight_width, corpus probe of 2026-10-19 on 514
# flights of 42 corpus models): the plan footprint is rasterised at this
# step, each point goes to its nearest walking-line segment, and the width
# is the extent across the longest segment of at least FLIGHT_SEGMENT_MIN_M.
FLIGHT_RASTER_M = 0.05
FLIGHT_SEGMENT_MIN_M = 0.3
FLIGHT_MIN_POINTS = 10


# ---- geometry primitives: fn(ctx, element) -> float | None ----

def _geometry(ctx, element):
    shape = ctx.shape(element)
    return None if shape is None else shape.geometry


def geom_z_extent(ctx, element):
    if element.is_a("IfcSpace"):
        return ctx.space_z_extent(element)
    geometry = _geometry(ctx, element)
    if geometry is None:
        return None
    top = ifcopenshell.util.shape.get_top_elevation(geometry)
    bottom = ifcopenshell.util.shape.get_bottom_elevation(geometry)
    return None if top is None or bottom is None else float(top - bottom)


def geom_footprint_area(ctx, element):
    if element.is_a("IfcSpace"):
        polygon = ctx.polygons.get(element.GlobalId)
        if polygon is not None:
            return float(polygon.area)
    geometry = _geometry(ctx, element)
    return None if geometry is None else float(ifcopenshell.util.shape.get_footprint_area(geometry))


def geom_volume(ctx, element):
    geometry = _geometry(ctx, element)
    if geometry is None:
        return None
    try:
        return float(ifcopenshell.util.shape.get_volume(geometry))
    except Exception:  # noqa: BLE001 - open mesh
        return None


def _obb_sides(ctx, element):
    polygon = ctx.polygons.get(element.GlobalId) if element.is_a("IfcSpace") else None
    if polygon is None or polygon.is_empty:
        return None
    coords = list(polygon.minimum_rotated_rectangle.exterior.coords)
    if len(coords) < 4:
        return None
    a = Point(coords[0]).distance(Point(coords[1]))
    b = Point(coords[1]).distance(Point(coords[2]))
    return min(a, b), max(a, b)


def geom_obb_short(ctx, element):
    sides = _obb_sides(ctx, element)
    return None if sides is None else float(sides[0])


def geom_obb_long(ctx, element):
    sides = _obb_sides(ctx, element)
    return None if sides is None else float(sides[1])


def geom_roof_pitch(ctx, element):
    """Pitch in degrees from the slab's triangulated faces: the area-weighted
    mean of the upward faces' normals (nz > 0.2) against vertical. A flat
    slab's top faces have nz = 1, a 30 degree roof's cos(30). None without
    geometry or without an upward face."""
    geometry = _geometry(ctx, element)
    if geometry is None:
        return None
    try:
        vertices = ifcopenshell.util.shape.get_vertices(geometry)
        faces = ifcopenshell.util.shape.get_faces(geometry)
    except Exception:  # noqa: BLE001
        return None
    if len(faces) == 0:
        return None
    tri = vertices[faces]
    normals = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    lengths = np.linalg.norm(normals, axis=1)
    keep = lengths > 0
    if not keep.any():
        return None
    nz = normals[keep][:, 2] / lengths[keep]
    areas = lengths[keep] / 2.0
    upward = nz > 0.2
    if not upward.any():
        return None
    mean_nz = float((nz[upward] * areas[upward]).sum() / areas[upward].sum())
    return math.degrees(math.acos(max(-1.0, min(1.0, mean_nz))))


def geom_sill_height(ctx, element):
    """Window placement z above its storey's elevation, metres."""
    storey = ctx.storey_of(element)
    if storey is None:
        return None
    xyz = placement_xyz(element, ctx.length_scale)
    elevation = ctx.storey_elevation_m(storey)
    if xyz is None or elevation is None:
        return None
    return float(xyz[2] - elevation)


def _glazing_by_space(ctx):
    """{"areas": space GUID -> glazed m2 of the windows nearest to it within
    WINDOW_REACH_M on its storey, "windows": space GUID -> their GUIDs
    (the `related: windows` facet, 2026-10-20), "ambiguous": the windows within
    reach of two or more rooms, "median_m": median window-to-room
    distance, "suspect": the median exceeds WINDOW_FRAME_SUSPECT_M}; once
    per model. Footprints and placements are both in the context's world
    frame."""
    spaces = ctx.model.by_type("IfcSpace")
    windows = ctx.model.by_type("IfcWindow")
    result = {"areas": {}, "windows": {}, "ambiguous": set(), "median_m": None, "suspect": False}
    if not spaces or not windows or not ctx.polygons:
        return result
    by_storey = index_by_storey(spaces, ctx.polygons)
    scale = ctx.length_scale
    distances = []
    for window in windows:
        storey = ifcopenshell.util.element.get_container(window, ifc_class="IfcBuildingStorey")
        width, height = window.OverallWidth, window.OverallHeight
        if storey is None or not width or not height:
            continue
        xy = placement_xy(window, scale)
        if xy is None:
            continue
        nearest, distance = nearest_space(Point(*xy), by_storey.get(storey.GlobalId, []), ctx.polygons)
        if nearest is None:
            continue
        distances.append(distance)
        if distance > WINDOW_REACH_M:
            continue
        result["areas"][nearest] = result["areas"].get(nearest, 0.0) + float(width) * float(height) * scale * scale
        result["windows"].setdefault(nearest, []).append(window.GlobalId)
        point = Point(*xy)
        # 2026-10-20: 18 % of corpus windows lie within reach of two or more rooms; there the
        # assignment is a tie-break, and the `related: windows` facet says so on the record.
        if sum(1 for guid in by_storey.get(storey.GlobalId, []) if ctx.polygons[guid].distance(point) <= WINDOW_REACH_M) >= 2:
            result["ambiguous"].add(window.GlobalId)
    if distances:
        distances.sort()
        result["median_m"] = distances[len(distances) // 2]
        result["suspect"] = result["median_m"] > WINDOW_FRAME_SUSPECT_M
    return result


def _local_extents(ctx, element):
    """(short, long) horizontal extents of the element's own frame: a wall's
    thickness and length, a flight's width and run, however it is rotated in
    the world (util.shape's get_x/get_y on a local-frame shape)."""
    shape = ctx.shape(element, local=True)
    if shape is None:
        return None
    x = ifcopenshell.util.shape.get_x(shape.geometry)
    y = ifcopenshell.util.shape.get_y(shape.geometry)
    return (min(x, y), max(x, y))


def geom_local_short(ctx, element):
    extents = _local_extents(ctx, element)
    return None if extents is None else float(extents[0])


def geom_local_long(ctx, element):
    extents = _local_extents(ctx, element)
    return None if extents is None else float(extents[1])


def geom_max_side_area(ctx, element):
    """The largest of the element's X, Y and Z side areas in its own frame:
    a wall's face, a window's pane side (util.shape.get_max_side_area)."""
    shape = ctx.shape(element, local=True)
    return None if shape is None else float(ifcopenshell.util.shape.get_max_side_area(shape.geometry))


def geom_outer_surface_area(ctx, element):
    """All sides except top and bottom in the element's frame (util.shape)."""
    shape = ctx.shape(element, local=True)
    return None if shape is None else float(ifcopenshell.util.shape.get_outer_surface_area(shape.geometry))


def geom_footprint_perimeter(ctx, element):
    geometry = _geometry(ctx, element)
    return None if geometry is None else float(ifcopenshell.util.shape.get_footprint_perimeter(geometry))


def geom_storey_rise(ctx, element):
    """Rise of the element's storey above the ground storey: the lowest
    storey at or above 0, else the lowest (K15's drop, approximated by
    the storey the railing stands on; 2026-10-20). None without storeys."""
    storey = ctx.storey_of(element) if not element.is_a("IfcBuildingStorey") else element
    if storey is None:
        return None
    elevations = [e for e in (ctx.storey_elevation_m(s) for s in ctx.storeys_sorted) if e is not None]
    own = ctx.storey_elevation_m(storey)
    if not elevations or own is None:
        return None
    ground = min([e for e in elevations if e >= 0] or elevations)
    return own - ground


def geom_storey_elevation(ctx, element):
    """A storey's elevation from its placement, else its Elevation attribute
    (util.placement.get_storey_elevation), metres."""
    try:
        return float(ifcopenshell.util.placement.get_storey_elevation(element)) * ctx.length_scale
    except Exception:  # noqa: BLE001 - not a storey, or no placement and no Elevation
        return None


def _axis_points(ctx, element):
    """The element's walking line (its Axis representation, IfcPolyline or
    IfcIndexedPolyCurve, possibly inside an IfcGeometricSet as Revit writes
    it) as an (n, 2) array in the element's own frame, metres; the longest
    curve when there are several; None without one."""
    representation = ifcopenshell.util.representation.get_representation(element, "Model", "Axis")
    if representation is None:
        representation = ifcopenshell.util.representation.get_representation(element, "Plan", "Axis")
    if representation is None:
        return None
    best = []
    for item in representation.Items:
        for curve in (item.Elements if item.is_a("IfcGeometricSet") else [item]):
            if curve.is_a("IfcPolyline"):
                coords = [p.Coordinates for p in curve.Points]
            elif curve.is_a("IfcIndexedPolyCurve"):
                coords = list(curve.Points.CoordList)
            else:
                continue
            if len(coords) > len(best):
                best = coords
    if len(best) < 2:
        return None
    return np.array([[c[0], c[1]] for c in best], dtype=float) * ctx.length_scale


def geom_walk_turn(ctx, element):
    """Total turn of the walking line in degrees: the sum of the absolute
    heading changes along the Axis polyline (an IfcStair without its own
    Axis reads the largest turn among its flights). A corpus probe
    (2026-10-20): Revit types any stair with an arc as SPIRAL_STAIR, 184
    stairs in 64 models, but only 38 of them turn 270 degrees or more; the
    K14 scenario is SPIRAL_STAIR AND a turn of at least 270. None without
    a walking line of three points or more."""
    points = _axis_points(ctx, element)
    if points is None and element.is_a("IfcStair"):
        turns = []
        for part in ifcopenshell.util.element.get_decomposition(element):
            if part.is_a("IfcStairFlight"):
                turn = geom_walk_turn(ctx, part)
                if turn is not None:
                    turns.append(turn)
        return max(turns) if turns else None
    if points is None or len(points) < 3:
        return None
    vectors = np.diff(points, axis=0)
    lengths = np.hypot(vectors[:, 0], vectors[:, 1])
    vectors = vectors[lengths > 0]
    if len(vectors) < 2:
        return None
    headings = np.arctan2(vectors[:, 1], vectors[:, 0])
    changes = np.diff(headings)
    changes = (changes + np.pi) % (2 * np.pi) - np.pi
    return float(np.degrees(np.abs(changes).sum()))


def _local_footprint(ctx, element):
    shape = ctx.shape(element, local=True)
    if shape is None:
        return None
    try:
        vertices = ifcopenshell.util.shape.get_vertices(shape.geometry)
        faces = ifcopenshell.util.shape.get_faces(shape.geometry)
    except Exception:  # noqa: BLE001
        return None
    if len(faces) == 0:
        return None
    triangles = shapely.polygons(vertices[faces][:, :, :2])
    triangles = triangles[shapely.is_valid(triangles) & (shapely.area(triangles) > 0)]
    if len(triangles) == 0:
        return None
    try:
        polygon = shapely.union_all(triangles)
    except Exception:  # noqa: BLE001 - GEOS topology exception on a degenerate mesh (corpus 0144): no width
        return None
    return None if polygon.is_empty else polygon


def geom_flight_width(ctx, element):
    """Usable run width of a flight: the extent of its plan footprint across
    the longest segment of its walking line, each raster point counted for
    the segment nearest to it (so a U- or L-shaped flight body that is the
    whole stair gives one run's width, not the stair's; the OBB short side
    was wrong by more than 0.3 m on 78 of 502 corpus flights that way).
    Without a walking line: the body's own short extent only when the body
    is a single straight run (longer than wide); else None."""
    polygon = _local_footprint(ctx, element)
    if polygon is None:
        return None
    axis = _axis_points(ctx, element)
    if axis is None:
        extents = _local_extents(ctx, element)
        return None if extents is None or extents[1] <= extents[0] else float(extents[0])
    segments = [(a, b) for a, b in zip(axis[:-1], axis[1:]) if np.linalg.norm(b - a) >= FLIGHT_SEGMENT_MIN_M]
    if not segments:
        return None
    minx, miny, maxx, maxy = polygon.bounds
    xs, ys = np.meshgrid(np.arange(minx, maxx, FLIGHT_RASTER_M), np.arange(miny, maxy, FLIGHT_RASTER_M))
    X, Y = xs.ravel(), ys.ravel()
    inside = shapely.contains_xy(polygon, X, Y)
    points = np.c_[X[inside], Y[inside]]
    if len(points) < FLIGHT_MIN_POINTS:
        return None
    distances = []
    for a, b in segments:
        ab = b - a
        t = np.clip(((points - a) @ ab) / (ab @ ab), 0.0, 1.0)
        distances.append(np.linalg.norm(points - (a + np.outer(t, ab)), axis=1))
    owner = np.argmin(np.array(distances), axis=0)
    longest = max(range(len(segments)), key=lambda i: np.linalg.norm(segments[i][1] - segments[i][0]))
    a, b = segments[longest]
    length = np.linalg.norm(b - a)
    direction = (b - a) / length
    normal = np.array([-direction[1], direction[0]])
    owned = points[owner == longest]
    along = (owned - a) @ direction
    owned = owned[(along >= 0.0) & (along <= length)]
    if len(owned) < FLIGHT_MIN_POINTS:
        return None
    across = owned @ normal
    return float(across.max() - across.min() + FLIGHT_RASTER_M)


def geom_glazed_area(ctx, element):
    """Glazed area assigned to the space, or None (no data) when the model
    has no IfcWindow, the space has no footprint, no window was assigned to
    the room (daylight_rooms' rule: a windowless room is not a glazing
    failure), or the model's windows do not meet its footprints at all
    (WINDOW_FRAME_SUSPECT_M)."""
    if not ctx.model.by_type("IfcWindow") or element.GlobalId not in ctx.polygons:
        return None
    glazing = ctx.fact("glazing_by_space", _glazing_by_space)
    if glazing["suspect"]:
        return None
    return glazing["areas"].get(element.GlobalId)


GEOMETRY = {
    "z_extent": geom_z_extent,
    "footprint_area": geom_footprint_area,
    "volume": geom_volume,
    "obb_short": geom_obb_short,
    "obb_long": geom_obb_long,
    "sill_height": geom_sill_height,
    "glazed_area": geom_glazed_area,
    "roof_pitch": geom_roof_pitch,
    "local_short": geom_local_short,
    "local_long": geom_local_long,
    "max_side_area": geom_max_side_area,
    "outer_surface_area": geom_outer_surface_area,
    "footprint_perimeter": geom_footprint_perimeter,
    "storey_elevation": geom_storey_elevation,
    "storey_rise": geom_storey_rise,
    "walk_turn": geom_walk_turn,
    "flight_width": geom_flight_width,
}
