"""Primitive measures as data, derived measures as expressions.

A PRIMITIVE is a name, a kind (how its raw value is scaled to SI) and a
fallback chain tried in order until one step returns a value that is
declared. A declared value equal to one of the primitive's `unset` values
(0 for every numeric kind unless the entry says otherwise) is "not
declared" and the chain goes on: the corpus sweep
found every K63 fail on a `PitchAngle` of 0 and every K112 hard fail on a
2.4384 m (8 ft) height, exporter defaults rather than decisions, so a zero
never reaches a verdict and a geometry step gets its turn. Chain steps:

    ("attr", "RiserHeight")                        the entity attribute
    ("pset", "Pset_StairFlightCommon", "RiserHeight")  one named property set
    ("qto", "NetFloorArea")                        any quantity set (get_psets qtos_only)
    ("prop", "RiserHeight")                        any property set (properties.property_value)
    ("geom", "z_extent")                           a geometry primitive below
    ("fact", "workstations")                       a per-room fact (facts.py), read by GUID
    ("fact_storey", "storey_lift_cores")           a per-storey fact, read through the element's storey
    ("fact_building", "dwelling_count")            a per-building fact, read through the element's
                                                   building (its storey's aggregate parent, else the
                                                   model's one building)
    ("value", "type.Name")                         an ifcopenshell.util.selector value path
                                                   (2026-10-19): type.X, storey.X, container.X,
                                                   building.X, material.X, Pset.X, Qto.X, x/y/z,
                                                   predefined_type; scaled by the kind like a pset
    ("parent_pset", "Pset_StairCommon", "RiserHeight")  the named property set of the element's
                                                   aggregate parent (a flight's IfcStair)
    ("corroborated", "riser")                      the flight-trust verdict (below): a value the
                                                   declared chain is overruled with, or a rejection

Flight trust (2026-10-20, the validation round): a
flight's declared riser x declared riser count is checked against the rise
of its own body. When the product, less RISER_SLACK risers, EXCEEDS the
body's rise by more than CORROBORATE_TOL (one-directional: a body
covering both runs of a stair reads larger, never smaller, than one run's
count says; the slack absorbs the top riser a run leaves to its landing),
the declared
values are exporter junk (the Digital Hub: 0.587 m and a 1 ft default
beside a parent IfcStair that says 0.177 m) and the flight is re-read from
its parent's Pset_StairCommon with the count derived from the body:
round(rise / parent riser), accepted when within COUNT_ROUND_TOL of a
whole number (corpus probe: 312 of 3,800 flights depart, 302 of
them recover this way). A flight that departs and cannot be recovered is
nodata, never judged on the junk.

`measure(ctx, element, name, derived)` returns (value, source): the SI value
and the step that produced it ("IfcDoor.OverallHeight",
"Pset_StairFlightCommon.RiserHeight", "geom:z_extent", "derived"), or
(None, None) when the chain is exhausted. Kinds: length (x length scale),
area, volume, angle_deg (project angle -> degrees), percent_from_angle
(project angle -> rise/run x 100), count, ratio, enum (string, unscaled).
A geometry step's value is already SI (metres, m2, m3, or degrees for
`flight_pitch`) and is returned as is.

A DERIVED measure is an arithmetic expression over primitive names, declared
in a rule's binding (`derived: {flight.step_length: "2*flight.riser +
flight.tread"}`): evaluated with Python's ast over + - * / and parentheses
only; any None input makes it None. A quantity that only one K-rule needs
is therefore config, not code.

Geometry primitives live in geometry.py (world or element frame, cached
shapes); `flight_pitch` stays here because it reads the riser/tread chain.
"""

import ast
import math

import ifcopenshell.util.element
import ifcopenshell.util.selector

from . import facts, geometry

# Values a numeric primitive treats as "not declared" unless its entry says otherwise.
DEFAULT_UNSET = (0,)
# Flight trust (module docstring): the declared rise may exceed the body's rise by this share ...
CORROBORATE_TOL = 0.25
# ... after this many risers of slack: a run's body stops one or two risers short of its count (the
# top riser belongs to the landing; corpus 0159: 5 risers of 0.15 m on a 0.50 m body are sound).
RISER_SLACK = 2
# The count derived from the body must be this close to a whole number.
COUNT_ROUND_TOL = 0.1
# A corroborated chain step's answer when the declared values are rejected and nothing replaces them.
REJECTED = object()


