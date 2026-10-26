"""Declared grids as viewer line specs.

The viewer cannot draw a model's own IfcGrid: web-ifc 0.0.66 builds no mesh
for curves (it logs one "unexpected mesh type" per axis instead), and a tiled
model never runs web-ifc in the browser at all. So the axes are read here,
with declared_grid, and written as line specs (viewer/
views/lineSpec.js) into the model's line sidecar, where the viewer's "Lines"
button already looks (views/lineSidecar.js).

What is drawn, and why (measured 2026-10-06 on the 19 uploads that declare a
grid and on the corpus survey):
  - One line per merged axis, not per declared copy. Revit writes one IfcGrid
    copy per storey (1,445 grids in 265 models); drawing each would stack
    identical grids at every level, a median of 80 lines per model instead of
    17.
  - Storeys whose merged axes are identical form one variant, drawn once at
    the height of its lowest storey, with every storey it covers in the
    line's meta. A model whose storeys carry different grids (66 corpus
    models, all with different axis counts) gets one variant per distinct
    grid, so each extra variant shows where the grid changes.
  - A storey without a grid of its own is not drawn. declared_grid lends it
    the union of the model's grids ("borrowed") so grid words still work;
    drawn, that would be a grid the designer never placed there (at least 153
    storeys in 63 corpus models). It is listed in the sidecar's storey table
    with its source instead.
  - Colour follows the geometric family (declared_grid.assign_families),
    never the declared U/V/W list: Revit files axes parallel to U or V under
    WAxes (56 corpus models, 1,353 axes).
  - Height is given in IFC metres ({"ifcZ": z}, the grid placement's world z)
    and turned into scene Y by the viewer at draw time, because the scene
    shift is chosen when the model loads and depends on the host (T.y on
    4558d77b...: 6.06 m from web-ifc called directly, 1.90 m in the viewer)
    and cannot be known here.

Plan coordinates are declared_grid's world plan metres, the frame the
viewer's "ifcPlan" space expects: checked against web-ifc's own geometry to
1 mm on 4558d77b... (site rotated -9 degrees) and c99be381... (millimetres).

Determinism (docs/detectors.md rule 1): storeys in (elevation, GlobalId)
order, axes in declared_grid's id order, ids built from storey GUIDs and
axis tags.
"""

from ifc_units import placement_matrix, to_metres
from modality import declared_grid as dg

GRID_LINE_PREFIX = "grid:"
# Distinct from the detector lines' orange (#ff6a00, views/lineSpec.js) and
# from each other; families past the fifth reuse the last colour.
FAMILY_COLOURS = ("#2f80ed", "#16a394", "#9b51e0", "#d4a017", "#c2185b")
UNGROUPED_COLOUR = "#7f8c8d"  # curved axes have no family
LINE_WIDTH_PX = 2
LINE_OPACITY = 0.9
DRAWN_SOURCES = ("own", "building")
# Labels list at most this many storey names, then "+n".
LABEL_STOREYS = 3


def _r(value):
    return round(float(value), 3)


def storey_records(model, scale):
    """Every storey as {guid, name, elevation, z}, in (elevation, GlobalId)
    order. `elevation` is the Elevation attribute in metres, `z` the world z
    of the storey placement (the two agree on all 19 uploads)."""
    records = []
    for storey in model.by_type("IfcBuildingStorey"):
        elevation = to_metres(storey.Elevation, scale) if storey.Elevation is not None else None
        matrix = placement_matrix(storey, scale)
        z = float(matrix[2][3]) if matrix is not None else elevation
        records.append({"guid": storey.GlobalId, "name": storey.Name, "elevation": elevation, "z": z})
    records.sort(key=lambda s: (s["elevation"] if s["elevation"] is not None else 0.0, s["guid"]))
    return records


def grid_heights(model, scale):
    """{IfcGrid GlobalId: world z of its placement, metres}; grids without a
    resolvable placement are left out."""
    heights = {}
    for grid in model.by_type("IfcGrid"):
        matrix = placement_matrix(grid, scale)
        if matrix is not None:
            heights[grid.GlobalId] = float(matrix[2][3])
    return heights


def _signature(axes):
    return tuple((a["id"], tuple((_r(x), _r(y)) for x, y in a["points"])) for a in axes)


