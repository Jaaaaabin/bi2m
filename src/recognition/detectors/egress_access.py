"""Building access points: IfcDoor instances the model declares external
(`Pset_DoorCommon.IsExternal = True`), grouped one intent per storey -
where you can actually enter or leave the building at each level - with each
door's hosting wall resolved through the model's own opening relations.

The first detector anywhere in this package to treat IfcDoor as a SUBJECT.
Doors were 19 of 920 covered corpus-wide before this module and 83 of 920
after thermal_envelope.py, and in circulation.py they
appear only as *evidence* that some stair's enclosing space has a declared
door - never as the thing being recognized. An exterior door is a
first-class design-intent object: it is the building's interface to the
outside, and where the egress questions start.

Signal, and why it is trustworthy: `IsExternal` on doors is present and
discriminating on 5 of the 6 corpus models - data/test_3.ifc 4 of 135 doors
external, data/test_2.ifc 40 of 86, data/test_4.ifc 9 of 111,
data/test_7.ifc 12 of 172, data/test_5.ifc 0 of 236 (the property is
present on all 236 and set False on all 236 - a model that genuinely
declares no external door, not a missing property). data/test_6.ifc leaves
it unset on all 180 doors and yields nothing here. Note this is a strictly
declared signal: a door is an entrance because the model says so, not
because geometry was inspected. That is the point - it is the cheap,
explicit rung that was under-used - but it also means a
mis-tagged export is invisible to this detector, which is exactly what the
validation panel is for.

Hosting wall, via IfcRelFillsElement -> IfcOpeningElement ->
IfcRelVoidsElement -> the wall. This is the package's second use of a
native IFC relation (connection.py's IfcRelSpaceBoundary was the first) and
a far more portable one: space boundaries exist in only ONE of the six
models (1032 in data/test_3.ifc, zero in the other five), whereas fill/void
relations are present in ALL SIX (110-362 each). The host wall is carried
as a `context` member rather than a `member` so a reviewer highlighting
this intent sees the doorway in its wall, while the intent's own subject
stays the set of doors.

Cross-check worth reading in the evidence: `hostExternalCount` reports how
many of the hosting walls are THEMSELVES tagged IsExternal. An exterior
door sitting in a wall the model calls internal is a genuine tagging
contradiction between two independently-authored properties - the kind of
inconsistency no geometric detector in this package can surface, and a
concrete thing for a human validator to rule on.
"""

from collections import Counter, defaultdict


from ..intent import make_member, make_intent
from ..properties import is_external
from ..room_routes import host_element as _host_element  # shared since 2026-10-18 (room_routes.py)
from ..storeys import get_storey

DEFAULT_MIN_MEMBERS = 1


def detect(model, extracted, file_key, min_members=DEFAULT_MIN_MEMBERS):
    try:
        doors = model.by_type("IfcDoor")
    except RuntimeError:
        return []
    if not doors:
        return []

    by_storey = defaultdict(list)
    for door in doors:
        if not is_external(door):
            continue
        storey = get_storey(door)
        if storey is not None:
            by_storey[storey.GlobalId].append(door)

    intents = []
    for storey_guid, external_doors in by_storey.items():
        if len(external_doors) < min_members:
            continue

        storey = model.by_guid(storey_guid)
        storey_name = storey.Name if storey and storey.Name else storey_guid

        hosts = {}
        for door in external_doors:
            host = _host_element(door)
            if host is not None:
                hosts[host.GlobalId] = host

        # Counted over the DISTINCT hosting walls, not per door - several
        # doors routinely share one wall, which would otherwise push the
        # count past len(hosts) and make `contradiction` below negative.
        host_external = sum(
            1 for host in hosts.values()
            if is_external(host)
        )
        host_classes = Counter(host.is_a() for host in hosts.values())
        contradiction = len(hosts) - host_external
        contradiction_note = (
            f" {contradiction} of {len(hosts)} hosting walls are NOT themselves "
            f"tagged external - a tagging contradiction worth review."
            if hosts and contradiction else ""
        )

        intents.append(make_intent(
            intent_id=f"{file_key}-access-{storey_guid}",
            intent_type="egress_external_access",
            label=f"External access points ({storey_name}, {len(external_doors)} doors)",
            members=(
                [make_member(door.GlobalId, ifc_class=door.is_a()) for door in external_doors]
                + [
                    make_member(guid, role="context", ifc_class=host.is_a())
                    for guid, host in sorted(hosts.items())
                ]
            ),
            detector="egress_access",
            rule="external_door_access_point",
            summary=(
                f"{len(external_doors)} IfcDoor instances on storey {storey_name} "
                f"are tagged IsExternal=True - the building's entry/exit points at "
                f"this level. {len(hosts)} hosting wall(s) resolved via "
                f"IfcRelFillsElement/IfcRelVoidsElement"
                f"{' (' + ', '.join(f'{n} {c}' for c, n in host_classes.most_common()) + ')' if host_classes else ''}."
                f"{contradiction_note}"
            ),
            related_guids=[storey_guid],
            metrics={
                "storey": storey_name,
                "externalDoorCount": len(external_doors),
                "hostsResolved": len(hosts),
                "hostExternalCount": host_external,
                "hostTaggingContradictions": contradiction,
            },
        ))

    return intents
