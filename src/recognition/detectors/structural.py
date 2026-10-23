"""Structural vertical-support detection: a column/load-bearing wall whose
footprint recurs directly above another one, storey after storey - i.e. one
member plausibly carries its load down onto the next, forming a continuous
vertical load path. Each recognized intent covers a member's FULL run
through every level it continues on by default, not just one storey
transition at a time - a column continuing from Floor 0 through Floor 3
is one 4-member intent, not three separate 2-member ones.

Columns: matched purely on (x, y) location, reusing extracted["info_st_columns"]
- the same enriched, placement-based location alignment.py already trusts (see
its own docstring for why raw ObjectPlacement inspection alone isn't enough
for this file's columns).

Walls: matched on axis line - orientation (mod 180) plus the wall's fixed
coordinate on that axis - AND a minimum overlap between the two walls' spans
along their own length, so two colinear-but-disjoint wall segments on
adjacent storeys are never mistaken for one supporting the other. Only
axis-aligned walls (orientation within DEFAULT_WALL_ANGLE_TOLERANCE_DEG of 0
or 90) are matched - a deliberate scope limit, same spirit as alignment.py's
X/Y-only axes.

Self-contained wall extraction: reuses extraction.walls's pure functions
(get_wall_dimensions/calc_wall_loadbearing/enrich_wall_information) via
IfcDataExtractor.extract_structural_walls_only() - skips
post_process_walls()'s glue/curtainwall/floor-outlier steps entirely, since
those are display-oriented cleanup, not something a recognition detector's
raw axis-line matching needs.

Chaining mechanism: both column and wall matching first find the same
storey-to-storey "does A directly support B" edges as before (only ever
between ADJACENT structural storeys - storeys with none of the relevant
element, e.g. a mezzanine with no columns, are skipped rather than treated
as a break), then `_connected_chains` merges edges sharing a member via
union-find into one full run per structural stack, spanning however many
storeys that member actually continues through. A stack that genuinely
stops and a different one starts one storey up (no matching footprint/axis
between them) correctly stays as two separate intents - only actual
continuity gets merged. A chain can legitimately branch (e.g. one long wall
below matching two shorter, colinear wall segments split by a door on the
storey above) - `related_guids`/the label's storey count always de-duplicate
by storey, so a branch never gets miscounted as spanning more storeys than
it actually does, even though it does have more members than storeys.
Verified against data/test_3.ifc: chaining collapses what used to be 86
column-support pairs into 31 full-height column stacks (28 spanning all 4
structural storeys) and 35 wall-support pairs into 11 wall stacks (all 4
storeys, one with a branch).
"""

from collections import defaultdict

import ifcopenshell.util.element

from ..intent import make_member, make_intent

DEFAULT_COLUMN_TOLERANCE_M = 0.05
DEFAULT_WALL_ANGLE_TOLERANCE_DEG = 3
DEFAULT_WALL_POSITION_TOLERANCE_M = 0.1
DEFAULT_WALL_MIN_OVERLAP_M = 0.3


def _get_storey_cache(model):
    cache = {}

    def get_storey(guid):
        if guid not in cache:
            element = model.by_guid(guid)
            cache[guid] = (
                ifcopenshell.util.element.get_container(element, ifc_class="IfcBuildingStorey")
                if element else None
            )
        return cache[guid]

    return get_storey


def _ordered_storeys_with(entries_by_storey, model):
    storeys_sorted = sorted(model.by_type("IfcBuildingStorey"), key=lambda s: s.Elevation)
    storey_index = {s.GlobalId: i for i, s in enumerate(storeys_sorted)}
    return sorted(entries_by_storey, key=lambda guid: storey_index[guid])


def _connected_chains(edges):
    """edges: iterable of (lower_id, upper_id) "directly supports" pairs.
    Merges any that share a member (via union-find) into one full vertical
    stack per component. Returns a list of id sets - only ids that appear in
    at least one edge are included, so a lone unmatched column/wall never
    shows up as a 1-member "stack"."""
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

    for lower_id, upper_id in edges:
        union(lower_id, upper_id)

    chains = defaultdict(set)
    for lower_id, upper_id in edges:
        root = find(lower_id)
        chains[root].add(lower_id)
        chains[root].add(upper_id)
    return list(chains.values())


