"""Egress reachability: which rooms can actually reach a way out, how far
they have to travel to do it, and - the part that turned out to matter most
on this corpus - which rooms cannot reach one at all.

The package's first TRUE tier-4 (path/route) detector on the granularity
ladder. space_access.py laid the foundation by building the door/space
graph; what remained was the metric cost per edge and the code thresholds. This adds
the metric cost and runs a real shortest-path search over it. It still does
NOT add code thresholds - see "What this deliberately does not claim" below.

Exits are seeded three ways, and the third is an assumption worth stating:
  1. Any room touched by a door the model tags `IsExternal` - a genuine way
     out of the building, the same signal egress_access.py reports.
  2. Any room touched by a door whose HOST WALL is tagged `IsExternal` and
     which reaches exactly one room on its storey (2026-10-08):
     312 doors in 10 of 23 local models sit in
     an external wall without a tag of their own, and on 4173e835... every
     door does, so the wall tag alone is not trusted - an interior door in a
     mis-tagged wall reaches two rooms. `exit_door_guids` holds the rule.
  3. Any room whose name marks it as protected vertical circulation (stair,
     elevator, lift, shaft, escalator, ramp - the keyword set vertical.py's
     `critical` flag already uses). On an upper storey there is no external
     door, and the real exit IS the stair core; without this seed every
     upper floor would trivially report zero reachable rooms. This is an
     assumption about the building, not a fact read from it, and it is why
     `exitSeedKinds` is reported per intent.

Path cost is a polyline through doorways: from a room's interior point, to
the door, to the next room's interior point, summed along the route, with
Dijkstra from the exit set. Room points come from
`AccessGraph.centroid` (shapely's representative_point, guaranteed to lie
inside even an L-shaped room), door points from the door placements the
graph already resolved.

That distance is a LOWER BOUND on real travel distance, and must be read as
one. It is a straight line between centroid and doorway, so it cuts through
furniture, ignores the actual walking line around a wall return, and takes
no account of the diagonal being unwalkable. A code-compliant travel
distance is measured along an actual path of travel; this is the
shortest-possible idealization of it. It is still informative - it orders
rooms correctly by remoteness and it cannot UNDER-report a violation, only
miss one.

What the corpus actually showed, and why the negative record exists. The
honest headline is that egress is largely NOT computable on these models,
for reasons that are themselves findings:
  - data/test_3.ifc Floor 0: 25 of 27 rooms reach an exit, median travel
    14.8m, max 29.0m - a real, usable result.
  - data/test_3.ifc Floors 1-3: only 2 of ~30 rooms reach anything. The
    stairwells are exactly the IfcSpace instances that reach the storey
    through IfcRelAggregates rather than a door (vertical.py documents this
    quirk; space_access.py already reports them as isolated), so the stair
    seed is present but connects to nothing.
  - data/test_5.ifc: 19 of 76 rooms per storey reach the single external
    door. The other 57 are the apartments, which connect to a corridor that
    is not modeled as an IfcSpace at all - the same fragmentation
    unit_typology.py turned to advantage.
  - data/test_4.ifc: 21 of 22 rooms reach an exit on each main storey,
    median 25.3m, max 42.0m. Its lowest and highest storeys have no exit
    seed whatsoever.
So `egress_unreachable` is not an edge case bolted on for completeness; on
most storeys in this corpus it is the majority finding, and it says
something true and useful: THE MODEL CANNOT DEMONSTRATE EGRESS for these
rooms. Whether that is a building problem or a modeling gap is exactly the
judgement a human validator should make, which is the whole point of the
panel.

What this deliberately does not claim. No code threshold is applied. Maximum
travel distance is jurisdictional (and depends on occupancy, sprinklering
and whether the route is protected), and encoding a clause is the
separate [[bim-compliance]] layer. The distance is
reported; the verdict is not.
"""

from ..access_graph import DEFAULT_DOOR_MARGIN_M, AccessGraph, space_label
from ..intent import make_member, make_intent
from ..properties import property_value
from .. import vocabulary
# The exit rule, the door-graph cost and Dijkstra are shared with the
# Neufert facts since 2026-10-18 (room_routes.py; the extraction was proven
# byte-identical on the corpus per hash seed). `exit_door_guids` stays
# importable from here for scripts/verify_soft_signals.py.
from ..room_routes import exit_door_guids, host_element as _host_element, shortest_distances, storey_adjacency  # noqa: F401

# Same keyword set vertical.py's `critical` flag uses (kept in step by hand;
# the shared vocabulary table is recognition/vocabulary.py).
VERTICAL_EGRESS_KEYWORDS = vocabulary.words("vertical_core")  # recognition/vocabulary.py, 2026-10-08
DEFAULT_MIN_ROOMS = 2


def _is_vertical_egress(space):
    return vocabulary.matches(vocabulary.space_text(space), "vertical_core")