# ---- geometry primitives (geometry.py) plus the one that reads a chain ----

def geom_flight_pitch(ctx, element):
    """Pitch in degrees from the flight's own riser and tread chain."""
    riser, _ = primitive(ctx, element, "flight.riser")
    tread, _ = primitive(ctx, element, "flight.tread")
    if riser is None or tread is None or tread <= 0:
        return None
    return math.degrees(math.atan2(riser, tread))


GEOMETRY = dict(geometry.GEOMETRY, flight_pitch=geom_flight_pitch)

# ---- primitives: name -> (kind, chain) ----

PRIMITIVES = {
    # OverallHeight/OverallWidth are the opening's overall size, not the
    # clear passage (frame not deducted); the names say so, the cards'
    # clear-dimension thresholds are applied to them with that caveat.
    "door.overall_height": ("length", (("attr", "OverallHeight"), ("qto", "Height"))),
    "door.overall_width": ("length", (("attr", "OverallWidth"), ("qto", "Width"))),
    # Clear passage (2026-10-20, corpus probe: a declared clear-passage property on 708 doors of 26
    # corpus models, Revit DE "Durchgangsbreite/-höhe", ArchiCAD "Architekturlichte"; Qto_DoorBaseQuantities
    # is the opening, never the clear passage) with the overall size as the visible fallback.
    "door.clear_height": ("length", (("prop", "Durchgangshöhe"), ("prop", "Durchgangslichte Höhe"), ("qto", "Architekturlichte Höhe"),
                                     ("prop", "Architekturlichte Höhe"), ("prop", "ClearHeight"), ("attr", "OverallHeight"), ("qto", "Height"))),
    "door.clear_width": ("length", (("prop", "Durchgangsbreite"), ("prop", "Durchgangslichte Breite"), ("qto", "Architekturlichte Breite"),
                                    ("prop", "Architekturlichte Breite"), ("prop", "ClearWidth"), ("attr", "OverallWidth"), ("qto", "Width"))),
    "door.operation": ("enum", (("attr", "OperationType"), ("type_attr", "OperationType"))),
    "window.width": ("length", (("attr", "OverallWidth"), ("qto", "Width"))),
    "window.height": ("length", (("attr", "OverallHeight"), ("qto", "Height"))),
    "window.sill_height": ("length", (("geom", "sill_height"),)),
    "flight.riser": ("length", (("corroborated", "riser"), ("attr", "RiserHeight"), ("pset", "Pset_StairFlightCommon", "RiserHeight"),
                                ("prop", "RiserHeight"), ("parent_pset", "Pset_StairCommon", "RiserHeight"))),
    "flight.tread": ("length", (("corroborated", "tread"), ("attr", "TreadLength"), ("pset", "Pset_StairFlightCommon", "TreadLength"),
                                ("prop", "TreadLength"), ("parent_pset", "Pset_StairCommon", "TreadLength"))),
    "flight.pitch_deg": ("angle_deg_ready", (("geom", "flight_pitch"),)),
    "flight.turn_deg": ("angle_deg_ready", (("geom", "walk_turn"),)),
    "stair.turn_deg": ("angle_deg_ready", (("geom", "walk_turn"),)),
    # Usable run width: no IFC4 attribute or Pset carries it (WalkingLineOffset
    # is an offset, and Revit writes it in feet); geometry only.
    "flight.width": ("length", (("geom", "flight_width"),)),
    "flight.risers": ("count", (("corroborated", "risers"), ("attr", "NumberOfRisers"), ("pset", "Pset_StairFlightCommon", "NumberOfRiser"),
                                ("prop", "NumberOfRisers"), ("prop", "NumberOfRiser"), ("parent_pset", "Pset_StairCommon", "NumberOfRiser"))),
    # No geometry step: 322 of 370 corpus models carry the Pset, the z-extent
    # of a baluster railing cost up to 0.1 s per railing (6 s on one model).
    "railing.height": ("length", (("pset", "Pset_RailingCommon", "Height"), ("prop", "Height"))),
    "ramp.slope_percent": ("slope_percent", (("pset", "Pset_RampFlightCommon", "Slope"), ("prop", "Slope"))),  # IfcPlaneAngleMeasure, as roof.slope_percent
    "roof.pitch_deg": ("angle_deg", (("pset", "Pset_SlabCommon", "PitchAngle"), ("pset", "Pset_RoofCommon", "PitchAngle"), ("prop", "PitchAngle"), ("geom", "roof_pitch"))),
    "roof.slope_percent": ("slope_percent", (("pset", "Pset_SlabCommon", "PitchAngle"), ("pset", "Pset_RoofCommon", "PitchAngle"), ("prop", "PitchAngle"), ("geom", "roof_pitch"))),
    "space.area": ("area", (("qto", "NetFloorArea"), ("qto", "GrossFloorArea"), ("geom", "footprint_area"))),
    "space.height": ("length", (("qto", "FinishCeilingHeight"), ("qto", "Height"), ("qto", "NetHeight"), ("geom", "z_extent"))),
    "space.volume": ("volume", (("qto", "NetVolume"), ("qto", "GrossVolume"), ("geom", "volume"))),
    "space.width": ("length", (("geom", "obb_short"),)),
    "space.depth": ("length", (("geom", "obb_long"),)),
    "space.occupancy": ("count", (("pset", "Pset_SpaceOccupancyRequirements", "OccupancyNumber"), ("prop", "OccupancyNumber"), ("prop", "OccupancyNumberPeak"))),
    "space.glazed_area": ("area", (("geom", "glazed_area"),)),
    # Desks per room (facts.workstations); the card's own fallback is the
    # occupancy property (K141: "count(desks) or sum OccupancyNumber").
    "space.workstations": ("count", (("fact", "workstations"), ("pset", "Pset_SpaceOccupancyRequirements", "OccupancyNumber"), ("prop", "OccupancyNumber"))),
    # Seating furniture per room (K129's seats per seminar room): a room
    # without a seat is 0, so an area-per-seat expression gives None there.
    "space.seats": ("count", (("fact", "seats"),)),
    "storey.height": ("length", (("qto", "GrossHeight"), ("qto", "NetHeight"), ("geom", "storey_height"))),
    "storey.elevation": ("length", (("geom", "storey_elevation"),)),
    # Storeys holding an inferred dwelling, read on the IfcBuilding (K83's gate).
    "building.dwelling_storeys": ("count", (("fact", "dwelling_storeys"),)),
    "building.dwelling_count": ("count", (("fact", "dwelling_count"),)),
    "building.top_storey_rise": ("length", (("fact", "top_storey_rise"),)),
    "element.building_dwellings": ("count", (("fact_building", "dwelling_count"),)),
    # Vertical cores (cores.py): read on an IfcStair, on a storey, or on any
    # element through its storey.
    "stair.core_storeys": ("count", (("fact", "stair_core_storeys"),)),
    "stair.core_flats_per_floor": ("count", (("fact", "stair_core_flats_per_floor"),)),
    "stair.core_has_lift": ("count", (("fact", "stair_core_has_lift"),)),
    "storey.stair_cores": ("count", (("fact", "storey_stair_cores"),)),
    "storey.lift_cores": ("count", (("fact", "storey_lift_cores"),)),
    "element.storey_lift_cores": ("count", (("fact_storey", "storey_lift_cores"),)),
    "element.storey_stair_cores": ("count", (("fact_storey", "storey_stair_cores"),)),
    # Any element's own geometry (2026-10-19, util.shape): extents in its
    # own frame (a wall's thickness and length, a flight's width and run),
    # face and side areas, and the world-frame footprint and perimeter. A
    # card names them through a derived measure or a check on any class.
    "element.storey_rise": ("length", (("geom", "storey_rise"),)),
    "element.local_short": ("length", (("geom", "local_short"),)),
    "element.local_long": ("length", (("geom", "local_long"),)),
    "element.z_extent": ("length", (("geom", "z_extent"),)),
    "element.max_side_area": ("area", (("geom", "max_side_area"),)),
    "element.outer_surface_area": ("area", (("geom", "outer_surface_area"),)),
    "element.footprint_area": ("area", (("geom", "footprint_area"),)),
    "element.footprint_perimeter": ("length", (("geom", "footprint_perimeter"),)),
    "element.volume": ("volume", (("geom", "volume"),)),
}


