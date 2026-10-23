"""The shared name vocabulary: concepts, their words per language, and the
readers that turn an element or space into the text they are matched on.

The second deliberate exception to the package's per-detector duplication
convention (access_graph.py is the first, and says why that convention
exists). Six keyword tuples lived in six modules and drifted apart: the
library survey of 2026-09-23 found 167 of 518 models
naming no space with any English circulation word, German circulation words
in 14 of them and German fixture names in 20, while each module carried its
own partial list. One table, with a language column, is what that finding
asked for. Pre-flight probes the same table through the same
readers, so a `vocab:` signal cannot disagree with its detector.

Matching stays what it was: lowercase substring over the joined text, with
the one deliberate leading space in " wc" so "newcastle" is not a toilet.
Words that are common English or room words are left out on purpose: "bad"
(German bathroom, English bad), "bank" (bench, bank), "herd" (stove,
shepherd). The misspelling "corridoor" recurs in three library models and is
kept.

Readers:
  space_text(space)      Name, LongName and the IfcSpaceType's Name, lowercased
  element_text(element)  the family segment (before the first ":") of the
                         element's Name and of its type's Name - Revit names
                         are "Family:Variant:Id", and a dimension in the
                         variant ("15\\" Seat Height") must never count as
                         seating (furniture_occupancy.py's measured bug)
"""

import re

import ifcopenshell.util.element

