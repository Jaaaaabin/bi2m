"""Spatial relation between two room populations inside a container, as
data: `from` rooms must relate to `to` rooms (K87: the kitchen and WC of a
dwelling share a door with its entrance hall; K82: a dwelling's open space
shares a door with a living, working or dining room).

Binding keys:
    per:        dwelling | storey   (the container the populations are taken from)
    from, to:   {concept: "kitchen|wc"} - rooms matching a vocabulary concept
                {role: "unit.hall" | "unit.rooms"} - a role facts.dwelling_units exposes
                {external: true} - rooms tagged IsExternal (balconies, terraces)
    relation:   door   (the two rooms share a door in the storey room graph; the
                room itself counts as related to itself). `boundary` and `wall`
                are not built: a binding naming them stays deferred.
    quantifier: all (every `from` room relates to some `to` room; value = share),
                any (at least one does; value = 1 or 0),
                count (how many do; value = the count, compared with the param)
    checks:     [{param}]

Per container: no `from` room -> no record; no `to` room -> nodata for
the `from` rooms (the relation cannot be tested); else one outcome for
the container, carried by every room of it so the storey rollup keeps
the container whole. `all`/`any` take the param's severity when they
fail; `count` compares with the param's op and value. A `widened` rule
reports fail/warn as info.
"""

from .. import compare, facts
from ..records import nodata_record, outcome_records
from ...room_graph import storey_room_graph
from ..rules import DOWNGRADED, status_kind
from ... import vocabulary
from ...properties import is_external

RELATIONS = ("door",)
QUANTIFIERS = ("all", "any", "count")


def _containers(ctx, per):
    """[(key, storey guid, [room guids], roles)]"""
    graph = ctx.graph
    if per == "dwelling":
        return [(u["key"], u["storey"], list(u["rooms"]), {"unit.hall": list(u["halls"]), "unit.rooms": list(u["rooms"])})
                for u in ctx.fact("dwelling_units", facts.dwelling_units)]
    return [(storey_guid, storey_guid, list(rooms), {}) for storey_guid, rooms in sorted(graph.spaces_by_storey.items())
            if storey_guid not in graph.degenerate_storeys]


def _resolve(ctx, spec, rooms, roles):
    if "role" in spec:
        return [g for g in roles.get(spec["role"], []) if g in rooms]
    out = []
    for g in rooms:
        space = ctx.graph.space_by_guid.get(g)
        if space is None:
            continue
        if "concept" in spec and not vocabulary.matches(ctx.text(space), spec["concept"]):
            continue
        if spec.get("external") and not (is_external(space) or vocabulary.matches(ctx.text(space), "balcony")):
            continue
        out.append(g)
    return out


def run(ctx, file_key, category_id, rule):
    graph = ctx.graph
    if not ctx.graph_usable():
        return []
    relation = rule.get("relation", "door")
    quantifier = rule.get("quantifier", "all")
    if relation not in RELATIONS or quantifier not in QUANTIFIERS:
        raise compare.Unsupported(f"adjacency relation {relation!r} / quantifier {quantifier!r}")
    downgraded = status_kind(rule["status"]) in DOWNGRADED
    graphs = {}
    records, missing = [], {}
    for check in rule["checks"]:
        param = rule["params"][check["param"]]
        severity = str(param.get("severity", "WARN")).lower()
        results = []
        for key, storey_guid, rooms, roles in _containers(ctx, rule.get("per") or "storey"):
            if storey_guid not in graphs:
                graphs[storey_guid] = storey_room_graph(graph, storey_guid)[0]
            G = graphs[storey_guid]
            sources = _resolve(ctx, rule.get("from", {}), rooms, roles)
            targets = _resolve(ctx, rule.get("to", {}), rooms, roles)
            if not sources:
                continue
            if not targets:
                for g in rooms:
                    missing.setdefault(g, (graph.space_by_guid[g], []))[1].append(f"{rule.get('to')} room to relate to")
                continue
            related = [g for g in sources if g in targets or any(G.has_edge(g, t) for t in targets if g in G and t in G)]
            if quantifier == "count":
                value = float(len(related))
                outcome = compare.outcome(value, param, negate=bool(check.get("negate")))
            else:
                ok = len(related) == len(sources) if quantifier == "all" else bool(related)
                value = len(related) / len(sources) if quantifier == "all" else float(bool(related))
                outcome = "pass" if ok else ("info" if severity in ("info", "report") else severity)
            if downgraded and outcome in ("fail", "warn"):
                outcome = "info"
            if outcome is None:
                continue
            for g in rooms:
                results.append((graph.space_by_guid[g], value, f"{relation} adjacency, {quantifier}", outcome))
        for record in outcome_records(ctx, file_key, category_id, rule, check, results):
            record["evidence"]["summary"] += (
                f" Relation {relation}, quantifier {quantifier}: value = "
                + ("share of the `from` rooms related to a `to` room" if quantifier == "all" else "1 when any `from` room relates" if quantifier == "any" else "count of related rooms")
                + f"; containers per {rule.get('per') or 'storey'}"
                + (", inferred from the door graph (facts.dwelling_units)" if rule.get("per") == "dwelling" else "") + ".")
            records.append(record)
    nodata = nodata_record(ctx, file_key, category_id, rule, missing)
    if nodata is not None:
        records.append(nodata)
    return records
