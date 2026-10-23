"""Retired 2026-10-07: row claims are made by alignment.py now.

This was the "Column Alignment Continuity" category (until 2026-10-06 "Grid
Line Consistency"): one record per column row across the building, re-derived
from `alignment`'s per-storey rows - positive (`grid_line_consistency`) when
the row is on every column-bearing storey, negative (`grid_line_gap`) when it
is missing on some (docs/detectors.md rule 12). Measured on the 22 local
shards: 748 of alignment's 921 row records were restated by these 185
claims, so a reviewer judged the same columns twice.
alignment.py now writes the claims itself, under the same type ids, rules and
record ids, and keeps a per-storey row only when no other storey has it (its
module docstring has the numbers).

The registry entry stays, at its place, as a tombstone: the panel's category
colours follow the manifest order (docs/detectors.md rule 5), so removing it would
recolour every category appended after it. Running it returns nothing, which
also clears this category's old records from a shard when it is recomputed
(writers.write_intent_shard drops a recomputed category's prior records).
"""


def detect(model, extracted, file_key, **_):
    return []
