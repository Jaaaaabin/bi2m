"""Population selectors, driven by the `select` dict of a binding or check.

    class:      "IfcDoor" or ["IfcRoof", "IfcSlab"]; subtypes included, GUID-deduplicated
                (census.elements_by_guid), GUID-sorted (docs/detectors.md rule 1)
    query:      an ifcopenshell.util.selector query (2026-10-19), applied to the class
                population when `class` is given, else to the whole model: facets joined
                by "," (and) or "+" (or): "IfcWall, Pset_WallCommon.IsExternal=TRUE",
                "! IfcSlab", "type *= Single", "material *= Brick", "location = Level 0",
                "Name = /.*Treppe.*/", "query:type.Name *= x". Numbers in a query are RAW
                project units and a decimal must be quoted; an element lacking the
                property is dropped (not `unknown`), so a gate whose absence must be
                reported stays a `prop:` gate.
    expand:     "IfcStairFlight" - after the gates, replace each element by the elements
                of that class in its decomposition (get_decomposition, sorted), e.g. the
                flights of the external stairs; `unknown` lists the un-gated parents
    expand_leaf: true - with `expand`, an element that has no part of that class stays
                itself (a leaf IfcRoof with its own body beside roofs built of slabs)
    a LIST of specs is their union (GUID-deduplicated, sorted): K63's ROOF slabs plus
                the leaf roofs (2026-10-20)
    prop:       {IsExternal: false, FireExit: true} - every named property must equal the
                value (properties.property_value over every Pset; a boolean compares as
                boolean, a string case-insensitively)
    on_missing: "exclude" (default: an element lacking a gated property is not selected
                and is counted in `unknown`) or "include"
    predefined: "FLOOR" - get_predefined_type equals the value
    role:       "unit.entrance_doors" | "unit.rooms" | "unit.halls" - the elements a fact exposes
                (facts.dwelling_units), before the class and the gates (2026-10-19)
    where:      [{measure, op, value}] - keep the elements whose measure satisfies the
                comparison (compare.satisfied); an element whose measure is None is
                dropped and counted in `unknown`. The value is a logic constant of the
                card ("one flat per floor", "no lift"), never a threshold: thresholds
                stay in rules/<KID>.yaml and are named by `param`
    kind:       "desk" | "seat" | "bed" (or "a|b"): furniture of that kind by the shared
                classifier (furnishing.classify, with its precedence: a desk chair is a seat)
    exclude_use: a concept (or "a|b"): drop the elements whose text matches it (a lift-named
                lobby is no lift car; 2026-10-20)
    exclude_role: "unit.rooms" - drop the elements a fact exposes under that role (a home office
                inside a flat is no office room for the office cards)
    has_prop:   ["FireRating"] - keep the elements that declare every named property with a
                non-empty value, whatever it is (properties.property_value over every Pset)
    related:    [{via, ...}] - the entities reached from the selected ones through a relation
                (related.py: windows, doors, host_wall, furniture, parts, storey, building,
                unit_rooms, unit_doors, neighbours, served_storeys), filtered by the ordinary
                keys; they are members of role "context" on a scenario record (2026-10-20)
    use:        a vocabulary concept, or "a|b" for any of them, matched on space_text
                (spaces) or, for any other element, on EVERY segment of its Name, its
                type's Name and its ObjectType (2026-10-19: a Revit family path
                "Vertical Circulation : Elevator-Electric : 3000 lbs" names the lift in
                its second segment, which vocabulary.element_text's first-segment rule
                drops; that rule stays for the live detectors, this text is the Neufert
                selector's own)

Returns (selected, unknown): both GUID-sorted lists of entities.
"""

import ifcopenshell.util.element
import ifcopenshell.util.selector

from .. import vocabulary
from ..furnishing import classify
from ..census import elements_by_guid
from . import compare, facts


def _classes(spec):
    classes = spec.get("class") or []
    return [classes] if isinstance(classes, str) else list(classes)


def _prop_matches(ctx, element, name, wanted):
    value = ctx.property_value(element, (name,))
    if value is None:
        return None
    if isinstance(wanted, bool):
        return (value is True) == wanted if isinstance(value, bool) else str(value).strip().lower() == str(wanted).lower()
    if isinstance(wanted, (int, float)):
        try:
            return abs(float(value) - float(wanted)) < 1e-9
        except (TypeError, ValueError):
            return False
    return str(value).strip().lower() == str(wanted).strip().lower()


def element_text(element):
    """Every segment of the element's Name, its type's Name and its
    ObjectType, lowercased: the Neufert selector's text for a non-space."""
    try:
        element_type = ifcopenshell.util.element.get_type(element)
    except Exception:  # noqa: BLE001
        element_type = None
    parts = (getattr(element, "Name", None), getattr(element_type, "Name", None) if element_type is not None else None,
             getattr(element, "ObjectType", None))
    return " ".join(part for part in parts if part).lower()


def _expand(elements, ifc_class, keep_leaf=False):
    expanded = {}
    for element in elements:
        try:
            parts = ifcopenshell.util.element.get_decomposition(element)
        except Exception:  # noqa: BLE001
            parts = ()
        found = False
        for part in parts:
            if part.is_a(ifc_class):
                expanded[part.GlobalId] = part
                found = True
        if keep_leaf and not found:
            expanded[element.GlobalId] = element
    return [expanded[guid] for guid in sorted(expanded)]


