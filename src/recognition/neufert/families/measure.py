"""Per-item measure vs threshold: the plan's families 1 (element) and 2
(space). Select a population, read one named measure per element, compare
it with one param, roll the outcomes up per storey (records.py).

Binding keys read here: `select` (rule population), `derived`, and per
check: `measure`, `param`, optional `select` (its own population), `when`
({measure, param}: a gate param that must be satisfied first, e.g. K63's
S_FLAT), `negate` (the violation is the threshold being met, e.g. K24's
banned operation types). A `widened` rule reports fail/warn as info.

An element whose measure (or gate measure) is None goes to the rule's
nodata record, and so does an element the rule's selector could not gate
(a door with no IsExternal anywhere, 2026-10-20: silence is not an
answer). A `when` gate on a `split` param (K15's DROP_HI) takes `side`:
"above" (default) keeps the elements at or above the split value,
"below" the others. An op the comparator does not implement (compare.Unsupported)
raises: the rule should have been deferred, and a loud failure of the Topic
category is better than a silent gap (the CLI keeps previous records).
"""

from .. import compare
from ..measures import measure
from ..records import nodata_record, outcome_records
from ..rules import DOWNGRADED, status_kind
from ..select import population


def _gate_open(value, gate, param):
    if param.get("op") == "split":
        return (value >= float(param["value"])) == (gate.get("side", "above") == "above")
    return compare.satisfied(value, param)


def _gate_names(spec):
    specs = spec if isinstance(spec, list) else [spec]
    names = []
    for part in specs:
        names += [f"prop:{name} (gate)" for name in (part.get("prop") or {})]
        names += [f"{condition['measure']} (gate)" for condition in (part.get("where") or [])]
    return names or ["select gate"]


def run(ctx, file_key, category_id, rule):
    base, base_unknown = population(ctx, rule["select"]) if rule["select"] else ([], [])
    derived = rule["derived"]
    widened = status_kind(rule["status"]) in DOWNGRADED
    records = []
    missing = {}
    for element in base_unknown:
        missing.setdefault(element.GlobalId, (element, []))[1].extend(_gate_names(rule["select"]))
    for check in rule["checks"]:
        elements = population(ctx, check["select"])[0] if check.get("select") else base
        param = rule["params"][check["param"]]
        gate = check.get("when")
        results = []
        for element in elements:
            if gate:
                gate_value, _ = measure(ctx, element, gate["measure"], derived)
                if gate_value is None:
                    missing.setdefault(element.GlobalId, (element, []))[1].append(gate["measure"])
                    continue
                if not _gate_open(gate_value, gate, rule["params"][gate["param"]]):
                    continue
            value, source = measure(ctx, element, check["measure"], derived)
            if value is None:
                missing.setdefault(element.GlobalId, (element, []))[1].append(check["measure"])
                continue
            outcome = compare.outcome(value, param, negate=bool(check.get("negate")))
            if widened and outcome in ("fail", "warn"):
                outcome = "info"
            if outcome is None:
                continue
            results.append((element, value, source, outcome))
        records.extend(outcome_records(ctx, file_key, category_id, rule, check, results))
    nodata = nodata_record(ctx, file_key, category_id, rule, missing)
    if nodata is not None:
        records.append(nodata)
    return records
