"""L1 grid words and L0 facade bands for IFC models that declare an IfcGrid.

    uv run python scripts/grid_words.py --out DIR model.ifc [model.ifc ...]
    uv run python scripts/grid_words.py --out DIR --per-model-timeout 600 --resume $BI2M_IFC_CORPUS

Writes DIR/<content key>.json per model (schema "bi2m.gridwords/1"), the
threshold-calibration inputs to DIR/<content key>.calib.json, and appends one
row per model to DIR/summary.jsonl. A model without an IfcGrid gets a row and
no JSON. A directory argument means every *.ifc in it, in name order.

The IFC files are only read: nothing is written next to them. With
--per-model-timeout, each model is copied to a scratch folder, processed in a
child process under a wall-clock cap (IfcOpenShell's C++ geometry does not
answer to signals), and the copy deleted - the pattern of
scripts/detector_sweep.py. The parent writes the summary row, so a model that
times out or crashes still leaves one. --resume skips models whose latest row
is "ok" or "no-grid".

The definitions live in src/modality/declared_grid.py (axes, cells, rhythm),
src/modality/grid_words.py (elements, symbols, words) and
src/modality/facade_bands.py (outline, runs, bands);
scripts/verify_grid_words.py checks them on synthetic grids.
"""

import argparse
from collections import Counter, defaultdict
import json
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

import ifcopenshell  # noqa: E402
import numpy as np  # noqa: E402
from shapely.geometry import LineString, Point, Polygon  # noqa: E402

from file_identity import resolve_file_identity  # noqa: E402
from ifc_units import length_scale, to_metres  # noqa: E402
from modality import declared_grid as dg  # noqa: E402
from modality import facade_bands as fb  # noqa: E402
from modality import grid_words as gw  # noqa: E402

DONE = ("ok", "no-grid")


def _r(value, digits=3):
    return None if value is None else round(float(value), digits)


def _points(points):
    return [[round(x, 4), round(y, 4)] for x, y in points]


def _calibration(geo, on_storey, rects_on_cut, runs, z_cut):
    """Raw distances for sweeping the thresholds later without re-reading the
    model: each column to the nearest cell corner and to the nearest axis,
    each window on the cut to the nearest facade run, and the run lengths."""
    corners = [cell["polygon"][i] for cell in geo["cells"] for i in (cell["corners"] or range(len(cell["polygon"])))]
    corners = np.asarray(corners, dtype=float) if corners else None
    axis_lines = [LineString(a["points"]) for a in geo["axes"]]
    column_corner, column_axis = [], []
    for prim in on_storey:
        if prim["kind"] != "C":
            continue
        p = np.asarray(prim["point"])
        column_corner.append(_r(np.min(np.hypot(*(corners - p).T)) if corners is not None else None))
        column_axis.append(_r(min((line.distance(Point(p)) for line in axis_lines), default=None)))
    run_lines = [LineString(r["points"]) for r in runs]
    window_run = []
    for rect in rects_on_cut:
        if rect["kind"] != "N":
            continue
        centre = Polygon(rect["rect"]).centroid
        window_run.append(_r(min((line.distance(centre) for line in run_lines), default=None)))
    return {"cut": _r(z_cut), "columnCornerDist": column_corner, "columnAxisDist": column_axis,
            "windowRunDist": window_run, "runLengths": sorted(r["length"] for r in runs)}


