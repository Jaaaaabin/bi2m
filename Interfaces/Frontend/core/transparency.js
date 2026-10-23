// ======== Global Transparency Slider ========
// Moved here VERBATIM from ThatOpenCompanyLoader.js.
// Nothing about what it does to materials, or to the slider's own readout,
// is changed - this is the same code in a module of its own so that
// highlighting.js can call setTransparencyValue() (referByGuids starts a
// refer at 90%, clearReferForViewer ends it at 0%) without importing the
// whole orchestrator.

import { viewerData } from "./viewerRegistry.js";
import { log } from "./debug.js";

// Live percentage readout + a filled track (via a --_fill custom property the
// CSS gradient reads - see .styled-range in style.css) instead of the old
// static "0% ... 100%" end labels that never reflected the actual value.
const transparencySlider = /** @type {HTMLInputElement} */ (
  document.getElementById("global-opacity-slider")
);
const transparencyValueLabel = document.getElementById("transparency-value");

function updateTransparencyUI(value) {
  transparencyValueLabel.textContent = `${value}%`;
  transparencySlider.style.setProperty("--_fill", `${value}%`);
  // The slider is vertical and 32px of sidebar has no room for the word
  // "Transparency" (2026-09-24), so the tooltip carries it - the same thing
  // the camera panel's Context slider does for the same reason. The visible
  // caption is the percentage under the track.
  transparencySlider.title = `Transparency ${value}% · 0% at the bottom`;
}

updateTransparencyUI(transparencySlider.value);

// Applies `value` (0-100, "how transparent") to every open viewer's WHOLE
// model uniformly - unconditionally, regardless of whether that viewer has
// an active Refer (see referByGuids/clearReferForViewer, which just call
// this at 90/0 to start/end one - there's no separate fade mode to branch
// on here). Real material opacity, same mechanism this slider always used.
// Referred items need no special-casing in this loop at all: they
// physically live in their own separate fragment/mesh by this point (see
// splitReferredItems), which is never registered in fragments.groups - the
// one registry this loop walks - so it simply can't reach them.
export function applyTransparencyValue(value) {
  updateTransparencyUI(value);
  const opacity = 1 - value / 100;
  log(`🔧 Global transparency adjusted to ${value}% (opacity = ${opacity})`);

  viewerData.forEach((entry) => {
    for (const group of entry.fragments.groups.values()) {
      for (const fragment of group.items) {
        const mesh = fragment.mesh;
        if (!mesh) continue;

        const applyOpacity = (mat) => {
          if (!mat) return;
          mat.transparent = opacity < 1;
          mat.opacity = opacity;
          mat.needsUpdate = true;
        };

        if (Array.isArray(mesh.material)) {
          mesh.material.forEach(applyOpacity);
        } else {
          applyOpacity(mesh.material);
        }
      }
    }
  });
}

export function setTransparencyValue(value) {
  transparencySlider.value = value;
  applyTransparencyValue(value);
}

transparencySlider.addEventListener("input", () => {
  applyTransparencyValue(parseInt(transparencySlider.value, 10));
});
