"""Element-coverage report: which share of a model's physical products appear
in at least one recognized intent (reproduces the earlier coverage figures,
which were produced by an ad-hoc script that was never committed, so nobody
could re-run them).

Method: count `IfcProduct` instances excluding
`IfcSpatialStructureElement`, `IfcAnnotation` and `IfcGrid`; a product is
covered when its GlobalId appears in any intent's `members` or
`evidence.relatedGuids` in that model's shard. Models are de-duplicated by
content key (data/test_1.ifc and data/test_2.ifc are byte-identical
and count once).

    uv run python scripts/coverage_report.py                 # every data/*.ifc with a shard
    uv run python scripts/coverage_report.py --files test_3  # a subset
    uv run python scripts/coverage_report.py --json out.json # machine-readable too
    uv run python scripts/coverage_report.py --min-total 60  # exit 1 below this corpus %

Reads shards only - never runs recognition. Exit 2 when a requested model
has no shard yet.
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

import ifcopenshell  # noqa: E402

from file_identity import resolve_file_identity  # noqa: E402
from io_utils import read_json_file  # noqa: E402

DATA_DIR = REPO_ROOT / "data"
INTENTS_DIR = REPO_ROOT / "viewer" / "public" / "res" / "intents"
EXCLUDED = ("IfcSpatialStructureElement", "IfcAnnotation", "IfcGrid")


def physical_products(model):
    for product in model.by_type("IfcProduct"):
        if any(product.is_a(cls) for cls in EXCLUDED):
            continue
        yield product


def covered_guids(shard):
    guids = set()
    for intent in shard.get("intents", []):
        guids.update(m.get("guid") for m in intent.get("members", []) if m.get("guid"))
        guids.update(g for g in intent.get("evidence", {}).get("relatedGuids", []) if g)
    return guids


def report_file(ifc_path):
    identity = resolve_file_identity(ifc_path, ifc_path.name)
    key = identity["key"]
    shard = read_json_file(str(INTENTS_DIR / f"{key}.json"))
    if not isinstance(shard, dict):
        return key, None
    model = ifcopenshell.open(str(ifc_path))
    guids = covered_guids(shard)
    per_class = defaultdict(lambda: [0, 0])
    total = covered = 0
    for product in physical_products(model):
        cls = product.is_a()
        per_class[cls][0] += 1
        total += 1
        if product.GlobalId in guids:
            per_class[cls][1] += 1
            covered += 1
    storeys = len(model.by_type("IfcBuildingStorey"))
    intents = shard.get("intents", [])
    negative = sum(1 for p in intents if p.get("polarity") == "negative")
    return key, {
        "file": ifc_path.name, "storeys": storeys, "products": total, "covered": covered,
        "percent": round(100 * covered / total, 1) if total else 0.0,
        "intents": len(intents), "negative": negative,
        "spaces": len(model.by_type("IfcSpace")),
        "perClass": {cls: {"total": t, "covered": c} for cls, (t, c) in per_class.items()},
        "preflight": [e["category"] for e in (shard.get("preflight") or {}).get("inapplicable", [])],
    }


def main():
    parser = argparse.ArgumentParser(description="Element coverage of recognized intents per model.")
    parser.add_argument("--files", help="Comma-separated IFC names (with or without .ifc). Default: every data/*.ifc.")
    parser.add_argument("--json", help="Also write the full report to this path.")
    parser.add_argument("--min-total", type=float, help="Exit 1 if corpus coverage falls below this percentage.")
    args = parser.parse_args()

    if args.files:
        paths = [DATA_DIR / (n if n.endswith(".ifc") else f"{n}.ifc") for n in args.files.split(",")]
    else:
        paths = sorted(DATA_DIR.glob("*.ifc"))

    rows, missing, seen = [], [], set()
    class_totals = Counter()
    class_covered = Counter()
    for path in paths:
        if not path.is_file():
            print(f"not found: {path}", file=sys.stderr)
            continue
        key, row = report_file(path)
        if row is None:
            missing.append(path.name)
            continue
        if key in seen:
            print(f"  {path.name}: same bytes as an earlier file (key {key}) - counted once")
            continue
        seen.add(key)
        rows.append(row)
        for cls, v in row["perClass"].items():
            class_totals[cls] += v["total"]
            class_covered[cls] += v["covered"]

    if not rows:
        print("No models with shards found." if not missing else f"No shards for: {', '.join(missing)}")
        sys.exit(2 if missing else 0)

    total = sum(r["products"] for r in rows)
    covered = sum(r["covered"] for r in rows)
    pct = 100 * covered / total if total else 0.0

    print("| File | storeys | products | covered | % | intents | negative | IfcSpace | not applicable |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---|")
    for r in sorted(rows, key=lambda r: -r["percent"]):
        print(f"| `{r['file']}` | {r['storeys']} | {r['products']} | {r['covered']} | **{r['percent']}** | "
              f"{r['intents']} | {r['negative']} | {r['spaces']} | {len(r['preflight'])} categories |")
    print(f"| **total** | | **{total}** | **{covered}** | **{pct:.1f}** | **{sum(r['intents'] for r in rows)}** | "
          f"**{sum(r['negative'] for r in rows)}** | | |")
    print()
    print("| Class | total | covered | % |")
    print("|---|---:|---:|---:|")
    for cls, t in class_totals.most_common():
        c = class_covered[cls]
        print(f"| `{cls}` | {t} | {c} | **{round(100 * c / t)}** |")
    if missing:
        print(f"\nNo shard yet for: {', '.join(missing)} (run scripts/recognize_intents.py first)")

    if args.json:
        Path(args.json).write_text(json.dumps({
            "totalProducts": total, "covered": covered, "percent": round(pct, 1), "files": rows,
            "perClass": {cls: {"total": t, "covered": class_covered[cls]} for cls, t in class_totals.items()},
        }, indent=2))
        print(f"\nWrote {args.json}")

    if args.min_total is not None and pct < args.min_total:
        print(f"\nCorpus coverage {pct:.1f}% is below the required {args.min_total}%.")
        sys.exit(1)
    if missing:
        sys.exit(2)


if __name__ == "__main__":
    main()