def process(path):
    started = time.time()
    identity = resolve_file_identity(path, path.name)
    model = ifcopenshell.open(str(path))
    scale = length_scale(model)
    grids = dg.read_declared_grids(model, scale)
    if not grids:
        return None, {"file": path.name, "key": identity["key"], "grids": 0}, None

    primitives, element_report = gw.element_primitives(model)
    by_storey = defaultdict(list)
    for prim in primitives:
        by_storey[prim["storey"]].append(prim)
    rectangles, facade_elements = fb.element_rectangles(model)
    all_rects = [rectangles[guid] for guid in sorted(rectangles)]
    slabs = fb.slab_footprints(model)

    storeys = sorted(model.by_type("IfcBuildingStorey"),
                     key=lambda s: (to_metres(s.Elevation, scale) if s.Elevation is not None else 0.0, s.GlobalId))
    out_storeys, symbol_counts, sources, calib = [], Counter(), Counter(), []
    for storey in storeys:
        axes, source = dg.active_axes(grids, storey.GlobalId)
        sources[source] += 1
        entry = {"guid": storey.GlobalId, "name": storey.Name,
                 "elevation": _r(to_metres(storey.Elevation, scale)) if storey.Elevation is not None else None,
                 "gridSource": source}
        if not axes:
            out_storeys.append({**entry, "axes": [], "cells": [], "symbols": {}, "facadeBands": []})
            continue
        geo = dg.storey_grid(axes)
        on_storey = by_storey.get(storey.GlobalId, [])
        described = gw.describe_cells(geo["cells"], on_storey)
        symbols = {cid: d["symbol"] for cid, d in described.items()}
        symbol_counts.update(symbols.values())
        z_cut = fb.cut_height(all_rects, storey.GlobalId)
        cut_rects = fb.on_cut(all_rects, z_cut) if z_cut is not None else []
        if z_cut is None:
            runs, facade_report = [], {"cut": None}
        else:
            runs, facade_report = fb.storey_bands(cut_rects, geo["axes"], cover=fb.cover_above(slabs, z_cut))
            facade_report["cut"] = round(z_cut, 3)
        calib.append({"guid": storey.GlobalId, **_calibration(geo, on_storey, cut_rects, runs, z_cut)})
        entry.update({
            "axes": [{"id": a["id"], "tags": a["tags"], "declaredFamilies": a["declaredFamilies"], "grids": a["grids"],
                      "family": a["family"], "offset": _r(a["offset"]), "partial": a["partial"],
                      "danglingEnds": a["danglingEnds"], "curve": a["curve"], "points": _points(a["points"])}
                     for a in geo["axes"]],
            "families": {name: {"angleDeg": f["angleDeg"], "axes": f["axes"]} for name, f in geo["families"].items()},
            "rhythm": geo["rhythm"],
            "cells": [{"id": c["id"], "polygon": c["polygon"], "area": _r(c["area"], 2), "axes": c["axes"],
                       "internalAxes": c["internalAxes"], **described[c["id"]]} for c in geo["cells"]],
            "words": gw.slot_words(geo["slots"], symbols),
            "symbols": symbols,
            "elements": dict(Counter(p["kind"] for p in on_storey)),
            "stats": geo["stats"],
            "facadeBands": runs,
            "facadeReport": facade_report,
        })
        out_storeys.append(entry)

    result = {
        "schema": "bi2m.gridwords/1",
        "file": path.name,
        "fileKey": identity["key"],
        "units": "m",
        "parameters": {"snapM": dg.SNAP_M, "duplicateM": dg.DUP_M, "familyAngleDeg": dg.FAMILY_ANGLE_DEG,
                       "spacingTolM": dg.SPACING_TOL_M, "cornerTolM": gw.CORNER_TOL_M, "edgeTolM": gw.EDGE_TOL_M,
                       "edgeAngleDeg": gw.EDGE_ANGLE_DEG, "edgeOverlap": gw.EDGE_OVERLAP,
                       "facadeCloseM": fb.CLOSE_M, "facadeTurnDeg": fb.TURN_DEG, "facadeDepthM": fb.DEPTH_M,
                       "facadeBinM": fb.BIN_M, "facadeCutM": fb.CUT_M, "courtyardCover": fb.COURT_COVER},
        "grids": [{"guid": g["guid"], "name": g["name"], "predefinedType": g["predefinedType"], "storey": g["storey"],
                   "axes": len(g["axes"]), "skippedAxes": g["skippedAxes"]} for g in grids],
        "elementReport": element_report,
        "facadeElementReport": facade_elements,
        "storeys": out_storeys,
        "verticalWords": gw.vertical_words(out_storeys),
    }
    with_grid = [s for s in out_storeys if s["cells"]]
    summary = {
        "file": path.name, "key": identity["key"], "grids": len(grids),
        "gridSource": dict(sources),
        "axes": sorted({len(s["axes"]) for s in with_grid}),
        "partial": max((sum(1 for a in s["axes"] if a["partial"]) for s in with_grid), default=0),
        "dangling": max((sum(1 for a in s["axes"] if a["danglingEnds"]) for s in with_grid), default=0),
        "cells": sorted({len(s["cells"]) for s in with_grid}),
        "symbols": dict(symbol_counts.most_common()),
        "elements": element_report["elements"], "degenerate": element_report["degenerate"],
        "noStorey": element_report["noStorey"],
        "facadeRuns": sorted({len(s["facadeBands"]) for s in with_grid}),
        "windowsOnCut": sum(s.get("facadeReport", {}).get("windows", 0) for s in with_grid),
        "windowsOnNoRun": sum(s.get("facadeReport", {}).get("windowsOnNoRun", 0) for s in with_grid),
        "doorsOnCut": sum(s.get("facadeReport", {}).get("doors", 0) for s in with_grid),
        "doorsOnARun": sum(s.get("facadeReport", {}).get("doorsOnARun", 0) for s in with_grid),
        "courtyards": max((s.get("facadeReport", {}).get("courtyards", 0) for s in with_grid), default=0),
        "seconds": round(time.time() - started, 1),
    }
    return result, summary, {"file": path.name, "key": identity["key"], "storeys": calib}