def detect(model, extracted, file_key,
           door_margin_m=DEFAULT_DOOR_MARGIN_M, min_rooms=DEFAULT_MIN_ROOMS,
           graph=None):
    graph = graph if graph is not None else AccessGraph(model, door_margin_m)
    if not graph.usable():
        return []

    doors = list(model.by_type("IfcDoor"))
    is_external = {door.GlobalId: property_value(door, ("IsExternal",)) is True for door in doors}
    host_external = {}
    for door in doors:
        host = _host_element(door)
        host_external[door.GlobalId] = host is not None and property_value(host, ("IsExternal",)) is True
    reach = {guid: len(reached) for guid, (_storey, reached) in graph.door_links.items()}
    exit_doors, _kinds = exit_door_guids([door.GlobalId for door in doors], is_external, host_external, reach)
    exit_kind = {guid: "external door" if is_external[guid] else "external wall door" for guid in exit_doors}

    intents = []
    for storey_guid, storey_spaces in graph.spaces_by_storey.items():
        if storey_guid in graph.degenerate_storeys:
            continue  # footprints overlap too much to tell rooms apart (2026-10-08)
        storey_name = graph.storey_name(storey_guid)

        seeds, seed_kinds = {}, set()
        for door_guid, (door_storey, reached) in graph.door_links.items():
            if door_storey == storey_guid and door_guid in exit_doors:
                for guid in reached:
                    seeds[guid] = 0.0
                    seed_kinds.add(exit_kind[door_guid])
        # An external door is a way OUT, not a route between two interior
        # rooms, so it contributes no traversal edge (room_routes.py).
        adjacency = storey_adjacency(graph, storey_guid, skip_doors=exit_doors)

        for guid in storey_spaces:
            space = graph.space_by_guid.get(guid)
            if space is not None and _is_vertical_egress(space):
                seeds.setdefault(guid, 0.0)
                seed_kinds.add("vertical core")

        if not seeds:
            # No way out modeled at all on this storey - reported as one
            # unreachable record below rather than silently skipped.
            distances = {}
        else:
            distances = shortest_distances(adjacency, seeds)

        reached_rooms = [guid for guid in storey_spaces if guid in distances]
        unreached = [guid for guid in storey_spaces if guid not in distances]

        # Only rooms that actually had to travel carry a meaningful figure;
        # a seed room sits at 0.0 and would drag every statistic down.
        travelled = sorted(
            (distances[guid], guid) for guid in reached_rooms if distances[guid] > 0
        )
        if travelled and len(reached_rooms) >= min_rooms:
            values = [value for value, _ in travelled]
            median = values[len(values) // 2]
            worst_value, worst_guid = travelled[-1]
            intents.append(make_intent(
                intent_id=f"{file_key}-egress-reach-{storey_guid}",
                intent_type="egress_reachable",
                label=(
                    f"Egress reachable ({storey_name}, {len(reached_rooms)} rooms, "
                    f"worst {worst_value:.1f}m)"
                ),
                members=[make_member(guid, ifc_class="IfcSpace") for guid in sorted(reached_rooms)],
                detector="egress_reachability",
                rule="shortest_path_to_exit",
                summary=(
                    f"{len(reached_rooms)} of {len(storey_spaces)} rooms on storey "
                    f"{storey_name} can reach an exit ({', '.join(sorted(seed_kinds))}). "
                    f"Travel distance median {median:.1f}m, worst "
                    f"{worst_value:.1f}m (\"{space_label(graph.space_by_guid[worst_guid])}\"). "
                    f"Measured centroid-to-doorway-to-centroid, so it is a LOWER BOUND "
                    f"on a real path of travel; no code threshold is applied."
                ),
                related_guids=[storey_guid],
                metrics={
                    "storey": storey_name,
                    "reachedCount": len(reached_rooms),
                    "storeySpaceCount": len(storey_spaces),
                    "exitSeedCount": len(seeds),
                    "exitSeedKinds": sorted(seed_kinds),
                    "travelMedianM": round(median, 2),
                    "travelMaxM": round(worst_value, 2),
                    "worstRoom": space_label(graph.space_by_guid[worst_guid]),
                    "isLowerBound": True,
                },
            ))

        if len(unreached) >= min_rooms:
            labels = [space_label(graph.space_by_guid[guid]) for guid in unreached]
            intents.append(make_intent(
                intent_id=f"{file_key}-egress-unreach-{storey_guid}",
                intent_type="egress_unreachable",
                polarity="negative",
                label=f"No modeled egress path ({storey_name}, {len(unreached)} rooms)",
                members=[make_member(guid, ifc_class="IfcSpace") for guid in sorted(unreached)],
                detector="egress_reachability",
                rule="no_path_to_exit",
                summary=(
                    f"{len(unreached)} of {len(storey_spaces)} rooms on storey "
                    f"{storey_name} have NO modeled door path to any exit"
                    + (
                        f" (exits seeded from: {', '.join(sorted(seed_kinds))})"
                        if seed_kinds else
                        " - and this storey has no exit seed at all: no external door "
                        "and no room named as a stair or shaft"
                    )
                    + f". The model cannot demonstrate egress for these rooms. This is "
                      f"commonly a modeling gap rather than a building defect - an "
                      f"unmodeled corridor, or a stairwell linked to the storey by "
                      f"IfcRelAggregates instead of a door - and distinguishing the two "
                      f"is exactly the reviewer's call. Rooms: {', '.join(labels[:8])}"
                    + (f" and {len(labels) - 8} more." if len(labels) > 8 else ".")
                ),
                related_guids=[storey_guid],
                metrics={
                    "storey": storey_name,
                    "unreachedCount": len(unreached),
                    "storeySpaceCount": len(storey_spaces),
                    "exitSeedCount": len(seeds),
                    "exitSeedKinds": sorted(seed_kinds),
                },
            ))

    return intents
