"""Outcome rollup -> make_intent records.

One record per rule, param, outcome and scope container: the storey (rule
scope "storey") or the building ("building"), under ONE rollup policy
chosen per outcome class, never per rule: an `info`
outcome is always one model-level record with its per-storey
distribution; a pass/fail/warn outcome that at least ROLLUP_SHARE of the
model's judged items share is one model-level record (K23's 46 models
failing on more than half their doors are a door library, not decisions;
a pass the corpus never contradicts is one line, not one per storey); the
rest stay per storey. A model-level record keys on "building" and lists
its storeys in relatedGuids and `byStorey`.

Every length value that is a whole number of feet (0.3048 m) is counted
in `imperialDefault`: 2.4384 m rooms and 1.2192 m railings were every hard
fail of K112 and the median railing on the corpus, template defaults a
reviewer must be able to tell from decisions. The general form of that
(2026-10-19, after K19's treads at exactly 0.20 m on every
flight of 81 models): `templateValue` on every record of a check whose
judged items in the model carry one identical value (to TEMPLATE_TOLERANCE)
on at least ROLLUP_SHARE of TEMPLATE_MIN_ITEMS or more items, with the
value, its share and the count. It explains a rollup; it changes no
outcome. Id
`{file_key}-{kid}-{param slug}-{outcome}-{storey GUID | building}`, members
the elements GUID-sorted (docs/detectors.md rule 1), the storey in
relatedGuids,
`rule` = the KID, polarity negative for fail, warn and nodata, positive for
pass and info. The record type is `<category>_<outcome>`.

Missing data: one `nodata` record per rule and model, listing every element
of the population whose measure chain ended in None and the measures tried.
Never a failure (the plan's hard rule).
"""

import re
import statistics
from collections import Counter, defaultdict

from ..intent import make_intent, make_member
from .rules import status_kind, status_note

NEGATIVE = ("fail", "warn", "nodata")
# Share of a model's judged items (one check) that makes an outcome model-level.
ROLLUP_SHARE = 0.9
FOOT_M = 0.3048
FOOT_TOLERANCE_M = 0.001
TEMPLATE_TOLERANCE = 0.001
TEMPLATE_MIN_ITEMS = 5
LENGTH_UNITS = ("m",)


def slug(text):
    return re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")


def _container(ctx, rule, element):
    if rule["scope"] == "building":
        return "building", None
    # A container stand-in (provision.py's zero-count storey) carries its storey itself.
    storey = element.storey if getattr(element, "placeholder", False) else ctx.storey_of(element)
    return (storey.GlobalId, storey) if storey is not None else ("nostorey", None)


def _whole_feet(value):
    feet = value / FOOT_M
    return abs(feet - round(feet)) * FOOT_M <= FOOT_TOLERANCE_M and round(feet) >= 1


def _model_level(outcome, share):
    return outcome == "info" or share >= ROLLUP_SHARE


def _template_value(values):
    """(value, share, count) of the one value most of `values` repeat, or None."""
    numeric = [v for v in values if isinstance(v, (int, float))]
    if len(numeric) < TEMPLATE_MIN_ITEMS:
        return None
    rounded = Counter(round(v / TEMPLATE_TOLERANCE) for v in numeric)
    key, count = rounded.most_common(1)[0]
    share = count / len(numeric)
    if share < ROLLUP_SHARE:
        return None
    return round(key * TEMPLATE_TOLERANCE, 4), round(share, 3), len(numeric)


def _unit(param):
    return f" {param['unit']}" if param.get("unit") else ""


def _threshold_text(param):
    value = param.get("value", param.get("expr"))
    if isinstance(value, (list, tuple)):
        value = "[" + ", ".join(str(v) for v in value) + "]"
    return f"{param.get('op')} {value}{_unit(param)}"


