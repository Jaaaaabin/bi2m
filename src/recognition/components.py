"""Connected components over an edge list, shared since 2026-10-09.

`connected_components(edges)` is the edges-only union-find: an id that
appears in no edge is in no component, so a lone element never becomes a
one-member chain or cluster. `access_graph.AccessGraph` keeps the other
behaviour, a node set whose unconnected rooms stay singletons; the two are
different questions and stay two functions.

Components come back as a list of sets, in the order their roots are first
met while walking `edges` a second time. That order decides record order in
a shard, so `edges` must be a list, not a one-shot iterator. Callers sort
each component's members themselves (docs/detectors.md rule 1).

Used by `circulation`, `window_alignment`, `envelope` and
`lighting_clusters`. `structural` keeps its own copy by decision
(docs/detectors.md rule 7).
"""

from collections import defaultdict


def connected_components(edges):
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for a, b in edges:
        union(a, b)

    components = defaultdict(set)
    for a, b in edges:
        root = find(a)
        components[root].add(a)
        components[root].add(b)
    return list(components.values())
