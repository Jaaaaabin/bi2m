"""Horizontal circulation detection - IfcSpace instances on ONE storey whose
own Name/LongName identifies them as a movement path (corridor, hall,
lobby, ...) rather than an occupied room, grouped one intent per storey.

circulation.py's counterpart at scope="storey" instead of "vertical" - the
same alignment.py/structural.py split. That detector (now labeled "Vertical
Circulation" - see registry.py) chains real IfcStair/IfcRamp entities
moving BETWEEN storeys; this one flags IfcSpace instances that carry people
WITHIN one storey. Distinct concepts, not two views of the same thing - a
building can have plenty of one without the other (a single-storey building
has horizontal circulation but no vertical circulation at all).

Signal: keyword match on Name/LongName, the same convention vertical.py's
own `_is_circulation` already uses for its "critical" flag (there: stair/
elevator/lift/shaft/escalator/ramp; here: corridor/hall/lobby/foyer/
vestibule/passage/aisle) - a naming-convention-dependent signal, so
coverage varies by file the same way vertical.py's "critical" flag already
does. Confirmed directly across every real file: data/test_3.ifc has 25
explicitly-named corridor/lobby spaces (grouping into one intent per
storey, ~6-7 spaces each across its 4 storeys); data/test_1.ifc and
data/test_2.ifc each have 5 spaces named "Hall"; data/test_4.ifc and
data/test_5.ifc have none at all under this keyword set (their own space
names - "Common Area", "Open Office Area" - don't unambiguously mean
"movement path" the way "Corridor"/"Hall"/"Lobby" do, so they're
deliberately NOT included; a real gap in that file's own naming, not a
bug). A geometry-based fallback (e.g. flagging a space with an unusually
high door-connectivity degree as a likely circulation hub even without a
helpful name) is a plausible next step, not built here - it risks
false-positiving on a genuinely large shared room (an open-plan office, a
cafeteria) that just happens to have several doors, which a name-based
signal never does.
"""

from collections import defaultdict


from ..access_graph import space_label
from ..intent import make_member, make_intent
from ..storeys import get_storey
from .. import vocabulary

# The words live in recognition/vocabulary.py since 2026-10-08 (one table with
# a language column; its docstring has the 2026-09-23 history: "hall" also
# matching "hallway", the library's German and misspelled names). The name
# stays as a reference for readers of this module.
HORIZONTAL_CIRCULATION_KEYWORDS = vocabulary.words("horizontal_circulation")


def _is_horizontal_circulation(space):
    # Name, LongName and the space type's name (vocabulary.space_text).
    return vocabulary.matches(vocabulary.space_text(space), "horizontal_circulation")


def detect(model, extracted, file_key):
    spaces = model.by_type("IfcSpace")
    if not spaces:
        return []

    by_storey = defaultdict(list)
    for space in spaces:
        if not _is_horizontal_circulation(space):
            continue
        storey = get_storey(space)
        if storey is not None:
            by_storey[storey.GlobalId].append(space)

    intents = []
    for storey_guid, storey_spaces in by_storey.items():
        storey = model.by_guid(storey_guid)
        storey_name = storey.Name or storey.GlobalId
        space_names = [space_label(space) for space in storey_spaces]

        intents.append(make_intent(
            intent_id=f"{file_key}-circh-{storey_guid}",
            intent_type="circulation_horizontal_space",
            label=f"Horizontal circulation: {storey_name} ({len(storey_spaces)} spaces)",
            members=[make_member(space.GlobalId, role="member", ifc_class="IfcSpace") for space in storey_spaces],
            detector="circulation_horizontal",
            rule="space_name_circulation_keyword",
            summary=(
                f"{len(storey_spaces)} IfcSpace instances on {storey_name} are named as a movement "
                f"path rather than an occupied room ({', '.join(space_names)})."
            ),
            related_guids=[storey_guid],
            metrics={"storey": storey_name, "spaceCount": len(storey_spaces), "spaceNames": space_names},
        ))
    return intents
