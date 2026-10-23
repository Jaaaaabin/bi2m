"""Circulation detection - a continuous vertical run of IfcStair/IfcRamp
instances (one storey transition each, chained together the same way
structural.py chains column/wall supports) verified against real door
evidence on every storey it passes through.

Anchored on the stair/ramp entities themselves, doors as connectivity
evidence, IfcSpace only as an optional secondary lookup - deliberately NOT
anchored on vertical.py's IfcSpace footprint-recurrence groups (an earlier
version of this detector was: it filtered vertical.py's output to groups
whose member name matched a circulation keyword, then verified those
IfcSpace groups against doors). That approach only ever found a vertical
connection where a Revit export happened to model the shaft as one
identically-named/positioned IfcSpace per storey - it never looked at
IfcStair/IfcRamp at all, so a building using a different modeling
convention (or genuinely lacking that per-storey shaft space) would be
invisible to it despite having a perfectly real, IFC-native stair. This
version fixes that by making the stair/ramp entities themselves the primary
subject, exactly what "Circulation ... focusing on doors, ramps, and stairs"
calls for - IfcSpace now only ever answers "does the room this stair sits in
have a declared door", it never decides whether a circulation intent exists
in the first place. One consequence: elevators/lifts/shafts (which
vertical.py's keyword list also caught) are out of scope here - there is no
IfcStair/IfcRamp entity for those, they would need a different element type
(e.g. IfcTransportElement) and are left for a future addition, not silently
folded back in through the keyword list.

Anchor point, not shape, with a per-flight fallback: IfcStair/IfcRamp
themselves have no Body representation (only their child
IfcStairFlight/IfcRampFlight do - same fact vertical.py's own docstring
already established), AND IfcStair's own ObjectPlacement is degenerate -
(0, 0, storey elevation) for every single stair in every real file checked -
useless for telling two different stairs apart. `_resolve_anchors` uses
each flight CHILD's own placement instead (a single point, not a footprint,
but that's all a chaining anchor needs), EXCEPT that two DIFFERENT real
files hit two DIFFERENT, mutually exclusive breakages of this, so both a
placement- and a shape-based signal are tried per flight rather than
committing to one for an entire file - see `_resolve_anchors`'s own
docstring for the concrete before/after evidence from both.

Chaining: identical spirit to structural.py's column/wall matching -
storey-adjacent (lower, upper) pairs within DEFAULT_POSITION_TOLERANCE_M of
each other become an edge, edges sharing a member get merged via union-find
into one full run. A run must span >= DEFAULT_MIN_STOREYS to be reported (a
single-storey entry stair with nothing above/below it is correctly not
"vertical circulation").

Per-storey door verification - three tiers, in order, each checked against
the stair/ramp's own anchor point (not a vertical.py space group):
1. "boundary" - the anchor point falls inside an IfcSpace's own footprint on
   that storey (`_enclosing_spaces` - a lookup, not a discovery step), and
   that space has an IfcRelSpaceBoundary entry whose RelatedBuildingElement
   is an IfcDoor (the exact `boundaries_by_space` grouping connection.py
   already builds for walls, reused here filtered to IfcDoor).
2. "geometric" - no enclosing space had a declared door, so fall back to
   whether any IfcDoor's own placement point (not shape geometry - IfcDoor
   shapes in data/test_3.ifc resolve to a small LOCAL-origin bbox even with
   USE_WORLD_COORDS=True, the same placement-chain quirk as stair flights,
   just on a different element type) falls inside one of the SAME enclosing
   spaces' bbox, expanded by DEFAULT_SPACE_MARGIN_M (a room-sized
   containment check, not a fixed radius from the stair's own point -
   confirmed necessary: a real door verified against "026 Staircase" sits
   0.43m past that room's own bbox edge, so a small/wall-thickness-sized
   margin undercounts real matches). When more than one IfcSpace contains
   the anchor (common, not an edge case - see `_enclosing_spaces`'s own
   docstring for a real nested-open-plan example this fixes), every
   candidate is checked, most specific (smallest) first. If no enclosing
   space was found at all, falls back further to
   DEFAULT_DOOR_PROXIMITY_TOLERANCE_M as a plain point-to-point radius
   around the anchor - a cruder last resort for when there's no room
   geometry to lean on at all (e.g. a file with zero IfcSpace instances).
3. "none" - neither. A genuine negative finding, not an error - confirmed
   by direct investigation to still occur on real data even after both
   fixes above (see below), not a sign either fix is incomplete.

Verified against every real IFC file under data/ with an IfcStair/IfcRamp
that has flight geometry (six files, not just data/test_3.ifc):
- data/test_3.ifc: of 7 IfcStair instances, chaining recovers exactly 2
  three-storey runs (Floor 0 -> Floor 1 -> Floor 2, at the same two XY
  locations an earlier, IfcSpace-anchored version of this detector already
  found) - NOT four storeys, unlike that earlier version's answer. There is
  no IfcStair entity anywhere in the file for the Floor 2 -> Floor 3
  transition, even though a "...Staircase" IfcSpace with a recurring
  footprint exists on Floor 3 too - a real, previously invisible gap that an
  IfcSpace-anchored detector could never surface, because it never looks
  past the space layer.
- Two more, unrelated real models (distinct AR exports) each independently
  reproduce full or near-full runs (a 4-storey elevator-shaft-style run
  fully geometric-verified; a set of 4- and 2-storey stair runs, several
  fully verified) - confirming the design isn't overfit to data/test_3.ifc's
  specific numbers.
- A THIRD and FOURTH real model each had every single IfcStairFlight's own
  placement resolve to exactly (0, 0) (the file genuinely stores a zero
  relative offset - not a resolution bug - but that same flight's
  triangulated shape resolves correctly instead - the mirror image of
  data/test_3.ifc's IfcDoor shape quirk). Before the shape fallback in
  `_resolve_anchors` existed, this merged an entire building's 9 stairs into
  one bogus chain (or, in a fifth file, several bogus long chains); after
  it, both files instead recover multiple correctly-sized 2/4-storey runs.
- The nested-enclosing-space fix in `_enclosing_spaces` took 3 of these
  files' runs from partially- to fully-door-verified (an open-plan office
  model's stairs going from 1-of-4 to 4-of-4; a below-grade-heavy model
  going from 0-of-2 to 2-of-2 on one run).
- What's left unverified after both fixes is a genuine, investigated finding,
  not an unfixed bug: e.g. data/test_3.ifc's second stair run has its
  nearest real door 1.49m past its stairwell room's own bbox edge (vs. 0.0
  to 0.43m for every confirmed real match in this file) - a real gap in the
  source data (or an unusual door representation), not something a looser
  tolerance should paper over without more evidence either way.

No `related_space` member: an earlier version also attached each storey's
smallest enclosing IfcSpace as a "related_space" member, for Refer-highlight
context. Dropped per explicit request after `data/test_1.ifc` showed why:
its two ground-floor stairs sit ~28m apart in unrelated stairwells, but both
open onto the SAME open-plan "Hall" - so both runs' EG-storey related_space
came back identical, and that shared space is itself named exactly like a
`circulation_horizontal.py` keyword ("Hall"), making a Vertical Circulation
intent visually/evidentially point at a Horizontal Circulation space. Doors
stay (they're the run's own per-storey verification evidence, not a
borrowed room), only the room attachment was removed - `spaces` itself is
still resolved and used below for door-boundary/bbox lookups, just never
turned into a member.
"""