# Per-primitive "not declared" values; every numeric primitive not listed
# uses DEFAULT_UNSET. A geometry step is never subject to this.
UNSET = {
    "space.occupancy": (),          # an occupancy of 0 is a statement
    "flight.risers": (),
    "space.workstations": (),       # a room without a desk holds 0 workstations
    "space.seats": (),              # a room without a seat holds 0; a division by it is nodata
    "building.dwelling_storeys": (), "building.dwelling_count": (), "element.building_dwellings": (),
    "building.top_storey_rise": (), "element.storey_rise": (),   # a rise of 0 is a measurement (the ground storey)
    "stair.core_storeys": (), "stair.core_flats_per_floor": (), "stair.core_has_lift": (),
    "storey.stair_cores": (), "storey.lift_cores": (), "element.storey_lift_cores": (), "element.storey_stair_cores": (),
}


def _qto(ctx, element, name):
    for quantities in ctx.qtos(element).values():
        value = quantities.get(name)
        if value is not None:
            return value
    return None


def _scale(ctx, kind, value):
    if kind == "length":
        return float(value) * ctx.length_scale
    if kind == "area":
        return float(value) * ctx.area_scale
    if kind == "volume":
        return float(value) * ctx.volume_scale
    if kind == "angle_deg":
        return math.degrees(float(value) * ctx.angle_scale)
    if kind == "slope_percent":
        return math.tan(float(value) * ctx.angle_scale) * 100.0
    if kind in ("count", "ratio"):
        return float(value)
    return value


