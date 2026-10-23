"""Per-model annotations for the IFC library button: which models are worth a
manual look, and why. Written next to the corpus vis index as
`$BI2M_VIS_DIR/annotations.json`, keyed by content key (never by number: the
corpus is renumbered after every screening pass), and read by
server/api.mjs's /api/library-models so the flyout can cluster the list.

    uv run python scripts/library_annotations.py \\
        --sweep sweep_main.json --diagnosis residual_diag.json --refined residual_refined.json

Two facts per model:
  unit      the ASSIGNED length unit (mm / cm / dm / m / ft), resolved through
            IfcUnitAssignment at the byte level (scripts/input_survey.py) - the
            models on which every placement-reading detector was silently wrong
            before src/ifc_units.py
  residual  for models covered by a scripts/unit_sweep.py run: whether the door
            graph still finds no rooms AFTER the unit fix, and why -
            "storey-split" (rooms exist at 0 m but hang off another storey
            object) or "frame" (placements and geometry in different frames)

Idempotent and additive: an existing annotations.json is merged, keys not seen
this time are kept but flagged `absent` (the model left the corpus folder), and
a model's residual verdict is only overwritten when a newer sweep says something
about it. The summary block counts PRESENT models only, so the flyout's cluster
notes describe what it lists.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "src"))

from file_identity import resolve_file_identity  # noqa: E402
from input_survey import resolve_length_unit  # noqa: E402
from local_env import env_path  # noqa: E402

CORPUS_DIR = env_path("BI2M_IFC_CORPUS")
VIS_DIR = env_path("BI2M_VIS_DIR")
CONV_UNITS = {"conv:FOOT": ("ft", 0.3048), "conv:INCH": ("in", 0.0254)}


def unit_of(path):
    import mmap
    with open(path, "rb") as fh:
        buf = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
        try:
            name, scale = resolve_length_unit(buf)
        finally:
            buf.close()
    if name in CONV_UNITS:
        return CONV_UNITS[name]
    return name, scale


def dominant(hist):
    return int(max(hist.items(), key=lambda kv: (kv[1], -int(kv[0])))[0]) if hist else None


def residual_from(sweep_path, diagnosis_path, refined_path):
    """{key: {...}} for every model a sweep covered; verdicts for the residual ones."""
    out = {}
    if not sweep_path:
        return out
    for row in json.load(open(sweep_path)):
        if "error" in row or "after_reach" not in row:
            continue
        after = row["after_reach"]
        entry = {
            "swept": True,
            "doors": after.get("doors_placed", 0),
            "reach_before": row.get("before_reach", {}).get("reach", {}),
            "reach_after": after.get("reach", {}),
            "median_door_to_room_m": after.get("median_door_to_room_m"),
        }
        usable = after.get("doors_placed") and after.get("spaces_with_footprint")
        entry["residual"] = bool(usable) and dominant(after.get("reach", {})) == 0
        out[row["key"]] = entry
    verdicts = {}
    if diagnosis_path:
        for d in json.load(open(diagnosis_path)):
            verdicts[d["key"]] = d["verdict"]
    if refined_path:
        for key, _name, _unit, _median, kind in json.load(open(refined_path)).get("refined_frame", []):
            verdicts[key] = "storey-split" if kind.startswith("storey-split") else "frame"
    for key, verdict in verdicts.items():
        out.setdefault(key, {"swept": True})["verdict"] = verdict
        out[key]["residual"] = True
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sweep", help="scripts/unit_sweep.py JSON")
    parser.add_argument("--diagnosis", help="residual diagnosis JSON (per-model verdicts)")
    parser.add_argument("--refined", help="refined frame/storey-split verdicts JSON")
    parser.add_argument("--out", default=str(VIS_DIR / "annotations.json") if VIS_DIR else None)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    if CORPUS_DIR is None or VIS_DIR is None:
        sys.exit("Set BI2M_IFC_CORPUS and BI2M_VIS_DIR (in .env at the repository root, see .env.example)")

    index_path = VIS_DIR / "index.json"
    index = json.load(open(index_path)) if index_path.exists() else {}
    models_in_index = index.get("models", index) if isinstance(index, dict) else {}

    existing = {}
    if os.path.exists(args.out):
        existing = json.load(open(args.out)).get("models", {})

    residual = residual_from(args.sweep, args.diagnosis, args.refined)

    files = sorted(CORPUS_DIR.glob("*.ifc"))
    if args.limit:
        files = files[: args.limit]
    models = dict(existing)
    seen = set()
    t0 = time.time()
    for i, path in enumerate(files, 1):
        key = resolve_file_identity(path, path.name)["key"]
        seen.add(key)
        unit, scale = unit_of(path)
        entry = models.get(key, {})
        entry.pop("absent", None)
        entry.update({"name": path.name, "size_bytes": path.stat().st_size, "unit": unit, "unit_scale": scale})
        if key in residual:
            entry.update(residual[key])
        tags = set()
        if unit != "m":
            tags.add(f"unit:{unit}")
        if entry.get("residual"):
            tags.add("residual:" + entry.get("verdict", "unclassified"))
        if entry.get("swept"):
            tags.add("swept")
        entry["tags"] = sorted(tags)
        models[key] = entry
        if i % 100 == 0 or i == len(files):
            print(f"  ... {i}/{len(files)} ({time.time() - t0:.0f}s)", file=sys.stderr, flush=True)

    if not args.limit:
        for key, e in models.items():
            if key not in seen:
                e["absent"] = True
    present = [e for e in models.values() if not e.get("absent")]
    units = {}
    for e in present:
        units[e.get("unit")] = units.get(e.get("unit"), 0) + 1
    summary = {
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "corpus_dir": str(CORPUS_DIR),
        "count": len(present),
        "absent": len(models) - len(present),
        "units": units,
        "residual": sum(1 for e in present if e.get("residual")),
        "residual_by_verdict": {
            v: sum(1 for e in present if e.get("residual") and e.get("verdict") == v)
            for v in ("storey-split", "frame", "unclassified")
        },
        "swept": sum(1 for e in present if e.get("swept")),
        "sources": {"sweep": args.sweep, "diagnosis": args.diagnosis, "refined": args.refined},
        "models": models,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    tmp = args.out + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(summary, fh, indent=1)
    os.replace(tmp, args.out)
    absent = [k for k in models_in_index if k not in models]
    print(f"wrote {args.out}: {len(present)} present + {summary['absent']} absent models, units {units}, residual {summary['residual']} "
          f"{summary['residual_by_verdict']}, swept {summary['swept']}; keys in index but not hashed here: {len(absent)}")


if __name__ == "__main__":
    main()