ROLES = {
    "unit.entrance_doors": lambda units: [g for u in units for g in u["entrance_doors"]],
    "unit.rooms": lambda units: [g for u in units for g in u["rooms"]],
    "unit.halls": lambda units: [g for u in units for g in u["halls"]],
    "unit.garden_doors": lambda units: [g for u in units for g in u.get("garden_doors", [])],
}


def _role_elements(ctx, role):
    if role not in ROLES:
        raise compare.Unsupported(f"selector role {role!r}")
    units = ctx.fact("dwelling_units", facts.dwelling_units) if ctx.graph_usable() else []
    out = {}
    for guid in ROLES[role](units):
        try:
            out[guid] = ctx.model.by_guid(guid)
        except RuntimeError:  # a graph fixture's synthetic door id
            continue
    return out


def population(ctx, spec):
    """(selected, unknown) for one selector spec against ctx.model; a list
    of specs is their union."""
    if isinstance(spec, list):
        selected, unknown = {}, {}
        for part in spec:
            part_selected, part_unknown = population(ctx, part)
            selected.update({e.GlobalId: e for e in part_selected})
            unknown.update({e.GlobalId: e for e in part_unknown})
        return [selected[g] for g in sorted(selected)], [unknown[g] for g in sorted(unknown) if g not in selected]
    by_guid = elements_by_guid(ctx.model, _classes(spec)) if _classes(spec) else {}
    if spec.get("role"):
        roles = _role_elements(ctx, spec["role"])
        by_guid = {g: e for g, e in roles.items() if not _classes(spec) or g in by_guid}
    if spec.get("query"):
        # an empty class/role population stays empty: None (and an empty set) would search the whole model (code review 2026-10-20)
        if (_classes(spec) or spec.get("role")) and not by_guid:
            found = []
        else:
            found = ifcopenshell.util.selector.filter_elements(ctx.model, spec["query"], set(by_guid.values()) if by_guid else None)
        by_guid = {e.GlobalId: e for e in found if hasattr(e, "GlobalId")}
    elements = [by_guid[guid] for guid in sorted(by_guid)]
    return apply_gates(ctx, elements, spec)


def apply_gates(ctx, elements, spec):
    """(kept, unknown) after the spec's gates (predefined, prop, use,
    exclude_use, exclude_role, has_prop, where, expand) over `elements`:
    the second half of `population`, shared with the `related` facet."""
    unknown = []
    on_missing = spec.get("on_missing", "exclude")

    predefined = spec.get("predefined")
    if predefined is not None:
        wanted = {str(v).upper() for v in (predefined if isinstance(predefined, list) else [predefined])}
        elements = [e for e in elements if str(ifcopenshell.util.element.get_predefined_type(e) or "").upper() in wanted]

    for name, wanted in (spec.get("prop") or {}).items():
        kept = []
        for element in elements:
            verdict = _prop_matches(ctx, element, name, wanted)
            if verdict is None:
                if on_missing == "include":
                    kept.append(element)
                else:
                    unknown.append(element)
            elif verdict:
                kept.append(element)
        elements = kept

    use = spec.get("use")
    if use:
        kept = []
        for element in elements:
            text = ctx.text(element)
            if vocabulary.matches(text, use):
                kept.append(element)
        elements = kept
    if spec.get("kind"):
        # furniture kinds through the shared classifier (furnishing.classify: a "desk chair" is a
        # seat, never a desk; a DESK PredefinedType counts without a name), "a|b" for any
        kinds = tuple(spec["kind"].split("|"))
        elements = [e for e in elements if classify(e, kinds) in kinds]
    if spec.get("exclude_use"):
        elements = [e for e in elements if not vocabulary.matches(ctx.text(e), spec["exclude_use"])]
    if spec.get("exclude_role"):
        excluded = _role_elements(ctx, spec["exclude_role"])
        elements = [e for e in elements if e.GlobalId not in excluded]
    for name in spec.get("has_prop") or []:
        elements = [e for e in elements if ctx.property_value(e, (name,)) not in (None, "")]

    for condition in spec.get("where") or []:
        from .measures import measure  # lazy: measures imports facts, which imports cores, which reads this module's text
        kept = []
        for element in elements:
            value, _source = measure(ctx, element, condition["measure"], {})
            if value is None:
                unknown.append(element)
            elif compare.satisfied(value, {"op": condition["op"], "value": condition["value"]}):
                kept.append(element)
        elements = kept

    # Gates apply to the selected class; the expansion comes last, so K13's
    # IsExternal is read on the IfcStair (Pset_StairCommon), not on the
    # flights it decomposes into, which never carry it.
    if spec.get("expand"):
        elements = _expand(elements, spec["expand"], keep_leaf=bool(spec.get("expand_leaf")))

    unknown_by_guid = {e.GlobalId: e for e in unknown}
    return elements, [unknown_by_guid[g] for g in sorted(unknown_by_guid)]


def related(ctx, spec, primary):
    """{guid: (element, via)} for the spec's `related` entries (related.py),
    empty without any; a list spec gathers every part's entries."""
    from .related import related_elements  # lazy: related imports facts, which reads this module's text
    specs = spec if isinstance(spec, list) else [spec]
    entries = [e for part in specs for e in (part.get("related") or [])]
    return related_elements(ctx, primary, entries, apply_gates) if entries else {}
