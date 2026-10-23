"""Declared reference grids (IfcGrid) as plan geometry, and the cells they cut.

Two token levels sit on top of a model's grid: L1 grid
words (src/modality/grid_words.py) and L0 facade bands. Both start here. This
module reads every IfcGrid a model declares, puts each axis into world plan
coordinates in metres, and splits the plane into cells: the bounded faces of
the noded axis arrangement.

Faces of the arrangement, not a U x V table, because one mechanism then covers
what declared grids actually do:
  - uneven bays and bands of twin axes (any spacing at all);
  - partial axes: an axis splits only the cells it crosses, and an axis that
    stops inside a cell splits nothing - it is recorded on that cell as an
    internal axis instead of being lost;
  - several IfcGrid objects that together make one system: their axes are
    unioned per storey, near-identical copies merged first;
  - rotated, skewed, radial and curved axes: nothing assumes two orthogonal
    families. Slots, row words and rhythm words need two straight families;
    any other arrangement still gets cells.
Text scan of the 16 uploaded models that declare a grid (data/uploads/,
2026-10-02): every axis is a straight two-point IfcIndexedPolyCurve or
IfcPolyline; three models carry two distinct grid objects whose axes overlap
(a2b650f1..., c99be381..., 32c49fb2...); c99be381... splits one line into three
axis pieces; 32c49fb2... adds sub-axes "1a" and "8a" 2 m off their primaries.
No declared arc exists in the sample. IfcOpenShell evaluates arcs: an
IfcArcIndex segment of radius 10 m came back as 57 points on the exact radius.

Frames. `ifcopenshell.geom.create_shape` evaluates an axis curve into metres in
the grid's own coordinate system, and `placement_matrix(grid, scale)` maps that
into world coordinates - the frame grid_words.world_settings() gives element
shapes. (extraction.model_loader.configure_settings does not: with IfcOpenShell
0.8.5 its attribute-style USE_WORLD_COORDS is ignored, so its shapes are in
local coordinates.) The recognition extraction cache is not used either: its
column positions are mapped-item offsets in a different frame.

Storeys. A grid contained in a storey (IfcRelContainedInSpatialStructure) is
active on that storey; Revit exports one copy per level. A grid contained in
no storey is active on every storey. A storey with neither borrows the union
of all the model's grids and says so (`gridSource: "borrowed"`), so a model
that attached its grid to one level still gets words on the others.

Determinism (docs/detectors.md rule 1): grids are read in GlobalId order,
axes are sorted by tag and geometry before merging, and every id is built
from axis tags, never from iteration order.
"""

from collections import defaultdict
import math

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element
import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import polygonize, unary_union

from ifc_units import length_scale, placement_matrix

# Conventions, not corpus measurements (docs/detectors.md rule 2 asks to say
# which).
# An axis end within SNAP_M of another axis is extended to meet it, so a
# partial axis drawn to a cross axis still splits the cell even if the export
# leaves it a few millimetres short; the overshooting stubs are dangles, which
# polygonize discards.
SNAP_M = 0.05
# Two axes whose Hausdorff distance is at most DUP_M are one axis. The copies
# in the sample are identical to the millimetre.
DUP_M = 0.01
# Faces smaller than this are numerical slivers of the noding.
MIN_CELL_AREA_M2 = 1e-4
# Straight axes whose directions differ by at most this many degrees form one
# family.
FAMILY_ANGLE_DEG = 2.0
# Two bay widths within this many metres get the same rhythm letter.
SPACING_TOL_M = 0.05
# Two axis offsets within this many metres are one position in a family.
OFFSET_MERGE_M = 0.005
# A boundary vertex is a cell corner when the boundary turns by more than this.
CORNER_TURN_DEG = 10.0


# --------------------------------------------------------------------------
# Reading IfcGrid
# --------------------------------------------------------------------------

