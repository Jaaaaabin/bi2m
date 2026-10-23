"""Shared runner for the merged categories (2026-10-08): room_access,
egress_fire, window_patterns, repeated_units.

A merged category is a list of part modules, each the rule it always was.
Its detect() calls every part's detect() in the declared order, hands the
shared door graph to the parts whose signature takes `graph=` (the test
scripts/recognize_intents.py makes), and writes the merged category's id
into provenance.detector. Nothing else on a record changes: ids, types,
rules, metrics and members are the parts' own, so review decisions keyed
on record ids survive the merge, and views/intentLines.js, which keys on
type ids, needs no change.

A part's exception propagates: the merged category then fails as one, and
the CLI keeps its previous records (scripts/recognize_intents.py's rule for
a failed category). Catching per part would silently drop the failed rule's
previous records on that write.
"""

import inspect


def run_parts(category_id, parts, model, extracted, file_key, graph=None):
    records = []
    for part in parts:
        kwargs = {"graph": graph} if "graph" in inspect.signature(part.detect).parameters else {}
        found = part.detect(model, extracted, file_key, **kwargs)
        for record in found:
            record["provenance"]["detector"] = category_id
        records.extend(found)
    return records
