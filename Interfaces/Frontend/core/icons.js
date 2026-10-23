// ======== Inline SVG icons ========
// The page carries one SVG sprite (index.html, `<symbol id="icon-<name>">`,
// the 17 Material Symbols this app uses plus two hand-drawn glyphs:
// `icon-eject` for Unload model and, since 2026-10-01, `icon-polyline` for
// the Lines (test) button). These two helpers are for icons
// built from JS - the same markup the static HTML uses, so one CSS rule
// (`.icon`, style.css) styles both. `fill: currentColor` means every existing
// `color` rule keeps applying; nothing here knows about colours.
//
// Replaces the Material Symbols icon FONT: 314 KB
// from fonts.gstatic.com for 12 glyphs, rendering as ligature text until it
// arrived, and a third-party origin standing between this app and
// cross-origin isolation.

export const iconSvg = (name, className = "icon") =>
  `<svg class="${className}" aria-hidden="true" focusable="false"><use href="#icon-${name}"></use></svg>`;

/** Points an existing icon `<svg>` at another symbol (the theme toggle). */
export function setIcon(svgEl, name) {
  svgEl?.querySelector("use")?.setAttribute("href", `#icon-${name}`);
}
