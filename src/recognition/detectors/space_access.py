"""Space access graph: which rooms a door actually connects, and therefore
which rooms are mutually reachable on a storey - plus the rooms that are
reachable from nothing at all.

The package's first tier-4 (path/route) detector on the granularity ladder,
and the first to build a GRAPH over spaces rather than a group of
similar-looking elements. It was ranked the single
highest-value addition: a `circulation` domain existed with two detectors
in it, yet nothing in the codebase could answer a routing question, because
nothing built an adjacency structure. circulation.py chains a vertical
stack of stair entities; circulation_horizontal.py keyword-matches space
names. Neither knows which room adjoins which.

Mechanism, and why it is geometric rather than relational. The IFC-native
answer would be IfcRelSpaceBoundary, which connection.py already reads -
but that relation exists in exactly ONE of the six corpus models (1032
entries in data/test_3.ifc, zero in the other five), so a detector built on
it is a one-model detector. This instead derives the same topology from
geometry every model does carry: each IfcSpace's own triangulated footprint
unioned into a 2D polygon, each IfcDoor's placement point, and a door is
taken to connect every same-storey space whose polygon lies within
DEFAULT_DOOR_MARGIN_M of that point.

DEFAULT_DOOR_MARGIN_M = 0.4 is not a guess - it is the measured plateau. A
door sits INSIDE the wall between two rooms, so neither room's polygon
contains its point; the margin has to reach across half a wall. Swept over
the 4 corpus models that have both spaces and doors, the "how many spaces
does one door touch" histogram moves as follows:

    margin   test_3        test_4        test_5        test_2
    0.15m    1x135         1x111         2x212,1x18    1x85
    0.40m    2x67,3x36     2x105,1x6     2x206,3x24    2x80,3x5
    0.80m    2x53,3x50     2x88,3x22     2x170,3x60    2x80,3x5

At 0.15m almost every door reaches only ONE room - too tight to cross the
wall. At 0.40m the dominant answer becomes exactly TWO in all four files
(105 of 111 doors in data/test_4.ifc, 206 of 236 in data/test_5.ifc, 80 of
86 in data/test_2.ifc), which is the physically correct cardinality
for a door and therefore strong evidence the association is real rather
than tuned. At 0.80m the three-space bucket grows in every file - the
margin has started reaching past the adjoining room into a third. 0.40m is
also the value half a typical 24cm masonry wall plus a frame predicts
independently. data/test_3.ifc is the noisiest (36 doors still reach 3
spaces at 0.40m) and is the reason the cardinality anomalies below are
reported rather than silently resolved.

Geometry health, confirmed before relying on any of it: space polygons
build for 100% of spaces in all four models (73/73, 108/108, 106/106,
302/302) and door placements resolve non-degenerately for 100% of doors
(86/86, 135/135, 111/111, 236/236) - none of the mapped-representation
breakage documented for IfcColumn (extraction/columns.py), IfcStairFlight
(vertical.py/circulation.py) or IfcBeam (beam_framing.py) affects IfcSpace
or IfcDoor placement in this corpus.

Three intent types, and the first NEGATIVE-POLARITY records in this
package. All 1264 prior intents asserted that
something IS there, and a validation panel has no way to rank a queue
of purely affirmative findings. Two of the three types here are assertions
of absence or of malformation, which is exactly what a reviewer should look
at first:

  - `access_reachable_group` (affirmative) - one connected component of the
    storey's access graph: these rooms can be walked between. A storey
    yielding more than one such intent has its rooms split into groups with
    no door path between them.
  - `access_isolated_space` (NEGATIVE) - a space no door touches at all.
    Either a genuinely sealed volume (a shaft, a void, a plenum) or a real
    modeling defect; the detector cannot tell which, which is precisely why
    it goes to a human rather than being filtered out.
  - `access_door_anomaly` (NEGATIVE) - a door whose resolved cardinality is
    not 2: reaching 1 space (an exterior door, or one side unmodeled) or 3+
    (an open-plan junction, or overlapping space footprints). This is the
    `IFC.DoorSpaceCardinalityReport` check, the
    closest conceptual match to this panel, computed here without
    topologicpy.

Not attempted here: shortest paths, travel distance and egress thresholds.
Those need this graph plus a metric cost per edge and a code threshold -
the separate [[bim-compliance]] layer. The graph is
the prerequisite, and it is what this module contributes.
"""

