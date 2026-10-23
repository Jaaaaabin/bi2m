"""Shared facts the families read through ctx.fact(): exit seeds, route
distances over the door graph, inferred dwelling units. Each is computed
once per model (or per call signature) and shared by every rule that
names it, so a fact is built once and releases its whole group of rules.

Route cost is egress_reachability.py's, shared through room_routes.py
since 2026-10-18 (the extraction was proven byte-identical on the 371
corpus models per hash seed with the shard harness).
Seeds are the rooms an exit door
touches (exit_door_guids: a door tagged IsExternal, or one in an external
wall reaching exactly one room) and rooms named as vertical circulation,
both at 0; a door reaching two rooms is an edge weighted centroid ->
door point -> centroid; Dijkstra from the seed set. The result is a LOWER
BOUND on the walking distance (straight polyline, room representative
point rather than its farthest corner, and a target set that is a superset
of "legally essential"): a measured distance above a threshold is a real
violation, a pass is optimistic. Rooms with no path carry None: the model
cannot demonstrate a route for them, which is a modelling gap as often as
a building defect (egress_reachability's reading).

Dwelling units: see dwelling_units() - cores of the storey room graph
with circulation removed, merged back through the circulation rooms that
only one flat uses, plus single rooms named as a dwelling. Measured on the
corpus before any rule used it.

Workstations and seats: desks and seating furniture per room through the shared furnishing helper
(recognition/furnishing.py, the classifier furniture_occupancy uses), on
the context's world-frame footprints. 217 of the 370 corpus models name a
desk. None when the model has no desk at all, so a measure chain can fall
through to the card's own fallback (OccupancyNumber).

BUILT lists the facts that exist, so a deferred rule cannot keep waiting
on one of them (verify_neufert checks the `needs` tags against it).
"""

from collections import defaultdict

import ifcopenshell.util.element

from .. import vocabulary
from ..components import connected_components
from ..census import elements_by_guid
from shapely.geometry import Point

from ifc_units import placement_xy

from ..furnishing import DEFAULT_FURNITURE_REACH_M, FURNITURE_CLASSES, room_contents
from ..room_graph import components, storey_room_graph
from ..room_routes import exit_door_guids, host_element, shortest_distances, storey_adjacency
from ..spaces import nearest_space
from .cores import (Z_MARGIN_M, _bboxes, stair_core_flats_per_floor, stair_core_has_lift, stair_core_storeys, storey_lift_cores,  # noqa: F401 - re-exported facts
                    storey_stair_cores, vertical_cores)

CIRCULATION = "horizontal_circulation|lobby|vertical_core"
# An exit door reaching only one of these rooms is a garden / terrace door of the flat, not its entrance.
GARDEN_ROOMS = "living|dining|bedroom|kitchen"
# A space of another storey spans this one when the storey's elevation lies this far inside its body.
TALL_MARGIN_M = 0.3
# Storey-less rooms whose bodies stand within this of a level's floor belong to that level.
LEVEL_BAND_M = 0.5
BUILT = ("exit_doors", "exit_seeds", "route_distances", "dwelling_units", "workstations", "seats", "dwelling_storeys", "dwelling_count", "top_storey_rise",
         "windows_by_room", "doors_by_room", "furniture_by_room",
         "vertical_cores", "stair_core_storeys", "stair_core_flats_per_floor", "stair_core_has_lift", "storey_stair_cores", "storey_lift_cores")
UNIT_SERVICE = "kitchen|bathroom|wc"
UNIT_LIVING = "living|bedroom|dwelling"


def exit_doors(ctx):
    """{door guid: "external door" | "external wall door"} through
    egress_reachability's exit_door_guids; built once per model."""
    doors = list(ctx.model.by_type("IfcDoor"))
    is_external = {door.GlobalId: ctx.property_value(door, ("IsExternal",)) is True for door in doors}
    host_external = {}
    for door in doors:
        host = host_element(door)
        host_external[door.GlobalId] = host is not None and ctx.property_value(host, ("IsExternal",)) is True
    reach = {guid: len(reached) for guid, (_s, reached) in ctx.graph.door_links.items()} if ctx.graph is not None else {}
    exits, _kinds = exit_door_guids([door.GlobalId for door in doors], is_external, host_external, reach)
    return {guid: ("external door" if is_external[guid] else "external wall door") for guid in exits}


