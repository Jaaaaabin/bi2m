"""Batch intent-recognition entry point.

Runs the detectors registered in src/recognition/registry.py against IFC
files in the data directory, writing results to
Interfaces/Frontend/core/public/res/intents/<fileKey>.json - one shard per
model, plus a small index.json catalogue - which is what
ThatOpenCompanyLoader.js fetches lazily for whichever model is actually open.
`--categories`/`--files` let a run cover only a subset of either, without
disturbing categories/files not being recomputed (see
recognition/writers.py's merge-by-category logic).

`<fileKey>` is the CONTENT-ADDRESSED key from src/file_identity.py (a
truncated SHA-256 of the file's own bytes), not a filename stem - the same
key the browser computes for the same file, so a result written here is
findable by whatever session opens that model next, whatever it is named
locally. See docs/architecture.md "One key for everything".

Output lives under public/res/, not a plain res/ sibling of index.html -
Vite only copies publicDir contents into a production build; the former
location was dev-server-only and silently absent from `npm run build`'s
dist/ (confirmed by inspection - a real, invisible-failure production gap,
since the frontend's fetch just falls back to "no data" on a 404, not an
error).

Usage:
    uv run python scripts/recognize_intents.py
    uv run python scripts/recognize_intents.py --categories alignment
    uv run python scripts/recognize_intents.py --files test_3 --categories connection
    uv run python scripts/recognize_intents.py --list-categories
    uv run python scripts/recognize_intents.py --no-cache   # ignore the extraction cache
"""

import argparse
import inspect
import traceback
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

import ifcopenshell  # noqa: E402

from extraction import IfcDataExtractor  # noqa: E402
from file_identity import resolve_file_identity  # noqa: E402
from io_utils import read_json_file, write_json  # noqa: E402
from recognition.preflight import format_report, format_zero_output, merge_report, preflight, zero_output  # noqa: E402
from recognition.registry import CATEGORIES  # noqa: E402
from recognition.session import ModelSession  # noqa: E402
from recognition.writers import read_preflight, recomputed_with_tombstones, write_category_manifest, write_intent_shard  # noqa: E402

DATA_DIR = REPO_ROOT / "data"
FRONTEND_RES_DIR = REPO_ROOT / "Interfaces" / "Frontend" / "core" / "public" / "res"
INTENT_CATEGORIES_PATH = FRONTEND_RES_DIR / "intent_categories.json"

# Bump when a change to src/extraction/ alters what any of the extraction
# keys below produce for unchanged input - a cached entry stamped with an
# older version is ignored and recomputed. The cache is only sound at all
# because its directory is keyed by file CONTENT (see build_extracted): same
# bytes plus same extraction code must mean same result.
#
# 2: geometry_iteration.iterate_shapes now yields in express-id order (it
#    used to be the worker pool's completion order, different every run).
#    Version-1 caches hold one arbitrary order each and must be recomputed.
#
# 3: columns.py and floors.py convert raw coordinates with the file's declared
#    length unit (src/ifc_units.py) instead of guessing millimetres from the
#    size of the numbers. Identical for every metre-authored file and for
#    test_6 (millimetres, whose coordinates all exceeded the old threshold);
#    different for centimetre, foot and georeferenced files.
EXTRACTION_CACHE_VERSION = 3
EXTRACTION_CACHE_FILENAME = "recognition_cache.json"


def resolve_categories(requested):
    # No argument and `all` mean the same thing: every registered category.
    # Until 2026-09-20 the default ran only the 4 `verified` ones, which made a
    # bare run the most redundant slice of the pipeline (~14% element coverage
    # against ~69%); `maturity` is now a trust badge only (see registry.py) and
    # a detector that fails is skipped by process_file, not allowed to abort
    # the run - so there is no longer a reason to hold anything back.
    if not requested or requested == ["all"]:
        return list(CATEGORIES)

    unknown = sorted(set(requested) - set(CATEGORIES))
    if unknown:
        raise SystemExit(
            f"Unknown categor{'y' if len(unknown) == 1 else 'ies'}: {', '.join(unknown)}. "
            f"Registered: {', '.join(CATEGORIES)}"
        )
    return requested


