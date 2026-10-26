#!/usr/bin/env python3
"""Batch pre-conversion of IFC models into streamable tile sets.

The offline half of the interface review's first finding
(docs/architecture.md "Viewer"): a model the viewer has to parse in the browser takes seconds of
frozen main thread, and the same model streamed from a tile set is on screen
before the user's hand leaves the mouse. Measured on test_5.ifc (18.5 MB):
13.1 s to a reviewable panel parsed, 0.6 s streamed, after 3.0 s of conversion
here.

    npm run dev                       # in viewer, another shell
    uv run python scripts/tile_corpus.py --dry-run     # what is missing
    uv run python scripts/tile_corpus.py --stride 30   # a spread, to sanity-check
    uv run python scripts/tile_corpus.py               # the whole library
    uv run python scripts/tile_corpus.py --fixtures    # data/*.ifc instead

This drives `viewer/scripts/tileIfc.mjs` once per model
rather than reimplementing it: that script is what `/api/upload-ifc` already
spawns for an uploaded file, so a batch-tiled model and an uploaded one get
byte-identical treatment. Nothing about the conversion lives here.

READS the corpus, WRITES only inside the repo. Tile sets go to
`viewer/public/tiles/<content_key>/`, which is a gitignored
build artifact (.gitignore) - so no BI2M_* output variable, unlike
autocamera.py's $BI2M_VIS_DIR. The corpus itself is never written to.

Resumable: a model whose `tileset.json` already exists is skipped unless
--force. tileIfc.mjs writes that file last, so an interrupted conversion does
not look finished.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time
import urllib.request

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
FRONTEND_CORE = REPO_ROOT / "viewer"
TILER = FRONTEND_CORE / "scripts" / "tileIfc.mjs"
TILES_DIR = FRONTEND_CORE / "public" / "tiles"
sys.path.append(str(REPO_ROOT / "src"))

from local_env import env_path  # noqa: E402

DEFAULT_CORPUS = env_path("BI2M_IFC_CORPUS")
BASE_URL = "http://localhost:3000"


def mb(num_bytes: float) -> float:
    return num_bytes / 1048576


def dir_size(path: pathlib.Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def library_models(url: str) -> list[dict]:
    """The corpus as the viewer sees it: content-keyed, and already without the
    keys the vis index flags `absent` (370 of 518 at the time of writing). Read
    from the running dev server rather than from the index on disk, so this
    driver and the Library button can never disagree about what exists."""
    with urllib.request.urlopen(f"{url}/api/library-models", timeout=30) as response:
        payload = json.load(response)
    if not payload.get("ok"):
        sys.exit(f"{url}/api/library-models returned ok=false: {payload}")
    return payload["files"]


def content_key(path: pathlib.Path) -> str:
    """The same 16-hex content key fileIdentity.js, src/file_identity.py and
    tileIfc.mjs all derive: the first 64 bits of the SHA-256 of the bytes.
    Recomputed here only so --dry-run and the resume skip can name a fixture's
    tile directory without shelling out to the tiler first."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def fixture_models() -> list[dict]:
    """data/*.ifc - the handful of models the e2e harnesses load. Two fixtures
    can share one key (test_1.ifc and test_2.ifc are the same bytes), and the
    tile set is named by the key, so the duplicate is dropped rather than
    converted twice."""
    seen: set[str] = set()
    models = []
    for path in sorted((REPO_ROOT / "data").glob("*.ifc")):
        key = content_key(path)
        if key in seen:
            continue
        seen.add(key)
        models.append({"fileKey": key, "fileName": path.name, "sizeBytes": path.stat().st_size})
    return models


def already_tiled(file_key: str | None) -> bool:
    return bool(file_key) and (TILES_DIR / file_key / "tileset.json").is_file()


