"""Room graph and justified-graph (space syntax) measures over AccessGraph.

Shared by space_syntax.py and unit_layout.py, the two detectors that read the
door/space graph as a GRAPH - depth, rings, isomorphism - rather than as a
set of connected groups. It adds no geometry of its own: everything here is
derived from what access_graph.AccessGraph already built (footprints, door
points, which rooms each door reaches), so no triangulation pass is repeated.
This shared graph module is new and additive, and nothing that existed
before imports it.

The room graph differs from AccessGraph.groups_for_storey in one deliberate
way. A door is a permeability between exactly two spaces, but at the 0.4 m
margin 10.9 % of door placements in a 41-model private-corpus sample reach three
or more rooms (522 of 4,786 placed doors; data/test_3.ifc: 40 of 135), and
groups_for_storey joins every pair of them. For connectivity that is
harmless. For depth and rings it is not: a door touching rooms A, B and C
becomes the triangle A-B-C, a ring that does not exist, and a shortcut
that makes C one step from B when the only way between them is through A.
Here such a door joins only its TWO NEAREST rooms (door point to footprint
distance, ties broken by GUID), which is where a door sitting in the wall
between two rooms physically leads. Components can therefore come out
smaller than space_access's: data/test_3.ifc Floor 1-2 have 22-room
components here where groups_for_storey reports 27. On data/test_1.ifc,
test_4 and test_5 the two agree.

Doors that reach exactly one room lead onto space nobody modelled - a
corridor that is not an IfcSpace, a balcony, the outside - and are kept
separately as `open_rooms`: they are how unit_layout.py knows where a unit
is entered from when the corridor in front of it is missing (data/
test_5.ifc: every apartment door reaches only the apartment).

Measures follow Hillier & Hanson (The Social Logic of Space, 1984) and
Hillier (Space is the Machine, 1996), computed on one connected component:
  - mean depth MD: average number of door-steps from a room to every other
    room of the component;
  - relative asymmetry RA = 2(MD - 1) / (k - 2), and real relative asymmetry
    RRA = RA / D_k with the diamond value D_k, which normalises for the
    component's size so storeys of 10 and 100 rooms are comparable. Lower
    RRA = more integrated; integration is conventionally 1/RRA, but RRA is
    what gets reported because it is finite for a room adjacent to all
    others (RRA 0);
  - choice: how often a room lies on shortest routes between two others
    (networkx betweenness, normalised) - through-movement;
  - space types: a = one door only (dead end), b = on no ring but more than
    one door (a room you pass through on a tree), c = on exactly one ring,
    d = where rings meet (two or more ring neighbours beyond a single loop);
    operationalised on the biconnected blocks of three or more rooms;
  - rings: independent cycles, E - V + 1 for a connected component;
  - cut rooms (articulation points) and single-door links (bridges whose
    edge carries one door; two doors between the same rooms are an
    alternative, not a single point of failure).
"""

import math

import networkx as nx
from shapely.geometry import Point


def _storey_scan(graph, storey_guid):
    """The door-link scan behind storey_room_graph, once per (graph, storey):
    (nodes in GUID order, [(pair, sorted doors)] in pair order, [(room,
    doors)] in door order). Memoised on the graph instance (2026-10-22: five
    callers built the same graph 28 times for 6 storeys), so a hand-built
    graph (AccessGraph.__new__ in verify_soft_signals) gets it too."""
    scans = graph.__dict__.setdefault("_storey_scans", {})
    if storey_guid in scans:
        return scans[storey_guid]
    nodes = sorted(graph.spaces_by_storey.get(storey_guid, []))
    edges = {}
    open_rooms = {}
    for door_guid in sorted(graph.door_links):
        door_storey, reached = graph.door_links[door_guid]
        if door_storey != storey_guid or not reached:
            continue
        if len(reached) == 1:
            open_rooms.setdefault(reached[0], []).append(door_guid)
            continue
        if len(reached) > 2:
            point = graph.door_points.get(door_guid)
            if point is None:
                continue
            here = Point(*point)
            reached = sorted(reached, key=lambda guid: (graph.polygons[guid].distance(here), guid))[:2]
        pair = tuple(sorted(reached))
        edges.setdefault(pair, []).append(door_guid)
    scan = (nodes, [(pair, sorted(doors)) for pair, doors in sorted(edges.items())], list(open_rooms.items()))
    scans[storey_guid] = scan
    return scan


