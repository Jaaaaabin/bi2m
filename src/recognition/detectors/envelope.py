"""Building-envelope footprint continuity - one intent per group of
storeys whose floor-slab footprint continues from one level to the next,
capped by the roof as a final "top" node where it does (per explicit
request: roof handled together with floor/slab continuity, in one
category, not split out separately).

Distinct from vertical.py/circulation.py (both already spatial/vertical):
those track spaces/stairs recurring or running through storeys: this tracks
the building's own outer footprint - does the floor plate at one level
still cover roughly the same ground as the level below it, or does it step
back/cantilever - all the way up through the roof capping it. A genuine
setback (a real, intentional massing choice, e.g. a stepped tower) is
correctly reported as a break in the chain, not an error.

A building isn't guaranteed to have exactly one such footprint end to end
(a podium can split into two or more towers above some level; two blocks
on the same site may never have shared one footprint at all) - so, like
structural.py/circulation.py, this builds a graph (a node per distinct
footprint found at each level, an edge wherever two levels' footprints
overlap enough) and reports each CONNECTED COMPONENT as its own intent,
rather than assuming a single linear chain. A podium splitting into two
towers reports as ONE intent that branches (both towers share the podium
levels); two structures that never overlap report as two separate
intents. `_build_nodes` keeps every sufficiently-large footprint per
level (not just the single largest, as an earlier version of this detector
did) precisely so a second block/tower is never silently discarded.

Extraction: src/extraction/extractor.py's extract_envelope_shapes() ->
extraction_keys=("info_envelope_shapes",) in registry.py - each entry is one
IfcSlab or IfcRoof's own flat XY footprint (a list of 2-point edges, world-
coordinates), tagged with which of the two it came from. This module does
its OWN storey grouping and closed-loop merging, deliberately not reusing
src/extraction/floor_refinement.py's per-elevation grouping: that groups by
raw float shape elevation (exact dict-key equality), which is fine for
slabs alone but starts from a difference: this detector needs the roof kept
as a single, always-last node regardless of which storey the roof's own
IFC container relation happens to attach it to (commonly the topmost
storey, alongside that storey's own ceiling slab) - grouping by native
IfcBuildingStorey containment (the same relation every other detector here
already keys off) makes that an explicit, controlled choice instead of an
accident of float equality.

Multi-panel storeys (a floor plate made of several IfcSlab pieces) are
merged the same way src/extraction/floor_refinement.py merges multi-slab
storeys, but per footprint island rather than unconditionally for the
whole storey: each slab/roof's own polygon is computed individually, then
polygons that touch/overlap are transitively clustered (_cluster_infos)
and unioned - so two genuinely separate blocks on one storey, each made of
several panels, merge internally but never with each other.

Verified against every current data/*.ifc file with usable geometry - none
of them actually branches (no podium/multi-tower case in the current test
data), so this generalization is not yet empirically exercised on a real
branching building; _split into_chains's graph logic is covered by a
synthetic two-tower construction instead (see the detector's own tests, if
any exist, or re-derive: two 10x10 squares sharing no area, each present at
2+ levels, should report as two separate intents, not one and not zero).
data/test_3.ifc: 6 storeys, 11 slabs, 1 (unusable - see extract_roofs' own
docstring) roof -> one intent covering all 4 non-fragment storeys (a
small stair-landing storey between the ground floor and the next real
floor is correctly dropped as a fragment - see _drop_fragment_nodes -
rather than severing the chain), no roof (the file's own IfcRoof
aggregates nothing, a genuinely empty export, not a detector gap).
"""

from collections import defaultdict

from shapely.ops import unary_union

from ..chains import roles_by_rank
from ..components import connected_components
from ..footprints import info_polygon
from ..intent import make_member, make_intent
from ..storeys import get_storey

DEFAULT_IOU_CONTINUOUS = 0.5
DEFAULT_MIN_LEVELS = 2
DEFAULT_FRAGMENT_AREA_RATIO = 0.2
DEFAULT_FOOTPRINT_GAP_TOLERANCE_M = 0.6