def exit_seeds(ctx):
    """{storey guid: {room guid: kind}} - rooms an exit door touches
    ("external door" / "external wall door") and rooms named as vertical
    circulation ("vertical core"); {} without a usable door graph."""
    graph = ctx.graph
    if not ctx.graph_usable():
        return {}
    seeds = defaultdict(dict)
    for door_guid, kind in ctx.fact("exit_doors", exit_doors).items():
        link = graph.door_links.get(door_guid)
        if link is None:
            continue
        storey_guid, reached = link
        for guid in reached:
            seeds[storey_guid][guid] = kind
    for storey_guid, storey_spaces in graph.spaces_by_storey.items():
        for guid in storey_spaces:
            space = graph.space_by_guid.get(guid)
            if space is not None and vocabulary.matches(ctx.text(space), "vertical_core"):
                seeds[storey_guid].setdefault(guid, "vertical core")
    return dict(seeds)


def route_distances(ctx, storey_guid, targets):
    """{room guid: metres} from every room of the storey that can reach a
    target room through doors (targets at 0); rooms without a path are
    absent. Exit doors contribute no edge, as in egress_reachability."""
    exits = ctx.fact("exit_doors", exit_doors)
    adjacency = ctx.fact(("adjacency", storey_guid), lambda c: storey_adjacency(c.graph, storey_guid, skip_doors=set(exits)))
    return shortest_distances(adjacency, {guid: 0.0 for guid in sorted(targets)})


def _is(text, concept):
    return vocabulary.matches(text, concept)


def dwelling_units(ctx):
    """[{"key", "storey", "rooms", "entrance_doors", "halls", "garden_doors", "single",
    "shared_circulation", "container"}]: first the flats modelled as a
    container space over their rooms (`container` = its GUID,
    _container_units), then the units inferred from the door graph among
    the remaining rooms (`container` None); [] without a usable graph.
    `key` is the unit's first room GUID in sorted order, the stable
    container key.

    Third form (2026-10-18, after the corpus measurements): cores are
    the components of the storey room graph with
    every circulation room removed; a unit-marker core holds a kitchen or
    a room named as a dwelling (studios and "flat 3" have no kitchen room).
    A circulation room is SHARED when it is a lobby or vertical core, when
    it touches two or more marker cores directly (flats opening onto a
    corridor), when two or more of its adjacent circulation rooms each
    touch a marker core (flats reached through their own halls), or when
    it touches a vertical core or an exit door and sees two or more markers
    counting those neighbours (the corridor between one hall-flat and one
    studio). A flat's own hall touches one marker core and one corridor,
    and no exit or stair, so it is never shared; a house's hall touches the
    front door but only its own kitchen. Every other
    circulation room (a flat's own hall) is merged with the cores it
    touches and with adjacent unshared circulation rooms. A unit is such a
    group of two or more rooms holding at least one kitchen, bathroom or
    wc and one living, bedroom or dwelling room, or a single room named as
    a dwelling ("apartment", "flat", "wohnung").
    """
    graph = ctx.graph
    if not ctx.graph_usable():
        return []
    exits = ctx.fact("exit_doors", exit_doors)
    units, flat_rooms = _container_units(ctx, graph, exits)
    for storey_guid in sorted(graph.spaces_by_storey):
        if storey_guid in graph.degenerate_storeys:
            continue
        through = through_doors(ctx, storey_guid)
        exits_here = set(exits) | through
        G, _open_rooms = storey_room_graph(graph, storey_guid)
        G.remove_nodes_from([guid for guid in list(G.nodes) if guid in flat_rooms])
        texts = {guid: ctx.text(graph.space_by_guid[guid]) for guid in G.nodes}
        circulation = {guid for guid in G.nodes if _is(texts[guid], CIRCULATION)}
        core_of, marker_cores = _unit_cores(G, circulation, texts)
        shared = _shared_circulation(G, circulation, core_of, marker_cores, texts,
                                     _exit_rooms(graph, storey_guid, exits_here))
        for rooms in _room_groups(G, circulation, shared):
            unit = _unit_of(ctx, graph, storey_guid, rooms, exits, shared, through)
            if unit is not None:
                units.append(unit)
    return units


def through_doors(ctx, storey_guid):
    """The through-doors of one storey, computed once per context (the
    container units and the main loop both ask)."""
    table = ctx.fact("through_doors", lambda _ctx: {})
    if storey_guid not in table:
        table[storey_guid] = _through_doors(ctx, ctx.graph, storey_guid)
    return table[storey_guid]