def resolve_files(requested):
    if not requested:
        return sorted(DATA_DIR.glob("*.ifc"))

    files = []
    for name in requested:
        candidate = Path(name)
        if candidate.suffix != ".ifc":
            candidate = candidate.with_suffix(".ifc")
        path = candidate if candidate.is_absolute() else DATA_DIR / candidate.name
        if not path.is_file():
            raise SystemExit(f"IFC file not found: {path}")
        files.append(path)
    return files


def build_extracted(ifc_path, file_key, needed_keys, use_cache=True):
    """Runs only the extraction steps a detector actually declared it needs
    (registry.py's per-category extraction_keys) - not the full
    extract_batch.py pipeline (floors/curtainwalls/glue/plots), none of which
    any current detector needs.

    Caches into <ifc_path's own folder>/extracted/<file_key>/, where file_key
    is the file's CONTENT key. That is what makes the cache trustworthy:
    under the old filename-stem key, "test_1" meant whatever file happened to
    be called that, so a cache hit could serve another model's extraction
    entirely, and the extraction was simply redone every run. Keyed by
    content, a hit provably describes the same bytes - so a repeat run (the
    common case when iterating on one detector, or re-running the same model
    from the viewer's Compute button) skips the expensive ifcopenshell
    geometry pass outright.

    For a plain data/test_3.ifc this is data/extracted/<key>/, shared with
    extract_batch.py; for a remotely-uploaded file at
    data/uploads/<key>/<key>.ifc (see vite.config.js's /api/upload-ifc) it
    nests at data/uploads/<key>/extracted/<key>/.
    """
    extracted_dir = ifc_path.parent / "extracted" / file_key
    cache_path = extracted_dir / EXTRACTION_CACHE_FILENAME

    cached = {}
    if use_cache:
        stored = read_json_file(str(cache_path))
        if isinstance(stored, dict) and stored.get("cacheVersion") == EXTRACTION_CACHE_VERSION:
            cached = stored.get("extracted", {}) or {}

    missing = [key for key in needed_keys if key not in cached]
    extracted = {key: cached[key] for key in needed_keys if key in cached}
    if not missing:
        print(f"  extraction: {len(extracted)} key(s) from cache")
        return extracted

    # Only construct the extractor (which opens the model and walks every
    # element type) if something actually has to be recomputed.
    extractor = IfcDataExtractor(str(ifc_path), str(extracted_dir))

    # Every list below is sorted by element GUID before it is used or cached.
    # The geometry iterator behind them runs a worker pool and yields in
    # completion order, which differs run to run (geometry_iteration.py says
    # why it cannot sort the shapes itself). Left as-is, that order leaked
    # into intent output: alignment members listed differently each run, and
    # structural_wall_support IDS changed, because that id joins member guids
    # sorted by storey rank and a stable sort keeps iteration order for walls
    # on the same storey - orphaning any verdict keyed to the id. Measured
    # 2026-09-19 (two --no-cache runs, same bytes). No producer imposes an
    # order of its own and no detector reads list position, so this is the
    # one place that makes the whole recognition output reproducible.
    by_guid = lambda infos: sorted(infos, key=lambda info: info["id"])

    if "info_st_columns" in missing:
        extractor.extract_all_columns()
        extracted["info_st_columns"] = by_guid(extractor.info_st_columns)
    if "info_st_walls" in missing:
        extractor.extract_structural_walls_only()
        extracted["info_st_walls"] = by_guid(extractor.info_st_walls)
    if "info_envelope_shapes" in missing:
        extractor.extract_envelope_shapes()
        extracted["info_envelope_shapes"] = by_guid(extractor.info_envelope_shapes)

    # Merge rather than replace: a later run needing a different key set must
    # not throw away keys an earlier run already paid for.
    merged = dict(cached)
    merged.update(extracted)
    write_json(str(cache_path), {
        "cacheVersion": EXTRACTION_CACHE_VERSION,
        "fileKey": file_key,
        "extracted": merged,
    }, indent=None)

    if extracted and len(extracted) > len(missing):
        print(f"  extraction: {len(missing)} key(s) computed, {len(extracted) - len(missing)} from cache")
    return extracted


def _accepts_graph(detector):
    return "graph" in inspect.signature(detector).parameters


