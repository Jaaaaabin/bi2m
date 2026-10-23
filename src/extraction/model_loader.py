"""IFC model loading, geometry settings, entity listing, and shared property lookups."""

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element


def configure_settings(type_geo):
    """Build ifcopenshell.geom.settings() for the given geometry read mode
    ('triangle' or 'brep')."""

    if type_geo == "triangle":
        settings = ifcopenshell.geom.settings()
        settings.USE_PYTHON_OPENCASCADE = True
        # only option to activate both triangulation and the generation of normals
        settings.DISABLE_TRIANGULATION = False
        settings.WELD_VERTICES = False
        settings.NO_NORMALS = False
        settings.GENERATE_UVS = True
        settings.S = False
        settings.USE_WORLD_COORDS = True

    elif type_geo == "brep":
        settings = ifcopenshell.geom.settings()
        settings.USE_PYTHON_OPENCASCADE = True
        settings.DISABLE_TRIANGULATION = True
        settings.USE_BREP_DATA = True
        settings.USE_WORLD_COORDS = True

    return settings


def extract_all_ifc_elements(model):
    """Extract the raw IFC entity lists this pipeline cares about. Returns a dict
    of element-type name -> list of IFC entities."""

    if not model:
        return {}

    return {
        "storeys": model.by_type("IfcBuildingStorey"),
        "slabs": model.by_type("IfcSlab"),
        "roofs": model.by_type("IfcRoof"),
        "st_columns": model.by_type("IfcColumn"),
        "walls": model.by_type("IfcWall") + model.by_type("IfcWallStandardCase"),
        "curtainwalls": model.by_type("IfcCurtainWall"),
        "plates": model.by_type("IfcPlate"),
        "members": model.by_type("IfcMember"),
    }


def get_file_prefix_code(filename):
    """First two '-'-separated segments of a filename, used as a short display prefix."""
    parts = filename.split("-")
    return "-".join(parts[:2])


def add_marks(model, existing_info_list):
    """Enrich each info dict with its IFC 'Mark' identity-data property, if present."""

    for element in existing_info_list:
        ifc_element = model.by_guid(element["id"])

        if ifc_element:
            identity_data = ifcopenshell.util.element.get_pset(ifc_element, "Identity Data")
            element["mark"] = identity_data.get("Mark", "") if identity_data else ""
        else:
            element["mark"] = ""

    return existing_info_list
