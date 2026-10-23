"""Run every registered detector over many library models and record what a
reviewer would otherwise only discover one model at a time: exceptions,
categories that were eligible but produced nothing, degenerate outputs
(record explosions, all-negative storeys, a cluster detector mirroring
another), graph health (door reach, storey splits, frame mismatches), storey
anomalies (duplicate names or elevations), containment gaps, and timing.

    uv run python scripts/detector_sweep.py $BI2M_IFC_CORPUS --json sweep.json
    uv run python scripts/detector_sweep.py --report sweep.json

Writes no shard. Each model is copied to a scratch folder first (the
extractor caches next to the file it reads; a library folder is never
written to), processed, and the copy removed. Results are keyed by content
key; the number is only the current name (docs/architecture.md "One key
for everything").
"""

import argparse
import collections
import gc
import json
import os
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "src"))

import ifcopenshell  # noqa: E402
import ifcopenshell.util.element as ue  # noqa: E402
from shapely.geometry import Point  # noqa: E402

import ifc_units  # noqa: E402
import recognize_intents as rp  # noqa: E402
from recognition.access_graph import AccessGraph  # noqa: E402
from recognition.preflight import preflight  # noqa: E402
from recognition.registry import CATEGORIES  # noqa: E402


def storey_of(e):
    return ue.get_parent(e, ifc_class="IfcBuildingStorey")


def count_unique(model, ifc_class):
    try:
        return len({e.GlobalId for e in model.by_type(ifc_class)})
    except RuntimeError:
        return 0


def facts(model):
    storeys = model.by_type("IfcBuildingStorey")
    names = [s.Name for s in storeys]
    elevations = [s.Elevation for s in storeys]
    spaces = model.by_type("IfcSpace")
    doors = model.by_type("IfcDoor")
    scale = ifc_units.length_scale(model)
    return {
        "schema": model.schema,
        "unit": ifc_units.unit_name(scale),
        "unit_scale": scale,
        "storeys": len(storeys),
        "storey_duplicate_names": len(names) - len(set(names)),
        "storey_duplicate_elevations": len(elevations) - len(set(elevations)),
        "storey_elevation_none": sum(1 for e in elevations if e is None),
        "spaces": len(spaces),
        "spaces_without_storey": sum(1 for s in spaces if storey_of(s) is None),
        "spaces_without_representation": sum(1 for s in spaces if s.Representation is None),
        "doors": len(doors),
        "doors_without_storey": sum(1 for d in doors if storey_of(d) is None),
        "doors_without_placement": sum(1 for d in doors if d.ObjectPlacement is None),
        "windows": count_unique(model, "IfcWindow"),
        "walls": count_unique(model, "IfcWall"),
        "columns": count_unique(model, "IfcColumn"),
        "beams": count_unique(model, "IfcBeam"),
        "slabs": count_unique(model, "IfcSlab"),
        "stairs": count_unique(model, "IfcStair") + count_unique(model, "IfcRamp"),
        "flights": count_unique(model, "IfcStairFlight") + count_unique(model, "IfcRampFlight"),
        "curtain_walls": count_unique(model, "IfcCurtainWall"),
        "curtain_parts": count_unique(model, "IfcMember") + count_unique(model, "IfcPlate"),
        "furnishing": count_unique(model, "IfcFurnishingElement") + count_unique(model, "IfcBuildingElementProxy")
        + count_unique(model, "IfcFlowTerminal"),
        "space_boundaries": count_unique(model, "IfcRelSpaceBoundary"),
        "zones": count_unique(model, "IfcZone"),
        "grids": count_unique(model, "IfcGrid"),
        "products": count_unique(model, "IfcProduct"),
    }


def graph_health(model):
    graph = AccessGraph(model)
    classes = collections.Counter()
    all_polys = list(graph.polygons.values())
    far_any = []
    for guid, (storey, reached) in graph.door_links.items():
        if reached:
            classes["ok"] += 1
            continue
        pt = Point(*graph.door_points[guid])
        same = [graph.polygons[s] for s in graph.spaces_by_storey.get(storey, [])]
        if not same:
            classes["storey_split"] += 1
            if all_polys:
                far_any.append(min(p.distance(pt) for p in all_polys))
            continue
        d = min(p.distance(pt) for p in same)
        classes["margin" if d <= 1.0 else "frame"] += 1
        if d > 1.0 and all_polys:
            far_any.append(min(p.distance(pt) for p in all_polys))
    return {
        "reach": {str(k): v for k, v in sorted(graph.door_reach.items())},
        "median_door_to_room_m": graph.median_door_to_room_m,
        "doors_placed": len(graph.door_links),
        "spaces_with_footprint": sum(len(v) for v in graph.spaces_by_storey.values()),
        "storeys_with_spaces": len(graph.spaces_by_storey),
        "classes": dict(classes),
        "unreached_nearest_any_storey_median_m": round(statistics.median(far_any), 3) if far_any else None,
    }


