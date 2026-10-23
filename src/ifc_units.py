"""Length units, resolved once per model and applied wherever a raw IFC
coordinate enters this codebase.

The convention this module enforces (docs/detectors.md "Writing a detector",
rule 13): **every coordinate handled in src/ is metres.** Three sources
feed coordinates in, and only one of them is already metres:

    ifcopenshell.geom shapes (extraction.geometry_iteration.iterate_shapes)
        -> METRES. IfcOpenShell converts to SI unless CONVERT_BACK_UNITS is
           set, and model_loader.configure_settings never sets it.
    ifcopenshell.util.placement.get_local_placement(ObjectPlacement)
        -> PROJECT UNITS. Millimetres in 133 of the 518 tumgni_all models,
           centimetres in 13, feet in 2 (scripts/input_survey.py, 2026-09-22).
    raw attributes: IfcBuildingStorey.Elevation, IfcWindow.OverallHeight,
    IfcCartesianPoint.Coordinates read off an entity
        -> PROJECT UNITS.

Before this module existed, ten categories compared placement points in
project units against footprints in metres (on a
millimetre model every door "reaches" zero rooms and the whole AccessGraph
family emits confident false negatives), and the extraction package guessed
the unit from the magnitude of the numbers (`geometry_math.divide_unit`:
divide by 1000 if any coordinate exceeds 1000; `floors._update_floor_info`:
divide by 1000 if the elevation exceeds 100) - right for metre and
millimetre files with ordinary coordinates, wrong for centimetres, feet, and
georeferenced metre files.

`length_scale(model)` reads the unit the file actually assigns
(IfcProject.UnitsInContext, through ifcopenshell.util.unit, which also
resolves conversion-based units such as feet) and never raises: an
unresolvable unit is 1.0, the same assumption the code made implicitly
before. `to_metres` divides by the exact integer when the scale is an SI
prefix (1000 for millimetres, 100 for centimetres) rather than multiplying
by 0.001, so a millimetre file converted here is bit-identical to what the
old `/ 1000` produced and a metre file is untouched (`x / 1 == x`). Ids
built from these coordinates therefore do not move on any file the old
code handled correctly; they change only where the old code was wrong.
"""

import ifcopenshell.util.placement
import ifcopenshell.util.unit

# How close 1/scale must be to an integer to divide by that integer instead
# of multiplying by the float scale. SI prefixes give 1000.0 or 100.0 to the
# last bit; a conversion factor such as 1/0.3048 = 3.2808... does not.
_EXACT_INVERSE_TOLERANCE = 1e-9

# For labels and metrics: which unit a scale corresponds to.
_UNIT_NAMES = {1.0: "m", 0.1: "dm", 0.01: "cm", 0.001: "mm"}


def length_scale(model):
    """Metres per project length unit: 1.0 for a metre file, 0.001 for
    millimetres, 0.01 for centimetres, 0.3048 for feet. 1.0 when the file
    declares no usable length unit, which is what every caller assumed
    before this helper existed."""
    try:
        scale = ifcopenshell.util.unit.calculate_unit_scale(model)
    except Exception:  # noqa: BLE001 - a malformed unit assignment must not take a detector down
        return 1.0
    try:
        scale = float(scale)
    except (TypeError, ValueError):
        return 1.0
    if scale <= 0 or scale != scale:  # zero, negative or NaN
        return 1.0
    return scale


def unit_name(scale):
    """'m' / 'cm' / 'mm' / 'dm' for SI prefixes, otherwise 'x<scale>' (e.g. 'x0.3048')."""
    for value, name in _UNIT_NAMES.items():
        if abs(scale - value) <= _EXACT_INVERSE_TOLERANCE * max(1.0, value):
            return name
    return f"x{scale:g}"


def to_metres(value, scale):
    """Convert one number or a sequence of numbers from project units to
    metres. Exact division for SI prefixes (see module docstring), plain
    multiplication otherwise. `None` passes through as `None`."""
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return type(value)(to_metres(v, scale) for v in value)
    if scale == 1.0:
        return float(value)
    inverse = 1.0 / scale
    rounded = round(inverse)
    if rounded and abs(inverse - rounded) < _EXACT_INVERSE_TOLERANCE * rounded:
        return float(value) / rounded
    return float(value) * scale


def placement_matrix(element, scale):
    """The element's resolved 4x4 placement with its translation in metres,
    or `None` when the element has no ObjectPlacement or the chain cannot
    be resolved. get_local_placement(None) returns the identity matrix,
    i.e. a phantom element at the origin - the reason this guard exists
    (a cluster of four placement-less windows at (0, 0))."""
    placement = getattr(element, "ObjectPlacement", None)
    if placement is None:
        return None
    try:
        matrix = ifcopenshell.util.placement.get_local_placement(placement)
    except Exception:  # noqa: BLE001 - a broken placement chain is "no placement", not a crash
        return None
    if matrix is None:
        return None
    matrix = matrix.copy()
    for row in range(3):
        matrix[row][3] = to_metres(matrix[row][3], scale)
    return matrix


def placement_xyz(element, scale):
    """(x, y, z) of the element's placement origin in metres, or `None`."""
    matrix = placement_matrix(element, scale)
    if matrix is None:
        return None
    return (float(matrix[0][3]), float(matrix[1][3]), float(matrix[2][3]))


def placement_xy(element, scale):
    """(x, y) of the element's placement origin in metres, or `None`. The
    one call every plan-view detector should make instead of reading
    get_local_placement directly."""
    point = placement_xyz(element, scale)
    return None if point is None else point[:2]
