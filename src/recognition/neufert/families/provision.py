"""Count of a population per container vs threshold: the plan's EXIST /
count rules (K122: a cleaner's room per storey, K94: a kitchen per
dwelling).

Binding keys: `count` (a selector: the things counted; a check may carry
its own `count` and overrides it, K94's storerooms beside its kitchens,
2026-10-19), `per` ("storey", "building" or "dwelling": the inferred
units of facts.dwelling_units),
`checks` ([{param, when?, exists?, count?}]: the count threshold, or with `exists:
true` the plan's EXIST form, "at least one", the param lending its
severity and its gate; `when` {measure, param}
is a gate measured on the container itself, the IfcBuilding or the
storey, that must be satisfied before the container is judged, e.g.
K83's "more than N_LIFT storeys with dwellings"; a container whose gate
measure is None is skipped, not judged). Members are the counted
elements; a storey with none has no member and names the storey in
relatedGuids; a dwelling with none lists the dwelling's rooms as members
(so a reviewer can Refer to the flat) with the count 0. A `widened` rule
reports fail/warn as info.
"""

from collections import defaultdict

from .. import compare, facts
from ..measures import measure
from ..records import outcome_records
from ..rules import DOWNGRADED, status_kind
from ..select import population


class _Container:
    """Stands in for an element so records.py can place a zero-count
    outcome on its storey."""

    placeholder = True

    def __init__(self, storey):
        self.storey = storey
        self.GlobalId = storey.GlobalId if storey is not None else "building"

    def is_a(self, *_):
        return "IfcBuildingStorey" if self.storey is not None else "IfcBuilding"


def _counted(ctx, rule, check):
    """The elements a check counts: its own `count` selector, else the rule's."""
    return population(ctx, check.get("count") or rule["count"] or {})[0]


def run(ctx, file_key, category_id, rule):
    per = rule.get("per") or "storey"
    widened = status_kind(rule["status"]) in DOWNGRADED
    if per == "dwelling":
        return _per_dwelling(ctx, file_key, category_id, rule, widened)
    records = []
    buildings = ctx.model.by_type("IfcBuilding")
    for check in rule["checks"]:
        counted = _counted(ctx, rule, check)
        by_container = defaultdict(list)
        if per == "building":
            by_container["building"] = list(counted)
            containers = {"building": None}
        else:
            containers = {s.GlobalId: s for s in ctx.storeys_sorted}
            # storeys without an Elevation are not in storeys_sorted; they still hold elements (code review 2026-10-20)
            containers.update({s.GlobalId: s for s in sorted(ctx.model.by_type("IfcBuildingStorey"), key=lambda s: s.GlobalId) if s.GlobalId not in containers})
            for element in counted:
                storey = ctx.storey_of(element)
                if storey is not None:
                    by_container[storey.GlobalId].append(element)
        param = rule["params"][check["param"]]
        gate = check.get("when")
        results = []
        for key, storey in containers.items():
            if gate:
                subject = storey if storey is not None else (buildings[0] if buildings else None)
                gate_value = measure(ctx, subject, gate["measure"], rule["derived"])[0] if subject is not None else None
                if gate_value is None or not compare.satisfied(gate_value, rule["params"][gate["param"]]):
                    continue
            elements = by_container.get(key, [])
            outcome = _exists_outcome(elements, param) if check.get("exists") else compare.outcome(float(len(elements)), param, negate=bool(check.get("negate")))
            if widened and outcome in ("fail", "warn"):
                outcome = "info"
            if outcome is None:
                continue
            if elements:
                for element in elements:
                    results.append((element, float(len(elements)), "count", outcome))
            else:
                results.append((_Container(storey), 0.0, "count", outcome))
        scope_rule = dict(rule, scope="building" if per == "building" else "storey")
        records.extend(outcome_records(ctx, file_key, category_id, scope_rule, check, results))
    return records


def _exists_outcome(elements, param):
    """The EXIST form: pass with at least one element, else the param's severity (INFO -> info)."""
    if elements:
        return "pass"
    severity = str(param.get("severity", "FAIL")).lower()
    return "info" if severity in ("info", "report") else severity


def _per_dwelling(ctx, file_key, category_id, rule, widened):
    """One outcome per inferred unit: the count of the check's counted
    rooms inside it against the param. Every room of the unit carries the
    unit's count, so the storey rollup keeps whole flats together; `units`
    in metrics maps each unit key to its count."""
    units = ctx.fact("dwelling_units", facts.dwelling_units)
    if not units:
        return []
    in_any_unit = {g for unit in units for g in unit["rooms"]}
    records = []
    for check in rule["checks"]:
        counted = _counted(ctx, rule, check)
        counted_guids = {e.GlobalId for e in counted}
        # Counted rooms on a storey that belong to no inferred unit: the
        # candidates a reviewer looks at when a unit counts zero (a flat's
        # storeroom is mostly outside the flat, corpus probe: 145 of 450
        # storage rooms on unit storeys sit outside every unit).
        outside_by_storey = defaultdict(int)
        for element in counted:
            storey = ctx.storey_of(element)
            if storey is not None and element.GlobalId not in in_any_unit:
                outside_by_storey[storey.GlobalId] += 1
        param = rule["params"][check["param"]]
        results, unit_counts, outside_counts = [], {}, {}
        for unit in units:
            inside = [g for g in unit["rooms"] if g in counted_guids]
            outside_counts[unit["key"]] = outside_by_storey.get(unit["storey"], 0)
            outcome = compare.outcome(float(len(inside)), param, negate=bool(check.get("negate")))
            if widened and outcome in ("fail", "warn"):
                outcome = "info"
            if outcome is None:
                continue
            unit_counts[unit["key"]] = len(inside)
            for guid in unit["rooms"]:
                results.append((ctx.graph.space_by_guid[guid], float(len(inside)), "count per dwelling", outcome))
        for record in outcome_records(ctx, file_key, category_id, rule, check, results):
            member_guids = {m["guid"] for m in record["members"]}
            record["evidence"]["metrics"]["units"] = {
                unit["key"]: unit_counts[unit["key"]] for unit in units if unit["key"] in unit_counts and member_guids & set(unit["rooms"])}
            record["evidence"]["metrics"]["unitCount"] = len(record["evidence"]["metrics"]["units"])
            record["evidence"]["metrics"]["outsideOnStorey"] = {
                key: outside_counts[key] for key in record["evidence"]["metrics"]["units"] if outside_counts.get(key)}
            record["evidence"]["summary"] += (
                f" Dwellings are inferred from the door graph (facts.dwelling_units); "
                f"{record['evidence']['metrics']['unitCount']} unit(s) in this record.")
            records.append(record)
    return records
