"""Repeated unit layouts, matched on the door graph alone: groups of rooms
whose room-to-room door topology recurs elsewhere in the building, whatever
the rooms are called and wherever they sit.

unit_typology.py recognises a repeated unit by its PROGRAM - the multiset of
normalised room names - and its own docstring names the two limits that
leaves: a model whose rooms are unnamed, numbered or named in another
language yields nothing, and "same program" says nothing about layout. This
is the other half, and the one space syntax calls a genotype (Hillier &
Hanson 1984): two units are the same layout when their door graphs are
isomorphic, rooms matched by how many doors join them and by whether they
open to the outside of the unit. Names are never read for matching; they
appear in the evidence only so a reviewer can see what was found.

Candidates, per storey, on room_graph.py's door graph:
  - every connected component of at least DEFAULT_MIN_ROOMS rooms - a unit
    whose corridor is not modelled (data/test_5.ifc's apartments) or a whole
    floor plate;
  - every MAXIMAL single-door part of a component: the smaller side of a
    door whose removal splits the component, when nothing larger of the
    same kind contains it - a unit entered through one door from a
    corridor that IS modelled (private-corpus model 0208, content key
    70c5715315419707 below: 55 instances of one 8-room layout inside five
    48-room floors, which unit_typology sees only as two floor programs).
Both levels are kept on purpose: a floor plate and the apartment inside it
are different claims. A layout is dropped only when every instance of it
sits inside an instance of a larger recurring layout that recurs exactly
as often - then it adds nothing the larger record does not already imply,
because an isomorphism of the larger layouts carries their single-door
parts onto each other.

Matching. A room is labelled by its door count inside the candidate plus
whether it has a door out of it (a door that reaches no other modelled
room, or for a single-door part the door it hangs from); candidates are
bucketed by room count, door-edge count and a Weisfeiler-Lehman hash of
that labelled graph, and every bucket is split by an exact isomorphism test
(networkx VF2++), because the hash alone is not an isomorphism invariant.
The id carries the hash, so a layout keeps its id while its instance list
changes; two exact classes that share a hash take a -2, -3 suffix in order
of their smallest room GUID.

Room areas are evidence, not a gate. Measured 2026-09-23 on 45 models (the
four fixtures with rooms and doors, and 41 of 42 evenly spaced private-corpus
models - every ninth; 0298's door graph is unusable), the worst room-area
difference between an instance and the first one has no plateau to put a
threshold in: of the 49 layouts found, 18 are exact copies, 12 differ by up
to 10 %, 7 by 10-20 %, 7 by 20-50 % and 5 by more. The prototype's 238
pairwise comparisons had the same shape (89 exact, 76 up to 10 %, 19 at
10-20 %, 54 above). The 55-instance group above spans 10.1 % on its own,
so a 10 % tolerance would cut one plan in two. `areaSpreadMaxRel` reports
the worst difference (areas compared as sorted profiles), and the summary
says when it is large.

DEFAULT_MIN_ROOMS = 4, not unit_typology's 3. With three rooms there are
two unlabelled layouts in total (a chain and a triangle), so "bath - bed -
hall" and "kitchen - living - store" would be one layout; names keep
unit_typology's 3-room matches apart, topology cannot. On the sample the
cut costs 13 of 62 groups.

What the sample shows (DEFAULT settings): recurring layouts in 25 of the
42 private-corpus models against 17 for unit_typology; both fire on 16, this
alone on 9 - models whose repeated units are named inconsistently, in
German or not at all - and unit_typology alone on 1 (a 3-room type, below
DEFAULT_MIN_ROOMS). 144 of the 230 instances in those 42 models are
single-door parts of a larger floor, which unit_typology cannot see.
data/test_5.ifc gives the same 24 apartments unit_typology finds by name
and its 19-room office core three times; data/test_1.ifc its three
identical 13-room office floors; private-corpus model 0289 (043653332ec17ab1) one
6-room layout seven times where the names split it into two programs of
four and three instances.
"""

