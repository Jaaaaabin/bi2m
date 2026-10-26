// ======== GUID Resolution, Highlighting, Refer & Gray-Out ========
// Extracted from ThatOpenCompanyLoader.js. The only
// behavioral change in here is the GUID index cache - see
// resolveGuidIndex() below. Everything touching materials, colors, opacity
// or visibility is moved verbatim.

import * as OBCF from "@thatopen/components-front";
import * as THREE from "three";

import { getGuidIndex } from "./viewerModel.js";
import { setTransparencyValue } from "./transparency.js";
import { findViewerByWorld, setCameraScope } from "./viewerRegistry.js";
import { log } from "./debug.js";

// ======== External GUID Map ========
// Used for highlighting specific components in IFC models based on external
// mapping. Tracked as a promise (guidMapReady) so callers can await it instead
// of racing against the fetch.
//
// NOTE: this file is externally generated and
// its keys are 12-hex codes that match NONE of this repo's own models - the
// intersection with every data/*.ifc content key AND filename stem is empty,
// so the lookup below currently misses for every fixture present here. That is
// a data-provenance problem (whoever produces this file keys it by something
// this repo can't reproduce), not a code problem, so the code path is left
// exactly as it was rather than being removed - it works the moment the map
// arrives keyed by something resolvable.
let guidMapByFile = {};

export const guidMapReady = fetch("./res/map_visualization.json")
  .then((res) => res.json())
  .then((data) => {
    guidMapByFile = data;
    log("GUID JSON uploaded:", guidMapByFile);
  })
  .catch((err) => {
    console.error("GUID JSON couldn't be uploaded:", err);
  });

export const getGuidMapFor = (fileKey) => guidMapByFile[fileKey];

// ======== Base Gray Material (default viewer appearance) ========
// Recolors every fragment's OWN material to a neutral gray right after load.
// This touches one shared material per FRAGMENT (a batch of same-material
// instances - a handful to a few hundred per model), not per element, so
// it's cheap even on a huge model.
//
// This replaced doing the gray-out on demand: "Gray Out Rest" used to
// highlight the entire model-minus-a-few-GUIDs complement through the
// per-INSTANCE Highlighter path (tens of thousands of individual instance-
// color writes on a large model) every time it was clicked - genuinely slow,
// and the reported cause of "Gray Out Rest takes too long". Making gray the
// baseline at load time moves that cost to one cheap, one-time operation.
//
// Safe to layer real color highlighting on top of: confirmed in
// @thatopen/components-front's source that a highlighted instance is pulled
// onto a SEPARATE mesh with its own dedicated material (not blended with the
// fragment's base material), so recoloring the base material here never
// washes out highlightGUIDs's colors or anything highlighted afterward.
export const BASE_GRAY_COLOR = "#9e9e9e";

export function applyBaseGrayColor(fragments, grayColor = BASE_GRAY_COLOR) {
  for (const group of fragments.groups.values()) {
    applyBaseGrayToFragments(group.items, grayColor);
  }
}

/**
 * The same recolor, for a specific list of fragments rather than every
 * fragment of every group.
 *
 * Needed by the streamed load path: its geometry arrives progressively, in
 * batches the camera culler decides on, so fragments created AFTER the
 * one-shot applyBaseGrayColor() above would otherwise keep their authored IFC
 * colors and the model would render half gray, half not - a difference from
 * the parsed path, not an intended appearance. Scoped to the new fragments
 * specifically (rather than re-running the whole-model version per batch) so
 * it can never touch instance colors an active highlight/refer is relying on.
 */
