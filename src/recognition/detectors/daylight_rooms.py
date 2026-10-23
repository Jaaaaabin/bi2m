"""Daylit rooms: each IfcSpace's glazing ratio - the window area actually
serving that room divided by its own floor area - grouped per storey into
the rooms that meet a conventional daylight provision and the rooms that
have glazing but fall short of it.

This fills the one empty cell in registry.py's domain x scope grid
(daylight x storey, vacant since window_sight was superseded by
lighting_clusters on 2026-09-18) and, more importantly, closes what
had been the sharpest cross-discipline gap in the package: the
`daylight` domain never touched IfcSpace. window_alignment.py chains window
placements against each other; lighting_clusters.py classifies windows
against the building's ENVELOPE FOOTPRINT. Neither ever asks which room a
window actually lights, so "this room is naturally daylit" - the canonical
tier-1/tier-4 daylight intent on the granularity ladder - was unanswerable despite
a whole domain existing for daylight. This module answers it.

Window-to-room association, and why it is nearest-wins rather than
within-margin. space_access.py associates a DOOR with every space inside a
margin, because a door genuinely serves two rooms. A window serves one: the
room it opens into. Applying the door rule to windows fails, and fails
differently in each model - at a 0.4m margin 50 of 139 windows in
data/test_2.ifc reach NO space (its exterior walls are thick enough
that 0.4m never crosses them) while 76 of 126 in data/test_5.ifc already
reach TWO; widening to 1.0m fixes the first file (138 of 139 reach exactly
one) and makes the second worse (85 reach two, 14 reach three). There is no
single margin that is right for both.

Nearest-wins has no such tension, because the measured distances are not
close to ambiguous. The distance from a window to its NEAREST same-storey
space is at most 0.43m in data/test_2.ifc (89 of 139 at 0.00m, the
rest at ~0.43m) and at most 0.25m in data/test_5.ifc (120 of 126 at
0.00m). DEFAULT_WINDOW_REACH_M = 0.6 therefore captures 100% of windows in
both models with better than a 0.15m margin of safety, and the second-
nearest space - the one the margin rule was wrongly picking up - is far
enough behind that it never wins.

Glazing area comes from IfcWindow's own OverallWidth x OverallHeight,
present on 100% of windows in both models (139/139, 126/126) - the same
completeness window_alignment.py's docstring already records for this
element type. Floor area is the space's own unioned triangulated footprint
(access_graph.space_polygons), not a declared quantity: Qto_SpaceBase
Quantities.NetFloorArea is present in data/test_2.ifc but absent on
all 302 spaces of data/test_5.ifc, so a declared-quantity version of this
detector would be a one-model detector, exactly the trap connection.py
fell into.

DEFAULT_MIN_GLAZING_RATIO = 0.10 is a convention, NOT a derived or verified
threshold, and is the one number here a reviewer should treat with
suspicion. A glazed area of one tenth to one eighth of floor area is the
rule of thumb several residential codes state for habitable rooms; this
takes the looser end. It is deliberately a parameter rather than a
hardcoded rule because the actual figure is jurisdictional - encoding a
real code clause is the separate [[bim-compliance]] layer, not something
this detector should pretend to have done.
The `ratio` is reported per room in the evidence regardless, so a reviewer
can judge against their own threshold without re-running anything.

Rooms with NO glazing at all are counted in each storey's metrics
(`unglazedRooms`) but deliberately do NOT get their own intent. A
windowless corridor, store or toilet is normal and intended; flooding the
validation queue with them would bury the `daylight_deficit` records,
which are the genuinely interesting ones - a room someone DID glaze, but
under-provided.
"""

from collections import defaultdict

import ifcopenshell.util.element
from shapely.geometry import Point

from ifc_units import length_scale, placement_xy

from ..access_graph import space_label, space_polygons
from ..intent import make_member, make_intent
from ..spaces import index_by_storey, nearest_space

# Covers 100% of windows in both corpus models with >=0.15m to spare - see
# the module docstring for the measured nearest-distance distribution.
DEFAULT_WINDOW_REACH_M = 0.6
# A convention, not a verified rule. See the module docstring.
DEFAULT_MIN_GLAZING_RATIO = 0.10
DEFAULT_MIN_MEMBERS = 2
# Below this a "room" is a niche or a modeling artifact, and its ratio is
# dominated by noise in the footprint triangulation.
DEFAULT_MIN_FLOOR_AREA_M2 = 2.0


