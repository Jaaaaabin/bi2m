"""Space syntax on the door graph: which room is the hub of each storey's
connected rooms, found from how the rooms are joined rather than from what
they are called - plus where the door graph closes into rings.

The door/space graph (access_graph.py) is already what space syntax calls
the access graph of a building: rooms as nodes, doors as permeabilities
(Hillier & Hanson 1984). space_access.py asks only which rooms are joined;
egress_reachability.py measures metres from an exit. Neither reads the
graph's SHAPE. This does, with the justified-graph measures in
room_graph.py: mean depth, relative asymmetry normalised for size (RRA),
choice, the a/b/c/d space types and rings.

Two record types, per connected component of at least
DEFAULT_MIN_COMPONENT_ROOMS rooms on one storey:
  - `syntax_integration_core` (positive): the component's most integrated
    room - lowest RRA, exact ties kept together - as the only member. Its
    evidence carries every room's RRA, choice, space type and (where the
    storey has an external door) door-steps from the entrance.
  - `syntax_ring` (positive): the rooms that lie on a closed loop of the door
    graph (types c and d), when the component has one. A room on a ring can
    be left in two directions without retracing a door; everything else in
    the component is reached along a single route.

Why integration, and why this answers an earlier rejection. A
connectivity-degree fallback for circulation_horizontal was
considered and NOT built: a large room with many doors would read as a
corridor. Measured 2026-09-23 on 45 models - the four fixtures with rooms
and doors (test_1, test_3, test_4, test_5) and 41 of 42 evenly spaced
private-corpus models (every ninth; 0298's door graph is unusable) - over the
106 components of >= 5 rooms that contain a keyword-named circulation
room, taking the single top-ranked room of each component:

    ranked by        named circulation   component contains named
                     among the picks     circulation in the pick
    integration      0.81                0.88
    choice           0.84                0.87
    degree           0.53                0.77

Degree is what that rejection was about, and it deserved it. Integration
and choice are thirty points better, because a big room with many doors
that all lead to dead ends is shallow only to its own neighbours, not to
the rest of the storey. Integration is the measure that ranks; choice is
reported beside it. The core is the top TIER, not the top 10 % space syntax
often uses: on the same sample a 10 % core falls to 0.52 precision because
it pulls in the rooms around the hub (kitchens and WCs off the lobby),
which are integrated but are not what a reviewer is being asked about.

Names are not the ground truth here, and on the failures they are the part
that is wrong. private-corpus model 0253 (content key c14302b1d97ac16c) calls its
corridor "10 Floor" - a translation of the German Flur - and the keyword
detector instead picks "38 Entrance", the least integrated room of the
nine; integration puts "10 Floor" first (RRA 0.11, on 91 % of shortest
routes). In 0217 (6b9918fc20686013) the hub of a 46-room storey is a
566 m2 room named just "Raum" (RRA 0.30, choice 0.89) while the only
keyword match, "5 hall", is a 9.8 m2 apartment hall ranked 44th. In
components of >= 8 rooms with no keyword-named room at all, the top tier
is "Common Area" (test_4 - a known example of a missed
corridor), "Elevator" (test_5's office cores), "Common", "Loby", "Open
Office Space" and a room nobody renamed from "Room Name". So
`coreNamedAsCirculation` is reported as agreement, never used as a gate.
(Model numbers are the 2026-09-23 numbering; the keys are the identity.)

DEFAULT_MIN_COMPONENT_ROOMS = 10. Below that a component is usually a
dwelling or a suite: data/test_5.ifc's 24 apartments are 8-room components
whose top tier is a store room, and 24 hub records saying so would repeat
one fact 24 times. A unit's layout, depth profile and rings belong to its
unit_layout.py record, once per layout. At >= 10 rooms the 42 library
models give 72 core records (median 0 per model, max 10; 57 of the cores
are also named as circulation) and 18 ring records in 5 models; top-tier
precision against keyword names is 0.79 at this size.

Two things this is not. It is not a route length: depth is door-steps,
egress_reachability.py measures metres. And it is not a verdict about the
building. The door graph is what the model states; where corridors are not
modelled as spaces (67 of 370 private-corpus models) the
storey falls apart into small components and nothing here fires. Doors that
reach three rooms join only the nearest two (room_graph.py says why), so
components can be smaller than space_access's where that happens.
Degenerate storeys (AccessGraph.degenerate_storeys) are skipped outright.
"""


from ..access_graph import DEFAULT_DOOR_MARGIN_M, AccessGraph, space_label
from ..intent import make_member, make_intent
from ..properties import is_external
from ..room_graph import component_graph, components, depth_from, justified_measures, storey_room_graph, top_tier
# Read, never modified: the keyword list only feeds the `coreNamedAsCirculation`
# agreement metric. Nothing about the core depends on a name.
from .. import vocabulary

DEFAULT_MIN_COMPONENT_ROOMS = 10


def _named_as_circulation(space):
    return vocabulary.matches(vocabulary.space_text(space), "horizontal_circulation")


def _join_labels(labels, limit=3):
    shown = ", ".join(f'"{label}"' for label in labels[:limit])
    return shown + (f" and {len(labels) - limit} more" if len(labels) > limit else "")