def _curve_points(settings, curve):
    """Ordered (n, 3) points of an evaluated IfcCurve in metres, grid frame."""
    try:
        shape = ifcopenshell.geom.create_shape(settings, curve)
    except Exception:  # noqa: BLE001 - an unreadable curve is reported, not fatal
        return None
    verts = np.asarray(shape.verts, dtype=float).reshape(-1, 3)
    edges = np.asarray(shape.edges, dtype=int).reshape(-1, 2)
    if len(verts) < 2:
        return None
    if len(edges) == 0:
        return verts
    neighbours = defaultdict(list)
    for a, b in edges:
        neighbours[int(a)].append(int(b))
        neighbours[int(b)].append(int(a))
    ends = sorted(v for v, n in neighbours.items() if len(n) == 1)
    start = ends[0] if ends else int(edges[0][0])
    order, visited, current = [start], {start}, start
    while True:
        nxt = [n for n in neighbours[current] if n not in visited]
        if not nxt:
            break
        current = nxt[0]
        visited.add(current)
        order.append(current)
    if not ends and len(order) > 2:
        order.append(start)  # a closed curve, e.g. a full circle
    return verts[order]


def read_declared_grids(model, scale=None):
    """Every IfcGrid of the model as {guid, name, predefinedType, storey,
    axes, skippedAxes}. Axis points are world plan coordinates in metres."""
    if scale is None:
        scale = length_scale(model)
    settings = ifcopenshell.geom.settings()
    grids = []
    for grid in sorted({g.GlobalId: g for g in model.by_type("IfcGrid")}.values(), key=lambda g: g.GlobalId):
        matrix = placement_matrix(grid, scale)
        if matrix is None:
            matrix = np.eye(4)
        matrix = np.asarray(matrix, dtype=float)
        storey = ifcopenshell.util.element.get_container(grid, ifc_class="IfcBuildingStorey")
        axes, skipped = [], []
        for family, attribute in (("U", "UAxes"), ("V", "VAxes"), ("W", "WAxes")):
            for axis in getattr(grid, attribute, None) or []:
                curve = axis.AxisCurve
                points = _curve_points(settings, curve) if curve is not None else None
                if points is None or len(points) < 2:
                    skipped.append({"tag": axis.AxisTag, "family": family,
                                    "curve": curve.is_a() if curve is not None else None})
                    continue
                world = points @ matrix[:3, :3].T + matrix[:3, 3]
                axes.append(make_axis(axis.AxisTag or "", family, grid.GlobalId, world[:, :2], curve.is_a()))
        grids.append({
            "guid": grid.GlobalId,
            "name": grid.Name,
            "predefinedType": getattr(grid, "PredefinedType", None),
            "storey": storey.GlobalId if storey is not None else None,
            "axes": axes,
            "skippedAxes": skipped,
        })
    return grids


def make_axis(tag, family, grid_guid, points, curve="synthetic"):
    """One axis as a plain dict. Also the entry point for synthetic tests."""
    points = [[float(x), float(y)] for x, y in points]
    if len(points) > 2 and math.dist(points[0], points[-1]) <= 1e-6:
        points[-1] = list(points[0])  # a nearly closed curve is closed exactly, or polygonize misses its faces
    line = LineString(points)
    chord = np.subtract(points[-1], points[0])
    chord_len = float(np.hypot(*chord))
    straight = chord_len > 0 and abs(line.length - chord_len) <= 1e-6 * max(1.0, line.length)
    return {
        "tags": [str(tag)],
        "declaredFamilies": [family],
        "grids": [grid_guid],
        "curve": curve,
        "points": points,
        "length": line.length,
        "straight": bool(straight),
        "angle": math.degrees(math.atan2(chord[1], chord[0])) % 180.0 if chord_len > 0 else None,
    }


def active_axes(grids, storey_guid):
    """(axes, source) active on a storey; see the module docstring."""
    own = [g for g in grids if g["storey"] == storey_guid]
    building = [g for g in grids if g["storey"] is None]
    if own or building:
        chosen, source = own + building, "own" if own else "building"
    elif grids:
        chosen, source = grids, "borrowed"
    else:
        return [], "none"
    return [axis for g in chosen for axis in g["axes"]], source


# --------------------------------------------------------------------------
# Pure geometry: merge, families, cells, slots, rhythm
# --------------------------------------------------------------------------

def _rounded(points):
    return tuple((round(x, 3), round(y, 3)) for x, y in points)


