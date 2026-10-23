"""Room-boundary-connection detection - one recognized group per IfcSpace,
listing the IfcWall elements linked to it via IfcRelSpaceBoundary.

Filtered to PHYSICAL boundaries whose RelatedBuildingElement is a wall -
VIRTUAL boundaries (no real building element, RelatedBuildingElement is
None) and non-wall physical boundaries (slabs, doors) are excluded. Verified
against data/test_3.ifc: IfcSpace "014 Office" resolves to exactly the 4
walls res/intent_groups.json's original hand-authored mock already
described, once its 3 non-wall boundaries (2 slabs, 1 door) are filtered out.

Works directly off the open ifcopenshell model - no dependency on the
extraction pipeline (`extracted` is accepted but unused), since IFC already
encodes this relationship natively via IfcRelSpaceBoundary.
"""

from collections import defaultdict

from ..intent import make_member, make_intent

WALL_CLASSES = ("IfcWall", "IfcWallStandardCase")
DEFAULT_MIN_MEMBERS = 2


def _space_label(space):
    """"014" + "Office" -> "014 Office" (room number + room name, the common
    Revit-export convention confirmed on data/test_3.ifc: Name="014",
    LongName="Office") - falls back to whichever of the two is present, or
    the GUID if neither is set."""
    parts = [part for part in (space.Name, space.LongName) if part]
    return " ".join(parts) or space.GlobalId


def detect(model, extracted, file_key, min_members=DEFAULT_MIN_MEMBERS):
    boundaries_by_space = defaultdict(list)
    for boundary in model.by_type("IfcRelSpaceBoundary"):
        boundaries_by_space[boundary.RelatingSpace.id()].append(boundary)

    intents = []
    for space in model.by_type("IfcSpace"):
        # Keep the wall entity itself, not just its GUID - `.is_a()` (its
        # concrete class, "IfcWall" or "IfcWallStandardCase") was already
        # resolved to build this filter; carrying the entity through means
        # make_member() below reuses that same value instead of re-deriving it.
        walls = [
            boundary.RelatedBuildingElement
            for boundary in boundaries_by_space.get(space.id(), [])
            if boundary.RelatedBuildingElement is not None
            and boundary.RelatedBuildingElement.is_a() in WALL_CLASSES
        ]
        if len(walls) < min_members:
            continue

        space_name = _space_label(space)

        intents.append(make_intent(
            intent_id=f"{file_key}-room-{space.GlobalId}",
            intent_type="connection_boundary_adjacency",
            label=f"Walls bounding space \"{space_name}\"",
            members=(
                [make_member(wall.GlobalId, role="member", ifc_class=wall.is_a()) for wall in walls]
                + [make_member(space.GlobalId, role="context", ifc_class="IfcSpace")]
            ),
            detector="connection",
            rule="space_boundary_walls",
            summary=f"{len(walls)} walls linked to IfcSpace \"{space_name}\" via IfcRelSpaceBoundary.",
            metrics={"boundaryRelationCount": len(walls)},
        ))

    return intents
