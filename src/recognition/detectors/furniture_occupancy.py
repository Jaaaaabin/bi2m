"""Room occupancy from furniture: seating and sleeping furniture assigned to
the room it stands in, aggregated per storey into how many people the
modeled furniture actually accommodates.

Opens a "functional" domain - the programmatic/occupancy question, a
content domain absent from registry.py's four. It also answers a specific
tier-4 intent nothing in this package could touch:
"this room holds 40 occupants".

Closes the largest remaining zero-coverage element family. IfcFurniture was
0 of 2324 covered corpus-wide and IfcSystemFurnitureElement 0 of 96 -
together the biggest untouched block after
IfcBuildingElementProxy, and unlike proxies these carry real, legible
meaning.

Why furniture is a genuine intent signal rather than decoration. It is an
INDEPENDENT statement of what a room is for, authored separately from the
room's own name, which makes it the package's first chance to corroborate
one declared signal against another. What the corpus holds, all of it
consistent and none of it noise:
  - data/test_2.ifc: 680 Breuer chairs, 252 desk chairs, 252
    rectangular tables, 98 round dining tables, 3 shelving units. The
    matched 252/252 desk-chair-to-table pairing is a workstation count,
    not a coincidence.
  - data/test_6.ifc: 234 chairs, 98 rectangular tables, 95 sofa sets, 40
    chair layouts, 10 digital boards - a meeting/teaching program.
  - data/test_5.ifc: 72 beds (48 box + 24 standard), 84 sofas, 168 storage
    cabinets, 24 TV stands, 24 counter-tops with sink holes. 24 beds of one
    type across exactly the 24 apartments unit_typology.py independently
    recovered from the access graph - two unrelated mechanisms agreeing on
    the same unit count is the strongest cross-validation in this package.
  - data/test_4.ifc: 176 "Chair-Executive" among 2071 IfcBuildingElementProxy
    - the same furnishing intent, carried by a different IFC class. See
    FURNITURE_CLASSES below.

Assignment is nearest-room, the same rule daylight_rooms.py uses and for
the same reason, but the geometry here is easier: furniture stands INSIDE
a room rather than in the wall between two, so the great majority resolve
at distance 0.0 (true containment) and DEFAULT_FURNITURE_REACH_M only has
to absorb a piece pushed slightly through a wall face.

Counting is by NAME KEYWORD, and that is the honest weak point. Whether a
piece seats someone is read from its own name/type string (chair, seat,
stool, sofa, couch, bench, bed), the same naming-convention dependence
circulation_horizontal.py and unit_typology.py already carry - it works on
all three corpus models because all three use descriptive Revit family
names, and it would yield nothing on a model whose furniture is named
"FU-003". data/test_6.ifc is exactly that case at the instance level ("FU -
003") and is rescued only because its TYPE names are descriptive ("Chair 10
27"), which is why both the instance name and the type name are checked.

Counts reconcile exactly against the raw models, which is the check that
caught the one real bug here: IfcFurniture and IfcSystemFurnitureElement
are both subtypes of IfcFurnishingElement, so an unguarded by_type() sweep
returns every element twice and doubles every figure. After de-duplicating
by GUID, data/test_5.ifc totals 72 beds against the 48 M_Bed-Box + 24
M_Bed-Standard it actually contains, and data/test_2.ifc totals 1030
seats against its 680 Breuer chairs + 252 desk chairs + 98 dining sets.

One known over-count survives that reconciliation and is left in
deliberately: data/test_2.ifc's "M_Table-Dining Round w Chairs" is a
SINGLE object whose name contains "chairs", so it scores one seat where it
depicts several. Counting it as seating is right - it is seating furniture -
but the figure is one place per object, so a model using
composite table-and-chair families under-counts. A per-family seat
multiplier would fix it and is not attempted; the raw object count is at
least transparent about what it measured.

An occupancy count is a FLOOR, not a capacity: it says how many seats were
modeled, not how many people a room may legally hold. Real occupancy
capacity is an area-per-person calculation against a code table - the
separate [[bim-compliance]] layer - and this detector
deliberately does not pretend to it. Sleeping and seating are counted
separately (`beds` vs `seats`) because conflating them would make a
bedroom read as a lounge.
"""

from ifc_units import length_scale

from ..access_graph import space_label, space_polygons
from ..census import elements_by_guid
from ..furnishing import DEFAULT_FURNITURE_REACH_M, FURNITURE_CLASSES, room_contents
from ..intent import make_member, make_intent
from ..spaces import index_by_storey