def merge_axes(axes, dup_m=DUP_M):
    """Merge near-identical axes (copies of one grid line in two grid objects,
    or in the per-storey copies of a building-level grid). The survivor keeps
    every tag, declared family and grid. Returns new dicts with ids."""
    ordered = sorted(axes, key=lambda a: (sorted(a["tags"]), _rounded(a["points"])))
    kept = []
    for axis in ordered:
        line = LineString(axis["points"])
        for k in kept:
            if k["_line"].hausdorff_distance(line) <= dup_m:
                k["tags"] = sorted(set(k["tags"]) | set(axis["tags"]))
                k["declaredFamilies"] = sorted(set(k["declaredFamilies"]) | set(axis["declaredFamilies"]))
                k["grids"] = sorted(set(k["grids"]) | set(axis["grids"]))
                break
        else:
            copy = {key: (list(value) if isinstance(value, list) else value) for key, value in axis.items()}
            copy["_line"] = line
            kept.append(copy)
    # ids from tags; a repeated tag set gets a positional suffix in a sorted order
    by_name = defaultdict(list)
    for k in kept:
        by_name["/".join(k["tags"]) or "?"].append(k)
    for name, group in by_name.items():
        group.sort(key=lambda a: _rounded(a["points"]))
        for index, k in enumerate(group):
            k["id"] = name if len(group) == 1 else f"{name}#{index + 1}"
    kept.sort(key=lambda a: a["id"])
    return kept


def assign_families(axes, tol_deg=FAMILY_ANGLE_DEG):
    """Group straight axes by direction. Families are named F1, F2, ... by
    ascending angle in [0, 180). Curved axes get family None. Returns
    {name: {"angleDeg", "direction", "normal", "axes": [ids]}} and sets
    axis["family"] and axis["offset"] (position along the family normal)."""
    # angles just below 180 are the same direction as angles just above 0
    items = sorted(((a["angle"] - 180.0 if a["angle"] >= 180.0 - tol_deg else a["angle"], a["id"], a)
                    for a in axes if a["straight"]), key=lambda t: (t[0], t[1]))
    clusters = []
    for angle, _, axis in items:
        if clusters and angle - clusters[-1]["angles"][0] <= tol_deg:
            clusters[-1]["axes"].append(axis)
            clusters[-1]["angles"].append(angle)
        else:
            clusters.append({"axes": [axis], "angles": [angle]})
    families = {}
    for index, cluster in enumerate(sorted(clusters, key=lambda c: float(np.mean(c["angles"])))):
        name = f"F{index + 1}"
        angle = float(np.mean(cluster["angles"])) % 180.0
        if angle > 180.0 - 1e-6:
            angle = 0.0
        direction = (math.cos(math.radians(angle)), math.sin(math.radians(angle)))
        normal = (-direction[1], direction[0])
        for axis in cluster["axes"]:
            mid = np.mean(np.asarray(axis["points"]), axis=0)
            axis["family"] = name
            axis["offset"] = float(normal[0] * mid[0] + normal[1] * mid[1])
        families[name] = {"angleDeg": round(angle, 3), "direction": direction, "normal": normal,
                          "axes": sorted(a["id"] for a in cluster["axes"])}
    for axis in axes:
        axis.setdefault("family", None)
        axis.setdefault("offset", None)
    return families


def _closed(axis):
    pts = axis["points"]
    return len(pts) > 2 and np.allclose(pts[0], pts[-1])


def _extended(points, by):
    """The polyline with both end segments lengthened by `by` metres."""
    pts = [list(p) for p in points]
    for i, j in ((0, 1), (-1, -2)):
        d = np.subtract(pts[i], pts[j])
        n = float(np.hypot(*d))
        if n > 0:
            pts[i] = list(np.add(pts[i], d / n * by))
    return pts


def _corner_indices(coords, turn_deg=CORNER_TURN_DEG):
    """Indices of the boundary vertices where the boundary turns."""
    n = len(coords)
    corners = []
    for i in range(n):
        a, b, c = np.asarray(coords[i - 1]), np.asarray(coords[i]), np.asarray(coords[(i + 1) % n])
        u, v = b - a, c - b
        nu, nv = np.hypot(*u), np.hypot(*v)
        if nu == 0 or nv == 0:
            continue
        cos = float(np.clip(np.dot(u, v) / (nu * nv), -1.0, 1.0))
        if math.degrees(math.acos(cos)) > turn_deg:
            corners.append(i)
    return corners


