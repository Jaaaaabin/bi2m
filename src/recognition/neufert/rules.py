"""The two config layers, loaded lazily and validated once per process.

config/neufert/rules/<KID>.yaml   the card's block, verbatim: `rule`, `params`
                                  ({NAME: {op, value|expr, unit, severity, desc}})
config/neufert/bindings.yaml      bi2m's binding per KID: topic, family,
                                  status, scope, applies, select, derived,
                                  checks, needs (the shared facts, geometry
                                  or inputs a deferred rule waits for, as
                                  `fact:`, `geom:`, `input:`, `family:` tags),
                                  and the card's title / rule type / priority
                                  / level for the records

A binding that names a param its YAML lacks, a family or measure that does
not exist, or a status outside bound/partial/widened/deferred is a
ValueError at load time. `partial: <note>` = some of the card's checks are
skipped, the outcomes of the rest stand; `widened: <note>` = the population
or the targets are wider than the card's gate, so fail and warn become
info (a false fail is the error to avoid); `deferred: <reason>` = not run. Loading happens on the first detect() (engine.py), so a config
error fails that run's Neufert categories - the CLI keeps their previous
records - and never the registry import.
"""

import functools
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parents[3] / "config" / "neufert"
RULES_DIR = CONFIG_DIR / "rules"
BINDINGS_PATH = CONFIG_DIR / "bindings.yaml"

STATUSES = ("bound", "partial", "widened", "deferred")
# (CLASS and PARAM severities never produce a record: compare.outcome never
# sees them because no check binds them; the plan's rule, kept as data.)
# Statuses whose fail/warn outcomes are downgraded to info: a WIDENED
# population can produce false fails (every railing judged as a balcony
# guard); a PARTIAL rule only skipped checks and keeps its outcomes.
DOWNGRADED = ("widened",)


def status_kind(status):
    """'bound', 'partial', 'widened' or 'deferred' from a status string
    such as 'widened: every railing judged against H_LOW'."""
    return str(status).split(":", 1)[0].strip()


def status_note(status):
    parts = str(status).split(":", 1)
    return parts[1].strip() if len(parts) == 2 else ""


def _load_yaml(path):
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


@functools.lru_cache(maxsize=1)
def load_rules():
    """{KID: rule dict}. Each rule: kid, title, topic, family, status, scope,
    select, derived, checks, params, rule_type, priority, level, notes."""
    from . import measures as M  # noqa: WPS433 - avoid an import cycle at module load
    from .families import FAMILIES

    bindings = _load_yaml(BINDINGS_PATH) or {}
    rules = {}
    for kid, binding in bindings.items():
        path = RULES_DIR / f"{kid}.yaml"
        if not path.is_file():
            raise ValueError(f"{kid}: no {path.name} under {RULES_DIR}")
        card = _load_yaml(path) or {}
        if card.get("rule") != kid:
            raise ValueError(f"{kid}: {path.name} declares rule {card.get('rule')!r}")
        params = card.get("params") or {}
        status = binding.get("status", "deferred")
        if status_kind(status) not in STATUSES:
            raise ValueError(f"{kid}: status {status!r}")
        family = binding.get("family")
        if family not in FAMILIES:
            raise ValueError(f"{kid}: family {family!r} is not one of {sorted(FAMILIES)}")
        derived = dict(binding.get("derived") or {})
        checks = list(binding.get("checks") or [])
        if status_kind(status) != "deferred":
            if not checks:
                raise ValueError(f"{kid}: a {status_kind(status)} rule needs checks")
            for check in checks:
                param = check.get("param")
                if param not in params:
                    raise ValueError(f"{kid}: check names param {param!r}, YAML has {sorted(params)}")
                for term in (check, check.get("numerator"), check.get("denominator"),
                             binding.get("numerator"), binding.get("denominator")):
                    measure = (term or {}).get("measure")
                    if measure and measure not in M.PRIMITIVES and measure not in derived:
                        raise ValueError(f"{kid}: measure {measure!r} is neither primitive nor derived")
            for name, expression in derived.items():
                M.validate_expression(name, expression, derived)
        scenario = binding.get("scenario")
        if scenario is not None:
            _validate_selector(kid, "scenario", scenario, M, derived, params)
        # Every other selector-valued key is validated the same way, and a `where ... param` in any of
        # them is resolved here (code review 2026-10-20: only `scenario` was checked before).
        for name in ("select", "applies", "count"):
            if binding.get(name):
                _validate_selector(kid, name, binding[name], M, derived, params)
        # the route targets and the adjacency endpoints carry their families' own keys beside the selector's
        if binding.get("targets"):
            _validate_selector(kid, "targets", binding["targets"], M, derived, params, extra=ROUTE_TARGET_KEYS)
        for name in ("from", "to"):
            if binding.get(name):
                _validate_selector(kid, name, binding[name], M, derived, params, extra=ADJACENCY_KEYS)
        for name in ("numerator", "denominator"):
            for sub in ("select", "count"):
                if (binding.get(name) or {}).get(sub):
                    _validate_selector(kid, f"{name}.{sub}", binding[name][sub], M, derived, params)
        for index, check in enumerate(checks):
            for sub in ("select", "count"):
                if check.get(sub):
                    _validate_selector(kid, f"checks[{index}].{sub}", check[sub], M, derived, params)
            for name in ("numerator", "denominator"):
                for sub in ("select", "count"):
                    if (check.get(name) or {}).get(sub):
                        _validate_selector(kid, f"checks[{index}].{name}.{sub}", check[name][sub], M, derived, params)
        rules[kid] = {
            "kid": kid,
            "title": binding.get("title", kid),
            "topic": binding["topic"],
            "family": family,
            "status": status,
            "scope": binding.get("scope", "storey"),
            "select": binding.get("select") or {},
            "derived": derived,
            "checks": checks,
            "params": params,
            "rule_type": binding.get("rule_type"),
            "priority": binding.get("priority"),
            "level": binding.get("level"),
            "notes": binding.get("notes"),
            "count": binding.get("count"),
            "numerator": binding.get("numerator") or {},
            "denominator": binding.get("denominator") or {},
            "per": binding.get("per"),
            "applies": binding.get("applies") or {},
            "targets": binding.get("targets") or {},
            "from": binding.get("from") or {},
            "to": binding.get("to") or {},
            "relation": binding.get("relation", "door"),
            "quantifier": binding.get("quantifier", "all"),
            "needs": list(binding.get("needs") or []),
            # The scenario layer (2026-10-20): the selector that finds the situation the card
            # addresses, None with `scenario_reason` when the gate itself is the missing fact.
            "scenario": scenario,
            "scenario_reason": binding.get("scenario_reason"),
            "scenario_note": binding.get("scenario_note"),
            "applies_text": binding.get("applies_text"),
        }
    return rules