def summarize(found):
    members = [len(p["members"]) for p in found]
    return {
        "records": len(found),
        "negative_records": sum(1 for p in found if p.get("polarity") == "negative"),
        "negative_members": sum(len(p["members"]) for p in found if p.get("polarity") == "negative"),
        "members": sum(members),
        "max_members": max(members, default=0),
        "types": dict(collections.Counter(p["type"] for p in found)),
    }


def sweep_one(path, scratch):
    row = {"file": str(path), "name": path.name}
    copy = Path(scratch) / path.name
    shutil.copyfile(path, copy)
    t_model = time.time()
    try:
        identity = rp.resolve_file_identity(copy, copy.name)
        key = identity["key"]
        row["key"] = key
        model = ifcopenshell.open(str(copy))
        row["facts"] = facts(model)
        report = preflight(model, CATEGORIES)
        row["inapplicable"] = {e["category"]: e["missing"] for e in report["inapplicable"]}
        needed = {k for c in CATEGORIES.values() for k in c["extraction_keys"]}
        t = time.time()
        try:
            extracted = rp.build_extracted(copy, key, needed, use_cache=False)
            row["extraction_error"] = None
        except Exception as e:  # noqa: BLE001
            extracted = None
            row["extraction_error"] = f"{type(e).__name__}: {e}"
        row["extraction_seconds"] = round(time.time() - t, 2)
        cats = {}
        for cid, info in CATEGORIES.items():
            t = time.time()
            try:
                found = info["detector"](model, extracted, key)
                entry = summarize(found)
            except Exception as e:  # noqa: BLE001
                entry = {"error": f"{type(e).__name__}: {e}"}
            entry["seconds"] = round(time.time() - t, 2)
            cats[cid] = entry
        row["categories"] = cats
        try:
            row["graph"] = graph_health(model)
        except Exception as e:  # noqa: BLE001
            row["graph"] = {"error": f"{type(e).__name__}: {e}"}
        del model
        gc.collect()
    except Exception as e:  # noqa: BLE001
        row["error"] = f"{type(e).__name__}: {e}"
    finally:
        row["seconds"] = round(time.time() - t_model, 1)
        shutil.rmtree(Path(scratch) / "extracted", ignore_errors=True)
        try:
            os.remove(copy)
        except OSError:
            pass
    return row


