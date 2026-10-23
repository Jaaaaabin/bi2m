"""The detector of a retired registry entry: it returns nothing.

A category whose rules moved into another category keeps its registry entry
in place as a tombstone, because a category's colour is its position in the
manifest (docs/detectors.md rule 5), so entries are never removed. The entry has no
types, no inputs and no signals, names its successor in `retired`, and uses
this detector. Recomputing it, or its successor, clears the category's old
records from a shard: writers.write_intent_shard drops a recomputed
category's prior records, and recognize_intents.py counts every tombstone
whose successor completed as recomputed (writers.recomputed_with_tombstones),
so a run that names live categories only, as the viewer's Run does, retires
them too. The panel's Compute list hides tombstones.

Tombstoned 2026-10-08: the ten categories folded into room_access,
egress_fire, window_patterns and repeated_units (grid_claims, retired
2026-10-07, keeps its own documented stub).
"""


def detect(model, extracted, file_key, **_):
    return []