def _through_doors(ctx, graph, storey_guid):
    """Doors of the storey that reach one room and stand in a space of
    ANOTHER storey whose body spans this one: a stairwell modelled as one
    space through every floor (0263, the validation pack's apartment
    building) is on the door graph of its base storey only, so the front
    doors above reach their flat's hall and nothing else. Such a door
    opens onto shared circulation like an exit door does (2026-10-20)."""
    storey = graph.space_by_guid.get(storey_guid) or _entity(ctx, storey_guid)
    elevation = ctx.storey_elevation_m(storey) if storey is not None else None
    if elevation is None:
        return set()
    tall = []
    for other_guid, rooms in graph.spaces_by_storey.items():
        if other_guid == storey_guid:
            continue
        other = _entity(ctx, other_guid)
        base = ctx.storey_elevation_m(other) if other is not None else None
        if base is None:
            continue
        for room in rooms:
            space, polygon = graph.space_by_guid.get(room), ctx.polygons.get(room)
            height = ctx.space_z_extent(space) if space is not None and polygon is not None else None
            if height and base + TALL_MARGIN_M < elevation < base + height - TALL_MARGIN_M:
                tall.append(polygon.buffer(getattr(graph, "door_margin_m", 0)))
    if not tall:
        return set()
    through = set()
    for door_guid, (door_storey, reached) in graph.door_links.items():
        point = graph.door_points.get(door_guid)
        if door_storey == storey_guid and len(reached) == 1 and point is not None and any(p.contains(Point(*point)) for p in tall):
            through.add(door_guid)
    return through


def _entity(ctx, guid):
    try:
        return ctx.model.by_guid(guid)
    except RuntimeError:
        return None


def _container_units(ctx, graph, exits):
    """Units from the flats modelled as one container space over their rooms
    (2026-10-19, corpus probe: 0027's "Wohnung N" and 0095's
    "area-apt.NNN" enclose their rooms geometrically and nothing relational
    ties them; AccessGraph.container_spaces already detects the enclosure).
    A container whose text matches the dwelling concept is a unit whose
    rooms are the leaf rooms it encloses on one storey; Revit "area"
    containers are not dwellings and stay out. Returns (units, the rooms
    taken), so the door-graph inference skips those rooms."""
    containers = getattr(graph, "container_spaces", None) or {}
    storey_of_room = {guid: storey for storey, guids in graph.spaces_by_storey.items() for guid in guids}
    units, taken = [], set()
    for guid, enclosed in sorted(containers.items()):
        try:
            space = ctx.model.by_guid(guid)
        except RuntimeError:
            continue
        if not vocabulary.matches(ctx.text(space), "dwelling"):
            continue
        by_storey = defaultdict(list)
        for room in enclosed:
            storey = storey_of_room.get(room)
            if storey is not None and storey not in graph.degenerate_storeys and room not in taken:
                by_storey[storey].append(room)
        for storey_guid, rooms in sorted(by_storey.items()):
            rooms = sorted(rooms)
            entrance_doors, halls, garden = _entrance_doors(ctx, graph, storey_guid, set(rooms), exits, through_doors(ctx, storey_guid))
            units.append({"key": rooms[0], "storey": storey_guid, "rooms": rooms, "single": len(rooms) == 1,
                          "entrance_doors": entrance_doors, "halls": halls, "garden_doors": garden, "shared_circulation": [],
                          "container": guid})
            taken.update(rooms)
    return units, taken


def _entrance_doors(ctx, graph, storey_guid, room_set, exits, through=()):
    """(entrance doors, halls, garden doors): the storey's doors reaching a
    room inside the set and one outside, or a through-door (a stairwell of
    another storey) reaching one inside room, are the entrances; an exit
    door reaching one inside room is a GARDEN door when that room is a
    living, dining, bedroom or kitchen room (a terrace door: 0263's ground
    floor, 2026-10-20) and an entrance candidate otherwise; the
    exit candidates count as entrances only when the unit has no proper
    one (a house). Halls are the inside rooms the entrances reach."""
    primary, fallback, garden = {}, {}, {}
    for door_guid, (door_storey, reached) in graph.door_links.items():
        if door_storey != storey_guid:
            continue
        inside = [g for g in reached if g in room_set]
        outside = [g for g in reached if g not in room_set]
        if inside and (outside or door_guid in through):
            primary[door_guid] = inside
        elif inside and len(reached) == 1 and door_guid in exits:
            space = graph.space_by_guid.get(inside[0])
            if space is not None and _is(ctx.text(space), GARDEN_ROOMS):
                garden[door_guid] = inside
            else:
                fallback[door_guid] = inside
    chosen = primary or fallback
    return sorted(chosen), sorted({g for inside in chosen.values() for g in inside}), sorted(garden)


