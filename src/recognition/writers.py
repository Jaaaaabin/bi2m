"""JSON output for recognition results.

Layout (replaces the single whole-corpus `intent_groups.json`; see
docs/architecture.md "The shard"):

    public/res/intents/<fileKey>.json   one shard per model
    public/res/intents/index.json       small catalogue of the shards
    public/res/intent_categories.json   the global category vocabulary

`<fileKey>` is the content-addressed key from `file_identity.py`, NOT a
filename stem - see docs/architecture.md "One key for everything" for
why.

Why sharded. The previous single file had to be read AND rewritten in full to
record one category of one model: it had grown to 10.4MB / 28 entries, of
which 21 (7.1MB) were orphaned upload snapshots of the same 7 models. The
browser fetched all of it on every page load to use exactly one entry
(~200KB). Sharding makes both sides O(one model): Python rewrites one shard,
the browser fetches one shard lazily when that model is actually opened.

Merge-by-category is unchanged in spirit and now happens within a shard:
re-running one category must not erase another category's previously-computed
intents for the same model.

What is deliberately NOT published. Each shard carries the opaque
`IfcProject` GlobalId as `projectGuid` (useful later for offering "carry
verdicts forward from the previous export of this project?") but NOT the
`lineage.ifcFileName`/`fileName` strings `file_identity.py` also resolves -
those are frequently a real author name or an absolute authoring-machine path
(confirmed across this repo's own fixtures), and this directory is served to
the browser and may be committed. Local provenance belongs in the gitignored
extraction cache, not here.
"""

import os
from collections import defaultdict
from datetime import datetime, timezone

from io_utils import read_json_file, write_json

from .corroboration import annotate_corroboration

INTENTS_DIRNAME = "intents"
INDEX_FILENAME = "index.json"
# Bumped only if a shard's own envelope shape changes; the intent records
# inside it keep the existing schema vocabulary untouched.
# 2 (2026-09-24): the envelope's list key was renamed `patterns` -> `intents`
# and index.json's per-file `patternCount` -> `intentCount`, with the project's
# "pattern" -> "intent" rename. Nothing inside a record changed and the ids are
# byte-identical, so a v1 shard holds exactly the right data under the wrong
# key - which is why the version has to move: the reader's array check would
# otherwise see no `intents`, fall back to an empty list, and render "no
# recognized intents" for a model that has hundreds.
STORE_VERSION = 2


def intents_dir(res_dir):
    return os.path.join(res_dir, INTENTS_DIRNAME)


def shard_path(res_dir, file_key):
    return os.path.join(intents_dir(res_dir), f"{file_key}.json")


def index_path(res_dir):
    return os.path.join(intents_dir(res_dir), INDEX_FILENAME)


def _read_dict(path):
    existing = read_json_file(path)
    return existing if isinstance(existing, dict) else {}


def write_intent_shard(res_dir, file_key, new_intents, recomputed_categories,
                        known_categories, project_guid=None, storey_guids=frozenset(),
                        preflight=None, excluded_corroboration_pairs=frozenset()):
    """Write one model's shard, merging by category.

    `known_categories` is the full registry (registry.CATEGORIES.keys()), not
    just this run's `recomputed_categories` - a prior intent is kept only if
    it belongs to a category that is both registered AND not being recomputed
    right now. That also retires stray non-registered detector ids (e.g. the
    original hand-authored mock's "mock.manual") the first time any real
    category is recomputed for that model, rather than leaving them stuck in
    the output forever because they never match any real category's
    recomputed set."""
    path = shard_path(res_dir, file_key)
    existing = _read_dict(path)

    prior_intents = existing.get("intents", [])
    kept = [
        p for p in prior_intents
        if p["provenance"]["detector"] in known_categories
        and p["provenance"]["detector"] not in recomputed_categories
    ]
    intents = kept + new_intents

    # Display handle "<category>-<NNN>", numbered per category over the MERGED
    # list (kept + new together) in id order, so a human can say "structural
    # -017" instead of a 60-character id. It is re-derived on every write:
    # when an intent appears or disappears, later numbers in that category
    # shift. Anything that must survive a re-run - verdicts, the planned
    # `corroborates` cross-reference - keys on `id`, never on this.
    by_category = defaultdict(list)
    for intent in intents:
        by_category[intent["provenance"]["detector"]].append(intent)
    for category_id, group in by_category.items():
        for number, intent in enumerate(sorted(group, key=lambda p: p["id"]), start=1):
            intent["index"] = f"{category_id}-{number:03d}"

    # `corroborates`: other-detector intents whose element set
    # coincides with this one's. Recomputed over the merged list on every
    # write, keyed on `id` (never `index`) - see corroboration.py.
    annotate_corroboration(intents, storey_guids=set(storey_guids), excluded_pairs=excluded_corroboration_pairs)

    write_json(path, {
        "storeVersion": STORE_VERSION,
        "fileKey": file_key,
        # Preserved if this shard already had one and this run didn't resolve
        # it, so a re-run from a path that can't read the header doesn't drop
        # provenance that was already known.
        "projectGuid": project_guid if project_guid is not None else existing.get("projectGuid"),
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        # Which categories cannot produce output for THIS model, and why
        # (preflight.py). Preserved from the previous write when this run did
        # not compute one, like projectGuid.
        "preflight": preflight if preflight is not None else existing.get("preflight"),
        "intents": intents,
    }, indent=None)

    _update_index(res_dir, file_key, intents)
    return path