from collections import defaultdict

from ..access_graph import DEFAULT_DOOR_MARGIN_M, AccessGraph, space_label
from ..intent import make_member, make_intent

# A component of 2 rooms is already a meaningful "you can walk between
# these"; 1 is just an isolated room, which gets its own intent type.
DEFAULT_MIN_GROUP = 2


def detect(model, extracted, file_key,
           door_margin_m=DEFAULT_DOOR_MARGIN_M, min_group=DEFAULT_MIN_GROUP,
           graph=None):
    graph = graph if graph is not None else AccessGraph(model, door_margin_m)
    if not graph.usable():
        return []

    space_by_guid = graph.space_by_guid
    door_links = graph.door_links

    intents = []
    for storey_guid, storey_spaces in graph.spaces_by_storey.items():
        if storey_guid in graph.degenerate_storeys:
            continue  # footprints overlap too much to tell rooms apart (2026-10-08)
        storey_name = graph.storey_name(storey_guid)
        groups, touched = graph.groups_for_storey(storey_guid)

        for group in groups:
            if len(group) < min_group:
                continue
            group_doors = graph.doors_within(group)
            labels = [space_label(space_by_guid[guid]) for guid in sorted(group)]
            intents.append(make_intent(
                intent_id=f"{file_key}-access-group-{sorted(group)[0]}",
                intent_type="access_reachable_group",
                label=(
                    f"Mutually reachable rooms ({storey_name}, "
                    f"{len(group)} spaces via {len(group_doors)} doors)"
                ),
                members=(
                    [make_member(guid, ifc_class="IfcSpace") for guid in sorted(group)]
                    + [
                        make_member(guid, role="context", ifc_class="IfcDoor")
                        for guid in group_doors
                    ]
                ),
                detector="space_access",
                rule="door_space_reachability",
                summary=(
                    f"{len(group)} IfcSpace instances on storey {storey_name} are "
                    f"mutually reachable through {len(group_doors)} doors "
                    f"(door-to-space margin {door_margin_m}m). Rooms: "
                    f"{', '.join(labels[:8])}"
                    f"{f' and {len(labels) - 8} more' if len(labels) > 8 else ''}."
                ),
                related_guids=[storey_guid],
                metrics={
                    "storey": storey_name,
                    "spaceCount": len(group),
                    "doorCount": len(group_doors),
                    "doorMarginM": door_margin_m,
                    "groupsOnStorey": sum(1 for g in groups if len(g) >= min_group),
                },
            ))

        isolated = [guid for guid in storey_spaces if guid not in touched]
        if isolated:
            labels = [space_label(space_by_guid[guid]) for guid in isolated]
            # Graph health for the reviewer: on 27 of 80
            # library models every door "reaches" nothing because doors and
            # rooms hang off different storey objects or sit in different
            # frames, and the isolation is the detector's, not the building's.
            doors_here = [reached for door_storey, reached in door_links.values() if door_storey == storey_guid]
            doors_reaching = sum(1 for reached in doors_here if reached)
            intents.append(make_intent(
                intent_id=f"{file_key}-access-isolated-{storey_guid}",
                intent_type="access_isolated_space",
                polarity="negative",
                label=f"Rooms with no door access ({storey_name}, {len(isolated)})",
                members=[make_member(guid, ifc_class="IfcSpace") for guid in sorted(isolated)],
                detector="space_access",
                rule="space_without_door_access",
                summary=(
                    f"{len(isolated)} IfcSpace instances on storey {storey_name} are not "
                    f"reached by any IfcDoor within {door_margin_m}m - no modeled way in "
                    f"or out. Either sealed volumes (shafts, voids, plenums) or a modeling "
                    f"gap; this detector cannot distinguish the two. Rooms: "
                    f"{', '.join(labels[:8])}"
                    f"{f' and {len(labels) - 8} more' if len(labels) > 8 else ''}."
                ),
                related_guids=[storey_guid],
                metrics={
                    "storey": storey_name,
                    "isolatedCount": len(isolated),
                    "storeySpaceCount": len(storey_spaces),
                    "doorMarginM": door_margin_m,
                    "doorsOnStorey": len(doors_here),
                    "doorsReachingAnyRoom": doors_reaching,
                    "medianDoorToRoomM": (
                        round(graph.median_door_to_room_m, 3) if graph.median_door_to_room_m is not None else None
                    ),
                    # True when the storey has doors and none of them meets a
                    # room: read "isolated" as "unmatched" until that is explained.
                    "isolationSuspect": bool(doors_here) and doors_reaching == 0,
                    # True when the storey's room footprints overlap so much that
                    # rooms cannot be told apart (AccessGraph.degenerate_storeys).
                    "footprintsDegenerate": storey_guid in graph.degenerate_storeys,
                },
            ))

    # Storeys that have doors but no room footprint at all: the rooms were
    # not modelled there (private-corpus model 0062: 51 spaces on Level 0, doors on four
    # levels). One record per storey saying so, instead of every door on it
    # becoming an "anomaly" for reaching nothing (2026-09-23).
    for storey_guid, door_guids in sorted(graph.doors_by_storey.items()):
        if graph.spaces_by_storey.get(storey_guid):
            continue
        storey_name = graph.storey_name(storey_guid)
        intents.append(make_intent(
            intent_id=f"{file_key}-access-noroom-{storey_guid}",
            intent_type="access_storey_without_rooms",
            polarity="negative",
            label=f"Doors but no rooms modelled ({storey_name}, {len(door_guids)} doors)",
            members=[make_member(guid, ifc_class="IfcDoor") for guid in sorted(door_guids)],
            detector="space_access",
            rule="storey_without_space_footprints",
            summary=(
                f"Storey {storey_name} carries {len(door_guids)} IfcDoor instances but not one IfcSpace "
                f"with a footprint, so nothing on it can be reached or isolated: the rooms are not "
                f"modelled at this level. A modelling gap to record, not a door defect."
            ),
            related_guids=[storey_guid],
            metrics={"storey": storey_name, "doorCount": len(door_guids), "spaceCount": 0},
        ))

    # Door cardinality anomalies, one intent per storey per anomaly kind.
    # Doors on a storey without any room are covered by the record above.
    anomalies = defaultdict(list)
    for door_guid, (storey_guid, reached) in door_links.items():
        if not graph.spaces_by_storey.get(storey_guid):
            continue
        if storey_guid in graph.degenerate_storeys:
            continue  # an "under" anomaly there is what the overlapping footprints fabricate
        if len(reached) == 2:
            continue
        kind = "under" if len(reached) < 2 else "over"
        anomalies[(storey_guid, kind)].append((door_guid, len(reached)))

    for (storey_guid, kind), entries in anomalies.items():
        storey_name = graph.storey_name(storey_guid)
        counts = sorted({count for _, count in entries})
        explanation = (
            "an exterior door, or a door whose other side is not modeled as a space"
            if kind == "under" else
            "overlapping space footprints, or an opening onto an open-plan junction"
        )
        intents.append(make_intent(
            intent_id=f"{file_key}-access-cardinality-{kind}-{storey_guid}",
            intent_type="access_door_anomaly",
            polarity="negative",
            label=(
                f"Doors not connecting exactly 2 rooms ({storey_name}, "
                f"{len(entries)} doors reaching {'/'.join(str(c) for c in counts)})"
            ),
            members=[
                make_member(guid, ifc_class="IfcDoor")
                for guid, _ in sorted(entries)
            ],
            detector="space_access",
            rule="door_space_cardinality",
            summary=(
                f"{len(entries)} IfcDoor instances on storey {storey_name} resolve to "
                f"{'/'.join(str(c) for c in counts)} adjoining space(s) rather than the "
                f"expected 2 (margin {door_margin_m}m) - typically {explanation}."
            ),
            related_guids=[storey_guid],
            metrics={
                "storey": storey_name,
                "doorCount": len(entries),
                "cardinalities": counts,
                "anomalyKind": kind,
                "doorMarginM": door_margin_m,
            },
        ))

    return intents
