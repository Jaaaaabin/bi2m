"""Curtain wall extraction: two independent strategies (sub-element assembly vs.
single Body representation), selected per-element by what the IFC authoring tool
actually provided.
"""

import math

import numpy as np
import ifcopenshell.geom
import ifcopenshell.util.shape

from toolsQuickUtils import get_rectangle_corners, distance_between_points, find_most_common_value

from .geometry_iteration import iterate_shapes
from .geometry_math import (
    calc_element_orientation,
    calc_element_orientation_from_reference_points,
    shape2_location_verts,
    vertices2dimensions,
    vertices2dimensions_pca_advanced,
)


def process_curtainwall_subelements(plates, members):
    """Precompute per-GUID orientation lookups for plates/members."""

    id2orientation_plates = {plate.GlobalId: calc_element_orientation(plate) for plate in plates}
    id2orientation_members = {member.GlobalId: calc_element_orientation(member) for member in members}
    return id2orientation_plates, id2orientation_members


def _process_ifc_members(settings, model, cw_related_members, type_geo):
    member_z_location_per_cw = []
    for shape in iterate_shapes(settings, model, cw_related_members, type_geo):
        location, _ = shape2_location_verts(shape)
        member_z_location_per_cw.append(list(location)[-1])
    return min(member_z_location_per_cw) if member_z_location_per_cw else None


def _calculate_plate_locations(location, dimensions, orientation_deg):

    location_p_center = location.tolist()
    location_p1 = [
        location_p_center[0] - 0.5 * dimensions["length"] * math.cos(math.radians(orientation_deg)),
        location_p_center[1] - 0.5 * dimensions["length"] * math.sin(math.radians(orientation_deg)),
        location_p_center[2],
    ]
    location_p2 = [
        location_p_center[0] + 0.5 * dimensions["length"] * math.cos(math.radians(orientation_deg)),
        location_p_center[1] + 0.5 * dimensions["length"] * math.sin(math.radians(orientation_deg)),
        location_p_center[2],
    ]
    location_p3 = location_p1[:2] + [location_p1[2] + dimensions["height"]]
    location_p4 = location_p2[:2] + [location_p2[2] + dimensions["height"]]
    return [location_p1, location_p2, location_p3, location_p4]


def _process_ifc_plates(settings, model, cw_related_plates, type_geo, id2orientation_plates):

    plate_location_per_cw, plate_orientation_per_cw = [], []
    plate_width_per_cw, plate_z_ranges_per_cw = [], []

    for shape in iterate_shapes(settings, model, cw_related_plates, type_geo):
        location, grouped_verts = shape2_location_verts(shape)
        dimensions = vertices2dimensions(grouped_verts)
        orientation_deg = id2orientation_plates[shape.guid]
        plate_locations = _calculate_plate_locations(location, dimensions, orientation_deg)
        plate_location_per_cw.extend(plate_locations)
        plate_orientation_per_cw.append(orientation_deg)
        plate_width_per_cw.append(dimensions["width"])
        plate_z_values = [sublist[2] for sublist in plate_locations]
        plate_z_ranges_per_cw.extend([min(plate_z_values), max(plate_z_values)])

    return plate_location_per_cw, plate_orientation_per_cw, plate_width_per_cw, plate_z_ranges_per_cw


def _get_closest_points_to_elevation(corner_points, elevation):
    corner_points = np.array(corner_points)
    differences = np.abs(corner_points[:, 2] - elevation)
    sorted_indices = np.argsort(differences)
    closest_indices = sorted_indices[:2]
    return [corner_points[idx].tolist() for idx in closest_indices]


def _adjust_curtainwall_z_location(wall_location_p1, wall_dimensions, wall_location_centroid):

    half_h = wall_dimensions["height"] * 0.5
    if abs(wall_location_p1[-1] - wall_location_centroid[-1]) > 0.5:  # tempo hard-coded threshold value.
        wall_location_p1[-1] = round(wall_location_centroid[-1] - half_h, 6)

    return wall_location_p1


