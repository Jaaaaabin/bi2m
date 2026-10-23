"""Ratio of two aggregates per container vs threshold: the plan's AGG rules
(K141: office area per workstation; K113: total area per workstation;
K119: toilet area per workstation, mean tea-kitchen area).

Binding keys (rule-level, each overridable per check):
    per:          building | storey | dwelling   (the container the terms are summed in; a
                  storey is the element's storey or, for a room the export left without one,
                  its pseudo-level by body z, facts.level_of, 2026-10-20)
    numerator,
    denominator:  {select: <selector>, measure: <name>}  the SUM of a measure over the
                                                         selected population, or
                  {count: <selector>}                    the COUNT of the population
    checks:       [{param, numerator?, denominator?}]

Per container: no numerator element -> no record (not applicable there);
a None measure inside a sum -> the container is nodata, listing the
elements whose measure is missing (the plan's rule: never sum partial
data silently); a zero denominator -> nodata on the numerator elements;
else value = numerator / denominator, one outcome for the container,
carried by every numerator element so the rollup keeps the container
whole. `aggregate` in the metrics gives each container's terms. A
`widened` rule reports fail/warn as info.
"""

from collections import defaultdict

from .. import compare, facts
from ..measures import measure
from ..records import nodata_record, outcome_records
from ..rules import DOWNGRADED, status_kind
from ..select import population

PER = ("building", "storey", "dwelling")


def _container_of(ctx, per, units_of):
    if per == "building":
        return lambda element: "building"
    if per == "dwelling":
        return lambda element: units_of.get(element.GlobalId)
    return lambda element: facts.level_of(ctx, element)  # the storey, or the pseudo-level of a floor the export left out


def _term(ctx, spec, derived, container_of, missing):
    """{container: (total, [elements])}: sums (or counts) per container;
    a container with a missing measure is dropped and its elements are
    recorded in `missing`."""
    if "count" in spec:
        elements, _unknown = population(ctx, spec["count"])
        name = None
    else:
        elements, _unknown = population(ctx, spec["select"])
        name = spec["measure"]
    totals, members, broken = defaultdict(float), defaultdict(list), set()
    for element in elements:
        key = container_of(element)
        if key is None:
            continue
        if name is None:
            value = 1.0
        else:
            value, _source = measure(ctx, element, name, derived)
            if value is None:
                missing.setdefault(element.GlobalId, (element, []))[1].append(name)
                broken.add(key)
                continue
        totals[key] += value
        members[key].append(element)
    return {key: (totals[key], members[key]) for key in totals if key not in broken}


def _label(spec):
    return f"count({spec['count'].get('use') or spec['count'].get('class')})" if "count" in spec else f"sum({spec['measure']})"


def run(ctx, file_key, category_id, rule):
    per = rule.get("per") or "building"
    if per not in PER:
        raise compare.Unsupported(f"aggregate per {per!r}")
    units_of = {}
    if per == "dwelling":
        for unit in ctx.fact("dwelling_units", facts.dwelling_units):
            for guid in unit["rooms"]:
                units_of[guid] = unit["key"]
        if not units_of:
            return []
    container_of = _container_of(ctx, per, units_of)
    downgraded = status_kind(rule["status"]) in DOWNGRADED
    derived = rule["derived"]
    records, missing = [], {}
    for check in rule["checks"]:
        param = rule["params"][check["param"]]
        num_spec = check.get("numerator") or rule["numerator"]
        den_spec = check.get("denominator") or rule["denominator"]
        numerators = _term(ctx, num_spec, derived, container_of, missing)
        denominators = _term(ctx, den_spec, derived, container_of, missing)
        source = f"{_label(num_spec)} / {_label(den_spec)}"
        results, terms = [], {}
        for key, (total, elements) in sorted(numerators.items()):
            if not elements:
                continue
            den = denominators.get(key)
            if den is None or den[0] == 0:
                for element in elements:
                    missing.setdefault(element.GlobalId, (element, []))[1].append(f"{_label(den_spec)} is zero or unknown")
                continue
            value = total / den[0]
            outcome = compare.outcome(value, param, negate=bool(check.get("negate")))
            if downgraded and outcome in ("fail", "warn"):
                outcome = "info"
            if outcome is None:
                continue
            terms[key] = {"numerator": round(total, 4), "denominator": round(den[0], 4), "value": round(value, 4)}
            for element in elements:
                results.append((element, value, source, outcome))
        scope_rule = dict(rule, scope="building" if per == "building" else "storey")
        for record in outcome_records(ctx, file_key, category_id, scope_rule, check, results):
            member_guids = {m["guid"] for m in record["members"]}
            keys = sorted(key for key, (_t, elements) in numerators.items() if key in terms and member_guids & {e.GlobalId for e in elements})
            record["evidence"]["metrics"]["aggregate"] = {key: terms[key] for key in keys}
            record["evidence"]["summary"] += (
                f" Value = {_label(num_spec)} / {_label(den_spec)} per {per}"
                + (", dwellings inferred from the door graph (facts.dwelling_units)" if per == "dwelling" else "")
                + "; the ratio is carried by every element summed in the numerator.")
            records.append(record)
    nodata = nodata_record(ctx, file_key, category_id, rule, missing)
    if nodata is not None:
        records.append(nodata)
    return records
