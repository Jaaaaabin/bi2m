"""Cross-references between intents that prove the same fact independently
(docs/architecture.md "Recognition", step 5).

Several categories cover one fact from different sides - `test_3`'s four
exterior doors are `egress_access` access points AND `convention_outlier`
exceptions; `thermal_envelope` and `convention_outlier` both key off
`IsExternal`. Until now that agreement was invisible: a reviewer met the same
elements twice without being told why. This module stamps each intent with
a `corroborates` list naming the OTHER-detector intents whose element set
substantially coincides with its own, so the panel can show "also found by
Convention Outliers" and a reviewer can judge the pair together.

What counts as corroboration - measured, not guessed. Two intents from
DIFFERENT detectors whose member GUID sets (plus `evidence.relatedGuids`)
satisfy either

    jaccard(A, B) >= JACCARD_MIN      (0.5 - they are mostly the same set), or
    |A ∩ B| / min(|A|, |B|) >= CONTAINMENT_MIN   (0.8 - one is mostly inside the other)
        AND min(|A|, |B|) / max(|A|, |B|) >= SIZE_RATIO_MIN   (0.5 - and comparable in size)

with at least MIN_SHARED elements in common. Same-detector pairs are
skipped: two `alignment` groups sharing a column is a grid intersection, not
corroboration. So are pairs a registry entry declares as `derived_from` the
other (grid_claims is computed FROM alignment's groups - agreement between
them is construction, not evidence).

Measured 2026-09-21 on the regenerated corpus (1974 records): containment
alone produced 991 pairs, 644 of them `structural` stacks (4 columns) sitting
inside `grid_claims` lines (40 columns) - one set trivially contained in a
much larger one is not "the same fact". The size-ratio clause cuts that to
41 pairs, every one of which reads as genuine cross-validation:
lighting_clusters <-> window_alignment (16), egress_reachability <->
space_access (7), convention_outlier <-> egress_access (4 - the motivating
example: test_3's four exterior doors), fire_compartments <-> space_access
(4), curtainwall_assembly <-> thermal_envelope (3), ... Plain Jaccard alone
gave 38; the three it missed are egress/space_access pairs where one record
adds a couple of doors the other lacks. The trivial `alignment` x
`structural` overlap (one shared column, Jaccard ~1/6) is rejected either
way.

Keys on `id`, never on `index` (docs/detectors.md rule 9): the list survives a
re-run exactly as long as the referenced intents do. Recomputed on every
shard write over the MERGED list (kept + new), so a category recomputed
alone still cross-references against the categories that were kept.

Storey GUIDs are excluded from the comparison: nearly every intent lists
its storey in `relatedGuids`, and two unrelated intents on the same floor
would otherwise "share" an element.
"""

JACCARD_MIN = 0.5
CONTAINMENT_MIN = 0.8
SIZE_RATIO_MIN = 0.5
MIN_SHARED = 1


def _element_guids(intent, storey_guids):
    guids = {m["guid"] for m in intent.get("members", []) if m.get("guid")}
    guids.update(g for g in intent.get("evidence", {}).get("relatedGuids", []) if g)
    return guids - storey_guids


def annotate_corroboration(intents, storey_guids=frozenset(), excluded_pairs=frozenset()):
    """Adds/refreshes `corroborates` on every record in place. Each entry:
    {"id", "detector", "sharedGuids", "jaccard"} - sorted by jaccard desc then
    id, so the order is deterministic. Records with no partner get an empty
    list (explicit, so a reader can distinguish "none" from "not computed").
    `excluded_pairs`: frozensets of two detector ids never to pair (derived
    categories). Returns the number of corroborating pairs found."""
    sets = [_element_guids(p, storey_guids) for p in intents]
    for p in intents:
        p["corroborates"] = []

    pairs = 0
    for i in range(len(intents)):
        a = sets[i]
        if not a:
            continue
        det_a = intents[i]["provenance"]["detector"]
        for j in range(i + 1, len(intents)):
            det_b = intents[j]["provenance"]["detector"]
            if det_b == det_a or frozenset((det_a, det_b)) in excluded_pairs:
                continue
            b = sets[j]
            if not b:
                continue
            shared = len(a & b)
            if shared < MIN_SHARED:
                continue
            jaccard = shared / len(a | b)
            containment = shared / min(len(a), len(b))
            size_ratio = min(len(a), len(b)) / max(len(a), len(b))
            if jaccard < JACCARD_MIN and not (containment >= CONTAINMENT_MIN and size_ratio >= SIZE_RATIO_MIN):
                continue
            pairs += 1
            entry_ab = {"id": intents[j]["id"], "detector": intents[j]["provenance"]["detector"],
                        "sharedGuids": shared, "jaccard": round(jaccard, 3)}
            entry_ba = {"id": intents[i]["id"], "detector": det_a,
                        "sharedGuids": shared, "jaccard": round(jaccard, 3)}
            intents[i]["corroborates"].append(entry_ab)
            intents[j]["corroborates"].append(entry_ba)

    for p in intents:
        p["corroborates"].sort(key=lambda e: (-e["jaccard"], e["id"]))
    return pairs
