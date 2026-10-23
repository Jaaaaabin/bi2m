"""Column raw extraction: IFC shapes -> info_st_columns.

The original `_get_location_column` carried a large commented-out "old version"
block alongside the active code; dropped here (git history preserves it), keeping
only the active direct-placement fallback path.
"""

from .geometry_iteration import iterate_shapes
import ifcopenshell.util.element

from ifc_units import length_scale, to_metres

from .geometry_math import shape2_location_verts, vertices2dimensions


def get_column_dimensions(settings, model, st_columns, type_geo):

    info_st_columns = []
    for shape in iterate_shapes(settings, model, st_columns, type_geo):
        column_location_p1, grouped_verts = shape2_location_verts(shape)
        column_dimensions = vertices2dimensions(grouped_verts)
        column_location_p1 = column_location_p1.tolist()

        dict_of_a_column = {
            "id": shape.guid,
            "location": [column_location_p1],
        }
        dict_of_a_column.update(column_dimensions)
        info_st_columns.append(dict_of_a_column)

    return info_st_columns


def _get_location_column(column):

    c_location_pt_from_body = None

    for r in column.Representation.Representations:
        if r.RepresentationIdentifier == "Body":
            if hasattr(r.Items[0], "MappingSource"):
                mapped_r = r.Items[0].MappingSource.MappedRepresentation
                if hasattr(mapped_r.Items[0], "Position"):
                    c_location_pt_from_body = mapped_r.Items[0].Position.Location.Coordinates
                    break  # Assuming we only need the first matching 'Body'
            else:
                continue

    # directly use the "rel_storey_elevation" as the point location z value.
    if c_location_pt_from_body is None or (
        abs(c_location_pt_from_body[0]) < 0.001 and abs(c_location_pt_from_body[1]) < 0.001
    ):
        c_location_pt_directplacement = column.ObjectPlacement.RelativePlacement.Location.Coordinates
        # The parent placement usually places the storey, but not always:
        # tumgni_all/0386.ifc places its columns relative to the IfcBuilding,
        # which has no Elevation and used to abort the whole extraction.
        placed = column.ObjectPlacement.PlacementRelTo.PlacesObject
        rel_storey_elevation = getattr(placed[0], "Elevation", None) if placed else None
        if rel_storey_elevation is None:
            storey = ifcopenshell.util.element.get_parent(column, ifc_class="IfcBuildingStorey")
            rel_storey_elevation = getattr(storey, "Elevation", None) if storey is not None else None
        if rel_storey_elevation is None:
            rel_storey_elevation = 0.0
        rel_placement = column.ObjectPlacement.PlacementRelTo.RelativePlacement.Location.Coordinates
        c_location_pt_directplacement = tuple(
            sum(x) for x in zip(c_location_pt_directplacement, rel_placement))
        c_location_pt_directplacement = c_location_pt_directplacement[:2] + (rel_storey_elevation,)
        return c_location_pt_directplacement
    else:
        return c_location_pt_from_body


def _update_column_info(column, info_c, scale):

    # Raw placement / mapped-item coordinates are in the file's own unit;
    # `scale` (ifc_units.length_scale) converts them to metres, replacing the
    # old divide_unit() guess of "millimetres if any value exceeds 1000",
    # which was wrong for centimetre, foot and georeferenced files.
    column_location_p1 = to_metres(_get_location_column(column), scale)

    column_location_p2 = column_location_p1[:2] + (column_location_p1[2] + info_c["height"],)

    info_c.update({
        "elevation": round(column_location_p1[-1], 3),
        "location": [column_location_p1, column_location_p2],
    })

    return info_c


def enrich_column_information(st_columns, info_st_columns):
    id_to_column = {c.GlobalId: c for c in st_columns}
    scale = length_scale(st_columns[0].file) if st_columns else 1.0
    return [
        _update_column_info(id_to_column[info["id"]], info, scale)
        for info in info_st_columns
        if info["id"] in id_to_column and info["height"] is not None
    ]


def extract_columns(settings, model, st_columns, type_geo):
    """Raw column extraction + enrichment. Returns info_st_columns."""
    info_st_columns = get_column_dimensions(settings, model, st_columns, type_geo)
    return enrich_column_information(st_columns, info_st_columns)