# --------------------------------------------------------------------------
# Running one model, here or in a capped child process
# --------------------------------------------------------------------------

def run_here(path, out):
    """Process one model in this process; returns its summary row."""
    started = time.time()
    try:
        result, summary, calib = process(path)
    except Exception as e:  # noqa: BLE001 - one model failing must not stop the others
        return {"file": path.name, "status": "error", "error": f"{type(e).__name__}: {e}",
                "traceback": traceback.format_exc(limit=8), "seconds": round(time.time() - started, 1)}
    if result is None:
        return {**summary, "status": "no-grid", "seconds": round(time.time() - started, 1)}
    (out / f"{summary['key']}.json").write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n")
    (out / f"{summary['key']}.calib.json").write_text(json.dumps(calib, ensure_ascii=False) + "\n")
    return {**summary, "status": "ok"}


def run_capped(path, out, scratch, seconds):
    """Copy the model to `scratch`, process it in a child process with a
    wall-clock cap, delete the copy. Returns its summary row."""
    copy = scratch / path.name
    row_file = scratch / f"{path.name}.row.json"
    started = time.time()
    shutil.copy2(path, copy)
    try:
        proc = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--out", str(out),
                               "--child-row", str(row_file), str(copy)],
                              timeout=seconds, capture_output=True, text=True, check=False)
        if row_file.exists():
            row = json.loads(row_file.read_text())
        else:
            row = {"file": path.name, "status": "error",
                   "error": f"child exited with code {proc.returncode} and wrote no row",
                   "stderrTail": proc.stderr[-2000:]}
    except subprocess.TimeoutExpired:
        row = {"file": path.name, "status": "timeout", "error": f"timeout after {seconds:g} s"}
    finally:
        copy.unlink(missing_ok=True)
        row_file.unlink(missing_ok=True)
    row.setdefault("seconds", round(time.time() - started, 1))
    return row


def expand(paths):
    files = []
    for p in paths:
        if p.is_dir():
            files.extend(sorted(q for q in p.iterdir() if q.suffix.lower() == ".ifc"))
        else:
            files.append(p)
    return files


def done_keys(rows_path):
    latest = {}
    if rows_path.exists():
        for line in rows_path.read_text().splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("key"):
                latest[row["key"]] = row.get("status")
    return {k for k, status in latest.items() if status in DONE}


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("files", nargs="+", type=Path, help="IFC files, or folders of them")
    parser.add_argument("--out", required=True, type=Path, help="output folder")
    parser.add_argument("--per-model-timeout", type=float, default=0,
                        help="seconds; run each model on a scratch copy in a capped child process")
    parser.add_argument("--resume", action="store_true", help="skip models whose latest row is ok or no-grid")
    parser.add_argument("--child-row", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    if args.child_row:  # internal: one model, row to a file for the parent
        row = run_here(args.files[0], args.out)
        args.child_row.write_text(json.dumps(row, ensure_ascii=False))
        return 0

    rows_path = args.out / "summary.jsonl"
    skip = done_keys(rows_path) if args.resume else set()
    files = expand(args.files)
    scratch = Path(tempfile.mkdtemp(prefix="grid_words_")) if args.per_model_timeout else None
    failures = 0
    try:
        for index, path in enumerate(files, 1):
            key = resolve_file_identity(path, path.name)["key"]
            if key in skip:
                print(f"[{index}/{len(files)}] {path.name} [{key}]: done before, skipped")
                continue
            row = run_capped(path, args.out, scratch, args.per_model_timeout) if scratch else run_here(path, args.out)
            row["key"] = row.get("key") or key
            row["source"] = str(path)
            with rows_path.open("a") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            failures += row["status"] in ("error", "timeout")
            detail = row.get("error") or (f"cells {row.get('cells')}, runs {row.get('facadeRuns')}"
                                          if row["status"] == "ok" else "")
            print(f"[{index}/{len(files)}] {path.name} [{row['key']}]: {row['status']} in {row['seconds']} s {detail}")
    finally:
        if scratch:
            shutil.rmtree(scratch, ignore_errors=True)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
