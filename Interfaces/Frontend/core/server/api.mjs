// The viewer's server-side API (upload, recognition, tiling, example and
// library models) and the opt-in cross-origin-isolation headers. Moved out of
// vite.config.js on 2026-10-23 unchanged, so that one implementation serves
// both `npm run dev` (vite.config.js) and the production server
// (server/serve.mjs, `npm start`, the Docker image).
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, readdirSync, statSync, createReadStream, readFileSync } from "node:fs";
import { writeFile, rename, mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

// This file lives in server/, one level below the viewer root.
const CORE_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const REPO_ROOT = path.resolve(CORE_DIR, "../../..");
const TILES_DIR = path.join(CORE_DIR, "public", "tiles");
const DATA_DIR = path.join(REPO_ROOT, "data");
const UPLOADS_DIR = path.join(DATA_DIR, "uploads");

// Machine-specific paths (the model library's corpus) live in the repository's
// gitignored .env, which the Python scripts read too (src/local_env.py; the
// variables are listed in .env.example). Variables already set in the
// environment win: Node's loader does not override them.
const ENV_FILE = path.join(REPO_ROOT, ".env");
if (existsSync(ENV_FILE)) process.loadEnvFile(ENV_FILE);

// data/uploads/<fileKey>/<fileKey>.ifc for a given fileKey - the one place
// both routes below need to agree on this layout, so it's centralized here
// instead of duplicated in each handler.
function uploadIfcPath(fileKey) {
  return path.join(UPLOADS_DIR, fileKey, `${fileKey}.ifc`);
}

// Must stay identical to Interfaces/Frontend/core/fileIdentity.js's
// computeContentKey() and src/file_identity.py's compute_content_key():
// SHA-256 over the raw bytes, first 16 lowercase hex chars. The browser
// computes this key for the same file independently, and the upload route
// below refuses to store anything whose server-side hash disagrees with the
// key the client claimed.
const KEY_HEX_CHARS = 16;

function contentKeyOf(buffer) {
  return createHash("sha256").update(buffer).digest("hex").slice(0, KEY_HEX_CHARS);
}

// Shared by both routes below - a plain safe-token check (letters/digits/
// underscore/dot/hyphen only), not a semantic allowlist. It exists so junk
// can't even reach a subprocess argv or a filesystem path; the actual
// semantic validation (does this category exist, does this file exist) is
// left to Python, which already does it (resolve_categories/resolve_files in
// scripts/recognize_intents.py).
const TOKEN_RE = /^[A-Za-z0-9_.-]+$/;

// The upload route holds a whole model in memory before hashing it, so it
// refuses bodies above this size (413). 500 MB by default, above the largest
// real model seen so far (288 MB); BI2M_MAX_UPLOAD_MB raises or lowers it.
const DEFAULT_MAX_UPLOAD_MB = 500;
const maxUploadMb = Number(process.env.BI2M_MAX_UPLOAD_MB);
const MAX_UPLOAD_MB = maxUploadMb > 0 ? maxUploadMb : DEFAULT_MAX_UPLOAD_MB;
const MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024;

function uploadTooLarge(res, bytes) {
  // The body may not have been read in full, so the socket is not reused.
  res.setHeader("Connection", "close");
  sendJson(res, 413, {
    ok: false,
    error: `File too large (${(bytes / 1024 / 1024).toFixed(0)} MB; the limit is ${MAX_UPLOAD_MB} MB, set by BI2M_MAX_UPLOAD_MB).`,
  });
}

// The example-models route's allowlist: only generically named test_*.ifc
// and example_*.ifc copies, whose names carry no project reference number -
// never every data/*.ifc file, which can be a real, confidential project
// export. (No model is in git at all since 2026-09-20; this boundary is about
// what the dev server will hand to a browser, not about what is committed.)
// `example_` was added 2026-09-24, when the owner reduced the fixtures to a
// single `example_autcon.ifc`. It widens the allowlist by one generic prefix
// and not by one inch of the confidentiality rule: a file still has to be
// named after nothing, and a project export called `4711_Nordbau.ifc` is as
// unreachable as it was before.
const EXAMPLE_RE = /^(?:test|example)_[A-Za-z0-9_.-]*\.ifc$/i;

function sendJson(res, status, body) {
  res.statusCode = status;
  res.setHeader("Content-Type", "application/json");
  res.end(JSON.stringify(body));
}

// API backing the intent panel's "Run" button - lets it
// actually execute scripts/recognize_intents.py instead of only copying the
// CLI command (the original v1 "no live backend" call - superseded
// now that on-demand local recomputation is worth the convenience; the
// deployable artifact is still the batch-exported JSON, this is a local dev
// convenience layered on top). Registered twice from registerApiRoutes() below:
// by vite.config.js under `vite dev`, and by server/serve.mjs in front of a
// production build (`npm start`, the Docker image). `vite preview` has none.
//
// Two routes:
// - POST /api/upload-ifc?fileKey=X - writes the raw request body to
//   data/uploads/<contentKey>/<contentKey>.ifc, where contentKey is a
//   SHA-256 of the bytes that actually arrived (NOT the X query param, which
//   is only the client's claimed key and is echoed back for cross-checking).
//   Needed because the browser and this dev server can be different machines
//   (e.g. reached over an SSH port-forward) - the server can't assume it
//   already has whatever file the browser's picker showed, so "Run" ships
//   those exact bytes here first.
//
//   Naming the folder by content rather than by "<name>-<timestamp>" is what
//   makes this idempotent AND collision-free at once: two different real
//   projects both named "AR.ifc" get different folders (different bytes), and
//   the SAME file uploaded twice reuses one folder instead of writing another
//   full copy - the previous scheme accumulated 317MB of ~20 folders holding
//   7 distinct files, and stranded each run's results under a throwaway key.
//   See docs/architecture.md "One key for everything". data/uploads/ is
//   gitignored (see .gitignore).
// - POST /api/recognize-intents - spawns the CLI command server-side and
//   streams back its outcome (see below). Resolves fileKey against
//   data/uploads/<fileKey>/<fileKey>.ifc first (an upload from the route
//   above) and falls back to a bare data/<fileKey>.ifc (the existing
//   dev-fixture convention, e.g. test_1/test_2) when no such upload exists.
// - GET /api/example-models[?fileKey=X] - lets the viewer load one of this
//   *server's* data/test_*.ifc fixtures directly, for exactly the same
//   reason /api/upload-ifc exists in reverse: over an SSH port-forward, the
//   browser's own file picker only sees the client machine's files, not
//   this server's. Without a fileKey, lists {fileKey, fileName, sizeBytes}
//   for every data/test_*.ifc file; with one, streams that file's raw
//   bytes back. Deliberately scoped to the test_*.ifc naming convention
//   ONLY (re-checked server-side on every request, not just in the list) -
//   the same boundary .gitignore already draws between small, genuinely
//   shareable fixtures and real/confidential project files that happen to
//   also live under data/ (e.g. an uploaded or manually-placed project
//   file) - so this route can never be used to read out anything else.
//
// Both are safe by construction, not by validation: spawn() passes argv
// directly (shell: false, the default), so there is no shell to inject into -
// a hostile fileKey/category can only reach Python's own argparse as a
// literal string and fail there. TOKEN_RE just keeps obviously-malformed
// input from bothering the subprocess/filesystem at all.
// ======== Cross-origin isolation - OPT-IN ========
// COOP + COEP make `crossOriginIsolated` true, the one condition web-ifc
// checks before loading its multi-threaded build. Measured 2026-09-21 and
// REJECTED as a default: under `vite dev` the -mt build's pthread workers
// all die ("worker sent an error!" x N, model never loads), because
// Emscripten's worker importScripts() the main web-ifc script, which Vite
// serves as an ES module. Single-thread web-ifc from /wasm/ loads test_1 in
// ~4.8 s. Kept as an opt-in for a later spike against a production build:
// BI2M_COI=1 on the server, or `?coi=1` on the page URL; `?coi=0` always
// wins. Everything the page loads is same-origin since 1.1/1.2, so the
// headers themselves block nothing when on.
const coiEnabledByEnv = process.env.BI2M_COI === "1";

export function crossOriginIsolation(req, res, next) {
  const url = new URL(req.url, "http://internal");
  const wantsDocument = !url.pathname.includes(".") || url.pathname.endsWith(".html");
  const flag = url.searchParams.get("coi");
  const on = flag === "1" || (coiEnabledByEnv && flag !== "0");
  if (wantsDocument && on) {
    res.setHeader("Cross-Origin-Opener-Policy", "same-origin");
    res.setHeader("Cross-Origin-Embedder-Policy", "require-corp");
  }
  next();
}

// ======== Auto-tile on upload ========
// The streamed path opens test_7 in 0.36s where the parsed path needs
// seconds and blocks the main thread, but it only applies to models someone
// ran scripts/tileIfc.mjs on by hand. Now every upload that lands (or is
// found already present) without a tile set gets one built in the
// background, so the SECOND open of any model streams. Status is readable
// through GET /api/tile-status?fileKey=X for the Compute flyout.
const tileJobs = new Map(); // contentKey -> "building" | "failed"

function tileSetReady(contentKey) {
  return existsSync(path.join(TILES_DIR, contentKey, "tileset.json"));
}

function tileInBackground(contentKey, ifcPath) {
  if (tileSetReady(contentKey) || tileJobs.get(contentKey) === "building") return;
  tileJobs.set(contentKey, "building");
  const child = spawn(process.execPath, [path.join(CORE_DIR, "scripts", "tileIfc.mjs"), ifcPath], {
    cwd: CORE_DIR,
    stdio: ["ignore", "pipe", "pipe"],
  });
  let stderr = "";
  child.stderr.on("data", (chunk) => {
    stderr += chunk;
  });
  child.on("error", (err) => {
    tileJobs.set(contentKey, "failed");
    console.warn(`[tile] could not start tileIfc.mjs for ${contentKey}: ${err.message}`);
  });
  child.on("close", (code) => {
    if (code === 0 && tileSetReady(contentKey)) {
      tileJobs.delete(contentKey);
      console.log(`[tile] ${contentKey}: tile set ready - next open streams.`);
    } else {
      tileJobs.set(contentKey, "failed");
      console.warn(
        `[tile] ${contentKey}: tiling failed (exit ${code}). ${stderr.trim().slice(-400)}`,
      );
    }
  });
}

function tileStatus(contentKey) {
  if (tileSetReady(contentKey)) return "ready";
  return tileJobs.get(contentKey) ?? "none";
}

// ======== Model library (2026-09-23) ========
// The corpus the sidebar's lightning-bolt button lists (page/libraryModels.js).
// Where /api/example-models is allowlisted to data/test_*.ifc, this route is
// allowlisted to the CONTENT KEYS in the corpus vis index
// (scripts/build_vis_index.py): a client names a key, never a path. The index
// is re-read on every request so a renumbering pass needs no restart, and the
// served file is re-hashed so a stale index can never hand out the wrong model
// under a familiar number (409 instead). Read-only: no upload, no tiling, no
// recognition - "Run from the library" is a separate, later step.
// Both folders come from BI2M_IFC_CORPUS and BI2M_VIS_DIR (.env). Without
// them the library is simply not configured: the route answers 404 with a
// hint, which the flyout shows.
const LIBRARY_CORPUS_DIR = process.env.BI2M_IFC_CORPUS || null;
const LIBRARY_VIS_DIR = process.env.BI2M_VIS_DIR || null;
const LIBRARY_INDEX_PATH = LIBRARY_VIS_DIR && path.join(LIBRARY_VIS_DIR, "index.json");
const CONTENT_KEY_RE = /^[0-9a-f]{16}$/;
// Optional, beside the index: per-model annotations (assigned unit, residual
// verdict after the unit fix) written by scripts/library_annotations.py. The
// flyout clusters the list from them; without the file it stays flat.
const LIBRARY_ANNOTATIONS_PATH = LIBRARY_VIS_DIR && path.join(LIBRARY_VIS_DIR, "annotations.json");

function readLibraryAnnotations() {
  if (!LIBRARY_ANNOTATIONS_PATH || !existsSync(LIBRARY_ANNOTATIONS_PATH)) return null;
  try {
    const raw = JSON.parse(readFileSync(LIBRARY_ANNOTATIONS_PATH, "utf8"));
    if (!raw || typeof raw.models !== "object") return null;
    return raw;
  } catch {
    return null;
  }
}

function readLibraryIndex() {
  if (!LIBRARY_CORPUS_DIR || !LIBRARY_INDEX_PATH || !existsSync(LIBRARY_INDEX_PATH)) return null;
  const raw = JSON.parse(readFileSync(LIBRARY_INDEX_PATH, "utf8"));
  // build_vis_index.py writes {corpus_dir, built_at, count, absent, models: {key: {name, size_bytes}}};
  // an older index was the bare mapping. The corpus location is NOT taken from
  // the index (data, not authority) - it comes from the environment or the default.
  const mapping = raw && typeof raw.models === "object" && raw.models ? raw.models : raw;
  const entries = [];
  for (const [key, value] of Object.entries(mapping)) {
    if (!CONTENT_KEY_RE.test(key) || !value || typeof value.name !== "string" || value.absent)
      continue;
    // A name is a bare file name, never a path - the index is data, not authority.
    if (path.basename(value.name) !== value.name || !value.name.toLowerCase().endsWith(".ifc"))
      continue;
    entries.push({ fileKey: key, fileName: value.name, sizeBytes: Number(value.size_bytes) || 0 });
  }
  entries.sort((a, b) => a.fileName.localeCompare(b.fileName, undefined, { numeric: true }));
  return entries;
}

// Every route as (mount path, connect-style handler). The caller supplies
// `use`: Vite's server.middlewares.use, or serve.mjs's own router.
export function registerApiRoutes(use) {
  use("/api/upload-ifc", (req, res) => {
    if (req.method !== "POST") {
      sendJson(res, 405, { ok: false, error: "Method Not Allowed" });
      return;
    }

    // The client's CLAIMED content key - echoed back for a cross-check
    // only; the authoritative key is hashed from the bytes below.
    const fileKey = new URL(req.url, "http://internal").searchParams.get("fileKey") || "";
    if (!TOKEN_RE.test(fileKey)) {
      sendJson(res, 400, { ok: false, error: "Invalid fileKey." });
      return;
    }

    // fileKey is already a validated safe token, so this is just a
    // human-traceable prefix - Date.now() is what actually guarantees no
    // two uploads (even of files named identically) ever share a folder.
    // Content-Length rejects an oversized upload before any of it is read;
    // the running count catches a body sent without one (or with a wrong one).
    const declaredBytes = Number(req.headers["content-length"]);
    if (declaredBytes > MAX_UPLOAD_BYTES) {
      uploadTooLarge(res, declaredBytes);
      req.resume();
      return;
    }
    const chunks = [];
    let receivedBytes = 0;
    let tooLarge = false;
    req.on("data", (chunk) => {
      receivedBytes += chunk.length;
      if (tooLarge) return;
      if (receivedBytes > MAX_UPLOAD_BYTES) {
        tooLarge = true;
        chunks.length = 0;
        return;
      }
      chunks.push(chunk);
    });
    req.on("end", async () => {
      if (tooLarge) {
        uploadTooLarge(res, receivedBytes);
        return;
      }
      const buffer = Buffer.concat(chunks);
      if (!buffer.length) {
        sendJson(res, 400, { ok: false, error: "Empty upload body." });
        return;
      }

      // The folder is named by the file's own CONTENT, not by its name
      // plus a timestamp. That single change is what makes this route
      // idempotent: re-running recognition on an unchanged file finds the
      // bytes already here and writes nothing, where the old
      // "<fileKey>-<Date.now()>" scheme wrote a fresh full copy every
      // time (measured: 317MB across ~20 folders holding 7 distinct
      // files, and intent results stranded under a key no later session
      // ever looked up). See docs/architecture.md "One key for everything".
      //
      // Hashed here independently rather than trusting the client's
      // `fileKey` query param: the key decides where bytes land and which
      // results they overwrite, so it must be derived from what actually
      // arrived. A mismatch is reported back and the client refuses to
      // proceed.
      const contentKey = contentKeyOf(buffer);
      const uploadDir = path.join(UPLOADS_DIR, contentKey);
      const destPath = uploadIfcPath(contentKey);
      const claimedKeyMatches = fileKey === contentKey;

      if (existsSync(destPath) && statSync(destPath).size === buffer.length) {
        tileInBackground(contentKey, destPath);
        sendJson(res, 200, {
          ok: true,
          fileKey: contentKey,
          claimedKeyMatches,
          deduplicated: true,
          bytesWritten: 0,
          tiles: tileStatus(contentKey),
        });
        return;
      }

      // Temp file + rename - same atomicity convention src/io_utils.py's
      // write_json already uses. An interrupted upload must never leave
      // a half-written .ifc file sitting at the path
      // scripts/recognize_intents.py is about to open. Temp file lives
      // in the same uploadDir so the rename stays on one filesystem
      // (required for rename() to be atomic).
      const tmpPath = path.join(uploadDir, `.${contentKey}.ifc.${process.pid}.tmp`);
      try {
        await mkdir(uploadDir, { recursive: true });
        await writeFile(tmpPath, buffer);
        await rename(tmpPath, destPath);
        tileInBackground(contentKey, destPath);
        sendJson(res, 200, {
          ok: true,
          fileKey: contentKey,
          claimedKeyMatches,
          deduplicated: false,
          bytesWritten: buffer.length,
          tiles: tileStatus(contentKey),
        });
      } catch (err) {
        sendJson(res, 500, { ok: false, error: err.message });
      }
    });
  });

  use("/api/recognize-intents", (req, res) => {
    if (req.method !== "POST") {
      sendJson(res, 405, { ok: false, error: "Method Not Allowed" });
      return;
    }

    let body = "";
    req.on("data", (chunk) => {
      body += chunk;
    });
    req.on("end", () => {
      let payload;
      try {
        payload = JSON.parse(body || "{}");
      } catch {
        sendJson(res, 400, { ok: false, error: "Invalid JSON body." });
        return;
      }

      const fileKey = typeof payload.fileKey === "string" ? payload.fileKey : "";
      const categories = Array.isArray(payload.categories) ? payload.categories : [];
      if (
        !TOKEN_RE.test(fileKey) ||
        !categories.length ||
        !categories.every((c) => TOKEN_RE.test(c))
      ) {
        sendJson(res, 400, { ok: false, error: "Invalid fileKey or categories." });
        return;
      }

      // An upload (see /api/upload-ifc above) lives nested under
      // data/uploads/<contentKey>/, which Python's own bare-name
      // resolution (relative to data/*.ifc) can't see - pass its absolute
      // path explicitly in that case. Anything else (e.g. test_3/test_1)
      // falls back to the existing bare-fileKey behavior, resolved
      // against data/*.ifc by scripts/recognize_intents.py itself, which
      // derives the same content key from whatever file it opens.
      const uploadPath = uploadIfcPath(fileKey);
      const filesArg = existsSync(uploadPath) ? uploadPath : fileKey;

      const scriptArgs = [
        "scripts/recognize_intents.py",
        "--files",
        filesArg,
        "--categories",
        categories.join(","),
      ];
      // BI2M_PYTHON names a fixed interpreter (the Docker image sets it to
      // its venv); unset, this is the dev setup's `uv run python` as before.
      const child = process.env.BI2M_PYTHON
        ? spawn(process.env.BI2M_PYTHON, scriptArgs, { cwd: REPO_ROOT })
        : spawn("uv", ["run", "python", ...scriptArgs], { cwd: REPO_ROOT });

      let stdout = "";
      let stderr = "";
      let responded = false;
      const respond = (status, resBody) => {
        if (responded) return;
        responded = true;
        sendJson(res, status, resBody);
      };

      child.stdout.on("data", (chunk) => {
        stdout += chunk;
      });
      child.stderr.on("data", (chunk) => {
        stderr += chunk;
      });
      child.on("error", (err) =>
        respond(500, { ok: false, error: `Failed to start: ${err.message}` }),
      );
      child.on("close", (code) => respond(200, { ok: code === 0, code, stdout, stderr }));
    });
  });

  // GET /api/tile-status?fileKey=X -> {ok, status: "ready"|"building"|"failed"|"none"}
  use("/api/tile-status", (req, res) => {
    if (req.method !== "GET") {
      sendJson(res, 405, { ok: false, error: "Method Not Allowed" });
      return;
    }
    const fileKey = new URL(req.url, "http://internal").searchParams.get("fileKey") || "";
    if (!TOKEN_RE.test(fileKey)) {
      sendJson(res, 400, { ok: false, error: "Invalid fileKey." });
      return;
    }
    sendJson(res, 200, { ok: true, fileKey, status: tileStatus(fileKey) });
  });

  use("/api/example-models", (req, res) => {
    if (req.method !== "GET") {
      sendJson(res, 405, { ok: false, error: "Method Not Allowed" });
      return;
    }

    const fileKey = new URL(req.url, "http://internal").searchParams.get("fileKey");

    if (!fileKey) {
      // List mode - EXAMPLE_RE (not TOKEN_RE) is what actually keeps
      // this to the generically named test_*.ifc copies (see the
      // constant's comment above).
      const files = readdirSync(DATA_DIR)
        .filter((name) => EXAMPLE_RE.test(name))
        .map((name) => {
          const { size } = statSync(path.join(DATA_DIR, name));
          return { fileKey: name.slice(0, -".ifc".length), fileName: name, sizeBytes: size };
        })
        .sort((a, b) => a.sizeBytes - b.sizeBytes);
      sendJson(res, 200, { ok: true, files });
      return;
    }

    // Re-validated here independently of the list above - this route
    // must never serve an arbitrary data/<fileKey>.ifc (which could be a
    // real, confidential project file) just because a client asked for
    // it by name; only names matching the example-fixture convention
    // are ever readable through this endpoint.
    if (!EXAMPLE_RE.test(`${fileKey}.ifc`)) {
      sendJson(res, 403, { ok: false, error: "Not an example model." });
      return;
    }

    const filePath = path.join(DATA_DIR, `${fileKey}.ifc`);
    if (!existsSync(filePath)) {
      sendJson(res, 404, { ok: false, error: "Example model not found." });
      return;
    }

    res.statusCode = 200;
    res.setHeader("Content-Type", "application/octet-stream");
    createReadStream(filePath).pipe(res);
  });

  use("/api/library-models", (req, res) => {
    if (req.method !== "GET") {
      sendJson(res, 405, { ok: false, error: "Method Not Allowed" });
      return;
    }
    const fileKey = new URL(req.url, "http://internal").searchParams.get("fileKey");
    let entries;
    try {
      entries = readLibraryIndex();
    } catch (err) {
      sendJson(res, 500, { ok: false, error: `Library index unreadable: ${err.message}` });
      return;
    }
    if (!entries) {
      sendJson(res, 404, {
        ok: false,
        error:
          LIBRARY_CORPUS_DIR && LIBRARY_INDEX_PATH
            ? `No library index at ${LIBRARY_INDEX_PATH} - build it with scripts/build_vis_index.py.`
            : "No model library configured: set BI2M_IFC_CORPUS and BI2M_VIS_DIR in .env (see .env.example).",
      });
      return;
    }
    if (!fileKey) {
      const annotations = readLibraryAnnotations();
      const files = annotations
        ? entries.map((e) => {
            const a = annotations.models[e.fileKey];
            return a ? { ...e, annotation: a } : e;
          })
        : entries;
      const summary = annotations
        ? {
            built_at: annotations.built_at,
            units: annotations.units,
            residual: annotations.residual,
            residual_by_verdict: annotations.residual_by_verdict,
            swept: annotations.swept,
          }
        : null;
      sendJson(res, 200, {
        ok: true,
        corpus: path.basename(LIBRARY_CORPUS_DIR),
        files,
        summary,
      });
      return;
    }
    if (!CONTENT_KEY_RE.test(fileKey)) {
      sendJson(res, 400, { ok: false, error: "fileKey must be a 16-hex content key." });
      return;
    }
    const entry = entries.find((e) => e.fileKey === fileKey);
    if (!entry) {
      sendJson(res, 404, { ok: false, error: "Not in the library index." });
      return;
    }
    const filePath = path.join(LIBRARY_CORPUS_DIR, entry.fileName);
    if (!existsSync(filePath)) {
      sendJson(res, 404, {
        ok: false,
        error: `${entry.fileName} is listed but not on disk - rebuild the index.`,
      });
      return;
    }
    let buffer;
    try {
      buffer = readFileSync(filePath);
    } catch (err) {
      sendJson(res, 500, {
        ok: false,
        error: `Could not read ${entry.fileName}: ${err.message}`,
      });
      return;
    }
    const actual = contentKeyOf(buffer);
    if (actual !== fileKey) {
      sendJson(res, 409, {
        ok: false,
        error: `Library index is stale: ${entry.fileName} now has key ${actual}, not ${fileKey}. Rebuild it with scripts/build_vis_index.py.`,
      });
      return;
    }
    res.statusCode = 200;
    res.setHeader("Content-Type", "application/octet-stream");
    res.setHeader("Content-Length", buffer.length);
    res.setHeader("X-Content-Key", actual);
    res.setHeader("X-File-Name", entry.fileName);
    res.end(buffer);
  });
}
