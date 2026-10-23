"""Pre-flight completeness report (docs/detectors.md
"How categories are organised"): say up front which categories CANNOT produce output for this model,
and why, instead of letting them degrade silently to zero intents - and,
since 2026-10-08, which ones are UNLIKELY to, and why.

The corpus is the binding constraint - `IfcSpace` exists in 4 of 6 models,
`IfcWindow` in 2, `IfcRelSpaceBoundary` in 1 - and a category whose input
signal is absent used to look identical to one that ran and found nothing.
Each registry entry may declare `signals` (hard: absent -> inapplicable) and
`soft_signals` (soft: absent -> unlikely, the category still runs), in one
grammar:

    "IfcSpace"                        an instance of this class (subtypes included)
    "IfcStair|IfcRamp"                an instance of ANY of these
    "prop:IsExternal"                 an IfcPropertySingleValue of that name with a value
    "prop:FireRating@IfcDoor|IfcWall" a value of that property on an instance of one of these classes
    "true:IsExternal@IfcDoor|IfcWall" the boolean property True on an instance of one of these classes
    "vocab:horizontal_circulation"    a space whose name text matches the concept (recognition/vocabulary.py);
                                      "vocab:seating|sleeping" = any of; the fixture concepts are
                                      matched on elements of the owning detector's classes instead
                                      (seating, sleeping: furniture_occupancy.FURNITURE_CLASSES;
                                      sanitary_fixture, sanitary_accessory: sanitary_provision.FIXTURE_CLASSES)
    "footprints:usable"               room footprints are not degenerate on most storeys with rooms,
                                      judged from the shared door graph (AccessGraph.degenerate_storeys);
                                      not evaluated without a graph

A category with no `signals` (or an empty tuple) is always applicable.
Probes are cheap (`by_type` on a class, one pass over property values or
names) and run once per model before the detectors; the `vocab:` probes use
the detectors' own readers, so a probe cannot disagree with its detector.

The report is written into the shard (`preflight`) so the panel can tell the
reviewer "Not applicable to this model (no IfcSpace): Room Access, ..." - a
statement about the MODEL, not a zero count - and, in a second line,
"Unlikely to produce output here (no door or wall tagged IsExternal): Egress
and Fire". Inapplicable categories still run (a probe can be wrong for an
exotic export, and running costs nothing when the input is empty); the
report only labels. After the run, `zero_output` names the categories that
were applicable, ran, and produced nothing: the loop closed on every run.
`merge_report` folds a partial run's report into the
shard's stored one, so a run of some categories never erases what an
earlier run knew about the others.
"""

import math
import weakref

import ifcopenshell.util.element

from . import vocabulary
from .session import psets_of
from .detectors.furniture_occupancy import FURNITURE_CLASSES
from .detectors.sanitary_provision import FIXTURE_CLASSES

PROP_PREFIX = "prop:"
TRUE_PREFIX = "true:"
VOCAB_PREFIX = "vocab:"
FOOTPRINTS_PREFIX = "footprints:"
# Fixture concepts are probed on the classes the owning detector scans, so a
# probe cannot say "unlikely" where the detector fires.
FIXTURE_CONCEPTS = {
    "sanitary_fixture": FIXTURE_CLASSES, "sanitary_accessory": FIXTURE_CLASSES,
    "seating": FURNITURE_CLASSES, "sleeping": FURNITURE_CLASSES,
}

# Per-model memo for the property and vocabulary probes. Keyed on the model
# OBJECT through a weak reference: the previous `(id(model), name)` key in a
# module-level dict could hand a later file the answer computed for an
# earlier one once CPython reused the freed address (main() opens the
# corpus one model after another in a single process).
_PROPERTY_CACHE = weakref.WeakKeyDictionary()


def parse_signal(signal):
    """(kind, name, classes) for one signal string; kind is "class", "prop",
    "true", "vocab" or "footprints". Raises ValueError on an unknown form."""
    for prefix, kind in ((PROP_PREFIX, "prop"), (TRUE_PREFIX, "true")):
        if signal.startswith(prefix):
            name, _, scope = signal[len(prefix):].partition("@")
            if not name:
                raise ValueError(f"signal {signal!r} names no property")
            return kind, name, tuple(cls for cls in scope.split("|") if cls)
    if signal.startswith(VOCAB_PREFIX):
        concepts = signal[len(VOCAB_PREFIX):]
        for concept in concepts.split("|"):
            if concept != "sanitary_fixture" and concept not in vocabulary.CONCEPTS:
                raise ValueError(f"signal {signal!r} names no vocabulary concept")
        return "vocab", concepts, ()
    if signal.startswith(FOOTPRINTS_PREFIX):
        if signal != FOOTPRINTS_PREFIX + "usable":
            raise ValueError(f"signal {signal!r}: only footprints:usable exists")
        return "footprints", "usable", ()
    if ":" in signal:
        raise ValueError(f"signal {signal!r} has an unknown prefix")
    return "class", "", tuple(signal.split("|"))


