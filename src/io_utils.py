"""Shared file I/O helpers for the extraction pipeline."""

import json
import os


def write_json(path, data, indent=4):
    """Write `data` as JSON to `path`, raising IOError with context on
    failure. Atomic: writes to a temp file in the same directory first, then
    `os.replace()`s it over `path` - a process killed mid-write (Ctrl+C, OOM,
    crash) leaves the original file (or nothing) intact, never a truncated/
    invalid partial write. `os.replace` is same-filesystem-atomic on both
    POSIX and Windows, which is why the temp file is written next to `path`
    rather than into a generic temp dir.

    `indent` defaults to 4 (unchanged) for the human-read extraction outputs.
    Machine-read artifacts the browser fetches pass `indent=None`: measured on
    the intent store, indentation was 55% of the bytes on the wire (10.4MB
    indented vs 4.7MB compact), which is pure cost for a file nobody opens by
    hand. Creates `path`'s parent directory if it doesn't exist yet, so
    callers writing into a fresh per-file shard directory don't each need
    their own mkdir."""
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    tmp_path = os.path.join(directory, f".{os.path.basename(path)}.{os.getpid()}.tmp")
    try:
        with open(tmp_path, "w") as json_file:
            json.dump(data, json_file, indent=indent)
        os.replace(tmp_path, path)
    except IOError as e:
        raise IOError(f"Failed to write to {path}: {e}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def read_json_file(file_path):
    """Read JSON from `file_path`. Returns None on missing/invalid file content,
    or an empty list if the file itself does not exist."""
    if os.path.isfile(file_path):
        try:
            with open(file_path, "r") as file:
                return json.load(file)
        except FileNotFoundError:
            print(f"File {file_path} not found.")
            return None
        except json.JSONDecodeError:
            print(f"Error decoding JSON from {file_path}.")
            return None
    else:
        return []
