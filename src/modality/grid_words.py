"""L1 grid words: one symbol per declared-grid cell.

A cell's symbol says which of three structural element classes it holds:
C (IfcColumn), B (IfcBeam) and W (IfcWall), with '-' for each class it lacks.
'C-W' is a cell with columns and walls but no beam. The symbols are then read
as words:
  - row and column words, along the two families of a straight two-family
    grid in ascending offset. A cell that spans several slots (a partial axis
    left it unsplit) appears once, as 'C-W*2';
  - vertical words, one per cell id across the storeys in elevation order,
    '.' where the storey has no such cell;
  - rhythm words for the bay widths, from declared_grid.rhythm.
Next to every symbol is the record that makes it checkable: which corner,
which side and what in the interior, with element GUIDs.

Elements. Columns, beams and walls are read from their triangulated shapes
in world coordinates (world_settings below): a column is the centre of its
plan box, a beam or wall the long axis of the minimum rotated rectangle of
its plan points. Placements are not used: columns resolve to (0, 0, 0) in
raw placements on this corpus (docs/detectors.md rule 10). A beam or wall
whose rectangle is shorter than MIN_SEGMENT_M is counted as degenerate and reported
per model, never silently dropped; beam geometry was degenerate in 2 of 5
models (docs/detectors.md rule 10). by_type() returns subtypes
(IfcWallStandardCase under IfcWall), so elements are de-duplicated by GUID
(rule 3).

Tolerances (metres), measured on the uploaded models, 2026-10-02: comparing
declared axes with column centres, the centres sit within 0.06 m of their
axes in most models but 0.07-0.30 m off in d85a2ea7... and 0.02-0.32 m in
4558d77b... (axes drawn on faces, not centres). CORNER_TOL_M = 0.35 covers
every measured offset; it must stay below half of the narrowest deliberate
spacing, the 1 m bands of twin axes in a2b650f1..., or a column would sit on
two axes at once. EDGE_TOL_M takes the same value for walls and beams, whose
axis offsets are half an element thickness at most.
"""

from collections import Counter, defaultdict
import math

import ifcopenshell.geom
import ifcopenshell.util.element
import numpy as np
from shapely import STRtree
from shapely.geometry import LineString, MultiPoint, Point, Polygon

from extraction.geometry_iteration import iterate_shapes

CORNER_TOL_M = 0.35
EDGE_TOL_M = 0.35
EDGE_ANGLE_DEG = 5.0
# A beam or wall lies along a cell side when its projection overlaps at least
# this share of the shorter of the two.
EDGE_OVERLAP = 0.5
MIN_SEGMENT_M = 0.05
CLASSES = (("C", "IfcColumn"), ("B", "IfcBeam"), ("W", "IfcWall"))


# --------------------------------------------------------------------------
# Elements
# --------------------------------------------------------------------------

def world_settings():
    """Triangulated shapes in world coordinates. Set through settings.set():
    with IfcOpenShell 0.8.5, extraction.model_loader.configure_settings'
    attribute assignment `settings.USE_WORLD_COORDS = True` leaves the engine
    option "use-world-coords" False (checked 2026-10-02: a column of
    d85a2ea7... came back at (0.10, 0.10) through it and at (27.10, -7.16) with
    settings.set). That function is left unchanged here; see the hand-off
    note of 2026-10-02."""
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    return settings


def element_primitives(model):
    """Columns as points, beams and walls as centre segments, world metres.
    Returns (primitives sorted by GUID, report)."""
    kind_of, entity_of = {}, {}
    for kind, ifc_class in CLASSES:
        for element in model.by_type(ifc_class):
            if element.GlobalId not in kind_of:
                kind_of[element.GlobalId] = kind
                entity_of[element.GlobalId] = element
    elements = [entity_of[g] for g in sorted(entity_of)]
    settings = world_settings()
    shapes = {}
    for shape in iterate_shapes(settings, model, elements, "triangle"):
        verts = np.asarray(shape.geometry.verts, dtype=float).reshape(-1, 3)
        if len(verts):
            shapes[shape.guid] = verts
    primitives, report = [], {"elements": Counter(), "noShape": Counter(), "degenerate": Counter(),
                              "noStorey": Counter()}
    for guid in sorted(entity_of):
        kind = kind_of[guid]
        report["elements"][kind] += 1
        verts = shapes.get(guid)
        if verts is None:
            report["noShape"][kind] += 1
            continue
        storey = ifcopenshell.util.element.get_container(entity_of[guid], ifc_class="IfcBuildingStorey")
        if storey is None:
            report["noStorey"][kind] += 1
        plan = verts[:, :2]
        base = {"guid": guid, "kind": kind, "storey": storey.GlobalId if storey is not None else None,
                "z": [float(verts[:, 2].min()), float(verts[:, 2].max())]}
        if kind == "C":
            lo, hi = plan.min(axis=0), plan.max(axis=0)
            primitives.append({**base, "point": [float((lo[0] + hi[0]) / 2), float((lo[1] + hi[1]) / 2)]})
            continue
        rect = MultiPoint([tuple(p) for p in plan]).minimum_rotated_rectangle
        if rect.geom_type != "Polygon":
            report["degenerate"][kind] += 1
            continue
        c = np.asarray(rect.exterior.coords)[:4]
        e1, e2 = c[1] - c[0], c[2] - c[1]
        long_edge, short_edge = (e1, e2) if np.hypot(*e1) >= np.hypot(*e2) else (e2, e1)
        length, width = float(np.hypot(*long_edge)), float(np.hypot(*short_edge))
        if length < MIN_SEGMENT_M:
            report["degenerate"][kind] += 1
            continue
        centre = np.asarray(rect.centroid.coords[0])
        d = long_edge / length
        primitives.append({**base, "segment": [list(centre - d * length / 2), list(centre + d * length / 2)],
                           "width": width})
    return primitives, {k: dict(v) for k, v in report.items()}