export function applyBaseGrayToFragments(fragmentList, grayColor = BASE_GRAY_COLOR) {
  const color = new THREE.Color(grayColor);
  for (const fragment of fragmentList) {
    const mesh = fragment.mesh;
    if (!mesh) continue;
    const applyGray = (mat) => {
      if (!mat) return;
      mat.color.set(color);
      mat.needsUpdate = true;
    };
    if (Array.isArray(mesh.material)) {
      mesh.material.forEach(applyGray);
    } else {
      applyGray(mesh.material);
    }
    // Elements with an explicit IfcStyledItem color in the source file get
    // that color baked as a per-instance MULTIPLIER (InstancedMesh.instanceColor),
    // which otherwise keeps rendering regardless of the shared material's own
    // color set above (confirmed by testing: one door kept its original tan
    // color until this was added). Reset every instance's multiplier to
    // white - the identity value, so it stops tinting - rather than nulling
    // the buffer outright: Highlighter's own highlightByID()/resetColor()
    // require this buffer to still exist for later per-instance highlight
    // writes (confirmed: nulling it breaks highlighting with "This fragment
    // doesn't have color per instance!").
    if (mesh.instanceColor) {
      mesh.instanceColor.array.fill(1);
      mesh.instanceColor.needsUpdate = true;
    }
  }
}

// ======== GUID Index Builder (one pass per model) ========
// Maps every element's GlobalId GUID to its {fragmentID, expressID} location.
// Built once per model and reused across all color groups, instead of the
// model's full fragment map being re-scanned with a fresh property lookup per
// element for every color group.
async function buildGuidIndex(model) {
  const fragmentMap = model.getFragmentMap();
  const guidToLocation = new Map();

  // Fast path: for models loaded locally (useJSON: true, non-streamed - which is
  // what this app always does), all properties are already in memory and
  // getLocalProperties() returns them synchronously - no async lookups needed.
  const localProperties = model.getLocalProperties?.();

  if (localProperties) {
    for (const [fragmentID, expressIDs] of Object.entries(fragmentMap)) {
      for (const expressID of expressIDs) {
        const props = localProperties[expressID];
        const guid = props?.GlobalId?.value ?? props?.GlobalId;
        if (guid) guidToLocation.set(guid, { fragmentID, expressID: Number(expressID) });
      }
    }
    return guidToLocation;
  }

  // Fallback for streamed models without local properties: fetch in parallel
  // rather than one expressID at a time.
  console.warn("⚠️ No local properties on model - falling back to per-element async lookups.");
  const lookups = [];
  for (const [fragmentID, expressIDs] of Object.entries(fragmentMap)) {
    for (const expressID of expressIDs) {
      lookups.push(
        model
          .getProperties(Number(expressID))
          .then((props) => {
            const guid = props?.GlobalId?.value ?? props?.GlobalId;
            if (guid) guidToLocation.set(guid, { fragmentID, expressID: Number(expressID) });
          })
          .catch(() => {}),
      );
    }
  }
  await Promise.all(lookups);
  return guidToLocation;
}

// The one entry point for GUID resolution. Routes through viewerModel.js's
// per-model cache, so the O(elements) walk above happens at most ONCE per
// loaded model instead of once per call - see getGuidIndex()'s own comment
// for why that is safe, and for the measured "one Refer click = two full
// model scans" this removes.
export const resolveGuidIndex = (model) => getGuidIndex(model, buildGuidIndex);

