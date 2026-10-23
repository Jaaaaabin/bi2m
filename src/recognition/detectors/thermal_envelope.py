"""Thermal/weather envelope: the elements a model itself declares as the
boundary between inside and outside (`IsExternal = True`), grouped one
intent per storey - the building's enclosing ring at each level, plus
whatever thermal specification those elements carry.

The first detector in the "environmental" domain, and the first anywhere in
this package that recognizes an intent from a PROPERTY the model already
states rather than from geometry it has to re-derive. That was
the cheapest untapped rung: on the explicit -> implicit ->
extrinsic -> tacit difficulty ladder, "already tagged in the file" should be
the easiest thing to harvest, and before this module nothing in
src/recognition/ read a property set at all (extraction/walls.py's
calc_wall_loadbearing was the pipeline's only property-derived signal, and
no detector consumed it as such).

Why this one first, of everything in the coverage backlog: `IsExternal` is
the single most portable signal measured across the corpus. Confirmed
present and non-trivial on every one of the 6 distinct models (counts of
elements tagged True): data/test_3.ifc 81, data/test_2.ifc 138,
data/test_6.ifc 207, data/test_5.ifc 450, data/test_7.ifc 477,
data/test_4.ifc 659. Contrast `IfcRelSpaceBoundary`, which connection.py
depends on: 1032 entries in data/test_3.ifc and ZERO in the other five, so
that detector is effectively a one-model detector. An envelope built on
`IsExternal` is not.

It also reaches element classes no other detector touches at all. Across
the corpus IfcCurtainWall was 0/303 covered and IfcPlate 0/1867 before this
module; curtain walls are tagged external in 5 of 6 models (293 of those
303 instances), and data/test_4.ifc alone tags 491 IfcPlate - a curtain-wall
assembly's own skin panels, which ARE the envelope at that level, not an
unrelated element family. Including them is deliberate.

Scope note: registered scope="storey" because the ring is grouped and
reported per level. The envelope as a whole is a building-level object, and
`scope` currently has no value for that (lighting_clusters has the same
mis-fit); per-storey is the honest reading of what
this detector actually emits.

Thermal specification is reported, never required. `ThermalTransmittance`
(Pset_WallCommon/Pset_WindowCommon) is present on walls in only 4 of the 6
models, and data/test_7.ifc spells the same quantity
"Heat Transfer Coefficient (U)" under a Revit-authored "Analytical
Properties" set instead - both names are accepted. A storey whose envelope
declares no U-value at all is still a perfectly real envelope, so it is
still reported; the metrics simply record `thermalSpecified: 0`. That
count is the interesting part for a reviewer: an envelope that is
geometrically complete but thermally unspecified is exactly the kind of
incompleteness a human validator should see, and it is invisible to every
geometric detector in this package.
"""

from collections import Counter, defaultdict


from ..intent import make_member, make_intent
from ..properties import is_external, property_value
from ..storeys import get_storey

# Classes that can legitimately form an enclosing boundary. IfcPlate and
# IfcMember are in because a curtain wall is exported as an assembly of
# them (confirmed on data/test_4.ifc: 491 externally-tagged plates) - they
# are the skin itself, not a separate element family.
ENVELOPE_CLASSES = (
    "IfcWall", "IfcWallStandardCase", "IfcCurtainWall", "IfcPlate", "IfcMember",
    "IfcWindow", "IfcDoor", "IfcSlab", "IfcRoof",
)

# Both spellings seen in the corpus - the IFC-standard property name, and
# the Revit "Analytical Properties" label data/test_7.ifc uses instead.
U_VALUE_NAMES = ("ThermalTransmittance", "Heat Transfer Coefficient (U)")

DEFAULT_MIN_MEMBERS = 3


def _u_values(elements):
    values = []
    for element in elements:
        value = property_value(element, U_VALUE_NAMES)
        if isinstance(value, (int, float)) and value > 0:
            values.append(float(value))
    return values


def detect(model, extracted, file_key, min_members=DEFAULT_MIN_MEMBERS):
    by_storey = defaultdict(list)
    for ifc_class in ENVELOPE_CLASSES:
        try:
            elements = model.by_type(ifc_class)
        except RuntimeError:
            # Class absent from this file's schema - nothing to do.
            continue
        for element in elements:
            # IfcWallStandardCase is a subtype of IfcWall, so by_type returns
            # it twice; key the bucket by GUID later rather than filtering
            # here, which would need the class hierarchy re-derived.
            if is_external(element):
                storey = get_storey(element, parent_container=True)
                if storey is not None:
                    by_storey[storey.GlobalId].append(element)

    intents = []
    for storey_guid, elements in by_storey.items():
        # De-duplicate the IfcWall/IfcWallStandardCase double-hit.
        unique = {element.GlobalId: element for element in elements}
        if len(unique) < min_members:
            continue

        storey = model.by_guid(storey_guid)
        storey_name = storey.Name if storey and storey.Name else storey_guid
        class_counts = Counter(element.is_a() for element in unique.values())
        values = _u_values(unique.values())

        metrics = {
            "storey": storey_name,
            "elementCount": len(unique),
            "classBreakdown": dict(class_counts.most_common()),
            "thermalSpecified": len(values),
            "thermalUnspecified": len(unique) - len(values),
        }
        if values:
            metrics.update({
                "uValueMin": round(min(values), 3),
                "uValueMax": round(max(values), 3),
                "uValueMean": round(sum(values) / len(values), 3),
            })

        spec_note = (
            f"{len(values)} of {len(unique)} declare a thermal transmittance"
            if values else "none declare a thermal transmittance"
        )
        intents.append(make_intent(
            intent_id=f"{file_key}-envelope-external-{storey_guid}",
            intent_type="envelope_thermal_boundary",
            label=f"External envelope ring ({storey_name}, {len(unique)} elements)",
            members=[
                make_member(guid, ifc_class=element.is_a())
                for guid, element in sorted(unique.items())
            ],
            detector="thermal_envelope",
            rule="is_external_envelope_ring",
            summary=(
                f"{len(unique)} elements on storey {storey_name} are tagged "
                f"IsExternal=True, forming its inside/outside boundary "
                f"({', '.join(f'{n} {c}' for c, n in class_counts.most_common())}); "
                f"{spec_note}."
            ),
            related_guids=[storey_guid],
            metrics=metrics,
        ))

    return intents