def _class_present(model, ifc_class):
    try:
        return bool(model.by_type(ifc_class))
    except RuntimeError:
        # Not a class in this schema (e.g. an IFC2X3 export asked about an
        # IFC4-only class) - treat as absent.
        return False


def _instances(model, classes):
    found = []
    for ifc_class in classes:
        try:
            found.extend(model.by_type(ifc_class))
        except RuntimeError:
            continue
    return found


def _cached(model, key, compute):
    try:
        cache = _PROPERTY_CACHE.setdefault(model, {})
    except TypeError:  # not weak-referenceable: probe without memoising
        cache = {}
    if key not in cache:
        cache[key] = compute()
    return cache[key]


def _property_present(model, name):
    def compute():
        for prop in model.by_type("IfcPropertySingleValue"):
            if prop.Name == name and prop.NominalValue is not None:
                value = prop.NominalValue.wrappedValue
                if value not in (None, "", False) or value is False and name == "IsExternal":
                    return True
        return False
    return _cached(model, PROP_PREFIX + name, compute)


def _property_on(model, name, classes, require_true):
    """A value (or, with require_true, the value True) of property `name` in
    any property set of an instance of one of `classes`."""
    for element in _instances(model, classes):
        for pset in psets_of(element).values():  # the model session's memo (session.py)
            value = pset.get(name)
            if value is None or value == "":
                continue
            if not require_true or value is True:
                return True
    return False


def _property_true_anywhere(model, name):
    for prop in model.by_type("IfcPropertySingleValue"):
        if prop.Name == name and prop.NominalValue is not None and prop.NominalValue.wrappedValue is True:
            return True
    return False


def _vocab_present(model, concepts):
    for concept in concepts.split("|"):
        if concept in FIXTURE_CONCEPTS:
            for element in _instances(model, FIXTURE_CONCEPTS[concept]):
                text = vocabulary.element_text(element)
                hit = vocabulary.fixture_kind(text) is not None if concept == "sanitary_fixture" else vocabulary.matches(text, concept)
                if hit:
                    return True
        else:
            for space in _instances(model, ("IfcSpace",)):
                if vocabulary.matches(vocabulary.space_text(space), concept):
                    return True
    return False


def _storeys_with_rooms(graph):
    return [guid for guid, rooms in graph.spaces_by_storey.items() if rooms]


def footprints_usable(graph):
    """False when degenerate storeys are at least half of the storeys with
    rooms; True with nothing to judge."""
    with_rooms = _storeys_with_rooms(graph)
    if not with_rooms:
        return True
    return len(graph.degenerate_storeys) < math.ceil(len(with_rooms) / 2)


def signal_available(model, signal, graph=None):
    """True / False, or None for a footprints signal without a graph."""
    kind, name, classes = parse_signal(signal)
    if kind == "class":
        return any(_class_present(model, cls) for cls in classes)
    if kind == "prop":
        if not classes:
            return _property_present(model, name)
        return _cached(model, signal, lambda: _property_on(model, name, classes, require_true=False))
    if kind == "true":
        if not classes:
            return _cached(model, signal, lambda: _property_true_anywhere(model, name))
        return _cached(model, signal, lambda: _property_on(model, name, classes, require_true=True))
    if kind == "vocab":
        return _cached(model, signal, lambda: _vocab_present(model, name))
    return None if graph is None else footprints_usable(graph)


def describe_signal(signal, graph=None):
    kind, name, classes = parse_signal(signal)
    if kind == "class":
        return "no " + " / ".join(classes)
    if kind == "prop":
        return f"no {name} property values" if not classes else f"no {name} values on {' / '.join(classes)}"
    if kind == "true":
        return f"no {' / '.join(classes) if classes else 'element'} tagged {name}"
    if kind == "vocab":
        concepts = name.split("|")
        if all(concept in FIXTURE_CONCEPTS for concept in concepts):
            if concepts == ["seating", "sleeping"]:
                return "no fixture named as seating or sleeping furniture"
            return "no fixture named as " + " or ".join("a " + c.replace("_", " ") for c in concepts)
        return f"no space named as {' or '.join(c.replace('_', ' ') for c in concepts)} (any language in the table)"
    if graph is None:
        return "room footprints not judged (no door graph)"
    return f"room footprints degenerate on {len(graph.degenerate_storeys)} of {len(_storeys_with_rooms(graph))} storeys"


