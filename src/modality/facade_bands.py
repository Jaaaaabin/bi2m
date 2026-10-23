"""L0 facade bands: one token per element along a storey's facade, cut into
bays by the declared grid.

For each storey:
  1. The outline. The plan rectangles of the storey's walls and curtain-wall
     panels are unioned and closed (buffer +CLOSE_M, then -CLOSE_M), which
     bridges the gaps between separate wall elements. Every outer ring is a
     facade line. An inner ring (a hole) is a facade line only when it is a
     courtyard: the ring of exterior walls also encloses the building's own
     rooms as holes, so a hole counts as a courtyard when slabs above the
     cut (floors, roofs) cover less than COURT_COVER of it - open to the
     sky, unlike a room. Rings are oriented with the building on the left
     (outer rings counter-clockwise, courtyards clockwise). Measured
     2026-10-02: in e8e8c39a... every window the outer rings missed (26 to 32
     per storey) sits on one 479 m2 courtyard, about 15 m from the outer
     ring.
  2. Runs. A ring is split where it turns by more than TURN_DEG, so a
     rectangle gives four runs and a curved facade stays one run. Positions
     along a run are arc lengths (shapely `project`), so curved runs work
     the same way as straight ones.
  3. Items. The facade is read on a plan cut: CUT_M above the storey's
     floor, which is the median bottom of the walls and columns the storey
     contains. Every wall (W), window (N), door (D), curtain-wall panel (G,
     IfcPlate of a curtain wall) and column (C) that crosses the cut plane,
     whichever storey contains it, and whose plan rectangle lies within
     DEPTH_M of a run, is projected onto it as an interval. Storey
     containment alone is not enough: a wall or curtain wall spanning
     several levels is contained in its base storey only.
     The outline in step 1 is built from the same cut. Where
     intervals overlap, the higher class wins: D > N > G > C > W, and '_'
     marks stretches with no element. Neighbouring W or _ pieces merge;
     openings, panels and columns stay one token each, so a rhythm of
     windows stays visible.
  4. Bays. Each declared axis active on the storey (declared_grid) that
     crosses the run puts a '|' at its crossing, and a token straddling it is
     split. A partial axis that stops inside the building does not reach
     the facade and splits nothing.

Tokens are class plus width. Two width encodings are written side by side,
because they answer different questions: `band` uses a fixed resolution of
BIN_M (W12 = 12 x 0.25 m = 3.0 m), which keeps exact repeats comparable;
`bandCoarse` uses size classes (XS < 0.6 m, S < 1.2, M < 2.4, L < 4.8, XL),
which survives small dimensional noise.

All thresholds here are conventions, not corpus measurements (docs/detectors.md
rule 2); the per-model report counts the windows and doors that landed
on no run, which is the check that they are adequate.
"""

from collections import Counter, defaultdict
import math

import ifcopenshell.util.element
import numpy as np
from shapely.geometry import LineString, MultiPoint, Point, Polygon
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

from extraction.geometry_iteration import iterate_shapes
from modality.grid_words import world_settings

CLOSE_M = 0.6
CUT_M = 1.2
SIMPLIFY_M = 0.05
TURN_DEG = 20.0
DEPTH_M = 1.0
MIN_RUN_M = 0.5
MIN_HOLE_M2 = 4.0
COURT_COVER = 0.5
MIN_TRIANGLE_M2 = 1e-6
BIN_M = 0.25
COARSE = ((0.6, "XS"), (1.2, "S"), (2.4, "M"), (4.8, "L"), (math.inf, "XL"))
PRIORITY = {"D": 5, "N": 4, "G": 3, "C": 2, "W": 1, "_": 0}
CLASSES = (("W", "IfcWall"), ("N", "IfcWindow"), ("D", "IfcDoor"), ("C", "IfcColumn"), ("G", "IfcPlate"))


# --------------------------------------------------------------------------
# Elements
# --------------------------------------------------------------------------

def _curtain_panels(model):
    """GUIDs of IfcPlate elements that are parts of an IfcCurtainWall."""
    panels = set()
    for wall in model.by_type("IfcCurtainWall"):
        for part in ifcopenshell.util.element.get_decomposition(wall):
            if part.is_a("IfcPlate"):
                panels.add(part.GlobalId)
    return panels


