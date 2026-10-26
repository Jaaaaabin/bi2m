// Bundle budget (CONTRIBUTING.md "Bundle budget"). Run after `vite build`:
//   node scripts/checkBundleSize.mjs
// Compares each dist/assets chunk's gzip size against a per-chunk-family
// budget and fails (exit 1) when one is more than 10% over. Budgets are the
// 2026-09-21 build's numbers rounded up; raise them deliberately, in this
// file, when a dependency genuinely grows - never silently.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { gzipSync } from "node:zlib";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ASSETS = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../dist/assets");
const TOLERANCE = 1.1;
// family -> gzip budget in KB. A chunk belongs to the first family whose
// prefix matches its file name.
const BUDGETS_KB = {
  // App code, all first-party (no node_modules inside, checked by sourcemap).
  // 2026-10-23: 30 -> 52 after measuring 50 KB at ~14k source lines (30 KB was
  // ~8k lines on 2026-09-21), ~50 modules, none above 12%. 52, not more: the
  // 10% tolerance then fails above ~57 KB, so one stray heavy import still
  // trips it. When it does, lazy-load before raising again: views/lines*.js +
  // linePicker.js (~11%), page/libraryModels.js (5%), views/bcfExport.js
  // (1.5%). Any NEW lazy chunk needs its own entry here - a chunk with no
  // budget is never checked.
  "index-": 52,
  "InspectorPanel-": 65, // React island (lazy); rolldown may put react-dom here or in react-
  "react-": 65,
  "three-": 130,
  "thatopen-": 500,
  "web-ifc-": 400, // JS only; the viewer serves web-ifc's .wasm from public/wasm/ (vite.config.js)
  "geometryLabels.worker-": 5, // inspector/geometryLabels.js in its Worker
  "hud-": 5,
  "rolldown-runtime-": 2,
};
const CSS_BUDGET_KB = 30;
// The viewer serves web-ifc's .wasm itself, from public/wasm/ (vite.config.js),
// so a .wasm in dist/assets is always a second, bundled copy that some import
// pulled in (a `?url` import, a library resolving its own) - the removed 3D
// preview shipped one, 1.2 MB, until 2026-10-26. Any such file fails the check.
const WASM_HINT = "a bundled .wasm duplicates public/wasm/ - find the import that emits it";

let failed = false;
const rows = [];
for (const name of readdirSync(ASSETS).sort()) {
  const file = path.join(ASSETS, name);
  if (!statSync(file).isFile() || /\.(gz|br|map)$/.test(name)) continue;
  if (name.endsWith(".wasm")) {
    failed = true;
    rows.push([name, `${(statSync(file).size / 1024).toFixed(0)} KB raw`, "none", WASM_HINT]);
    continue;
  }
  if (!/\.(js|css)$/.test(name)) continue;
  const gz = gzipSync(readFileSync(file), { level: 9 }).length / 1024;
  // The families above are JS. Matching them against index-*.css too made the
  // stylesheet inherit the app-code budget (30, and 52 after 2026-10-23); it
  // keeps the 30 it had in effect, now stated on its own.
  const family = name.endsWith(".js")
    ? Object.keys(BUDGETS_KB).find((prefix) => name.startsWith(prefix))
    : undefined;
  const budget = family ? BUDGETS_KB[family] : name.endsWith(".css") ? CSS_BUDGET_KB : null;
  const over = budget !== null && gz > budget * TOLERANCE;
  failed ||= over;
  rows.push([
    name,
    `${gz.toFixed(0)} KB gz`,
    budget === null ? "-" : `${budget} KB`,
    over ? "OVER" : budget === null ? "unbudgeted" : "ok",
  ]);
}
const w = rows.reduce((m, r) => Math.max(m, r[0].length), 0);
for (const [n, size, budget, status] of rows)
  console.log(`${n.padEnd(w)}  ${size.padStart(12)}  budget ${budget.padStart(8)}  ${status}`);
if (failed) {
  console.error("\nBundle budget exceeded.");
  process.exit(1);
}
console.log("\nAll chunks within budget.");
