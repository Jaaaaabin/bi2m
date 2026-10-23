"""Survey the declared grids (IfcGrid) of a set of IFC models, without
computing any element geometry. One JSON row per model.

    uv run python scripts/grid_survey.py $BI2M_IFC_CORPUS --out survey.jsonl

Read-only: models are opened in place with ifcopenshell (only grid axis
curves are evaluated), and nothing is written next to them.

Per grid: what contains it (a storey, the building, the site, nothing), its
PredefinedType, axis counts per U/V/W list, the curve types of its axes (an
IfcArcIndex segment or a trimmed circle counts as an arc), and the axis
directions in the BUILDING frame - the grid placement composed against the
building placement, so a rotated site (true north) does not read as a rotated
grid. Per model: exporter (IfcApplication), schema, storeys, the number of
distinct grids (by geometry), whether storeys carry different grids, and a
shape class:
  none          no IfcGrid
  orthogonal    two families at 0 and 90 degrees in the building frame
  rotated       two perpendicular families at another angle
  oblique       two families not at 90 degrees, or more than two families
  curved        at least one axis is an arc or another curve
Partial axes are counted per grid: an axis shorter than 90 % of the longest
axis of its own family.
"""

import argparse
from collections import Counter
import hashlib
import json
import math
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

import ifcopenshell  # noqa: E402
import ifcopenshell.geom  # noqa: E402
import ifcopenshell.util.element  # noqa: E402
import numpy as np  # noqa: E402

from file_identity import resolve_file_identity  # noqa: E402
from ifc_units import length_scale, placement_matrix  # noqa: E402
from modality.declared_grid import _curve_points  # noqa: E402

FAMILY_DEG = 2.0
PARTIAL_SHARE = 0.9


def curve_kind(curve):
    if curve.is_a("IfcIndexedPolyCurve"):
        segments = getattr(curve, "Segments", None) or []
        return "arc" if any(s.is_a("IfcArcIndex") for s in segments) else "polyline"
    if curve.is_a("IfcTrimmedCurve"):
        return "arc" if curve.BasisCurve.is_a("IfcConic") else "line"
    if curve.is_a("IfcPolyline"):
        return "polyline"
    if curve.is_a("IfcLine"):
        return "line"
    if curve.is_a("IfcConic"):
        return "arc"
    return curve.is_a()


def container_kind(grid):
    container = ifcopenshell.util.element.get_container(grid)
    if container is None:
        return "none", None
    for kind in ("IfcBuildingStorey", "IfcBuilding", "IfcSite"):
        if container.is_a(kind):
            return kind[3:].lower(), container.GlobalId
    return container.is_a(), container.GlobalId


def families(angles):
    items = sorted(a - 180.0 if a >= 180.0 - FAMILY_DEG else a for a in angles)
    out = []
    for a in items:
        if out and a - out[-1][0] <= FAMILY_DEG:
            out[-1].append(a)
        else:
            out.append([a])
    angles = [round(float(np.mean(f)) % 180.0, 2) for f in out]
    return sorted(0.0 if a >= 180.0 - 1e-6 else a for a in angles)


def shape_class(fams, curved):
    if curved:
        return "curved"
    if not fams:
        return "none"
    if len(fams) == 2 and abs(abs(fams[1] - fams[0]) - 90.0) <= FAMILY_DEG:
        on_axes = all(min(a % 90.0, 90.0 - a % 90.0) <= FAMILY_DEG for a in fams)
        return "orthogonal" if on_axes else "rotated"
    if len(fams) == 1:
        return "one-family"
    return "oblique"


def application(model):
    apps = model.by_type("IfcApplication")
    if not apps:
        return None
    app = apps[0]
    return " ".join(str(x) for x in (app.ApplicationFullName, app.Version) if x)