def _cluster_infos(items, gap_tolerance_m):
    """items: [(info, polygon), ...] all at ONE level. Groups them into
    "footprint islands" via transitive polygon overlap (union-find over a
    pairwise .intersects() graph, checked on each polygon buffered out by
    `gap_tolerance_m`) - a multi-panel floor plate (several IfcSlab pieces
    forming one tower's floor) merges into one cluster, while a second,
    unconnected block on the same storey (a separate tower, or a podium
    that has already split above some level) stays its own cluster. This
    is what lets a level contribute MORE THAN ONE node to _build_nodes,
    instead of collapsing straight to a single "biggest footprint" pick
    and silently dropping any other block.

    The buffer exists because real adjacent floor panels routinely do NOT
    share an exact boundary - confirmed directly on data/test_5.ifc's
    "005 Ground Floor" (11 separate IfcSlab panels): real gaps between
    genuinely adjacent panels measured 0.25m-0.5m (structural bay/pour
    joints), while the next-nearest, genuinely non-adjacent pair in the
    same file measured 5m+. A zero-tolerance .intersects() check (the
    first version of this function) misread every one of those 11 panels
    as its own separate one-panel "block", contradicting the single
    2512sqm outer-perimeter footprint the old (pre-multi-footprint)
    edge-pooling approach had already found, which had already been
    recorded as correct for this exact file. 0.6m sits with
    headroom on both sides of that gap."""
    n = len(items)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    buffered = [polygon.buffer(gap_tolerance_m) for _, polygon in items]
    for i in range(n):
        for j in range(i + 1, n):
            if buffered[i].intersects(buffered[j]):
                union(i, j)

    clusters = defaultdict(list)
    for i in range(n):
        clusters[find(i)].append(items[i])
    return list(clusters.values())


def _iou(polygon_a, polygon_b):
    union_area = polygon_a.union(polygon_b).area
    if union_area == 0:
        return 0.0
    return polygon_a.intersection(polygon_b).area / union_area


def _build_nodes(model, info_shapes, gap_tolerance_m):
    """info_shapes -> a list of level nodes - POSSIBLY MORE THAN ONE PER
    RANK, one per distinct footprint island found at that level (see
    _cluster_infos), plus a final synthetic "roof" rank pooling every
    IfcRoof-sourced entry regardless of its own IFC container - the roof
    caps the whole building architecturally even where a real file's
    container relation happens to attach it to the topmost storey
    alongside that storey's own ceiling slab (see module docstring)."""
    storeys_sorted = sorted(model.by_type("IfcBuildingStorey"), key=lambda s: s.Elevation)
    storey_rank = {s.GlobalId: i for i, s in enumerate(storeys_sorted)}
    storey_name = {i: (s.Name or s.GlobalId) for i, s in enumerate(storeys_sorted)}
    roof_rank = len(storeys_sorted)

    by_rank = defaultdict(list)
    for info in info_shapes:
        if info["source"] == "IfcRoof":
            by_rank[roof_rank].append(info)
            continue
        element = model.by_guid(info["id"])
        storey = element and get_storey(element)
        if storey is None or storey.GlobalId not in storey_rank:
            continue
        by_rank[storey_rank[storey.GlobalId]].append(info)

    nodes = []
    for rank in sorted(by_rank):
        items = [(info, polygon) for info in by_rank[rank] for polygon in [info_polygon(info)] if polygon is not None]
        clusters = _cluster_infos(items, gap_tolerance_m)
        # Deterministic left-to-right order when a level has more than one
        # footprint, so "(block N)" labels stay stable across runs.
        clusters.sort(key=lambda cluster: unary_union([polygon for _, polygon in cluster]).centroid.x)
        multi_block = len(clusters) > 1
        base_label = "Roof" if rank == roof_rank else storey_name.get(rank, f"Level {rank}")
        for block_index, cluster in enumerate(clusters):
            # Morphological closing (buffer out, union, buffer back in) at
            # the same gap_tolerance_m used to cluster - fills the small
            # real gaps between adjacent panels (see _cluster_infos) into
            # one clean combined outline instead of leaving them as
            # lace-like internal holes in a plain unary_union.
            polygon = unary_union([p.buffer(gap_tolerance_m) for _, p in cluster]).buffer(-gap_tolerance_m)
            if polygon.area <= 0:
                continue
            nodes.append({
                "rank": rank,
                "is_roof": rank == roof_rank,
                "label": f"{base_label} (block {block_index + 1})" if multi_block else base_label,
                "storey_guid": None if rank == roof_rank else storeys_sorted[rank].GlobalId,
                "polygon": polygon,
                "members": [(info["id"], info["source"]) for info, _ in cluster],
            })
    return nodes


