// ======== Refer-linked lines: the referred intent's line and shapes ========
// "Link components, for example the alignment placement": when a row is
// Referred, its record's line (views/intentLines.js: the alignment through
// the columns, the stack through its members, a polyline through any other
// record's members) and its shapes (footprint, room outlines) are drawn, at
// 3 px, and go when the Refer does.
//
// GATED behind the Lines (test) button: only while that button's own lines
// are drawn (any line not prefixed `refer:`). With the button off a Refer
// changes nothing, so the label-free views - the batch snapshots
// scripts/autocamera.py takes and the pictures a VLM judge sees - stay as
// they were. Opt-in, like the numbered labels (`colorMode`).
//
// Event-driven, so the owner's intent panel needs no change: a Refer ends in
// `intent-refer-complete` on the row (detail.intentId), and every Refer and
// Clear goes through setCameraScope, which emits `camera-scope-change` on the
// container with the new scope or null. The scope change clears the previous
// intent's lines; the completion draws the new one's. Ownership is by id
// prefix (`refer:`), derived from the engine's own list, never stored - a
// stored list would go stale when Unload or Close clear everything.
//
// RACE. addLines awaits anchor resolution; a second Refer before the first
// resolves could land the old intent's lines after the new scope. A sequence
// number taken before the await says whether the world moved on; if it did,
// what just landed is removed again.

import { getModelContext } from "../viewerModel.js";
import { lineSpecFromIntent, shapeSpecsFromIntent } from "./intentLines.js";
import { addLines, listLines, removeLines } from "./lines.js";

export const REFER_LINE_PREFIX = "refer:";
export const REFER_LINE_WIDTH = 3;

/** Ids of the lines a Refer drew in this world. */
export function referLineIds(world) {
  return listLines(world)
    .map((l) => l.id)
    .filter((id) => id.startsWith(REFER_LINE_PREFIX));
}

/** True while the Lines button's own lines (anything not Refer-drawn) are present: the gate. */
export function hasOwnLines(world) {
  return listLines(world).some((l) => !l.id.startsWith(REFER_LINE_PREFIX));
}

/**
 * The specs a Refer draws for one intent: its line and shapes, re-keyed
 * under the refer prefix and at least REFER_LINE_WIDTH wide. Pure.
 * @param {Record<string, any>} intent
 * @param {Array<Record<string, any>> | null} [intents] - the model's records, so a
 *   stack-failure Refer can also draw the stacks it names (views/intentLines.js)
 * @returns {Array<Record<string, any>>}
 */
export function referSpecsForIntent(intent, intents = null) {
  const specs = [lineSpecFromIntent(intent), ...shapeSpecsFromIntent(intent, { intents })].filter(
    Boolean,
  );
  return specs.map((spec) => ({
    ...spec,
    id: REFER_LINE_PREFIX + spec.id,
    style: { ...(spec.style ?? {}), width: Math.max(REFER_LINE_WIDTH, spec.style?.width ?? 1) },
  }));
}

/**
 * Wires the two events on a viewer container. `resolveViewer` looks the
 * viewer entry up at event time (setupViewer's return value does not exist
 * yet while the tile's chrome is built).
 * @param {HTMLElement} container
 * @param {() => any} resolveViewer
 */
export function attachReferLines(container, resolveViewer) {
  let sequence = 0;
  const clear = (world) => {
    const ids = referLineIds(world);
    if (ids.length) removeLines(world, ids);
  };

  container.addEventListener("camera-scope-change", (event) => {
    const viewer = resolveViewer();
    if (!viewer) return;
    const scope = /** @type {CustomEvent} */ (event).detail?.scope ?? null;
    const drawnFor = new Set(
      listLines(viewer.world)
        .filter((l) => l.id.startsWith(REFER_LINE_PREFIX))
        .map((l) => l.spec.meta?.intentId),
    );
    if (drawnFor.size === 0) return;
    const stillReferred = scope?.intentId && drawnFor.size === 1 && drawnFor.has(scope.intentId);
    if (!stillReferred) {
      sequence += 1;
      clear(viewer.world);
    }
  });

  // `intent-refer-complete`: a Refer landed (the intent panel). `intent-refer-
  // reapplied`: the loader painted the active Refer again over tiles that
  // streamed in after it, which cleared the scope (and so these lines) on its
  // way through referByGuids (ThatOpenCompanyLoader.js, Step 6.9).
  const redraw = async (event) => {
    const viewer = resolveViewer();
    if (!viewer?.hasModel) return;
    const { world } = viewer;
    if (!hasOwnLines(world)) return; // the gate: nothing without the Lines button
    const model = viewer.getCurrentModel?.() ?? null;
    const intentId = /** @type {CustomEvent} */ (event).detail?.intentId;
    const intents = getModelContext(model)?.intents ?? [];
    const intent = intents.find((i) => i.id === intentId);
    if (!intent) return;
    const specs = referSpecsForIntent(intent, intents);
    if (specs.length === 0) return;
    const ticket = ++sequence;
    clear(world);
    try {
      const { added } = await addLines(world, specs, { model });
      if (ticket !== sequence && added.length) removeLines(world, added); // a later Refer or Clear won
    } catch (err) {
      console.warn("⚠️ Refer lines: could not draw -", err.message);
    }
  };
  container.addEventListener("intent-refer-complete", redraw);
  container.addEventListener("intent-refer-reapplied", redraw);
}