// ======== Refer by GUID List ========
// Real alpha transparency, not a color trick: the base model uses the SAME
// whole-model material.opacity the slider always controlled. Referred items
// need more than that alone can give though: material.opacity is a
// per-FRAGMENT property, and fragments here are heavily shared - confirmed on
// real data (test_1.ifc) that a single fragment can hold 22 identical columns
// while only 4 of them belong to the intent actually being referred. An
// earlier version of this code excluded the whole fragment from the fade
// instead of just the referred items - which correctly kept those 4 opaque,
// but incorrectly kept the OTHER 18 (same type, not referred) opaque too.
// This is the bug that got reported and reproduced.
//
// The real fix is physical: split the referred itemIDs out of their origin
// fragment into their own, independent Fragment (own mesh, own cloned
// material), so opacity can finally be set per REFERRED SUBSET rather than
// per fragment. Fragment.clone(itemIDs) does the data-level split (shares
// geometry - cheap - but gets its own InstancedMesh/material reference).
function splitReferredItems(viewerEntry, fragMap) {
  const splits = [];
  for (const [fragmentID, itemIdSet] of Object.entries(fragMap)) {
    const fragment = viewerEntry.fragments.list.get(fragmentID);
    if (!fragment) continue;
    const itemIds = [...itemIdSet];

    // clone() reads matrices/CURRENT colors (e.g. whatever highlightGUIDs
    // just painted; see visualizeIntentGroups, which deliberately colors
    // before referring so this capture already includes it) - purely
    // read-only on the original fragment, so this is always safe.
    const referredFragment = fragment.clone(itemIds);
    const mats = Array.isArray(referredFragment.mesh.material)
      ? referredFragment.mesh.material
      : [referredFragment.mesh.material];
    const clonedMats = mats.map((mat) => mat?.clone() ?? mat);
    referredFragment.mesh.material = Array.isArray(referredFragment.mesh.material)
      ? clonedMats
      : clonedMats[0];
    for (const mat of clonedMats) {
      if (!mat) continue;
      mat.transparent = false;
      mat.opacity = 1;
      mat.needsUpdate = true;
    }
    viewerEntry.world.scene.three.add(referredFragment.mesh);

    // HIDE (not remove) these in the ORIGINAL fragment - prevents double-
    // rendering without touching Fragment.remove(), which has a confirmed
    // bug when removing a proper subset of a multi-item fragment: its
    // inner loop iterates itemToInstances.get(itemID) directly (a live
    // Set), while the putLast() it calls on every iteration mutates that
    // exact Set as a side effect of swapping a DIFFERENT, displaced item
    // into the vacated slot - the loop then picks up that newly-added
    // instance and keeps going, eventually deleting a instanceToItem entry
    // it still needs and throwing "Keys not found" (reproduced directly
    // against real data - this is what the reported bug traced back to).
    // setVisibility's own hide/show loops defensively iterate `new
    // Set(instances)` (a snapshot) instead of the live Set, sidestepping
    // that exact bug, and - as a bonus - preserve all data, so undoing
    // this later is a lossless setVisibility(true, ...), no captured data
    // to restore.
    fragment.setVisibility(false, itemIds);

    splits.push({ fragment, referredFragment, itemIds });
  }
  return splits;
}

// Reverses splitReferredItems: un-hides each origin fragment's items
// (setVisibility never discarded anything, so this is exact and lossless),
// then disposes the temporary referred-only fragment. dispose(false) - not
// the default true - because the clone SHARES geometry with the original;
// disposing resources would destroy that geometry out from under it. Only
// the clone's own (independently cloned) material needs manual disposal.
function restoreSplitItems(splits) {
  for (const { fragment, referredFragment, itemIds } of splits) {
    fragment.setVisibility(true, itemIds);
    const mats = Array.isArray(referredFragment.mesh.material)
      ? referredFragment.mesh.material
      : [referredFragment.mesh.material];
    for (const mat of mats) mat?.dispose();
    referredFragment.dispose(false);
  }
}

// Ends any active Refer for this viewer: restores every split-off item to
// its origin fragment and returns the global transparency slider to 0 - a
// no-op (slider left untouched) if this viewer had no active Refer, so an
// unrelated general-transparency choice (on this viewer earlier, or on
// another viewer right now) is never disturbed by clicking e.g. the
// intent panel's Reset. Returns this viewer's own viewerData entry (or
// undefined) so referByGuids, which needs it right after, doesn't have to
// look it up a second time.
export function clearReferForViewer(world) {
  const viewerEntry = findViewerByWorld(world);
  if (viewerEntry?.referSplits) {
    restoreSplitItems(viewerEntry.referSplits);
    viewerEntry.referSplits = null;
    setTransparencyValue(0);
  }
  // Outside the branch above, unlike the transparency reset: the camera scope
  // is what the view-preset buttons frame instead of the whole building,
  // and "no longer referring anything" has to put them back
  // on the building whether or not this particular call had splits to undo.
  // referByGuids calls this on its way IN, so a fresh Refer clears the old
  // scope here and sets its own afterwards.
  if (viewerEntry) setCameraScope(world, null);
  return viewerEntry;
}