def build_cells(axes, snap_m=SNAP_M, min_area=MIN_CELL_AREA_M2):
    """Cells = bounded faces of the noded axis arrangement. `axes` must come
    from merge_axes (they carry ids). Also marks each axis's dangling ends
    and returns (cells, stats)."""
    lines = {a["id"]: LineString(a["points"]) for a in axes}
    noded = unary_union([LineString(a["points"] if _closed(a) else _extended(a["points"], snap_m))
                         for a in axes])
    faces = [f for f in polygonize(noded) if f.area >= min_area]
    slivers = sum(1 for f in polygonize(noded) if f.area < min_area)

    # An axis end is dangling when it stops inside the gridded region without
    # meeting another axis. Ends beyond the outermost cross axis are the
    # ordinary overshoot of a drawn grid line and do not count.
    region = unary_union(faces).buffer(-snap_m) if faces else None
    for a in axes:
        others = unary_union([lines[b["id"]] for b in axes if b["id"] != a["id"]]) if len(axes) > 1 else None
        ends = (Point(a["points"][0]), Point(a["points"][-1]))
        a["danglingEnds"] = 0 if _closed(a) or region is None else sum(
            1 for p in ends if region.contains(p) and (others is None or others.distance(p) > snap_m))

    cells = []
    for face in faces:
        boundary = face.exterior
        bounding = sorted(aid for aid, line in lines.items()
                          if boundary.intersection(line.buffer(1e-4)).length > 1e-3)
        inner = face.buffer(-1e-4)
        internal = sorted(aid for aid, line in lines.items()
                          if aid not in bounding and inner.intersection(line).length > 2 * snap_m)
        coords = [(round(x, 4), round(y, 4)) for x, y in list(boundary.coords)[:-1]]
        cells.append({
            "polygon": [[x, y] for x, y in coords],
            "corners": _corner_indices(coords),
            "area": face.area,
            "centroid": [face.centroid.x, face.centroid.y],
            "axes": bounding,
            "internalAxes": internal,
        })
    # ids from bounding axis tags (stable across storey copies); collisions
    # are numbered in centroid order
    by_name = defaultdict(list)
    for cell in cells:
        by_name["|".join(cell["axes"])].append(cell)
    for name, group in by_name.items():
        group.sort(key=lambda c: (round(c["centroid"][0], 3), round(c["centroid"][1], 3)))
        for index, cell in enumerate(group):
            cell["id"] = f"c[{name}]" if len(group) == 1 else f"c[{name}]#{index + 1}"
    cells.sort(key=lambda c: c["id"])
    return cells, {"faces": len(faces), "slivers": slivers}


def family_positions(axes, family):
    """Distinct offsets of a family, ascending, merged within OFFSET_MERGE_M."""
    offsets = sorted(a["offset"] for a in axes if a["family"] == family)
    merged = []
    for o in offsets:
        if not merged or o - merged[-1] > OFFSET_MERGE_M:
            merged.append(o)
    return merged


def mark_partial(axes, families, snap_m=SNAP_M):
    """For two-family arrangements: an axis is partial when its extent does
    not reach the outermost axes of the other family. Sets axis["partial"]
    (None when not applicable) and axis["reach"] (its extent in the other
    family's offsets)."""
    names = sorted(families)
    for axis in axes:
        axis["partial"], axis["reach"] = None, None
    if len(names) != 2:
        return
    for axis in axes:
        if axis["family"] not in names:
            continue
        other = names[1] if axis["family"] == names[0] else names[0]
        nx, ny = families[other]["normal"]
        proj = [nx * x + ny * y for x, y in axis["points"]]
        positions = family_positions(axes, other)
        if not positions:
            continue
        lo, hi = min(proj), max(proj)
        axis["reach"] = [lo, hi]
        axis["partial"] = bool(lo > positions[0] + snap_m or hi < positions[-1] - snap_m)