def grid_variants(grids, storeys, heights):
    """Group the storeys that draw identical axes. Returns (variants, table):
    variants in order of their lowest storey, each {id, storeys, z, axes,
    families}; table one row per storey, {guid, name, elevation, source,
    variant} with variant None when nothing is drawn for it."""
    variants, by_signature, table = [], {}, []
    for storey in storeys:
        axes, source = dg.active_axes(grids, storey["guid"])
        row = {"guid": storey["guid"], "name": storey["name"],
               "elevation": None if storey["elevation"] is None else _r(storey["elevation"]),
               "source": source, "variant": None}
        table.append(row)
        if source not in DRAWN_SOURCES or not axes:
            continue
        merged = dg.merge_axes(axes)
        families = dg.assign_families(merged)
        dg.mark_partial(merged, families)
        signature = _signature(merged)
        variant = by_signature.get(signature)
        if variant is None:
            own = [heights[g["guid"]] for g in grids
                   if g["storey"] == storey["guid"] and g["guid"] in heights]
            z = min(own) if own else storey["z"]
            variant = {"id": storey["guid"], "storeys": [], "z": z, "axes": merged, "families": families}
            by_signature[signature] = variant
            variants.append(variant)
        variant["storeys"].append({"guid": storey["guid"], "name": storey["name"]})
        row["variant"] = variant["id"]
    return variants, table


def _family_colour(family):
    if family is None:
        return UNGROUPED_COLOUR
    index = int(family[1:]) - 1
    return FAMILY_COLOURS[min(index, len(FAMILY_COLOURS) - 1)]


def _storey_label(storeys):
    names = [s["name"] or s["guid"] for s in storeys]
    if len(names) <= LABEL_STOREYS:
        return ", ".join(names)
    return ", ".join(names[:LABEL_STOREYS]) + f" +{len(names) - LABEL_STOREYS}"


def line_specs(variants, grid_names):
    """One line spec per axis per variant (views/lineSpec.js schema)."""
    specs = []
    for variant in variants:
        storey_text = _storey_label(variant["storeys"])
        for axis in variant["axes"]:
            names = sorted({grid_names.get(g) or g for g in axis["grids"]})
            tags = "/".join(axis["tags"]) or "?"
            label = f"Axis {tags} · {axis['family'] or 'curved'} · {', '.join(names)} · {storey_text}"
            if axis.get("partial"):
                label += " · partial"
            points = [[_r(x), _r(y)] for x, y in axis["points"]]
            specs.append({
                "id": f"{GRID_LINE_PREFIX}{variant['id']}:{axis['id']}",
                "kind": "segment" if len(points) == 2 else "polyline",
                "space": "ifcPlan",
                "points": points,
                "height": {"ifcZ": _r(variant["z"])},
                "style": {"color": _family_colour(axis["family"]), "width": LINE_WIDTH_PX, "opacity": LINE_OPACITY},
                "meta": {
                    "source": "IfcGrid",
                    "type": "declared_grid",
                    "label": label,
                    "tags": list(axis["tags"]),
                    "family": axis["family"],
                    "declaredFamilies": list(axis["declaredFamilies"]),
                    "partial": axis.get("partial"),
                    "grids": list(axis["grids"]),
                    "variant": variant["id"],
                    "storeys": [s["guid"] for s in variant["storeys"]],
                },
            })
    return specs


def model_grid_lines(model, scale):
    """Everything the sidecar needs for one model: (specs, summary)."""
    grids = dg.read_declared_grids(model, scale)
    storeys = storey_records(model, scale)
    variants, table = grid_variants(grids, storeys, grid_heights(model, scale))
    names = {g["guid"]: g["name"] for g in grids}
    specs = line_specs(variants, names)
    summary = {
        "grids": len(grids),
        "skippedAxes": sum(len(g["skippedAxes"]) for g in grids),
        "outsideStoreys": sum(1 for g in grids if g["storey"] is None),
        "variants": [{"id": v["id"], "z": _r(v["z"]), "axes": len(v["axes"]),
                      "families": {name: f["angleDeg"] for name, f in sorted(v["families"].items())},
                      "storeys": [s["guid"] for s in v["storeys"]]} for v in variants],
        "storeys": table,
    }
    return specs, summary
