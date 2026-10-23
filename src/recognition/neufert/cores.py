"""Vertical cores: stacks of stairs and of lifts, each with the storeys it
serves, from the elements' world-frame bodies (a corpus probe of
2026-10-19 on 404 stairs of 53 corpus models and all 89 transport
elements: only 12 stairs carry their own body, so a stair is read from
its flights and landings; 84 % of stairs span exactly two storeys and 31
of 53 models model one IfcStair per storey, so "storeys served" is a
STACK fact or a six-storey core reads as two storeys everywhere).

A storey is served when its elevation lies within [z_min - Z_MARGIN_M,
z_max + Z_MARGIN_M] of the stack's body. Two elements of one kind join a
stack when their plan bounding boxes overlap with IoU >= STACK_IOU and
their bases differ by more than STACK_BASE_GAP_M (one stair per storey,
stacked; two stairs side by side on one storey stay apart). Lift evidence
(2026-10-20, corpus probe: only 13 corpus models carry an
IfcTransportElement, 61 more name a lift without one, as 456 shaft or
lobby spaces in 63 models and as doors in 4) comes from three sources in
one stack: IfcTransportElement, IfcSpace and IfcDoor named as a lift
(vocabulary `lift`, every name segment). Lift items join a stack when
their plan boxes come within LIFT_REACH_M of each other, on the same
storey (the car, its shaft space and its landing door are one lift) or
across storeys; the core records its `sources`, since a lift-named space
may be the lobby rather than the car.

Tables the measures read (facts.BUILT lists them):
    vertical_cores(ctx)      [{key, kind, elements, storeys, xy, z}] sorted by key
    stair_core_storeys       {stair guid: storeys its core serves}
    stair_core_flats_per_floor {stair guid: the most dwellings any served
                             storey holds, inferred units assigned to the
                             nearest stair core by their entrance door}
    stair_core_has_lift      {stair guid: 1 when a lift stack serves the core
                             (shares a storey and stands within
                             LIFT_CORE_REACH_M or in its stairwell), else 0}
    storey_stair_cores, storey_lift_cores   {storey guid: count}
"""

import math

import ifcopenshell.util.element
import ifcopenshell.util.shape
import numpy as np

from extraction.geometry_iteration import iterate_shapes

from ..census import elements_by_guid
from ..components import connected_components
from .. import vocabulary

Z_MARGIN_M = 0.15
STACK_IOU = 0.3
STACK_BASE_GAP_M = 1.0
LIFT_REACH_M = 0.6  # measured door stacks: lift doors of one shaft within 0.6 m in plan
# A lift serves a stair core when its stack lies within this plan distance of the core (or in the
# core's own stairwell space): "a lift stack shares a storey with the core" marked every core of a
# one-lift building as lifted (2026-10-20).
LIFT_CORE_REACH_M = 3.0
LIFT_SOURCES = (("IfcTransportElement", "transport"), ("IfcSpace", "space"), ("IfcDoor", "door"))


STAIR_PART_CLASSES = ("IfcStairFlight", "IfcSlab")  # flights and landings; railings (balusters) cost seconds and add no extent


def _parts(stair):
    try:
        return [p for p in ifcopenshell.util.element.get_decomposition(stair) if any(p.is_a(c) for c in STAIR_PART_CLASSES)]
    except Exception:  # noqa: BLE001
        return []


def _bboxes(ctx, elements):
    """{guid: (min xyz, max xyz)} in the world frame from ONE streaming
    iterator pass (the shared helper, multi-threaded): one create_shape per
    stair part cost 24 CPU-minutes over the corpus the first time."""
    boxes = {}
    if not elements:
        return boxes
    try:
        for shape in iterate_shapes(ctx.settings, ctx.model, elements, "triangle"):
            try:
                vertices = ifcopenshell.util.shape.get_vertices(shape.geometry)
            except Exception:  # noqa: BLE001
                continue
            if len(vertices):
                boxes[shape.guid] = (vertices.min(axis=0), vertices.max(axis=0))
    except Exception:  # noqa: BLE001 - the iterator failed outright: no cores
        return {}
    return boxes


def _union(boxes):
    boxes = [b for b in boxes if b is not None]
    if not boxes:
        return None
    return np.min([b[0] for b in boxes], axis=0), np.max([b[1] for b in boxes], axis=0)


