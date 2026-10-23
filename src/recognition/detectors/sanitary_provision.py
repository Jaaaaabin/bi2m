"""Sanitary and kitchen provision: WC, washing, bathing and kitchen
fixtures located in the rooms they serve and counted per storey - how much
sanitary capacity the model actually provides at each level.

Opens a "services" domain. MEP/services had been absent
from registry.py's domains AND an element family nothing touched at all
(168 IfcFlowTerminal corpus-wide, 0 covered). It also lands on a
programmatic intent none of the other categories can express - "every
dwelling has a bathroom", "this floor provides N WCs" - which sits close to
the regulatory questions that belong to the separate
[[bim-compliance]] layer, without pretending to answer them.

Fixtures are gathered across IfcFlowTerminal, IfcSanitaryTerminal,
IfcBuildingElementProxy and IfcFurniture, because the corpus scatters the
same fixtures across all of them - data/test_5.ifc puts its sinks, showers
and bidets in IfcFlowTerminal but its toilets, kitchenettes and cook tops
in IfcBuildingElementProxy, while data/test_4.ifc puts everything in
IfcBuildingElementProxy. Classification is therefore by name, never by
class, and de-duplicated by GUID for the subtype overlap furniture_
occupancy.py documents.

Two name traps in this corpus, both real, both handled:

1. ACCESSORIES that name the fixture they serve. data/test_4.ifc exports 50
   "Dispencer-Toilet Paper-2D" - a paper dispenser is not a WC, but it
   contains "toilet". ACCESSORY_KEYWORDS rejects these outright. Note the
   deny-list deliberately does NOT contain "stall": data/test_5.ifc's real
   showers are named "Basin Shower - Stall", and rejecting on that word
   would discard 48 genuine fixtures to remove a different file's
   duplicates. Those duplicates are handled by (2) instead.

2. COMPOSITE double-counting. data/test_4.ifc has both "Toilet Stall w
   Toilet" (50) and "Toilet-Commercial-Wall-3D" (50) - a stall enclosure
   modeled around the fixture it contains, and the fixture itself. Counting
   objects would report 100 WCs where the building has 50. Rather than
   guess from names which one is "the real" fixture, this de-duplicates
   SPATIALLY, and the radius is measured rather than chosen. Dumping every
   WC-class fixture on one storey of data/test_4.ifc ("Ground +0.00", 24
   objects at 10 distinct positions) shows the two populations are cleanly
   separated:
     - a stall and the toilet inside it are co-located EXACTLY - distance
       0.000m at 3 decimal places, every time. The same file also carries
       true duplicates (two stalls plus two toilets stacked on one point),
       which are a modeling artifact and collapse the same way.
     - the nearest two GENUINELY distinct fixtures are 0.36m apart (a
       urinal beside a toilet), and consecutive toilets in a row are 1.03m
       apart.
   DEFAULT_DUPLICATE_RADIUS_M = 0.05 therefore collapses every composite
   and separates every real fixture, with a 7x margin to the nearest real
   pair. An earlier 0.6m value was wrong in a way worth recording: it
   silently swallowed all 4 urinals on that storey into their neighbouring
   toilets, reporting 6 WC-class fixtures where there are 10. Both figures
   are reported (`wcRaw` vs `wc`) so a reviewer can see how much collapsing
   occurred rather than having to trust it.

The same composite caveat furniture_occupancy.py records applies here: a
"Counter Top w Sinks" is one object depicting several basins, so
multi-fixture families under-count. The raw object count is at least
transparent about what it measured.
"""

from collections import defaultdict

import ifcopenshell.util.element
from shapely.geometry import Point

from ifc_units import length_scale, placement_xy

from ..access_graph import space_label, space_polygons
from ..census import elements_by_guid
from ..intent import make_member, make_intent
from ..spaces import index_by_storey, nearest_space
from .. import vocabulary

FIXTURE_CLASSES = (
    "IfcFlowTerminal", "IfcSanitaryTerminal",
    "IfcBuildingElementProxy", "IfcFurniture",
)

# Checked FIRST - an accessory that names its fixture is not that fixture.
# "stall" is deliberately absent; see the module docstring.
# Both tables live in recognition/vocabulary.py since 2026-10-08, with their
# German words (Waschbecken, Dusche, ...: 20 library models name fixtures only
# in German). The names stay as references.
ACCESSORY_KEYWORDS = vocabulary.words("sanitary_accessory")
FIXTURE_KINDS = vocabulary.SANITARY_FIXTURE_KIND_WORDS

# Measured, not chosen: composites sit at exactly 0.000m, the nearest two
# real fixtures at 0.36m. See the module docstring.
DEFAULT_DUPLICATE_RADIUS_M = 0.05
DEFAULT_FIXTURE_REACH_M = 0.5
DEFAULT_MIN_FIXTURES = 2