def _get_curtainwall_dimensions(settings, curtainwall_element, info_curtainwalls):

    shape = ifcopenshell.geom.create_shape(settings, curtainwall_element)
    wall_location_p1, grouped_verts = shape2_location_verts(shape)

    wall_location_p1 = wall_location_p1.tolist()
    location_centroid = ifcopenshell.util.shape.get_shape_bbox_centroid(shape, shape.geometry)
    wall_dimensions = vertices2dimensions_pca_advanced(grouped_verts)

    wall_location_p1 = _adjust_curtainwall_z_location(wall_location_p1, wall_dimensions, location_centroid)
    wall_orientation = calc_element_orientation_from_reference_points(wall_location_p1, location_centroid)
    orientation_in180 = wall_orientation - 180 if wall_orientation >= 180 else wall_orientation

    wall_location_p2 = (
        wall_location_p1[0] + wall_dimensions["length"] * math.cos(math.radians(wall_orientation)),
        wall_location_p1[1] + wall_dimensions["length"] * math.sin(math.radians(wall_orientation)),
        wall_location_p1[2],
    )

    dict_of_a_curtainwall = {
        "id": shape.guid,
        "elevation": round(wall_location_p1[-1], 4),
        "location": [wall_location_p1, wall_location_p2],
        "orientation": orientation_in180,
    }

    dict_of_a_curtainwall.update(wall_dimensions)
    info_curtainwalls.append(dict_of_a_curtainwall)


def _process_curtainwall_with_sub_elements(settings, model, cw, type_geo, info_curtainwalls,
                                            id2orientation_plates, deci=4):

    cw_related_objects = cw.IsDecomposedBy[0].RelatedObjects
    cw_related_members = [ob for ob in cw_related_objects if ob.is_a("IfcMember")]
    cw_related_plates = [ob for ob in cw_related_objects if ob.is_a("IfcPlate")]

    min_z_per_cw = _process_ifc_members(settings, model, cw_related_members, type_geo)
    plate_location_per_cw, plate_orientation_per_cw, plate_width_per_cw, plate_z_ranges_per_cw = \
        _process_ifc_plates(settings, model, cw_related_plates, type_geo, id2orientation_plates)

    cw_corner_points = get_rectangle_corners(plate_location_per_cw)
    cw_elevation = min(pt[2] for pt in cw_corner_points)
    cw_location = [pt.tolist() for pt in cw_corner_points if pt[2] == cw_elevation]
    cw_height = max(plate_z_ranges_per_cw) - min(plate_z_ranges_per_cw)

    if len(cw_location) < 2:
        cw_location = _get_closest_points_to_elevation(cw_corner_points, cw_elevation)

    cw_length = distance_between_points(cw_location[0], cw_location[1])
    cw_width = find_most_common_value(plate_width_per_cw)[0]
    cw_orientation = find_most_common_value(plate_orientation_per_cw)[0]

    if min_z_per_cw is not None and min_z_per_cw < cw_elevation:
        cw_elevation = min_z_per_cw
        for sub_loc in cw_location:
            sub_loc[-1] = cw_elevation

    info_curtainwalls.append({
        "id": cw.GlobalId,
        "elevation": round(cw_elevation, deci),
        "location": cw_location,
        "height": round(cw_height, deci),
        "length": cw_length,
        "width": round(cw_width, deci),
        "orientation": cw_orientation % 180.0,
    })


def _process_curtainwall_with_representation(settings, cw, info_curtainwalls):
    if hasattr(cw.Representation, "Representations"):
        for r in cw.Representation.Representations:
            if r.RepresentationIdentifier == "Body":
                _get_curtainwall_dimensions(settings, cw, info_curtainwalls)
                break


def extract_curtainwalls(settings, model, curtainwalls, plates, members, type_geo):
    """Extract info_curtainwalls, picking per-element the sub-elements strategy
    (IfcMember/IfcPlate decomposition) or the single-Body-representation strategy.

    Note: preserves the original's loop-level try/except - an exception on any one
    curtainwall aborts processing of the remaining ones in the list (not per-element).
    """

    id2orientation_plates, _ = process_curtainwall_subelements(plates, members)

    info_curtainwalls = []
    try:
        for cw in curtainwalls:
            if hasattr(cw, "IsDecomposedBy") and len(cw.IsDecomposedBy) == 1 and cw.IsDecomposedBy[0].is_a("IfcRelAggregates"):
                _process_curtainwall_with_sub_elements(
                    settings, model, cw, type_geo, info_curtainwalls, id2orientation_plates)
            elif hasattr(cw, "Representation"):
                _process_curtainwall_with_representation(settings, cw, info_curtainwalls)
            else:
                print(f"Attribute check failed for IfcCurtainWall with guid {cw.GlobalId}.")
    except Exception as e:
        print(f"An error occurred: {str(e)}")

    return info_curtainwalls