def _is_lift(ctx, element):
    return vocabulary.matches(ctx.text(element), "lift")  # ctx.text dispatches spaces vs elements, cached


def _lift_items(ctx):
    """[(guid, element, source)] for every lift-named element of LIFT_SOURCES."""
    items = []
    for ifc_class, source in LIFT_SOURCES:
        for guid, element in sorted(elements_by_guid(ctx.model, [ifc_class]).items()):
            if _is_lift(ctx, element):
                items.append((guid, element, source))
    return items


def _plan_gap(a, b):
    dx = max(0.0, max(a[0][0], b[0][0]) - min(a[1][0], b[1][0]))
    dy = max(0.0, max(a[0][1], b[0][1]) - min(a[1][1], b[1][1]))
    return math.hypot(dx, dy)


def _stair_join(a, b):
    return abs(float(a[0][2]) - float(b[0][2])) > STACK_BASE_GAP_M and _iou(a, b) >= STACK_IOU


def _lift_join(a, b):
    return _plan_gap(a, b) <= LIFT_REACH_M


def _iou(a, b):
    ix = max(0.0, min(a[1][0], b[1][0]) - max(a[0][0], b[0][0]))
    iy = max(0.0, min(a[1][1], b[1][1]) - max(a[0][1], b[0][1]))
    inter = ix * iy
    area_a = (a[1][0] - a[0][0]) * (a[1][1] - a[0][1])
    area_b = (b[1][0] - b[0][0]) * (b[1][1] - b[0][1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _anchors(ctx, boxes):
    """{guid: space guid} for every boxed element whose plan centre lies in
    the footprint of a space named as a vertical core (a stairwell drawn as
    one space through every storey, 0263): the stairs inside it are one
    stack whatever their plan offsets, and a lift door inside it belongs to
    that core (2026-10-20)."""
    from shapely.geometry import Point
    wells = []
    for space in ctx.model.by_type("IfcSpace"):
        polygon = ctx.polygons.get(space.GlobalId)
        if polygon is not None and vocabulary.matches(ctx.text(space), "vertical_core"):
            wells.append((space.GlobalId, polygon))
    anchors = {}
    for guid, box in boxes.items():
        centre = Point((float(box[0][0]) + float(box[1][0])) / 2, (float(box[0][1]) + float(box[1][1])) / 2)
        for well, polygon in wells:
            if polygon.contains(centre):
                anchors[guid] = well
                break
    return anchors


def _stacks(items, join=_stair_join, anchors=None):
    """items: [(guid, box)] of one kind -> [[guid, ...]] stacks (sorted);
    `join(box_a, box_b)` says when two items belong to one stack, and two
    items anchored in the same stairwell space always do."""
    edges = []
    anchors = anchors or {}
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            same_well = anchors.get(items[i][0]) is not None and anchors.get(items[i][0]) == anchors.get(items[j][0])
            if same_well or join(items[i][1], items[j][1]):
                edges.append((items[i][0], items[j][0]))
    grouped = connected_components(edges)
    seen = {g for group in grouped for g in group}
    stacks = [sorted(group) for group in grouped] + [[guid] for guid, _ in items if guid not in seen]
    return sorted(stacks)


def vertical_cores(ctx):
    elevations = [(storey.GlobalId, ctx.storey_elevation_m(storey)) for storey in ctx.storeys_sorted]
    stairs = sorted(elements_by_guid(ctx.model, ["IfcStair"]).items())
    lifts = _lift_items(ctx)
    source_of = {g: source for g, _e, source in lifts}
    parts = {g: _parts(e) for g, e in stairs}
    wanted = {e.GlobalId: e for _, e in stairs}
    wanted.update({e.GlobalId: e for _g, e, _s in lifts})
    for members in parts.values():
        wanted.update({p.GlobalId: p for p in members})
    boxes = _bboxes(ctx, list(wanted.values()))
    kinds = {"stair": ([(g, boxes.get(g) or _union([boxes.get(p.GlobalId) for p in parts[g]])) for g, _ in stairs], _stair_join),
             "lift": ([(g, boxes.get(g)) for g, _e, _s in lifts], _lift_join)}
    cores = []
    for kind, (items, join) in kinds.items():
        boxes = {g: b for g, b in items if b is not None}
        anchors = _anchors(ctx, boxes)
        for stack in _stacks(list(boxes.items()), join, anchors):
            box = _union([boxes[g] for g in stack])
            z_lo, z_hi = float(box[0][2]), float(box[1][2])
            storeys = [guid for guid, elevation in elevations if elevation is not None and z_lo - Z_MARGIN_M <= elevation <= z_hi + Z_MARGIN_M]
            cores.append({"key": stack[0], "kind": kind, "elements": stack, "storeys": storeys,
                          "sources": sorted({source_of[g] for g in stack if g in source_of}),
                          "anchors": sorted({anchors[g] for g in stack if g in anchors}),
                          "xy": (float(box[0][0]), float(box[0][1]), float(box[1][0]), float(box[1][1])), "z": (z_lo, z_hi)})
    return sorted(cores, key=lambda c: c["key"])


def _lift_serves(core, lift):
    """A lift stack serves a stair core when they share a storey and the
    lift stands within LIFT_CORE_REACH_M of the core or in its stairwell."""
    if not set(core["storeys"]) & set(lift["storeys"]):
        return False
    if set(core.get("anchors", ())) & set(lift.get("anchors", ())):
        return True
    a = ((core["xy"][0], core["xy"][1], 0.0), (core["xy"][2], core["xy"][3], 0.0))
    b = ((lift["xy"][0], lift["xy"][1], 0.0), (lift["xy"][2], lift["xy"][3], 0.0))
    return _plan_gap(a, b) <= LIFT_CORE_REACH_M


def _distance_to_box(point, xy):
    dx = max(xy[0] - point[0], 0.0, point[0] - xy[2])
    dy = max(xy[1] - point[1], 0.0, point[1] - xy[3])
    return math.hypot(dx, dy)


def _core_tables(ctx):
    from . import facts  # lazy: facts imports this module
    cores = ctx.fact("vertical_cores", vertical_cores)
    stair_cores = [c for c in cores if c["kind"] == "stair"]
    lift_cores = [c for c in cores if c["kind"] == "lift"]
    # dwellings per storey per stair core: each unit goes to the nearest core
    # spanning its storey, measured from its first entrance door (else its
    # first room's centroid)
    flats = {c["key"]: {} for c in stair_cores}
    graph = ctx.graph
    units = ctx.fact("dwelling_units", facts.dwelling_units) if ctx.graph_usable() else []
    for unit in units:
        candidates = [c for c in stair_cores if unit["storey"] in c["storeys"]]
        if not candidates:
            continue
        point = None
        for door in unit["entrance_doors"]:
            point = graph.door_points.get(door)
            if point is not None:
                break
        if point is None:
            point = graph.centroid(unit["rooms"][0])
        nearest = min(candidates, key=lambda c: (_distance_to_box(point, c["xy"]) if point is not None else 0.0, c["key"]))
        flats[nearest["key"]][unit["storey"]] = flats[nearest["key"]].get(unit["storey"], 0) + 1
    stair = {}
    for core in stair_cores:
        values = {"core_storeys": float(len(core["storeys"])),
                  "core_flats_per_floor": float(max(flats[core["key"]].values(), default=0)),
                  "core_has_lift": 1.0 if any(_lift_serves(core, lift) for lift in lift_cores) else 0.0}
        for guid in core["elements"]:
            stair[guid] = values
    storey_stairs = {s.GlobalId: 0.0 for s in ctx.storeys_sorted}
    storey_lifts = dict(storey_stairs)
    for core in cores:
        table = storey_stairs if core["kind"] == "stair" else storey_lifts
        for guid in core["storeys"]:
            table[guid] = table.get(guid, 0.0) + 1.0
    return {"stair": stair, "storey_stairs": storey_stairs, "storey_lifts": storey_lifts}


def stair_core_storeys(ctx):
    return {g: v["core_storeys"] for g, v in ctx.fact("core_tables", _core_tables)["stair"].items()}


def stair_core_flats_per_floor(ctx):
    return {g: v["core_flats_per_floor"] for g, v in ctx.fact("core_tables", _core_tables)["stair"].items()}


def stair_core_has_lift(ctx):
    return {g: v["core_has_lift"] for g, v in ctx.fact("core_tables", _core_tables)["stair"].items()}


def storey_stair_cores(ctx):
    return ctx.fact("core_tables", _core_tables)["storey_stairs"]


def storey_lift_cores(ctx):
    return ctx.fact("core_tables", _core_tables)["storey_lifts"]