def _storey_height(ctx, storey):
    ordered = ctx.storeys_sorted
    for below, above in zip(ordered, ordered[1:]):
        if below.GlobalId == storey.GlobalId:
            return (above.Elevation - below.Elevation) * ctx.length_scale
    return None


def _read_attr(ctx, element, step):
    return getattr(element, step[1], None), f"{element.is_a()}.{step[1]}"


def _read_type_attr(ctx, element, step):
    element_type = ifcopenshell.util.element.get_type(element)
    if element_type is None:
        return None, None
    return getattr(element_type, step[1], None), f"{element_type.is_a()}.{step[1]}"


def _read_pset(ctx, element, step):
    return ctx.pset_value(element, step[1], step[2]), f"{step[1]}.{step[2]}"


def _read_qto(ctx, element, step):
    return _qto(ctx, element, step[1]), f"Qto.{step[1]}"


def _read_prop(ctx, element, step):
    return ctx.property_value(element, (step[1],)), f"prop:{step[1]}"


def _read_parent_pset(ctx, element, step):
    """The named property set on the element's aggregate parent."""
    parent = ifcopenshell.util.element.get_aggregate(element)
    if parent is None:
        return None, None
    return ctx.pset_value(parent, step[1], step[2]), f"{step[1]}.{step[2]} (parent {parent.is_a()})"


def _flight_trust(ctx, element):
    """None when the flight's declared values stand; else the verdict dict
    (module docstring): "riser"/"tread"/"risers" from the parent and the
    body (None each when unrecoverable) and "rejected", the reason."""
    table = ctx.fact("flight_trust", lambda _ctx: {})
    guid = element.GlobalId
    if guid in table:
        return table[guid]
    verdict = None
    riser, _source = _walk(ctx, element, "flight.riser", skip=("corroborated", "parent_pset"))
    count, _source = _walk(ctx, element, "flight.risers", skip=("corroborated", "parent_pset"))
    rise = geometry.geom_z_extent(ctx, element)
    if riser and count and rise and riser * (count - RISER_SLACK) > (1 + CORROBORATE_TOL) * rise:
        rejected = f"declared riser {riser:.3f} m x {count:g} risers exceeds the body's {rise:.2f} m rise"
        verdict = {"riser": None, "tread": None, "risers": None, "rejected": rejected, "source": None}
        parent_riser, source = _read_parent_pset(ctx, element, ("parent_pset", "Pset_StairCommon", "RiserHeight"))
        parent_tread, _source = _read_parent_pset(ctx, element, ("parent_pset", "Pset_StairCommon", "TreadLength"))
        if parent_riser:
            parent_riser = _scale(ctx, "length", parent_riser)
            risers = _parent_count_per_flight(ctx, element)
            derived = rise / parent_riser if parent_riser > 0 else 0
            if risers is not None and abs(risers * parent_riser - rise) > CORROBORATE_TOL * rise + RISER_SLACK * parent_riser:
                risers = None  # the parent's count over its flights does not fit this body either
            if risers is None and abs(derived - round(derived)) <= COUNT_ROUND_TOL and round(derived) >= 1:
                risers = float(round(derived))
            if risers is not None:
                verdict.update({"riser": parent_riser, "tread": _scale(ctx, "length", parent_tread) if parent_tread else None,
                                "risers": risers, "source": f"{source} + geometry ({rejected})"})
    table[guid] = verdict
    return verdict


