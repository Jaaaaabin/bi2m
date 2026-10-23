"""Reclaim duplicate browser uploads under data/uploads/.

The dev server's /api/upload-ifc used to name each upload folder
"<fileKey>-<Date.now()>", so every press of the intent panel's Run button
wrote a brand-new copy of the same 20MB model - measured at 317MB across ~20
folders holding 7 distinct files. Content-addressed uploads
stop the growth: the server now names the folder by the file's own
content key and skips the write when it already has those bytes. This script
reclaims what the old scheme already accumulated.

Grouping is by CONTENT, never by name: every data/uploads/*/ folder's .ifc is
hashed, folders sharing a hash are one model, and one folder per model is
kept. Preference order for which to keep:
  1. a folder already named with the model's content key (the new layout)
  2. otherwise the OLDEST legacy folder, so the longest-lived path on disk is
     the survivor
A folder whose .ifc is missing or unreadable is reported and never touched.

Dry-run by default; --apply deletes. Deletion is recursive and permanent, so
--apply also requires the folders it is about to remove to have been listed
in the same run's output.

Usage:
    uv run python scripts/prune_uploads.py
    uv run python scripts/prune_uploads.py --apply
"""

import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from file_identity import compute_content_key  # noqa: E402

UPLOADS_DIR = REPO_ROOT / "data" / "uploads"


def folder_size(path):
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def human(num_bytes):
    for unit in ("B", "KB", "MB", "GB"):
        if abs(num_bytes) < 1024 or unit == "GB":
            return f"{num_bytes:.1f}{unit}"
        num_bytes /= 1024


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--apply", action="store_true", help="Actually delete (default: dry run).")
    args = parser.parse_args()

    if not UPLOADS_DIR.is_dir():
        print(f"No uploads directory at {UPLOADS_DIR}")
        return

    by_key = {}
    unreadable = []

    for folder in sorted(UPLOADS_DIR.iterdir()):
        if not folder.is_dir():
            continue
        ifc_files = sorted(folder.glob("*.ifc"))
        if not ifc_files:
            unreadable.append((folder, "no .ifc inside"))
            continue
        try:
            key = compute_content_key(ifc_files[0])
        except OSError as e:
            unreadable.append((folder, str(e)))
            continue
        by_key.setdefault(key, []).append(folder)

    total_reclaimed = 0
    to_delete = []

    for key, folders in sorted(by_key.items()):
        named_by_key = [f for f in folders if f.name == key]
        keep = named_by_key[0] if named_by_key else min(folders, key=lambda f: f.stat().st_mtime)
        drop = [f for f in folders if f != keep]
        sizes = {f: folder_size(f) for f in folders}
        print(f"{key}: {len(folders)} folder(s), {human(sum(sizes.values()))}")
        print(f"  keep   {keep.name}  ({human(sizes[keep])})")
        for f in drop:
            print(f"  delete {f.name}  ({human(sizes[f])})")
            total_reclaimed += sizes[f]
        to_delete.extend(drop)

    if unreadable:
        print("\nSkipped (left untouched):")
        for folder, why in unreadable:
            print(f"  {folder.name}: {why}")

    print(f"\nDistinct models: {len(by_key)} | folders to delete: {len(to_delete)} | "
          f"reclaims: {human(total_reclaimed)}")

    if not to_delete:
        return
    if not args.apply:
        print("Dry run - nothing deleted. Re-run with --apply to delete the folders listed above.")
        return

    for folder in to_delete:
        shutil.rmtree(folder)
        print(f"Deleted {folder.name}")
    print(f"Reclaimed {human(total_reclaimed)}.")


if __name__ == "__main__":
    main()
