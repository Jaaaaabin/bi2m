"""Storey lookup and storey order, shared by the detectors since 2026-10-09.

`get_storey(element)` is the container-then-aggregate lookup: the storey
that contains the element (IfcRelContainedInSpatialStructure, through
ifcopenshell's `get_container`), else a storey that aggregates it directly
(IfcRelAggregates, read from `Decomposes`). Spaces need the second step: an
IfcSpace is aggregated to its storey, never contained, so `get_container`
alone resolves none of them (0 of 886 measured).

`get_storey(element, parent_container=True)` also asks for the container
of the element's aggregate parent. `thermal_envelope` and
`curtainwall_assembly` have always used that spelling, written for
curtain-wall panels, and keep it. `get_container` already climbs from a
panel to its curtain wall's storey on its own (ifcopenshell 0.8.5),
so the extra hop only changes the answer for an element
contained in a structure that is not a storey and also aggregated into a
part that has one.

Not folded in: the sites that call `get_container` alone (windows,
columns, furniture, fixtures, door points). Giving them the aggregate
fallback would change which elements they see, so they keep calling it
directly.

`ordered_storeys_with` sorts the storeys a detector found entries on by
`Elevation`, the order every cross-storey chain is built in. A storey whose
`Elevation` is None raises TypeError here exactly as it did in each copy
(none in the corpus).

The four verified detectors, `structural`, `alignment`, `connection` and
`vertical`, keep their own copies by decision: their code stays exactly as
verified (docs/detectors.md rule 7).
"""

import ifcopenshell.util.element


def get_storey(element, parent_container=False):
    storey = ifcopenshell.util.element.get_container(element, ifc_class="IfcBuildingStorey")
    if storey is not None:
        return storey
    for rel in element.Decomposes:
        relating = rel.RelatingObject
        if relating.is_a("IfcBuildingStorey"):
            return relating
        if parent_container:
            parent = ifcopenshell.util.element.get_container(relating, ifc_class="IfcBuildingStorey")
            if parent is not None:
                return parent
    return None


def ordered_storeys_with(entries_by_storey, model):
    """The storey GUIDs that key `entries_by_storey`, lowest elevation first."""
    storeys_sorted = sorted(model.by_type("IfcBuildingStorey"), key=lambda s: s.Elevation)
    storey_index = {s.GlobalId: i for i, s in enumerate(storeys_sorted)}
    return sorted(entries_by_storey, key=lambda guid: storey_index[guid])
