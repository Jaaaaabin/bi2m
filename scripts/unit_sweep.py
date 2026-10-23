"""Library-scale check of src/ifc_units.py: run the detectors over many models
with and without the unit helper and report what changed.

    uv run python scripts/unit_sweep.py --files-from list.txt --json sweep.json
    uv run python scripts/unit_sweep.py $BI2M_IFC_CORPUS --limit 20 --json sweep.json

Per model, in-process and without writing a shard:
  - the file is COPIED to a scratch folder first, because the extractor caches
    next to the file it reads and a library folder must not be written to
  - AFTER  = today's code, all 22 categories (records, negative-polarity
    members, errors) plus the AccessGraph door-reach histogram
  - BEFORE = the pre-helper behaviour for the placement-reading categories,
    reproduced exactly by forcing the length scale to 1.0 (that is what the
    old code assumed); daylight_rooms is left out of BEFORE because the old
    code did scale its window areas, so a forced 1.0 would misrepresent it
  - the column extractor's old magnitude guess (geometry_math.divide_unit)
    against the new unit-aware conversion, per column
Read the JSON with scripts/unit_sweep.py --report sweep.json.
"""

import argparse
import collections
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "src"))

import ifcopenshell  # noqa: E402
import ifcopenshell.util.unit  # noqa: E402

import ifc_units  # noqa: E402
import recognize_intents as rp  # noqa: E402
from extraction.columns import _get_location_column  # noqa: E402
from extraction.geometry_math import divide_unit  # noqa: E402
from recognition.access_graph import AccessGraph  # noqa: E402
from recognition.registry import CATEGORIES  # noqa: E402

PLACEMENT_BEFORE = (
    # 2026-10-08: merged ids (see scripts/verify_units.py PLACEMENT_CATEGORIES).
    "window_patterns", "circulation", "room_access", "repeated_units",
    "egress_fire", "sanitary_provision", "furniture_occupancy",
)
ALL_PLACEMENT = PLACEMENT_BEFORE + ("daylight_rooms",)


def run_categories(model, extracted, key, categories):
    out = {}
    for cid in categories:
        try:
            found = CATEGORIES[cid]["detector"](model, extracted, key)
            out[cid] = {
                "records": len(found),
                "ids": sorted(p["id"] for p in found),
                "types": dict(collections.Counter(p["type"] for p in found)),
                "negative_members": sum(len(p["members"]) for p in found if p.get("polarity") == "negative"),
                "members": sum(len(p["members"]) for p in found),
            }
        except Exception as e:  # noqa: BLE001 - recorded, not raised
            out[cid] = {"error": f"{type(e).__name__}: {e}"}
    return out


def reach(model):
    graph = AccessGraph(model)
    return {
        "reach": {str(k): v for k, v in sorted(graph.door_reach.items())},
        "median_door_to_room_m": graph.median_door_to_room_m,
        "spaces_with_footprint": sum(len(v) for v in graph.spaces_by_storey.values()),
        "doors_placed": len(graph.door_links),
    }


def column_diffs(model, scale):
    """How many columns the old magnitude guess placed differently from the
    unit-aware conversion (0 for every metre file with ordinary coordinates)."""
    differ = total = 0
    for column in model.by_type("IfcColumn"):
        try:
            raw = _get_location_column(column)
        except Exception:  # noqa: BLE001
            continue
        total += 1
        if tuple(divide_unit(raw)) != tuple(ifc_units.to_metres(raw, scale)):
            differ += 1
    return {"columns": total, "old_guess_differs": differ}


