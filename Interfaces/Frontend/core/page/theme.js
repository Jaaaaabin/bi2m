// ======== Dark Mode (page chrome) ========
// Moved out of ThatOpenCompanyLoader.js 2026-09-21 (code motion only,
// behaviour unchanged). Respects the OS preference by
// default (handled purely in CSS via prefers-color-scheme - see style.css).
// Manually toggling sets an explicit data-theme attribute that overrides the
// OS preference either direction, and is remembered across reloads
// (settings.js, key "theme").

import * as THREE from "three";

import { viewerData } from "../viewerRegistry.js";
import { setIcon } from "../icons.js";
import { getSetting, setSetting } from "../settings.js";

// Reads --color-bg (the page's own background - see style.css) live via
// computed style, same technique getIntentColorPalette() already uses for
// --intent-color-N - one source of truth for the color, no hex duplicated
// into JS, and a theme switch (OS-driven or manual) is picked up automatically.
export function getGlobalBackgroundColor() {
  return getComputedStyle(document.documentElement).getPropertyValue("--color-bg").trim();
}

export function applyTheme(theme) {
  const icon = document.getElementById("theme-toggle-icon");
  if (theme) {
    document.documentElement.setAttribute("data-theme", theme);
    setIcon(icon, theme === "dark" ? "light_mode" : "dark_mode");
  } else {
    document.documentElement.removeAttribute("data-theme");
    const prefersDark = window.matchMedia?.("(prefers-color-scheme: dark)").matches;
    setIcon(icon, prefersDark ? "light_mode" : "dark_mode");
  }

  // Keeps every already-open viewer's 3D background matching the page
  // background rather than @thatopen/components' own fixed SimpleScene
  // default (#202932) - a freshly-created viewer picks this up too, see
  // setupViewer's own call to getGlobalBackgroundColor right after
  // world.scene.setup().
  const bgColor = getGlobalBackgroundColor();
  for (const { world } of viewerData) {
    world.scene.config.backgroundColor = new THREE.Color(bgColor);
  }
}

export function initTheme() {
  applyTheme(getSetting("theme"));
  document.getElementById("theme-toggle-btn").addEventListener("click", () => {
    const current =
      document.documentElement.getAttribute("data-theme") ||
      (window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    const next = current === "dark" ? "light" : "dark";
    setSetting("theme", next);
    applyTheme(next);
  });
}