# --------------------------------------------------------------------------
# Cells
# --------------------------------------------------------------------------

def _along(seg, side, tol, angle_deg, overlap):
    """Does segment `seg` run along the straight side (chord) `side`?"""
    (ax, ay), (bx, by) = seg
    (cx, cy), (dx, dy) = side
    u = np.array([bx - ax, by - ay])
    v = np.array([dx - cx, dy - cy])
    lu, lv = np.hypot(*u), np.hypot(*v)
    if lu == 0 or lv == 0:
        return False
    cos = abs(float(np.dot(u, v) / (lu * lv)))
    if math.degrees(math.acos(min(1.0, cos))) > angle_deg:
        return False
    w = v / lv
    mid = np.array([(ax + bx) / 2 - cx, (ay + by) / 2 - cy])
    if abs(float(mid[0] * w[1] - mid[1] * w[0])) > tol:
        return False
    t0 = float(np.dot([ax - cx, ay - cy], w))
    t1 = float(np.dot([bx - cx, by - cy], w))
    lo, hi = min(t0, t1), max(t0, t1)
    shared = max(0.0, min(hi, lv) - max(lo, 0.0))
    return shared >= overlap * min(lu, lv)


def describe_cells(cells, primitives, corner_tol=CORNER_TOL_M, edge_tol=EDGE_TOL_M,
                   angle_deg=EDGE_ANGLE_DEG, overlap=EDGE_OVERLAP):
    """Symbol and record for every cell of one storey."""
    geoms = [Point(p["point"]) if p["kind"] == "C" else LineString(p["segment"]) for p in primitives]
    tree = STRtree(geoms) if geoms else None
    out = {}
    for cell in cells:
        poly = Polygon(cell["polygon"])
        coords = cell["polygon"]
        corners = cell["corners"] or list(range(len(coords)))
        sides = [(corners[k], corners[(k + 1) % len(corners)]) for k in range(len(corners))]
        reach = poly.buffer(max(corner_tol, edge_tol))
        inner = poly.buffer(-edge_tol)
        record = {"corners": defaultdict(list), "sides": defaultdict(lambda: defaultdict(list)),
                  "interior": defaultdict(list)}
        candidates = sorted(int(i) for i in tree.query(reach)) if tree is not None else []
        for index in candidates:
            prim = primitives[index]
            if not reach.intersects(geoms[index]):
                continue
            if prim["kind"] == "C":
                pt = prim["point"]
                dists = [math.dist(pt, coords[i]) for i in corners]
                k = int(np.argmin(dists)) if dists else None
                if k is not None and dists[k] <= corner_tol:
                    record["corners"][k].append(prim["guid"])
                    continue
                point = Point(pt)
                if poly.exterior.distance(point) <= edge_tol:
                    side = int(np.argmin([LineString([coords[i], coords[j]]).distance(point) for i, j in sides]))
                    record["sides"][side]["C"].append(prim["guid"])
                elif poly.contains(point):
                    record["interior"]["C"].append(prim["guid"])
                continue
            placed = False
            for s, (i, j) in enumerate(sides):
                if _along(prim["segment"], (coords[i], coords[j]), edge_tol, angle_deg, overlap):
                    record["sides"][s][prim["kind"]].append(prim["guid"])
                    placed = True
            if not placed:
                a, b = prim["segment"]
                if inner.contains(Point((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)):
                    record["interior"][prim["kind"]].append(prim["guid"])
        present = set()
        if record["corners"]:
            present.add("C")
        for side in record["sides"].values():
            present.update(k for k, v in side.items() if v)
        present.update(k for k, v in record["interior"].items() if v)
        symbol = "".join(k if k in present else "-" for k, _ in CLASSES)
        out[cell["id"]] = {
            "symbol": symbol,
            "corners": [[k, sorted(v)] for k, v in sorted(record["corners"].items())],
            "sides": [[s, {k: sorted(v) for k, v in sorted(d.items())}] for s, d in sorted(record["sides"].items())],
            "interior": {k: sorted(v) for k, v in sorted(record["interior"].items())},
        }
    return out


# --------------------------------------------------------------------------
# Words
# --------------------------------------------------------------------------

def _run_tokens(ids, symbols):
    """One token per run of slots held by the same cell: 'C-W', or 'C-W*2'
    for one cell spanning two slots; '.' for slots no cell covers."""
    tokens, i = [], 0
    while i < len(ids):
        j = i
        while j + 1 < len(ids) and ids[j + 1] == ids[i]:
            j += 1
        token = "." if ids[i] is None else symbols[ids[i]]
        tokens.append(token if j == i else f"{token}*{j - i + 1}")
        i = j + 1
    return tokens


def slot_words(slot_table, symbols):
    """Row words (along the columns family) and column words (along the rows
    family), as token lists."""
    if slot_table is None:
        return None
    table = slot_table["table"]
    rows = [_run_tokens(list(row), symbols) for row in table]
    cols = [_run_tokens([row[c] for row in table], symbols) for c in range(len(table[0]))] if table else []
    return {"rowFamily": slot_table["rows"], "columnFamily": slot_table["columns"],
            "rows": [" ".join(t) for t in rows], "columns": [" ".join(t) for t in cols]}


def vertical_words(storeys):
    """{cell id: word} across storeys in the given order (lowest first)."""
    ids = sorted({cid for s in storeys for cid in s["symbols"]})
    return {cid: " ".join(s["symbols"].get(cid, ".") for s in storeys) for cid in ids}