def detect(model, extracted, file_key,
           window_reach_m=DEFAULT_WINDOW_REACH_M,
           min_glazing_ratio=DEFAULT_MIN_GLAZING_RATIO,
           min_members=DEFAULT_MIN_MEMBERS,
           min_floor_area_m2=DEFAULT_MIN_FLOOR_AREA_M2):
    spaces = model.by_type("IfcSpace")
    windows = model.by_type("IfcWindow")
    if not spaces or not windows:
        return []

    polygons = space_polygons(model, spaces)
    if not polygons:
        return []

    # One scale for both uses below: window sizes (OverallWidth x
    # OverallHeight are raw attributes) and window placements, so a
    # millimetre model's windows land on their rooms (docs/detectors.md rule 13).
    unit_scale = length_scale(model)
    space_by_guid = {space.GlobalId: space for space in spaces}

    spaces_by_storey = index_by_storey(spaces, polygons)

    # space guid -> [(window guid, glazed area m2)]
    glazing = defaultdict(list)
    for window in windows:
        storey = ifcopenshell.util.element.get_container(
            window, ifc_class="IfcBuildingStorey")
        if storey is None:
            continue
        width, height = window.OverallWidth, window.OverallHeight
        if not width or not height:
            continue
        xy = placement_xy(window, unit_scale)
        if xy is None:
            continue
        point = Point(*xy)

        nearest, nearest_distance = nearest_space(point, spaces_by_storey.get(storey.GlobalId, []), polygons)
        if nearest is None or nearest_distance > window_reach_m:
            continue
        area = float(width) * float(height) * unit_scale * unit_scale
        glazing[nearest].append((window.GlobalId, area))

    intents = []
    for storey_guid, storey_spaces in spaces_by_storey.items():
        storey = model.by_guid(storey_guid)
        storey_name = storey.Name if storey and storey.Name else storey_guid

        lit, deficit, unglazed = [], [], 0
        for guid in storey_spaces:
            floor_area = polygons[guid].area
            if floor_area < min_floor_area_m2:
                continue
            entries = glazing.get(guid, [])
            if not entries:
                unglazed += 1
                continue
            glazed = sum(area for _, area in entries)
            ratio = glazed / floor_area
            record = (guid, glazed, floor_area, ratio, [w for w, _ in entries])
            (lit if ratio >= min_glazing_ratio else deficit).append(record)

        for records, intent_type, rule, affirmative in (
            (lit, "daylight_room_group", "space_glazing_ratio_met", True),
            (deficit, "daylight_deficit", "space_glazing_ratio_short", False),
        ):
            if len(records) < min_members:
                continue
            records.sort(key=lambda r: r[3], reverse=affirmative)
            ratios = [r[3] for r in records]
            detail = ", ".join(
                f"{space_label(space_by_guid[guid])} {ratio:.0%}"
                for guid, _, _, ratio, _ in records[:6]
            )
            window_guids = sorted({w for r in records for w in r[4]})

            intents.append(make_intent(
                intent_id=f"{file_key}-daylight-{'lit' if affirmative else 'short'}-{storey_guid}",
                intent_type=intent_type,
                polarity="positive" if affirmative else "negative",
                label=(
                    f"{'Daylit rooms' if affirmative else 'Under-glazed rooms'} "
                    f"({storey_name}, {len(records)})"
                ),
                members=[
                    make_member(guid, ifc_class="IfcSpace")
                    for guid, _, _, _, _ in records
                ] + [
                    make_member(guid, role="context", ifc_class="IfcWindow")
                    for guid in window_guids
                ],
                detector="daylight_rooms",
                rule=rule,
                summary=(
                    f"{len(records)} rooms on storey {storey_name} "
                    + (
                        f"reach a glazing ratio of at least {min_glazing_ratio:.0%} "
                        f"of their floor area"
                        if affirmative else
                        f"have glazing but fall below {min_glazing_ratio:.0%} of their "
                        f"floor area - someone glazed them, but under-provided"
                    )
                    + f" (window area from OverallWidth x OverallHeight, floor area from "
                      f"the space footprint; each window assigned to its nearest room "
                      f"within {window_reach_m}m). {detail}"
                    + (f" and {len(records) - 6} more." if len(records) > 6 else ".")
                ),
                related_guids=[storey_guid],
                metrics={
                    "storey": storey_name,
                    "roomCount": len(records),
                    "ratioMin": round(min(ratios), 4),
                    "ratioMax": round(max(ratios), 4),
                    "ratioMean": round(sum(ratios) / len(ratios), 4),
                    "thresholdRatio": min_glazing_ratio,
                    "unglazedRoomsOnStorey": unglazed,
                    "windowReachM": window_reach_m,
                },
            ))

    return intents