from collections import defaultdict

import ifcopenshell.util.element

from extraction.geometry_iteration import iterate_shapes
from extraction.geometry_math import shape2_location_verts
from extraction.model_loader import configure_settings
from ifc_units import length_scale, placement_xy

from ..chains import adjacent_storey_edges, roles_by_rank
from ..components import connected_components
from ..intent import make_member, make_intent
from ..storeys import get_storey, ordered_storeys_with

DEFAULT_POSITION_TOLERANCE_M = 0.5
DEFAULT_SPACE_MARGIN_M = 1.0
DEFAULT_DOOR_PROXIMITY_TOLERANCE_M = 3.0
DEFAULT_MIN_STOREYS = 2

RUN_TYPES = (
    ("IfcStair", "IfcStairFlight"),
    ("IfcRamp", "IfcRampFlight"),
)


DEGENERATE_ANCHOR_EPSILON_M = 1e-6


def _is_degenerate(point):
    """A real building's model origin essentially never sits exactly inside
    a stairwell, so an (almost) exact (0, 0) resolved point is treated as
    "not usable", not trusted at face value - see _resolve_anchors."""
    return abs(point[0]) < DEGENERATE_ANCHOR_EPSILON_M and abs(point[1]) < DEGENERATE_ANCHOR_EPSILON_M


