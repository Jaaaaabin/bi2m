"""Floor/slab raw extraction: IFC shapes -> info_floors.

Also covers IfcRoof (extract_roofs() below, added for
src/recognition/detectors/envelope.py) - but via its OWN reasoning
(_roof_footprint_edges), not _floorshape_reasoning() reused as-is:
_floorshape_reasoning() assumes a thin flat prism (a real flat slab) and
returns None for anything taller than 0.5m in Z, which real pitched/gable
roofs routinely are - confirmed directly: data/test_4.ifc's roof mesh spans
~7.9m in Z, data/test_5.ifc's ~5.4m (a genuine ridge/slope height, not a
coordinate artifact - that spread is a relative vertex-to-vertex quantity,
unaffected by whichever frame the raw mesh happens to be defined in)."""

import numpy as np
import ifcopenshell.util.shape
from shapely.geometry import MultiPoint

from ifc_units import length_scale, to_metres

from .geometry_iteration import iterate_shapes


def _floorshape_reasoning(shape):

    grouped_verts = ifcopenshell.util.shape.get_vertices(shape.geometry)
    grouped_faces = ifcopenshell.util.shape.get_faces(shape.geometry)

    locations_per_face = []
    for sublist in grouped_faces:
        new_sublist = [grouped_verts[i].tolist() for i in sublist]
        locations_per_face.append(new_sublist)
    locations_per_face = np.array(locations_per_face, dtype=object)
    all_z_values = np.array([vertex[2] for face in locations_per_face for vertex in face])
    z_min, z_max = np.min(all_z_values), np.max(all_z_values)

    floor_width = z_max - z_min
    if floor_width > 0.5:
        return None, None

    faces_side, faces_upper, faces_lower = [], [], []
    for face in locations_per_face:
        z_values = [vertex[2] for vertex in face]
        if len(set(z_values)) == 1:
            if z_values[0] == z_max:
                faces_upper.append(face)
            if z_values[0] == z_min:
                faces_lower.append(face)
        else:
            faces_side.append(face)

    floor_location_xy = []

    for f_side in faces_side:
        sliced_f = f_side[:, :2]

        keep_mask = np.ones(sliced_f.shape[0], dtype=bool)
        for i in range(sliced_f.shape[0]):
            for j in range(i + 1, sliced_f.shape[0]):
                if np.all(sliced_f[i] == sliced_f[j]):
                    keep_mask[j] = False
        xy_locations_per_face_s = sliced_f[keep_mask]
        floor_location_xy.append(xy_locations_per_face_s.tolist())

    # tempo intervention. dirty but works for now....
    floor_location_xy = [sublist for sublist in floor_location_xy if len(sublist) <= 2]

    return floor_width, floor_location_xy


def _add_values_to_points(points, add_values):
    if points is None:
        # _floorshape_reasoning's own "not a thin flat shape" outcome
        # (floor_width > 0.5) - a real, valid "no usable flat footprint"
        # result for this shape, not an error. Every regular slab checked so
        # far has stayed under that threshold, so this path was previously
        # unreachable in practice; a pitched/thick IfcRoof (extract_roofs()
        # below) hits it routinely, so it needs to actually propagate here
        # instead of crashing on `for outer_point in points`.
        return None
    updated_points = []
    for outer_point in points:
        updated_outer = []
        for point in outer_point:
            new_point = [
                point[0] + add_values[0],
                point[1] + add_values[1],
                add_values[2],
            ]
            updated_outer.append(new_point)
        updated_points.append(updated_outer)
    return updated_points


def get_floor_dimensions_non_ar(settings, model, floors, type_geo):
    """Extract floor dimensions for non-Autodesk-Revit-authored models."""

    info_floors = []
    for shape in iterate_shapes(settings, model, floors, type_geo):
        floor_width, floor_location_xy = _floorshape_reasoning(shape)

        tempo_matrix = ifcopenshell.util.shape.get_shape_matrix(shape)
        tempo_location = tempo_matrix[:, 3][0:3]
        floor_location_xy = _add_values_to_points(floor_location_xy, tempo_location)

        info_floors.append({
            "id": shape.guid,
            "location": floor_location_xy,
            "width": floor_width,
            "elevation": tempo_location[-1],
        })

    return info_floors


def get_floor_dimensions_ar(settings, model, floors, type_geo):
    """Extract floor dimensions for Autodesk-Revit-authored models."""

    info_floors = []
    for shape in iterate_shapes(settings, model, floors, type_geo):
        floor_width, floor_location_xy = _floorshape_reasoning(shape)

        info_floors.append({
            "id": shape.guid,
            "location": floor_location_xy,
            "width": floor_width,
        })

    return info_floors


def _update_floor_info(floor, info_f):

    # The parent placement's z is in the file's own unit; convert with the
    # declared unit (ifc_units) instead of the old "divide by 1000 if it
    # exceeds 100" guess, which read a 350 cm storey as 0.35 m.
    floor_elevation = to_metres(
        floor.ObjectPlacement.PlacementRelTo.RelativePlacement.Location.Coordinates[-1],
        length_scale(floor.file),
    )

    for lcs in info_f["location"]:
        for lc in lcs:
            lc.append(floor_elevation)

    info_f.update({"elevation": round(floor_elevation, 4)})
    return info_f