SELECTOR_KEYS = frozenset({"class", "query", "expand", "expand_leaf", "prop", "on_missing", "predefined", "role", "where", "use",
                           "exclude_use", "exclude_role", "has_prop", "related", "kind"})


ROUTE_TARGET_KEYS = frozenset({"fact"})            # families/route.py: a fact's rooms as targets
ADJACENCY_KEYS = frozenset({"concept", "external"})  # families/adjacency.py: endpoint by concept, external flag, role


def _validate_selector(kid, name, spec, M, derived, params=None, extra=frozenset()):
    """A selector spec (or a list of them) uses known keys only and names
    measures the chains know (select.py's grammar)."""
    for part in (spec if isinstance(spec, list) else [spec]):
        if not isinstance(part, dict) or not part:
            raise ValueError(f"{kid}: {name} must be a selector dict or a list of them, got {part!r}")
        unknown = set(part) - SELECTOR_KEYS - extra
        if unknown:
            raise ValueError(f"{kid}: {name} has unknown selector keys {sorted(unknown)}")
        for entry in part.get("related") or []:
            from .related import RELATIONS
            if not isinstance(entry, dict) or entry.get("via") not in RELATIONS:
                raise ValueError(f"{kid}: {name} related entry {entry!r} needs a `via` among {sorted(RELATIONS)}")
            from .related import ENTRY_OPTIONS
            _validate_selector(kid, f"{name}.related", {k: v for k, v in entry.items() if k != "via" and k not in ENTRY_OPTIONS} or {"class": "IfcProduct"}, M, derived, params)
        for condition in part.get("where") or []:
            measure = condition.get("measure")
            if measure not in M.PRIMITIVES and measure not in derived:
                raise ValueError(f"{kid}: {name} where-measure {measure!r} is neither primitive nor derived")
            if "param" in condition:
                # The card's own param as the where value (K01's H_HR): resolved here, so the
                # threshold stays in rules/<KID>.yaml and the selector names it.
                if condition["param"] not in params:
                    raise ValueError(f"{kid}: {name} where-param {condition['param']!r} is not in the YAML")
                condition["value"] = params[condition["param"]]["value"]
            elif "value" not in condition:
                raise ValueError(f"{kid}: {name} where-condition needs a value or a param")


def rules_for_topic(topic_suffix, active_only=True):
    """The rules of one Topic, in KID order; `active_only` drops deferred ones."""
    found = [rule for rule in load_rules().values() if rule["topic"] == topic_suffix]
    if active_only:
        found = [rule for rule in found if status_kind(rule["status"]) != "deferred"]
    return sorted(found, key=lambda rule: int(rule["kid"][1:]))