export async function referByGuids(model, world, guidList) {
  const viewerEntry = clearReferForViewer(world);
  const guidToLocation = await resolveGuidIndex(model);
  const expressIDs = [];
  const unmatched = [];

  for (const guid of guidList) {
    const location = guidToLocation.get(guid);
    if (location) expressIDs.push(location.expressID);
    else unmatched.push(guid);
  }

  if (expressIDs.length > 0 && viewerEntry) {
    const fragMap = model.getFragmentMap(expressIDs);
    viewerEntry.referSplits = splitReferredItems(viewerEntry, fragMap);

    // "Automatically" mostly see-through - 90%, not fully invisible, so the
    // rest of the model stays faintly visible as spatial context around
    // whatever's referred, rather than vanishing outright. Adjustable
    // afterward via the same global slider that also controls the ordinary
    // whole-model transparency when no Refer is active.
    //
    // This function still does NOT touch the camera, but the REASON changed
    // (2026-09-19). It used to be "Refer must never move the
    // camera at all", from feedback on an early auto-fit. The standing
    // requirement is now the opposite: Refer SHOULD zoom to the intent, while
    // the rest of the building stays exactly as this function leaves it -
    // ghosted, not hidden. The framing simply lives at the call site (the
    // intent panel's Refer handler, via fitCameraToScope) rather than in
    // here, which keeps this module free of camera concerns and leaves the
    // Show All path - whose union of every intent is roughly the whole
    // building - with nothing to zoom to.
    setTransparencyValue(90);
  }

  return { matchedCount: expressIDs.length, totalCount: guidList.length, unmatched };
}

// ======== Gray Out Non-Specified Elements ========
// The complementary "context" layer to referByGuids: keeps everything
// visible, but ensures nothing EXCEPT the given GUIDs shows a color
// highlight - the rest reverts to the base gray every model already loads
// in (see applyBaseGrayColor above), while the specified elements keep
// whatever highlightGUIDs already applied to them.
//
// Earlier version: computed the full model-minus-guidList complement and
// re-highlighted all of it gray via the Highlighter's per-instance path -
// correct, but O(model size), and the reported cause of "Gray Out Rest
// takes too long" on large models. Now that gray IS the baseline, there's
// nothing to actively gray - the only work left is UN-highlighting whatever
// currently has a real color (from highlightGUIDs) that isn't in guidList.
// `highlighter.selection` already tracks exactly that, so this is bounded by
// how many elements are ACTUALLY highlighted (typically a handful to a few
// dozen from map_visualization.json), never by model size.
export async function grayOutExceptGuids(components, model, guidList) {
  const guidToLocation = await resolveGuidIndex(model);
  const specifiedExpressIDs = new Set();
  const unmatched = [];

  for (const guid of guidList) {
    const location = guidToLocation.get(guid);
    if (location) specifiedExpressIDs.add(location.expressID);
    else unmatched.push(guid);
  }

  const highlighter = components.get(OBCF.Highlighter);
  for (const [styleName, fragMap] of Object.entries(highlighter.selection)) {
    if (styleName === "select" || styleName === "hover") continue; // not color highlights
    const toClear = {};
    for (const [fragmentID, expressIDs] of Object.entries(fragMap)) {
      const remaining = Array.from(expressIDs).filter((id) => !specifiedExpressIDs.has(Number(id)));
      if (remaining.length > 0) toClear[fragmentID] = new Set(remaining);
    }
    if (Object.keys(toClear).length > 0) {
      highlighter.clear(styleName, toClear);
    }
  }

  return { matchedCount: specifiedExpressIDs.size, totalCount: guidList.length, unmatched };
}