def slots(axes, families, cells):
    """For two straight families: the slot table. Rows are the intervals of
    family F1, columns the intervals of F2, both in ascending offset; each
    slot holds the id of the cell containing the slot centre, or None.
    Returns None for any other arrangement."""
    names = sorted(families)
    if len(names) != 2 or any(not a["straight"] for a in axes):
        return None
    row_pos, col_pos = family_positions(axes, names[0]), family_positions(axes, names[1])
    if len(row_pos) < 2 or len(col_pos) < 2:
        return None
    n1, n2 = np.asarray(families[names[0]]["normal"]), np.asarray(families[names[1]]["normal"])
    system = np.vstack([n1, n2])
    polygons = [(cell["id"], Polygon(cell["polygon"])) for cell in cells]
    table = []
    for r in range(len(row_pos) - 1):
        row = []
        for c in range(len(col_pos) - 1):
            target = [(row_pos[r] + row_pos[r + 1]) / 2, (col_pos[c] + col_pos[c + 1]) / 2]
            x, y = np.linalg.solve(system, target)
            centre = Point(x, y)
            hit = next((cid for cid, poly in polygons if poly.contains(centre)), None)
            row.append(hit)
        table.append(row)
    return {"rows": names[0], "columns": names[1], "rowPositions": row_pos,
            "columnPositions": col_pos, "table": table}


def rhythm_word(spacings, classes=None, tol=SPACING_TOL_M):
    """Letters for a bay sequence, by first appearance: 5, 8, 8, 5 -> ABBA.
    `classes` (letter -> width) is extended in place, so several rows can
    share one alphabet."""
    classes = {} if classes is None else classes
    letters = []
    for s in spacings:
        letter = next((k for k, v in classes.items() if abs(v - s) <= tol), None)
        if letter is None:
            letter = _letter(len(classes))
            classes[letter] = s
        letters.append(letter)
    return "".join(letters), classes


def _letter(index):
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return alphabet[index] if index < 26 else f"[{index}]"


def rhythm(axes, families, slot_table):
    """Bay rhythm per family, and per row/column: which axes of the other
    family actually cross that row (partial axes make rows differ)."""
    out = {}
    for name in sorted(families):
        positions = family_positions(axes, name)
        spacings = [round(b - a, 3) for a, b in zip(positions, positions[1:])]
        word, classes = rhythm_word(spacings)
        out[name] = {"positions": [round(p, 3) for p in positions], "spacings": spacings,
                     "word": word, "classes": {k: round(v, 3) for k, v in classes.items()}}
    if slot_table is None:
        return out
    lines = {a["id"]: LineString(a["points"]) for a in axes}
    for along, across in ((slot_table["rows"], slot_table["columns"]),
                          (slot_table["columns"], slot_table["rows"])):
        # bands of family `along`; inside each band, which `across` axes cross
        d = np.asarray(families[along]["direction"])
        n_along = np.asarray(families[along]["normal"])
        n_across = np.asarray(families[across]["normal"])
        pos_along = family_positions(axes, along)
        pos_across = family_positions(axes, across)
        span = (pos_across[0] - 1.0, pos_across[-1] + 1.0)
        classes = dict((k, v) for k, v in out[across]["classes"].items())
        words = []
        for k in range(len(pos_along) - 1):
            mid = (pos_along[k] + pos_along[k + 1]) / 2
            # a midline of the band, long enough to cross the whole arrangement
            system = np.vstack([n_along, n_across])
            p0 = np.linalg.solve(system, [mid, span[0]])
            p1 = np.linalg.solve(system, [mid, span[1]])
            midline = LineString([p0, p1])
            crossing = sorted({round(a["offset"], 3) for a in axes
                               if a["family"] == across and lines[a["id"]].intersects(midline)})
            spacings = [round(b - a, 3) for a, b in zip(crossing, crossing[1:])]
            word, classes = rhythm_word(spacings, classes)
            words.append(word)
        out[along]["bandRhythm"] = words
        out[across]["classes"] = {k: round(v, 3) for k, v in classes.items()}
    return out


def storey_grid(axes):
    """Everything geometric for one storey's active axes."""
    merged = merge_axes(axes)
    families = assign_families(merged)
    cells, stats = build_cells(merged)
    mark_partial(merged, families)
    table = slots(merged, families, cells)
    return {"axes": merged, "families": families, "cells": cells, "slots": table,
            "rhythm": rhythm(merged, families, table), "stats": stats}