CONCEPTS = {
    "horizontal_circulation": {
        "en": ("corridor", "hall", "lobby", "foyer", "vestibule", "passage", "aisle",
               "circulation", "entrance", "entry", "atrium", "corridoor"),
        "de": ("flur", "gang", "korridor", "diele", "eingang"),
    },
    "vertical_core": {
        "en": ("stair", "elevator", "lift", "shaft", "escalator", "ramp", "vertical"),
        "de": ("treppe", "aufzug", "fahrstuhl", "stiege"),
    },
    "seating": {
        "en": ("chair", "seat", "stool", "sofa", "couch", "bench"),
        "de": ("stuhl", "sessel", "hocker", "sitz"),
    },
    "sleeping": {
        "en": ("bed",),
        "de": ("bett",),
    },
    # Desks, for the Neufert workstations fact (2026-10-18): 217 of the 370
    # corpus models name a desk, 16 carry IfcFurniture.PredefinedType DESK.
    # "table" is left out (dining and meeting tables); "desk chair" is
    # classified as seating first (furnishing.KIND_CONCEPTS order).
    "desk": {"en": ("desk", "workstation", "work station"), "de": ("schreibtisch", "arbeitstisch")},
    # Lifts (2026-10-19), matched on an element's names: PredefinedType
    # ELEVATOR is set on 3 of the 13 corpus models with transport elements,
    # the rest name their lifts ("Elevator-Electric", type "Aufzug 26");
    # escalators and the one model naming its lifts only in ObjectType stay out.
    "lift": {"en": ("elevator", "lift"), "de": ("aufzug", "fahrstuhl")},
    # Space-use classes for the Neufert categories (2026-10-18, config/neufert;
    # the plan's config/keywords/space_use.yaml folded in here). Swept over
    # the 1,942 spaces of the 40 local models before adoption: "bad" (10 hits,
    # one German model) stays out as before, "kind" (1 hit, "kinderwagen"),
    # "store" (2 hits; would also match "storey") and "essen" (0 hits; would
    # match "essential") were dropped; "putz" became "putzraum".
    # 2026-10-18, second pass: the words the 370-model
    # corpus named and the first list missed. Words in
    # BOUNDED match on word boundaries instead of as substrings.
    # "wc" is BOUNDED (below) so a room named "WC 1" matches at the start of its text; the sanitary
    # fixture kinds keep their own " wc" spelling and are not touched.
    "wc": {"en": ("toilet", "tiolet", "restroom", "rest room", "lavatory", "washroom", "wash room", "wc", "w/c"), "de": ("toilette",)},
    "bathroom": {"en": ("bath", "shower"), "de": ("badezimmer", "dusche", "bad")},
    "kitchen": {"en": ("kitchen", "kitchenette", "pantry"), "de": ("küche", "kueche", "kochen", "teeküche")},
    "dining": {"en": ("dining",), "de": ("esszimmer",)},
    "living": {"en": ("living", "lounge"), "de": ("wohnzimmer", "wohnen", "wohnbereich")},
    "dwelling": {"en": ("apartment", "apt", "flat", "studio", "cabin"), "de": ("wohnung", "whg")},  # "cabin" BOUNDED (no cabinet); "flat roof" excluded below
    "assembly_hall": {"en": ("auditorium", "lecture hall", "assembly hall", "concert"), "de": ("saal", "hörsaal", "aula")},
    "bedroom": {"en": ("bedroom", "bed room", "sleeping room", "kids room", "master bed", "bed"), "de": ("schlafzimmer", "schlafen", "kinderzimmer", "eltern")},
    "office": {"en": ("office", "workspace", "working space", "workstation", "study room", "manager room", "copy room", "secretary room"), "de": ("büro", "buero", "arbeitsplatz")},
    "open_plan_office": {"en": ("open office", "open-plan", "open plan"), "de": ("großraum", "grossraum")},
    "meeting": {"en": ("meeting", "conference", "confrence", "seminar", "classroom", "class room"), "de": ("besprechung", "konferenz")},
    "storage": {"en": ("storage", "store room", "storeroom", "store", "closet", "wardrobe", "utility room"), "de": ("abstellraum", "abstell", "lager")},
    "filing": {"en": ("archive", "filing"), "de": ("archiv", "registratur")},
    "technical": {"en": ("server", "shaft", "plant room", "mechanical"), "de": ("haustechnik", "technik", "hausanschluss", "schacht")},
    "lobby": {"en": ("foyer", "lobby", "entrance", "reception"), "de": ("eingang", "empfang")},
    "balcony": {"en": ("balcony", "terrace", "loggia"), "de": ("balkon", "terrasse")},
    "cellar": {"en": ("basement", "cellar"), "de": ("keller",)},
    "garage": {"en": ("garage", "carport", "parking"), "de": ("stellplatz",)},
    "cleaning": {"en": ("cleaner", "cleaning", "janitor"), "de": ("putzraum", "putzmittel")},
    # Scenario concepts (2026-10-20, config/neufert/scenarios.yaml): a staff restaurant (K125, K128), a post room
    # (K144), a server room (K145). "mensa" is BOUNDED.
    "canteen": {"en": ("canteen", "cafeteria", "restaurant", "refectory", "mensa"), "de": ("kantine", "speisesaal", "casino")},
    "post_room": {"en": ("post room", "postroom", "mail room", "mailroom"), "de": ("poststelle", "postraum")},
    "server_room": {"en": ("server", "data centre", "data center"), "de": ("serverraum", "rechenzentrum", "edv-raum")},
    # Corpus signals for the "not determinable" cards (2026-10-20): fire zones (K42, 36 models with IfcZone),
    # terraced houses (K92, 14 models), university rooms (K130, 19 models), industrial workrooms (K53, 2 models).
    "fire_compartment": {"en": ("fire compartment", "fire zone", "fire section"), "de": ("brandabschnitt", "brandschutzabschnitt", "brandwand")},
    "terraced_house": {"en": ("terraced house", "terrace house", "row house", "townhouse", "town house"), "de": ("reihenhaus", "reihenmittelhaus", "reihenendhaus")},
    "university": {"en": ("lecture hall", "lecture theatre", "lecture room", "auditorium", "professor", "institute"), "de": ("hörsaal", "hoersaal", "institut", "professor", "lehrstuhl")},
    "workshop": {"en": ("workshop", "production hall", "factory", "assembly line"), "de": ("werkstatt", "werkhalle", "produktion", "fertigung", "montagehalle")},
    "sanitary_accessory": {
        "en": ("dispencer", "dispenser", "paper", "screen", "holder", "grab",
               "mirror", "towel", "hole", "partition", "rail"),
        "de": ("spender", "halter", "spiegel", "handtuch"),
    },
}