def element_rectangles(model):
    """{guid: {"kind", "storey", "rect"}}: the plan minimum rotated rectangle
    of each wall, window, door, column and curtain-wall panel, world metres.
    Returns (rectangles, report)."""
    panels = _curtain_panels(model)
    kind_of, entity_of = {}, {}
    for kind, ifc_class in CLASSES:
        for element in model.by_type(ifc_class):
            if kind == "G" and element.GlobalId not in panels:
                continue
            if element.GlobalId not in kind_of:
                kind_of[element.GlobalId] = kind
                entity_of[element.GlobalId] = element
    elements = [entity_of[g] for g in sorted(entity_of)]
    shapes = {}
    for shape in iterate_shapes(world_settings(), model, elements, "triangle"):
        verts = np.asarray(shape.geometry.verts, dtype=float).reshape(-1, 3)
        if len(verts):
            shapes[shape.guid] = verts
    out, report = {}, {"elements": Counter(), "noShape": Counter(), "noStorey": Counter()}
    for guid in sorted(entity_of):
        kind = kind_of[guid]
        report["elements"][kind] += 1
        verts = shapes.get(guid)
        if verts is None:
            report["noShape"][kind] += 1
            continue
        container = entity_of[guid]
        if kind == "G":  # a panel sits in its curtain wall, which sits in the storey
            parent = ifcopenshell.util.element.get_aggregate(container)
            container = parent if parent is not None else container
        storey = ifcopenshell.util.element.get_container(container, ifc_class="IfcBuildingStorey")
        if storey is None:
            report["noStorey"][kind] += 1
        rect = MultiPoint([tuple(p) for p in verts[:, :2]]).minimum_rotated_rectangle
        if rect.geom_type != "Polygon":
            rect = rect.buffer(0.01)  # a degenerate (line or point) footprint keeps a 1 cm body
        out[guid] = {"guid": guid, "kind": kind, "storey": storey.GlobalId if storey is not None else None,
                     "z": [float(verts[:, 2].min()), float(verts[:, 2].max())],
                     "rect": [list(map(float, c)) for c in list(rect.exterior.coords)[:-1]]}
    return out, {k: dict(v) for k, v in report.items()}