def _shared_access_graph(model, category_ids):
    """One door/space graph per model for every category whose detect() takes
    `graph=` (room_access, egress_fire and repeated_units, which hand it to
    their part modules; detectors/merged.py) - built here once instead of once per detector
    (it was four identical triangulation passes; docs/architecture.md
    "Recognition"). Same class, same
    default margin, so the output is what each detector would have built for
    itself. None when no requested category wants it, when the model has no
    spaces or doors, or when building it fails - in that last case every
    detector falls back to building its own and fails or succeeds alone."""
    if not any(_accepts_graph(CATEGORIES[cid]["detector"]) for cid in category_ids):
        return None
    if not model.by_type("IfcSpace") or not model.by_type("IfcDoor"):
        return None
    try:
        from recognition.access_graph import AccessGraph
        return AccessGraph(model)
    except Exception as e:  # noqa: BLE001 - the detectors will report it individually
        print(f"  shared door/space graph could not be built ({type(e).__name__}: {e}); detectors build their own")
        return None


def process_file(ifc_path, category_ids, use_cache=True):
    identity = resolve_file_identity(ifc_path, ifc_path.name)
    file_key = identity["key"]
    print(f"Recognizing {ifc_path.name} [{file_key}] -> categories: {', '.join(category_ids)}")

    needed_keys = {key for category_id in category_ids for key in CATEGORIES[category_id]["extraction_keys"]}
    extracted = build_extracted(ifc_path, file_key, needed_keys, use_cache=use_cache) if needed_keys else None

    # Opened after the extraction cache is consulted - a fully-cached run of
    # detectors that need no raw model at all still has to open it here, but
    # a cached run never pays for the extractor's own second open.
    model = ifcopenshell.open(str(ifc_path))
    # One explicit model session per file (recognition/session.py, 2026-10-22):
    # the property-set memo every detector, preflight and the Neufert Context
    # read through, closed when the file is done so a corpus run keeps one model alive.
    session = ModelSession.of(model, file_key=file_key, path=ifc_path)
    try:

        # The shared door graph is built before pre-flight (2026-10-08) so the
        # footprint verdict (`footprints:usable`) can be judged on it; None when
        # no requested category takes a graph, and then that verdict is skipped.
        shared_graph = _shared_access_graph(model, category_ids)

        # Pre-flight (docs/architecture.md "Recognition"): which of the requested categories have
        # no input signal in this model, and which are unlikely to produce output
        # (soft signals, 2026-10-08). Printed before the detectors run and
        # written into the shard, so "0 intents" and "cannot apply here" stop
        # looking identical. The categories still run - the probe only labels.
        # Computed over EVERY registered category, not just this run's subset: the
        # report is stored in the shard for the panel, which shows all categories.
        # Only the requested ones are printed here.
        report = preflight(model, CATEGORIES, graph=shared_graph)
        print(format_report({**report,
                             "inapplicable": [e for e in report["inapplicable"] if e["category"] in category_ids],
                             "unlikely": [e for e in report["unlikely"] if e["category"] in category_ids]}))

        # One detector failing must not take the other twenty down with it, and
        # must not erase its own previous results either: write_intent_shard
        # drops every prior record whose category is being recomputed, so a
        # failed category is deliberately left OUT of `completed` - its last good
        # output stays in the shard until a run actually succeeds. The one-line
        # failure goes to stdout (the panel's Run button shows it), the traceback
        # to stderr so the cause is locatable without a re-run.
        intents = []
        completed = set()
        failed = []
        counts = {}
        for category_id in category_ids:
            detector = CATEGORIES[category_id]["detector"]
            kwargs = {"graph": shared_graph} if shared_graph is not None and _accepts_graph(detector) else {}
            try:
                found = detector(model, extracted, file_key, **kwargs)
            except Exception as e:  # noqa: BLE001 - a detector may fail for any reason; the run continues
                failed.append((category_id, e))
                print(f"  {category_id}: FAILED - {type(e).__name__}: {e} (previous results kept)")
                traceback.print_exc(file=sys.stderr)
                continue
            negative = sum(1 for p in found if p.get("polarity") == "negative")
            print(f"  {category_id}: {len(found)} intent(s)" + (f" ({negative} negative)" if negative else ""))
            if found and any(e["category"] == category_id for e in report["inapplicable"]):
                # The signals table in registry.py said this category could not
                # apply here, yet it produced output: the table is wrong for this
                # model. Loud, so it gets fixed rather than trusted.
                print(f"  WARNING: {category_id} was flagged inapplicable by pre-flight but produced "
                      f"{len(found)} intent(s) - check its `signals` in registry.py")
            intents.extend(found)
            completed.add(category_id)
            counts[category_id] = len(found)

        # Zero output, recorded on every run: applicable, ran,
        # produced nothing - stored beside the pre-flight report.
        report["zeroOutput"] = zero_output(report, [cid for cid in category_ids if cid in completed], counts, categories=CATEGORIES)
        if report["zeroOutput"]:
            print(format_zero_output(report["zeroOutput"]))

        # A tombstone's old records go when its successor completed, even if the
        # run never named the tombstone (the viewer's Run lists live categories
        # only); they stay when the successor failed (writers.py says why).
        recomputed = recomputed_with_tombstones(CATEGORIES, completed, failed=[cid for cid, _ in failed])
        # The shard is cumulative: a run of some categories folds its pre-flight
        # report into the stored one rather than replacing it (preflight.merge_report).
        report = merge_report(read_preflight(str(FRONTEND_RES_DIR), file_key), report, CATEGORIES, recomputed)
        write_intent_shard(
            str(FRONTEND_RES_DIR), file_key, intents,
            recomputed_categories=recomputed, known_categories=set(CATEGORIES),
            project_guid=identity["lineage"].get("projectGuid"),
            # Storey GUIDs are excluded from corroboration - nearly every intent
            # lists its storey in relatedGuids (corroboration.py).
            storey_guids={s.GlobalId for s in model.by_type("IfcBuildingStorey")},
            preflight=report,
            excluded_corroboration_pairs=frozenset(
                frozenset((cid, src)) for cid, info in CATEGORIES.items() for src in info.get("derived_from", ())
            ),
        )

        # Full lineage (which can include a real author name or an absolute
        # authoring-machine path) stays in the gitignored extraction cache, never
        # in the browser-served shard - see recognition/writers.py's header.
        write_json(str(ifc_path.parent / "extracted" / file_key / "identity.json"), identity)
        return file_key, failed
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description="Run intent-recognition detectors over IFC files.")
    parser.add_argument(
        "--categories",
        help="Comma-separated category ids to run. Default (and 'all'): every registered category.",
    )
    parser.add_argument(
        "--files",
        help="Comma-separated IFC file names (with or without .ifc) from the data directory. "
             "Default: every data/*.ifc file.",
    )
    parser.add_argument(
        "--list-categories", action="store_true", help="Print registered categories and exit.",
    )
    parser.add_argument(
        "--no-cache", action="store_true",
        help="Recompute extraction even when a content-keyed cache entry exists.",
    )
    args = parser.parse_args()

    if args.list_categories:
        for category_id, info in CATEGORIES.items():
            types = ", ".join(info["intent_types"]) if info["intent_types"] else f"retired into {info.get('retired', '?')}"
            print(f"{category_id} ({info['level']}/{info['domain']}, {info['maturity']}): {info['label']} -> {types}")
        return

    category_ids = resolve_categories(args.categories.split(",") if args.categories else None)
    ifc_files = resolve_files(args.files.split(",") if args.files else None)

    if not ifc_files:
        print(f"No .ifc files found in {DATA_DIR}")
        return

    written = []
    failures = []  # (file name, category id, error)
    for ifc_path in ifc_files:
        try:
            file_key, failed = process_file(ifc_path, category_ids, use_cache=not args.no_cache)
            written.append(file_key)
            failures.extend((ifc_path.name, category_id, e) for category_id, e in failed)
        except Exception as e:  # noqa: BLE001 - keep going with the next file
            print(f"Error recognizing intents in {ifc_path.name}: {type(e).__name__}: {e}")
            traceback.print_exc(file=sys.stderr)
            failures.append((ifc_path.name, "*", e))

    write_category_manifest(INTENT_CATEGORIES_PATH, CATEGORIES)
    shard_dir = (FRONTEND_RES_DIR / "intents").relative_to(REPO_ROOT)
    print(f"Wrote {len(written)} shard(s) under {shard_dir}/ and {INTENT_CATEGORIES_PATH.relative_to(REPO_ROOT)}")
    if failures:
        print(f"{len(failures)} failure(s) - shards were still written; the failed categories kept their previous results:")
        for name, category_id, e in failures:
            print(f"  {name} / {category_id}: {type(e).__name__}: {e}")
        # 2, not 1: "completed, with failures" - distinct from a run that
        # could not start. vite.config.js's Run endpoint reports ok only for 0,
        # so the panel shows this as a failure WITH the stdout above attached.
        sys.exit(2)


if __name__ == "__main__":
    main()
