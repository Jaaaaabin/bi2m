"""The `related` selector facet (2026-10-20): from a
primary population to the entities a card reasons over, through relations
the context already knows. A selector may carry

    related:
    - {via: windows}                      the windows assigned to the selected rooms
    - {via: doors}                        the doors reaching the selected rooms (door graph)
    - {via: host_wall}                    the walls the selected windows / doors fill (FillsVoids)
    - {via: furniture, kind: desk}        the furniture standing in the selected rooms, filtered
    - {via: furniture, inside: true}      only the pieces whose placement lies strictly inside the footprint
    - {via: parts, class: IfcSlab}        the decomposition of the selected elements, filtered
    - {via: storey} / {via: building}     the storey / building of the selected elements
    - {via: unit_rooms} / {via: unit_doors}  the rooms / entrance doors of the dwelling a
                                          selected room belongs to (facts.dwelling_units)
    - {via: neighbours}                   the rooms one door away (room_graph)
    - {via: served_storeys}               the storeys a selected stair's or lift's CORE serves
    - {via: served_storeys, span: own}    the storeys the selected element's own body spans

Each entry starts from the whole primary set, follows one relation and may
filter the result with the ordinary selector keys (class, use, prop,
predefined, exclude_use, has_prop, where). The result is {guid: (element,
via)}, primary elements excluded, GUID-sorted by the caller. On the record
the related elements are members of role "context" (highlighting.js draws
them beside the primary members), never counted as judged.

Corpus conditions (the measured basis): windows
reach their room by footprint proximity on 83 % of corpus windows (space
boundaries exist on 12 of 370 models); doors through the shared door graph
(96 % sound on 352 models, empty under the frame guard on 17); furniture by
footprint containment (343 models); dwellings inferred on 92; host walls
through FillsVoids on 97 %; parts by decomposition; cores by z-range.
"""

import ifcopenshell.util.element

from ..room_graph import storey_room_graph
from ..room_routes import host_element
from . import cores, facts


def _guid_map(elements):
    return {e.GlobalId: e for e in elements}


_entity = facts._entity


# ---- relation resolvers: (ctx, primary elements) -> [elements] ----

def via_parts(ctx, elements):
    out = {}
    for element in elements:
        try:
            parts = ifcopenshell.util.element.get_decomposition(element)
        except Exception:  # noqa: BLE001
            parts = ()
        out.update(_guid_map(p for p in parts if hasattr(p, "GlobalId")))
    return list(out.values())


def via_storey(ctx, elements):
    out = {}
    for element in elements:
        storey = ctx.storey_of(element)
        if storey is not None:
            out[storey.GlobalId] = storey
    return list(out.values())


def via_building(ctx, elements):
    out = {}
    buildings = ctx.model.by_type("IfcBuilding")
    for element in elements:
        storey = ctx.storey_of(element)
        parent = ifcopenshell.util.element.get_aggregate(storey) if storey is not None else None
        if parent is not None and parent.is_a("IfcBuilding"):
            out[parent.GlobalId] = parent
        elif len(buildings) == 1:
            out[buildings[0].GlobalId] = buildings[0]
    return list(out.values())


def via_windows(ctx, elements):
    table = ctx.fact("windows_by_room", facts.windows_by_room) or {}
    out = {}
    for element in elements:
        for guid in table.get(element.GlobalId, ()):
            window = _entity(ctx, guid)
            if window is not None:
                out[guid] = window
    return list(out.values())


def via_doors(ctx, elements):
    table = ctx.fact("doors_by_room", facts.doors_by_room) or {}
    out = {}
    for element in elements:
        for guid in table.get(element.GlobalId, ()):
            door = _entity(ctx, guid)
            if door is not None:
                out[guid] = door
    return list(out.values())


def via_host_wall(ctx, elements):
    out = {}
    for element in elements:
        host = host_element(element)  # room_routes' FillsVoids -> VoidsElements walk
        if host is not None:
            out[host.GlobalId] = host
    return list(out.values())


def via_furniture(ctx, elements, inside=False):
    table = ctx.fact("furniture_by_room", facts.furniture_by_room) or {}
    if inside:
        table = table.get("inside", {})
    out = {}
    for element in elements:
        for guid in table.get(element.GlobalId, ()):
            piece = _entity(ctx, guid)
            if piece is not None:
                out[guid] = piece
    return list(out.values())


