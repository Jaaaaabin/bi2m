"""The 13 Neufert Topics as registry categories. Static: reads no file, so
registry.py can import it at any time (the YAML layers load on the first
detect(), rules.py).

Order is the Topics' first appearance in neufert_logic.md. `level` is the
largest spatial level among a Topic's cards (Site & Building -> building,
Storey and Zone -> storey, Space and Element -> room); the panel groups
these entries by `section` instead (intentPanel.js), so `level` stays an
honest claim-reach tag and nothing more.
"""

SECTION = "neufert"
# `scenario` (2026-10-20): the situation a card addresses is present in the model; the requirement
# itself may or may not be judged (records.scenario_record).
OUTCOMES = ("pass", "fail", "warn", "info", "nodata", "scenario")

# id suffix, the Topic string on the cards, level, the classes its bound
# rules select (pre-flight soft signals: absent -> "unlikely", still runs)
TOPICS = (
    ("site", "Site and massing", "building", ("IfcSite",)),
    ("rooms", "Habitable-room standards and area calculation", "building", ("IfcSpace",)),
    ("housing", "Housing: layout and entrance", "building", ("IfcSpace", "IfcDoor|IfcStair")),
    ("offices", "Offices", "building", ("IfcSpace", "IfcGrid|IfcCurtainWall|IfcCovering|IfcFurnishingElement|IfcFurniture")),
    ("highrise", "High-rise buildings", "building", ("IfcBuildingStorey",)),
    ("stairs", "Stairs, ramps, lifts and railings", "storey", ("IfcStairFlight", "IfcStair|IfcRamp|IfcRailing|IfcTransportElement")),
    ("accessibility", "Accessibility", "storey", ("IfcSpace", "IfcDoor", "IfcTransportElement|IfcRamp|IfcStair")),
    ("escape", "Escape and fire protection", "storey", ("IfcDoor", "IfcSpace|IfcWindow")),
    ("bedrooms", "Housing: bedrooms, bathrooms and storage", "storey", ("IfcSpace", "IfcSanitaryTerminal")),
    ("daylight", "Daylight, sunlight, ventilation and windows", "room", ("IfcSpace", "IfcWindow")),
    ("doors", "Doors", "room", ("IfcDoor",)),
    ("envelope", "Building envelope and thermal insulation", "room", ("IfcRoof|IfcSlab", "IfcWall|IfcCovering|IfcRoof")),
    ("walls", "Walls and construction", "room", ("IfcWall", "IfcColumn|IfcGrid|IfcCurtainWall|IfcCovering")),
)


def category_id(suffix):
    return f"{SECTION}_{suffix}"


def intent_types(suffix):
    return [f"{category_id(suffix)}_{outcome}" for outcome in OUTCOMES]


def topic_by_category(category_id_):
    for suffix, topic, level, classes in TOPICS:
        if category_id(suffix) == category_id_:
            return suffix, topic, level, classes
    raise KeyError(category_id_)