def _flight_points(element, flight_class, scale):
    """(flight_entity, (x, y)) for each of `element`'s direct `flight_class`
    children (IfcStairFlight/IfcRampFlight), from the flight's OWN resolved
    placement in metres (`scale`: ifc_units.length_scale) - see module
    docstring for why `element`'s own placement isn't used instead. A flight
    without a placement contributes no point rather than a point at the
    origin."""
    points = []
    for rel in element.IsDecomposedBy:
        for child in rel.RelatedObjects:
            if child.is_a(flight_class):
                xy = placement_xy(child, scale)
                if xy is not None:
                    points.append((child, xy))
    return points


def _resolve_anchors(model, elements, flight_class, scale):
    """element.id() -> average world-space (x, y) anchor, one entry per
    element that has at least one usable flight point. Missing from the
    result entirely if it has no flight_class children, or every one of
    them is unusable.

    Two DIFFERENT, mutually exclusive placement/geometry quirks show up
    across the real files under data/, so both signals are tried per
    flight rather than committing to one for an entire file:
    - data/test_3.ifc: each flight's own placement
      (ifcopenshell.util.placement.get_local_placement) resolves correctly
      to real world coordinates, but its triangulated Body shape resolves
      to a small LOCAL-origin bbox even with USE_WORLD_COORDS=True (the
      same quirk documented for IfcDoor shapes elsewhere in this file).
    - data/test_1.ifc (a second, unrelated real model): the exact opposite -
      confirmed by direct inspection that every single IfcStairFlight's own
      ObjectPlacement.RelativePlacement.Location is a real, literal (0, 0, 0)
      relative to its parent (not a resolution bug, the file really does
      store it that way), so get_local_placement() degenerates to (0, 0)
      for every flight in the file - but that SAME flight's triangulated
      shape resolves to correct, real-looking world coordinates (confirmed:
      its bbox sits right next to a sibling IfcRailing's own, independently
      correct, non-degenerate placement). Left unguarded, every stair in
      that file reads as sitting at the same (0, 0) point, and
      tolerance-based storey-to-storey matching in `_find_runs` would merge
      every stair in the entire building into one nonsensical chain -
      confirmed this actually happened before this fallback was added.

    So: prefer each flight's placement point; only for a flight whose
    placement is degenerate, fall back to that flight's own shape bbox
    center (batched into one iterate_shapes call across every element
    needing it, not per-element, per geometry_iteration.py's own guidance).
    """
    points_by_id = {element.id(): _flight_points(element, flight_class, scale) for element in elements}
    needs_shape = [
        flight for points in points_by_id.values() for flight, point in points if _is_degenerate(point)
    ]

    shape_centers = {}
    if needs_shape:
        settings = configure_settings("triangle")
        for shape in iterate_shapes(settings, model, needs_shape, "triangle"):
            _, verts = shape2_location_verts(shape)
            xs, ys = [v[0] for v in verts], [v[1] for v in verts]
            shape_centers[shape.guid] = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)

    anchors = {}
    for element_id, points in points_by_id.items():
        resolved = []
        for flight, point in points:
            if _is_degenerate(point):
                point = shape_centers.get(flight.GlobalId)
            if point is not None and not _is_degenerate(point):
                resolved.append(point)
        if resolved:
            anchors[element_id] = (
                sum(p[0] for p in resolved) / len(resolved), sum(p[1] for p in resolved) / len(resolved)
            )
    return anchors


def _find_runs(model, ifc_class, flight_class, position_tolerance_m, min_storeys, scale):
    elements = model.by_type(ifc_class)
    anchors_by_id = _resolve_anchors(model, elements, flight_class, scale)

    by_storey = defaultdict(list)
    info_by_id = {}
    for element in elements:
        anchor = anchors_by_id.get(element.id())
        storey = get_storey(element)
        if storey is None or anchor is None:
            continue
        by_storey[storey.GlobalId].append((element.id(), anchor[0], anchor[1]))
        info_by_id[element.id()] = (element, storey, anchor)

    ordered = ordered_storeys_with(by_storey, model)

    edges = adjacent_storey_edges(ordered, by_storey, position_tolerance_m)

    storey_rank = {guid: i for i, guid in enumerate(ordered)}
    runs = []
    for chain_ids in connected_components(edges):
        distinct_storeys = {info_by_id[cid][1].GlobalId for cid in chain_ids}
        if len(distinct_storeys) < min_storeys:
            continue
        # (storey rank, GUID) - ids here are express ints, so this guards
        # insertion-order effects rather than hash randomisation; same idea.
        members_sorted = sorted(chain_ids, key=lambda cid: (storey_rank[info_by_id[cid][1].GlobalId], info_by_id[cid][0].GlobalId))
        runs.append([info_by_id[cid] for cid in members_sorted])
    return runs