def _classify(element):
    # Family segments of the instance and type names (vocabulary.element_text);
    # accessories that name their fixture are rejected first.
    return vocabulary.fixture_kind(vocabulary.element_text(element))


def _deduplicate(entries, radius_m):
    """Collapse same-kind fixtures within `radius_m` into one provision.
    Simple greedy clustering - the counts involved are small (tens per
    storey) and the clusters are tight pairs, so this needs nothing more."""
    kept = []
    for guid, point in entries:
        if any(point.distance(other) <= radius_m for _, other in kept):
            continue
        kept.append((guid, point))
    return kept


def detect(model, extracted, file_key,
           fixture_reach_m=DEFAULT_FIXTURE_REACH_M,
           duplicate_radius_m=DEFAULT_DUPLICATE_RADIUS_M,
           min_fixtures=DEFAULT_MIN_FIXTURES):
    spaces = model.by_type("IfcSpace")
    if not spaces:
        return []

    by_guid = elements_by_guid(model, FIXTURE_CLASSES)
    if not by_guid:
        return []

    polygons = space_polygons(model, spaces)
    if not polygons:
        return []

    space_by_guid = {space.GlobalId: space for space in spaces}
    spaces_by_storey = index_by_storey(spaces, polygons)

    # Fixture placements in metres, like the footprints (docs/detectors.md rule 13).
    scale = length_scale(model)
    # storey guid -> kind -> [(fixture guid, point)]
    fixtures = defaultdict(lambda: defaultdict(list))
    # storey guid -> space guid -> set of kinds
    rooms_served = defaultdict(lambda: defaultdict(set))
    for element in by_guid.values():
        kind = _classify(element)
        if kind is None:
            continue
        storey = ifcopenshell.util.element.get_container(
            element, ifc_class="IfcBuildingStorey")
        if storey is None:
            continue
        xy = placement_xy(element, scale)
        if xy is None:
            continue
        point = Point(*xy)
        fixtures[storey.GlobalId][kind].append((element.GlobalId, point))

        nearest, nearest_distance = nearest_space(point, spaces_by_storey.get(storey.GlobalId, []), polygons)
        if nearest is not None and nearest_distance <= fixture_reach_m:
            rooms_served[storey.GlobalId][nearest].add(kind)

    intents = []
    for storey_guid, by_kind in fixtures.items():
        storey = model.by_guid(storey_guid)
        storey_name = storey.Name if storey and storey.Name else storey_guid

        counts, raw_counts, members = {}, {}, []
        for kind, entries in by_kind.items():
            raw_counts[kind] = len(entries)
            kept = _deduplicate(entries, duplicate_radius_m)
            counts[kind] = len(kept)
            members.extend(guid for guid, _ in kept)
        if sum(counts.values()) < min_fixtures:
            continue

        served = rooms_served.get(storey_guid, {})
        collapsed = sum(raw_counts.values()) - sum(counts.values())
        collapsed_note = (
            f" {collapsed} co-located duplicate(s) collapsed (a stall and the "
            f"fixture inside it count once)."
            if collapsed else ""
        )
        provision = ", ".join(
            f"{count} {kind}" for kind, count in sorted(counts.items(), key=lambda kv: -kv[1])
        )
        room_detail = ", ".join(
            f"{space_label(space_by_guid[guid])} ({'/'.join(sorted(kinds))})"
            for guid, kinds in list(served.items())[:5]
        )

        intents.append(make_intent(
            intent_id=f"{file_key}-sanitary-{storey_guid}",
            intent_type="sanitary_provision",
            label=f"Sanitary provision ({storey_name}: {provision} fixtures)",
            members=[
                make_member(guid, ifc_class=by_guid[guid].is_a()) for guid in sorted(members)
            ] + [
                make_member(guid, role="context", ifc_class="IfcSpace")
                for guid in sorted(served)
            ],
            detector="sanitary_provision",
            rule="fixture_provision_count",
            summary=(
                f"Storey {storey_name} provides {provision} - counted as "
                f"FIXTURES, not rooms (an apartment kitchen modeled as a "
                f"kitchenette plus a cook top plus a sink scores 3) - serving "
                f"{len(served)} rooms.{collapsed_note} Fixtures are classified by "
                f"name across IfcFlowTerminal/IfcBuildingElementProxy/IfcFurniture "
                f"(accessories such as paper dispensers are excluded)."
                + (f" Rooms: {room_detail}." if room_detail else "")
            ),
            related_guids=[storey_guid],
            metrics={
                "storey": storey_name,
                **{kind: count for kind, count in sorted(counts.items())},
                **{f"{kind}Raw": count for kind, count in sorted(raw_counts.items())},
                "roomsServed": len(served),
                "duplicatesCollapsed": collapsed,
                "duplicateRadiusM": duplicate_radius_m,
            },
        ))

    return intents