// ======== Highlight Elements by GUIDs with Color Groups ========
// Takes the model EXPLICITLY. It used to re-derive one as
// `FragmentsManager.groups.values().next().value` - the first group registered
// in this viewer's manager - and ignore whatever the caller was actually
// working on. That happened to be correct because each viewer owns its own
// OBC.Components (so its manager holds exactly one model), but it would
// silently resolve GUIDs against the wrong model the moment a second model was
// loaded into one viewer, and the per-model GUID index cache
// (viewerModel.js's getGuidIndex) would then pin that mistake for the rest of
// the session. Every caller already has the right model in hand, so it is
// passed in. `world` was in the old signature but never used in the body.
export async function highlightGUIDs(components, model, colorGuidMap, styleNamespace) {
  const namespace = styleNamespace?.split(".")[0] || "model";

  if (!colorGuidMap || typeof colorGuidMap !== "object") {
    console.warn("⚠️ Invalid or missing colorGuidMap");
    return;
  }

  // Drop null/empty placeholder entries (map_visualization.json uses [null] to
  // mark "nothing for this color") and skip entirely if there's nothing real to do.
  const colorGroups = Object.entries(colorGuidMap)
    .map(([color, guidList]) => [color, (Array.isArray(guidList) ? guidList : []).filter(Boolean)])
    .filter(([, guidList]) => guidList.length > 0);

  if (colorGroups.length === 0) {
    log(`ℹ️ No highlight GUIDs specified for ${styleNamespace}.`);
    return;
  }

  if (!model) {
    console.warn("❌ No model found.");
    return;
  }

  const guidToLocation = await resolveGuidIndex(model);

  // Already set up once in setupViewer() (also wires click-to-inspect there).
  const highlighter = components.get(OBCF.Highlighter);

  for (const [color, guidList] of colorGroups) {
    const selection = {};

    for (const guid of guidList) {
      const location = guidToLocation.get(guid);
      if (!location) continue;
      if (!selection[location.fragmentID]) selection[location.fragmentID] = new Set();
      selection[location.fragmentID].add(location.expressID);
    }

    const count = Object.values(selection).reduce((acc, set) => acc + set.size, 0);

    if (count === 0) {
      log(`ℹ️ No matches found for color ${color} (${guidList.length} GUID(s) requested).`);
      continue;
    }

    try {
      const name = `highlight-${namespace}-${color}`;
      const highlightColor = new THREE.Color(color);

      try {
        highlighter.add(name, highlightColor);
      } catch (err) {
        console.warn(`🟡 Style "${name}" already exists, skipping add`);
      }

      log(`🚀 Highlighting ${count} item(s) with color ${color}`);
      await highlighter.highlightByID(name, selection, false, false);
    } catch (err) {
      console.warn(`❗ highlightByID failed for color ${color}:`, err.message);
    }
  }
}

// ======== Intent-Group Color Palette ========
// Reads the 9 themed --intent-color-N custom properties (see style.css) at
// call time, rather than caching them - so a light/dark theme toggle is
// picked up on the very next refer/highlight call with no extra wiring.
// Same values also drive the intent panel's category icons directly via CSS,
// one source of truth for both - colorIndex is assigned per CATEGORY
// (assignCategoryColorIndexes), not per intent, so every intent in one
// category always resolves to the same palette slot here too.
export const INTENT_COLOR_SLOTS = 9;

export function getIntentColorPalette() {
  const styles = getComputedStyle(document.documentElement);
  const palette = [];
  for (let i = 1; i <= INTENT_COLOR_SLOTS; i++) {
    palette.push(styles.getPropertyValue(`--intent-color-${i}`).trim());
  }
  return palette;
}