def _parent_count_per_flight(ctx, element):
    """The parent stair's NumberOfRiser shared equally by its flights, when
    that is a whole number (the Digital Hub: 18 risers over two runs of 9);
    else None and the count comes from the body."""
    parent = ifcopenshell.util.element.get_aggregate(element)
    total, _source = _read_parent_pset(ctx, element, ("parent_pset", "Pset_StairCommon", "NumberOfRiser"))
    if parent is None or not total:
        return None
    flights = [p for p in ifcopenshell.util.element.get_decomposition(parent) if p.is_a("IfcStairFlight")]
    if not flights or float(total) % len(flights):
        return None
    return float(total) / len(flights)


def _read_corroborated(ctx, element, step):
    verdict = _flight_trust(ctx, element)
    if verdict is None:
        return None, None
    value = verdict.get(step[1])
    if value is None:
        return REJECTED, f"rejected: {verdict['rejected']}"
    return value, verdict["source"]


# Per-room facts a chain step may read; the fact returns {guid: value} or None.
FACTS = {"workstations": facts.workstations, "seats": facts.seats, "dwelling_storeys": facts.dwelling_storeys, "dwelling_count": facts.dwelling_count,
         "top_storey_rise": facts.top_storey_rise,
         "stair_core_storeys": facts.stair_core_storeys, "stair_core_flats_per_floor": facts.stair_core_flats_per_floor,
         "stair_core_has_lift": facts.stair_core_has_lift, "storey_stair_cores": facts.storey_stair_cores,
         "storey_lift_cores": facts.storey_lift_cores}


def _read_value(ctx, element, step):
    """An ifcopenshell.util.selector value path, raw project units like a pset."""
    try:
        return ifcopenshell.util.selector.get_element_value(element, step[1]), f"value:{step[1]}"
    except Exception:  # noqa: BLE001 - a path that does not resolve on this element
        return None, f"value:{step[1]}"


def _read_fact(ctx, element, step):
    table = ctx.fact(step[1], FACTS[step[1]])
    return (None if table is None else table.get(element.GlobalId)), f"fact:{step[1]}"


def _read_fact_storey(ctx, element, step):
    """A per-storey fact read through the element's storey."""
    storey = ctx.storey_of(element)
    table = ctx.fact(step[1], FACTS[step[1]])
    if storey is None or table is None:
        return None, f"fact:{step[1]}"
    return table.get(storey.GlobalId), f"fact:{step[1]}"


def _read_fact_building(ctx, element, step):
    """A per-building fact read through the element's building."""
    table = ctx.fact(step[1], FACTS[step[1]])
    if table is None:
        return None, f"fact:{step[1]}"
    building = element if element.is_a("IfcBuilding") else None
    if building is None:
        storey = ctx.storey_of(element)
        parent = ifcopenshell.util.element.get_aggregate(storey) if storey is not None else None
        if parent is not None and parent.GlobalId in table:
            building = parent
    if building is None:
        buildings = ctx.model.by_type("IfcBuilding")
        building = buildings[0] if len(buildings) == 1 else None
    return (None if building is None else table.get(building.GlobalId)), f"fact:{step[1]}"


def _read_geom(ctx, element, step):
    raw = _storey_height(ctx, element) if step[1] == "storey_height" else GEOMETRY[step[1]](ctx, element)
    return raw, f"geom:{step[1]}"


