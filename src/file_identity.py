"""Content-addressed file identity - the Python half of
Interfaces/Frontend/core/fileIdentity.js.

Both sides must produce the SAME key for the same bytes, since that key is
what joins a browser session's model to the intent results this pipeline
writes for it. See the JS module's header for why identity moved off the
filename stem in the first place, and docs/architecture.md
"One key for everything".

Keep in sync with fileIdentity.js:
    - algorithm: SHA-256 over the full, raw file bytes
    - KEY_HEX_CHARS: how much of the lowercase hex digest is kept
"""

import hashlib
import re

# Must match fileIdentity.js's own KEY_HEX_CHARS.
KEY_HEX_CHARS = 16

# Read in chunks rather than slurping the whole file - these are routinely
# 20MB+ and can be up to the ~100MB target.
_HASH_CHUNK_BYTES = 1 << 20

# Same tolerant header scan as the JS side: IFC is ISO-10303-21 text, the
# HEADER section is at the very top, so only the first slice is read.
_HEADER_SCAN_BYTES = 65536
_FILE_NAME_RE = re.compile(rb"FILE_NAME\s*\(\s*'((?:[^']|'')*)'", re.IGNORECASE)
_PROJECT_GUID_RE = re.compile(rb"IFCPROJECT\s*\(\s*'((?:[^']|'')*)'", re.IGNORECASE)


def compute_content_key(path):
    """SHA-256 of `path`'s raw bytes, truncated to KEY_HEX_CHARS hex chars."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(_HASH_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()[:KEY_HEX_CHARS]


def compute_content_key_from_bytes(data):
    """Same key, for bytes already in memory."""
    return hashlib.sha256(data).hexdigest()[:KEY_HEX_CHARS]


def _unescape_step_string(value):
    return value.decode("utf-8", "replace").replace("''", "'") if value is not None else None


def read_ifc_lineage(path, file_name=None):
    """Weaker, re-export-stable identifiers from the file's own IFC header -
    recorded for provenance beside the exact content key, never joined on.
    Mirrors fileIdentity.js's readIfcLineage()."""
    lineage = {"fileName": file_name, "ifcFileName": None, "projectGuid": None}
    try:
        with open(path, "rb") as handle:
            head = handle.read(_HEADER_SCAN_BYTES)
        name_match = _FILE_NAME_RE.search(head)
        guid_match = _PROJECT_GUID_RE.search(head)
        lineage["ifcFileName"] = _unescape_step_string(name_match.group(1) if name_match else None)
        lineage["projectGuid"] = _unescape_step_string(guid_match.group(1) if guid_match else None)
    except OSError:
        pass  # lineage is never load-critical
    return lineage


def resolve_file_identity(path, file_name=None):
    """The one call every Python entry point uses, mirroring the JS
    resolveFileIdentity(). Unlike the browser there is no secure-context
    caveat here - hashlib is always available - so `keySource` is always
    "content"; the field exists so both sides' records have the same shape."""
    return {
        "key": compute_content_key(path),
        "keySource": "content",
        "fileName": file_name,
        "lineage": read_ifc_lineage(path, file_name),
    }