// Resets every intent-panel color highlight (style names "highlight-
// intent-*") back to each item's pre-highlight color. Needed before
// painting a new Refer/Show All round: highlightGUIDs calls
// highlighter.highlightByID(name, selection, false, false) with
// removePrevious hard-coded false, so a style's previous selection is
// otherwise never cleared - it only merges with the new one. Since color is
// assigned per CATEGORY, stepping Refer between two intents in the same
// category reuses the exact same style name, so without this the first
// intent's members stayed colored forever, on top of whatever the next
// round highlighted. Also called from Reset/Clear, which otherwise only undo
// the visibility split - so un-hidden items came back still bearing whatever
// color was last painted on them.
export function clearIntentHighlights(components) {
  const highlighter = components.get(OBCF.Highlighter);
  for (const styleName of Object.keys(highlighter.selection)) {
    if (styleName.startsWith("highlight-intent-")) highlighter.clear(styleName);
  }
}

// ======== Intent-Group Visualization ========
// Composes referByGuids + highlightGUIDs rather than duplicating either -
// makes the whole model genuinely see-through (real material opacity - not a
// hide, a color trick, or a camera move: the view stays exactly where the
// user left it), while every GUID gets colored in its intent's own
// categorical color EXCEPT "context"-role ones, which get the plain base gray
// (BASE_GRAY_COLOR - i.e. no apparent color change). "context" is the
// inert-evidence role (connection.py's own docstring: the IfcSpace a wall
// group bounds; circulation.py's own docstring: the door(s) that verify a
// stair run) - real geometry that backs up why an intent was recognized,
// without implying it as a colored subject.
// Every OTHER role a detector uses for its real subject (alignment.py/
// connection.py/vertical.py's "member"; structural.py's/circulation.py's
// "base"/"intermediate"/"top" chain-position roles) gets the full category
// color - checking `=== "member"` here instead of `!== "context"` would
// silently leave every structural.py/circulation.py intent rendering as
// flat, uncolored gray, unlike every other category. Giving "context"
// elements a highlight color at all (even a no-op-looking gray) is what
// makes them immune to the base-model fade too, exactly like fully-colored
// elements - see referByGuids/splitReferredItems, which is what actually
// enforces that immunity now.
// highlightGUIDs runs BEFORE referByGuids deliberately: referByGuids
// physically splits referred items into their own fragment, capturing each
// item's CURRENT instance color as part of that split - coloring first
// means the capture already includes the highlight, with no extra plumbing
// needed to carry it across the split. Works identically whether `intents`
// is the full list (Show All) or a single-element array (Refer on one row) -
// each intent's color comes from its own stable `colorIndex`, never from its
// position in whatever subset is passed here.
export async function visualizeIntentGroups(components, model, world, intents, styleNamespace) {
  clearIntentHighlights(components);
  const palette = getIntentColorPalette();
  const allGuids = intents.flatMap((p) => p.members.map((m) => m.guid));
  const colorGuidMap = {};

  for (const intent of intents) {
    const memberGuids = intent.members.filter((m) => m.role !== "context").map((m) => m.guid);
    if (memberGuids.length) {
      const color = palette[intent.colorIndex % palette.length];
      // Two intents can share a color slot once there are more than
      // INTENT_COLOR_SLOTS (the palette cycles) - merge rather than
      // overwrite so neither loses its highlight.
      colorGuidMap[color] = (colorGuidMap[color] || []).concat(memberGuids);
    }
    const contextGuids = intent.members.filter((m) => m.role === "context").map((m) => m.guid);
    if (contextGuids.length) {
      colorGuidMap[BASE_GRAY_COLOR] = (colorGuidMap[BASE_GRAY_COLOR] || []).concat(contextGuids);
    }
  }

  // `intent-${...}` (not the plain name) keeps this highlighter style
  // namespace ("highlight-intent-<name>-<color>") from colliding with
  // map_visualization.json's own ("highlight-<name>-<color>") even if a
  // palette color happens to match one of that file's 3 legend colors.
  await highlightGUIDs(components, model, colorGuidMap, `intent-${styleNamespace}`);
  return referByGuids(model, world, allGuids);
}
