"""Build the content-addressed index for per-model visual outputs.

Visual outputs (floor plans, axonometrics, thumbnails, detector overlays) are
MANY files per model, so they get one folder per model rather than one folder
per output type - the same fan-out rule that already makes res/intents/ flat
(one shard per model) but public/tiles/ and data/uploads/ folder-per-model.

Those folders are named by the model's CONTENT key (src/file_identity.py),
never by its 0001.ifc-style number, because the numbering is not stable: the
corpus is periodically screened and then renumbered to contiguous, so a folder
named for a number silently stops describing its contents the moment the
screening pass runs. The number is not recorded in the filesystem at all - it
lives in exactly one place, this index's `name` field - which is what makes a
renumber a rewrite of one JSON file instead of 518 directory renames (renames
that additionally need a two-phase dance, since 0207 -> 0198 collides with the
0198 that already exists).

Corollary, worth preserving: per-model meta.json files are written by the
RENDERER, not by this script, and hold only facts that are true of the bytes
(content_key, unit_scale, storey list, complete). No mutable name or number
goes in them, or the single-source-of-truth property above is lost.

Re-run semantics (this script is idempotent and never deletes):
  - key in corpus, already indexed  -> `name` refreshed (this is the renumber)
  - key in corpus, not yet indexed  -> added
  - key indexed, no longer in corpus -> kept, flagged `absent: true`, so a
    screened-out model's renders stay findable and explicable rather than
    becoming orphans nobody can identify.

Usage:
    # BI2M_IFC_CORPUS and BI2M_VIS_DIR come from .env or the environment
    uv run python scripts/build_vis_index.py            # build or refresh
    uv run python scripts/build_vis_index.py --list     # readable listing
    uv run python scripts/build_vis_index.py --corpus DIR --out DIR

Both locations are machine-specific (the corpus lives outside the repo, on a
storage mount), so they are taken from the environment or the command line
rather than from paths.yaml - see that file's "never commit a machine-specific
absolute path" note.
"""

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from local_env import load_local_env  # noqa: E402

from file_identity import compute_content_key  # noqa: E402
from io_utils import write_json, read_json_file  # noqa: E402

INDEX_NAME = "index.json"
PROGRESS_EVERY = 50


def _resolve_dir(cli_value, env_var, what):
    """CLI argument wins, then the environment variable. Exits with the two
    ways to supply it rather than falling back to a path that only exists on
    one machine."""
    load_local_env()
    raw = cli_value or os.environ.get(env_var)
    if not raw:
        sys.exit(f"No {what} given: pass --{what} or set {env_var} (in .env at the repository root, see .env.example)")
    path = Path(raw).expanduser()
    return path


def scan_corpus(corpus_dir):
    """Hash every .ifc in `corpus_dir`, returning {content_key: {name, size}}
    plus a list of (key, name) pairs that collided on an already-seen key -
    two byte-identical files under different names."""
    models = Path(corpus_dir)
    if not models.is_dir():
        sys.exit(f"Corpus directory does not exist: {corpus_dir}")

    ifc_files = sorted(p for p in models.iterdir() if p.suffix.lower() == ".ifc")
    if not ifc_files:
        sys.exit(f"No .ifc files found in {corpus_dir}")

    total_bytes = sum(p.stat().st_size for p in ifc_files)
    print(f"{len(ifc_files)} models, {total_bytes / 2**30:.1f} GiB in {corpus_dir}")

    started = time.time()
    found, duplicates = {}, []
    for index, path in enumerate(ifc_files, start=1):
        key = compute_content_key(path)
        if key in found:
            duplicates.append((key, path.name, found[key]["name"]))
        else:
            found[key] = {"name": path.name, "size_bytes": path.stat().st_size}
        if index % PROGRESS_EVERY == 0 or index == len(ifc_files):
            print(f"  ... {index}/{len(ifc_files)} ({time.time() - started:.0f}s)",
                  flush=True)
    return found, duplicates


def merge(previous, found, corpus_dir):
    """Fold a fresh scan into the previous index. Returns (index, report)."""
    prior_models = (previous or {}).get("models", {}) if isinstance(previous, dict) else {}

    added, renamed, unchanged = [], [], 0
    models = {}
    for key, entry in found.items():
        was = prior_models.get(key)
        if was is None:
            added.append((key, entry["name"]))
        elif was.get("name") != entry["name"]:
            renamed.append((key, was.get("name"), entry["name"]))
        else:
            unchanged += 1
        models[key] = dict(entry)

    absent = []
    for key, entry in prior_models.items():
        if key in models:
            continue
        kept = dict(entry)
        kept["absent"] = True
        models[key] = kept
        absent.append((key, entry.get("name")))

    index = {
        "corpus_dir": str(corpus_dir),
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "count": len(found),
        "absent": sum(1 for e in models.values() if e.get("absent")),
        "models": models,
    }
    return index, {"added": added, "renamed": renamed,
                   "unchanged": unchanged, "absent": absent}


def print_listing(index):
    """The readable `ls` that content-addressed folder names cost you."""
    rows = sorted(index.get("models", {}).items(),
                  key=lambda kv: (bool(kv[1].get("absent")), kv[1].get("name") or ""))
    for key, entry in rows:
        flag = "  [absent]" if entry.get("absent") else ""
        size = entry.get("size_bytes") or 0
        print(f"{entry.get('name', '?'):<14} {key}  {size / 2**20:7.1f} MiB{flag}")
    print(f"\n{len(rows)} entries "
          f"({sum(1 for _, e in rows if e.get('absent'))} absent)")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--corpus", help="directory of .ifc models "
                                         "(env: BI2M_IFC_CORPUS)")
    parser.add_argument("--out", help="visual-output root holding index.json "
                                      "(env: BI2M_VIS_DIR)")
    parser.add_argument("--list", action="store_true",
                        help="print the existing index instead of rebuilding")
    args = parser.parse_args()

    out_dir = _resolve_dir(args.out, "BI2M_VIS_DIR", "out")
    index_path = out_dir / INDEX_NAME

    if args.list:
        existing = read_json_file(str(index_path))
        if not existing:
            sys.exit(f"No index at {index_path} - build it first")
        print_listing(existing)
        return

    corpus_dir = _resolve_dir(args.corpus, "BI2M_IFC_CORPUS", "corpus")
    previous = read_json_file(str(index_path))
    found, duplicates = scan_corpus(corpus_dir)
    index, report = merge(previous, found, corpus_dir)

    write_json(str(index_path), index, indent=2)

    print(f"\nwrote {index_path}")
    print(f"  indexed   {index['count']}")
    print(f"  added     {len(report['added'])}")
    print(f"  renamed   {len(report['renamed'])}")
    print(f"  unchanged {report['unchanged']}")
    print(f"  absent    {len(report['absent'])}")
    for key, was, now in report["renamed"][:10]:
        print(f"    renamed {was} -> {now}  ({key})")
    if len(report["renamed"]) > 10:
        print(f"    ... and {len(report['renamed']) - 10} more")
    for key, name in report["absent"][:10]:
        print(f"    absent  {name}  ({key}) - renders kept")
    for key, name, first in duplicates:
        print(f"    DUPLICATE bytes: {name} == {first}  ({key}) - indexed once")


if __name__ == "__main__":
    main()