def storey_room_graph(graph, storey_guid):
    """(G, open_rooms) for one storey of an AccessGraph.

    G: networkx.Graph, nodes = the storey's leaf rooms (graph.spaces_by_storey,
    so containers, duplicates and rooms without a footprint are already out),
    inserted in GUID order; one edge per pair of rooms joined by at least one
    door, carrying `doors` (sorted door GUIDs). open_rooms: room guid ->
    sorted door GUIDs of the doors that reach that room and no other.

    Built fresh on every call from the memoised scan (_storey_scan), by the
    same insertions in the same order as before, so a caller that edits the
    graph it gets (neufert/facts.py removes nodes) edits its own copy."""
    nodes, edges, open_items = _storey_scan(graph, storey_guid)
    G = nx.Graph()
    G.add_nodes_from(nodes)
    for (left, right), doors in edges:
        G.add_edge(left, right, doors=list(doors))
    return G, {room: list(doors) for room, doors in open_items}


def components(G):
    """Connected components as sorted GUID lists, ordered by their smallest
    GUID - never by set iteration order, which follows the hash seed."""
    return sorted((sorted(component) for component in nx.connected_components(G)), key=lambda c: c[0])


def component_graph(G, nodes):
    """An independent copy of one component with nodes and edges inserted in
    GUID order, so every networkx traversal over it is reproducible."""
    H = nx.Graph()
    H.add_nodes_from(sorted(nodes))
    node_set = set(nodes)
    H.add_edges_from(sorted(
        (left, right, data) for left, right, data in G.edges(sorted(nodes), data=True)
        if left in node_set and right in node_set
    ))
    return H


def diamond_value(k):
    """D_k, the RA of the root of a 'diamond' justified graph with k nodes
    (Hillier & Hanson 1984) - the normaliser that turns RA into RRA."""
    return 2 * (k * (math.log2((k + 2) / 3) - 1) + 1) / ((k - 1) * (k - 2))


def justified_measures(H):
    """Space-syntax measures of one connected room graph with >= 3 rooms.

    Returns a dict: `k`, `doors` (door GUIDs on its edges), `rings`,
    `mean_depth`/`rra`/`choice`/`space_type` (room -> value), `cut_rooms`
    (sorted), `single_door_links` (sorted (room, room) pairs), `cyclic_blocks`
    (number of biconnected blocks with a ring), `max_depth`."""
    k = H.number_of_nodes()
    if k < 3:
        raise ValueError("justified measures need a connected component of at least 3 rooms")
    depths = {room: dict(nx.single_source_shortest_path_length(H, room)) for room in H}
    mean_depth = {room: sum(depths[room].values()) / (k - 1) for room in H}
    d_k = diamond_value(k)
    rra = {room: (2 * (mean_depth[room] - 1) / (k - 2)) / d_k for room in H}
    choice = nx.betweenness_centrality(H, normalized=True)

    blocks = [block for block in nx.biconnected_components(H) if len(block) >= 3]
    space_type = {}
    for room in H:
        ring_neighbours = sum(len(set(H[room]) & block) for block in blocks if room in block)
        if H.degree(room) == 1:
            space_type[room] = "a"
        elif ring_neighbours == 0:
            space_type[room] = "b"
        elif ring_neighbours == 2:
            space_type[room] = "c"
        else:
            space_type[room] = "d"

    return {
        "k": k,
        "doors": sorted({door for _, _, data in H.edges(data=True) for door in data["doors"]}),
        "rings": H.number_of_edges() - k + 1,
        "mean_depth": mean_depth,
        "rra": rra,
        "choice": choice,
        "space_type": space_type,
        "cut_rooms": sorted(nx.articulation_points(H)),
        "single_door_links": sorted(
            tuple(sorted(edge)) for edge in nx.bridges(H) if len(H.edges[edge]["doors"]) == 1
        ),
        "cyclic_blocks": len(blocks),
        "max_depth": max(max(row.values()) for row in depths.values()),
    }


def top_tier(values):
    """The rooms sharing the lowest value (floats compared at 1e-9), sorted by
    GUID - the 'core' of a ranking, with exact ties kept together rather than
    cut arbitrarily."""
    best = min(round(value, 9) for value in values.values())
    return sorted(room for room, value in values.items() if round(value, 9) == best)


def depth_from(H, sources):
    """Door-steps from the nearest of `sources` to every room it reaches."""
    return dict(nx.multi_source_dijkstra_path_length(H, set(sources), weight=lambda *_: 1))