def _roles_by_rank(ranks):
    """First (lowest-rank) member(s) get "base", last (highest-rank) get
    "top", everything between gets "intermediate" - grouped by rank rather
    than position so a rare tie (two members matched at the same storey)
    still gets a sensible role instead of an arbitrary one."""
    min_rank, max_rank = min(ranks), max(ranks)
    return ["base" if r == min_rank else "top" if r == max_rank else "intermediate" for r in ranks]


def _skipped_column_ids(columns, get_storey, tolerance_m):
    """GUIDs to leave out where several columns share a plan position on one
    storey: all of them at the origin, where the extraction leaves columns
    whose mapped offset it could not resolve (48 in aff2ec9a..., which chained
    into one 48-member "stack" over 6 storeys); all but the first by GUID
    elsewhere, where the model holds the same column twice (250 copies in
    4173e835...; measured on the local models, 2026-10-07). The same guard as
    alignment.skipped_column_ids, kept here per the package's per-detector
    convention (docs/detectors.md rule 7)."""
    by_position = defaultdict(list)
    for column in columns:
        storey = get_storey(column["id"])
        if storey is None:
            continue
        x, y = column["location"][0][0], column["location"][0][1]
        by_position[(storey.GlobalId, round(x / tolerance_m), round(y / tolerance_m))].append(column["id"])
    skipped = set()
    for (_storey, bx, by), guids in by_position.items():
        if len(guids) < 2:
            continue
        skipped.update(guids if (bx, by) == (0, 0) else sorted(guids)[1:])
    return skipped


def _detect_column_supports(model, columns, file_key, tolerance_m):
    get_storey = _get_storey_cache(model)
    skipped = _skipped_column_ids(columns, get_storey, tolerance_m)

    by_storey = defaultdict(list)
    info_by_id = {}
    for column in columns:
        storey = get_storey(column["id"])
        if storey is None or column["id"] in skipped:
            continue
        x, y = column["location"][0][0], column["location"][0][1]
        by_storey[storey.GlobalId].append((column["id"], x, y))
        info_by_id[column["id"]] = (storey, x, y)

    ordered = _ordered_storeys_with(by_storey, model)
    storey_rank = {guid: i for i, guid in enumerate(ordered)}

    edges = []
    for lower_guid, upper_guid in zip(ordered, ordered[1:]):
        for lower_id, lx, ly in by_storey[lower_guid]:
            for upper_id, ux, uy in by_storey[upper_guid]:
                if abs(lx - ux) <= tolerance_m and abs(ly - uy) <= tolerance_m:
                    edges.append((lower_id, upper_id))

    intents = []
    chains_info = []
    storey_names_by_rank = {storey_rank[g]: (model.by_guid(g).Name or g) for g in ordered}
    for chain_ids in _connected_chains(edges):
        # (storey rank, GUID): the GUID tie-break makes same-storey members - and
        # the intent id joined from them - independent of set-iteration order,
        # which for str ids follows Python's per-process hash seed (measured
        # 2026-09-19: same seed identical, different seed different ids).
        # The tie-break is the COLUMN's guid (`cid`), as in the wall stacks
        # below. Until 2026-09-22 it was the storey's guid, which is equal for
        # every same-storey member and therefore broke no tie at all: on
        # private-corpus model 0388, whose stacks branch to several columns per
        # storey, 32 of 40 structural ids changed between two identical runs.
        # No corpus stack has two members on one storey, so corpus ids are
        # unaffected (scripts/verify_units.py checks that).
        members_sorted = sorted(chain_ids, key=lambda cid: (storey_rank[info_by_id[cid][0].GlobalId], cid))
        ranks = [storey_rank[info_by_id[cid][0].GlobalId] for cid in members_sorted]
        storey_names = [info_by_id[cid][0].Name or info_by_id[cid][0].GlobalId for cid in members_sorted]
        anchor_x, anchor_y = info_by_id[members_sorted[0]][1], info_by_id[members_sorted[0]][2]
        related_guids = sorted({info_by_id[cid][0].GlobalId for cid in members_sorted},
                                key=lambda guid: storey_rank[guid])
        chains_info.append((members_sorted, ranks, storey_names))

        intents.append(make_intent(
            intent_id=f"{file_key}-colsupport-" + "-".join(members_sorted),
            intent_type="structural_column_support",
            label=(
                f"Column support stack: {storey_names[0]} → {storey_names[-1]} "
                f"({len(related_guids)} storeys)"
            ),
            members=[
                make_member(cid, role=role, ifc_class="IfcColumn")
                for cid, role in zip(members_sorted, _roles_by_rank(ranks))
            ],
            detector="structural",
            rule="column_vertical_continuity",
            summary=(
                f"{len(members_sorted)} IfcColumn instances share X,Y ≈ "
                f"({anchor_x:.3f}, {anchor_y:.3f}) continuously from {storey_names[0]} to "
                f"{storey_names[-1]} - a continuous vertical load path."
            ),
            related_guids=related_guids,
            metrics={
                "x": round(anchor_x, 3), "y": round(anchor_y, 3),
                "toleranceM": tolerance_m, "storeys": storey_names,
            },
        ))
    intents.extend(_discontinuity_intents(model, chains_info, storey_rank, storey_names_by_rank,
                                            file_key, "column", "IfcColumn"))
    return intents