from collections import defaultdict

import networkx as nx

from ..access_graph import DEFAULT_DOOR_MARGIN_M, AccessGraph, space_label
from ..intent import make_member, make_intent
from ..room_graph import component_graph, components, depth_from, justified_measures, storey_room_graph, top_tier

DEFAULT_MIN_ROOMS = 4
DEFAULT_MIN_INSTANCES = 2
WL_ITERATIONS = 4
LARGE_AREA_SPREAD = 0.20


def _single_door_parts(H, min_rooms):
    """Maximal smaller sides of single-door links, as (rooms, root) pairs."""
    parts = []
    for left, right in sorted(tuple(sorted(edge)) for edge in nx.bridges(H)):
        if len(H.edges[left, right]["doors"]) != 1:
            continue
        cut = H.copy()
        cut.remove_edge(left, right)
        side_left = nx.node_connected_component(cut, left)
        side_right = nx.node_connected_component(cut, right)
        if len(side_left) == len(side_right):
            continue
        small, root = (side_left, left) if len(side_left) < len(side_right) else (side_right, right)
        if len(small) >= min_rooms:
            parts.append((frozenset(small), root))
    maximal = [(rooms, root) for rooms, root in parts if not any(rooms < other for other, _ in parts)]
    return sorted(set(maximal), key=lambda part: min(part[0]))


def _labelled(H, rooms, exits):
    S = component_graph(H, rooms)
    for room in S:
        S.nodes[room]["lab"] = f"{S.degree(room)}{'o' if room in exits else ''}"
    return S


def _area_profile(graph, rooms):
    return sorted(graph.polygons[room].area for room in rooms)


def _spread(reference, other):
    return max(abs(a - b) / max(a, b, 1e-9) for a, b in zip(reference, other))


