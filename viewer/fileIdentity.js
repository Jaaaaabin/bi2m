// ======== File Identity (content-addressed) ========
// One model = one key, derived from the file's own BYTES, not its name.
//
// Everything in this app joins on a per-file key: the GUID highlight map,
// recognized intent groups, human verdicts (localStorage), the server's
// upload folder, and the Python extraction cache. That key used to be
// `file.name.split(".")[0]` - a filename stem - which is neither stable nor
// unique, and produced four measured defects:
// results computed under an upload-suffixed key were unreachable on the next
// page load, verdicts were silently orphaned the same way, upload keys
// compounded ("<key>-<ts>-<ts>-<ts>"), and a dotted filename
// ("Building.v2.ifc") collided with its own sibling.
//
// A content hash fixes all four at once: the same bytes produce the same key
// on every machine, in every session, whatever the file happens to be called
// - which also makes uploading idempotent (the server can recognize a file
// it already has instead of writing a 20MB duplicate) and gives the
// per-file tile-set lookup (tileSet.js) a key it can trust.
//
// Design choice implemented here (docs/architecture.md "One key for
// everything"): the KEY is an exact hash of the full file bytes (so it can
// never match two genuinely different models), while the IFC header's own
// weaker, re-export-stable identifiers are recorded ALONGSIDE it as
// `lineage`. That keeps the default behavior exact, and leaves the data
// present to offer "carry this model's verdicts forward from its previous
// export?" later without a re-keying migration.

// 16 hex chars = 64 bits of a SHA-256. Long enough that an accidental
// collision across any plausible number of models is not a real concern,
// short enough to stay readable in a folder name, a log line, and a
// localStorage key. Must match src/file_identity.py's KEY_HEX_CHARS.
const KEY_HEX_CHARS = 16;

function toHex(buffer) {
  return Array.from(new Uint8Array(buffer))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

/**
 * Content key for an IFC file's raw bytes.
 *
 * `crypto.subtle` is only exposed in a secure context - which covers this
 * app's documented setup (the localhost URL Vite prints, including through
 * an SSH port-forward, since the browser still sees localhost) and any real
 * https deployment, but NOT a plain-http LAN address. Rather than silently
 * computing a DIFFERENT key in that case - which would be worse than no
 * content key at all, since two contexts would disagree about what the same
 * file is - this returns null and lets the caller fall back to the legacy
 * filename-stem key with a visible warning.
 *
 * @param {ArrayBuffer} arrayBuffer - must not have been transferred/detached yet.
 * @returns {Promise<string|null>} 16-char hex key, or null if unavailable.
 */
export async function computeContentKey(arrayBuffer) {
  if (!globalThis.crypto?.subtle) return null;
  try {
    const digest = await crypto.subtle.digest("SHA-256", arrayBuffer);
    return toHex(digest).slice(0, KEY_HEX_CHARS);
  } catch {
    return null;
  }
}

// The legacy key, kept as one named function rather than three scattered
// copies of `split(".")[0]`. Uses the LAST dot, not the first, so
// "Building.v2.ifc" becomes "Building.v2" instead of colliding with a
// sibling "Building.ifc" - the old expression's fourth defect.
export function legacyNameKey(fileName) {
  if (!fileName) return "model";
  const dot = fileName.lastIndexOf(".");
  return (dot > 0 ? fileName.slice(0, dot) : fileName) || "model";
}

// IFC files are ASCII/ISO-10303-21 text; the HEADER section is always at the
// very top, so only the first slice needs decoding to read it. 64KB is
// generously past any real header.
const HEADER_SCAN_BYTES = 65536;

// Both are single-quoted STEP strings. Deliberately tolerant: a malformed or
// unusual header must never fail a model load, it just yields less lineage.
const FILE_NAME_RE = /FILE_NAME\s*\(\s*'((?:[^']|'')*)'/i;
const PROJECT_GUID_RE = /IFCPROJECT\s*\(\s*'((?:[^']|'')*)'/i;

function unescapeStepString(value) {
  return value === undefined ? null : value.replace(/''/g, "'");
}

/**
 * Weaker, re-export-stable identifiers read straight out of the file's own
 * header: the IFC `FILE_NAME` entry (what the authoring tool called this
 * model, independent of what the file is named on disk) and the
 * `IfcProject` GlobalId (stable across re-exports of the same project from
 * the same authoring model).
 *
 * Recorded for provenance only - nothing joins on these today. See this
 * file's header for why they're kept beside the exact key rather than used
 * as it.
 */
export function readIfcLineage(bytes, fileName) {
  const lineage = { fileName: fileName ?? null, ifcFileName: null, projectGuid: null };
  try {
    const head = new TextDecoder("utf-8", { fatal: false }).decode(
      bytes.subarray(0, Math.min(HEADER_SCAN_BYTES, bytes.length)),
    );
    lineage.ifcFileName = unescapeStepString(head.match(FILE_NAME_RE)?.[1]);
    lineage.projectGuid = unescapeStepString(head.match(PROJECT_GUID_RE)?.[1]);
  } catch {
    // Leave whatever was already resolved; lineage is never load-critical.
  }
  return lineage;
}

/**
 * The one call every intake path uses. Returns the content key when it can
 * be computed, and the legacy filename-stem key when it can't - `source`
 * says which, so callers can warn once instead of silently behaving
 * differently in two deployments.
 *
 * @param {ArrayBuffer} arrayBuffer - not yet transferred/detached.
 * @param {Uint8Array} bytes - a view over it, for the header scan.
 * @param {string} fileName
 */
export async function resolveFileIdentity(arrayBuffer, bytes, fileName) {
  const contentKey = await computeContentKey(arrayBuffer);
  if (!contentKey) {
    console.warn(
      "⚠️ crypto.subtle unavailable (not a secure context) - falling back to the filename-based key. " +
        "Intent results and verdicts for this model will not be shared with other sessions. " +
        "Use the localhost URL Vite prints, or serve over https, to get stable content-addressed keys.",
    );
  }
  return {
    key: contentKey ?? legacyNameKey(fileName),
    keySource: contentKey ? "content" : "filename",
    fileName,
    lineage: readIfcLineage(bytes, fileName),
  };
}
