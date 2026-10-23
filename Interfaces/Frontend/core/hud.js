// ======== Dev performance HUD ========
// The acceptance instrument for rendering work:
// frame time from the real GPU the user is looking at, plus the renderer's
// own counters. Headless CI renders through SwiftShader and its frame times
// are not evidence; this runs on the user's machine and is.
//
// Opt-in only: `?hud` on the page URL. Lazy-imported by
// ThatOpenCompanyLoader.js so it costs nothing otherwise. Read-only - it
// never touches a viewer, only reads `world.renderer.three.info` and the
// fragments registry of the first open viewer.

import { viewerData } from "./viewerRegistry.js";

const SAMPLE_WINDOW = 120; // frames kept for the rolling percentiles

export function startHud() {
  const el = document.createElement("pre");
  el.id = "perf-hud";
  el.setAttribute("aria-live", "off");
  document.body.appendChild(el);

  const frames = [];
  let last = performance.now();
  let rafId = 0;
  const tick = (t) => {
    frames.push(t - last);
    if (frames.length > SAMPLE_WINDOW) frames.shift();
    last = t;
    rafId = requestAnimationFrame(tick);
  };
  rafId = requestAnimationFrame(tick);

  const pct = (arr, p) => {
    if (!arr.length) return 0;
    const sorted = [...arr].sort((a, b) => a - b);
    return sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * p))];
  };
  const fmt = (n) => n.toLocaleString("en-US");

  const render = () => {
    const entry = viewerData[0];
    const info = entry?.world.renderer.three.info.render;
    let fragments = 0;
    let instances = 0;
    if (entry) {
      for (const group of entry.fragments.groups.values()) {
        for (const fragment of group.items) {
          fragments++;
          instances += fragment.mesh?.count ?? 0;
        }
      }
    }
    const heap = performance.memory
      ? `${Math.round(performance.memory.usedJSHeapSize / 1048576)} MB`
      : "n/a";
    el.textContent = [
      `frame  ${pct(frames, 0.5).toFixed(1).padStart(6)} ms p50   ${pct(frames, 0.95).toFixed(1).padStart(6)} ms p95`,
      `draw   ${fmt(info?.calls ?? 0).padStart(8)} calls   ${fmt(info?.triangles ?? 0).padStart(10)} tris`,
      `frags  ${fmt(fragments).padStart(8)}          ${fmt(instances).padStart(10)} inst`,
      `heap   ${heap.padStart(8)}   viewers ${viewerData.length}`,
    ].join("\n");
  };
  const timer = setInterval(render, 500);
  render();

  return () => {
    cancelAnimationFrame(rafId);
    clearInterval(timer);
    el.remove();
  };
}