def _update_index(res_dir, file_key, intents):
    """Small catalogue so a future "which models have results?" view costs one
    fetch instead of one per shard. Rewritten whole - it stays tiny (one short
    record per model) no matter how many intents each shard holds, which is
    exactly the property the old monolith lacked."""
    path = index_path(res_dir)
    index = _read_dict(path)
    files = index.get("files")
    if not isinstance(files, dict):
        files = {}

    categories = sorted({p["provenance"]["detector"] for p in intents if p.get("provenance")})
    files[file_key] = {
        "intentCount": len(intents),
        "categories": categories,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    write_json(path, {"storeVersion": STORE_VERSION, "files": files}, indent=None)


def recomputed_with_tombstones(categories, completed, failed=()):
    """The categories whose prior records a write must drop: the ones this
    run completed, plus every tombstone (registry.py `retired`) whose
    successor completed. A run that names only live categories - the
    viewer's Run button lists no tombstone - must still retire the old
    records, or a shard written before the merge keeps each record twice,
    under the old category and the new (found in review, 2026-10-08). A
    tombstone whose successor FAILED is never dropped, even when the run
    named it: its old records are all that model has until the successor
    runs (the CLI's rule that a failed category keeps its previous records).
    """
    completed, failed = set(completed), set(failed)
    out = set(completed)
    for category_id, info in categories.items():
        successor = info.get("retired")
        if not successor:
            continue
        if successor in completed:
            out.add(category_id)
        elif successor in failed:
            out.discard(category_id)
    return out


def read_preflight(res_dir, file_key):
    """The pre-flight report a shard already holds, None without a shard -
    what preflight.merge_report folds a partial run into."""
    return _read_dict(shard_path(res_dir, file_key)).get("preflight")


def write_category_manifest(output_path, categories):
    """The category vocabulary the panel groups/colors by - generated fresh
    from registry.CATEGORIES every run, never keyed per file (categories are a
    fixed, global vocabulary). Carries each category's domain/level/maturity,
    and `retired` on a tombstone, so the frontend needs no copy of that
    classification.

    Stays indented: it is small (a few KB), and it is the one artifact here a
    human might reasonably open to see which categories exist."""
    manifest = []
    for category_id, info in categories.items():
        entry = {
            "id": category_id,
            "label": info["label"],
            "intentTypes": info["intent_types"],
            "domain": info["domain"],
            # The spatial level the panel groups by (registry.py, 2026-10-08);
            # it replaced `scope`, which nothing in the viewer read.
            "level": info["level"],
            "maturity": info["maturity"],
        }
        # A tombstone keeps its position for the colour contract and names
        # its successor; the panel's Compute list hides it.
        if info.get("retired"):
            entry["retired"] = info["retired"]
        # A category with its own panel section (the Neufert Topics,
        # 2026-10-18): the panel groups by `section` before `level`.
        if info.get("section"):
            entry["section"] = info["section"]
        manifest.append(entry)
    write_json(output_path, manifest)
