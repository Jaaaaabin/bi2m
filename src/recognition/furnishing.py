"""Furniture, classified and assigned to the room it stands in. Shared
since 2026-10-18 by `furniture_occupancy` (seats and beds per room) and
the Neufert `workstations` fact (desks per room); the extraction was
proven byte-identical on the 371-model corpus with the shard harness.

`classify(element, kinds)` reads the family segment of the instance and
type names (vocabulary.element_text) in a fixed order - sleeping, then
seating, then desk - and returns the first kind in `kinds` that matches,
or None. The order matters: "desk chair" names a seat, not a desk, and a
"bed" never doubles as seating (furniture_occupancy's rule). An IfcFurniture
whose PredefinedType is DESK counts as a desk when its names say nothing
(16 corpus models carry the type, 217 name their desks).

`room_contents(elements, kinds, polygons, by_storey, reach_m, scale)`
assigns each classified element to the nearest room footprint on its
storey within `reach_m` (nearest-wins, as daylight_rooms and
furniture_occupancy do; furniture stands inside its room so most resolve at
0.0 m) and returns {room guid: {kind: [element guids]}} in element order.
The caller chooses the footprints' frame: furniture_occupancy passes the
extraction-frame polygons it always used, the Neufert context its own
world-frame ones.
"""

from collections import defaultdict

import ifcopenshell.util.element
from shapely.geometry import Point

from ifc_units import placement_xy

from . import vocabulary
from .spaces import nearest_space

# IfcBuildingElementProxy is here deliberately: one authoring tool exports
# its furniture as proxies named "Chair-Executive" and
# "Furniture_System-Standing_Desk-L_w" (furniture_occupancy's reading).
# IfcFurniture and IfcSystemFurnitureElement are subtypes of
# IfcFurnishingElement; census.elements_by_guid de-duplicates the sweep.
FURNITURE_CLASSES = (
    "IfcFurniture", "IfcSystemFurnitureElement", "IfcFurnishingElement",
    "IfcBuildingElementProxy",
)
# (kind, vocabulary concept) in classification order.
KIND_CONCEPTS = (("bed", "sleeping"), ("seat", "seating"), ("desk", "desk"))
# PredefinedType values that name a kind when the names do not.
PREDEFINED_KINDS = {"DESK": "desk"}
# Furniture stands inside its room, so most resolve at 0.0 m; this only has
# to absorb a piece pushed slightly through a wall face.
DEFAULT_FURNITURE_REACH_M = 0.5


def classify(element, kinds):
    """The first kind in classification order that `element` names, when
    `kinds` asks for it (a "desk chair" is a seat, and is NOT a desk even
    to a caller that asks for desks only); else its DESK PredefinedType
    when the names say nothing; else None."""
    text = vocabulary.element_text(element)
    for kind, concept in KIND_CONCEPTS:
        if vocabulary.matches(text, concept):
            return kind if kind in kinds else None
    try:
        predefined = ifcopenshell.util.element.get_predefined_type(element)
    except Exception:  # noqa: BLE001 - a proxy without a type
        predefined = None
    kind = PREDEFINED_KINDS.get(str(predefined or "").upper())
    return kind if kind in kinds else None


def container_storey(element):
    return ifcopenshell.util.element.get_container(element, ifc_class="IfcBuildingStorey")


def room_contents(elements, kinds, polygons, by_storey, reach_m, scale, storey_of=container_storey):
    """{room guid: {kind: [element guids]}} for the elements of `kinds`
    within `reach_m` of a room footprint on their storey; element order.
    `storey_of(element)` names the storey (the spatial container unless
    the caller resolves it otherwise)."""
    contents = defaultdict(lambda: defaultdict(list))
    for element in elements:
        kind = classify(element, kinds)
        if kind is None:
            continue
        storey = storey_of(element)
        if storey is None:
            continue
        xy = placement_xy(element, scale)
        if xy is None:
            continue
        nearest, nearest_distance = nearest_space(Point(*xy), by_storey.get(storey.GlobalId, []), polygons)
        if nearest is None or nearest_distance > reach_m:
            continue
        contents[nearest][kind].append(element.GlobalId)
    return contents