def detect(model, extracted, file_key,
           door_margin_m=DEFAULT_DOOR_MARGIN_M, min_rooms=DEFAULT_MIN_COMPONENT_ROOMS,
           graph=None):
    graph = graph if graph is not None else AccessGraph(model, door_margin_m)
    if not graph.usable():
        return []

    external_doors = {
        door.GlobalId for door in model.by_type("IfcDoor")
        if is_external(door)
    }
    label_of = lambda guid: space_label(graph.space_by_guid[guid])  # noqa: E731

    intents = []
    for storey_guid in sorted(graph.spaces_by_storey):
        if storey_guid in graph.degenerate_storeys:
            continue
        storey_name = graph.storey_name(storey_guid)
        G, _ = storey_room_graph(graph, storey_guid)
        entrance_rooms = {
            room
            for door_guid, (door_storey, reached) in graph.door_links.items()
            if door_storey == storey_guid and door_guid in external_doors
            for room in reached
        }

        for rooms in components(G):
            if len(rooms) < min_rooms:
                continue
            H = component_graph(G, rooms)
            m = justified_measures(H)
            k = m["k"]
            core = top_tier(m["rra"])
            mean_rra = sum(m["rra"].values()) / k
            types = {kind: sum(1 for value in m["space_type"].values() if value == kind) for kind in "abcd"}
            seeds = sorted(room for room in rooms if room in entrance_rooms)
            steps = depth_from(H, seeds) if seeds else {}
            core_labels = [label_of(room) for room in core]
            named = [room for room in core if _named_as_circulation(graph.space_by_guid[room])]
            lead = core[0]
            cut = [room for room in core if room in set(m["cut_rooms"])]

            entrance_clause = (
                f" Counted from the {len(seeds)} room(s) with an external door, the deepest "
                f"room is {max(steps.values())} door(s) in."
                if steps else ""
            )
            intents.append(make_intent(
                intent_id=f"{file_key}-syntax-core-{rooms[0]}",
                intent_type="syntax_integration_core",
                label=f"Integration core: {core_labels[0]}"
                      + (f" +{len(core) - 1}" if len(core) > 1 else "")
                      + f" ({storey_name}, {k} rooms)",
                members=[make_member(room, ifc_class="IfcSpace") for room in core],
                detector="space_syntax",
                rule="lowest_real_relative_asymmetry",
                summary=(
                    f"Of the {k} rooms joined by doors on {storey_name}, {_join_labels(core_labels)} "
                    f"{'is' if len(core) == 1 else 'are'} the most integrated: {m['mean_depth'][lead]:.2f} "
                    f"door-steps on average to every other room (RRA {m['rra'][lead]:.2f} against a "
                    f"component mean of {mean_rra:.2f}), on {m['choice'][lead]:.0%} of the shortest "
                    f"routes between two other rooms"
                    + (", and a cut room: some rooms can only be reached through it" if cut else "")
                    + ". Found from the door graph alone, not from room names"
                    + ("; the room is also named as circulation." if named else ".")
                    + (f" The component has {m['rings']} ring(s) ({types['c'] + types['d']} rooms on a loop)"
                       if m["rings"] else " The component has no rings: every room is reached along one route")
                    + f" and {types['a']} dead-end room(s)."
                    + entrance_clause
                ),
                related_guids=[storey_guid],
                metrics={
                    "storey": storey_name,
                    "componentRooms": k,
                    "componentDoors": len(m["doors"]),
                    "core": core_labels,
                    "coreRRA": round(m["rra"][lead], 4),
                    "coreMeanDepth": round(m["mean_depth"][lead], 3),
                    "coreChoice": round(m["choice"][lead], 4),
                    "meanRRA": round(mean_rra, 4),
                    "coreIsCutRoom": bool(cut),
                    "coreNamedAsCirculation": bool(named),
                    "rings": m["rings"],
                    "spaceTypes": types,
                    "cutRooms": len(m["cut_rooms"]),
                    "singleDoorLinks": len(m["single_door_links"]),
                    "maxDepth": m["max_depth"],
                    "entranceRooms": len(seeds),
                    "entranceDepthMax": max(steps.values()) if steps else None,
                    # The whole justified graph of the component, keyed by GUID:
                    # [RRA, choice, space type, door-steps from an entrance or None].
                    "roomMeasures": {
                        room: [round(m["rra"][room], 4), round(m["choice"][room], 4),
                               m["space_type"][room], steps.get(room)]
                        for room in rooms
                    },
                },
            ))

            if m["rings"] > 0:
                ring_rooms = sorted(room for room in rooms if m["space_type"][room] in ("c", "d"))
                junctions = [room for room in ring_rooms if m["space_type"][room] == "d"]
                intents.append(make_intent(
                    intent_id=f"{file_key}-syntax-ring-{rooms[0]}",
                    intent_type="syntax_ring",
                    label=f"Access rings ({storey_name}, {m['rings']} ring(s) through {len(ring_rooms)} rooms)",
                    members=[make_member(room, ifc_class="IfcSpace") for room in ring_rooms],
                    detector="space_syntax",
                    rule="door_graph_cycle",
                    summary=(
                        f"{len(ring_rooms)} of the {k} rooms joined by doors on {storey_name} lie on a "
                        f"closed loop of the door graph ({m['rings']} independent ring(s)): each can be "
                        f"left in two directions without going back through the same door"
                        + (f", and {_join_labels([label_of(room) for room in junctions])} "
                           f"{'joins' if len(junctions) == 1 else 'join'} two or more loops" if junctions else "")
                        + f". The other {k - len(ring_rooms)} rooms are reached along a single route. "
                          f"Rooms: {_join_labels([label_of(room) for room in ring_rooms], limit=8)}."
                    ),
                    related_guids=[storey_guid],
                    metrics={
                        "storey": storey_name,
                        "rings": m["rings"],
                        "ringRooms": len(ring_rooms),
                        "junctionRooms": len(junctions),
                        "cyclicBlocks": m["cyclic_blocks"],
                        "componentRooms": k,
                    },
                ))

    return intents