def _unit_cores(G, circulation, texts):
    """Components of the room graph without circulation rooms, and the
    indices of those that mark a unit (a kitchen, or a dwelling-named
    room: studios and "flat 3" have no kitchen room)."""
    H = G.copy()
    H.remove_nodes_from(circulation)
    core_of, marker_cores = {}, set()
    for index, component in enumerate(components(H)):
        for guid in component:
            core_of[guid] = index
        if any(_is(texts[g], "kitchen|dwelling") for g in component):
            marker_cores.add(index)
    return core_of, marker_cores


def _exit_rooms(graph, storey_guid, exits):
    rooms = set()
    for door_guid, (door_storey, reached) in graph.door_links.items():
        if door_storey == storey_guid and door_guid in exits:
            rooms.update(reached)
    return rooms


def _shared_circulation(G, circulation, core_of, marker_cores, texts, exit_rooms):
    """The circulation rooms two or more flats use (module docstring)."""
    direct = {r: {core_of[n] for n in G.neighbors(r) if n in core_of and core_of[n] in marker_cores} for r in circulation}
    shared = set()
    for r in circulation:
        marked_neighbours = [n for n in G.neighbors(r) if n in circulation and direct[n]]
        touches_core = r in exit_rooms or any(n in circulation and _is(texts[n], "lobby|vertical_core") for n in G.neighbors(r))
        if (_is(texts[r], "lobby|vertical_core") or len(direct[r]) >= 2 or len(marked_neighbours) >= 2
                or (touches_core and len(direct[r]) + len(marked_neighbours) >= 2)):
            shared.add(r)
    return shared


def _room_groups(G, circulation, shared):
    """Room groups: the room-room edges plus the unshared circulation rooms'
    edges through the shared union-find (components.py); a room with no
    edge is a group of one. Sorted, so record order is stable."""
    edges = [(a, b) for a, b in G.edges if a not in circulation and b not in circulation]
    for r in sorted(circulation - shared):
        for n in G.neighbors(r):
            if n not in shared:
                edges.append((r, n))
    grouped = connected_components(edges)
    in_group = {g for rooms in grouped for g in rooms}
    groups = {min(rooms): sorted(rooms) for rooms in grouped}
    for guid in sorted(G.nodes):
        if guid not in shared and guid not in in_group:
            groups[guid] = [guid]
    return [rooms for _key, rooms in sorted(groups.items())]


def _unit_of(ctx, graph, storey_guid, rooms, exits, shared, through=()):
    """The unit record for a room group that passes the gate, else None."""
    texts = [ctx.text(graph.space_by_guid[g]) for g in rooms]
    single = len(rooms) == 1
    if single:
        if not vocabulary.matches(texts[0], "dwelling"):
            return None
    elif not any(vocabulary.matches(t, UNIT_SERVICE) for t in texts) or not any(vocabulary.matches(t, UNIT_LIVING) for t in texts):
        return None
    entrance_doors, halls, garden = _entrance_doors(ctx, graph, storey_guid, set(rooms), exits, through)
    return {"key": rooms[0], "storey": storey_guid, "rooms": rooms, "single": single,
            "entrance_doors": entrance_doors, "halls": halls, "garden_doors": garden, "shared_circulation": sorted(shared), "container": None}


def _furniture_per_room(ctx, kind):
    """{room guid: elements of `kind` assigned to it} for every room on a
    storey with footprints (0 for a room without one), or None when no
    element of the model is classified as that kind."""
    spaces = ctx.model.by_type("IfcSpace")
    furniture = list(elements_by_guid(ctx.model, FURNITURE_CLASSES).values())
    if not spaces or not furniture or not ctx.polygons:
        return None
    by_level, level_of = ctx.fact("levels", _level_table)
    contents = room_contents(furniture, (kind,), ctx.polygons, by_level, DEFAULT_FURNITURE_REACH_M, ctx.length_scale, storey_of=level_of)
    if not contents:
        return None
    counts = {guid: 0 for guids in by_level.values() for guid in guids}
    for guid, kinds in contents.items():
        counts[guid] = len(kinds.get(kind, ()))
    return counts