def outcome_records(ctx, file_key, category_id, rule, check, results):
    """`results`: [(element, value, source, outcome)] for one check."""
    param_name = check["param"]
    param = rule["params"][param_name]
    partial = status_kind(rule["status"]) in ("partial", "widened")
    judged = [r for r in results if not getattr(r[0], "placeholder", False)]
    judged_total = len(judged) or len(results)
    template = _template_value([r[1] for r in judged])
    shares = Counter(r[3] for r in (judged or results))
    groups = defaultdict(list)
    for element, value, source, outcome in results:
        key, storey = _container(ctx, rule, element)
        if _model_level(outcome, shares[outcome] / judged_total if judged_total else 0):
            key = "building"
        groups[(key, outcome)].append((element, value, source, storey))

    records = []
    for (key, outcome), items in sorted(groups.items()):
        items.sort(key=lambda item: item[0].GlobalId)
        storeys = {item[3].GlobalId: item[3] for item in items if item[3] is not None}
        storey = items[0][3] if key != "building" else None
        values = [item[1] for item in items if isinstance(item[1], (int, float))]
        sources = Counter(item[2] for item in items)
        # A container stand-in (provision.py: a storey with a count of zero)
        # places the record on its storey but is not a member.
        members_items = [item for item in items if not getattr(item[0], "placeholder", False)]
        classes = Counter(item[0].is_a() for item in members_items)
        by_storey = Counter(ctx.storey_name(item[3]) if item[3] is not None else "-" for item in items)
        where = ("whole model" if key == "building" else ctx.storey_name(storey) if storey is not None else "no storey")
        verb = {"pass": "meet", "fail": "fail", "warn": "fall short of", "info": "reported against"}[outcome]
        metrics = {
            "kid": rule["kid"], "title": rule["title"], "ruleType": rule["rule_type"],
            "priority": rule["priority"], "topic": rule["topic"], "param": param_name,
            "op": param.get("op"), "threshold": param.get("value", param.get("expr")),
            "unit": param.get("unit"), "measure": check.get("measure"), "count": len(members_items),
            "sources": dict(sources), "status": rule["status"],
            "shareOfJudged": round(shares[outcome] / judged_total, 3) if judged_total else None,
            "modelLevel": key == "building",
        }
        if key == "building":
            metrics["byStorey"] = dict(by_storey)
        if values:
            metrics.update({"min": round(min(values), 4), "max": round(max(values), 4),
                            "mean": round(statistics.fmean(values), 4)})
            if param.get("unit") in LENGTH_UNITS:
                feet = sum(1 for v in values if _whole_feet(v))
                if feet:
                    metrics["imperialDefault"] = feet
        if template is not None:
            metrics["templateValue"] = {"value": template[0], "share": template[1], "count": template[2]}
        if outcome in NEGATIVE or outcome == "info":
            metrics["values"] = {item[0].GlobalId: (round(item[1], 4) if isinstance(item[1], float) else item[1]) for item in members_items}
        class_text = ", ".join(f"{n} {c}" for c, n in classes.most_common()) or "none"
        summary = (
            f"{rule['kid']} {rule['title']}: {len(members_items)} element(s) ({class_text}) {verb} "
            f"{param_name} {_threshold_text(param)} ({param.get('desc', '')}) on {where}"
            + (f", {metrics['shareOfJudged']:.0%} of the judged" if key == "building" and judged_total else "")
            + (f"; measured {metrics['min']} to {metrics['max']}" if values else "")
            + f". Sources: {', '.join(f'{s} x{n}' for s, n in sources.most_common())}."
            + (f" {metrics['imperialDefault']} value(s) are whole feet, a template default rather than a decision."
               if metrics.get("imperialDefault") else "")
            + (f" {template[1]:.0%} of the model's {template[2]} judged values are exactly {template[0]}{_unit(param)}: a template value, not {template[2]} decisions."
               if template is not None else "")
            + (f" {status_kind(rule['status']).capitalize()} rule: {status_note(rule['status'])}." if partial else "")
        )
        records.append(make_intent(
            intent_id=f"{file_key}-{rule['kid'].lower()}-{slug(param_name)}-{outcome}-{key}",
            intent_type=f"{category_id}_{outcome}",
            label=f"{rule['kid']} {param_name} {outcome}: {len(members_items)} ({where})",
            members=[make_member(item[0].GlobalId, ifc_class=item[0].is_a()) for item in members_items],
            detector=category_id,
            rule=rule["kid"],
            summary=summary,
            related_guids=sorted(storeys),
            metrics=metrics,
            polarity="negative" if outcome in NEGATIVE else "positive",
        ))
    return records