def _drop_fragment_nodes(nodes, fragment_ratio):
    """Drops a node whose footprint area is under `fragment_ratio` of the
    largest footprint found at an immediately adjacent rank - a stray
    small slab (a stair landing, a sump/pit) sitting between two much
    larger, otherwise-continuous floors, rather than a real storey
    footprint the chain should have to route through. Compared against
    each node's own adjacent-rank neighbors, not the whole building's
    largest footprint, so a genuinely tapering tower (each floor gradually
    smaller than the one below, but still comparable in scale to ITS
    neighbors) is never mistaken for a fragment - and, now that a rank can
    hold more than one node, against every node at that adjacent rank, not
    just one, so a fragment next to a level that has already split into
    several blocks is still judged fairly.

    Threshold picked from the full spread confirmed across every current
    data/*.ifc file, which splits cleanly in two with a wide gap between
    them: every genuine storey's area is at least 69% of its neighbor's
    (data/test_6.ifc's legitimately-narrower top floor), while every
    fragment found so far is under 5% of its neighbor's
    (data/test_3.ifc's stair-landing "mid level" storey at 4.9% -
    confirmed dropping it reconnects the real floor below it, at 95%
    direct overlap, previously hidden behind the landing's own near-zero
    overlap on both sides; data/test_4.ifc's basement sliver at 0.1%,
    which stays excluded either way since it has no larger neighbor
    below it to reconnect through) - 20% sits with comfortable headroom
    on both sides of that gap, not tuned to one specific case."""
    if len(nodes) < 2:
        return nodes
    ranks = sorted({node["rank"] for node in nodes})
    rank_index = {rank: i for i, rank in enumerate(ranks)}
    by_rank = defaultdict(list)
    for node in nodes:
        by_rank[node["rank"]].append(node)

    def neighbor_max_area(node):
        i = rank_index[node["rank"]]
        areas = []
        if i > 0:
            areas += [n["polygon"].area for n in by_rank[ranks[i - 1]]]
        if i < len(ranks) - 1:
            areas += [n["polygon"].area for n in by_rank[ranks[i + 1]]]
        return max(areas) if areas else None

    kept = []
    for node in nodes:
        neighbor_area = neighbor_max_area(node)
        if neighbor_area is None or node["polygon"].area >= fragment_ratio * neighbor_area:
            kept.append(node)
    return kept


def _setback_intents(nodes, ranks, nodes_by_rank, edges, iou_continuous, file_key):
    """Negative-polarity companion (docs/detectors.md rule 12): every footprint that
    does NOT continue from the level below it. The module docstring has
    always said a setback is "a break in the chain, not an error" - true, but
    until now the break was not itself a record a reviewer could look at.
    For each node above the lowest rank that has no continuity edge to any
    node one rank down, one `envelope_setback` record names the best-
    overlapping footprint below it (or the largest, if nothing overlaps at
    all) and the IoU that fell short. A genuine stepped massing shows up
    here as design intent for a human to accept; a mis-modelled slab shows
    up as a gap to reject. Roof nodes are included: a roof much smaller than
    the top floor is a real (terrace) setback."""
    supported = {j for _, j in edges}
    intents = []
    for lower_rank, upper_rank in zip(ranks, ranks[1:]):
        for j in nodes_by_rank[upper_rank]:
            if j in supported:
                continue
            candidates = nodes_by_rank[lower_rank]
            if not candidates:
                continue
            best = max(candidates, key=lambda i: (_iou(nodes[i]["polygon"], nodes[j]["polygon"]), nodes[i]["polygon"].area))
            iou = _iou(nodes[best]["polygon"], nodes[j]["polygon"])
            lower_guids = [guid for guid, _ in nodes[best]["members"]]
            upper_guids = [guid for guid, _ in nodes[j]["members"]]
            area_ratio = nodes[j]["polygon"].area / nodes[best]["polygon"].area if nodes[best]["polygon"].area else 0
            intents.append(make_intent(
                intent_id=f"{file_key}-setback-" + "-".join(sorted(lower_guids) + sorted(upper_guids)),
                intent_type="envelope_setback",
                label=f"Footprint steps between {nodes[best]['label']} and {nodes[j]['label']} (overlap {iou:.0%})",
                members=[make_member(guid, role="base", ifc_class=src) for guid, src in nodes[best]["members"]]
                        + [make_member(guid, role="top", ifc_class=src) for guid, src in nodes[j]["members"]],
                detector="envelope",
                rule="footprint_setback",
                summary=(
                    f"{nodes[j]['label']} covers {area_ratio:.0%} of {nodes[best]['label']}'s area and overlaps it by "
                    f"{iou:.0%} of their combined footprint - below the {iou_continuous:.0%} continuity threshold, so the "
                    f"envelope steps here rather than continuing. A setback (intended massing) or a gap in the slab model."
                ),
                related_guids=[g for g in (nodes[best]["storey_guid"], nodes[j]["storey_guid"]) if g],
                metrics={"iou": round(iou, 3), "iouThreshold": iou_continuous, "areaRatioUpperToLower": round(area_ratio, 3),
                         "lower": nodes[best]["label"], "upper": nodes[j]["label"], "upperIsRoof": nodes[j]["is_roof"]},
                polarity="negative",
            ))
    return intents


