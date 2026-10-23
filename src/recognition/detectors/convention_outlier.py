"""Convention outliers: the handful of elements that break a rule the
overwhelming majority of their siblings follow - 9 walls of 159 drawn to a
different location line, 1 door of 86 at a different height, 1 column of 94
assigned to a different level.

Two gaps at once. This is the package's first tier-1 (component/attribute)
detector on the granularity ladder - the rung that had stayed the
emptiest, and the only one where the subject is a SINGLE
element judged against its own properties rather than a group judged by
geometry. And it is negative-polarity by construction: every record asserts
that something is WRONG-looking, never that something is present.

The reason tier 1 stayed empty was never really the schema - `make_intent`
has no minimum member count - it was VOLUME. A per-element check over 2244
walls would emit 2244 records and bury the queue. This inverts that: it
reports only the exceptions, so the whole corpus yields on the order of ten
records. An earlier measurement found that 64% of the existing review queue is
two mechanisms emitting near-identical records with no way to rank them; a
category that emits ~10 records, each meaning "this specific element is the
odd one out", is the opposite trade and belongs near the top of a
reviewer's list.

How a convention is established. For each (element class, property) pair
with at least DEFAULT_MIN_POPULATION elements carrying it, the most common
value is taken as the convention. If the minority is non-empty but no larger
than DEFAULT_MAX_MINORITY_FRACTION of the population, those minority
elements are reported. Both thresholds matter: the population floor stops
"1 of 3" being called a violation, and the fraction ceiling stops a
genuinely bimodal property (half the walls external, half internal) being
misread as 50% violations. A continuously-distributed property such as wall
length self-filters, because no value dominates and the minority fraction
approaches 1.

Properties are a curated allow-list, not everything the file carries. Swept
across the corpus without one, the top hits included
"Türgriff auswählen" (which door handle a Revit family uses, 6 variants in
data/test_7.ifc) - true, stable, and completely uninteresting as design
intent. WATCHED_PROPERTIES and NUMERIC_PROPERTIES below keep only
properties that plausibly encode a design or construction decision.

Numeric values are unit-scaled and rounded to millimetre precision before
comparison, which is what makes the sharpest finding in the corpus visible:
data/test_4.ifc has 110 doors at exactly 2.200m and ONE at 2.225m. A
25mm deviation in an otherwise perfectly uniform set is far more likely to
be a modeling slip than a design decision - precisely the judgement call
this detector exists to put in front of a person.

"Majority = convention" can point the wrong way, and the corpus contains a
clear example. In data/test_5.ifc, 125 of 126 IfcWindow carry
IsExternal=False and exactly one carries True, so this detector dutifully
reports the single True as the outlier. Architecturally that is backwards:
windows are overwhelmingly exterior elements, and the suspicious population
is the 125, not the 1. The rule is purely statistical and has no model of
what a property SHOULD be, so it can only ever say "these few differ from
the rest" - never "the rest are wrong". A reviewer reading the record still
learns something true and useful (this file's window IsExternal tagging is
strange), but they have to supply the direction. Treating this as a defect
to fix would mean encoding per-property expectations, which is the
separate [[bim-compliance]] layer.

Measured yield, and its honest limitation: 17 records across all
six models. Some deliberately overlap detectors that already cover the same
fact from the other side - the 4 doors in data/test_3.ifc tagged
IsExternal=True are both this detector's "exception to an interior-door
convention" and egress_access.py's access points. That overlap is
corroboration rather than duplication, but it does mean this category's
novel contribution is smaller than its record count suggests. The genuinely
new findings are the dimensional and construction-convention ones:
data/test_3.ifc's 9 walls at "Finish Face: Interior" against 150 at
"Wall Centerline", data/test_7.ifc's single column on a different base
level, and the 2.225m door above.
"""

from collections import Counter, defaultdict

import ifcopenshell.util.element
import ifcopenshell.util.unit

from ..session import psets_of
from ..intent import make_member, make_intent

CLASSES = (
    "IfcWall", "IfcDoor", "IfcWindow", "IfcColumn", "IfcBeam", "IfcSlab",
    "IfcSpace", "IfcCurtainWall",
)

# Categorical properties that plausibly encode a design/construction
# decision. See the module docstring for what an uncurated sweep returns.
WATCHED_PROPERTIES = {
    "LoadBearing", "IsExternal", "FireRating", "Status", "Function",
    "Location Line", "Level", "Base Level", "Reference Level",
    "ExtendToStructure", "Compartmentation", "AboveGround",
}

