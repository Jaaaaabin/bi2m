"""The class sweep that starts both fixture censuses, `furniture_occupancy`
and `sanitary_provision`, shared since 2026-10-09. Only this first step is
shared so far. The rest of the
proposed census engine (name classification, room assignment, per-storey
counts behind one table-driven call) is not built.

`elements_by_guid(model, classes)` returns every element of the given
classes once, as a GUID -> element dict in first-seen order. The
de-duplication is docs/detectors.md rule 3: `by_type()` returns subtypes, and
IfcFurniture and IfcSystemFurnitureElement are both IfcFurnishingElement, so
an unguarded sweep counted 144 beds in a file holding 72. A class name the file's
schema lacks raises RuntimeError in ifcopenshell and is skipped.
"""


def elements_by_guid(model, classes):
    by_guid = {}
    for ifc_class in classes:
        try:
            elements = model.by_type(ifc_class)
        except RuntimeError:
            continue
        for element in elements:
            by_guid[element.GlobalId] = element
    return by_guid