def _wall_axis_key(wall, angle_tolerance_deg, position_tolerance_m):
    """(axis, fixed-coordinate bucket) for an axis-aligned wall, plus its span
    along its own length - None if the wall isn't (nearly) aligned with the X
    or Y axis."""
    angle = wall["orientation"] % 180
    p1, p2 = wall["location"]

    if angle <= angle_tolerance_deg or angle >= 180 - angle_tolerance_deg:
        axis, fixed, span = "H", p1[1], sorted((p1[0], p2[0]))
    elif abs(angle - 90) <= angle_tolerance_deg:
        axis, fixed, span = "V", p1[0], sorted((p1[1], p2[1]))
    else:
        return None, None

    return (axis, round(fixed / position_tolerance_m)), span


def _spans_overlap(span_a, span_b, min_overlap_m):
    overlap = min(span_a[1], span_b[1]) - max(span_a[0], span_b[0])
    return overlap >= min_overlap_m


def _detect_wall_supports(model, walls, file_key, angle_tolerance_deg, position_tolerance_m, min_overlap_m):
    get_storey = _get_storey_cache(model)

    by_storey = defaultdict(list)
    storey_by_id = {}
    axis_by_id = {}
    for wall in walls:
        storey = get_storey(wall["id"])
        if storey is None:
            continue
        by_storey[storey.GlobalId].append(wall)
        storey_by_id[wall["id"]] = storey

    ordered = _ordered_storeys_with(by_storey, model)
    storey_rank = {guid: i for i, guid in enumerate(ordered)}

    edges = []
    for lower_guid, upper_guid in zip(ordered, ordered[1:]):
        for lower_wall in by_storey[lower_guid]:
            lower_key, lower_span = _wall_axis_key(lower_wall, angle_tolerance_deg, position_tolerance_m)
            if lower_key is None:
                continue
            for upper_wall in by_storey[upper_guid]:
                upper_key, upper_span = _wall_axis_key(upper_wall, angle_tolerance_deg, position_tolerance_m)
                if upper_key != lower_key or not _spans_overlap(lower_span, upper_span, min_overlap_m):
                    continue
                axis_by_id[lower_wall["id"]] = lower_key[0]
                axis_by_id[upper_wall["id"]] = upper_key[0]
                edges.append((lower_wall["id"], upper_wall["id"]))

    intents = []
    chains_info = []
    storey_names_by_rank = {storey_rank[g]: (model.by_guid(g).Name or g) for g in ordered}
    for chain_ids in _connected_chains(edges):
        # Same GUID tie-break as the column stacks above - this is the site
        # where two runs produced different wallsupport ids on test_7.
        members_sorted = sorted(chain_ids, key=lambda wid: (storey_rank[storey_by_id[wid].GlobalId], wid))
        ranks = [storey_rank[storey_by_id[wid].GlobalId] for wid in members_sorted]
        storey_names = [storey_by_id[wid].Name or storey_by_id[wid].GlobalId for wid in members_sorted]
        related_guids = sorted({storey_by_id[wid].GlobalId for wid in members_sorted},
                                key=lambda guid: storey_rank[guid])
        axis = axis_by_id.get(members_sorted[0])
        chains_info.append((members_sorted, ranks, storey_names))

        intents.append(make_intent(
            intent_id=f"{file_key}-wallsupport-" + "-".join(members_sorted),
            intent_type="structural_wall_support",
            label=(
                f"Wall support stack: {storey_names[0]} → {storey_names[-1]} "
                f"({len(related_guids)} storeys)"
            ),
            members=[
                make_member(wid, role=role, ifc_class="IfcWall")
                for wid, role in zip(members_sorted, _roles_by_rank(ranks))
            ],
            detector="structural",
            rule="wall_vertical_continuity",
            summary=(
                f"{len(members_sorted)} load-bearing IfcWall instances share one axis line "
                f"continuously from {storey_names[0]} to {storey_names[-1]} "
                f"(overlap ≥ {min_overlap_m}m) - a continuous vertical load path."
            ),
            related_guids=related_guids,
            metrics={"axis": axis, "overlapMinM": min_overlap_m, "storeys": storey_names},
        ))
    intents.extend(_discontinuity_intents(model, chains_info, storey_rank, storey_names_by_rank,
                                            file_key, "wall", "IfcWall"))
    return intents