def tile_one(source: pathlib.Path, timeout: float) -> dict:
    """One `node scripts/tileIfc.mjs <file>` run. cwd is the frontend core so
    the tiler resolves its own node_modules and its default output directory."""
    started = time.time()
    try:
        proc = subprocess.run(
            ["node", str(TILER), str(source)],
            cwd=str(FRONTEND_CORE),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "seconds": time.time() - started, "stderr": ""}
    seconds = time.time() - started
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-4:]
        return {"status": "failed", "seconds": seconds, "stderr": " | ".join(tail)}
    # The tiler prints the key it chose; the output directory is named by it.
    return {"status": "tiled", "seconds": seconds, "stderr": ""}


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--url", default=BASE_URL, help="dev server, for the model list")
    parser.add_argument("--corpus", default=DEFAULT_CORPUS,
                        help="directory holding the library's .ifc files (env: BI2M_IFC_CORPUS)")
    parser.add_argument("--fixtures", action="store_true",
                        help="tile data/*.ifc instead of the library")
    parser.add_argument("--keys", help="comma-separated content keys, instead of everything")
    parser.add_argument("--limit", type=int, help="only the first N of the selection")
    parser.add_argument("--stride", type=int,
                        help="every Nth model by size - a spread across the corpus, for a sample run")
    parser.add_argument("--force", action="store_true", help="re-tile models that already have a tile set")
    parser.add_argument("--dry-run", action="store_true", help="list what would be tiled, write nothing")
    parser.add_argument("--timeout", type=float, default=600.0, help="seconds per model")
    parser.add_argument("--json", dest="json_out", help="write a per-model record to this path")
    args = parser.parse_args()

    if not TILER.is_file():
        sys.exit(f"tiler not found: {TILER}")
    if shutil.which("node") is None:
        sys.exit("node is not on PATH - the tiler is a Node script")

    corpus = pathlib.Path(args.corpus) if args.corpus else None
    if args.fixtures:
        models = fixture_models()
        source_dir = REPO_ROOT / "data"
    else:
        models = library_models(args.url)
        source_dir = corpus
        if corpus is None or not corpus.is_dir():
            sys.exit(f"corpus directory not found: {corpus} (pass --corpus or set BI2M_IFC_CORPUS (in .env at the repository root, see .env.example))")

    models.sort(key=lambda m: m["sizeBytes"])
    if args.keys:
        wanted = {k.strip() for k in args.keys.split(",") if k.strip()}
        models = [m for m in models if m["fileKey"] in wanted]
    if args.stride:
        models = models[:: args.stride]
    if args.limit:
        models = models[: args.limit]

    todo, skipped = [], 0
    for model in models:
        if not args.force and already_tiled(model["fileKey"]):
            skipped += 1
            continue
        todo.append(model)

    print(f"{len(models)} selected, {skipped} already tiled, {len(todo)} to convert")
    if args.dry_run:
        for model in todo[:20]:
            print(f"  would tile {model['fileName']:<14} {mb(model['sizeBytes']):6.1f} MB")
        if len(todo) > 20:
            print(f"  ... and {len(todo) - 20} more")
        return 0

    records, failures = [], []
    source_total = tiles_total = 0
    started = time.time()
    for index, model in enumerate(todo, start=1):
        source = source_dir / model["fileName"]
        if not source.is_file():
            record = {"status": "missing", "seconds": 0.0, "stderr": str(source)}
        else:
            record = tile_one(source, args.timeout)
        record.update(key=model["fileKey"], name=model["fileName"], sizeBytes=model["sizeBytes"])
        if record["status"] == "tiled" and model["fileKey"]:
            out = TILES_DIR / model["fileKey"]
            record["tileBytes"] = dir_size(out) if out.is_dir() else 0
            source_total += model["sizeBytes"]
            tiles_total += record["tileBytes"]
            ratio = record["tileBytes"] / model["sizeBytes"] if model["sizeBytes"] else 0
            print(f"[{index}/{len(todo)}] {model['fileName']:<14} {mb(model['sizeBytes']):6.1f} MB"
                  f" -> {mb(record['tileBytes']):7.1f} MB ({ratio:.2f}x) in {record['seconds']:5.1f}s")
        else:
            failures.append(record)
            print(f"[{index}/{len(todo)}] {model['fileName']:<14} {record['status'].upper()}"
                  f" after {record['seconds']:.1f}s - {record['stderr'][:160]}")
        records.append(record)

    elapsed = time.time() - started
    done = [r for r in records if r["status"] == "tiled"]
    print(f"\n{len(done)}/{len(todo)} tiled in {elapsed / 60:.1f} min")
    if done:
        print(f"  {mb(source_total) / 1024:.2f} GB of IFC -> {mb(tiles_total) / 1024:.2f} GB of tiles"
              f" ({tiles_total / source_total:.2f}x), median {sorted(r['seconds'] for r in done)[len(done) // 2]:.1f}s per model")
    if failures:
        print(f"  {len(failures)} did not convert:")
        for record in failures:
            print(f"    {record['name']} [{record['status']}] {record['stderr'][:200]}")
    if args.json_out:
        pathlib.Path(args.json_out).write_text(json.dumps(records, indent=1))
        print(f"  per-model record: {args.json_out}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