def _units_of(ctx, elements):
    units = ctx.fact("dwelling_units", facts.dwelling_units) if ctx.graph_usable() else []
    wanted = {e.GlobalId for e in elements}
    return [u for u in units if wanted & set(u["rooms"])]


def via_unit_rooms(ctx, elements):
    out = {}
    for unit in _units_of(ctx, elements):
        for guid in unit["rooms"]:
            room = _entity(ctx, guid)
            if room is not None:
                out[guid] = room
    return list(out.values())


def via_unit_doors(ctx, elements):
    out = {}
    for unit in _units_of(ctx, elements):
        for guid in unit["entrance_doors"]:
            door = _entity(ctx, guid)
            if door is not None:
                out[guid] = door
    return list(out.values())


def via_neighbours(ctx, elements):
    if not ctx.graph_usable():
        return []
    graph = ctx.graph
    by_storey = {}
    for element in elements:
        storey = ctx.storey_of(element)
        if storey is not None:
            by_storey.setdefault(storey.GlobalId, set()).add(element.GlobalId)
    out = {}
    for storey_guid, rooms in by_storey.items():
        if storey_guid not in graph.spaces_by_storey:
            continue
        G, _open = storey_room_graph(graph, storey_guid)
        for room in rooms:
            if room in G:
                for other in G.neighbors(room):
                    neighbour = _entity(ctx, other)
                    if neighbour is not None:
                        out[other] = neighbour
    return list(out.values())


def via_served_storeys(ctx, elements, span="core"):
    """span "core": the storeys the element's core serves (one stair per
    storey in a stack reads the whole stack: right for core-level cards);
    "own": the storeys within the element's own body z-range
    (2026-10-20: 2,455 of 2,770 corpus stairs sit in multi-stair cores)."""
    out = {}
    if span == "own":
        boxes = cores._bboxes(ctx, list(elements))
        elevations = [(s.GlobalId, ctx.storey_elevation_m(s)) for s in ctx.storeys_sorted]
        for element in elements:
            box = boxes.get(element.GlobalId)
            if box is None:
                continue
            z_lo, z_hi = float(box[0][2]), float(box[1][2])
            for guid, elevation in elevations:
                if elevation is not None and z_lo - cores.Z_MARGIN_M <= elevation <= z_hi + cores.Z_MARGIN_M:
                    storey = _entity(ctx, guid)
                    if storey is not None:
                        out[guid] = storey
        return list(out.values())
    wanted = {e.GlobalId for e in elements}
    for core in ctx.fact("vertical_cores", cores.vertical_cores) or []:
        if wanted & set(core["elements"]):
            for guid in core["storeys"]:
                storey = _entity(ctx, guid)
                if storey is not None:
                    out[guid] = storey
    return list(out.values())


RELATIONS = {
    "parts": via_parts, "storey": via_storey, "building": via_building, "windows": via_windows, "doors": via_doors,
    "host_wall": via_host_wall, "furniture": via_furniture, "unit_rooms": via_unit_rooms, "unit_doors": via_unit_doors,
    "neighbours": via_neighbours, "served_storeys": via_served_storeys,
}


ENTRY_OPTIONS = {"inside", "span"}  # relation options, not filter keys


def related_elements(ctx, primary, entries, apply_gates):
    """{guid: (element, via)} for the `related` entries of a selector, from
    the primary elements; `apply_gates(ctx, elements, spec)` is the
    selector's own gate pass (select.py) for the entry's filter keys."""
    primary_guids = {e.GlobalId for e in primary}
    out = {}
    for entry in entries or []:
        via = entry["via"]
        options = {k: v for k, v in entry.items() if k in ENTRY_OPTIONS}
        found = RELATIONS[via](ctx, primary, **options) if options else RELATIONS[via](ctx, primary)
        classes = entry.get("class")
        if classes:
            classes = [classes] if isinstance(classes, str) else list(classes)
            found = [e for e in found if any(e.is_a(c) for c in classes)]  # the class gate, which population() applies before its gates
        filtered, _unknown = apply_gates(ctx, found, {k: v for k, v in entry.items() if k != "via" and k not in ENTRY_OPTIONS})
        for element in filtered:
            if element.GlobalId not in primary_guids and element.GlobalId not in out:
                out[element.GlobalId] = (element, via)
    return out


def ambiguous(ctx, related):
    """The related window guids whose room assignment was a tie-break."""
    if not any(via == "windows" for _e, via in related.values()):
        return set()
    from .geometry import _glazing_by_space
    return set(ctx.fact("glazing_by_space", _glazing_by_space)["ambiguous"]) & set(related)

