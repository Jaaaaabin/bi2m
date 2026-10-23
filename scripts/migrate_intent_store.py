"""One-shot migration: legacy intent_groups.json -> content-keyed shards.

The old store was a single Interfaces/Frontend/core/public/res/
intent_groups.json keyed by filename stem (and, for anything computed
through the viewer's Compute button, by a compounding
"<stem>-<timestamp>[-<timestamp>...]" upload id). The current store (docs/architecture.md
"The shard") replaces that with one shard per model under
public/res/intents/, keyed by the file's own content hash.

This script moves what is still meaningful across and reports what is not:

- An entry whose key maps to an .ifc file still present (either data/<stem>.ifc
  or data/uploads/<uploadId>/<uploadId>.ifc) is rewritten as
  intents/<contentKey>.json. Several legacy keys can map to ONE content key -
  that is the point, and the reason the old file was 68% redundant - so their
  intents are merged, newest generatedAt winning per intent id.
- Intent IDS are re-keyed as part of that merge. Every detector builds its id
  as f"{file_key}-...", so the SAME intent computed under "test_0" and under
  "test_0-1789715078294" carries two different ids and would otherwise survive
  the merge twice (measured: 232 + 228 intents sharing 228 identical
  suffixes). The legacy key prefix is replaced with the content key first, so
  the merge actually collapses them. No detector changes - from here on
  detectors simply receive the content key as file_key and emit content-keyed
  ids natively.
- An entry whose source file is gone is ORPHANED: its intents can never be
  re-associated with a model, since nothing records what bytes produced them.
  Reported, not migrated.

Dry-run by default; pass --apply to write. Never deletes the legacy file -
removing it is a separate, deliberate `git rm`/`rm` once the shards are
verified.

That removal happened on 2026-09-21: `public/res/intent_groups.json` is gone
from the working tree (still in `HEAD`, so recoverable). There is therefore
nothing left for this script to read - it reports the missing file and exits.
It is kept as the record of how 28 legacy keys became 6 content-keyed shards,
and it is the only place the id re-keying is written down.

Usage:
    uv run python scripts/migrate_intent_store.py
    uv run python scripts/migrate_intent_store.py --apply
"""

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from file_identity import compute_content_key, read_ifc_lineage  # noqa: E402
from io_utils import read_json_file  # noqa: E402
from recognition.registry import CATEGORIES  # noqa: E402
from recognition.writers import write_intent_shard  # noqa: E402

DATA_DIR = REPO_ROOT / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
RES_DIR = REPO_ROOT / "Interfaces" / "Frontend" / "core" / "public" / "res"
LEGACY_PATH = RES_DIR / "intent_groups.json"


def resolve_source_file(legacy_key):
    """Where a legacy key's bytes would live, if they still exist."""
    plain = DATA_DIR / f"{legacy_key}.ifc"
    if plain.is_file():
        return plain
    upload = UPLOADS_DIR / legacy_key / f"{legacy_key}.ifc"
    if upload.is_file():
        return upload
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--apply", action="store_true", help="Actually write the shards (default: dry run).")
    args = parser.parse_args()

    legacy = read_json_file(str(LEGACY_PATH))
    if not isinstance(legacy, dict) or not legacy:
        print(f"Nothing to migrate: {LEGACY_PATH} is missing or not a JSON object.")
        return

    by_content_key = {}
    orphaned = []

    for legacy_key, entry in legacy.items():
        intents = (entry or {}).get("intents", [])
        source = resolve_source_file(legacy_key)
        if source is None:
            orphaned.append((legacy_key, len(intents)))
            continue
        content_key = compute_content_key(source)
        bucket = by_content_key.setdefault(content_key, {
            "intents": {},
            "legacyKeys": [],
            "projectGuid": read_ifc_lineage(source).get("projectGuid"),
        })
        bucket["legacyKeys"].append(legacy_key)
        # Merge by RE-KEYED intent id, newest generatedAt winning - duplicate
        # upload snapshots of one model are exactly what produced the
        # redundancy, and re-keying is what lets them actually collapse.
        for intent in intents:
            rekeyed = _rekey_intent(intent, legacy_key, content_key)
            existing = bucket["intents"].get(rekeyed["id"])
            if existing is None or _generated_at(rekeyed) >= _generated_at(existing):
                bucket["intents"][rekeyed["id"]] = rekeyed

    print(f"Legacy entries: {len(legacy)}")
    print(f"Distinct models after content-keying: {len(by_content_key)}")
    for content_key, bucket in sorted(by_content_key.items()):
        print(f"  {content_key}: {len(bucket['intents'])} intent(s) "
              f"from {len(bucket['legacyKeys'])} legacy key(s) -> {', '.join(sorted(bucket['legacyKeys']))}")
    if orphaned:
        total = sum(count for _, count in orphaned)
        print(f"\nOrphaned (source .ifc no longer present, NOT migrated): "
              f"{len(orphaned)} key(s), {total} intent(s)")
        for key, count in sorted(orphaned):
            print(f"  {key}: {count} intent(s)")

    if not args.apply:
        print("\nDry run - nothing written. Re-run with --apply to write the shards.")
        return

    for content_key, bucket in sorted(by_content_key.items()):
        intents = list(bucket["intents"].values())
        detectors = {p["provenance"]["detector"] for p in intents if p.get("provenance")}
        path = write_intent_shard(
            str(RES_DIR), content_key, intents,
            # Every detector present is "recomputed" here so nothing prior is
            # kept: this migration is the authoritative content of the shard.
            recomputed_categories=detectors,
            known_categories=set(CATEGORIES) | detectors,
            project_guid=bucket["projectGuid"],
        )
        print(f"Wrote {Path(path).relative_to(REPO_ROOT)} ({len(intents)} intent(s))")

    print(f"\nDone. {LEGACY_PATH.relative_to(REPO_ROOT)} was left in place - "
          f"remove it yourself once the shards look right.")


def _rekey_intent(intent, legacy_key, content_key):
    """Swap an intent id's leading legacy file key for the content key.

    Only the exact "<legacy_key>-" prefix is replaced, and only when present -
    an id that does not carry it (a hand-authored fixture, a detector that
    ever stopped prefixing) is passed through untouched rather than guessed
    at. Returns a copy; the input dict is left alone."""
    intent_id = intent.get("id", "")
    prefix = f"{legacy_key}-"
    if not intent_id.startswith(prefix):
        return intent
    return {**intent, "id": f"{content_key}-{intent_id[len(prefix):]}"}


def _generated_at(intent):
    return (intent.get("provenance") or {}).get("generatedAt") or ""


if __name__ == "__main__":
    main()
