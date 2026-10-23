// ======== Picking drawn lines: hover tooltip and a click event ========
// A grid line that cannot say what it is defeats the point. Pointer moves
// over the canvas are raycast against the lines group alone (views/lines.js;
// never the model), rAF-throttled; the nearest hit shows a tooltip inside
// the canvas area with the spec's `meta.label` (or its id) and kind. A click
// on a hit announces `line-selected` on the viewer container with
// `{id, spec, point}` - additive, nothing on `window`.
//
// Thin lines are hit within LINE_PICK_THRESHOLD_M of the ray (three's
// Raycaster.params.Line.threshold, in metres); fat lines use Line2's
// screen-space raycast, which reads the material's resolution and the
// raycaster's camera - `setFromCamera` sets the camera, lines.js keeps the
// resolution at the canvas size. The Highlighter's own click selection is
// untouched: a click that hits both a line and an element fires both the
// `line-selected` and the `element-selected` events, by design.

import * as THREE from "three";

import { LINES_GROUP_NAME, listLines } from "./lines.js";

/** How far from the ray (metres) a 1 px line still counts as hit. */
export const LINE_PICK_THRESHOLD_M = 0.15;
const TOOLTIP_OFFSET_PX = 14;

const raycaster = new THREE.Raycaster();
raycaster.params.Line = { threshold: LINE_PICK_THRESHOLD_M };
raycaster.params.Line2 = { threshold: 0 };

/**
 * The nearest drawn line under a normalised device coordinate.
 * @param {any} world
 * @param {number} ndcX
 * @param {number} ndcY
 * @returns {{id: string, spec: any, point: number[], distance: number} | null}
 */
export function pickLine(world, ndcX, ndcY) {
  const group = world.scene.three.getObjectByName(LINES_GROUP_NAME);
  if (!group || group.children.length === 0) return null;
  raycaster.setFromCamera(new THREE.Vector2(ndcX, ndcY), world.camera.three);
  let hits;
  try {
    hits = raycaster.intersectObjects(group.children, false);
  } catch {
    return null; // a Line2 before its first frame has no resolution yet
  }
  if (hits.length === 0) return null;
  const hit = hits[0];
  const id = hit.object.userData?.lineId;
  if (!id) return null;
  const entry = listLines(world).find((l) => l.id === id);
  return { id, spec: entry?.spec ?? null, point: hit.point.toArray(), distance: hit.distance };
}

/** What the tooltip says for a hit: the label if the author gave one, else the id, then the kind. */
export function tooltipText(hit) {
  const label = hit.spec?.meta?.label || hit.id;
  const kind = hit.spec?.kind ? ` · ${hit.spec.kind}` : "";
  return `${label}${kind}`;
}

/**
 * Wires hover and click on a tile's canvas area.
 * @param {HTMLElement} canvasArea
 * @param {HTMLElement} container
 * @param {() => any} resolveViewer
 * @returns {() => void} detach
 */
export function attachLinePicker(canvasArea, container, resolveViewer) {
  const tooltip = document.createElement("div");
  tooltip.className = "viewer-line-tooltip";
  tooltip.setAttribute("aria-hidden", "true");
  canvasArea.appendChild(tooltip);

  const ndcOf = (viewer, event) => {
    const rect = viewer.world.renderer.three.domElement.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return null;
    return {
      x: ((event.clientX - rect.left) / rect.width) * 2 - 1,
      y: -((event.clientY - rect.top) / rect.height) * 2 + 1,
      left: event.clientX - rect.left,
      top: event.clientY - rect.top,
    };
  };
  const hide = () => {
    tooltip.classList.remove("is-visible");
    delete tooltip.dataset.lineId;
  };

  let pending = null;
  const onMove = (event) => {
    pending = event;
    if (onMove.raf) return;
    onMove.raf = requestAnimationFrame(() => {
      onMove.raf = 0;
      const viewer = resolveViewer();
      const e = pending;
      pending = null;
      // Only the canvas itself: the corner buttons and the name label share
      // the canvas area, and a hover over them must not raise the tooltip.
      if (!viewer?.hasModel || !e || e.target !== viewer.world.renderer.three.domElement)
        return hide();
      const ndc = ndcOf(viewer, e);
      const hit = ndc ? pickLine(viewer.world, ndc.x, ndc.y) : null;
      if (!hit) return hide();
      tooltip.textContent = tooltipText(hit);
      tooltip.dataset.lineId = hit.id;
      tooltip.style.left = `${ndc.left + TOOLTIP_OFFSET_PX}px`;
      tooltip.style.top = `${ndc.top + TOOLTIP_OFFSET_PX}px`;
      tooltip.classList.add("is-visible");
    });
  };
  onMove.raf = 0;
  const onClick = (event) => {
    const viewer = resolveViewer();
    if (!viewer?.hasModel || event.target !== viewer.world.renderer.three.domElement) return;
    const ndc = ndcOf(viewer, event);
    const hit = ndc ? pickLine(viewer.world, ndc.x, ndc.y) : null;
    if (!hit) return;
    container.dispatchEvent(
      new CustomEvent("line-selected", {
        bubbles: true,
        detail: { id: hit.id, spec: hit.spec, point: hit.point },
      }),
    );
  };
  canvasArea.addEventListener("pointermove", onMove);
  canvasArea.addEventListener("pointerleave", hide);
  canvasArea.addEventListener("click", onClick);
  return () => {
    canvasArea.removeEventListener("pointermove", onMove);
    canvasArea.removeEventListener("pointerleave", hide);
    canvasArea.removeEventListener("click", onClick);
    tooltip.remove();
  };
}