def preflight(model, categories, category_ids=None, graph=None):
    """Returns {"signals": {signal: bool}, "inapplicable": [{"category",
    "label", "missing": [signal, ...]}], "unlikely": [{"category", "label",
    "missing": [signal, ...], "why": [text, ...]}]} for the given registry
    dict, limited to `category_ids` when given. Soft signals that need the
    door graph are evaluated only when `graph` is given."""
    ids = list(category_ids) if category_ids else list(categories)
    needed = sorted({sig for cid in ids for sig in categories[cid].get("signals", ())})
    availability = {sig: signal_available(model, sig, graph) for sig in needed}
    inapplicable = []
    for cid in ids:
        missing = [sig for sig in categories[cid].get("signals", ()) if not availability[sig]]
        if missing:
            inapplicable.append({"category": cid, "label": categories[cid]["label"], "missing": missing})
    unlikely = []
    inapplicable_ids = {entry["category"] for entry in inapplicable}
    for cid in ids:
        if cid in inapplicable_ids:
            continue  # "cannot" already said; "unlikely" would be vacuous (review, 2026-10-08)
        soft = categories[cid].get("soft_signals", ())
        for sig in soft:
            if sig not in availability:
                availability[sig] = signal_available(model, sig, graph)
        missing = [sig for sig in soft if availability[sig] is False]
        if missing:
            unlikely.append({"category": cid, "label": categories[cid]["label"], "missing": missing,
                             "why": [describe_signal(sig, graph) for sig in missing]})
    return {"signals": availability, "inapplicable": inapplicable, "unlikely": unlikely}


def zero_output(report, completed, counts, categories=None):
    """The categories of a run that were applicable, completed, and produced
    no record - in `completed` order. A tombstone (registry `retired`) is
    never listed: it always produces nothing. Tolerates a report without
    `unlikely` (a shard written before 2026-10-08)."""
    inapplicable = {entry["category"] for entry in report.get("inapplicable", [])}
    retired = {cid for cid, info in (categories or {}).items() if info.get("retired")}
    return [cid for cid in completed if cid not in inapplicable and cid not in retired and counts.get(cid, 0) == 0]


def merge_report(previous, current, categories, recomputed):
    """The report to store after a run that may have recomputed only some
    categories (the viewer's Run, a `--categories` run): the shard is
    cumulative, so a per-run report must not erase what an earlier run
    knew. `signals` this run could not judge (None: a footprint verdict
    without a door graph) keep their previous value; a category with such a
    signal keeps its previous `unlikely` entry when it has one; `zeroOutput`
    keeps the entries of categories this run did not recompute. `previous`
    None (no shard yet) passes `current` through unchanged (review, 2026-10-08)."""
    if not previous:
        return current
    merged = dict(current)
    signals = dict(current.get("signals", {}))
    for sig, value in signals.items():
        if value is None and previous.get("signals", {}).get(sig) is not None:
            signals[sig] = previous["signals"][sig]
    merged["signals"] = signals
    current_signals = current.get("signals", {})
    # Unjudged = evaluated to None this run (a footprint verdict without a
    # graph); a signal the run never evaluated at all is not in `signals`.
    unjudged = {cid for cid, info in categories.items()
                if any(sig in current_signals and current_signals[sig] is None for sig in info.get("soft_signals", ()))}
    previous_unlikely = {entry["category"]: entry for entry in previous.get("unlikely", [])}
    current_unlikely = {entry["category"]: entry for entry in current.get("unlikely", [])}
    inapplicable_now = {entry["category"] for entry in current.get("inapplicable", [])}
    unlikely = []
    for cid in categories:
        if cid in inapplicable_now:
            continue  # "cannot" is this run's verdict; an older "unlikely" is vacuous beside it
        if cid in unjudged and cid in previous_unlikely:
            unlikely.append(previous_unlikely[cid])
        elif cid in current_unlikely:
            unlikely.append(current_unlikely[cid])
    merged["unlikely"] = unlikely
    recomputed = set(recomputed)
    kept = [cid for cid in previous.get("zeroOutput", []) if cid not in recomputed]
    merged["zeroOutput"] = kept + [cid for cid in current.get("zeroOutput", []) if cid not in kept]
    return merged


def format_report(report):
    """One human line per missing signal, for the CLI's stdout (which the
    panel's Run button shows)."""
    lines = []
    if not report["inapplicable"]:
        lines.append("  pre-flight: every category's input signals are present")
    else:
        by_missing = {}
        for entry in report["inapplicable"]:
            by_missing.setdefault(tuple(entry["missing"]), []).append(entry["category"])
        lines.append("  pre-flight: some categories cannot produce output for this model:")
        for missing, cids in sorted(by_missing.items()):
            why = ", ".join(describe_signal(sig) for sig in missing)
            lines.append(f"    {why}: {', '.join(cids)}")
    if report.get("unlikely"):
        by_why = {}
        for entry in report["unlikely"]:
            by_why.setdefault(", ".join(entry["why"]), []).append(entry["category"])
        lines.append("  pre-flight: unlikely to produce output here:")
        for why, cids in sorted(by_why.items()):
            lines.append(f"    {why}: {', '.join(cids)}")
    return "\n".join(lines)


def format_zero_output(ids):
    """One line naming the categories that were applicable, ran, and
    produced nothing; empty for none."""
    return f"  zero output (applicable, ran, nothing): {', '.join(ids)}" if ids else ""