def detect(model, extracted, file_key, iou_continuous=DEFAULT_IOU_CONTINUOUS, min_levels=DEFAULT_MIN_LEVELS,
           fragment_area_ratio=DEFAULT_FRAGMENT_AREA_RATIO, gap_tolerance_m=DEFAULT_FOOTPRINT_GAP_TOLERANCE_M):
    info_shapes = (extracted or {}).get("info_envelope_shapes") or []
    if not info_shapes:
        return []

    nodes = _build_nodes(model, info_shapes, gap_tolerance_m)
    nodes = _drop_fragment_nodes(nodes, fragment_area_ratio)
    if len(nodes) < min_levels:
        return []

    ranks = sorted({node["rank"] for node in nodes})
    nodes_by_rank = defaultdict(list)
    for i, node in enumerate(nodes):
        nodes_by_rank[node["rank"]].append(i)

    edges = []
    for lower_rank, upper_rank in zip(ranks, ranks[1:]):
        for i in nodes_by_rank[lower_rank]:
            for j in nodes_by_rank[upper_rank]:
                if _iou(nodes[i]["polygon"], nodes[j]["polygon"]) >= iou_continuous:
                    edges.append((i, j))

    intents = _setback_intents(nodes, ranks, nodes_by_rank, edges, iou_continuous, file_key)
    for chain_ids in connected_components(edges):
        chain_ranks = sorted({nodes[i]["rank"] for i in chain_ids})
        if len(chain_ranks) < min_levels:
            continue

        chain_nodes = sorted(chain_ids, key=lambda i: nodes[i]["rank"])
        roles = dict(zip(chain_nodes, roles_by_rank([nodes[i]["rank"] for i in chain_nodes])))
        chain_edge_ious = {
            (i, j): _iou(nodes[i]["polygon"], nodes[j]["polygon"])
            for (i, j) in edges if i in chain_ids and j in chain_ids
        }

        branches = len(chain_nodes) > len(chain_ranks)
        includes_roof = any(nodes[i]["is_roof"] for i in chain_nodes)
        rank_groups = [
            " & ".join(nodes[i]["label"] for i in chain_nodes if nodes[i]["rank"] == rank)
            for rank in chain_ranks
        ]
        all_member_guids = [guid for i in chain_nodes for guid, _ in nodes[i]["members"]]
        members = [
            make_member(guid, role=roles[i], ifc_class=source)
            for i in chain_nodes
            for guid, source in nodes[i]["members"]
        ]

        label = f"Building envelope: footprint continuous across {len(chain_ranks)} levels"
        if branches:
            label += f" ({len(chain_nodes)} footprints, splits partway up"
            label += ", roof included)" if includes_roof else ")"
        elif includes_roof:
            label += " (roof included)"

        intents.append(make_intent(
            intent_id=f"{file_key}-envelope-" + "-".join(all_member_guids),
            intent_type="envelope_footprint_continuity",
            label=label,
            members=members,
            detector="envelope",
            rule="footprint_overlap_continuity",
            summary=(
                f"{len(chain_ranks)} levels ({' -> '.join(rank_groups)}) each overlap the next by at least "
                f"{iou_continuous:.0%} of their combined footprint area "
                f"(lowest observed: {min(chain_edge_ious.values()):.0%})."
                + (" This footprint splits into multiple separate blocks partway up." if branches else "")
            ),
            related_guids=sorted({nodes[i]["storey_guid"] for i in chain_nodes if nodes[i]["storey_guid"]}),
            metrics={
                "levels": [nodes[i]["label"] for i in chain_nodes],
                "transitionIoU": {
                    f"{nodes[i]['label']} -> {nodes[j]['label']}": round(v, 3)
                    for (i, j), v in chain_edge_ious.items()
                },
                "includesRoof": includes_roof,
                "branches": branches,
                "iouThreshold": iou_continuous,
            },
        ))

    return intents
