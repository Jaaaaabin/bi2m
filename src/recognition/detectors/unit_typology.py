"""Repeated spatial unit types: groups of mutually-reachable rooms whose
room PROGRAM - the multiset of what the rooms are called, ignoring their
numbers and their position - recurs elsewhere in the building. An apartment
type, an office suite, a ward, a hotel room pod.

Fills tier 3 (local motif / typology) of the granularity ladder, which
was empty, and it is the first detector here whose
subject is a TYPE rather than an instance. Every other category in this
package makes an existential claim ("these 45 beams share a span", "these
19 rooms are reachable"); this one makes a universally-quantified,
type-level claim ("this 8-room program occurs 24 times"), the quantifier
axis, previously unused.

Why it is not another coordinate-repetition detector. Seven of the nine
original categories bucket coordinates within a tolerance and chain them -
which means they can only recognize a repeat that sits
at the same place, or stacks directly above. vertical.py comes closest to
typology and is explicitly limited this way: it matches a space footprint's
POSITION, so an apartment repeated along a corridor is invisible to it.
Here the signature is positional-free: a unit is recognized by what it
CONTAINS and how it is CONNECTED, so the same program is found wherever it
sits, at any orientation, on any storey.

Mechanism: the door/space access graph (access_graph.py, shared with
space_access.py - see that module for the measured 0.4m door margin and why
the association is geometric rather than from IfcRelSpaceBoundary). Each
connected component of a storey's room graph is one candidate unit. Its
signature is the sorted multiset of its members' normalized names, so
"003 Living"/"078 Living" both reduce to "living" and two components match
when their programs match exactly - same rooms, same counts.

What the corpus shows, and why this was worth building: data/test_5.ifc's
access graph splits each of its 4 residential storeys into 7 components,
and 6 of those 7 are the SAME 8-room program every time - master bedroom,
living, kitchen, bedroom, 2x store, 2x toilet - with the 7th being a
19-room office/reception core containing the elevator. That is a mixed-use
block whose apartment type repeats 6 times per floor across 4 floors, and
none of the nine original detectors could state it. The units are
components rather than arbitrary room groups precisely because a real
apartment is bounded by where you can walk: each one connects internally
and reaches the corridor only through a front door the corridor side of
which is not modeled as a space.

Deliberate limits. The signature is lexical - it inherits exactly the
naming-convention dependence circulation_horizontal.py and vertical.py's
`critical` flag already carry, and a model whose rooms are unnamed or named
per-instance ("Room 1", "Room 2") yields nothing rather than false
positives. It is also program-only: two units with identical room lists but
mirrored or differently-shaped layouts are reported as the same type,
because this asks "same program", not "same geometry". A geometric
congruence check (are the two footprint sets actually congruent up to
rotation/reflection?) is the natural refinement and is not attempted here.
"""

import re
from collections import Counter, defaultdict

from ..access_graph import DEFAULT_DOOR_MARGIN_M, AccessGraph, space_label
from ..intent import make_member, make_intent

# A unit needs enough rooms to be a program rather than a pair. 3 keeps
# genuine small suites (e.g. office + toilet + store) while dropping the
# two-room fragments a corridor split leaves behind.
DEFAULT_MIN_ROOMS = 3
# A type needs at least two instances to BE a type.
DEFAULT_MIN_INSTANCES = 2

# Leading room number ("003 Living"), trailing instance number ("Office 2"),
# and any bracketed suffix - all instance identity, none of it program.
_LEADING_NUMBER = re.compile(r"^[\s\-_.]*\d+[\s\-_.]*")
_TRAILING_NUMBER = re.compile(r"[\s\-_.]*\d+\s*$")
_BRACKETED = re.compile(r"[\(\[].*?[\)\]]")


