"""Shared "recognized intent group" record shape.

Every detector in `detectors/` returns a list of these dicts - the exact
shape `viewer/res/intent_groups.json` already ships
(originally as a hand-authored mock) and `ThatOpenCompanyLoader.js`/
`createIntentPanel` already consume. A real detector's output is therefore
a drop-in replacement for the mock: no frontend change needed as long as a
detector builds its records through `make_intent` below.
"""

from datetime import datetime, timezone


# Records with more members than this carry metrics.memberCount.
MEMBER_COUNT_NOTE = 200


def make_member(guid, role="member", ifc_class=None):
    """`ifc_class` (e.g. "IfcColumn", "IfcWall") should come from whatever the
    detector already knows/checked to build this member - every current
    detector already has it in hand at this point (it's how they filtered
    which elements qualify), so this never needs a fresh model lookup."""
    return {"guid": guid, "role": role, "ifcClass": ifc_class}


POLARITIES = ("positive", "negative")


def make_intent(intent_id, intent_type, label, members, detector, summary,
                  rule=None, confidence=None, related_guids=None, metrics=None,
                  polarity="positive"):
    """`detector` is the owning category's id (registry.py) - it's what
    verdicts.js/the future category filter key off, via provenance.detector.
    `confidence` is left `None` by a purely deterministic rule (exact match
    within a stated tolerance has no meaningful uncertainty to report) -
    only a probabilistic/LLM-labeled detector should ever set it.

    `polarity` says whether the record asserts that something IS there
    ("positive" - a column stack, a daylit room group) or reports an absence,
    violation or anomaly ("negative" - rooms with no egress path, the one
    door of 111 at a different height). The two are
    also called generative vs. prohibitive; the pipeline was
    100% positive until the first negative records landed, and this field is
    what lets a review queue rank them first instead of substring-matching
    five `type` names. Records written before this field existed have no
    key: readers must treat absent as "positive", which is also why the
    default is explicit here rather than None.

    One field is NOT set here: `index` ("<category>-<NNN>") is stamped by
    writers.write_intent_shard over the merged shard, because its numbering
    is per category per model and has to include records kept from earlier
    runs. It is a display handle and shifts when the set changes; `id` is
    the durable key, and any cross-reference between intents (the planned
    `corroborates` field) must use `id`.
    """
    if polarity not in POLARITIES:
        raise ValueError(f"polarity must be one of {POLARITIES}, got {polarity!r}")
    # A big record says how big it is (2026-10-09): members stay complete -
    # scopes are compressed by rollup, never by truncation - and the
    # count lets a reader see the size without the list.
    metrics = dict(metrics or {})
    if len(members) > MEMBER_COUNT_NOTE:
        metrics["memberCount"] = len(members)
    return {
        "id": intent_id,
        "type": intent_type,
        "polarity": polarity,
        "label": label,
        "members": members,
        "evidence": {
            "summary": summary,
            "relatedGuids": related_guids or [],
            "metrics": metrics,
        },
        "provenance": {
            "detector": detector,
            "rule": rule,
            "confidence": confidence,
            "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
    }