def _boundaries_by_space(model):
    boundaries_by_space = defaultdict(list)
    for boundary in model.by_type("IfcRelSpaceBoundary"):
        boundaries_by_space[boundary.RelatingSpace.id()].append(boundary)
    return boundaries_by_space


def _space_bboxes(model):
    settings = configure_settings("triangle")
    bboxes = {}
    for shape in iterate_shapes(settings, model, model.by_type("IfcSpace"), "triangle"):
        _, verts = shape2_location_verts(shape)
        xs, ys = [v[0] for v in verts], [v[1] for v in verts]
        bboxes[shape.guid] = (min(xs), min(ys), max(xs), max(ys))
    return bboxes


def _door_points_by_storey(model, scale):
    by_storey = defaultdict(list)
    for door in model.by_type("IfcDoor"):
        storey = ifcopenshell.util.element.get_container(door, ifc_class="IfcBuildingStorey")
        if storey is None:
            continue
        xy = placement_xy(door, scale)
        if xy is None:
            continue
        by_storey[storey.GlobalId].append((door, xy))
    return by_storey


def _enclosing_spaces(anchor, storey_guid, spaces_by_storey, space_bboxes):
    """Every IfcSpace on this storey whose own footprint bbox contains the
    stair/ramp anchor point, most specific (smallest bbox area) first - a
    lookup for door evidence below, never a discovery step for whether a
    circulation intent exists.

    More than one candidate is common, not an edge case: confirmed on a
    real model (an open-plan office layout) where a stair anchor sits
    inside BOTH a 729m^2 "Creative Space" and a 2612m^2 "Hall" that nests
    around it, and neither has a declared door, but a door genuinely
    exists within the larger Hall's own footprint - checking only the
    single smallest/first containing space would report no door evidence
    at all, even though a real, IFC-declared door for the wider circulation
    zone this stair sits in does exist."""
    x, y = anchor
    candidates = []
    for space in spaces_by_storey.get(storey_guid, []):
        bbox = space_bboxes.get(space.GlobalId)
        if bbox is None:
            continue
        x0, y0, x1, y1 = bbox
        if x0 <= x <= x1 and y0 <= y <= y1:
            candidates.append(((x1 - x0) * (y1 - y0), space))
    candidates.sort(key=lambda c: c[0])
    return [space for _, space in candidates]


def _space_door_boundary(space, boundaries_by_space):
    for boundary in boundaries_by_space.get(space.id(), []):
        element = boundary.RelatedBuildingElement
        if element is not None and element.is_a("IfcDoor"):
            return element
    return None


def _door_within_bbox(bbox, storey_guid, doors_by_storey, margin_m):
    """Nearest IfcDoor (by its own placement point, not shape geometry - see
    module docstring) whose point falls within `bbox` expanded by
    `margin_m` - a room-sized, not a fixed-radius, containment check. The
    margin needs to cover a door's placement origin sitting outside the
    room's own footprint (confirmed on data/test_3.ifc: a real door serving
    a stairwell sits 0.43m past that room's bbox edge - not wall-thickness
    sized, more likely which jamb/leaf reference point the placement uses -
    so DEFAULT_SPACE_MARGIN_M is set generously above that, not tightly)."""
    x0, y0, x1, y1 = bbox
    x0, y0, x1, y1 = x0 - margin_m, y0 - margin_m, x1 + margin_m, y1 + margin_m
    best = None
    for door, (x, y) in doors_by_storey.get(storey_guid, []):
        if not (x0 <= x <= x1 and y0 <= y <= y1):
            continue
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        distance = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
        if best is None or distance < best[1]:
            best = (door, distance)
    return best


def _nearest_geometric_door(anchor, storey_guid, doors_by_storey, tolerance_m):
    """Last-resort point-to-point check, used only when the anchor falls
    inside no known IfcSpace at all (so there's no room bbox to check
    containment against)."""
    x, y = anchor
    best = None
    for door, (dx, dy) in doors_by_storey.get(storey_guid, []):
        distance = ((dx - x) ** 2 + (dy - y) ** 2) ** 0.5
        if distance <= tolerance_m and (best is None or distance < best[1]):
            best = (door, distance)
    return best


