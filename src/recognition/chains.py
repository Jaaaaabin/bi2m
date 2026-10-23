"""The vertical-chain skeleton, shared since 2026-10-09: how
elements on adjacent storeys are matched into
edges, and how a finished chain names its ends.

A chain detector buckets its elements by storey, orders the storeys
(`storeys.ordered_storeys_with`), draws an edge between two elements on
adjacent storeys that sit within a plan tolerance of each other
(`adjacent_storey_edges`), merges the edges into chains
(`components.connected_components`), sorts each chain's members by
(storey rank, GUID) itself (docs/detectors.md rule 1), and labels them with
`roles_by_rank`.

Roles go by rank, not by position in the list, so several members tied on
the lowest or highest storey are all "base" or all "top".

`circulation` and `window_alignment` use both functions here, and
`envelope` uses `roles_by_rank`. `structural` keeps its own copies by
decision (docs/detectors.md rule 7).
"""


def adjacent_storey_edges(ordered, by_storey, tolerance_m):
    """(lower_id, upper_id) for every pair of entries on adjacent storeys of
    `ordered` whose x and y each differ by at most `tolerance_m`.
    `by_storey` maps a storey GUID to its (id, x, y) entries."""
    edges = []
    for lower_guid, upper_guid in zip(ordered, ordered[1:]):
        for lower_id, lx, ly in by_storey[lower_guid]:
            for upper_id, ux, uy in by_storey[upper_guid]:
                if abs(lx - ux) <= tolerance_m and abs(ly - uy) <= tolerance_m:
                    edges.append((lower_id, upper_id))
    return edges


def roles_by_rank(ranks):
    min_rank, max_rank = min(ranks), max(ranks)
    return ["base" if r == min_rank else "top" if r == max_rank else "intermediate" for r in ranks]
