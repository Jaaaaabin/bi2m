import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { existsSync, copyFileSync, mkdirSync } from "node:fs";
import { compression } from "vite-plugin-compression2";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { crossOriginIsolation, registerApiRoutes } from "./server/api.mjs";

const CORE_DIR = path.dirname(fileURLToPath(import.meta.url));

// ======== Self-hosted web-ifc engine ========
// Copies the three files web-ifc resolves as `<wasm.path> + <file>` into
// public/wasm/ on every dev-server start and every build, so IfcLoader never
// has to reach unpkg.com (its `autoSetWasm` default did, twice per fresh
// session - see ThatOpenCompanyLoader.js's loader.setup call). The -mt pair
// is what web-ifc picks by itself when `crossOriginIsolated` is true (1.3).
// public/wasm/ is gitignored: it is derived from node_modules, and the
// version stays whatever @thatopen/components 2.4.3 pins.
const WEB_IFC_FILES = ["web-ifc.wasm", "web-ifc-mt.wasm", "web-ifc-mt.worker.js"];

function webIfcWasmPlugin() {
  const copy = () => {
    const src = path.join(CORE_DIR, "node_modules", "web-ifc");
    const dest = path.join(CORE_DIR, "public", "wasm");
    mkdirSync(dest, { recursive: true });
    for (const name of WEB_IFC_FILES) {
      const from = path.join(src, name);
      if (existsSync(from)) copyFileSync(from, path.join(dest, name));
    }
  };
  // Copied right here, while this config file is being evaluated: Vite
  // indexes public/ once, before any plugin hook runs, and a file that
  // appears later is served as the SPA fallback (index.html) until the next
  // restart - observed 2026-09-21. buildStart keeps `vite build` covered too.
  copy();
  return { name: "web-ifc-wasm", buildStart: copy };
}

// ======== Cross-origin isolation - OPT-IN ========
// The middleware and its rationale live in server/api.mjs.
function crossOriginIsolationPlugin() {
  const apply = (server) => {
    server.middlewares.use(crossOriginIsolation);
  };
  return { name: "cross-origin-isolation", configureServer: apply, configurePreviewServer: apply };
}

// ======== Server API (server/api.mjs) ========
function apiPlugin() {
  return {
    name: "bi2m-api",
    configureServer(server) {
      registerApiRoutes((mount, handler) => server.middlewares.use(mount, handler));
    },
  };
}

// React is used for a small, additive UI island (the element inspector panel) -
// the rest of the app stays vanilla JS / @thatopen/ui web components. See
// inspector/InspectorPanel.jsx for the interop intent (CustomEvent bridge from the
// existing imperative code, no dependency the other way).
export default defineConfig({
  // The dev server must NOT watch the tile sets. `public/tiles/` is a
  // gitignored build artifact, and after 2026-09-24's corpus-wide conversion
  // it holds ~254,500 files across 388 model directories - four times this
  // machine's `fs.inotify.max_user_watches` (65,536). Vite's watcher walks
  // everything under the project root that is not ignored, so without this
  // the dev server dies on startup, or shortly after, with an inotify
  // ENOSPC. That is exactly how it died here: `npm run dev` was up and
  // healthy, `scripts/tile_corpus.py` wrote the library underneath it, and
  // the server was gone by the end of the run.
  // Nothing is lost by not watching them: a tile set is written once by
  // `scripts/tileIfc.mjs` and never edited, Vite still SERVES `public/`
  // statically (serving and watching are separate), and a newly tiled model
  // is picked up on the next page load. Raising the kernel limit would be
  // the other fix, but it is machine state this repo cannot carry.
  server: {
    watch: {
      ignored: ["**/public/tiles/**"],
    },
  },
  plugins: [
    react(),
    webIfcWasmPlugin(),
    crossOriginIsolationPlugin(),
    apiPlugin(),
    // Precompressed siblings (.gz + .br) next to every built asset, so any
    // static host that honours them sends ~1.4 MB instead of ~6.5 MB.
    // Build only; the dev server is unaffected.
    compression({
      algorithms: ["gzip", "brotliCompress"],
      include: /\.(js|mjs|css|html|svg|json|wasm)$/,
    }),
  ],
  build: {
    reportCompressedSize: true,
    // Vendor deps split into their own chunks, separate from app code
    // (ThatOpenCompanyLoader.js, inspector/InspectorPanel.jsx). Doesn't reduce
    // first-load bytes, but vendor code changes far less often than app
    // code - without this, every deploy invalidated the entire ~5.4MB
    // bundle for returning users even when only app code changed.
    // Vite 8 / rolldown (2026-09-21): `rollupOptions.output.manualChunks`
    // is gone - the object form fails ("manualChunks is not a function")
    // and the function form is only a partial shim that folded three and
    // web-ifc into the thatopen chunk. `codeSplitting.groups` is rolldown's
    // own mechanism (`advancedChunks` is its deprecated name).
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [
            { name: "three", test: /node_modules[\\/]three[\\/]/ },
            { name: "web-ifc", test: /node_modules[\\/]web-ifc[\\/]/ },
            { name: "thatopen", test: /node_modules[\\/]@thatopen[\\/]/ },
            { name: "react", test: /node_modules[\\/](react|react-dom|scheduler)[\\/]/ },
          ],
        },
      },
    },
  },
});
