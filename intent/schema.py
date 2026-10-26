"""Pydantic schema for one Neufert design intent.

Constraints for structured outputs (OpenAI strict + Anthropic): no defaults,
no free-form dicts, Optional fields typed as `X | None`, Literals for enums.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# --- controlled vocabularies -------------------------------------------------

Kind = Literal["hard_constraint", "soft_principle", "typical_value", "tacit"]
Modality = Literal["must", "should", "typical", "may"]
Checkable = Literal["direct", "relational", "not_checkable"]

ElementClass = Literal[
    "space", "wall", "door", "window", "slab", "stair", "roof", "balcony_terrace",
    "building", "site", "furniture", "service", "other",
]

Concept = Literal[
    "daylight_sun",          # daylight, sunlight, solar orientation
    "ventilation_air",       # natural/mechanical ventilation, air quality
    "thermal",               # heat loss/gain, insulation, thermal comfort
    "acoustic",              # sound insulation, noise separation
    "visual_privacy",        # overlooking, sight lines, privacy of use
    "circulation_access",    # movement, corridors, entrances, routes
    "accessibility",         # barrier-free, wheelchair, elderly
    "fire_egress",           # fire protection, escape routes
    "structure",             # load-bearing, spans, stacking of structure
    "services_stacking",     # plumbing/ducts routing, wet rooms stacked
    "ergonomics_anthropometry",  # human dimensions, reach, movement space
    "furniture_fit",         # room sized/shaped for furniture and equipment
    "area_economy",          # efficient use of area, cost, density
    "orientation_climate",   # compass orientation, wind, weather, climate
    "hygiene_moisture",      # damp, cleaning, sanitation
    "flexibility_adaptability",  # future change, convertibility
    "safety_security",       # falls, children, burglary
    "social_functional_zoning",  # grouping of rooms by use, zoning, adjacency logic
    "other",
]

CONCEPT_GLOSSARY = {
    "daylight_sun": "daylight, sunlight, solar orientation of rooms/windows",
    "ventilation_air": "natural or mechanical ventilation, air quality, cross-ventilation",
    "thermal": "heat loss/gain, insulation, thermal comfort, compactness",
    "acoustic": "sound insulation, separation of noisy and quiet uses",
    "visual_privacy": "overlooking, sight lines, privacy of use",
    "circulation_access": "movement, corridors, entrances, routes, door swing",
    "accessibility": "barrier-free design, wheelchair users, elderly",
    "fire_egress": "fire protection, escape routes, compartmentation",
    "structure": "load-bearing logic, spans, structural stacking/alignment",
    "services_stacking": "plumbing/duct routing, wet rooms stacked vertically",
    "ergonomics_anthropometry": "human body dimensions, reach, movement clearances",
    "furniture_fit": "room sized/shaped to hold furniture and equipment",
    "area_economy": "efficient use of area, cost, housing density",
    "orientation_climate": "compass orientation, wind, weather exposure, climate",
    "hygiene_moisture": "damp, condensation, cleaning, sanitation",
    "flexibility_adaptability": "future change of use, convertibility, extension",
    "safety_security": "falls, child safety, burglary protection",
    "social_functional_zoning": "grouping rooms by use, day/night zoning, adjacency logic",
    "other": "none of the above (describe in rationale.text)",
}


# --- record ------------------------------------------------------------------

class Scope(BaseModel):
    element_class: ElementClass
    ifc_entity: str | None = Field(description="Closest IFC entity, e.g. IfcSpace, IfcWindow, IfcDoor, IfcWall, IfcSlab, IfcStair, IfcBuilding, IfcSite; null if none fits")
    space_type: str | None = Field(description="Room/space type this applies to, lowercase, e.g. bedroom, living_room, kitchen, bathroom, corridor, entrance, balcony; null if not room-specific")
    element_qualifier: str | None = Field(description="Extra qualifier, e.g. 'exterior wall', 'entrance door', 'parents bedroom'")


class Condition(BaseModel):
    building_type: str | None = Field(description="e.g. residential, detached_house, flat, terrace_house; null if generic")
    room_type: str | None
    occupancy: str | None = Field(description="e.g. '1 person', '2 persons', 'family of 4'")
    adjacency: str | None = Field(description="Required neighbouring room/relationship, e.g. 'adjacent to living room', 'above another flat'")
    storey: str | None = Field(description="e.g. ground_floor, upper_floor, basement, attic")
    orientation: str | None = Field(description="e.g. south, east_southeast, north-facing")
    other: str | None = Field(description="Any other applicability condition, in plain words")


class Prescription(BaseModel):
    property: str | None = Field(description="Measured quantity in snake_case, e.g. net_floor_area, clear_height, clear_width, sill_height, window_area_ratio, distance, count; null for qualitative")
    op: Literal[">=", "<=", "=", "~", "range", "qualitative"]
    value_min: float | None = Field(description="Lower bound or single value; null if qualitative")
    value_max: float | None = Field(description="Upper bound for ranges; null otherwise")
    unit: str | None = Field(description="m, m2, m3, cm, mm, deg, percent, count, persons, ...")
    qualitative: str | None = Field(description="Prescription in words when there is no number, e.g. 'oriented east or southeast'")


class Rationale(BaseModel):
    concept: Concept
    text: str | None = Field(description="The WHY in one sentence. If stated=false this is your inference and must be phrased as such")
    stated: bool = Field(description="True ONLY if the source text itself gives this reason explicitly")


class Source(BaseModel):
    paragraph_ids: list[str] = Field(description="IDs of body-text paragraphs this comes from, e.g. page_0169_text_003")
    figure_ids: list[str] = Field(description="IDs of figures (captions) this comes from, e.g. page_0169_image_002")
    quote: str = Field(description="VERBATIM excerpt (<=200 chars) copied exactly from a paragraph, caption or table cell on this page that supports the intent")


class Intent(BaseModel):
    statement: str = Field(description="One self-contained normalized English sentence stating the rule, including the context it applies to")
    kind: Kind
    modality: Modality
    scope: Scope
    condition: Condition
    prescription: Prescription
    rationale: Rationale
    source: Source
    ifc_checkable: Checkable = Field(description="direct = computable from one element's geometry/properties; relational = needs relations between elements/spaces/storeys; not_checkable = material, colour, climate, process, taste")
    check_sketch: str | None = Field(description="One line: how a script would check this on an IFC model, or null if not_checkable")


class PageExtraction(BaseModel):
    page: str
    intents: list[Intent]
    notes: str | None = Field(description="Anything ambiguous on this page worth flagging to a human, or null")


# --- judge output ------------------------------------------------------------
# The judge does NOT re-emit full records (schema too large for constrained
# decoding). It references candidates by index and lists field corrections;
# Python assembles the final record.

Provenance = Literal["both", "A_only", "B_only"]


class FieldFix(BaseModel):
    path: str = Field(description="Dotted path into the intent record, e.g. 'prescription.op', 'rationale.stated', 'source.quote', 'statement'")
    value: str = Field(description="New value as a JSON literal string: numbers as 12.5, booleans as true/false, null as null, strings as plain text")


class Decision(BaseModel):
    a_index: int | None = Field(description="Index into the A candidate list (0-based) or null")
    b_index: int | None = Field(description="Index into the B candidate list (0-based) or null")
    prefer: Literal["A", "B"] = Field(description="Which candidate's record is the base for the merged intent")
    fixes: list[FieldFix] = Field(description="Corrections applied on top of the preferred record; empty if none")
    note: str | None = Field(description="Why merged/corrected, or null")


class Rejection(BaseModel):
    from_extractor: Literal["A", "B"]
    index: int
    reason: Literal["not_prescriptive", "hallucinated_quote", "wrong_page_scope", "too_vague", "other"]
    note: str | None


class PageJudgement(BaseModel):
    page: str
    decisions: list[Decision]
    rejected: list[Rejection]
    notes: str | None