def sweep_one(path, scratch):
    row = {"file": str(path), "name": path.name}
    copy = Path(scratch) / path.name
    shutil.copyfile(path, copy)
    try:
        identity = rp.resolve_file_identity(copy, copy.name)
        key = identity["key"]
        row["key"] = key
        model = ifcopenshell.open(str(copy))
        scale = ifc_units.length_scale(model)
        row.update({
            "schema": model.schema, "scale": scale, "unit": ifc_units.unit_name(scale),
            "storeys": len(model.by_type("IfcBuildingStorey")), "spaces": len(model.by_type("IfcSpace")),
            "doors": len(model.by_type("IfcDoor")), "windows": len(model.by_type("IfcWindow")),
        })
        needed = {k for c in CATEGORIES.values() for k in c["extraction_keys"]}
        try:
            extracted = rp.build_extracted(copy, key, needed, use_cache=False)
            row["extraction_error"] = None
        except Exception as e:  # noqa: BLE001
            extracted = None
            row["extraction_error"] = f"{type(e).__name__}: {e}"
        row["after"] = run_categories(model, extracted, key, CATEGORIES)
        row["after_reach"] = reach(model)
        row["columns"] = column_diffs(model, scale)

        # BEFORE: the old code assumed metres everywhere.
        original = ifcopenshell.util.unit.calculate_unit_scale
        ifcopenshell.util.unit.calculate_unit_scale = (
            lambda m, unit_type="LENGTHUNIT": 1.0 if unit_type == "LENGTHUNIT" else original(m, unit_type)
        )
        try:
            row["before"] = run_categories(model, extracted, key, PLACEMENT_BEFORE)
            row["before_reach"] = reach(model)
        finally:
            ifcopenshell.util.unit.calculate_unit_scale = original
    except Exception as e:  # noqa: BLE001
        row["error"] = f"{type(e).__name__}: {e}"
    finally:
        shutil.rmtree(Path(scratch) / "extracted", ignore_errors=True)
        try:
            os.remove(copy)
        except OSError:
            pass
    return row


def dominant(hist):
    if not hist:
        return None
    return int(max(hist.items(), key=lambda kv: (kv[1], -int(kv[0])))[0])


