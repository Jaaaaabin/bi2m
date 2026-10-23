"""Curtain-wall assemblies: each IfcCurtainWall together with the mullions
(IfcMember) and panels (IfcPlate) it is built from, plus how many other
assemblies in the same model share its exact composition - a repeated
facade module.

Opens a "constructional" domain - how the building is put together, its
modularity and repetition of manufactured assemblies. It is a content
domain that was absent from registry.py's set.

Closes by far the largest remaining coverage gap, and does it through a
native IFC relation rather than geometry. IfcMember was 4167 elements at
30.5% covered and IfcPlate 1867 at 26.4% (both only incidentally, via
thermal_envelope.py picking up the ones tagged IsExternal). Every single
one of them is aggregated into a curtain wall by IfcRelAggregates -
confirmed exactly across the corpus: data/test_7.ifc 4100 of 4100 members
and plates belong to its 35 curtain walls, data/test_4.ifc 1760 of 1844 to
its 13 (the other 84 belong to IfcStair, and are correctly left alone
here), data/test_2.ifc 44 of 44 to its 44, data/test_5.ifc 46 of 46
to its 46.

This matters disproportionately for the worst-covered model in the corpus.
data/test_7.ifc sat at 11.9% coverage because 4100 of its 5269 physical
products - 78% of the entire file - are curtain-wall parts that no detector
had any reason to look at. They are not noise: they are the building's
entire facade system.

Why the composition signature is the interesting part rather than the
membership. Listing a curtain wall's parts is bookkeeping; what carries
design intent is that the SAME assembly recurs. `moduleRecurrence` counts
how many curtain walls in the model share an identical (mullion count,
panel count) signature, which is a direct statement about prefabrication
and facade modularity - the constructional analogue of beam_framing.py's
`storeyRecurrence` and unit_typology.py's instance count. A facade built
from one repeated module reads very differently from one where every bay
is bespoke, and nothing else in this package could tell the two apart.

Deliberately NOT geometric, and therefore free of the placement quirks
that complicate most of this package: IfcRelAggregates is read directly,
so none of the mapped-representation breakage documented for IfcColumn,
IfcStairFlight or IfcBeam applies. The trade-off is that composition is
counted, not measured - two assemblies with the same part counts but
different dimensions are reported as the same module. A dimensional
signature would sharpen that and is not attempted here.
"""

from collections import Counter, defaultdict


from ..intent import make_member, make_intent
from ..storeys import get_storey

PART_CLASSES = ("IfcMember", "IfcPlate")
# 1, not 2. A curtain wall aggregating a single IfcPlate is still a real
# manufactured assembly - one glazed panel - and this is not an edge case:
# data/test_2.ifc and data/test_5.ifc build their facades entirely
# that way (44 curtain walls of 1 plate each, and 46 of 1 each). A
# threshold of 2 silently produced zero intents for both files. It is also
# exactly where `moduleRecurrence` is most informative: 44 curtain walls
# sharing one single-panel composition is a strong statement about
# facade modularity, not a degenerate case.
DEFAULT_MIN_PARTS = 1


def detect(model, extracted, file_key, min_parts=DEFAULT_MIN_PARTS):
    try:
        curtain_walls = model.by_type("IfcCurtainWall")
    except RuntimeError:
        return []
    if not curtain_walls:
        return []

    # curtain wall guid -> {class: [part guids]}
    parts = defaultdict(lambda: defaultdict(list))
    for ifc_class in PART_CLASSES:
        try:
            elements = model.by_type(ifc_class)
        except RuntimeError:
            continue
        for element in elements:
            for rel in element.Decomposes or []:
                owner = rel.RelatingObject
                # Parts aggregated into something else (data/test_4.ifc
                # attaches 84 of them to IfcStair) are not facade parts.
                if owner is not None and owner.is_a("IfcCurtainWall"):
                    parts[owner.GlobalId][element.is_a()].append(element.GlobalId)
                break

    # Composition signature -> how many assemblies share it.
    signatures = {}
    for guid, by_class in parts.items():
        signatures[guid] = tuple(sorted(
            (ifc_class, len(guids)) for ifc_class, guids in by_class.items()
        ))
    recurrence = Counter(signatures.values())

    intents = []
    for curtain_wall in curtain_walls:
        by_class = parts.get(curtain_wall.GlobalId)
        if not by_class:
            continue
        part_guids = [guid for guids in by_class.values() for guid in guids]
        if len(part_guids) < min_parts:
            continue

        storey = get_storey(curtain_wall, parent_container=True)
        storey_name = (storey.Name or storey.GlobalId) if storey is not None else "unassigned"
        mullions = len(by_class.get("IfcMember", []))
        panels = len(by_class.get("IfcPlate", []))
        shared = recurrence[signatures[curtain_wall.GlobalId]]
        composition = ", ".join(
            f"{len(guids)} {ifc_class}" for ifc_class, guids in sorted(by_class.items())
        )

        intents.append(make_intent(
            intent_id=f"{file_key}-curtainwall-{curtain_wall.GlobalId}",
            intent_type="curtainwall_assembly",
            label=(
                f"Curtain wall assembly ({composition}, {storey_name})"
                + (f" - module shared by {shared}" if shared > 1 else " - unique module")
            ),
            members=[
                make_member(curtain_wall.GlobalId, role="base", ifc_class=curtain_wall.is_a())
            ] + [
                make_member(guid, ifc_class=ifc_class)
                for ifc_class, guids in sorted(by_class.items())
                for guid in sorted(guids)
            ],
            detector="curtainwall_assembly",
            rule="curtainwall_part_aggregation",
            summary=(
                f"Curtain wall on storey {storey_name} is assembled from "
                f"{composition} via IfcRelAggregates"
                + (
                    f". {shared} curtain walls in this model share the same "
                    f"({mullions} mullion / {panels} panel) composition - a repeated "
                    f"facade module."
                    if shared > 1 else
                    f". No other curtain wall in this model shares its "
                    f"({mullions} mullion / {panels} panel) composition."
                )
            ),
            related_guids=[storey.GlobalId] if storey is not None else [],
            metrics={
                "storey": storey_name,
                "mullions": mullions,
                "panels": panels,
                "partCount": len(part_guids),
                "moduleRecurrence": shared,
            },
        ))

    return intents