def _normalize_room(name):
    """"003 Living" -> "living"; "Office 2" -> "office"; "  MASTER  BEDROOM "
    -> "master bedroom". Returns "" for a name that is nothing but a number,
    which is then treated as unnamed."""
    text = _BRACKETED.sub(" ", name or "")
    text = _LEADING_NUMBER.sub("", text)
    text = _TRAILING_NUMBER.sub("", text)
    return " ".join(text.lower().split())


def _signature(space_guids, space_by_guid):
    """Sorted multiset of normalized room names, or None if too much of the
    unit is unnamed to characterize it."""
    names = [_normalize_room(space_label(space_by_guid[guid])) for guid in space_guids]
    named = [name for name in names if name]
    if len(named) < len(names) / 2:
        return None
    return tuple(sorted(named))


def _program_text(signature, limit=6):
    counts = Counter(signature)
    parts = [
        f"{count}x {name}" if count > 1 else name
        for name, count in counts.most_common(limit)
    ]
    if len(counts) > limit:
        parts.append(f"+{len(counts) - limit} more")
    return ", ".join(parts)


def detect(model, extracted, file_key,
           door_margin_m=DEFAULT_DOOR_MARGIN_M, min_rooms=DEFAULT_MIN_ROOMS,
           min_instances=DEFAULT_MIN_INSTANCES, graph=None):
    graph = graph if graph is not None else AccessGraph(model, door_margin_m)
    if not graph.usable():
        return []

    space_by_guid = graph.space_by_guid

    # signature -> [(storey guid, [space guids])]
    instances = defaultdict(list)
    for storey_guid in graph.spaces_by_storey:
        if storey_guid in graph.degenerate_storeys:
            continue  # footprints overlap too much to tell rooms apart (2026-10-08)
        groups, _ = graph.groups_for_storey(storey_guid)
        for group in groups:
            if len(group) < min_rooms:
                continue
            signature = _signature(group, space_by_guid)
            if signature is None:
                continue
            instances[signature].append((storey_guid, sorted(group)))

    intents = []
    for signature, occurrences in instances.items():
        if len(occurrences) < min_instances:
            continue

        storey_guids = [storey_guid for storey_guid, _ in occurrences]
        storey_names = sorted({graph.storey_name(guid) for guid in storey_guids})
        all_spaces = [guid for _, group in occurrences for guid in group]
        unit_doors = sorted({
            door_guid
            for _, group in occurrences
            for door_guid in graph.doors_within(group)
        })
        program = _program_text(signature)
        # Stable, content-derived id: the same program in the same model
        # keeps its id across re-runs regardless of iteration order.
        signature_key = re.sub(r"[^a-z0-9]+", "", "".join(signature))[:40]

        intents.append(make_intent(
            intent_id=f"{file_key}-unittype-{len(signature)}-{signature_key}",
            intent_type="unit_type_recurrence",
            label=(
                f"Repeated unit type x{len(occurrences)} "
                f"({len(signature)} rooms: {_program_text(signature, limit=3)})"
            ),
            members=[
                make_member(guid, ifc_class="IfcSpace") for guid in sorted(all_spaces)
            ] + [
                make_member(guid, role="context", ifc_class="IfcDoor")
                for guid in unit_doors
            ],
            detector="unit_typology",
            rule="room_program_recurrence",
            summary=(
                f"A {len(signature)}-room unit ({program}) occurs "
                f"{len(occurrences)} times across {len(set(storey_guids))} storey(s) "
                f"({', '.join(storey_names)}), each time as a self-contained group of "
                f"mutually reachable rooms. Matched on room program, not position - "
                f"instances may sit anywhere on their storey."
            ),
            related_guids=sorted(set(storey_guids)),
            metrics={
                "instanceCount": len(occurrences),
                "roomsPerUnit": len(signature),
                "program": list(signature),
                "storeys": storey_names,
                "storeyCount": len(set(storey_guids)),
                "totalSpaces": len(all_spaces),
                "doorMarginM": door_margin_m,
            },
        ))

    return intents
