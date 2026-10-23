"""Shared pure 3D IFC-shape math, reused across walls/columns/curtainwalls.

Distinct from `toolsQuickUtils`/`toolsSpatialGlue` (2D/planar point-and-line math for
grid generation) - these operate on raw ifcopenshell shapes/elements.
"""

import math

import numpy as np
import ifcopenshell.util.shape
from sklearn.decomposition import PCA


def calc_element_orientation(element, deg_range=360):

    if element.ObjectPlacement.RelativePlacement.RefDirection is None:
        return 0.0

    orientation_vec = element.ObjectPlacement.RelativePlacement.RefDirection.DirectionRatios
    orientation_rad = math.atan2(orientation_vec[1], orientation_vec[0])
    orientation_deg = math.degrees(orientation_rad) % deg_range

    return round(orientation_deg, 4)


def calc_element_orientation_from_reference_points(endpoint, midpoint, deg_range=360):

    p1 = np.array(endpoint)
    p2 = np.array(midpoint)

    direction_vector = p2 - p1
    angle_deg = math.degrees(math.atan2(direction_vector[1], direction_vector[0]))
    if angle_deg < 0:
        angle_deg += deg_range

    return angle_deg


def vertices2dimensions(vertices, deci=4):
    verts_array = np.array(vertices)
    x_range, y_range, z_range = np.ptp(verts_array, axis=0)
    length, width = max(x_range, y_range), min(x_range, y_range)
    height = z_range

    return {
        "length": round(length, deci),
        "width": round(width, deci),
        "height": round(height, deci),
    }


def vertices2dimensions_pca_advanced(vertices, deci=4):

    pca = PCA(n_components=3)
    pca.fit(vertices)

    transformed_points = pca.transform(vertices)

    max_transformed = np.max(transformed_points, axis=0)
    min_transformed = np.min(transformed_points, axis=0)

    dimensions = max_transformed - min_transformed

    sorted_dimensions = sorted(dimensions, reverse=True)

    max_z = np.max(vertices[:, 2])
    min_z = np.min(vertices[:, 2])
    max_distance_z = max_z - min_z

    height = min(sorted_dimensions, key=lambda x: abs(x - max_distance_z))

    sorted_dimensions.remove(height)

    length, width = sorted(sorted_dimensions, reverse=True)

    length_index = np.argmax(dimensions == length)
    length_vector = pca.components_[length_index]

    angle_rad = np.arctan2(length_vector[1], length_vector[0])
    angle_deg = np.degrees(angle_rad)

    return {
        "length": round(length, deci),
        "width": round(width, deci),
        "height": round(height, deci),
        "orientation": round(angle_deg, 4),
    }


def shape2_location_verts(shape):

    matrix = ifcopenshell.util.shape.get_shape_matrix(shape)
    location = matrix[:, 3][0:3]
    grouped_verts = ifcopenshell.util.shape.get_vertices(shape.geometry)
    return location, grouped_verts


def divide_unit(loc):
    """DEPRECATED (2026-09-22): a magnitude guess - divide by 1000 if any
    value exceeds 1000 - that assumed every file is metres or millimetres.
    Kept only so older callers import; new code converts with
    ifc_units.to_metres(loc, ifc_units.length_scale(model))."""

    for value in loc:
        if abs(value) > 1000:
            loc = tuple([value / 1000 for value in loc])
            break
        else:
            continue
    return loc
