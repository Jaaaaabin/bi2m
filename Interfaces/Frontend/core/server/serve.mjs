// Production server: the built viewer (dist/) plus the API in server/api.mjs,
// in one Node process with no dependencies beyond Node itself. Run
// `npm run build` once, then `npm start` - or use the Docker image, which
// does both. `npm run dev` does not use this file.
//
// Static files resolve public/ first, then dist/. Recognition and tiling
// write into public/res/intents/ and public/tiles/ while the server runs;
// dist/ only holds the copy of public/ that `vite build` made, so a result
// computed after the build would otherwise never be served.
import http from "node:http";
import { createReadStream, existsSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { crossOriginIsolation, registerApiRoutes } from "./api.mjs";

const CORE_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const PUBLIC_DIR = path.join(CORE_DIR, "public");
const DIST_DIR = path.join(CORE_DIR, "dist");
const PORT = Number(process.env.PORT) || 3000;
// Loopback unless told otherwise: the API accepts uploads and starts Python
// without any login, so reaching it from other machines has to be a choice
// (HOST=0.0.0.0; the Docker image sets it inside its own network namespace,
// and docker-compose.yml publishes the port on 127.0.0.1 only).
const HOST = process.env.HOST || "127.0.0.1";

const CONTENT_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  // Must be exact: WebAssembly.instantiateStreaming refuses anything else.
  ".wasm": "application/wasm",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".ico": "image/x-icon",
  ".woff2": "font/woff2",
  ".txt": "text/plain; charset=utf-8",
};

const routes = new Map();
registerApiRoutes((mount, handler) => routes.set(mount, handler));

function sendText(res, status, text) {
  res.statusCode = status;
  res.setHeader("Content-Type", "text/plain; charset=utf-8");
  res.end(text);
}

// Connect's mount semantics, which the handlers were written against under
// Vite: a mount matches itself and anything below it, and the handler sees
// req.url with the mount stripped ("/api/tile-status?fileKey=x" -> "/?fileKey=x").
function dispatchApi(req, res, pathname) {
  for (const [mount, handler] of routes) {
    if (pathname !== mount && !pathname.startsWith(`${mount}/`)) continue;
    const rest = req.url.slice(mount.length);
    req.url = rest.startsWith("/") ? rest : `/${rest}`;
    try {
      handler(req, res);
    } catch (err) {
      console.error(`[api] ${mount}:`, err);
      if (!res.headersSent) {
        res.statusCode = 500;
        res.setHeader("Content-Type", "application/json");
        res.end(JSON.stringify({ ok: false, error: err.message }));
      }
    }
    return true;
  }
  return false;
}

function findFile(pathname) {
  let rel;
  try {
    rel = decodeURIComponent(pathname);
  } catch {
    return null;
  }
  if (rel.includes("\0")) return null;
  for (const root of [PUBLIC_DIR, DIST_DIR]) {
    const file = path.join(root, rel);
    // path.join has already collapsed any "..": whatever lands outside the
    // root is refused here.
    if (!file.startsWith(root + path.sep)) continue;
    if (existsSync(file) && statSync(file).isFile()) return { file, root };
  }
  return null;
}

function sendFile(req, res, { file, root }, pathname) {
  let body = file;
  // vite.config.js's compression plugin writes .br and .gz siblings for the
  // built assets; public/ files are served as they are.
  if (root === DIST_DIR) {
    const accepts = String(req.headers["accept-encoding"] || "");
    const encodings = [
      ["br", ".br"],
      ["gzip", ".gz"],
    ];
    for (const [encoding, suffix] of encodings) {
      if (accepts.includes(encoding) && existsSync(file + suffix)) {
        body = file + suffix;
        res.setHeader("Content-Encoding", encoding);
        break;
      }
    }
    res.setHeader("Vary", "Accept-Encoding");
  }
  res.statusCode = 200;
  res.setHeader(
    "Content-Type",
    CONTENT_TYPES[path.extname(file).toLowerCase()] || "application/octet-stream",
  );
  res.setHeader("Content-Length", statSync(body).size);
  // Hashed build output never changes under the same name; everything else
  // (index.html, intent shards, tiles) can.
  res.setHeader(
    "Cache-Control",
    pathname.startsWith("/assets/") ? "public, max-age=31536000, immutable" : "no-cache",
  );
  if (req.method === "HEAD") {
    res.end();
    return;
  }
  createReadStream(body).pipe(res);
}

function serveStatic(req, res, pathname) {
  if (req.method !== "GET" && req.method !== "HEAD") {
    sendText(res, 405, "Method Not Allowed");
    return;
  }
  const found = findFile(pathname);
  if (found) {
    sendFile(req, res, found, pathname);
    return;
  }
  // The viewer is a single page: any extension-less path gets index.html.
  if (!path.extname(pathname) || pathname.endsWith(".html")) {
    sendFile(req, res, { file: path.join(DIST_DIR, "index.html"), root: DIST_DIR }, pathname);
    return;
  }
  sendText(res, 404, "Not Found");
}

if (!existsSync(path.join(DIST_DIR, "index.html"))) {
  console.error(`No build at ${DIST_DIR}. Run \`npm run build\` first.`);
  process.exit(1);
}

const server = http.createServer((req, res) => {
  crossOriginIsolation(req, res, () => {
    const { pathname } = new URL(req.url, "http://internal");
    if (dispatchApi(req, res, pathname)) return;
    // An unknown /api route must answer JSON 404, never the page: the
    // viewer reads a 404's content type to tell "missing" from "no server".
    if (pathname.startsWith("/api/")) {
      res.statusCode = 404;
      res.setHeader("Content-Type", "application/json");
      res.end(JSON.stringify({ ok: false, error: "Not Found" }));
      return;
    }
    serveStatic(req, res, pathname);
  });
});

server.listen(PORT, HOST, () => {
  console.log(`bi2m viewer on http://${HOST === "0.0.0.0" ? "localhost" : HOST}:${PORT}`);
});

// Node as PID 1 in a container ignores SIGTERM unless it is handled, and
// `docker stop` would then wait its full grace period and SIGKILL.
for (const signal of ["SIGTERM", "SIGINT"]) {
  process.on(signal, () => {
    server.close(() => process.exit(0));
    setTimeout(() => process.exit(0), 5000).unref();
  });
}