# Dimensional properties, compared after unit scaling.
NUMERIC_PROPERTIES = {
    "Width", "Height", "Length", "Thickness", "NominalThickness",
    "OverallWidth", "OverallHeight", "CrossSectionArea", "Span", "Depth",
}

# Below this many elements carrying the property, "the majority" is not a
# convention - it is a coincidence.
DEFAULT_MIN_POPULATION = 20
# Above this share, the property is bimodal by design, not violated.
DEFAULT_MAX_MINORITY_FRACTION = 0.10
# Millimetre precision for numeric comparison.
_NUMERIC_DECIMALS = 3


def _hashable(value):
    """Property values are occasionally lists (enumerated Revit
    properties); those cannot key a Counter and carry no convention worth
    checking, so they are skipped rather than coerced."""
    return isinstance(value, (str, bool, int, float))


def detect(model, extracted, file_key,
           min_population=DEFAULT_MIN_POPULATION,
           max_minority_fraction=DEFAULT_MAX_MINORITY_FRACTION):
    unit_scale = ifcopenshell.util.unit.calculate_unit_scale(model)

    intents = []
    for ifc_class in CLASSES:
        try:
            elements = model.by_type(ifc_class)
        except RuntimeError:
            continue
        # by_type returns subtypes too (IfcWallStandardCase under IfcWall);
        # de-duplicate so one element cannot vote twice.
        elements = list({element.GlobalId: element for element in elements}.values())
        if len(elements) < min_population:
            continue

        # property name -> value -> [guids]
        observations = defaultdict(lambda: defaultdict(list))
        for element in elements:
            for pset in psets_of(element).values():  # the model session's memo (session.py)
                for key, value in pset.items():
                    if key == "id" or value is None or not _hashable(value):
                        continue
                    if key in WATCHED_PROPERTIES:
                        observations[key][value].append(element.GlobalId)
                    elif key in NUMERIC_PROPERTIES and isinstance(value, (int, float)) \
                            and not isinstance(value, bool):
                        scaled = round(float(value) * unit_scale, _NUMERIC_DECIMALS)
                        observations[key][scaled].append(element.GlobalId)

        for property_name, by_value in observations.items():
            counts = Counter({value: len(guids) for value, guids in by_value.items()})
            population = sum(counts.values())
            if population < min_population or len(counts) < 2:
                continue
            dominant, dominant_count = counts.most_common(1)[0]
            minority = population - dominant_count
            if minority == 0 or minority / population > max_minority_fraction:
                continue

            outliers = sorted(
                guid
                for value, guids in by_value.items() if value != dominant
                for guid in guids
            )
            deviations = {
                str(value): len(guids)
                for value, guids in sorted(
                    by_value.items(), key=lambda kv: -len(kv[1])
                ) if value != dominant
            }
            is_numeric = property_name in NUMERIC_PROPERTIES
            dominant_text = f"{dominant}m" if is_numeric else str(dominant)
            deviation_text = ", ".join(
                f"{value}{'m' if is_numeric else ''} x{count}"
                for value, count in deviations.items()
            )

            intents.append(make_intent(
                intent_id=f"{file_key}-outlier-{ifc_class}-{property_name.replace(' ', '')}",
                intent_type="convention_outlier",
                polarity="negative",
                label=(
                    f"{minority} {ifc_class} break the {property_name} convention "
                    f"({dominant_count}/{population} at {dominant_text})"
                ),
                members=[
                    make_member(guid, ifc_class=ifc_class) for guid in outliers
                ],
                detector="convention_outlier",
                rule="minority_property_deviation",
                summary=(
                    f"{dominant_count} of {population} {ifc_class} instances carry "
                    f"{property_name} = {dominant_text}; {minority} deviate "
                    f"({deviation_text}). A minority this small against an otherwise "
                    f"uniform set is more often a modeling slip than a design "
                    f"decision - but only a reviewer can say which."
                ),
                related_guids=[],
                metrics={
                    "ifcClass": ifc_class,
                    "property": property_name,
                    "dominantValue": str(dominant),
                    "dominantCount": dominant_count,
                    "population": population,
                    "outlierCount": minority,
                    "deviations": deviations,
                    "isNumeric": is_numeric,
                    "minPopulation": min_population,
                    "maxMinorityFraction": max_minority_fraction,
                },
            ))

    return intents