def detect(model, extracted, file_key,
           position_tolerance_m=DEFAULT_POSITION_TOLERANCE_M,
           space_margin_m=DEFAULT_SPACE_MARGIN_M,
           door_proximity_tolerance_m=DEFAULT_DOOR_PROXIMITY_TOLERANCE_M,
           min_storeys=DEFAULT_MIN_STOREYS):
    # Every point below is metres (docs/detectors.md rule 13): flight and door
    # placements through ifc_units, space footprints from ifcopenshell.geom.
    scale = length_scale(model)
    runs = []
    for ifc_class, flight_class in RUN_TYPES:
        runs.extend(
            (ifc_class, run)
            for run in _find_runs(model, ifc_class, flight_class, position_tolerance_m, min_storeys, scale)
        )
    if not runs:
        return []

    spaces_by_storey = defaultdict(list)
    for space in model.by_type("IfcSpace"):
        storey = get_storey(space)
        if storey is not None:
            spaces_by_storey[storey.GlobalId].append(space)
    boundaries_by_space = _boundaries_by_space(model)
    space_bboxes = _space_bboxes(model)
    doors_by_storey = _door_points_by_storey(model, scale)

    intents = []
    for ifc_class, run in runs:
        elements = [entry[0] for entry in run]
        storeys = [entry[1] for entry in run]
        anchors = [entry[2] for entry in run]
        storey_names = [storey.Name or storey.GlobalId for storey in storeys]

        verification = {}
        verified_door_guids = []
        for storey, anchor, storey_name in zip(storeys, anchors, storey_names):
            spaces = _enclosing_spaces(anchor, storey.GlobalId, spaces_by_storey, space_bboxes)

            door = None
            for space in spaces:
                door = _space_door_boundary(space, boundaries_by_space)
                if door is not None:
                    break
            if door is not None:
                verification[storey_name] = "boundary"
                verified_door_guids.append(door.GlobalId)
                continue

            match = None
            for space in spaces:
                match = _door_within_bbox(space_bboxes[space.GlobalId], storey.GlobalId, doors_by_storey, space_margin_m)
                if match is not None:
                    break
            if match is None and not spaces:
                match = _nearest_geometric_door(anchor, storey.GlobalId, doors_by_storey, door_proximity_tolerance_m)

            if match is not None:
                verification[storey_name] = "geometric"
                verified_door_guids.append(match[0].GlobalId)
            else:
                verification[storey_name] = "none"

        # `verification` is keyed by storey name, so len()/its keys are
        # already de-duplicated by storey - the same care structural.py's
        # own chaining takes, since a run can legitimately branch (e.g. two
        # colinear flights on one storey both matching a single flight
        # below) without spanning any more storeys than it actually does.
        distinct_storey_names = list(verification.keys())
        verified_count = sum(1 for status in verification.values() if status != "none")
        total = len(distinct_storey_names)
        ranks = [storey.Elevation for storey in storeys]
        run_label = elements[0].Name or ifc_class

        intents.append(make_intent(
            intent_id=f"{file_key}-circulation-" + "-".join(el.GlobalId for el in elements),
            intent_type="circulation_vertical_link",
            label=(
                f"Vertical circulation: {ifc_class} run across {total} storeys "
                f"({verified_count} of {total} door-verified)"
            ),
            members=[
                make_member(el.GlobalId, role=role, ifc_class=ifc_class)
                for el, role in zip(elements, roles_by_rank(ranks))
            ] + [
                # The verified doors as visible-but-uncolored "context" -
                # same convention connection.py uses for the IfcSpace a
                # wall group bounds: a real, geometric element that backs
                # up *why* this intent was recognized, shown alongside the
                # colored chain on Refer rather than hidden with the rest of
                # the model (ThatOpenCompanyLoader.js's `role !== "context"`
                # check already handles this generically - no frontend
                # change needed). Deduped since the same door can legitimately
                # verify more than one storey in `verification` above.
                make_member(guid, role="context", ifc_class="IfcDoor")
                for guid in dict.fromkeys(verified_door_guids)
            ],
            detector="circulation",
            rule="stair_ramp_vertical_continuity",
            summary=(
                f"{total} {ifc_class} instances ({run_label}) continue directly from "
                f"{storey_names[0]} to {storey_names[-1]} (flight position within "
                f"{position_tolerance_m}m) - "
                f"{', '.join(f'{name}: {verification[name]}' for name in distinct_storey_names)}. "
                f"{verified_count} of {total} storeys have door evidence (a declared IfcRelSpaceBoundary, "
                f"or a nearby door - see metrics.spaceMarginM/doorProximityToleranceM)."
            ),
            related_guids=verified_door_guids,
            metrics={
                "elementClass": ifc_class,
                "storeys": distinct_storey_names,
                "verification": verification,
                "verifiedCount": verified_count,
                "totalStoreys": total,
                "positionToleranceM": position_tolerance_m,
                "spaceMarginM": space_margin_m,
                "doorProximityToleranceM": door_proximity_tolerance_m,
            },
        ))

    return intents
