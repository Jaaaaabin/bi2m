"""Exit doors and door-graph routes, shared since 2026-10-18 by
`egress_reachability` and the Neufert facts (`recognition/neufert/facts.py`),
which carried a copy of the same cost model (the
extraction was proven byte-identical on the 371-model corpus per hash seed
with the shard harness).

`host_element(door)`      the wall a door is cut into (FillsVoids ->
                          RelatingOpeningElement -> VoidsElements ->
                          RelatingBuildingElement), None where the export
                          omits a hop; egress_access's resolver.
`exit_door_guids(...)`    the pure rule: a door tagged IsExternal is an
                          exit; a door in a wall tagged IsExternal is an
                          exit only when it reaches exactly one room (reach
                          2 = an interior door in a mis-tagged wall).
`storey_adjacency(...)`   {room: [(room, metres)]} for one storey: every
                          door that reaches two or more rooms and has a
                          door point is an edge weighted centroid -> door
                          point -> centroid (a LOWER BOUND on the walking
                          distance: straight polyline, representative point
                          rather than the farthest corner). Doors in
                          `skip_doors` (the exits: a way OUT, not a route
                          between rooms) contribute no edge. Lists keep the
                          door-graph order, as the original loop did.
`shortest_distances(...)` Dijkstra from a {room: cost} seed dict over that
                          adjacency; rooms without a path are absent.
"""

import heapq
import math
from collections import defaultdict


def host_element(door):
    for rel in getattr(door, "FillsVoids", None) or []:
        opening = rel.RelatingOpeningElement
        if opening is None:
            continue
        for void in getattr(opening, "VoidsElements", None) or []:
            host = void.RelatingBuildingElement
            if host is not None:
                return host
    return None


def exit_door_guids(door_guids, is_external, host_external, reach):
    """The doors that count as exits, and the seed kinds they contribute.
    Pure, so the rule is checked without a model. Returns (guids, kinds)."""
    exits, kinds = set(), set()
    for guid in door_guids:
        if is_external.get(guid):
            exits.add(guid)
            kinds.add("external door")
        elif host_external.get(guid) and reach.get(guid, 0) == 1:
            exits.add(guid)
            kinds.add("external wall door")
    return exits, kinds


def storey_adjacency(graph, storey_guid, skip_doors=frozenset()):
    """Built fresh on every call from a scan memoised on the graph instance per
    (storey, skip set) - 2026-10-22: egress_reachability and the Neufert facts
    built it eight times per run - as a defaultdict, because shortest_distances
    reads `adjacency[current]` and relies on the auto-insert."""
    scans = graph.__dict__.setdefault("_adjacency_scans", {})
    key = (storey_guid, frozenset(skip_doors))
    if key not in scans:
        scans[key] = _adjacency_scan(graph, storey_guid, skip_doors)
    adjacency = defaultdict(list)
    for left, right, weight in scans[key]:
        adjacency[left].append((right, weight))
        adjacency[right].append((left, weight))
    return adjacency


def _adjacency_scan(graph, storey_guid, skip_doors):
    """[(left, right, weight)] in the door-graph order the original loop used."""
    edges = []
    for door_guid, (door_storey, reached) in graph.door_links.items():
        if door_storey != storey_guid:
            continue
        if door_guid in skip_doors:
            continue
        if len(reached) < 2:
            continue
        door_point = graph.door_points.get(door_guid)
        if door_point is None:
            continue
        for i in range(len(reached)):
            for j in range(i + 1, len(reached)):
                left, right = reached[i], reached[j]
                a, b = graph.centroid(left), graph.centroid(right)
                if a is None or b is None:
                    continue
                weight = math.dist(a, door_point) + math.dist(door_point, b)
                edges.append((left, right, weight))
    return edges


def shortest_distances(adjacency, seeds):
    distances = dict(seeds)
    queue = [(value, guid) for guid, value in seeds.items()]
    heapq.heapify(queue)
    while queue:
        cost, current = heapq.heappop(queue)
        if cost > distances.get(current, math.inf):
            continue
        for neighbour, weight in adjacency[current]:
            candidate = cost + weight
            if candidate < distances.get(neighbour, math.inf):
                distances[neighbour] = candidate
                heapq.heappush(queue, (candidate, neighbour))
    return distances