# One reader per chain step kind; `primitive` only walks the chain.
READERS = {"attr": _read_attr, "type_attr": _read_type_attr, "pset": _read_pset,
           "qto": _read_qto, "prop": _read_prop, "geom": _read_geom, "fact": _read_fact, "fact_storey": _read_fact_storey,
           "value": _read_value, "parent_pset": _read_parent_pset, "corroborated": _read_corroborated,
           "fact_building": _read_fact_building}
# Steps whose value is already SI and whose zero is a measurement.
MEASURED_STEPS = ("geom", "corroborated")


def _declared(name, kind, value):
    """False for NaN and for the primitive's `unset` values (a declared 0
    that means "not set"); enum values are always declared."""
    if kind == "enum":
        return True
    if isinstance(value, float) and math.isnan(value):
        return False
    return not any(abs(value - unset) < 1e-9 for unset in UNSET.get(name, DEFAULT_UNSET))


def primitive(ctx, element, name):
    return _walk(ctx, element, name)


def _walk(ctx, element, name, skip=()):
    """The chain of `name` without the step kinds in `skip`."""
    kind, chain = PRIMITIVES[name]
    for step in chain:
        if step[0] in skip:
            continue
        raw, source = READERS[step[0]](ctx, element, step)
        if raw is REJECTED:
            return None, source
        if raw is None or raw == "":
            continue
        if step[0] in MEASURED_STEPS:
            # Geometry is already SI (metres, m2, m3, degrees for a pitch)
            # and a measured zero is a measurement, not a default.
            if isinstance(raw, float) and math.isnan(raw):
                continue
            return float(raw), source
        try:
            value = _scale(ctx, kind, raw)
        except (TypeError, ValueError):
            continue
        if not _declared(name, kind, value):
            continue  # declared but not set: the chain goes on
        return value, source
    return None, None


# ---- derived expressions ----

_ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div)


def _names_in(expression):
    """The measure names an expression reads: dotted attribute chains and
    bare names, with every other node type rejected."""
    tree = ast.parse(expression, mode="eval")
    names = set()

    def visit(node):
        if isinstance(node, ast.Expression):
            visit(node.body)
        elif isinstance(node, ast.Attribute):
            names.add(_dotted(node))
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Constant):
            if not isinstance(node.value, (int, float)):
                raise ValueError(f"expression {expression!r}: constant {node.value!r} not allowed")
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            visit(node.operand)
        elif isinstance(node, ast.BinOp) and isinstance(node.op, _ALLOWED_BINOPS):
            visit(node.left)
            visit(node.right)
        else:
            raise ValueError(f"expression {expression!r}: {type(node).__name__} not allowed")

    visit(tree)
    return names


def _dotted(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        raise ValueError("attribute chain must start with a name")
    parts.append(node.id)
    return ".".join(reversed(parts))


def validate_expression(name, expression, derived):
    for ref in _names_in(expression):
        if ref not in PRIMITIVES and (ref not in derived or ref == name):
            raise ValueError(f"derived {name!r}: {ref!r} is not a primitive or another derived measure")


def _evaluate(node, values):
    if isinstance(node, ast.Expression):
        return _evaluate(node.body, values)
    if isinstance(node, ast.Constant):
        return float(node.value)
    if isinstance(node, (ast.Attribute, ast.Name)):
        value = values[_dotted(node) if isinstance(node, ast.Attribute) else node.id]
        if value is None:
            raise _Missing()
        return float(value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_evaluate(node.operand, values)
    if isinstance(node, ast.BinOp):
        left, right = _evaluate(node.left, values), _evaluate(node.right, values)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            if right == 0:
                raise _Missing()
            return left / right
    raise ValueError(f"unsupported expression node {type(node).__name__}")


class _Missing(Exception):
    pass


def measure(ctx, element, name, derived=None):
    """(value, source) for a primitive or derived measure; (None, None) when
    any input of the chain is missing."""
    derived = derived or {}
    if name in PRIMITIVES:
        return primitive(ctx, element, name)
    expression = derived[name]
    values = {}
    for ref in _names_in(expression):
        value, _ = measure(ctx, element, ref, derived)
        values[ref] = value
    try:
        return _evaluate(ast.parse(expression, mode="eval"), values), "derived"
    except _Missing:
        return None, None