def survey(path):
    model = ifcopenshell.open(str(path))
    scale = length_scale(model)
    settings = ifcopenshell.geom.settings()
    building = next(iter(model.by_type("IfcBuilding")), None)
    to_building = np.linalg.inv(np.asarray(placement_matrix(building, scale) if building is not None
                                           and placement_matrix(building, scale) is not None else np.eye(4), dtype=float))
    grids, signatures, model_angles, curved = [], {}, [], False
    for grid in sorted({g.GlobalId: g for g in model.by_type("IfcGrid")}.values(), key=lambda g: g.GlobalId):
        matrix = placement_matrix(grid, scale)
        rel = to_building @ (np.asarray(matrix, dtype=float) if matrix is not None else np.eye(4))
        kinds, angles, lengths, sig, unread = Counter(), [], {"U": [], "V": [], "W": []}, [], 0
        counts = {}
        for fam, attr in (("U", "UAxes"), ("V", "VAxes"), ("W", "WAxes")):
            axes = getattr(grid, attr, None) or []
            counts[fam] = len(axes)
            for axis in axes:
                curve = axis.AxisCurve
                kind = curve_kind(curve) if curve is not None else None
                kinds[kind] += 1
                pts = _curve_points(settings, curve) if curve is not None else None
                if pts is None or len(pts) < 2:
                    unread += 1
                    continue
                p = pts @ rel[:3, :3].T + rel[:3, 3]
                length = float(np.sum(np.hypot(*np.diff(p[:, :2], axis=0).T)))
                lengths[fam].append(length)
                if kind == "arc":
                    curved = True
                else:
                    d = p[-1, :2] - p[0, :2]
                    if np.hypot(*d) > 0:
                        angles.append(math.degrees(math.atan2(d[1], d[0])) % 180.0)
                sig.append((fam, round(float(p[0, 0]), 2), round(float(p[0, 1]), 2),
                            round(float(p[-1, 0]), 2), round(float(p[-1, 1]), 2)))
        partial = sum(1 for fam in lengths.values() for L in fam if fam and L < PARTIAL_SHARE * max(fam))
        signature = hashlib.sha1(json.dumps(sorted(sig)).encode()).hexdigest()[:12]
        where, container = container_kind(grid)
        signatures.setdefault(signature, []).append(container)
        model_angles.extend(angles)
        grids.append({"guid": grid.GlobalId, "container": where, "predefinedType": getattr(grid, "PredefinedType", None),
                      "axes": counts, "curves": dict(kinds), "families": families(angles), "partialAxes": partial,
                      "unreadAxes": unread, "signature": signature})
    fams = families(model_angles)
    storey_grids = [g for g in grids if g["container"] == "buildingstorey"]
    return {
        "application": application(model),
        "schema": model.schema,
        "storeys": len(model.by_type("IfcBuildingStorey")),
        "grids": len(grids),
        "distinctGrids": len(signatures),
        "storeysDiffer": len({g["signature"] for g in storey_grids}) > 1,
        "containers": dict(Counter(g["container"] for g in grids)),
        "wAxes": sum(g["axes"]["W"] for g in grids),
        "predefinedTypes": dict(Counter(str(g["predefinedType"]) for g in grids)),
        "curves": dict(sum((Counter(g["curves"]) for g in grids), Counter())),
        "families": fams,
        "shape": shape_class(fams, curved) if grids else "none",
        "partialAxes": max((g["partialAxes"] for g in grids), default=0),
        "maxAxes": max((sum(g["axes"].values()) for g in grids), default=0),
        "gridDetail": grids,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("paths", nargs="+", type=Path, help="IFC files, or folders of them")
    parser.add_argument("--out", required=True, type=Path, help="JSONL file, one row per model")
    args = parser.parse_args()
    files = []
    for p in args.paths:
        files.extend(sorted(q for q in p.iterdir() if q.suffix.lower() == ".ifc") if p.is_dir() else [p])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    shapes = Counter()
    with args.out.open("w") as handle:
        for index, path in enumerate(files, 1):
            started = time.time()
            row = {"file": path.name, "key": resolve_file_identity(path, path.name)["key"],
                   "sizeMB": round(path.stat().st_size / 1e6, 1)}
            try:
                row.update(survey(path))
            except Exception as e:  # noqa: BLE001 - one unreadable model must not stop the survey
                row.update({"shape": "error", "error": f"{type(e).__name__}: {e}"})
            row["seconds"] = round(time.time() - started, 1)
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            shapes[row["shape"]] += 1
            if index % 25 == 0 or index == len(files):
                print(f"[{index}/{len(files)}] {dict(shapes)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