def _discontinuity_intents(model, chains_with_info, storey_rank, storey_names_by_rank,
                            file_key, kind, ifc_class):
    """Negative-polarity companions to the stacks above, ONE PER STOREY
    TRANSITION (docs/detectors.md rule 12; rolled up 2026-10-09:
    384 per-stack companions on the local shards listed their stacks'
    members again and read as 384 more rows for one fact per storey).

    For every stack, two things are checked against the storeys that carry
    this element type at all (`storey_rank` - a storey with no such element
    is skipped, not counted as a break, exactly as the positive detection
    does):

    - **unsupported base**: the stack's lowest member sits above the lowest
      such storey - the load path stops going down, i.e. something else must
      carry it (a transfer beam, a wall, or a modelling gap).
      `structural_unsupported_base`: one record per storey where stacks
      start unsupported, members = each stack's base element(s), role "base".
    - **early termination**: the stack's top is below the topmost such storey
      - storeys above continue without a matching member.
      `structural_stack_termination`: one record per storey where stacks end,
      members = each stack's top element(s), role "top". Common and often
      intended (fewer columns higher up), which is why it is a separate,
      lower-priority type rather than folded into the base case.

    Both are statements about geometry, not verdicts: a human decides which
    are design intent (a setback, a transfer structure) and which are gaps.
    Each record names its stacks' positive records (`metrics.stackIds`, in
    the same order as `metrics.membersPerStack`, each stack's full length),
    so the per-stack claim is one Refer away and never restated; the members
    themselves are sorted by GUID across stacks.
    `chains_with_info`: [(members_sorted, ranks, storey_names)] as computed
    for the positive records - nothing is re-derived. Ids are built from the
    boundary storey's GUID and members are sorted by GUID, so the records do
    not depend on the order the chains arrive in (docs/detectors.md rule 1)."""
    if not storey_rank:
        return []
    min_rank, max_rank = min(storey_rank.values()), max(storey_rank.values())
    guid_by_rank = {rank: guid for guid, rank in storey_rank.items()}
    positive_infix = {"column": "colsupport", "wall": "wallsupport"}[kind]
    groups = {"nobase": defaultdict(list), "stop": defaultdict(list)}
    for chain in chains_with_info:
        _members, ranks, _names = chain
        if min(ranks) > min_rank:
            groups["nobase"][min(ranks)].append(chain)
        if max(ranks) < max_rank:
            groups["stop"][max(ranks)].append(chain)

    def plural(n, noun):
        return f"{n} {noun}{'s' if n != 1 else ''}"

    def ends_of(chains, pick):
        """The member(s) of each stack at the rank `pick` selects, sorted by GUID."""
        return sorted(mid for members_sorted, ranks, _ in chains
                      for mid, rank in zip(members_sorted, ranks) if rank == pick(ranks))

    intents = []
    for boundary, chains in sorted(groups["nobase"].items()):
        chains = sorted(chains, key=lambda c: c[0])
        storey_guid, storey_name = guid_by_rank[boundary], storey_names_by_rank[boundary]
        below = [storey_names_by_rank[r] for r in range(min_rank, boundary)]
        n = len(chains)
        intents.append(make_intent(
            intent_id=f"{file_key}-{kind}nobase-{storey_guid}",
            intent_type="structural_unsupported_base",
            label=(f"{plural(n, f'{kind} stack')} {'have' if n != 1 else 'has'} no support below "
                   f"{storey_name} ({plural(len(below), 'storey')} beneath)"),
            members=[make_member(mid, role="base", ifc_class=ifc_class) for mid in ends_of(chains, min)],
            detector="structural",
            rule=f"{kind}_unsupported_base",
            summary=(
                f"{plural(n, f'{ifc_class} stack')} start{'' if n != 1 else 's'} at {storey_name} with no matching "
                f"{ifc_class} on {', '.join(below)} below - the vertical load path stops there and something else "
                f"must carry it (transfer structure, wall, or a modelling gap). A Refer draws the stacks themselves."
            ),
            related_guids=[storey_guid],
            metrics={"storey": storey_name, "stackCount": n, "stopsAboveStoreys": below,
                     "stackIds": [f"{file_key}-{positive_infix}-" + "-".join(c[0]) for c in chains],
                     "membersPerStack": [len(c[0]) for c in chains]},
            polarity="negative",
        ))
    for boundary, chains in sorted(groups["stop"].items()):
        chains = sorted(chains, key=lambda c: c[0])
        storey_guid, storey_name = guid_by_rank[boundary], storey_names_by_rank[boundary]
        above = [storey_names_by_rank[r] for r in range(boundary + 1, max_rank + 1)]
        n = len(chains)
        intents.append(make_intent(
            intent_id=f"{file_key}-{kind}stop-{storey_guid}",
            intent_type="structural_stack_termination",
            label=(f"{plural(n, f'{kind} stack')} end{'' if n != 1 else 's'} at {storey_name} "
                   f"({plural(len(above), 'storey')} above)"),
            members=[make_member(mid, role="top", ifc_class=ifc_class) for mid in ends_of(chains, max)],
            detector="structural",
            rule=f"{kind}_stack_termination",
            summary=(
                f"{plural(n, f'{ifc_class} stack')} end{'' if n != 1 else 's'} at {storey_name} with no matching "
                f"{ifc_class} on {', '.join(above)} above. A Refer draws the stacks themselves."
            ),
            related_guids=[storey_guid],
            metrics={"storey": storey_name, "stackCount": n, "continuesWithoutMatchOn": above,
                     "stackIds": [f"{file_key}-{positive_infix}-" + "-".join(c[0]) for c in chains],
                     "membersPerStack": [len(c[0]) for c in chains]},
            polarity="negative",
        ))
    return intents


def detect(model, extracted, file_key,
           column_tolerance_m=DEFAULT_COLUMN_TOLERANCE_M,
           wall_angle_tolerance_deg=DEFAULT_WALL_ANGLE_TOLERANCE_DEG,
           wall_position_tolerance_m=DEFAULT_WALL_POSITION_TOLERANCE_M,
           wall_min_overlap_m=DEFAULT_WALL_MIN_OVERLAP_M):
    extracted = extracted or {}
    columns = extracted.get("info_st_columns", [])
    walls = extracted.get("info_st_walls", [])

    intents = []
    if columns:
        intents.extend(_detect_column_supports(model, columns, file_key, column_tolerance_m))
    if walls:
        intents.extend(_detect_wall_supports(
            model, walls, file_key, wall_angle_tolerance_deg, wall_position_tolerance_m, wall_min_overlap_m))
    return intents