def enrich_floor_information(floors, info_floors):
    """Add elevation (from IFC placement) to each floor already extracted via the
    AR path. Drops entries with no usable width/location."""

    id_to_floor = {f.GlobalId: f for f in floors}
    return [
        _update_floor_info(id_to_floor[info["id"]], info)
        for info in info_floors
        if info["id"] in id_to_floor and info["width"] is not None and info["location"] is not None
    ]


def extract_floors(settings, model, floors, type_geo, authoring_tool):
    """Extract info_floors for `floors`, branching on authoring tool."""

    if authoring_tool != "ar":
        return get_floor_dimensions_non_ar(settings, model, floors, type_geo)
    else:
        info_floors = get_floor_dimensions_ar(settings, model, floors, type_geo)
        return enrich_floor_information(floors, info_floors)


def resolve_roof_geometry_sources(roofs):
    """element -> owning IfcRoof, for whichever entity actually carries
    Body geometry - itself, or (if IfcRoof.Representation is None) a
    decomposed child with its own Representation. The exact same
    dual-strategy split curtainwalls.py's extract_curtainwalls() already
    uses for IfcCurtainWall, confirmed necessary here too by direct
    inspection across data/*.ifc:
    - data/test_4.ifc, data/test_2.ifc: Body geometry sits directly
      on the IfcRoof entity.
    - data/test_5.ifc, data/test_7.ifc: IfcRoof.Representation is None;
      geometry instead sits on its own IfcRelAggregates-decomposed child
      IfcSlab entities.
    - data/test_3.ifc: neither - Representation is None AND its single
      IfcRelAggregates relationship aggregates nothing (RelatedObjects is
      empty). A genuinely empty/broken roof export, not a bug in this
      function - that roof is correctly absent from the returned dict, the
      same way a shape with no usable geometry is absent from
      iterate_shapes()'s own output."""
    source_to_roof = {}
    for roof in roofs:
        if roof.Representation is not None:
            source_to_roof[roof] = roof
            continue
        for rel in roof.IsDecomposedBy:
            for child in rel.RelatedObjects:
                if getattr(child, "Representation", None) is not None:
                    source_to_roof[child] = roof
    return source_to_roof


def _roof_footprint_edges(shape):
    """The roof's flat plan-view outline, as the same "list of 2-point XY
    edges" shape _floorshape_reasoning produces for a real flat slab - but
    derived as the 2D convex hull of the roof's own triangulated vertices
    projected onto XY, since a pitched/gabled roof has no flat top/side/
    bottom faces for _floorshape_reasoning's approach to find (see module
    docstring). A convex hull is coarser (a dormer notch or bay recess
    would be filled in) but is the right trade for "does the roof's own
    outer extent still line up with the floor below" - the only thing
    envelope.py's continuity check needs. None if the projected points are
    degenerate (collinear/near-zero-area - shapely's convex_hull then
    returns a Point/LineString, not a Polygon)."""
    verts = ifcopenshell.util.shape.get_vertices(shape.geometry)
    hull = MultiPoint(verts[:, :2].tolist()).convex_hull
    if not hasattr(hull, "exterior"):
        return None
    ring = list(hull.exterior.coords)
    return [[list(ring[i]), list(ring[i + 1])] for i in range(len(ring) - 1)]


def get_roof_dimensions(settings, model, roofs, type_geo):
    """Roof counterpart to get_floor_dimensions_non_ar() - same shape ->
    world-XY-edges pipeline (triangulate, then offset by the shape's own
    get_shape_matrix() translation - the same manual re-application
    get_floor_dimensions_non_ar() already needs, since get_vertices()
    resolves to a shape-local frame regardless of USE_WORLD_COORDS), but
    using _roof_footprint_edges() instead of _floorshape_reasoning() to
    actually get the outline in the first place. No AR/non-AR branch:
    unlike floors.py's original slab-only pipeline, this has only ever
    been checked against the shape-matrix-translation approach - a second,
    AR-specific elevation source was never confirmed necessary for roofs."""
    info_roofs = []
    for shape in iterate_shapes(settings, model, roofs, type_geo):
        tempo_matrix = ifcopenshell.util.shape.get_shape_matrix(shape)
        tempo_location = tempo_matrix[:, 3][0:3]
        edges = _roof_footprint_edges(shape)
        if edges is not None:
            edges = _add_values_to_points(edges, tempo_location)
        info_roofs.append({
            "id": shape.guid,
            "location": edges,
            "elevation": round(tempo_location[-1], 4),
        })
    return info_roofs


def extract_roofs(settings, model, roofs, type_geo):
    """Resolves each roof's real geometry source (see
    resolve_roof_geometry_sources), runs get_roof_dimensions() against
    those sources, then remaps each result's "id" back from the geometry
    source's own GUID to its owning IfcRoof's GUID - callers (and the
    frontend's Refer/highlight-by-GUID flow) should key on the roof
    itself, the conceptual "member", exactly as circulation.py's stair
    members are keyed on the parent IfcStair even when its anchor point
    had to be resolved via a child IfcStairFlight. Drops entries with no
    usable footprint (see _roof_footprint_edges)."""
    source_to_roof = resolve_roof_geometry_sources(roofs)
    info_roofs = get_roof_dimensions(settings, model, list(source_to_roof), type_geo)
    for info in info_roofs:
        source = model.by_guid(info["id"])
        info["id"] = source_to_roof[source].GlobalId
    return [info for info in info_roofs if info["location"] is not None]
