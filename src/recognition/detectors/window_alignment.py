"""Vertical window-bay alignment: an IfcWindow whose (x, y) placement
recurs directly above another one, storey after storey - the same repeated
facade-bay convention alignment.py recognizes for columns on one storey,
here applied across storeys instead (the "daylight" domain's first
category - see registry.py's docstring for the taxonomy this opens up).

Chaining mechanism is a direct reapplication of structural.py's own column-
support logic (storey-adjacent (x, y) tolerance match, then
`connected_components` merges edges sharing a member via union-find into
one full run per bay, spanning however many storeys that bay actually
continues through). Since 2026-10-09 that skeleton comes from
recognition/chains.py, components.py and storeys.py rather than a local
copy; structural.py keeps its own.

Self-contained: unlike structural.py's columns/walls, IfcWindow needs no
extraction pipeline at all - `ObjectPlacement` alone is enough. Confirmed
directly across every real file with windows (data/test_1.ifc: 139,
data/test_5.ifc: 126, data/test_2.ifc: 139): zero degenerate (0, 0)
placements, zero missing IfcBuildingStorey container, zero missing
OverallWidth/OverallHeight - none of the placement-chain quirks documented
elsewhere in this package (IfcDoor/IfcStairFlight/IfcRoof) show up for
IfcWindow in any file checked so far, so there is no fallback path here the
way there is in circulation.py/envelope.py.

Verified against data/test_1.ifc: 139 windows -> N vertical bays recovered
(see this module's own test run - re-derive with
`uv run python scripts/recognize_intents.py --files test_1 --categories window_alignment`
since exact counts depend on the tolerance chosen at the time this was
written, DEFAULT_POSITION_TOLERANCE_M).
"""

from collections import defaultdict

import ifcopenshell.util.element

from ifc_units import length_scale, placement_xy

from ..chains import adjacent_storey_edges, roles_by_rank
from ..components import connected_components
from ..intent import make_member, make_intent
from ..storeys import ordered_storeys_with

DEFAULT_POSITION_TOLERANCE_M = 0.05
DEFAULT_MIN_STOREYS = 2


def _interruption_intents(chains, info_by_id, ordered, storey_rank, file_key, position_tolerance_m):
    """Negative-polarity companion (docs/detectors.md rule 12): a facade bay that is
    interrupted - windows at (nearly) the same (x, y) on storeys below AND
    above a storey that has no window there. The positive detector sees two
    separate chains (or a chain and a lone window) and says nothing about the
    hole between them; this names it. Every window - chained or lone - is
    bucketed by (x, y) at the same tolerance the chaining uses; within a
    bucket, storey-adjacent gaps of one or more storeys (that DO carry
    windows elsewhere, per `ordered`) become one `window_bay_interrupted`
    record whose members are the window just below and just above the gap.
    Deterministic: buckets and members are ordered by (storey rank, GUID)."""
    buckets = defaultdict(list)
    for guid, (storey, x, y) in info_by_id.items():
        key = (round(x / position_tolerance_m), round(y / position_tolerance_m))
        buckets[key].append((storey_rank[storey.GlobalId], guid))
    # Chains can straddle two rounding buckets (tolerance match across a
    # bucket boundary); merge each chain's members into one bucket so a chain
    # is never split against itself.
    for chain_ids in chains:
        keys = {(round(info_by_id[c][1] / position_tolerance_m), round(info_by_id[c][2] / position_tolerance_m)) for c in chain_ids}
        if len(keys) > 1:
            target = min(keys)
            for k in keys - {target}:
                buckets[target].extend(buckets.pop(k, []))
    name_of_rank = {storey_rank[g]: g for g in ordered}
    intents = []
    for key in sorted(buckets):
        entries = sorted(set(buckets[key]))
        present = sorted({r for r, _ in entries})
        for lower_rank, upper_rank in zip(present, present[1:]):
            if upper_rank - lower_rank < 2:
                continue
            gap_ranks = list(range(lower_rank + 1, upper_rank))
            below = [g for r, g in entries if r == lower_rank]
            above = [g for r, g in entries if r == upper_rank]
            lower_storey = info_by_id[below[0]][0]
            upper_storey = info_by_id[above[0]][0]
            gap_names = []
            for r in gap_ranks:
                guid = name_of_rank[r]
                any_window = next((info_by_id[c][0] for c in info_by_id if info_by_id[c][0].GlobalId == guid), None)
                gap_names.append((any_window.Name if any_window is not None and any_window.Name else guid))
            x, y = info_by_id[below[0]][1], info_by_id[below[0]][2]
            intents.append(make_intent(
                intent_id=f"{file_key}-windowgap-" + "-".join(below + above),
                intent_type="window_bay_interrupted",
                label=f"Window bay interrupted on {', '.join(gap_names)} (X,Y ≈ {x:.2f}, {y:.2f})",
                members=[make_member(g, role="base", ifc_class="IfcWindow") for g in below]
                        + [make_member(g, role="top", ifc_class="IfcWindow") for g in above],
                detector="window_alignment",
                rule="window_bay_interruption",
                summary=(
                    f"Windows at X,Y ≈ ({x:.3f}, {y:.3f}) exist on {lower_storey.Name or lower_storey.GlobalId} and "
                    f"{upper_storey.Name or upper_storey.GlobalId} but not on {', '.join(gap_names)} in between - "
                    f"the facade bay is interrupted there."
                ),
                related_guids=[lower_storey.GlobalId] + [name_of_rank[r] for r in gap_ranks] + [upper_storey.GlobalId],
                metrics={"x": round(x, 3), "y": round(y, 3), "gapStoreys": gap_names, "toleranceM": position_tolerance_m},
                polarity="negative",
            ))
    return intents


