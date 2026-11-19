"""rule_detector(rid) -> detect(model, extracted, file_key, graph=None):
the one detector shape every Neufert category registers, one category per
rule of the Neufert section (2026-10-28; the 13 Topic categories before).
It loads the rule layers on first use (rules.py), builds the per-model
Context once, and runs the rule through its family (run_rules, which
verify_neufert also drives with its family fixtures). A rule's exception
propagates, so the category fails as one and the CLI keeps its previous
records (the merged.py rule). Record ids, types and metrics come from
records.py; nothing here knows a rule number.
"""


from .context import Context
from .families import FAMILIES
from .records import scenario_record
from . import pilot
from .rules import load_rules, status_kind
from .select import population, related


# One Context per (model, graph) across the Neufert categories of a run:
# the CLI calls each category's detect() in turn on the same model, and
# the footprints, property sets and facts are the same for all of them
# (profiled 2026-10-18: every category paid 0.3 s to rebuild them). Keyed
# on the model object through a weak reference, as preflight.py does, so a
# later file never gets an earlier file's context.
# Only the current model's contexts are kept: a Context holds the model, so
# a weak-key dictionary never freed anything (code review 2026-10-20: a
# 370-model run in one process kept every model, graph and cached shape
# alive); a later file clears the earlier one's contexts.
_CONTEXTS = {"model": None, "by_graph": {}}


def context_for(model, graph):
    if _CONTEXTS["model"] is not model:
        _CONTEXTS["model"], _CONTEXTS["by_graph"] = model, {}
    by_graph = _CONTEXTS["by_graph"]
    key = id(graph) if graph is not None else None
    if key not in by_graph:
        by_graph[key] = Context(model, graph)
    return by_graph[key]


def run_rules(rules, category_id_, model, file_key, graph=None, judge=True):
    """Every rule given, as records of one category: first its scenario
    record (the situation the card addresses is present, 2026-10-20,
    records.scenario_record), then, for an active rule and `judge`, its
    family's verdict records. `judge` False is the selection alone
    (pilot.JUDGE, 2026-10-29); the family fixtures keep the default."""
    if not rules:
        return []
    ctx = context_for(model, graph)
    records = []
    for rule in rules:
        if rule.get("scenario"):
            found, _unknown = population(ctx, rule["scenario"])
            record = scenario_record(ctx, file_key, category_id_, rule, found, related(ctx, rule["scenario"], found) if found else {}, judged=judge)
            if record is not None:
                records.append(record)
        if not judge or status_kind(rule["status"]) == "deferred":
            continue
        # The card's "Applies when" as a selector: an empty population means
        # NOT_APPLICABLE for this model, and the rule emits nothing.
        if rule.get("applies") and not population(ctx, rule["applies"])[0]:
            continue
        records.extend(FAMILIES[rule["family"]](ctx, file_key, category_id_, rule))
    return records


def run_rule(rid, model, file_key, graph=None, judge=None):
    """One pilot rule as its own category (2026-10-28); judged when `judge`
    is true, else as pilot.JUDGE says (2026-10-29: selection only)."""
    return run_rules([load_rules()[rid]], pilot.category_id(rid), model, file_key, graph=graph,
                     judge=pilot.JUDGE if judge is None else judge)


def rule_detector(rid):
    def detect(model, extracted, file_key, graph=None):
        return run_rule(rid, model, file_key, graph=graph)
    detect.__name__ = f"detect_{pilot.category_id(rid)}"
    detect.__doc__ = f"Neufert rule {rid}: its binding in config/neufert/bindings.yaml."
    return detect
