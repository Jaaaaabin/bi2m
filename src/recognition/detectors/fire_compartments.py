"""Fire compartments: the rooms you can move between WITHOUT passing
through a fire-rated door - i.e. the connected components of a storey's
access graph once every rated door is removed - together with the rated
doors that form each compartment's boundary.

Opens a "regulatory" domain, the last of the four content domains
recorded as missing (`functional`, `environmental`, `services` and `constructional` were
opened by the other categories added on this branch; only `aesthetic`
remains).

This is the clearest payoff so far from having built an access graph. A fire
compartment is definitionally a REACHABILITY question - what can a fire
spread to before it meets a rated barrier - and before space_access.py there
was no adjacency structure in this package to ask it against. Here the graph
is simply rebuilt with the rated doors deleted, and each remaining component
is a compartment. Nothing about this is expressible with coordinate
repetition, which is what the original nine detectors do.

Signal and its honest limit. `Pset_DoorCommon.FireRating` carries a real,
discriminating value in exactly ONE corpus model: data/test_3.ifc rates 90
of its 135 doors "1 hr", 24 explicitly "0" (present but unrated - correctly
treated as NOT a barrier) and leaves 21 unset. data/test_6.ifc has the
property on all 180 doors but empty on every one, and the remaining four
models omit it. So this is a one-model detector today, exactly the
limitation connection.py has - the difference is that it is declared here
rather than discovered later.

NO WALL is fire-rated anywhere in the corpus (`FireRating` is absent from
every IfcWall in all six models), which is a genuine and important weakness
of the result, not a detail. A real compartment boundary is a rated WALL
line with rated doors in it; this detector can only see the doors. The
compartments it reports are therefore an UPPER bound on containment derived
from door evidence alone - correct about where a rated door interrupts
movement, silent about whether the wall around that door resists fire at
all. A reviewer should read these as "candidate compartments suggested by
door ratings", which is why the category is `draft` and why every record
says so in its own summary.

Rating interpretation: any non-empty value that is not "0" counts as rated.
The corpus gives no basis for ordering ratings ("1 hr" is the only real
value present), so no attempt is made to treat a 30-minute door differently
from a 90-minute one; the rating string is carried through into the metrics
verbatim so a reviewer can see what it actually was.

Every door rated (2026-10-08). On
the corpus 86 of 92 eligible models produced nothing here, because a rating
exists but sits on every door that joins two rooms, so every room is its own
compartment and the two-room floor dropped them all. That is a
statement worth one record per storey, `fire_compartment_singletons`:
"every room on this storey is its own fire compartment", members the rooms,
the rated doors as related elements, with the same door-evidence caveat.
"""

from collections import Counter

import ifcopenshell.util.element

from ..access_graph import (
    DEFAULT_DOOR_MARGIN_M,
    AccessGraph,
    connected_groups,
    space_label,
)
from ..session import psets_of
from ..intent import make_member, make_intent

# Values that are present but mean "not a fire barrier".
UNRATED_VALUES = {"", "0", "0.0", "none", "no", "n/a"}
DEFAULT_MIN_ROOMS = 2


def _fire_rating(element):
    for pset in psets_of(element).values():  # the model session's memo (session.py)
        for key, value in pset.items():
            if key == "FireRating" and value is not None:
                text = str(value).strip()
                if text.lower() not in UNRATED_VALUES:
                    return text
    return None