# IfcBuildingElementProxy is in this list deliberately, and it is the one
# entry that needs justifying. It is the IFC dumping ground - it can hold
# anything - but in this corpus it is where one authoring tool put its
# FURNITURE: data/test_4.ifc exports 2071 proxies whose own names are
# "Chair-Executive" (176), "Furniture_System-Standing_Desk-L_w" (224),
# "Monitor" (224), "Furniture_System-Partition-Privacy" (176). The same
# design intent - how this room is furnished, and therefore how many people
# work in it - is simply carried by a different IFC class than the one
# data/test_5.ifc and data/test_2.ifc use. Including proxies is safe
# precisely because furnishing.classify() is a keyword allow-list: a proxy is
# counted only if it names itself as seating, so the 224 monitors and the
# privacy partitions are read and then ignored, exactly as they should be.
# FURNITURE_CLASSES, the classifier (sleeping first: a "bed" never doubles
# as seating; family segments of the instance and type names, since
# data/test_4.ifc exported 50 WCs as 'Toilet-Commercial-Wall-3D:15" Seat
# Height:129088') and the nearest-room assignment live in
# recognition/furnishing.py since 2026-10-18, shared with the Neufert
# workstations fact; the seating and sleeping words in vocabulary.py since
# 2026-10-08. FURNITURE_CLASSES stays importable from here (preflight).
KINDS = ("bed", "seat")
DEFAULT_MIN_ROOMS = 2
DEFAULT_MIN_OCCUPANCY = 1


def detect(model, extracted, file_key,
           furniture_reach_m=DEFAULT_FURNITURE_REACH_M,
           min_rooms=DEFAULT_MIN_ROOMS, min_occupancy=DEFAULT_MIN_OCCUPANCY):
    spaces = model.by_type("IfcSpace")
    if not spaces:
        return []

    # De-duplicated by GUID: IfcFurniture and IfcSystemFurnitureElement are
    # both subtypes of IfcFurnishingElement in IFC4, so by_type() returns
    # each element under more than one of these names. Left unguarded this
    # doubles every count (confirmed on data/test_5.ifc: 144 beds reported
    # against the 72 the file actually contains).
    furniture = list(elements_by_guid(model, FURNITURE_CLASSES).values())
    if not furniture:
        return []

    polygons = space_polygons(model, spaces)
    if not polygons:
        return []

    space_by_guid = {space.GlobalId: space for space in spaces}
    spaces_by_storey = index_by_storey(spaces, polygons)

    # Furniture placements in metres, like the footprints (docs/detectors.md rule 13).
    # space guid -> {"seat"/"bed": [guids]}, nearest room within the reach.
    contents = room_contents(furniture, KINDS, polygons, spaces_by_storey, furniture_reach_m, length_scale(model))

    intents = []
    for storey_guid, storey_spaces in spaces_by_storey.items():
        storey = model.by_guid(storey_guid)
        storey_name = storey.Name if storey and storey.Name else storey_guid

        rooms = []
        for guid in storey_spaces:
            entry = contents.get(guid)
            if not entry:
                continue
            seats, beds = len(entry.get("seat", [])), len(entry.get("bed", []))
            if seats + beds < min_occupancy:
                continue
            rooms.append((guid, seats, beds, polygons[guid].area))
        if len(rooms) < min_rooms:
            continue

        rooms.sort(key=lambda r: -(r[1] + r[2]))
        total_seats = sum(r[1] for r in rooms)
        total_beds = sum(r[2] for r in rooms)
        furniture_guids = sorted({
            guid
            for room_guid, _, _, _ in rooms
            for kind_guids in contents[room_guid].values()
            for guid in kind_guids
        })
        detail = ", ".join(
            f"{space_label(space_by_guid[guid])} "
            f"{'+'.join(filter(None, [f'{seats} seats' if seats else '', f'{beds} beds' if beds else '']))}"
            for guid, seats, beds, _ in rooms[:6]
        )

        intents.append(make_intent(
            intent_id=f"{file_key}-occupancy-{storey_guid}",
            intent_type="furniture_occupancy",
            label=(
                f"Furnished occupancy ({storey_name}, "
                + ", ".join(filter(None, [
                    f"{total_seats} seats" if total_seats else "",
                    f"{total_beds} beds" if total_beds else "",
                ]))
                + f" across {len(rooms)} rooms)"
            ),
            members=[
                make_member(guid, ifc_class="IfcSpace") for guid, _, _, _ in rooms
            ] + [
                make_member(guid, role="context", ifc_class=model.by_guid(guid).is_a())
                for guid in furniture_guids
            ],
            detector="furniture_occupancy",
            rule="furniture_seating_count",
            summary=(
                f"{len(rooms)} rooms on storey {storey_name} contain modeled "
                f"seating or sleeping furniture totalling {total_seats} seats"
                + (f" and {total_beds} beds" if total_beds else "")
                + f". This is how many places were MODELED, not a code occupancy "
                  f"capacity. Furniture assigned to its nearest room within "
                  f"{furniture_reach_m}m. {detail}"
                + (f" and {len(rooms) - 6} more." if len(rooms) > 6 else ".")
            ),
            related_guids=[storey_guid],
            metrics={
                "storey": storey_name,
                "roomCount": len(rooms),
                "seats": total_seats,
                "beds": total_beds,
                "furnitureCounted": len(furniture_guids),
                "maxSeatsInOneRoom": max((r[1] for r in rooms), default=0),
                "seatsPerRoomMean": round(total_seats / len(rooms), 2),
                "furnitureReachM": furniture_reach_m,
            },
        ))

    return intents