class _Level:
    """A level that is no IfcBuildingStorey: rooms and furniture of a floor
    the export left out, keyed by the z their bodies stand on."""

    def __init__(self, key):
        self.GlobalId = key


def _level_table(ctx):
    """(by_level, level_of) over every IfcSpace and piece of furniture of
    the model, once per context (facts._levels)."""
    return _levels(ctx, ctx.model.by_type("IfcSpace"), list(elements_by_guid(ctx.model, FURNITURE_CLASSES).values()))


def level_of(ctx, element):
    """The level key of a room or piece of furniture: its storey's GUID,
    else its pseudo-level (a floor whose storey the export left out), else
    None. The aggregate family's per-storey container (K119 on 0286)."""
    level = ctx.fact("levels", _level_table)[1](element)
    return level.GlobalId if level is not None else None


def _levels(ctx, spaces, furniture):
    """(by_level, level_of): rooms with a footprint grouped by level, and
    the level of any room or piece of furniture: its storey, else the
    highest level whose floor lies at or below the element's world body
    (storey elevations plus the pseudo-levels the storey-less rooms stand
    on, clustered by their body's z within LEVEL_BAND_M). A corpus probe
    (2026-10-20): 953 furniture elements in 12 corpus models have no
    storey and their placement z is unreliable while the body is not;
    0286 keeps 22 rooms and 13 desks on floors whose storeys were not
    exported, aggregated into the site. Bodies are read in one iterator
    pass for the storey-less elements only."""
    orphans = [e for e in list(spaces) + list(furniture) if ctx.storey_of(e) is None]
    boxes = _bboxes(ctx, orphans) if orphans else {}
    levels = [(elevation, storey) for elevation, storey in ((ctx.storey_elevation_m(s), s) for s in ctx.storeys_sorted) if elevation is not None]
    for z in sorted(float(boxes[space.GlobalId][0][2]) for space in spaces if space.GlobalId in boxes):
        if not any(abs(z - floor) <= LEVEL_BAND_M for floor, _level in levels):
            levels.append((z, _Level(f"z={z:.1f}")))
    levels.sort(key=lambda item: item[0])

    def level_of(element):
        storey = ctx.storey_of(element)
        if storey is not None or element.GlobalId not in boxes:
            return storey
        z = float(boxes[element.GlobalId][0][2])
        below = [level for floor, level in levels if floor <= z + Z_MARGIN_M]
        return below[-1] if below else None

    by_level = defaultdict(list)
    for space in spaces:
        level = level_of(space)
        if level is not None and space.GlobalId in ctx.polygons:
            by_level[level.GlobalId].append(space.GlobalId)
    return by_level, level_of


def workstations(ctx):
    """Desks per room (K141's workstation count); see _furniture_per_room."""
    return _furniture_per_room(ctx, "desk")


def seats(ctx):
    """Seating furniture per room (K129's seats); see _furniture_per_room."""
    return _furniture_per_room(ctx, "seat")


def dwelling_count(ctx):
    """{building guid: number of inferred dwellings} for every IfcBuilding
    (a unit counts for the building its storey is aggregated into, else for
    every building): the card logic "no more than two flats" / "more than
    two flats" (K12, K34, K68, K72 scenarios). None without a usable graph."""
    units = ctx.fact("dwelling_units", dwelling_units)
    buildings = ctx.model.by_type("IfcBuilding")
    if not ctx.graph_usable() or not buildings:
        return None
    counts = {b.GlobalId: 0 for b in buildings}
    for unit in units:
        storey = _entity(ctx, unit["storey"])
        parent = ifcopenshell.util.element.get_aggregate(storey) if storey is not None else None
        targets = [parent.GlobalId] if parent is not None and parent.GlobalId in counts else list(counts)
        for guid in targets:
            counts[guid] += 1
    return counts


def windows_by_room(ctx):
    """{room guid: [window guids]} by the glazing association (geometry.py:
    the windows within WINDOW_REACH_M of the room footprint on its storey);
    None when the model's windows do not meet its footprints at all."""
    from .geometry import _glazing_by_space
    glazing = ctx.fact("glazing_by_space", _glazing_by_space)
    if glazing["suspect"]:
        return None
    return {room: sorted(guids) for room, guids in glazing["windows"].items()}