def detect(model, extracted, file_key,
           door_margin_m=DEFAULT_DOOR_MARGIN_M, min_rooms=DEFAULT_MIN_ROOMS,
           graph=None):
    doors = model.by_type("IfcDoor")
    if not doors:
        return []

    ratings = {}
    for door in doors:
        rating = _fire_rating(door)
        if rating is not None:
            ratings[door.GlobalId] = rating
    if not ratings:
        return []

    graph = graph if graph is not None else AccessGraph(model, door_margin_m)
    if not graph.usable():
        return []

    intents = []
    for storey_guid, storey_spaces in graph.spaces_by_storey.items():
        if storey_guid in graph.degenerate_storeys:
            continue  # footprints overlap too much to tell rooms apart (2026-10-08)
        storey_name = graph.storey_name(storey_guid)

        # Edges from UNRATED doors only - a rated door is a barrier, so it
        # deliberately contributes no edge and therefore cannot merge two
        # compartments.
        edges = []
        boundary_doors = {}
        for door_guid, (door_storey, reached) in graph.door_links.items():
            if door_storey != storey_guid or len(reached) < 2:
                continue
            if door_guid in ratings:
                boundary_doors[door_guid] = reached
                continue
            for i in range(len(reached)):
                for j in range(i + 1, len(reached)):
                    edges.append(tuple(sorted((reached[i], reached[j]))))

        if not boundary_doors:
            continue

        all_compartments = connected_groups(storey_spaces, edges)
        compartments = [g for g in all_compartments if len(g) >= min_rooms]
        if not edges and not compartments:
            # No unrated door joins two rooms: every room is its own
            # compartment (see the module docstring). One record per storey
            # instead of the nothing this storey used to produce.
            unrated_here = sum(
                1 for door_guid, (door_storey, _reached) in graph.door_links.items()
                if door_storey == storey_guid and door_guid not in ratings
            )
            rating_counts = Counter(ratings[guid] for guid in boundary_doors)
            rating_text = ", ".join(f"{count}x {value}" for value, count in rating_counts.most_common())
            rooms = sorted(storey_spaces)
            intents.append(make_intent(
                intent_id=f"{file_key}-firesingletons-{storey_guid}",
                intent_type="fire_compartment_singletons",
                label=(
                    f"Every room on {storey_name} is its own fire compartment: "
                    f"{len(rooms)} rooms behind {len(boundary_doors)} rated doors"
                ),
                members=[make_member(guid, ifc_class="IfcSpace") for guid in rooms],
                detector="fire_compartments",
                rule="every_door_rated",
                summary=(
                    f"On {storey_name} every door that joins two rooms carries a FireRating ({rating_text}), "
                    f"so no two rooms share a compartment: {len(rooms)} single-room compartments behind "
                    f"{len(boundary_doors)} rated doors"
                    + (f"; {unrated_here} unrated door(s) reach one room only" if unrated_here else "")
                    + ". Door evidence only: no wall in this model carries a FireRating."
                ),
                related_guids=[storey_guid] + sorted(boundary_doors),
                metrics={
                    "storey": storey_name, "rooms": len(rooms), "ratedDoors": len(boundary_doors),
                    "ratings": dict(rating_counts), "unratedDoors": unrated_here,
                },
                polarity="positive",
            ))
            continue
        if not compartments:
            continue
        # Counted separately and reported, because in an office building
        # most rooms sit alone behind their own rated door: on every storey
        # of data/test_3.ifc the multi-room compartments are a small
        # minority of the real total. Reporting only the former as "the
        # compartments on this storey" would badly understate the
        # compartmentation.
        single_room = sum(1 for g in all_compartments if len(g) < min_rooms)

        rating_counts = Counter(ratings[guid] for guid in boundary_doors)
        rating_text = ", ".join(f"{count}x {value}" for value, count in rating_counts.most_common())

        for compartment in compartments:
            compartment_set = set(compartment)
            # Rated doors with a foot in this compartment bound it.
            own_boundary = sorted(
                door_guid for door_guid, reached in boundary_doors.items()
                if compartment_set.intersection(reached)
            )
            labels = [space_label(graph.space_by_guid[guid]) for guid in sorted(compartment)]

            intents.append(make_intent(
                intent_id=f"{file_key}-firecompartment-{sorted(compartment)[0]}",
                intent_type="fire_compartment",
                label=(
                    f"Fire compartment ({storey_name}, {len(compartment)} rooms, "
                    f"{len(own_boundary)} rated doors on its boundary)"
                ),
                members=[
                    make_member(guid, ifc_class="IfcSpace") for guid in sorted(compartment)
                ] + [
                    make_member(guid, role="context", ifc_class="IfcDoor")
                    for guid in own_boundary
                ],
                detector="fire_compartments",
                rule="unrated_door_reachability",
                summary=(
                    f"{len(compartment)} rooms on storey {storey_name} are mutually "
                    f"reachable WITHOUT passing a fire-rated door, bounded by "
                    f"{len(own_boundary)} rated door(s). This storey resolves into "
                    f"{len(all_compartments)} compartments in total, {single_room} of "
                    f"which are a single room behind its own rated door. Derived from door ratings "
                    f"alone - no IfcWall in this model carries a FireRating, so this "
                    f"is a candidate compartment, not a verified one. Rooms: "
                    f"{', '.join(labels[:8])}"
                    f"{f' and {len(labels) - 8} more' if len(labels) > 8 else ''}."
                ),
                related_guids=[storey_guid],
                metrics={
                    "storey": storey_name,
                    "roomCount": len(compartment),
                    "boundaryDoorCount": len(own_boundary),
                    "ratedDoorsOnStorey": len(boundary_doors),
                    "compartmentsOnStorey": len(all_compartments),
                    "multiRoomCompartments": len(compartments),
                    "singleRoomCompartments": single_room,
                    "ratings": rating_text,
                    "wallRatingsAvailable": False,
                    "doorMarginM": door_margin_m,
                },
            ))

    return intents
