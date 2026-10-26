// ======== Scene settings per view ========
// Today the scene is global: one transparency slider, storey × category
// checkboxes, category colours. A view spec can set, for THIS view: the
// non-member transparency, classes to hide (roofs, slabs, ceilings,
// furniture), a colour mode (category colours as now, one strong colour, or
// numbered members), and the page theme. Everything a spec changes is
// recorded on the viewer entry and undone by the next spec, so the state is
// always "what the last spec said" plus whatever the user does by hand.
//
// Three facts shape the code:
//
// - TRANSPARENCY is the global slider (transparency.js). Its meaning - whole
//   -model opacity, all viewers - is locked; the spec drives
//   the slider, it does not add a second mechanism.
// - HIDDEN CLASSES go through the Hider, minus the referred items' ORIGIN
//   instances, and are restored exactly (`hider.set(true, thatMap)`) and then
//   the Refer's own hides re-applied. Never `updateVisibility()`: it ends in
//   `hider.isolate`, which un-hides the origins while the opaque clones still
//   exist, so a member would render twice (and an ID pass count it twice).
//   The Categories checkboxes do not reflect a spec's hides - the app's rule
//   is "no shared mode state, later overrides win" (filterPanel.js), and a
//   checkbox click after a spec simply wins.
// - COLOURS on referred members must be written on the CLONES: the refer
//   split copies each item's colour into its own fragment at split time
//   (highlighting.js), and the Highlighter paints origin instances the clones
//   no longer show. Without a Refer the Highlighter is the right tool.

import * as OBCF from "@thatopen/components-front";
import * as THREE from "three";

import { computeGuidsBoundingBox } from "../cameraViews.js";
import { getIntentColorPalette, resolveGuidIndex } from "../highlighting.js";
import { applyTheme } from "../page/theme.js";
import { setTransparencyValue } from "../transparency.js";
import { getModelContext } from "../viewerModel.js";
import { addNumberLabels, clearNumberLabels } from "./labels.js";

const SINGLE_STYLE = "highlight-view-single";

/** Undoes what the previous spec did to this viewer's scene. */
export function restoreScene(world, entry) {
  const state = entry.viewScene;
  if (!state) return;
  if (state.hiddenMap) {
    entry.hider.set(true, state.hiddenMap);
    for (const split of entry.referSplits ?? []) split.fragment.setVisibility(false, split.itemIds);
  }
  if (state.cloneColors) {
    for (const { mesh, array } of state.cloneColors) {
      if (mesh.instanceColor && mesh.instanceColor.array.length === array.length) {
        mesh.instanceColor.array.set(array);
        mesh.instanceColor.needsUpdate = true;
      }
    }
  }
  if (state.highlighted) {
    try {
      world.components.get(OBCF.Highlighter).clear(SINGLE_STYLE);
    } catch {
      // style never created
    }
  }
  if (state.labels) clearNumberLabels(world);
  if (state.themeBefore !== undefined) applyTheme(state.themeBefore);
  entry.viewScene = null;
}

/** GUID -> {fragmentID, expressID} for a list of GUIDs, dropping unknowns. */
async function locate(model, guids) {
  const index = await resolveGuidIndex(model);
  return guids.map((g) => index.get(g)).filter(Boolean);
}

/**
 * Applies a resolved `scene` spec for a view, after undoing the previous one.
 *
 * @param {any} world
 * @param {Record<string, any>} sceneSpec - resolved (viewSpec.js)
 * @param {{entry: any, model: any, classifier: any, scope?: {guids?: string[] | null, intentId?: string | null} | null}} ctx
 * @returns {Promise<Record<string, any>>} what was applied, for the record
 */
export async function applyScene(world, sceneSpec, ctx) {
  const { entry, model, classifier } = ctx;
  restoreScene(world, entry);
  const state = { hiddenMap: null, cloneColors: null, highlighted: false, labels: 0, themeBefore: undefined };
  const applied = { nonMemberTransparency: null, hiddenClasses: [], colorMode: sceneSpec.colorMode, labels: 0, theme: null };

  if (sceneSpec.nonMemberTransparency !== null) {
    setTransparencyValue(sceneSpec.nonMemberTransparency);
    applied.nonMemberTransparency = sceneSpec.nonMemberTransparency;
  }

  if (sceneSpec.hiddenClasses.length) {
    const known = classifier?.list?.entities ?? {};
    const names = sceneSpec.hiddenClasses.map((n) => String(n).toUpperCase()).filter((n) => known[n]);
    if (names.length) {
      const map = classifier.find({ entities: names }) || {};
      // Never hide a referred item's origin instance: it is already hidden by
      // the split, and un-hiding it on restore must stay the split's business.
      for (const split of entry.referSplits ?? []) {
        const set = map[split.fragment.id];
        if (!set) continue;
        for (const id of split.itemIds) set.delete(id);
        if (set.size === 0) delete map[split.fragment.id];
      }
      if (Object.keys(map).length) {
        entry.hider.set(false, map);
        state.hiddenMap = map;
      }
    }
    applied.hiddenClasses = names;
  }

  const intent = ctx.scope?.intentId ? (getModelContext(model)?.intents ?? []).find((i) => i.id === ctx.scope.intentId) : null;
  const memberGuids = intent
    ? intent.members.filter((m) => m.role !== "context").map((m) => m.guid)
    : (ctx.scope?.guids ?? []);

  if (sceneSpec.colorMode === "single" && memberGuids.length) {
    const color = new THREE.Color(sceneSpec.color ?? getIntentColorPalette()[0] ?? "#ff6a00");
    const located = await locate(model, memberGuids);
    const memberIds = new Set(located.map((l) => l.expressID));
    if (entry.referSplits?.length) {
      state.cloneColors = [];
      for (const split of entry.referSplits) {
        const ids = split.itemIds.filter((id) => memberIds.has(id));
        if (!ids.length) continue;
        const mesh = split.referredFragment.mesh;
        if (mesh.instanceColor) state.cloneColors.push({ mesh, array: mesh.instanceColor.array.slice() });
        split.referredFragment.setColor(color, ids, true);
      }
    } else {
      const highlighter = world.components.get(OBCF.Highlighter);
      try {
        highlighter.add(SINGLE_STYLE, color);
      } catch {
        // already exists
      }
      const selection = {};
      for (const { fragmentID, expressID } of located) (selection[fragmentID] ??= new Set()).add(expressID);
      await highlighter.highlightByID(SINGLE_STYLE, selection, false, false);
      state.highlighted = true;
    }
    applied.color = `#${color.getHexString()}`;
  }

  if (sceneSpec.colorMode === "numbered" && memberGuids.length) {
    const points = [];
    for (const guid of memberGuids) {
      const box = await computeGuidsBoundingBox(world.components, model, [guid]);
      if (box) points.push({ position: box.getCenter(new THREE.Vector3()) });
    }
    state.labels = addNumberLabels(world, points);
    applied.labels = state.labels;
  }

  if (sceneSpec.theme !== "current") {
    state.themeBefore = document.documentElement.getAttribute("data-theme");
    applyTheme(sceneSpec.theme);
    applied.theme = sceneSpec.theme;
  }

  entry.viewScene = state;
  return applied;
}
