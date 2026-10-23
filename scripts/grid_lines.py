"""Declared grids (IfcGrid) as viewer line sidecars.

    uv run python scripts/grid_lines.py model.ifc [model.ifc ...]
    uv run python scripts/grid_lines.py data/uploads/*/*.ifc

Writes the model's declared axes into Interfaces/Frontend/core/public/res/
lines/<content key>.json and lists the key in index.json beside it, so the
viewer's Lines button draws them (views/lineSidecar.js). --out-dir writes
elsewhere. A directory argument means every *.ifc in it, in name order.

Only lines whose id starts with "grid:" belong to this script: every other
line in an existing sidecar (authored shapes) and every
other top-level field is kept, and a re-run replaces the grid lines only. A
model without an IfcGrid gets no new file, and loses its old grid lines if
it had a file. The IFC files are only read.

What is drawn (one line per merged axis, one variant per distinct storey
grid, nothing for borrowed storeys, colour by geometric family, height in IFC
metres) is src/modality/grid_lines.py; scripts/verify_grid_lines.py checks it.
"""

import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

import ifcopenshell  # noqa: E402

from file_identity import resolve_file_identity  # noqa: E402
from ifc_units import length_scale, unit_name  # noqa: E402
from modality.grid_lines import GRID_LINE_PREFIX, model_grid_lines  # noqa: E402

LINES_DIR = REPO_ROOT / "Interfaces" / "Frontend" / "core" / "public" / "res" / "lines"
SIDECAR_SCHEMA = 1  # views/lineSidecar.js LINE_SIDECAR_SCHEMA
GENERATOR = "scripts/grid_lines.py"


def expand(paths):
    files = []
    for p in paths:
        files.extend(sorted(q for q in p.iterdir() if q.suffix.lower() == ".ifc") if p.is_dir() else [p])
    return files


def read_json(path, default):
    if not path.exists():
        return default
    with path.open() as handle:
        return json.load(handle)


def write_json(path, doc):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2) + "\n")
    tmp.replace(path)


def update_sidecar(out_dir, key, file_name, specs, summary):
    """Merges the grid lines into the model's sidecar. Returns (total lines,
    kept authored lines), or None when nothing was written."""
    path = out_dir / f"{key}.json"
    existing = read_json(path, None)
    kept = [line for line in (existing or {}).get("lines", []) if not str(line.get("id", "")).startswith(GRID_LINE_PREFIX)]
    if not specs and existing is None:
        return None
    doc = dict(existing or {"schema": SIDECAR_SCHEMA, "model": file_name})
    doc["schema"] = SIDECAR_SCHEMA
    doc["lines"] = kept + specs
    if specs:
        doc["grid"] = {"generator": GENERATOR, **summary}
    else:
        doc.pop("grid", None)
    write_json(path, doc)
    return len(doc["lines"]), len(kept)


def update_index(out_dir, key, file_name, total, grid_lines):
    path = out_dir / "index.json"
    index = read_json(path, {"schema": SIDECAR_SCHEMA, "files": {}})
    files = index.setdefault("files", {})
    entry = dict(files.get(key) or {"model": file_name})
    entry["lines"] = total
    entry["gridLines"] = grid_lines
    entry.setdefault("note", f"declared IfcGrid ({GENERATOR})")
    files[key] = entry
    index["files"] = dict(sorted(files.items()))
    write_json(path, index)


def run(path, out_dir):
    started = time.time()
    identity = resolve_file_identity(path, path.name)
    model = ifcopenshell.open(str(path))
    scale = length_scale(model)
    specs, summary = model_grid_lines(model, scale)
    summary = {"unit": unit_name(scale), **summary}
    written = update_sidecar(out_dir, identity["key"], identity["fileName"], specs, summary)
    if written is not None:
        update_index(out_dir, identity["key"], identity["fileName"], written[0], len(specs))
    sources = {}
    for row in summary["storeys"]:
        sources[row["source"]] = sources.get(row["source"], 0) + 1
    return {"key": identity["key"], "lines": len(specs), "variants": len(summary["variants"]),
            "storeySources": sources, "kept": written[1] if written else 0,
            "written": written is not None, "seconds": round(time.time() - started, 1)}


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("files", nargs="+", type=Path, help="IFC files, or folders of them")
    parser.add_argument("--out-dir", type=Path, default=LINES_DIR, help=f"sidecar folder (default {LINES_DIR})")
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    files = expand(args.files)
    failures = 0
    for index, path in enumerate(files, 1):
        try:
            row = run(path, args.out_dir)
        except Exception as e:  # noqa: BLE001 - one unreadable model must not stop the rest
            failures += 1
            print(f"[{index}/{len(files)}] {path.name}: error {type(e).__name__}: {e}")
            continue
        what = (f"{row['lines']} grid lines in {row['variants']} variant(s), storeys {row['storeySources']}"
                if row["lines"] else "no declared grid")
        kept = f", {row['kept']} authored kept" if row["kept"] else ""
        print(f"[{index}/{len(files)}] {path.name} [{row['key']}]: {what}{kept}"
              f"{'' if row['written'] else ', nothing written'} ({row['seconds']} s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