def scenario_record(ctx, file_key, category_id, rule, elements, related=None):
    """One model-level record saying the situation the card addresses is
    present: `elements` is the scenario population (members), `related`
    {guid: (element, via)} the entities reached through the selector's
    `related` facet (members of role "context"), the summary
    quotes the card's "applies when", names the counts by class and
    storey, and states whether the requirement is judged (the rule's
    status) or what blocks it (its `needs`). Polarity positive: the record
    asserts that something IS there (intent.py); it never asserts a
    verdict. None for an empty population."""
    if not elements:
        return None
    guids = sorted({e.GlobalId: e for e in elements})
    by_guid = {e.GlobalId: e for e in elements}
    classes = Counter(by_guid[g].is_a() for g in guids)
    storeys = {}
    for g in guids:
        storey = ctx.storey_of(by_guid[g])
        if storey is not None:
            storeys[storey.GlobalId] = storey
    by_storey = Counter(ctx.storey_name(ctx.storey_of(by_guid[g])) if ctx.storey_of(by_guid[g]) is not None else "-" for g in guids)
    kind = status_kind(rule["status"])
    if kind == "deferred":
        judged = "the requirement is not judged: " + status_note(rule["status"]) + (
            f" (needs {', '.join(rule['needs'])})" if rule.get("needs") else "")
    else:
        judged = f"the requirement is judged by this rule ({kind}; see its pass/fail/warn/info/nodata records)"
    applies = rule.get("applies_text") or ""
    related = related or {}
    from .related import ambiguous
    ambiguous_guids = ambiguous(ctx, related)
    related_counts = Counter(via for _e, via in related.values())
    related_classes = Counter(e.is_a() for e, _via in related.values())
    related_text = ", ".join(f"{n} {via.replace('_', ' ')} ({', '.join(f'{m} {c}' for c, m in Counter(e.is_a() for e, v in related.values() if v == via).most_common(3))})"
                             for via, n in related_counts.most_common())
    summary = (
        f"{rule['kid']} {rule['title']}: the situation this card addresses is present"
        + (f" ({applies.rstrip('.')})" if applies else "")
        + f": {len(guids)} element(s) ({', '.join(f'{n} {c}' for c, n in classes.most_common())})"
        + (f" on {', '.join(f'{name} x{n}' for name, n in by_storey.most_common(6))}" if by_storey else "")
        + (f", with {related_text} as context" if related else "")
        + (f" ({len(ambiguous_guids)} of the windows lie within reach of two rooms; their room is a tie-break)" if ambiguous_guids else "")
        + f"; {judged}."
        + (f" Scenario: {rule['scenario_note']}." if rule.get("scenario_note") else "")
    )
    return make_intent(
        intent_id=f"{file_key}-{rule['kid'].lower()}-scenario",
        intent_type=f"{category_id}_scenario",
        label=f"{rule['kid']} scenario present: {len(guids)} element(s)",
        members=[make_member(g, ifc_class=by_guid[g].is_a()) for g in guids]
                + [make_member(g, role="context", ifc_class=related[g][0].is_a()) for g in sorted(related)],
        detector=category_id,
        rule=rule["kid"],
        summary=summary,
        related_guids=sorted(storeys),
        metrics={"kid": rule["kid"], "title": rule["title"], "topic": rule["topic"], "count": len(guids),
                 "classes": dict(classes), "byStorey": dict(by_storey), "status": rule["status"],
                 "needs": list(rule.get("needs") or []), "applies": applies, "scenario": rule.get("scenario"),
                 "related": {via: n for via, n in related_counts.items()}, "relatedClasses": dict(related_classes),
                 "relatedCount": len(related), "relatedAmbiguous": len(ambiguous_guids)},
        polarity="positive",
    )


def nodata_record(ctx, file_key, category_id, rule, missing):
    """`missing`: {guid: (element, [measure names tried])}; None when empty."""
    if not missing:
        return None
    guids = sorted(missing)
    measures = sorted({name for _, names in missing.values() for name in names})
    classes = Counter(missing[g][0].is_a() for g in guids)
    storeys = sorted({ctx.storey_of(missing[g][0]).GlobalId for g in guids if ctx.storey_of(missing[g][0]) is not None})
    return make_intent(
        intent_id=f"{file_key}-{rule['kid'].lower()}-nodata",
        intent_type=f"{category_id}_nodata",
        label=f"{rule['kid']} no data: {len(guids)} element(s)",
        members=[make_member(g, ifc_class=missing[g][0].is_a()) for g in guids],
        detector=category_id,
        rule=rule["kid"],
        summary=(
            f"{rule['kid']} {rule['title']}: {len(guids)} element(s) "
            f"({', '.join(f'{n} {c}' for c, n in classes.most_common())}) carry none of the data the "
            f"rule reads ({', '.join(measures)}); not judged. Missing data is never a failure."
        ),
        related_guids=storeys,
        metrics={"kid": rule["kid"], "title": rule["title"], "topic": rule["topic"],
                 "measures": measures, "count": len(guids), "status": rule["status"]},
        polarity="negative",
    )
