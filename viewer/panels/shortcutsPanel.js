// ======== Keyboard cheat sheet (floating, per viewer) ========
// Requested 2026-09-21: the review shortcuts list lives in its own floating
// panel over the 3D viewport, opened from a corner button next to the
// intent-panel toggle (bottom-left), not inline in the intent panel. Same
// floating mechanics as .viewer-camera-panel (a class on the tile toggles
// it), so opening it never resizes or re-frames the render. The `?` key in
// the intent panel toggles the same panel.
//
// The shortcuts themselves are handled in panels/intentPanel.js; this file
// only shows the list. Keep the two in step.

import { iconSvg } from "../icons.js";

export const SHORTCUTS_OPEN_CLASS = "shortcuts-open";

export const SHORTCUTS = [
  [["↓"], ["↑"], "next / previous intent"],
  [["Enter"], ["Space"], "Refer (zoom to it)"],
  [["a"], ["r"], ["u"], "Accept · Reject · Reset"],
  [["]"], ["["], "next / previous category"],
  [["e"], "expand / collapse evidence"],
  [["/"], "filter"],
  [["Esc"], "Clear selection"],
  [["?"], "this list"],
];

export function toggleShortcutsPanel(container, force) {
  const open = container.classList.toggle(SHORTCUTS_OPEN_CLASS, force);
  container
    .querySelector(".viewer-shortcuts-toggle-btn")
    ?.setAttribute("aria-expanded", String(open));
  return open;
}

export function createShortcutsPanel({ container }) {
  const btn = document.createElement("button");
  btn.className = "viewer-shortcuts-toggle-btn";
  btn.title = "Shortcuts";
  btn.setAttribute("aria-label", "Shortcuts");
  btn.setAttribute("aria-expanded", "false");
  btn.innerHTML = iconSvg("keyboard");
  btn.addEventListener("click", () => toggleShortcutsPanel(container));
  container.appendChild(btn); // tile-anchored (2026-09-23), like the intent toggle beside it

  const panel = document.createElement("div");
  panel.className = "viewer-shortcuts-panel";
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", "Keyboard review shortcuts");
  const rows = SHORTCUTS.map((entry) => {
    const keys = entry
      .slice(0, -1)
      .map((k) => `<kbd>${k[0]}</kbd>`)
      .join(" ");
    return `<dt>${keys}</dt><dd>${entry[entry.length - 1]}</dd>`;
  }).join("");
  panel.innerHTML = `
    <div class="viewer-shortcuts-head">
      <span class="intent-shortcuts-title">Keyboard review</span>
      <button type="button" class="viewer-shortcuts-close" title="Close" aria-label="Close">×</button>
    </div>
    <dl class="intent-shortcuts-list">${rows}</dl>
    <div class="viewer-shortcuts-hint">Click an intent row first; keys act on the current row.</div>
  `;
  panel
    .querySelector(".viewer-shortcuts-close")
    .addEventListener("click", () => toggleShortcutsPanel(container, false));
  container.appendChild(panel);
  return { button: btn, panel };
}