def detect(model, extracted, file_key,
           position_tolerance_m=DEFAULT_POSITION_TOLERANCE_M, min_storeys=DEFAULT_MIN_STOREYS):
    windows = model.by_type("IfcWindow")
    if not windows:
        return []

    # Placements in metres whatever the file's unit (docs/detectors.md rule 13);
    # a window without a placement is skipped, not put at the origin.
    scale = length_scale(model)
    by_storey = defaultdict(list)
    info_by_id = {}
    for window in windows:
        storey = ifcopenshell.util.element.get_container(window, ifc_class="IfcBuildingStorey")
        if storey is None:
            continue
        xy = placement_xy(window, scale)
        if xy is None:
            continue
        x, y = xy
        by_storey[storey.GlobalId].append((window.GlobalId, x, y))
        info_by_id[window.GlobalId] = (storey, x, y)

    ordered = ordered_storeys_with(by_storey, model)
    storey_rank = {guid: i for i, guid in enumerate(ordered)}

    edges = adjacent_storey_edges(ordered, by_storey, position_tolerance_m)

    chains = connected_components(edges)
    intents = _interruption_intents(chains, info_by_id, ordered, storey_rank, file_key, position_tolerance_m)
    for chain_ids in chains:
        distinct_storeys = {info_by_id[cid][0].GlobalId for cid in chain_ids}
        if len(distinct_storeys) < min_storeys:
            continue

        # (storey rank, GUID) - GUID tie-break for same-storey windows, so the
        # joined intent id does not follow set-iteration (hash-seed) order.
        members_sorted = sorted(chain_ids, key=lambda cid: (storey_rank[info_by_id[cid][0].GlobalId], cid))
        ranks = [storey_rank[info_by_id[cid][0].GlobalId] for cid in members_sorted]
        storey_names = [info_by_id[cid][0].Name or info_by_id[cid][0].GlobalId for cid in members_sorted]
        anchor_x, anchor_y = info_by_id[members_sorted[0]][1], info_by_id[members_sorted[0]][2]
        related_guids = sorted({info_by_id[cid][0].GlobalId for cid in members_sorted},
                                key=lambda guid: storey_rank[guid])

        intents.append(make_intent(
            intent_id=f"{file_key}-windowalign-" + "-".join(members_sorted),
            intent_type="window_vertical_alignment",
            label=(
                f"Window bay: {storey_names[0]} → {storey_names[-1]} "
                f"({len(related_guids)} storeys)"
            ),
            members=[
                make_member(cid, role=role, ifc_class="IfcWindow")
                for cid, role in zip(members_sorted, roles_by_rank(ranks))
            ],
            detector="window_alignment",
            rule="window_vertical_continuity",
            summary=(
                f"{len(members_sorted)} IfcWindow instances share X,Y ≈ "
                f"({anchor_x:.3f}, {anchor_y:.3f}) continuously from {storey_names[0]} to "
                f"{storey_names[-1]} - a repeated facade bay."
            ),
            related_guids=related_guids,
            metrics={
                "x": round(anchor_x, 3), "y": round(anchor_y, 3),
                "toleranceM": position_tolerance_m, "storeys": storey_names,
            },
        ))
    return intents