# Sanitary fixtures, per kind, in the order sanitary_provision.py classifies
# them (the first kind whose words match wins).
SANITARY_FIXTURE_KINDS = (
    ("wc", {"en": ("toilet", "urinal", "bidet", "lavatory", " wc"), "de": ("toilette", "pissoir")}),
    ("bath", {"en": ("shower", "bathtub", "bath"), "de": ("dusche", "badewanne", "wanne")}),
    ("kitchen", {"en": ("kitchen", "kitchenette", "cook", "stove"), "de": ("küche", "kochfeld")}),
    ("wash", {"en": ("sink", "basin", "washbasin"), "de": ("waschbecken", "waschtisch")}),
)
LANGUAGES = ("en", "de")
# Words that would match inside other words as substrings ("bad" in "badminton"
# and English "bad", "store" in "storey", "bed" in "embedded", "flat" in
# "flat roof"): matched on word boundaries, but ONLY inside the concepts
# added on 2026-10-18 (BOUNDED_CONCEPTS). The committed concepts keep
# substring matching as the live detectors always had it: "bed" in
# `sleeping` still matches "beds" and "doublebed" for furniture_occupancy
# (review). The first list left "bad" out for this reason; the
# corpus has 83 German bathrooms named exactly "Bad".
BOUNDED = frozenset({"bad", "store", "bed", "flat", "apt", "whg", "wc", "w/c", "lift", "mensa", "cabin"})
# Phrases that veto a concept's match even though one of its words occurs (code review 2026-10-20:
# a "Flat roof" space read as a one-room dwelling). Only the concepts listed here are affected.
EXCLUDE_PHRASES = {"dwelling": ("flat roof", "flatroof", "flat slab", "flat ceiling")}
BOUNDED_CONCEPTS = frozenset({
    "wc", "bathroom", "kitchen", "dining", "living", "bedroom", "office", "open_plan_office", "meeting",
    "storage", "filing", "technical", "lobby", "balcony", "cellar", "garage", "cleaning", "dwelling", "assembly_hall",
    "desk", "lift", "canteen", "post_room", "server_room", "fire_compartment", "terraced_house", "university", "workshop",
})
_BOUNDED_PATTERNS = {word: re.compile(r"(?<![a-zäöüß])" + re.escape(word) + r"(?![a-zäöüß])") for word in BOUNDED}


def _flatten(by_language):
    return tuple(word for language in LANGUAGES for word in by_language.get(language, ()))


# (kind, words) pairs - sanitary_provision.FIXTURE_KINDS keeps this shape.
SANITARY_FIXTURE_KIND_WORDS = tuple((kind, _flatten(by_language)) for kind, by_language in SANITARY_FIXTURE_KINDS)


def words(concept):
    """Every word of a concept, English first; "sanitary_fixture" gives
    every kind's words."""
    if concept == "sanitary_fixture":
        return tuple(word for _, kind_words in SANITARY_FIXTURE_KIND_WORDS for word in kind_words)
    return _flatten(CONCEPTS[concept])


def _word_in(word, text, bounded):
    pattern = _BOUNDED_PATTERNS.get(word) if bounded else None
    return pattern.search(text) is not None if pattern else word in text


def matches(text, concept):
    """True when any word of the concept - or of any concept in an "a|b"
    expression - occurs in `text` (already lowercased); as a substring,
    except that BOUNDED words of a concept in BOUNDED_CONCEPTS match on
    word boundaries."""
    return any(_word_in(word, text, name in BOUNDED_CONCEPTS)
               for name in concept.split("|") if not any(phrase in text for phrase in EXCLUDE_PHRASES.get(name, ()))
               for word in words(name))


def fixture_kind(text):
    """The sanitary fixture kind named by `text`, None for an accessory that
    merely names its fixture ("toilet paper holder") or for no fixture."""
    if matches(text, "sanitary_accessory"):
        return None
    for kind, kind_words in SANITARY_FIXTURE_KIND_WORDS:
        if any(word in text for word in kind_words):
            return kind
    return None


def _type_of(element):
    try:
        return ifcopenshell.util.element.get_type(element)
    except Exception:  # noqa: BLE001 - a plain object or an odd entity has no type
        return None


def space_text(space):
    element_type = _type_of(space)
    parts = (getattr(space, "Name", None), getattr(space, "LongName", None),
             getattr(element_type, "Name", None) if element_type is not None else None)
    return " ".join(part for part in parts if part).lower()


def _family_segment(name):
    return (name or "").split(":")[0]


def element_text(element):
    parts = [_family_segment(getattr(element, "Name", None))]
    element_type = _type_of(element)
    if element_type is not None:
        parts.append(_family_segment(getattr(element_type, "Name", None)))
    return " ".join(part for part in parts if part).lower()