def doors_by_room(ctx):
    """{room guid: [door guids]} from the shared door graph's links; None
    without a usable graph (facts of the frame-guarded models stay empty)."""
    if not ctx.graph_usable():
        return None
    table = {}
    for door_guid, (_storey, reached) in ctx.graph.door_links.items():
        for room in reached:
            table.setdefault(room, []).append(door_guid)
    return {room: sorted(guids) for room, guids in table.items()}


def furniture_by_room(ctx):
    """{room guid: [furniture guids]} for EVERY furniture element standing
    in a room (footprint containment within DEFAULT_FURNITURE_REACH_M on
    the element's level, whatever its kind; the `related: furniture` facet
    filters by concept afterwards), plus, under the key "inside", {room
    guid: [guids]} of the pieces whose placement point lies strictly inside
    the footprint (2026-10-20: 3,927 corridor pieces of 231 models
    stand in the 0.5 m reach outside the footprint, against the wall from
    the room side; "no furniture in escape routes" needs the strict set).
    None without furniture or footprints."""
    # Not furnishing.room_contents: that helper classifies by kind and drops the rest, while this
    # table keeps every piece and the strict `inside` set (code review 2026-10-20).
    furniture = list(elements_by_guid(ctx.model, FURNITURE_CLASSES).values())
    spaces = ctx.model.by_type("IfcSpace")
    if not furniture or not spaces or not ctx.polygons:
        return None
    by_level, level_of = ctx.fact("levels", _level_table)
    table, inside = {}, {}
    for element in furniture:
        level = level_of(element)
        xy = placement_xy(element, ctx.length_scale) if level is not None else None
        if xy is None:
            continue
        nearest, distance = nearest_space(Point(*xy), by_level.get(level.GlobalId, []), ctx.polygons)
        if nearest is not None and distance <= DEFAULT_FURNITURE_REACH_M:
            table.setdefault(nearest, []).append(element.GlobalId)
            if distance == 0:
                inside.setdefault(nearest, []).append(element.GlobalId)
    out = {room: sorted(guids) for room, guids in table.items()}
    out["inside"] = {room: sorted(guids) for room, guids in inside.items()}
    return out


def top_storey_rise(ctx):
    """{building guid: rise of the highest storey holding spaces above the
    ground storey (the lowest at or above 0, else the lowest)}: the
    high-rise gate of K01 (uppermost occupied floor above 22 m; corpus
    probe 2026-10-20: 1 corpus model at 25 m, while 27 models have a roof
    or parapet level above 22 m, which this reading leaves out). None
    without storeys."""
    buildings = ctx.model.by_type("IfcBuilding")
    storeys = [s for s in ctx.storeys_sorted if ctx.storey_elevation_m(s) is not None]
    if not buildings or not storeys:
        return None
    occupied = {}
    for space in ctx.model.by_type("IfcSpace"):
        storey = ctx.storey_of(space)
        if storey is not None:
            occupied[storey.GlobalId] = storey
    elevations = [ctx.storey_elevation_m(s) for s in storeys]
    ground = min([e for e in elevations if e >= 0] or elevations)
    result = {}
    for building in buildings:
        tops = [ctx.storey_elevation_m(s) for s in occupied.values()
                if ctx.storey_elevation_m(s) is not None
                and (ifcopenshell.util.element.get_aggregate(s) is None or ifcopenshell.util.element.get_aggregate(s).GlobalId == building.GlobalId
                     or len(buildings) == 1)]
        result[building.GlobalId] = (max(tops) - ground) if tops else None
    return result


def dwelling_storeys(ctx):
    """{building guid: number of storeys holding at least one inferred
    dwelling} for every IfcBuilding of the model (a storey counts for the
    building it is aggregated into, else for every building): K83's
    "full storeys containing dwellings". None without a usable graph."""
    units = ctx.fact("dwelling_units", dwelling_units)
    buildings = ctx.model.by_type("IfcBuilding")
    if not ctx.graph_usable() or not buildings:
        return None
    storeys_by_building = {b.GlobalId: set() for b in buildings}
    for storey_guid in {u["storey"] for u in units}:
        storey = ctx.model.by_guid(storey_guid)
        parent = ifcopenshell.util.element.get_aggregate(storey) if storey is not None else None
        targets = [parent.GlobalId] if parent is not None and parent.GlobalId in storeys_by_building else list(storeys_by_building)
        for guid in targets:
            storeys_by_building[guid].add(storey_guid)
    return {guid: len(storeys) for guid, storeys in storeys_by_building.items()}
