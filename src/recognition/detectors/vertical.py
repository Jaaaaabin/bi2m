"""Vertical space-connection detection - flags groups of IfcSpace instances
on different storeys that recur at (almost) the same XY footprint, e.g. a
stairwell/shaft/atrium modeled as one room per floor sharing a single
vertical volume. Still a geometric heuristic rather than a real IFC relation
(footprint recurrence is suggestive of a vertical connection, not a
guarantee - see connection.py for a detector that instead reads a native
IFC relation directly), but promoted out of registry.py's opt-in `draft`
tier once real runs confirmed it reliably recovers genuine vertical
connections (see next section) - still needs human validation in the panel,
same as every other category here.

Why footprint recurrence, not stair/ramp geometry: IfcStair/IfcRamp entities
themselves have no Body representation in data/test_3.ifc (only their child
IfcStairFlight/IfcRampFlight do), and even those flights' world-space
geometry - resolved via ifcopenshell.geom with USE_WORLD_COORDS=True, the
same setting extraction/columns.py and extraction/walls.py rely on - comes
back anchored near-local-origin instead of the real building coordinates
confirmed correct for IfcColumn/IfcSpace shapes in the same file (inspected
directly: a flight's own ObjectPlacement is (30.37, 9.4, 0) relative to its
parent IfcStair, yet its resolved shape vertices sit at (0,0)-(1.4,1.67) -
not the ~(30,9)-(32,11) a correctly-composed world transform would put them
at). ifcopenshell.util.placement.get_local_placement() *does* resolve that
flight's placement chain correctly (confirmed: matches the real building
coordinate range) but only gives a single point, not a footprint suitable
for matching against IfcSpace bounding boxes - and even with correct points,
data/test_3.ifc's own multi-storey "Staircase" IfcSpace instances (see next
paragraph) are a strictly more direct, IFC-native signal that needs none of
this geometry-chain reasoning at all.

The signal actually used instead: inspecting data/test_3.ifc found spaces
named "026 Staircase"/"130 Staircase"/"204 Staircase"/"305 Staircase" (one
per storey) share one identical XY footprint - each is IFC-linked to its
storey via IfcRelAggregates (Decomposes), NOT the usual
IfcRelContainedInSpatialStructure every other space in the file uses
(confirmed: ifcopenshell.util.element.get_container() returns None for
these; get_container() only walks ContainedInStructure, not Decomposes) -
apparently how this Revit export represents a vertical shaft space that
spans multiple levels. Grouping by recurring footprint sidesteps needing to
know that quirk exists: it recovers this stairwell AND 29 other recurring
footprints (offices/corridors/toilets/etc. stacked identically across
storeys - also legitimate vertical adjacency, just not safety-critical),
confirmed by direct inspection of data/test_3.ifc.

`_is_circulation` flags a group `critical` in its metrics/label whenever any
member's Name/LongName contains a circulation keyword (stair, elevator,
lift, shaft, escalator, ramp) - the "critical" case the vertical-
connection goal calls out - so a reviewer can prioritize those over routine
repeated-floor-plan matches in the same category.
"""

from collections import defaultdict

import ifcopenshell.util.element

from extraction.geometry_iteration import iterate_shapes
from extraction.geometry_math import shape2_location_verts
from extraction.model_loader import configure_settings

from ..intent import make_member, make_intent
from .. import vocabulary

DEFAULT_FOOTPRINT_TOLERANCE_M = 0.3
DEFAULT_MIN_STOREYS = 2

# The words live in recognition/vocabulary.py since 2026-10-08 ("vertical" and
# the German Treppe / Aufzug / Fahrstuhl / Stiege came from the 2026-09-23
# library survey). Affects only the `critical` flag and label, not ids.
CIRCULATION_KEYWORDS = vocabulary.words("vertical_core")


def _get_storey(space):
    """IfcRelContainedInSpatialStructure first (the normal path for every
    other space in data/test_3.ifc), falling back to a direct IfcRelAggregates
    (Decomposes) parent - the path this file's multi-storey "Staircase"
    spaces actually use instead (see module docstring)."""
    storey = ifcopenshell.util.element.get_container(space, ifc_class="IfcBuildingStorey")
    if storey is not None:
        return storey
    for rel in space.Decomposes:
        if rel.RelatingObject.is_a("IfcBuildingStorey"):
            return rel.RelatingObject
    return None


def _is_circulation(space):
    return vocabulary.matches(vocabulary.space_text(space), "vertical_core")


def detect(model, extracted, file_key,
           footprint_tolerance_m=DEFAULT_FOOTPRINT_TOLERANCE_M, min_storeys=DEFAULT_MIN_STOREYS):
    spaces = model.by_type("IfcSpace")
    if not spaces:
        return []

    settings = configure_settings("triangle")
    bbox_by_guid = {}
    for shape in iterate_shapes(settings, model, spaces, "triangle"):
        _, verts = shape2_location_verts(shape)
        xs, ys = [v[0] for v in verts], [v[1] for v in verts]
        bbox_by_guid[shape.guid] = (min(xs), min(ys), max(xs), max(ys))

    storeys_sorted = sorted(model.by_type("IfcBuildingStorey"), key=lambda s: s.Elevation)
    storey_index = {s.GlobalId: i for i, s in enumerate(storeys_sorted)}

    buckets = defaultdict(list)
    for space in spaces:
        bbox = bbox_by_guid.get(space.GlobalId)
        storey = _get_storey(space)
        if bbox is None or storey is None:
            continue
        key = tuple(round(v / footprint_tolerance_m) for v in bbox)
        buckets[key].append((space, storey, bbox))

    intents = []
    for members in buckets.values():
        distinct_storeys = {storey.GlobalId for _, storey, _ in members}
        if len(distinct_storeys) < min_storeys:
            continue

        members_sorted = sorted(members, key=lambda m: storey_index[m[1].GlobalId])
        anchor_space, _, anchor_bbox = members_sorted[0]
        label_name = anchor_space.LongName or anchor_space.Name or "space"
        storey_names = [storey.Name or storey.GlobalId for _, storey, _ in members_sorted]
        is_critical = any(_is_circulation(space) for space, _, _ in members_sorted)

        intents.append(make_intent(
            intent_id=f"{file_key}-vertical-" + "-".join(space.GlobalId for space, _, _ in members_sorted),
            intent_type="vertical_space_connection",
            label=(
                f"{'Critical vertical' if is_critical else 'Vertical'} connection: "
                f"\"{label_name}\" across {len(storey_names)} storeys"
            ),
            members=[
                make_member(space.GlobalId, role="member", ifc_class="IfcSpace")
                for space, _, _ in members_sorted
            ],
            detector="vertical",
            rule="space_footprint_recurrence",
            summary=(
                f"{len(members_sorted)} IfcSpace instances (\"{label_name}\") share the same XY "
                f"footprint (within {footprint_tolerance_m}m) across storeys "
                f"{', '.join(storey_names)} - a candidate continuous vertical connection "
                f"(stairwell/shaft/atrium)."
            ),
            related_guids=[storey.GlobalId for _, storey, _ in members_sorted],
            metrics={
                "storeys": storey_names,
                "footprint": [round(v, 3) for v in anchor_bbox],
                "toleranceM": footprint_tolerance_m,
                "critical": is_critical,
            },
        ))

    return intents