def report(rows):
    rows = [r for r in rows if "error" not in r]
    by_unit = collections.defaultdict(list)
    for r in rows:
        by_unit[r["unit"]].append(r)
    units = sorted(by_unit, key=lambda u: {"mm": 0, "cm": 1, "dm": 2, "m": 9}.get(u, 5))
    print(f"{len(rows)} models: " + ", ".join(f"{u}={len(by_unit[u])}" for u in units))

    print("\nDoor reach (rooms touched per door) - the figure the helper repairs:")
    print(f"{'unit':6}{'models':>7}{'w/ doors+rooms':>15}{'BEFORE dominant 0':>19}{'AFTER dominant 2':>17}{'AFTER dominant 1':>17}{'AFTER dominant 0':>17}")
    for u in units:
        rs = [r for r in by_unit[u] if r["after_reach"]["doors_placed"] and r["after_reach"]["spaces_with_footprint"]]
        b0 = sum(1 for r in rs if dominant(r["before_reach"]["reach"]) == 0)
        a2 = sum(1 for r in rs if dominant(r["after_reach"]["reach"]) == 2)
        a1 = sum(1 for r in rs if dominant(r["after_reach"]["reach"]) == 1)
        a0 = sum(1 for r in rs if dominant(r["after_reach"]["reach"]) == 0)
        print(f"{u:6}{len(by_unit[u]):7d}{len(rs):15d}{b0:19d}{a2:17d}{a1:17d}{a0:17d}")

    print("\nNegative-polarity members emitted by the three merged graph categories, summed over the non-metre models:")
    for cid in ("room_access", "egress_fire", "repeated_units"):
        nb = sum(r["before"][cid].get("negative_members", 0) for r in rows if r["unit"] != "m")
        na = sum(r["after"][cid].get("negative_members", 0) for r in rows if r["unit"] != "m")
        rb = sum(r["before"][cid].get("records", 0) for r in rows if r["unit"] != "m")
        ra = sum(r["after"][cid].get("records", 0) for r in rows if r["unit"] != "m")
        print(f"  {cid:22} records {rb:5d} -> {ra:5d}   negative members {nb:6d} -> {na:6d}")
    print("Records that could not exist before (non-metre models):")
    for cid in ("repeated_units", "daylight_rooms", "furniture_occupancy", "sanitary_provision"):
        ra = sum(r["after"][cid].get("records", 0) for r in rows if r["unit"] != "m")
        rb = sum(r["before"].get(cid, {}).get("records", 0) for r in rows if r["unit"] != "m") if cid != "daylight_rooms" else "-"
        print(f"  {cid:22} before {rb!s:>5}  after {ra:5d}")

    # Since 2026-10-08 stacks and clusters are types of window_patterns; the
    # old window_alignment count was stacks plus interrupted bays.
    def mirror(side):
        def stacks(t):
            return t.get("window_vertical_alignment", 0) + t.get("window_bay_interrupted", 0)
        return sum(1 for r in rows if r["unit"] != "m"
                   and r[side]["window_patterns"].get("types", {}).get("window_lighting_cluster")
                   and r[side]["window_patterns"]["types"]["window_lighting_cluster"] == stacks(r[side]["window_patterns"]["types"]))
    print(f"\nwindow cluster count equal to window stack count (the 7 mm-radius artefact): before {mirror('before')}, after {mirror('after')}")

    print("\nMetre controls: BEFORE must equal AFTER for every placement category")
    controls = [r for r in rows if r["unit"] == "m"]
    bad = [r["name"] for r in controls if any(r["before"][c].get("ids") != r["after"][c].get("ids") for c in PLACEMENT_BEFORE)]
    print(f"  {len(controls) - len(bad)} of {len(controls)} identical" + (f"; differing: {bad}" if bad else ""))

    print("\nColumn extractor: models where the old magnitude guess placed columns differently")
    for u in units:
        rs = [r for r in by_unit[u] if r["columns"]["columns"]]
        n = sum(1 for r in rs if r["columns"]["old_guess_differs"])
        cols = sum(r["columns"]["old_guess_differs"] for r in rs)
        print(f"  {u:4} {n:3d} of {len(rs):3d} models with columns ({cols} columns moved)")

    print("\nErrors")
    ext = [r["name"] for r in rows if r.get("extraction_error")]
    print(f"  extraction failed: {len(ext)} {ext[:8]}")
    det = collections.Counter()
    for r in rows:
        for cid, v in r["after"].items():
            if "error" in v:
                det[(cid, v["error"][:60])] += 1
    print(f"  detector exceptions (after): {sum(det.values())}" + (": " + "; ".join(f"{c} x{n} [{e}]" for (c, e), n in det.most_common(6)) if det else ""))

    print("\nResidual: non-metre models whose doors still mostly reach no room after the helper (frame mismatch, not units)")
    res = [r for r in rows if r["unit"] != "m" and r["after_reach"]["doors_placed"] and r["after_reach"]["spaces_with_footprint"] and dominant(r["after_reach"]["reach"]) == 0]
    for r in res[:12]:
        # Content key first: the corpus is renumbered after every screening
        # pass, so the number is a convenience only.
        print(f"  {r.get('key', '?'):17} {r['name']:10} {r['unit']:3} spaces={r['spaces']:4} doors={r['doors']:4} reach={r['after_reach']['reach']} median door->room {r['after_reach']['median_door_to_room_m'] and round(r['after_reach']['median_door_to_room_m'], 2)} m")
    print(f"  {len(res)} such models")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("targets", nargs="*", help="folders or .ifc files")
    parser.add_argument("--files-from", help="text file with one path per line")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--json", help="write per-model results here (also flushed every 10 models)")
    parser.add_argument("--report", help="only print the report for an existing JSON")
    parser.add_argument("--scratch", help="folder for the transient copies (default: a temp dir)")
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
    scratch = args.scratch or tempfile.mkdtemp(prefix="unit_sweep_")
    os.makedirs(scratch, exist_ok=True)
    rows, t0 = [], time.time()
    for i, path in enumerate(files, 1):
        rows.append(sweep_one(path, scratch))
        if i % 10 == 0 or i == len(files):
            print(f"  ... {i}/{len(files)} ({time.time() - t0:.0f}s)", file=sys.stderr, flush=True)
            if args.json:
                json.dump(rows, open(args.json, "w"))
    if args.json:
        json.dump(rows, open(args.json, "w"))
        print(f"wrote {args.json}", file=sys.stderr)
    report(rows)


if __name__ == "__main__":
    main()