def sweep_one_capped(path, scratch, seconds):
    """sweep_one in a child process with a wall-clock cap. C++ geometry does
    not answer to signals, so a cap has to be a process boundary."""
    import subprocess
    out = Path(scratch) / (path.stem + ".row.json")
    cmd = [sys.executable, __file__, str(path), "--json", str(out), "--scratch", scratch]
    t = time.time()
    try:
        subprocess.run(cmd, timeout=seconds, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        rows = json.load(open(out)) if out.exists() else []
        row = rows[0] if rows else {"file": str(path), "name": path.name, "error": "child produced no row"}
    except subprocess.TimeoutExpired:
        row = {"file": str(path), "name": path.name, "error": f"timeout after {seconds:.0f} s", "seconds": round(time.time() - t, 1)}
        shutil.rmtree(Path(scratch) / "extracted", ignore_errors=True)
        for stray in Path(scratch).glob("*.ifc"):
            stray.unlink(missing_ok=True)
    finally:
        out.unlink(missing_ok=True)
    return row


def dominant(hist):
    return int(max(hist.items(), key=lambda kv: (kv[1], -int(kv[0])))[0]) if hist else None


def pct(n, d):
    return f"{100 * n / d:.0f} %" if d else "-"


def report(rows):
    timeouts = [r["name"] for r in rows if "timeout" in str(r.get("error", ""))]
    if timeouts:
        print(f"skipped by the per-model cap: {len(timeouts)} - {timeouts[:12]}")
    rows = [r for r in rows if "error" not in r and "categories" in r]
    n = len(rows)
    print(f"{n} models; units {dict(collections.Counter(r['facts']['unit'] for r in rows))}; "
          f"median {statistics.median(r['seconds'] for r in rows):.1f} s per model, slowest {max(r['seconds'] for r in rows):.0f} s")

    print("\n== Per category: eligibility vs output, negatives, exceptions ==")
    print(f"{'category':24}{'eligible':>9}{'with output':>12}{'eligible-empty':>15}{'records':>9}{'neg rec':>9}{'neg members':>12}{'max members':>12}{'errors':>7}{'sec/model':>10}")
    for cid in CATEGORIES:
        elig = [r for r in rows if cid not in r["inapplicable"]]
        with_out = [r for r in elig if r["categories"][cid].get("records", 0) > 0]
        errs = sum(1 for r in rows if "error" in r["categories"][cid])
        recs = sum(r["categories"][cid].get("records", 0) for r in rows)
        negr = sum(r["categories"][cid].get("negative_records", 0) for r in rows)
        negm = sum(r["categories"][cid].get("negative_members", 0) for r in rows)
        mx = max((r["categories"][cid].get("max_members", 0) for r in rows), default=0)
        secs = statistics.median(r["categories"][cid].get("seconds", 0) for r in rows)
        print(f"{cid:24}{len(elig):9d}{len(with_out):12d}{len(elig) - len(with_out):15d}{recs:9d}{negr:9d}{negm:12d}{mx:12d}{errs:7d}{secs:10.2f}")

    print("\n== Detector exceptions (message -> models) ==")
    errs = collections.defaultdict(list)
    for r in rows:
        for cid, v in r["categories"].items():
            if "error" in v:
                errs[(cid, v["error"][:90])].append(r["name"])
    for (cid, msg), names in sorted(errs.items(), key=lambda kv: -len(kv[1]))[:15]:
        print(f"  {cid:22} x{len(names):3d}  {msg}  e.g. {names[:4]}")
    if not errs:
        print("  none")
    ext = [r["name"] + ": " + r["extraction_error"] for r in rows if r.get("extraction_error")]
    print(f"  extraction failures: {len(ext)} " + "; ".join(e[:100] for e in ext[:5]))

    print("\n== Storeys and containment ==")
    f = lambda k: sum(1 for r in rows if r["facts"][k])  # noqa: E731
    print(f"  models with duplicate storey names: {f('storey_duplicate_names')}; duplicate storey elevations: {f('storey_duplicate_elevations')}; "
          f"Elevation None: {f('storey_elevation_none')}; no storey at all: {sum(1 for r in rows if r['facts']['storeys'] == 0)}")
    print(f"  models with spaces lacking a storey: {f('spaces_without_storey')} ({sum(r['facts']['spaces_without_storey'] for r in rows)} spaces); "
          f"spaces without representation: {f('spaces_without_representation')} ({sum(r['facts']['spaces_without_representation'] for r in rows)}); "
          f"doors lacking a storey: {f('doors_without_storey')} ({sum(r['facts']['doors_without_storey'] for r in rows)}); doors without placement: {f('doors_without_placement')}")
    print(f"  models with IfcRelSpaceBoundary: {f('space_boundaries')}; IfcZone: {f('zones')}; IfcGrid: {f('grids')}; stairs without flights: "
          f"{sum(1 for r in rows if r['facts']['stairs'] and not r['facts']['flights'])}; curtain walls without parts: {sum(1 for r in rows if r['facts']['curtain_walls'] and not r['facts']['curtain_parts'])}")

    print("\n== Door graph health (models with doors and room footprints) ==")
    g = [r for r in rows if "graph" in r and "error" not in r["graph"] and r["graph"]["doors_placed"] and r["graph"]["spaces_with_footprint"]]
    by_dom = collections.Counter(dominant(r["graph"]["reach"]) for r in g)
    print(f"  {len(g)} models; dominant door reach: " + ", ".join(f"{k} rooms: {v}" for k, v in sorted(by_dom.items(), key=lambda kv: (kv[0] is None, kv[0]))))
    cls = collections.Counter()
    for r in g:
        c = r["graph"]["classes"]
        tot = sum(c.values()) or 1
        worst = max((k for k in c if k != "ok"), key=lambda k: c[k], default="ok")
        if c.get("ok", 0) / tot < 0.5:
            cls[worst] += 1
    print(f"  models where under half the doors reach a room, by main cause: {dict(cls)}")
    for unit in ("m", "mm", "cm", "ft"):
        gu = [r for r in g if r["facts"]["unit"] == unit]
        if gu:
            bad = sum(1 for r in gu if dominant(r["graph"]["reach"]) == 0)
            print(f"    {unit:3}: {len(gu):3d} models, {bad:3d} with most doors reaching no room")

    print("\n== Degenerate outputs ==")
    # Since 2026-10-08 the window and access readings are types inside the
    # merged categories window_patterns, egress_fire and room_access.
    def types_of(r, cid):
        return r["categories"][cid].get("types", {})
    def stacks(t):  # the old window_alignment count: stacks plus interrupted bays
        return t.get("window_vertical_alignment", 0) + t.get("window_bay_interrupted", 0)
    mirror = [r for r in rows if types_of(r, "window_patterns").get("window_lighting_cluster")
              and types_of(r, "window_patterns").get("window_lighting_cluster") == stacks(types_of(r, "window_patterns"))]
    print(f"  window clusters == window stacks record count: {len(mirror)}")
    allun = [r for r in rows if types_of(r, "egress_fire").get("egress_unreachable") and not types_of(r, "egress_fire").get("egress_reachable")]
    print(f"  egress: only unreachable records on the whole model: {len(allun)} of {sum(1 for r in rows if types_of(r, 'egress_fire').get('egress_reachable') or types_of(r, 'egress_fire').get('egress_unreachable'))} models with output")
    iso = [r for r in rows if types_of(r, "room_access").get("access_isolated_space") and not types_of(r, "room_access").get("access_reachable_group")]
    print(f"  room access: isolated rooms but no reachable group at all: {len(iso)}")
    big = collections.Counter()
    for r in rows:
        for cid, v in r["categories"].items():
            if v.get("records", 0) >= 200:
                big[cid] += 1
    print(f"  categories emitting >= 200 records on one model (models): {dict(big) or 'none'}")
    ratio = [(r["categories"]["alignment"].get("records", 0) / r["facts"]["columns"], r["name"]) for r in rows if r["facts"]["columns"] >= 20]
    if ratio:
        print(f"  alignment records per column (models with >= 20 columns): median {statistics.median(x for x, _ in ratio):.2f}, max {max(ratio)[0]:.2f} ({max(ratio)[1]})")
    ut0 = [r for r in rows if r["facts"]["spaces"] >= 10 and r["facts"]["doors"] >= 5 and "repeated_units" not in r["inapplicable"] and not types_of(r, "repeated_units").get("unit_type_recurrence")]
    print(f"  repeated_units: eligible, >= 10 spaces and >= 5 doors, no unit_type_recurrence record: {len(ut0)}")
    ch0 = [r for r in rows if r["facts"]["spaces"] >= 10 and not types_of(r, "room_access").get("circulation_horizontal_space")]
    print(f"  room_access: >= 10 spaces, no circulation_horizontal_space record: {len(ch0)} of {sum(1 for r in rows if r['facts']['spaces'] >= 10)}")

    print("\n== Timing ==")
    slow = sorted(rows, key=lambda r: -r["seconds"])[:5]
    print("  slowest models: " + "; ".join(f"{r['name']} {r['seconds']}s (products {r['facts']['products']}, extraction {r['extraction_seconds']}s)" for r in slow))
    percat = {cid: sum(r["categories"][cid].get("seconds", 0) for r in rows) for cid in CATEGORIES}
    print("  total seconds by category (top 6): " + ", ".join(f"{k} {v:.0f}" for k, v in sorted(percat.items(), key=lambda kv: -kv[1])[:6]))
    print(f"  total extraction seconds: {sum(r['extraction_seconds'] for r in rows):.0f}; total wall time {sum(r['seconds'] for r in rows) / 60:.0f} min")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("targets", nargs="*")
    parser.add_argument("--files-from")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--json")
    parser.add_argument("--report")
    parser.add_argument("--scratch")
    parser.add_argument("--per-model-timeout", type=float, default=0,
                        help="seconds; run each model in a child process and record a timeout instead of stalling "
                             "(tumgni_all/0233 alone ran past 20 minutes)")
    args = parser.parse_args()
    if args.report:
        report(json.load(open(args.report)))
        return
    files = []
    if args.files_from:
        files += [Path(l.strip()) for l in open(args.files_from) if l.strip()]
    for t in args.targets:
        p = Path(t)
        files += sorted(p.glob("*.ifc")) if p.is_dir() else [p]
    if args.limit:
        files = files[: args.limit]
    scratch = args.scratch or tempfile.mkdtemp(prefix="detector_sweep_")
    os.makedirs(scratch, exist_ok=True)
    rows, t0 = [], time.time()
    for i, path in enumerate(files, 1):
        if args.per_model_timeout:
            rows.append(sweep_one_capped(path, scratch, args.per_model_timeout))
        else:
            rows.append(sweep_one(path, scratch))
        if i % 10 == 0 or i == len(files):
            print(f"  ... {i}/{len(files)} ({time.time() - t0:.0f}s)", file=sys.stderr, flush=True)
            if args.json:
                json.dump(rows, open(args.json, "w"))
    if args.json:
        json.dump(rows, open(args.json, "w"))
    report(rows)


if __name__ == "__main__":
    main()
