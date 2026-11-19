"""The Neufert section's rules as registry categories (2026-10-28): the rules
the Neufert QA Workbench's Rules pilot marks final, one category per rule.
Static: reads no file, so registry.py can import it at any time (the YAML
layers load on the first detect(), rules.py).
"""

SECTION = "neufert"
# `scenario` (2026-10-20): the situation a card addresses is present in the model; the requirement
# itself may or may not be judged (records.scenario_record).
JUDGED_OUTCOMES = ("pass", "fail", "warn", "info", "nodata", "scenario")
# 2026-10-29 (Wu): the section selects the elements each rule may concern and judges nothing; the
# families stay built and tested behind this switch (engine.run_rule), a later second step.
JUDGE = False
OUTCOMES = JUDGED_OUTCOMES if JUDGE else ("scenario",)

# RID, the card's title, level (an element or space rule -> room, a storey
# rule -> storey; the panel groups by `section`, so `level` stays an honest
# claim-reach tag), the classes its selection reads, its subject first
# (pre-flight soft signals: absent -> "unlikely", still runs). RID order.
RULES = (
    ("R04", "Number of steps per flight and landings for legally essential stairs", "storey", ("IfcStair",)),
    ("R05", "Width and riser/tread ratio of legally essential stairs", "storey", ("IfcStair",)),
    ("R07", "Door clear height and accessible clear width", "room", ("IfcDoor",)),
    ("R10", "Natural lighting depth", "room", ("IfcSpace", "IfcWindow|IfcCurtainWall")),
    ("R24", "Legally essential stairs: enclosed stairwell, exit width, doors opening into the stairwell", "storey", ("IfcSpace", "IfcStair|IfcDoor")),
    ("R25", "Dimensional limits for legally essential stairs (non-residential)", "storey", ("IfcStair",)),
    ("R43", "Door type and width of emergency exits", "room", ("IfcDoor",)),
    ("R44", "External windows of heated rooms at least double/insulating glazing", "room", ("IfcWindow|IfcCurtainWall",)),
    ("R56", "Minimum dimensions of non-essential (additional) stairs", "storey", ("IfcStair",)),
)


def category_id(rid):
    return f"{SECTION}_{rid.lower()}"


def intent_types(rid):
    return [f"{category_id(rid)}_{outcome}" for outcome in OUTCOMES]