def detect(model, extracted, file_key,
           door_margin_m=DEFAULT_DOOR_MARGIN_M, min_rooms=DEFAULT_MIN_ROOMS,
           min_instances=DEFAULT_MIN_INSTANCES, graph=None):
    graph = graph if graph is not None else AccessGraph(model, door_margin_m)
    if not graph.usable():
        return []

    candidates = []
    for storey_guid in sorted(graph.spaces_by_storey):
        if storey_guid in graph.degenerate_storeys:
            continue
        G, open_rooms = storey_room_graph(graph, storey_guid)
        for rooms in components(G):
            if len(rooms) < min_rooms:
                continue
            H = component_graph(G, rooms)
            exits = {room for room in rooms if room in open_rooms}
            candidates.append({"storey": storey_guid, "rooms": frozenset(rooms), "kind": "component",
                               "S": _labelled(H, rooms, exits)})
            for part, root in _single_door_parts(H, min_rooms):
                part_exits = {room for room in part if room in open_rooms} | {root}
                candidates.append({"storey": storey_guid, "rooms": part, "kind": "part",
                                   "S": _labelled(H, part, part_exits)})

    # Exact isomorphism classes, bucketed by a WL hash first.
    buckets = defaultdict(list)
    for candidate in sorted(candidates, key=lambda c: min(c["rooms"])):
        S = candidate["S"]
        candidate["hash"] = nx.weisfeiler_lehman_graph_hash(S, node_attr="lab", iterations=WL_ITERATIONS)
        buckets[(S.number_of_nodes(), S.number_of_edges(), candidate["hash"])].append(candidate)
    groups = []
    for key in sorted(buckets):
        classes = []
        for candidate in buckets[key]:
            for members in classes:
                if nx.vf2pp_is_isomorphic(members[0]["S"], candidate["S"], node_label="lab"):
                    members.append(candidate)
                    break
            else:
                classes.append([candidate])
        recurring = [members for members in classes if len(members) >= min_instances]
        for rank, members in enumerate(recurring, start=1):
            groups.append({"key": key, "rank": rank, "instances": members})

    # A nested layout that recurs exactly as often as a larger one containing
    # each of its instances is implied by it.
    def implied(group):
        for other in groups:
            if other is group or other["key"][0] <= group["key"][0]:
                continue
            if len(other["instances"]) != len(group["instances"]):
                continue
            if all(any(inst["rooms"] <= outer["rooms"] for outer in other["instances"])
                   for inst in group["instances"]):
                return True
        return False

    groups = [group for group in groups if not implied(group)]

    intents = []
    for group in groups:
        instances = group["instances"]
        n_rooms, n_links, layout_hash = group["key"]
        first = instances[0]
        S = first["S"]
        reference_areas = _area_profile(graph, first["rooms"])
        spread = max(_spread(reference_areas, _area_profile(graph, inst["rooms"])) for inst in instances[1:])
        exits = sorted(room for room in S if S.nodes[room]["lab"].endswith("o"))
        root_kind = "a door out of the unit"
        if exits:
            steps = depth_from(S, exits)
        else:
            steps = depth_from(S, top_tier(justified_measures(S)["rra"]))
            root_kind = "its most integrated room"
        profile = [sum(1 for value in steps.values() if value == depth) for depth in range(max(steps.values()) + 1)]
        rings = S.number_of_edges() - n_rooms + 1

        storey_guids = sorted({inst["storey"] for inst in instances})
        storey_names = sorted({graph.storey_name(guid) for guid in storey_guids})
        all_rooms = sorted({room for inst in instances for room in inst["rooms"]})
        unit_doors = sorted({
            door
            for inst in instances
            for _, _, data in inst["S"].edges(data=True)
            for door in data["doors"]
        })
        kinds = {kind: sum(1 for inst in instances if inst["kind"] == kind) for kind in ("component", "part")}
        suffix = f"-{group['rank']}" if group["rank"] > 1 else ""
        sample = [space_label(graph.space_by_guid[room]) for room in sorted(first["rooms"])]

        intents.append(make_intent(
            intent_id=f"{file_key}-unitlayout-{n_rooms}-{layout_hash[:12]}{suffix}",
            intent_type="unit_layout_recurrence",
            label=f"Repeated layout x{len(instances)} ({n_rooms} rooms, {n_links} door links)",
            members=[
                make_member(room, ifc_class="IfcSpace") for room in all_rooms
            ] + [
                make_member(door, role="context", ifc_class="IfcDoor") for door in unit_doors
            ],
            detector="unit_layout",
            rule="door_graph_isomorphism",
            summary=(
                f"One {n_rooms}-room door layout occurs {len(instances)} times across "
                f"{len(storey_guids)} storey(s) ({', '.join(storey_names)}): every instance has the "
                f"same room-to-room door graph ({f'{rings} ring(s)' if rings else 'no rings'}; rooms by "
                f"door-steps from {root_kind}: {'-'.join(str(count) for count in profile)}). Matched on "
                f"topology alone, not on room names or position. Room areas differ by up to {spread:.0%} "
                f"between instances"
                + (", so this may be one plan built in different sizes" if spread > LARGE_AREA_SPREAD else "")
                + ". Instances: "
                + (f"{kinds['component']} self-contained group(s) of rooms" if kinds["component"] else "")
                + (" and " if kinds["component"] and kinds["part"] else "")
                + (f"{kinds['part']} part(s) of a larger floor, each entered through one door" if kinds["part"] else "")
                + "."
            ),
            related_guids=storey_guids,
            metrics={
                "instanceCount": len(instances),
                "roomsPerUnit": n_rooms,
                "doorLinksPerUnit": n_links,
                "rings": rings,
                "depthProfile": profile,
                "depthRoot": "exit" if exits else "core",
                "instanceKinds": kinds,
                "areaSpreadMaxRel": round(spread, 4),
                "areaProfileM2": [round(area, 1) for area in reference_areas],
                "storeys": storey_names,
                "storeyCount": len(storey_guids),
                "totalSpaces": len(all_rooms),
                "layoutHash": layout_hash,
                "sampleRooms": sample,
            },
        ))

    return intents