def cut_height(rects, storey_guid, cut_m=CUT_M):
    """The storey's plan-cut height in world metres: CUT_M above the median
    bottom of the walls and columns it contains, or None."""
    bottoms = sorted(r["z"][0] for r in rects if r["storey"] == storey_guid and r["kind"] in ("W", "C"))
    if not bottoms:
        return None
    return bottoms[len(bottoms) // 2] + cut_m


def on_cut(rects, z_cut):
    """The rectangles whose vertical extent crosses the cut plane."""
    return [r for r in rects if r["z"][0] - 1e-6 <= z_cut <= r["z"][1] + 1e-6]


def slab_footprints(model):
    """[{"guid", "polygon", "z"}]: the exact plan footprint (union of the
    projected triangles) of every IfcSlab and IfcRoof with its own shape."""
    elements = sorted({e.GlobalId: e for c in ("IfcSlab", "IfcRoof") for e in model.by_type(c)}.values(),
                      key=lambda e: e.GlobalId)
    out = []
    for shape in iterate_shapes(world_settings(), model, elements, "triangle"):
        verts = np.asarray(shape.geometry.verts, dtype=float).reshape(-1, 3)
        faces = np.asarray(shape.geometry.faces, dtype=int).reshape(-1, 3)
        triangles = []
        for a, b, c in faces:
            tri = Polygon([verts[a, :2], verts[b, :2], verts[c, :2]])
            if tri.is_valid and tri.area > MIN_TRIANGLE_M2:
                triangles.append(tri)
        if triangles:
            out.append({"guid": shape.guid, "polygon": unary_union(triangles).buffer(0),
                        "z": [float(verts[:, 2].min()), float(verts[:, 2].max())]})
    return sorted(out, key=lambda f: f["guid"])


def cover_above(footprints, z_cut):
    """Union of the slab footprints lying wholly above the cut plane."""
    above = [f["polygon"] for f in footprints if f["z"][0] > z_cut]
    return unary_union(above) if above else None


# --------------------------------------------------------------------------
# Outline and runs
# --------------------------------------------------------------------------

def storey_outline(rects):
    """The closed plan outline of a storey from its wall and panel rectangles."""
    body = [Polygon(r["rect"]) for r in rects if r["kind"] in ("W", "G")]
    body = [b for b in body if b.is_valid and b.area > 0]
    if not body:
        return None
    merged = unary_union([b.buffer(CLOSE_M, join_style="mitre") for b in body]).buffer(-CLOSE_M, join_style="mitre")
    return merged if not merged.is_empty else None


def _rings(outline, cover=None):
    """Facade rings in a stable order, with the building on the left: every
    outer ring, plus the holes that are courtyards (see the module
    docstring). Also returns the counts of holes and courtyards."""
    polygons = [outline] if outline.geom_type == "Polygon" else list(getattr(outline, "geoms", []))
    rings, holes, courts = [], 0, 0
    for poly in sorted(polygons, key=lambda p: (round(p.bounds[1], 3), round(p.bounds[0], 3))):
        holes += len(poly.interiors)
        outer = orient(Polygon(poly.exterior).simplify(SIMPLIFY_M), sign=1.0)
        rings.append(("outer", list(outer.exterior.coords)[:-1]))
        if cover is None:
            continue
        for hole in sorted(poly.interiors, key=lambda h: (round(h.bounds[1], 3), round(h.bounds[0], 3))):
            area = Polygon(hole)
            if area.area < MIN_HOLE_M2 or area.intersection(cover).area >= COURT_COVER * area.area:
                continue
            courts += 1
            court = orient(area.simplify(SIMPLIFY_M), sign=1.0)  # counter-clockwise ...
            rings.append(("court", list(court.exterior.coords)[:-1][::-1]))  # ... reversed: building on the left
    return rings, holes, courts


def split_runs(ring, turn_deg=TURN_DEG):
    """Split a closed ring (list of points, no repeat) at its corners into
    open polylines. A ring without corners is one closed run."""
    n = len(ring)
    corners = []
    for i in range(n):
        a, b, c = np.asarray(ring[i - 1]), np.asarray(ring[i]), np.asarray(ring[(i + 1) % n])
        u, v = b - a, c - b
        nu, nv = np.hypot(*u), np.hypot(*v)
        if nu and nv and math.degrees(math.acos(float(np.clip(np.dot(u, v) / (nu * nv), -1, 1)))) > turn_deg:
            corners.append(i)
    if not corners:
        return [ring + [ring[0]]]
    # start at the corner with the smallest (y, x), so the order is stable
    start = min(corners, key=lambda i: (round(ring[i][1], 3), round(ring[i][0], 3)))
    order = corners[corners.index(start):] + corners[:corners.index(start)]
    runs = []
    for k, i in enumerate(order):
        j = order[(k + 1) % len(order)]
        idx = list(range(i, j + 1)) if j > i else list(range(i, n)) + list(range(0, j + 1))
        runs.append([list(ring[t]) for t in idx])
    return runs


# --------------------------------------------------------------------------
# Bands
# --------------------------------------------------------------------------

def coarse_class(width):
    return next(name for limit, name in COARSE if width < limit)


def build_band(length, items, crossings, bin_m=BIN_M):
    """Pure core: items = [(kind, s0, s1, guid)], crossings = [(s, axis id)]
    along a run of `length` metres. Returns tokens and bays."""
    cuts = {0.0, round(length, 4)}
    for _, s0, s1, _ in items:
        cuts.update((round(min(max(s0, 0.0), length), 4), round(min(max(s1, 0.0), length), 4)))
    marks = sorted({round(min(max(s, 0.0), length), 4) for s, _ in crossings})
    cuts.update(marks)
    cuts = sorted(cuts)
    pieces = []
    for a, b in zip(cuts, cuts[1:]):
        if b - a <= 1e-4:
            continue
        mid = (a + b) / 2
        covering = [(PRIORITY[k], k, g) for k, s0, s1, g in items if min(s0, s1) <= mid <= max(s0, s1)]
        if covering:
            top = max(p for p, _, _ in covering)
            kind = next(k for p, k, _ in covering if p == top)
            guids = sorted({g for p, k, g in covering if p == top})
        else:
            kind, guids = "_", []
        key = (kind,) if kind in ("W", "_") else (kind, tuple(guids))
        if pieces and pieces[-1]["key"] == key and not any(abs(m - a) <= 1e-4 for m in marks):
            pieces[-1]["s1"] = b
            pieces[-1]["guids"] = sorted(set(pieces[-1]["guids"]) | set(guids))
        else:
            pieces.append({"key": key, "kind": kind, "s0": a, "s1": b, "guids": guids})
    tokens, coarse = [], []
    mark_ids = defaultdict(list)
    for s, axis in crossings:
        mark_ids[round(min(max(s, 0.0), length), 4)].append(axis)
    placed = set()
    for piece in pieces:
        for m in marks:
            if m not in placed and m <= piece["s0"] + 1e-4:
                tokens.append("|")
                coarse.append("|")
                placed.add(m)
        width = piece["s1"] - piece["s0"]
        tokens.append(f"{piece['kind']}{max(1, round(width / bin_m))}")
        coarse.append(f"{piece['kind']}:{coarse_class(width)}")
    for m in marks:
        if m not in placed:
            tokens.append("|")
            coarse.append("|")
    bays, edges = [], [0.0] + marks + [round(length, 4)]
    for a, b in zip(edges, edges[1:]):
        if b - a <= 1e-4:
            continue
        inside = [p for p in pieces if p["s0"] >= a - 1e-4 and p["s1"] <= b + 1e-4]
        bays.append({"from": sorted(mark_ids.get(a, [])) or None, "to": sorted(mark_ids.get(b, [])) or None,
                     "width": round(b - a, 3),
                     "word": " ".join(f"{p['kind']}{max(1, round((p['s1'] - p['s0']) / bin_m))}" for p in inside)})
    items_out = [[p["kind"], round(p["s0"], 3), round(p["s1"], 3), p["guids"]] for p in pieces]
    return {"band": " ".join(tokens), "bandCoarse": " ".join(coarse), "bays": bays, "pieces": items_out}


def storey_bands(rects_on_storey, axes, cover=None):
    """Facade bands of one storey: rects_on_storey from element_rectangles
    (on_cut), axes = the storey's merged declared axes
    (declared_grid.storey_grid), cover = cover_above(...) for the courtyard
    rule (None: outer rings only)."""
    outline = storey_outline(rects_on_storey)
    if outline is None:
        return [], _report(rects_on_storey, set(), 0, 0)
    polys = [(r, Polygon(r["rect"])) for r in rects_on_storey]
    axis_lines = [(a["id"], LineString(a["points"])) for a in axes]
    runs, used = [], set()
    rings, holes, courts = _rings(outline, cover)
    for ring_index, (ring_kind, ring) in enumerate(rings):
        for run_index, pts in enumerate(split_runs(ring)):
            line = LineString(pts)
            if line.length < MIN_RUN_M:
                continue
            zone = line.buffer(DEPTH_M)
            items = []
            for r, poly in polys:
                if not zone.intersects(poly):
                    continue
                inside = poly.intersection(zone)
                corners = list(inside.exterior.coords) if inside.geom_type == "Polygon" else \
                    [c for g in getattr(inside, "geoms", []) if g.geom_type == "Polygon" for c in g.exterior.coords]
                if not corners:
                    continue
                s = [line.project(Point(c)) for c in corners]
                s0, s1 = min(s), max(s)
                if s1 - s0 <= 1e-3:
                    continue
                items.append((r["kind"], s0, s1, r["guid"]))
                if r["kind"] in ("N", "D"):
                    used.add(r["guid"])
            crossings = []
            for aid, al in axis_lines:
                hit = al.intersection(line)
                points = [hit] if hit.geom_type == "Point" else [g for g in getattr(hit, "geoms", []) if g.geom_type == "Point"]
                crossings.extend((line.project(p), aid) for p in points)
            band = build_band(line.length, sorted(items, key=lambda t: (t[1], t[3])), sorted(crossings))
            runs.append({"id": f"{ring_kind}{ring_index + 1}.r{run_index + 1}", "length": round(line.length, 3),
                         "points": [[round(x, 3), round(y, 3)] for x, y in pts], **band})
    return runs, _report(rects_on_storey, used, holes, courts)


def _report(rects, used, holes, courts):
    windows = [r["guid"] for r in rects if r["kind"] == "N"]
    doors = [r["guid"] for r in rects if r["kind"] == "D"]
    return {"windows": len(windows), "windowsOnNoRun": sum(1 for g in windows if g not in used),
            "doors": len(doors), "doorsOnARun": sum(1 for g in doors if g in used), "holes": holes,
            "courtyards": courts}
