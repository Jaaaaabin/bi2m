"""topic_detector(suffix) -> detect(model, extracted, file_key, graph=None):
the one detector shape every Neufert category registers. It loads the rule
layers on first use (rules.py), builds the per-model Context once, and runs
each bound or partial rule of the Topic through its family. A rule's
exception propagates, so the category fails as one and the CLI keeps its
previous records (the merged.py rule). Record ids, types and metrics come
from records.py; nothing here knows a K-number.
"""


from .context import Context
from .families import FAMILIES
from .records import scenario_record
from .rules import rules_for_topic, status_kind
from .select import population, related
from .topics import category_id


# One Context per (model, graph) across the 13 Topic categories of a run:
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


def run_topic(suffix, model, file_key, graph=None):
    """Every rule of the Topic: first its scenario record (the situation the
    card addresses is present, 2026-10-20, records.scenario_record), then,
    for an active rule, its family's verdict records."""
    rules = rules_for_topic(suffix, active_only=False)
    if not rules:
        return []
    ctx = context_for(model, graph)
    records = []
    for rule in rules:
        if rule.get("scenario"):
            found, _unknown = population(ctx, rule["scenario"])
            record = scenario_record(ctx, file_key, category_id(suffix), rule, found, related(ctx, rule["scenario"], found) if found else {})
            if record is not None:
                records.append(record)
        if status_kind(rule["status"]) == "deferred":
            continue
        # The card's "Applies when" as a selector: an empty population means
        # NOT_APPLICABLE for this model, and the rule emits nothing.
        if rule.get("applies") and not population(ctx, rule["applies"])[0]:
            continue
        records.extend(FAMILIES[rule["family"]](ctx, file_key, category_id(suffix), rule))
    return records


def topic_detector(suffix):
    def detect(model, extracted, file_key, graph=None):
        return run_topic(suffix, model, file_key, graph=graph)
    detect.__name__ = f"detect_{category_id(suffix)}"
    detect.__doc__ = f"Neufert Topic '{suffix}': the rules bound to it in config/neufert/bindings.yaml."
    return detect
