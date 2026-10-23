"""Route distance from each origin room to the nearest target room over
the door graph (facts.route_distances: egress_reachability's cost, a
LOWER BOUND on the walking distance), compared with one param.

Binding keys: `select` (the origin rooms), `targets` ({fact: exit_seeds}
and/or {use: <concept>}; the union, per storey), `checks` ([{param}]).
A room with no modelled path to any target is `nodata` ("the model
cannot demonstrate a route"), never a fail; degenerate storeys are
skipped like every door-graph rule. Every record carries
`isLowerBound: true` and the target kinds. Scope is always the storey.
"""

from .. import compare, facts
from ..records import nodata_record, outcome_records
from ..rules import DOWNGRADED, status_kind
from ..select import population
from ... import vocabulary


def _targets_for_storey(ctx, rule, storey_guid, seeds):
    spec = rule.get("targets") or {}
    targets, kinds = set(), set()
    if spec.get("fact") == "exit_seeds":
        for guid, kind in seeds.get(storey_guid, {}).items():
            targets.add(guid)
            kinds.add(kind)
    if spec.get("use"):
        for guid in ctx.graph.spaces_by_storey.get(storey_guid, []):
            space = ctx.graph.space_by_guid.get(guid)
            if space is not None and vocabulary.matches(ctx.text(space), spec["use"]):
                targets.add(guid)
                kinds.add(f"room named {spec['use']}")
    return targets, kinds


def run(ctx, file_key, category_id, rule):
    graph = ctx.graph
    if not ctx.graph_usable():
        return []
    origins, _unknown = population(ctx, rule["select"]) if rule["select"] else ([], [])
    origin_guids = {o.GlobalId: o for o in origins}
    seeds = ctx.fact("exit_seeds", facts.exit_seeds)
    downgraded = status_kind(rule["status"]) in DOWNGRADED
    records, missing = [], {}
    for check in rule["checks"]:
        param = rule["params"][check["param"]]
        results = []
        for storey_guid, storey_spaces in sorted(graph.spaces_by_storey.items()):
            if storey_guid in graph.degenerate_storeys:
                continue
            here = [guid for guid in storey_spaces if guid in origin_guids]
            if not here:
                continue
            targets, kinds = _targets_for_storey(ctx, rule, storey_guid, seeds)
            distances = facts.route_distances(ctx, storey_guid, targets) if targets else {}
            source = "route:" + "+".join(sorted(kinds)) if kinds else "route:none"
            for guid in here:
                if guid not in distances:
                    missing.setdefault(guid, (origin_guids[guid], []))[1].append("route to " + (", ".join(sorted(kinds)) or "any target"))
                    continue
                outcome = compare.outcome(distances[guid], param)
                if downgraded and outcome in ("fail", "warn"):
                    outcome = "info"
                if outcome is None:
                    continue
                results.append((origin_guids[guid], distances[guid], source, outcome))
        for record in outcome_records(ctx, file_key, category_id, rule, check, results):
            record["evidence"]["metrics"]["isLowerBound"] = True
            record["evidence"]["summary"] += (
                " Distance is a lower bound (centroid to doorway polyline, targets a superset of the legally "
                "essential ones): a value above the threshold is a real violation, a pass is optimistic.")
            records.append(record)
    nodata = nodata_record(ctx, file_key, category_id, rule, missing)
    if nodata is not None:
        nodata["evidence"]["summary"] += " No modelled door path reaches a target: the model cannot demonstrate a route (a modelling gap as often as a defect)."
        records.append(nodata)
    return records
