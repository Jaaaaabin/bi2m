// ======== IFC Viewer - Orchestrator ========
// Viewer lifecycle (create/dispose), IFC intake, per-tile chrome, the load
// sequence, and the camera monitor. Everything that is not lifecycle lives in
// its own module now:
//
//   fileIdentity.js    content-addressed file key + IFC header lineage
//   viewerRegistry.js  the open-viewer list and the camera-sync flag
//   viewerModel.js     per-model context (key, geometryLabels, guidIndex, intents)
//   intentData.js     category manifest + lazy per-model intent shard
//   cameraViews.js     bounding boxes, clipping planes, view presets, fitting
//   highlighting.js    GUID index, highlight/refer/gray-out, intent colors
//   transparency.js    the global transparency slider
//   panels/*.js        the filter, camera, intent and compute UI
//   page/*.js          page chrome: theme, sidebar collapse, single-viewer
//                      layout, file intake, example models (2026-09-21)

import * as BUI from "@thatopen/ui";
import * as WEBIFC from "web-ifc";
import * as OBC from "@thatopen/components";
import * as OBCF from "@thatopen/components-front";
import * as THREE from "three";


import { resolveFileIdentity } from "./fileIdentity.js";
import { describeElement, indexGeometry } from "./inspector/describeElement.js";
import { getModelContext, setModelContext } from "./viewerModel.js";
import { loadIntentsForModel } from "./intentData.js";
import {
  enqueueViewerWork,
  findViewerById,
  getCameraScope,
  isCameraSyncEnabled,
  nextViewerContainerId,
  setCameraScope,
  toggleCameraSync,
  viewerData,
} from "./viewerRegistry.js";
import {
  applyBaseGrayColor,
  applyBaseGrayToFragments,
  clearReferForViewer,
  getGuidMapFor,
  guidMapReady,
  highlightGUIDs,
  resolveGuidIndex,
  visualizeIntentGroups,
} from "./highlighting.js";
import {
  applyAutoClippingPlanes,
  CAMERA_FIT_EXCLUDED_CLASSES,
  computeBuildingBoundingBox,
  computeModelBoundingBox,
  DEFAULT_FOV,
  fitCameraToWholeModel,
} from "./cameraViews.js";
import { monitorCamera } from "./cameraMonitor.js";
import { demoLineSpecs, floorRectangleSpec } from "./views/intentLines.js";
import { loadLineSidecar } from "./views/lineSidecar.js";
import { attachLinePicker } from "./views/linePicker.js";
import { attachReferLines, hasOwnLines } from "./views/referLines.js";
import { addLines, clearLines } from "./views/lines.js";
import {
  buildGuidIndexFromSeed,
  loadStreamedModel,
  probeTileSet,
  tileSetBoundingBox,
} from "./tileSet.js";
import { boxOfTileAssets, TILE_BOX_CONVENTION } from "./tileBounds.js";
import { createViewerMenu, snapshotMetadataOn } from "./panels/filterPanel.js";
import { createIntentPanel } from "./panels/intentPanel.js";
import { createShortcutsPanel } from "./panels/shortcutsPanel.js";
import { downloadViewerSnapshot } from "./snapshot.js";
import "./transparency.js"; // self-installing: binds the global slider
import { iconSvg } from "./icons.js";
import { getSetting, setSetting } from "./settings.js";
import { log } from "./debug.js";
import { getGlobalBackgroundColor, initTheme } from "./page/theme.js";
import { applySingleViewerLayout, initSingleViewerLayout } from "./page/layout.js";
import { initIntake } from "./page/intake.js";
import { attachExampleModelsToPlaceholder, initExampleModelsButton } from "./page/exampleModels.js";
import { initLibraryModelsButton } from "./page/libraryModels.js";

const DEFAULT_LOOK_AT = [12, 6, 8, 0, 0, -10];

// Page chrome (page/*.js) - theme first, so the first viewer's scene
// background is already right when it is set up below. The sidebar needs no
// init any more: it has had a single fixed layout since 2026-09-24, so
// page/sidebar.js (which only remembered the collapsed/expanded choice) is
// gone. `bi2m:sidebarCollapsed` may still sit in an old profile's
// localStorage; nothing reads it, and settings.js still migrates the legacy
// key so the value is not stranded under two names.
initTheme();

// ======== Viewer Creation / Removal (single implementation, used by every entry point) ========
// Centralizing this fixes a real bug the old duplicated version had: two separate
// code paths (add-viewer-btn and bulk-upload) each hand-rolled container creation,
// and removal assumed viewerData was always popped in the same order containers
// were created - which breaks the moment any viewer can be closed individually
// (see the per-viewer close button added in setupViewer below).
const viewerWrapperNode = document.getElementById("viewer-wrapper");
initSingleViewerLayout(viewerWrapperNode);

async function createViewer() {
  const id = nextViewerContainerId();

  const container = document.createElement("div");
  container.id = id;
  container.classList.add("viewer-container");
  document.getElementById("viewer-wrapper").appendChild(container);

  const data = await setupViewer({ id, lookAt: DEFAULT_LOOK_AT });
  viewerData.push(data);
  applySingleViewerLayout();
  return data;
}

// ======== Document title ========
// The tab names the open model (2026-10-01): "<file> - <base>" for one loaded
// tile, "<file> +N - <base>" for several, the bare base when none. The base is
// whatever index.html shipped, read once, so renaming it there is enough.
const BASE_DOCUMENT_TITLE = document.title || "Viewer";
function syncDocumentTitle() {
  const names = [...document.querySelectorAll(".viewer-container.has-model .ifc-name-label")]
    .map((el) => el.textContent.trim())
    .filter(Boolean);
  const more = names.length > 1 ? ` +${names.length - 1}` : "";
  document.title = names.length
    ? `${names[0]}${more} - ${BASE_DOCUMENT_TITLE}`
    : BASE_DOCUMENT_TITLE;
}

function removeViewerById(id) {
  if (viewerData.length <= 1) {
    console.warn("⚠️ At least one viewer must remain open.");
    return;
  }
  const index = findViewerById(id);
  if (index === -1) return;

  const data = viewerData[index];
  // Full teardown - previously only the DOM node was removed and the
  // ResizeObserver disconnected, leaving three real leaks behind for every
  // closed viewer (confirmed by code inspection): the camera-sync rAF loop
  // had no exit condition and ran forever; the window-level
  // "element-deselect-request" listener was never removed (holding the
  // highlighter alive indefinitely); and OBC.Components itself (scene,
  // renderer, WebGL context, every loaded model's GPU buffers) was never
  // disposed at all. Order: stop anything still running/listening first,
  // then release GPU/component resources, then remove the DOM node.
  data.cameraAspectObserver?.disconnect();
  data.stopCameraMonitor?.();
  data.stopStreamedFragmentWatch?.();
  if (data.onElementDeselectRequest) {
    window.removeEventListener("element-deselect-request", data.onElementDeselectRequest);
  }
  // Close the inspector if it shows an element of this tile.
  window.dispatchEvent(new CustomEvent("element-deselected", { detail: { container: data.container } }));
  // Lines (views/lines.js) before the scene they live in goes.
  clearLines(data.world);
  try {
    data.world.components.dispose();
  } catch (err) {
    console.warn("⚠️ Error disposing viewer components:", err.message);
  }
  document.getElementById(id)?.remove();
  viewerData.splice(index, 1);
  syncDocumentTitle();
  applySingleViewerLayout();
}

// The empty-state hint plus its list of this server's example models, shown
// while a tile holds no model. A function rather than inline setup because it
// is needed twice: once at viewer creation, and again when Unload releases a
// model - the load path REMOVES this node rather than hiding it, so putting
// the tile back to empty means rebuilding it and re-wiring its example-model
// click handlers.
function addEmptyPlaceholder(canvasArea, viewerId) {
  const emptyPlaceholder = document.createElement("div");
  emptyPlaceholder.className = "viewer-empty-placeholder";
  emptyPlaceholder.innerHTML = `
    ${iconSvg("upload_file")}
    <span>Drop an IFC file here</span>
  `;
  canvasArea.appendChild(emptyPlaceholder);
  attachExampleModelsToPlaceholder(emptyPlaceholder, {
    // This tile, if it is still open and still empty; otherwise the ordinary
    // intake routing.
    loadFile: async (file) => {
      await firstViewerReady;
      const index = findViewerById(viewerId);
      const target = index !== -1 && !viewerData[index].hasModel ? viewerData[index] : null;
      if (target) await loadMultiIFCIntoViewer(file, target);
      else await handleIncomingFiles([file]);
    },
  });
  return emptyPlaceholder;
}

// ======== Unload the Model from One Viewer (the viewer stays open) ========
// The counterpart to removeViewerById: that disposes the whole viewer (its
// OBC.Components, WebGL context and DOM node, and refuses to touch the last
// one); this releases only the MODEL and leaves the tile open, empty and
// ready for the next file - so a user can swap models without losing the
// tile, its size or its position.
//
/**
 * Deletes classification groups whose fragment map is empty.
 *
 * The counterpart to @thatopen's own disposal handler, which empties a
 * group's `map` and then fails to delete the group (see the Correction
 * below). Only empty groups go: a group that still holds fragments belongs to
 * a model still in this tile.
 *
 * Handles both shapes that turn up in `classifier.list`: the library's own
 * `{map, id, name}` groups from `byEntity`/`bySpatialStructure`, and a bare
 * FragmentIdMap, which Step 6 of the load sequence can write directly into
 * `spatialStructures`. A system left with no groups goes too, which is what
 * the library does correctly in its own `delete system[groupID]` branch.
 *
 * @returns {number} how many groups were removed - for the debug log, and so
 *   a caller can tell "nothing to prune" from "pruned nothing".
 */
function pruneEmptyClassifications(classifier) {
  const list = classifier?.list;
  if (!list || typeof list !== "object") return 0;
  let removed = 0;
  for (const [systemName, system] of Object.entries(list)) {
    if (!system || typeof system !== "object") continue;
    for (const [groupName, group] of Object.entries(system)) {
      if (!group || typeof group !== "object") continue;
      const entries = group.map && typeof group.map === "object" ? group.map : group;
      if (Object.keys(entries).length === 0) {
        delete system[groupName];
        removed += 1;
      }
    }
    if (Object.keys(system).length === 0) delete list[systemName];
  }
  if (removed) log(`Unload: pruned ${removed} empty classification group(s)`);
  return removed;
}

// One call does most of the work. `fragments.disposeGroup(model)` frees the
// GPU side (FragmentsGroup.dispose(true) -> every fragment's geometry and
// materials, then removeFromParent) AND triggers FragmentsManager's
// onFragmentsDisposed, which Classifier, IfcRelationsIndexer and
// components-front's IfcStreamer each subscribe to in order to prune their
// own per-model state (@thatopen/components index.mjs:17752 disposeGroup,
// :24652 Classifier, :17236 IfcRelationsIndexer; @thatopen/components-front
// index.js:26909 disposeStreamedGroup).
//
// **Correction, 2026-09-24 - and the reason step 4b below exists.** This
// comment used to end "...and drops groups left empty, so the next model's
// floor/category lists are built from a clean slate". The first half is true
// and the second was not. The Classifier does delete the disposed fragments
// from every group's `map`, but the line that is supposed to remove a group
// once it is empty reads
//
//     if (Object.values(group).length === 0) delete system[groupName];
//
// and `group` is `{map, id, name}`, not the map itself - so its value list is
// never empty and an emptied group was never deleted (index.mjs ~:24640).
// `classifier.list.spatialStructures` and `.entities` were therefore the
// UNION of every model this tile had ever held. Found while building
// scripts/autocamera.py: a model with no such storey reported "Level -2",
// inherited from the model rendered before it. In the viewer it meant the
// Floors and Categories lists kept the previous model's entries after an
// unload, and CAMERA_FIT_EXCLUDED_CLASSES could match a class only the
// previous model had. Step 4b prunes them here instead.
//
// The order below is not arbitrary: everything that still writes to fragment
// materials or listens for new fragments has to stop BEFORE they are
// disposed.
function unloadModelFromViewer(viewer, lookAt) {
  if (!viewer?.hasModel) return;
  const {
    container,
    canvasArea,
    filterPanel,
    cameraPanel,
    intentPanel,
    world,
    fragments,
    classifier,
    highlighter,
  } = viewer;

  // 1. Undo an active Refer first - restoreSplitItems writes to the very
  //    fragments about to be disposed - and put the camera scope back on the
  //    whole building, which is what the (about to be emptied) camera panel
  //    would otherwise still claim to be framing.
  clearReferForViewer(world);
  //    Lines (views/lines.js) are model state: they ran through
  //    THIS model's members and would otherwise float in the empty tile.
  //    Cleared here, before the fragments go, for the same reason the Refer is.
  clearLines(world);

  // 2. Drop the selection so the React inspector closes instead of
  //    describing an element that no longer exists: highlighter.clear fires
  //    the "element-deselected" event the panel listens for.
  try {
    highlighter?.clear("select");
  } catch (err) {
    log("Unload: nothing to clear in the highlighter -", err.message);
  }

  // 3. Stop the per-viewer watchers whose UI or target is about to go away.
  //    The streamed one especially: its per-batch handler recolours arriving
  //    fragments and would otherwise be able to run against a half-disposed
  //    model.
  viewer.stopStreamedFragmentWatch?.();
  viewer.stopStreamedFragmentWatch = null;
  viewer.streamedRefer = null;

  // 4. Release the model itself.
  let model = viewer.getCurrentModel?.() ?? null;
  if (!model) {
    // hasModel is true but nothing was tracked - only reachable when the
    // load could not measure a bounding box (see loadMultiIFCIntoViewer's
    // `if (modelBox)`), so fall back to this viewer's own single group
    // rather than leaving GPU buffers behind. Each viewer has its own
    // Components, so `fragments` here is this tile's manager alone.
    model = fragments.groups.values().next().value ?? null;
    if (model)
      console.warn(
        "⚠️ Unload: no current model tracked for this viewer - disposing its only fragment group.",
      );
  }
  if (model) {
    try {
      fragments.disposeGroup(model);
    } catch (err) {
      console.warn("⚠️ Error disposing the model's fragments:", err.message);
    }
  }

  // 4b. Drop the classification groups that disposal emptied but did not
  //     remove - see the Correction above this function for why they survive.
  //     Safe to do here and nowhere else: each tile builds its own
  //     `new OBC.Components()` (setupViewer), so this Classifier describes
  //     THIS tile's model and no other viewer's lists are touched.
  //     disposeGroup triggers onFragmentsDisposed synchronously, so by this
  //     line the maps are already empty.
  pruneEmptyClassifications(classifier);

  // 5. Back to an empty tile. The three panels described THAT model, so they
  //    are emptied and closed rather than left showing dead controls; the
  //    placeholder (and its example-model list) comes back.
  viewer.setCurrentModel(null);
  viewer.hasModel = false;
  viewer.referSplits = null;
  container.classList.remove(
    "has-model",
    "filters-open",
    "camera-open",
    "intent-open",
    "shortcuts-open",
  );
  filterPanel.innerHTML = "";
  cameraPanel.innerHTML = "";
  intentPanel.innerHTML = "";
  canvasArea.querySelector(".ifc-name-label")?.remove();
  syncDocumentTitle();
  const errorBanner = canvasArea.querySelector(".viewer-error");
  if (errorBanner) errorBanner.style.display = "none";
  if (!canvasArea.querySelector(".viewer-empty-placeholder")) {
    addEmptyPlaceholder(canvasArea, container.id);
  }

  // 6. The camera was framed on a building that is gone - back to this
  //    tile's opening pose. Clipping planes need no reset: the next load's
  //    applyAutoClippingPlanes sets near/far absolutely from that model's
  //    own box.
  world.camera.controls.setLookAt(...lookAt, true);
  console.info("📤 Model unloaded - viewer kept open.");
}

// ======== UI Button Event Listeners ========
// Toggles camera synchronization between viewers.
document.getElementById("sync-cam-btn").addEventListener("click", () => {
  toggleCameraSync();
  document.getElementById("sync-cam-btn").classList.toggle("active");
});

// ======== Panels open by default (intent + camera) ========
// Decided 2026-09-20: the two panels a review session
// actually uses start open. Default ON when nothing is stored. Toggling ON
// also opens them in every viewer currently on screen; OFF closes them, so
// the button always mirrors what is visible. The per-load application lives
// at the START of loadMultiIFCIntoViewer, deliberately before the whole-model
// fit: the intent panel is a flex sibling that narrows the canvas, so a fit
// computed with it closed would be stale the moment it opened.
const panelsDefaultBtn = document.getElementById("panels-default-btn");

export const isPanelsOpenByDefault = () => getSetting("panelsOpenByDefault") !== "0";

function applyDefaultPanels(container, open) {
  container.classList.toggle("intent-open", open);
  container.classList.toggle("camera-open", open);
}

panelsDefaultBtn.classList.toggle("active", isPanelsOpenByDefault());
panelsDefaultBtn.addEventListener("click", () => {
  const next = !isPanelsOpenByDefault();
  setSetting("panelsOpenByDefault", next ? "1" : "0");
  panelsDefaultBtn.classList.toggle("active", next);
  viewerData.forEach((entry) => applyDefaultPanels(entry.container, next));
});

// Adds a new viewer container with its own camera and scene.
document.getElementById("add-viewer-btn").addEventListener("click", () => createViewer());

// Removes the most recently added viewer container.
document.getElementById("remove-viewer-btn").addEventListener("click", () => {
  const last = viewerData[viewerData.length - 1];
  if (last) removeViewerById(last.container.id);
});

// Resizes every other open viewer to match the first one's current pixel
// dimensions (a no-op with 0 or 1 viewers open). Uses the same explicit
// width/height style that dragging .viewer-resize-handle sets, so it composes
// with everything else that reacts to a tile's size changing (the
// cameraAspectObserver on canvasArea, the filters-open min-width bump, etc.)
// without any extra wiring.
document.getElementById("match-sizes-btn").addEventListener("click", () => {
  if (viewerData.length <= 1) return;
  const reference = viewerData[0].container;
  const { width, height } = reference.getBoundingClientRect();
  for (let i = 1; i < viewerData.length; i++) {
    const container = viewerData[i].container;
    container.style.width = `${width}px`;
    container.style.height = `${height}px`;
  }
});

// ======== IFC File Intake (shared by the upload button and drag-and-drop) ========
async function handleIncomingFiles(fileList) {
  await firstViewerReady;
  const files = Array.from(fileList).filter((f) => f.name.toLowerCase().endsWith(".ifc"));
  if (files.length === 0) {
    console.warn("⚠️ No .ifc files found in the dropped/selected files.");
    return;
  }

  // Route each incoming file to an EMPTY viewer, not a positional index - a
  // plain viewerData[i] lookup picked whatever viewer already sat at that
  // slot, which meant adding a single file while viewer 1 already had a
  // model loaded landed it back in viewer 1 (piling a second model into
  // that scene and re-fitting the camera to just the new one, looking like
  // a replace) instead of opening a fresh viewer for it.
  for (const file of files) {
    const target = viewerData.find((v) => !v.hasModel) || (await createViewer());
    await loadMultiIFCIntoViewer(file, target);
  }
}

initIntake({ wrapper: viewerWrapperNode, onFiles: handleIncomingFiles });
initExampleModelsButton({ onFile: (file) => handleIncomingFiles([file]) });
initLibraryModelsButton({ onFile: (file) => handleIncomingFiles([file]) });

// ======== Viewer Setup Function ========
// Initializes a new viewer (canvas, scene, camera, renderer, etc.) with BIM components.
async function setupViewer(config) {
  const container = document.getElementById(config.id);
  if (!container) throw new Error(`Container ${config.id} not found!`);

  // .viewer-container is a flex column (see style.css) holding .viewer-row
  // (the 3D viewport + docked right-side filter panel); .viewer-camera-panel
  // used to be a full-span strip below it and now floats inside canvasArea
  // (see below). Everything that used to be an absolutely-positioned child
  // of `container` (canvas, corner buttons, name label, loading overlay)
  // anchors to `canvasArea` instead, so it stays scoped to the viewport
  // regardless of which panel is open.
  const viewerRow = document.createElement("div");
  viewerRow.className = "viewer-row";
  container.appendChild(viewerRow);

  const canvasArea = document.createElement("div");
  canvasArea.className = "viewer-canvas-area";
  viewerRow.appendChild(canvasArea);

  const filterPanel = document.createElement("div");
  filterPanel.className = "viewer-filter-panel";
  viewerRow.appendChild(filterPanel);

  // Docked left (order: -1 in CSS) - mirrors filterPanel's docked-right
  // mechanics so the two can open independently without fighting for the
  // same edge. Populated later by createIntentPanel, once this viewer's
  // recognized intent groups are known.
  const intentPanel = document.createElement("div");
  intentPanel.className = "viewer-intent-panel";
  viewerRow.appendChild(intentPanel);

  // Camera controls (Top/projection/saved views; populated later by
  // createViewerMenu). Floats over the viewport (position:absolute) and is a
  // child of canvasArea since 2026-09-23 - the same containing block as the
  // camera toggle button it lines up with (see .viewer-camera-panel in
  // style.css), so the two stay aligned when the docked filter panel opens.
  const cameraPanel = document.createElement("div");
  cameraPanel.className = "viewer-camera-panel";
  canvasArea.appendChild(cameraPanel);

  // Shown until a model is loaded into this tile, and again after the Unload
  // button releases one (see unloadModelFromViewer).
  addEmptyPlaceholder(canvasArea, config.id);

  const components = new OBC.Components();

  await components.init();

  const classifier = components.get(OBC.Classifier);
  const hider = components.get(OBC.Hider);
  const indexer = components.get(OBC.IfcRelationsIndexer);
  const fragments = components.get(OBC.FragmentsManager);
  const worlds = components.get(OBC.Worlds);

  const world = worlds.create();
  world.scene = new OBC.SimpleScene(components);
  world.renderer = new OBC.SimpleRenderer(components, canvasArea);
  // OrthoPerspectiveCamera extends SimpleCamera (all existing .controls/
  // .updateAspect() usage keeps working unchanged) and adds .projection
  // (Perspective/Orthographic toggle) plus .threePersp/.threeOrtho, both of
  // which applyAutoClippingPlanes() tunes per model scale. It also
  // auto-updates both cameras' aspect together on updateAspect() (confirmed
  // in its source: onAspectUpdated triggers setOrthoPerspCameraAspect()), so
  // the camera-aspect ResizeObserver below needed no changes for this swap.
  world.camera = new OBC.OrthoPerspectiveCamera(components);
  // The lens, chosen rather than inherited (cameraViews.js, DEFAULT_FOV).
  // Set on threePersp specifically: `.three` points at whichever projection
  // is active, and the orthographic camera has no fov at all. The aspect
  // observer below calls updateAspect(), which updates both projection
  // matrices, so this survives every resize.
  world.camera.threePersp.fov = DEFAULT_FOV;
  world.camera.threePersp.updateProjectionMatrix();

  world.camera.controls.setLookAt(...config.lookAt);
  world.scene.setup();
  // Matches the page's current background instead of SimpleScene's own
  // fixed default (#202932) - see getGlobalBackgroundColor/applyTheme above,
  // which also keeps this in sync on every later theme toggle.
  world.scene.config.backgroundColor = new THREE.Color(getGlobalBackgroundColor());

  world.renderer.three.setClearColor(0x000000, 0);
  canvasArea.style.backgroundColor = "transparent";

  // SimpleRenderer wires its own ResizeObserver internally (confirmed in the
  // library source) and keeps its canvas in sync automatically, but nothing in
  // @thatopen/components updates the camera's aspect ratio on resize - no
  // component subscribes to the renderer's resize event. Without this, dragging
  // a .viewer-container's resize handle - or toggling the filter panel, which
  // also changes canvasArea's width - stretches/squashes the render until
  // something else forces a re-fit. Observing canvasArea (not the outer
  // container) is what makes the filter-panel toggle also refresh the camera
  // aspect, since that's the element whose actual size changes.
  // The same observer keeps --camera-panel-height current, which the
  // inspector slot reads to end above the camera panel (style.css).
  const cameraAspectObserver = new ResizeObserver(() => {
    world.camera.updateAspect();
    canvasArea.style.setProperty("--camera-panel-height", `${cameraPanel.offsetHeight}px`);
  });
  cameraAspectObserver.observe(canvasArea);
  cameraAspectObserver.observe(cameraPanel);

  const cameraMonitor = monitorCamera(world, fragments, {
    peers: () => viewerData,
    syncEnabled: isCameraSyncEnabled,
  });

  // ---- Click-to-inspect: reuse the Highlighter's built-in click selection
  // (selectName "select", enabled by default) instead of writing a custom
  // raycaster. What the inspector shows is gathered by
  // inspector/describeElement.js and sent as a CustomEvent, so this vanilla
  // code never depends on React. The event names this tile (`container`):
  // the panel opens in this tile's inspector slot, and closing it clears
  // only this tile's selection.
  const highlighter = components.get(OBCF.Highlighter);
  if (!highlighter.isSetup) {
    await highlighter.setup({ world });
  }

  // The inspector's fixed place: top-right of this tile's 3D viewport, below
  // the button row and above the camera panel (style.css).
  const inspectorSlot = document.createElement("div");
  inspectorSlot.className = "viewer-inspector-slot";
  canvasArea.appendChild(inspectorSlot);

  highlighter.events.select.onHighlight.add(async (fragmentIdMap) => {
    const model = fragments.groups.values().next().value;
    const [fragmentID, expressIDs] = Object.entries(fragmentIdMap)[0] || [];
    const expressID = expressIDs ? Array.from(expressIDs)[0] : undefined;
    if (!model || expressID === undefined) return;
    const description = await describeElement(model, expressID);
    window.dispatchEvent(
      new CustomEvent("element-selected", { detail: { container, fragmentID, ...description } }),
    );
  });

  highlighter.events.select.onClear.add(() => {
    window.dispatchEvent(new CustomEvent("element-deselected", { detail: { container } }));
  });

  // The inspector's close button asks for the 3D selection to be cleared
  // too - in the tile it names (every tile listens). Named (not inline) so
  // removeViewerById can remove it on close - previously this leaked one
  // listener (holding a reference to this viewer's highlighter) per closed
  // viewer, forever, for the rest of the page's lifetime.
  const onElementDeselectRequest = (event) => {
    const target = event.detail?.container;
    if (!target || target === container) highlighter.clear("select");
  };
  window.addEventListener("element-deselect-request", onElementDeselectRequest);

  // ---- Per-viewer controls: close this viewer + unload model (top-left),
  // toggle filters (top-right) ---- (present immediately, independent of
  // whether an IFC has loaded yet). The close and unload buttons anchor to
  // canvasArea so they stay over the 3D viewport once the docked intent
  // panel opens; the filters toggle anchors to the tile itself (see below).
  // The "Reset camera view" home button that used to sit in the top-right
  // row was removed 2026-09-23 at the owner's request - the camera panel's
  // "Top" is the same whole-building fit.
  // Tracks the currently-loaded model - loadMultiIFCIntoViewer calls the
  // returned setCurrentModel() after every successful load, and
  // unloadModelFromViewer reads it back through getCurrentModel() to know
  // which model to dispose.
  let currentModel = null;

  // Top-left, right of the close button (moved there from the very right of
  // the top row 2026-09-23), and permanently in --color-danger (see
  // style.css): the one control here that throws work away should look like
  // it. Always shown, including on a tile with nothing loaded, where it is
  // simply inert - unloadModelFromViewer returns immediately unless
  // viewer.hasModel. Releases the model but keeps the viewer.
  const unloadModelBtn = document.createElement("button");
  unloadModelBtn.className = "viewer-unload-btn";
  unloadModelBtn.title = "Unload";
  unloadModelBtn.setAttribute("aria-label", "Unload");
  unloadModelBtn.innerHTML = iconSvg("eject");
  unloadModelBtn.addEventListener("click", () => {
    // Looks itself up rather than closing over the entry: this runs at click
    // time, and setupViewer's return value (the viewerData entry) does not
    // exist yet while these buttons are being built.
    const index = findViewerById(config.id);
    if (index !== -1) unloadModelFromViewer(viewerData[index], config.lookAt);
  });
  canvasArea.appendChild(unloadModelBtn);

  // Top-left, third in the row (2026-10-01): a TEST control for
  // the line engine (views/lines.js). One click draws the loaded model's demo
  // set - every alignment line and column stack as a polyline through the
  // members, the footprints and room outlines its records describe
  // (views/intentLines.js), plus the model's authored sidecar shapes
  // (views/lineSidecar.js), or the footprint rectangle when there is none of
  // that - and the next click clears them. `aria-pressed` mirrors
  // whether lines are drawn, set from the engine's own event so a line added
  // by a script shows here too; `aria-busy` holds while anchors resolve and
  // clicks during that are ignored (the Refer's precedent). Inert without a
  // model, like Unload. The block is one piece, meant to be replaced by real
  // line sources later; nothing else depends on it.
  const linesBtn = document.createElement("button");
  linesBtn.className = "viewer-lines-btn";
  linesBtn.title = "Lines (test)";
  linesBtn.setAttribute("aria-label", "Lines (test)");
  linesBtn.setAttribute("aria-pressed", "false");
  linesBtn.innerHTML = iconSvg("polyline");
  // Pressed = the button's OWN lines are drawn (anything not Refer-drawn,
  // views/referLines.js), so a Refer's line alone never shows it pressed.
  const resolveViewer = () => {
    const index = findViewerById(config.id);
    return index === -1 ? null : viewerData[index];
  };
  container.addEventListener("overlay-lines-changed", () => {
    const viewer = resolveViewer();
    linesBtn.setAttribute("aria-pressed", viewer && hasOwnLines(viewer.world) ? "true" : "false");
  });
  linesBtn.addEventListener("click", async () => {
    const index = findViewerById(config.id);
    if (index === -1) return;
    const viewer = viewerData[index];
    if (!viewer.hasModel || linesBtn.getAttribute("aria-busy") === "true") return;
    const { world } = viewer;
    if (hasOwnLines(world)) {
      // Off: the button's set goes, and with it the Refer-linked lines it
      // gates (views/referLines.js) - the tile is back to label-free.
      clearLines(world);
      return;
    }
    const model = viewer.getCurrentModel?.() ?? null;
    const context = model ? getModelContext(model) : null;
    // The authored sidecar (views/lineSidecar.js) joins the record-derived
    // set: public/res/lines/<key>.json, the authored grid lines' own home.
    const sidecar = await loadLineSidecar(context?.key);
    let specs = [...demoLineSpecs(context?.intents ?? []), ...sidecar];
    if (specs.length === 0 && model) {
      const box = computeModelBoundingBox(world.components, model);
      if (box) specs = [floorRectangleSpec(box)];
    }
    if (specs.length === 0) {
      log("Lines: nothing to draw - no alignment or stack records, no measurable model box.");
      return;
    }
    linesBtn.setAttribute("aria-busy", "true");
    try {
      const { added, skipped } = await addLines(world, specs, { model });
      log(`Lines: ${added.length} drawn, ${skipped.length} skipped.`);
    } catch (err) {
      console.warn("⚠️ Lines: could not draw -", err.message);
    } finally {
      linesBtn.removeAttribute("aria-busy");
    }
  });
  canvasArea.appendChild(linesBtn);
  // A Refer draws the referred intent's line and shapes while the button is
  // on (views/referLines.js); hovering a drawn line names it, clicking one
  // announces `line-selected` (views/linePicker.js). Both look the viewer up
  // at event time, like the buttons above.
  attachReferLines(container, resolveViewer);
  attachLinePicker(canvasArea, container, resolveViewer);

  // Anchored to the TILE (container), not canvasArea, since 2026-09-23: the
  // filter panel it opens is docked at the tile's right edge and narrows the
  // canvas by 220px, so a canvas-anchored button jumped left out from under
  // the pointer on every click. On the tile it stays put, floating over the
  // opened panel's top-right corner (style.css reserves that band).
  const filtersToggleBtn = document.createElement("button");
  filtersToggleBtn.className = "viewer-settings-btn";
  filtersToggleBtn.title = "Filters";
  filtersToggleBtn.setAttribute("aria-label", "Filters");
  filtersToggleBtn.innerHTML = iconSvg("tune");
  filtersToggleBtn.addEventListener("click", () => container.classList.toggle("filters-open"));
  container.appendChild(filtersToggleBtn);

  const closeViewerBtn = document.createElement("button");
  closeViewerBtn.className = "viewer-close-btn";
  closeViewerBtn.title = "Close";
  closeViewerBtn.setAttribute("aria-label", "Close");
  closeViewerBtn.textContent = "×";
  closeViewerBtn.addEventListener("click", () => removeViewerById(config.id));
  canvasArea.appendChild(closeViewerBtn);

  // Bottom-right, a pair. Snapshot (left) writes one PNG of the tile's
  // current render; the camera toggle (right) opens and closes the floating
  // camera panel (Top/projection/saved views), independent of the top-right
  // filters toggle. Both keep ONE fixed corner position whether that panel
  // is open or shut - the "static location" idiom the owner asked for on the
  // filters and intent toggles - and the open panel reaches down to them,
  // so its bottom row reads view name / Save / Snapshot / Camera left to
  // right and the last two controls of that row are these buttons
  // (style.css, 2026-09-24).
  //
  // Snapshot is the hand-operated twin of scripts/autocamera.py: that driver
  // photographs all 370 library models unattended, this photographs the one
  // view in front of you, with the same content-key-first naming so the two
  // sets stay joinable (snapshot.js, which also explains why the capture has
  // to render and read back in one synchronous block). Always shown and
  // inert with nothing loaded, like the Unload button - downloadViewerSnapshot
  // returns null unless viewer.hasModel, and there is nothing to photograph.
  const snapshotBtn = document.createElement("button");
  snapshotBtn.className = "viewer-snapshot-btn";
  snapshotBtn.title = "Snapshot";
  snapshotBtn.setAttribute("aria-label", "Snapshot");
  snapshotBtn.innerHTML = iconSvg("screenshot");
  snapshotBtn.addEventListener("click", async () => {
    // Looked up at click time, like the Unload button's handler: setupViewer's
    // return value does not exist yet while these buttons are being built.
    const index = findViewerById(config.id);
    if (index === -1) return;
    // The name the user typed next to Save, if any - the input lives in the
    // camera panel, which is rebuilt on every load, so it is read now rather
    // than captured. An empty box just means the file is called "snapshot".
    const viewName = container.querySelector(".viewer-view-name-input")?.value ?? "";
    // With the camera panel's Meta switch on (panels/filterPanel.js), the
    // GUID metadata goes out beside the PNG (snapshot.js, 2026-10-22).
    const shot = await downloadViewerSnapshot(viewerData[index], viewName, null, { metadata: snapshotMetadataOn() });
    if (!shot) return;
    // The only in-page sign anything happened: the file itself goes to the
    // browser's downloads, which this page never sees.
    snapshotBtn.classList.add("is-capturing");
    setTimeout(() => snapshotBtn.classList.remove("is-capturing"), 450);
    log(`Snapshot: ${shot.fileName} (${shot.width}x${shot.height})` + (shot.metadataFileName ? ` + ${shot.metadataFileName}` : ""));
  });
  canvasArea.appendChild(snapshotBtn);

  const cameraToggleBtn = document.createElement("button");
  cameraToggleBtn.className = "viewer-camera-toggle-btn";
  cameraToggleBtn.title = "Camera";
  cameraToggleBtn.setAttribute("aria-label", "Camera");
  cameraToggleBtn.innerHTML = iconSvg("photo_camera");
  cameraToggleBtn.addEventListener("click", () => container.classList.toggle("camera-open"));
  canvasArea.appendChild(cameraToggleBtn);

  // Bottom-left. Toggles the intent validation panel, independent of the
  // filters/camera toggles. Anchored to the TILE like the filters toggle
  // (2026-09-23, owner's request): the intent panel it opens is docked at
  // the tile's LEFT edge (order:-1) and pushes the canvas right, so a
  // canvas-anchored button jumped right on every click. On the tile it stays
  // in the lower-left, floating over the open panel's bottom-left corner
  // (style.css ends the panel's content 48px above the bottom for it).
  const intentToggleBtn = document.createElement("button");
  intentToggleBtn.className = "viewer-intent-toggle-btn";
  intentToggleBtn.title = "Intents";
  intentToggleBtn.setAttribute("aria-label", "Intents");
  intentToggleBtn.innerHTML = iconSvg("fact_check");
  intentToggleBtn.addEventListener("click", () => container.classList.toggle("intent-open"));
  container.appendChild(intentToggleBtn);

  // Next to it: the floating keyboard cheat sheet and its toggle
  // (panels/shortcutsPanel.js) - tile-anchored as well, so the pair and the
  // sheet above them move together.
  createShortcutsPanel({ container });

  attachResizeHandle(container);

  return {
    world,
    container,
    canvasArea,
    filterPanel,
    cameraPanel,
    intentPanel,
    fragments,
    classifier,
    hider,
    indexer,
    highlighter,
    cameraAspectObserver,
    stopCameraMonitor: cameraMonitor.stop,
    receiveCameraSync: cameraMonitor.receive, // the other viewers' monitors call this when sync is on (cameraMonitor.js)
    onElementDeselectRequest,
    setCurrentModel: (model) => {
      currentModel = model;
    },
    getCurrentModel: () => currentModel,
    hasModel: false, // flipped true once loadMultiIFCIntoViewer's first model lands - see handleIncomingFiles
    referSplits: null, // Array<{fragment, referredFragment, itemIds}> while a Refer is active for this viewer, or null
    stopStreamedFragmentWatch: null, // set only on the streamed path - see loadMultiIFCIntoViewer Step 6.9
    streamedRefer: null, // {intent, fileName, guids} while a Refer is active on a STREAMED model (intentPanel.js), re-applied per batch in Step 6.9
  };
}

// ======== Custom Viewer Resize Handle ========
// Replaces the native CSS `resize: both` on .viewer-container. Native resize
// fires no JS events during the drag (ResizeObserver only sees the end
// result), so there is no way to inspect Shift/Ctrl at drag time with it -
// this handle exists specifically to support:
//   Shift held  -> lock the aspect ratio the tile had when the drag started.
//   Ctrl held   -> lock to a single axis (horizontal-only or vertical-only),
//                  decided from whichever axis the first few pixels of
//                  movement favor, then held for the rest of that drag.
// canvasArea's own ResizeObserver (see setupViewer) picks up every width/
// height change this makes exactly like it does for the CSS resize/filters-
// open cases, so the 3D view stays correctly fitted with no extra wiring.
function attachResizeHandle(container) {
  const handle = document.createElement("div");
  handle.className = "viewer-resize-handle";
  handle.title = "Resize"; // Shift locks the aspect ratio, Ctrl one axis
  container.appendChild(handle);

  const AXIS_LOCK_THRESHOLD = 4; // px of movement before Ctrl commits to an axis

  let drag = null;

  function onMouseMove(event) {
    if (!drag) return;
    event.preventDefault();

    let dx = event.clientX - drag.startX;
    let dy = event.clientY - drag.startY;

    if (event.ctrlKey) {
      if (
        drag.axisLock === null &&
        (Math.abs(dx) > AXIS_LOCK_THRESHOLD || Math.abs(dy) > AXIS_LOCK_THRESHOLD)
      ) {
        drag.axisLock = Math.abs(dx) >= Math.abs(dy) ? "x" : "y";
      }
      if (drag.axisLock === "x") dy = 0;
      else if (drag.axisLock === "y") dx = 0;
    } else {
      drag.axisLock = null; // releasing Ctrl mid-drag returns to free resize
    }

    let width = Math.max(drag.minWidth, drag.startWidth + dx);
    let height = Math.max(drag.minHeight, drag.startHeight + dy);

    if (event.shiftKey) {
      // Re-derive the smaller dimension from the one that moved more, so the
      // tile scales uniformly from its size at drag-start.
      if (Math.abs(dx) >= Math.abs(dy)) {
        height = Math.max(drag.minHeight, width / drag.aspectRatio);
      } else {
        width = Math.max(drag.minWidth, height * drag.aspectRatio);
      }
    }

    container.style.width = `${width}px`;
    container.style.height = `${height}px`;
  }

  function onMouseUp() {
    drag = null;
    document.removeEventListener("mousemove", onMouseMove);
    document.removeEventListener("mouseup", onMouseUp);
  }

  handle.addEventListener("mousedown", (event) => {
    event.preventDefault();
    // From here on this tile is the user's: the single-viewer auto layout
    // (applySingleViewerLayout) must neither override nor later clear it.
    container.dataset.userSized = "1";
    delete container.dataset.autoSized;
    const rect = container.getBoundingClientRect();
    const computed = getComputedStyle(container);
    drag = {
      startX: event.clientX,
      startY: event.clientY,
      startWidth: rect.width,
      startHeight: rect.height,
      aspectRatio: rect.width / rect.height,
      minWidth: parseFloat(computed.minWidth) || 0,
      minHeight: parseFloat(computed.minHeight) || 0,
      axisLock: null,
    };
    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
  });
}

// ======== web-ifc threading guard ========
// web-ifc picks its multi-thread build ONCE per page, inside the first
// IfcAPI.Init() call, whenever `crossOriginIsolated` is true - and ThatOpen's
// IfcLoader never passes web-ifc's `forceSingleThread` flag. That build does
// not work here (its pthread workers die under `vite dev`),
// and a tab that happened to load its document while COOP/COEP headers were
// on then hangs at "Parsing…" on every model, for as long as the tab lives
// (observed 2026-09-21). The choice is module-global in web-ifc, so a
// throwaway IfcAPI initialised with forceSingleThread=true pins the whole
// page to the single-thread engine before the loader's own Init runs - on
// its own instance, so ThatOpen's later Init still sees a fresh one and logs
// nothing. Costs nothing unless the document is isolated. `?mt=1` opts back
// in, for the multi-thread spike against a production build.
const WEB_IFC_WASM_PATH = "/wasm/";
let webIfcThreadingPinned = null;

function pinWebIfcSingleThread() {
  if (!webIfcThreadingPinned) {
    webIfcThreadingPinned = (async () => {
      const wantMultiThread = new URLSearchParams(location.search).get("mt") === "1";
      if (wantMultiThread || !self.crossOriginIsolated) return;
      console.warn(
        "⚠️ This document is cross-origin isolated; pinning web-ifc to its single-thread build (add ?mt=1 to try the multi-thread one).",
      );
      const probe = new WEBIFC.IfcAPI();
      probe.SetWasmPath(WEB_IFC_WASM_PATH, true);
      await probe.Init(undefined, true);
      probe.Dispose();
    })().catch((err) => console.warn("⚠️ Could not pin web-ifc threading:", err.message));
  }
  return webIfcThreadingPinned;
}

// ======== Loading Indicator ========
// IFC parsing/streaming is genuinely slow (multi-second for real models) and
// previously gave zero visual feedback, so a large upload could look like a
// hang. Toggled around the load in loadMultiIFCIntoViewer below.
function setViewerLoading(container, isLoading, message = "Loading model…") {
  let overlay = container.querySelector(".viewer-loading");
  if (isLoading) {
    if (!overlay) {
      overlay = document.createElement("div");
      overlay.className = "viewer-loading";
      overlay.innerHTML = `<div class="viewer-loading-spinner"></div><span></span>`;
      container.appendChild(overlay);
    }
    overlay.querySelector("span").textContent = message;
    overlay.style.display = "flex";
  } else if (overlay) {
    overlay.style.display = "none";
  }
}

// ======== Inline Load-Error Banner ========
// Replaces the previous alert() call (a blocking native dialog) with an
// in-place, dismissible banner scoped to the viewer tile that failed - a bad
// file in one viewer no longer interrupts interaction with the rest of the page.
function setViewerError(container, message) {
  let overlay = container.querySelector(".viewer-error");
  if (!overlay) {
    overlay = document.createElement("div");
    overlay.className = "viewer-error";
    overlay.innerHTML = `
      ${iconSvg("error", "icon viewer-error-icon")}
      <span class="viewer-error-message"></span>
      <button class="viewer-error-dismiss" title="Dismiss" aria-label="Dismiss">×</button>
    `;
    overlay.querySelector(".viewer-error-dismiss").addEventListener("click", () => {
      overlay.style.display = "none";
    });
    container.appendChild(overlay);
  }
  overlay.querySelector(".viewer-error-message").textContent = message;
  overlay.style.display = "flex";
}

// The tile set's metadata as the model context keeps it (`tileMetadata`):
// the descriptor, the raw GlobalId -> expressID seed, each element's placed
// geometries, every geometry's box, and the whole-model boxes. A tile set
// written since 2026-10-21 (descriptor.boxConvention, tileBounds.js) ships
// boxes the viewer can trust; an older one shipped boxes composed on the
// wrong cube, so both boxes are recomputed here from the same metadata (~5k
// assets, one pass). The building box drops IfcSite / IfcGeographicElement
// exactly as the tiler does offline: IfcStreamer.load keeps the property
// tiler's `types` (expressID -> web-ifc type code) on
// `model.streamSettings.types`, so the types are there before anything is
// classified (review, 2026-10-21 - terrain would otherwise
// dominate every old set's whole-model frame, the case the measured
// camera reference distances cover).
const STREAMED_SITE_TYPES = new Set([WEBIFC.IFCSITE, WEBIFC.IFCGEOGRAPHICELEMENT]);

function streamedTileMetadata(descriptor, guidSeed, tiles, model) {
  const assetsById = new Map(tiles.assets.map((asset) => [asset.id, asset]));
  model.updateMatrixWorld(true);
  const trusted = descriptor.boxConvention === TILE_BOX_CONVENTION;
  let worldBox;
  let buildingBox;
  if (trusted) {
    worldBox = tileSetBoundingBox(descriptor, "worldBoundingBox", model.matrixWorld);
    buildingBox = tileSetBoundingBox(descriptor, "buildingBoundingBox", model.matrixWorld);
  } else {
    worldBox = boxOfTileAssets(tiles.assets, tiles.geometries, model.matrixWorld);
    const types = model.streamSettings?.types;
    const isSite = (asset) => types instanceof Map && STREAMED_SITE_TYPES.has(types.get(asset.id));
    const building = tiles.assets.filter((asset) => !isSite(asset));
    buildingBox = (building.length ? boxOfTileAssets(building, tiles.geometries, model.matrixWorld) : null) ?? worldBox;
    console.info(
      `📦 Tile set ${descriptor.fileKey} predates the 2026-10-21 box fix - whole-model boxes recomputed from its metadata ` +
        `(${tiles.assets.length - building.length} site/terrain element(s) excluded from the building box; ` +
        "re-run scripts/tileIfc.mjs to ship them in tileset.json).",
    );
  }
  return { descriptor, guidSeed, assetsById, geometries: tiles.geometries, worldBox, buildingBox, trusted };
}

// ======== IFC Loader for Bulk Uploads ========
// Loads an IFC file into one viewer.
async function loadMultiIFCIntoViewer(file, viewer) {
  const {
    container,
    canvasArea,
    filterPanel,
    cameraPanel,
    intentPanel,
    world,
    fragments,
    classifier,
    indexer,
    hider,
  } = viewer;
  const components = world.components;

  // Clear any error banner left over from a previous failed attempt on this
  // viewer - otherwise a successful retry still shows the old failure message.
  const previousError = canvasArea.querySelector(".viewer-error");
  if (previousError) previousError.style.display = "none";

  setViewerLoading(canvasArea, true, `Loading ${file.name}…`);

  // Before anything that measures the canvas (see the panels-default block
  // near the sidebar handlers): opening the intent panel resizes the canvas,
  // and the whole-model fit below must be computed for the size it will have.
  if (isPanelsOpenByDefault()) applyDefaultPanels(container, true);

  try {
    // --- Step 1: Load IFC file into buffer, and establish its identity ---
    const arrayBuffer = await file.arrayBuffer();
    const buffer = new Uint8Array(arrayBuffer);

    // Content key FIRST, while `arrayBuffer` is still intact: indexGeometry
    // (Step 4) transfers (detaches) it into a Worker, after which it can't be read
    // again. Hashing 20MB through crypto.subtle is native and fast, and it has
    // to happen before anything that joins on the key (highlight map, intent
    // shard, verdicts) is looked up. See fileIdentity.js and
    // docs/architecture.md "One key for everything".
    const identity = await resolveFileIdentity(arrayBuffer, buffer, file.name);

    // --- Step 1.5: Stream from a pre-converted tile set if one exists for
    // exactly these bytes, instead of re-parsing the whole raw IFC through
    // web-ifc (docs/architecture.md "Viewer"). Additive: any failure, or no
    // tile set at all, falls through to the raw path below unchanged. The
    // lookup is exact only because the key is the file's content - see
    // tileSet.js. ---
    let model = null;
    let streamedGuidSeed = null;
    let streamedTiles = null;
    const tileSet = await probeTileSet(identity.key);

    if (tileSet) {
      setViewerLoading(canvasArea, true, `Streaming ${file.name}…`);
      try {
        const streamed = await loadStreamedModel({ components, world, descriptor: tileSet });
        model = streamed.model;
        streamedGuidSeed = streamed.guidSeed;
        streamedTiles = streamed;
        console.info(
          `📦 Streamed ${file.name} from tiles/${identity.key}/ ` +
            `(${tileSet.assetCount} assets, ${tileSet.tileCount} geometry tiles) - raw IFC parse skipped.`,
        );
      } catch (err) {
        console.warn(
          "⚠️ Tile-set streaming failed, falling back to a full IFC parse:",
          err.message,
        );
        model = null;
      }
    }

    if (!model) {
      setViewerLoading(canvasArea, true, `Parsing ${file.name}…`);
      const loader = components.get(OBC.IfcLoader);
      // Self-hosted engine. setup()'s default
      // `autoSetWasm` fetched unpkg.com twice on every fresh session (the
      // components package.json to learn the web-ifc version, then
      // web-ifc.wasm itself), so a browser without internet - the SSH-forward
      // case this app is built around - could not open any un-tiled model.
      // vite.config.js's webIfcWasmPlugin copies web-ifc.wasm, web-ifc-mt.wasm
      // and web-ifc-mt.worker.js from node_modules into public/wasm/, and
      // web-ifc resolves `path + <file>` for all three, picking the -mt build
      // by itself when the page is cross-origin isolated (1.3).
      await pinWebIfcSingleThread();
      await loader.setup({
        autoSetWasm: false,
        wasm: { ...loader.settings.wasm, path: WEB_IFC_WASM_PATH, absolute: true },
      });

      model = await loader.load(buffer, { useJSON: true });
    }

    if (!model) throw new Error("Model is undefined.");
    model.name = file.name;
    const isStreamed = streamedGuidSeed !== null;

    // One per-model context from here on - replaces properties once set on the
    // model and every separate re-derivation of a key from the file name.
    const context = setModelContext(model, {
      key: identity.key,
      keySource: identity.keySource,
      fileName: identity.fileName,
      lineage: identity.lineage,
      geometryLabels: undefined,
      // For a streamed model the GUID index is already known offline (the
      // tile set ships a GlobalId -> expressID map), so it is seeded here
      // rather than being derived by walking every element's properties -
      // which a streamed model has none of locally anyway. A normal parsed
      // model leaves this null and builds it lazily on first use.
      guidIndex: isStreamed
        ? Promise.resolve(buildGuidIndexFromSeed(model, streamedGuidSeed))
        : null,
      intents: [],
      isStreamed,
      // The tile set's own metadata, kept so a Refer can measure its scope
      // box with no geometry in the scene (cameraViews.js -> tileBounds.js;
      // since 2026-10-21): the descriptor's
      // whole-model boxes, the raw GlobalId -> expressID seed (the
      // guidIndex above drops GUIDs the manifest has no fragment for), each
      // element's placed geometries, and every geometry's unit-cube box.
      tileMetadata: isStreamed ? streamedTileMetadata(tileSet, streamedGuidSeed, streamedTiles, model) : null,
    });

    // Model parsed successfully - the empty-state hint no longer applies.
    canvasArea.querySelector(".viewer-empty-placeholder")?.remove();
    viewer.hasModel = true;
    // The DOM mirror of viewer.hasModel, for automation and for any CSS that
    // wants to style a loaded tile. It no longer gates the Unload button's
    // visibility (that button is always shown). Removed again by
    // unloadModelFromViewer.
    container.classList.add("has-model");

    // --- Step 2: Add model name label to UI ---
    let nameLabel = canvasArea.querySelector(".ifc-name-label");
    if (!nameLabel) {
      nameLabel = document.createElement("div");
      nameLabel.className = "ifc-name-label";
      canvasArea.appendChild(nameLabel);
    }
    nameLabel.textContent = file.name;
    syncDocumentTitle();

    // --- Step 3: Add model to scene and wait one frame ---
    world.scene.three.add(model);
    await new Promise((resolve) => requestAnimationFrame(resolve));

    // Neutral gray is the default viewer appearance - see applyBaseGrayColor's
    // own comment for why this replaced doing it on-demand via "Gray rest".
    applyBaseGrayColor(fragments);
    // A streamed model has no geometry in the scene yet - the culler only
    // fetches tiles once it knows where the camera is - so measuring the scene
    // here yields a nearly-empty box and parks the camera inside the building
    // (measured: a 104.8m fit on the parsed path collapsed to 22.4m streamed).
    // The tile set ships the real extents, computed offline by tileIfc.mjs
    // from every asset's placement, so the very first frame is already right.
    const modelBox = isStreamed
      ? (context.tileMetadata.buildingBox?.clone() ?? null)
      : computeModelBoundingBox(components, model);
    // The model is current whether or not it could be framed: `has-model` is
    // already set above, and applyView refuses a viewer whose current model
    // is missing (review, 2026-10-22).
    viewer.setCurrentModel(model);
    if (modelBox) {
      applyAutoClippingPlanes(world, modelBox);
      await fitCameraToWholeModel(world, modelBox);
    }

    // --- Step 4: Look up this file's highlight map, waiting for it to finish
    // loading (guidMapReady guards against uploading before the initial fetch
    // resolves). Keyed by content now, like everything else. ---
    await guidMapReady;
    const colorMap = getGuidMapFor(identity.key);

    if (colorMap && typeof colorMap === "object") {
      setViewerLoading(canvasArea, true, "Applying highlights…");
      log(`Color-GUID map for ${file.name}:`, colorMap);
      await highlightGUIDs(components, model, colorMap, file.name);
    } else {
      // Gated (2026-10-01): most models have no colour map, so this is the
      // normal case, not a warning worth a line on every load.
      log(`No highlight data for ${file.name} (key ${identity.key})`);
    }

    // --- Step 4.5: Fetch THIS model's recognized intent shard. One request
    // for one file (res/intents/<key>.json), instead of the whole corpus:
    // the previous store was a single 10.4MB res/intent_groups.json fetched
    // eagerly at page load for every session. Each intent carries a stable
    // per-CATEGORY colorIndex - not a baked hex, so it stays correct across a
    // light/dark toggle. See intentData.js and docs/architecture.md
    // "The shard". ---
    const intents = await loadIntentsForModel(identity.key);
    context.intents = intents;

    // ---- The model is now visible, correctly colored, and correctly
    // clipped - everything below this point is NOT required for that, only
    // for optional features (the inspector's Geometry row) or for
    // the filter panel/classification UI to populate. Reveal now instead of
    // making the user wait through it: hides the loading overlay here
    // (rather than only in `finally`, at the very end) so classification/
    // indexing/geometry reading run in the background while the user can
    // already see and orbit their model.
    setViewerLoading(canvasArea, false);

    // The inspector's "Geometry:" row reads each element's shape type from the
    // file text, which ThatOpen's properties leave out
    // (inspector/geometryLabels.js). Started after the model is visible and
    // run in a Worker, so nothing here waits for it. `buffer`/`arrayBuffer`
    // must not be read again after this call: it transfers (detaches) them,
    // which is why the content key is computed in Step 1, before this point.
    indexGeometry(model, buffer);

    // --- Step 5: Classify entities and spatial structures ---
    // byEntity() reads the FragmentsGroup's own `data` map (expressID -> [props,
    // [.., ifcType]]), which the streamed manifest carries just like a parsed
    // model does - so this works for both paths unchanged.
    classifier.byEntity(model);
    // process() derives the relations index by walking every property, which
    // a streamed model does not have locally. For that path the index was
    // already computed offline and handed to the indexer in tileSet.js, so
    // this step is skipped rather than made to fail.
    if (!isStreamed) {
      await indexer.process(model);
    }

    try {
      await classifier.bySpatialStructure(model, {
        isolate: new Set([WEBIFC.IFCBUILDINGSTOREY]),
      });
    } catch (e) {
      console.warn("Spatial classification skipped:", e.message);
    }

    // --- Step 6: Organize floors into classifier list ---
    if (!classifier.list.spatialStructures) classifier.list.spatialStructures = {};
    const storeys = classifier.find({ entities: ["IFCBUILDINGSTOREY"] });
    if (storeys?.length) {
      for (const storey of storeys) {
        classifier.list.spatialStructures[storey.name || `Storey ${storey.id}`] = storey;
      }
    }

    // --- Step 6.5: Refine the camera fit now that real classification data
    // exists - the Step 3 fit above ran before classifier.byEntity(model)
    // (deliberately, to not delay first reveal), so it had no way to know
    // whether this model has oversized site/terrain geometry to exclude. Only
    // re-fits if it actually would exclude something, so files without
    // IfcSite/IfcGeographicElement content never see this extra camera snap.
    // Skipped when streamed: the tile-set box used above ALREADY excludes
    // site/terrain (tileIfc.mjs applies the same exclusion offline), and
    // re-measuring here would regress the fit - computeBuildingBoundingBox can
    // only see the handful of fragments streamed in so far.
    const hasSiteContext =
      !isStreamed && CAMERA_FIT_EXCLUDED_CLASSES.some((name) => classifier.list.entities?.[name]);
    if (hasSiteContext) {
      const buildingBox = computeBuildingBoundingBox(components, classifier, model);
      if (buildingBox) {
        applyAutoClippingPlanes(world, buildingBox);
        await fitCameraToWholeModel(world, buildingBox);
      }
    }

    // --- Step 6.9: Keep progressively-streamed geometry consistent with what
    // the parsed path produces. A streamed model's fragments arrive in
    // batches, decided by the culler, long after the one-shot setup above ran -
    // so without this, geometry that streams in later keeps its authored IFC
    // colors (half the model gray, half not) and ignores the site/terrain
    // categories that start hidden. Both are re-applied per batch, scoped to
    // just the new fragments. ---
    if (isStreamed) {
      const streamer = components.get(OBCF.IfcStreamer);
      // A Refer on a streamed model is a two-step affair (handled
      // since 2026-10-21): the scope box comes from the tile
      // metadata, the camera moves, and only THEN does the culler fetch the
      // tiles under the new view - after the highlight already ran over
      // whatever was resident. So whenever a batch carries one of the active
      // Refer's members, the Refer is applied again (visualizeIntentGroups,
      // whose referByGuids clears the camera scope on its way in - restored
      // here, the camera itself is not moved). Through the viewer's work
      // queue, like the panel's own Refer / Clear (viewerRegistry.js,
      // enqueueViewerWork): the active Refer is read when the task RUNS, so
      // a click that came in while a batch waited is what gets painted, and
      // a Clear that came in is never painted over.
      const reapplyStreamedRefer = async (newFragments) => {
        const active = viewer.streamedRefer;
        if (!active || !newFragments?.length) return;
        const guidToLocation = await resolveGuidIndex(model);
        const expressIDs = active.guids.map((guid) => guidToLocation.get(guid)?.expressID).filter((id) => id !== undefined);
        if (!expressIDs.length) return;
        const fragMap = model.getFragmentMap(expressIDs);
        if (!newFragments.some((fragment) => fragment.id in fragMap)) return;
        if (viewer.streamedRefer !== active) return;
        const scope = getCameraScope(world);
        await visualizeIntentGroups(components, model, world, [active.intent], active.fileName);
        if (viewer.streamedRefer !== active) return;
        if (scope) setCameraScope(world, scope);
        // referByGuids cleared the scope on its way in, which told the refer
        // lines (views/referLines.js) to clear; restoring the scope does not
        // redraw them, and `intent-refer-complete` must not be re-sent (the
        // drivers count it, and the automation contract is additive-only). A
        // separate event, so the lines come back with the highlight.
        container.dispatchEvent(
          new CustomEvent("intent-refer-reapplied", { bubbles: true, detail: { intentId: active.intent.id } }),
        );
      };
      const onStreamedFragments = (newFragments) => {
        applyBaseGrayToFragments(newFragments);
        enqueueViewerWork(viewer, () => reapplyStreamedRefer(newFragments)).catch((err) => {
          console.warn("Refer: could not re-apply to streamed geometry:", err?.message ?? err);
        });
        // Site/terrain starts hidden (see createViewerMenu's own comment on
        // why these categories are wired to a direct hider.set): re-assert it
        // for whatever just arrived, or terrain pops into view as it streams.
        for (const name of CAMERA_FIT_EXCLUDED_CLASSES) {
          if (!classifier.list.entities?.[name]) continue;
          const fragMap = classifier.find({ entities: [name] }) || {};
          hider.set(false, fragMap);
        }
      };
      streamer.onFragmentsLoaded.add(onStreamedFragments);
      viewer.stopStreamedFragmentWatch = () =>
        streamer.onFragmentsLoaded.remove(onStreamedFragments);

      // Load every geometry once and keep it (2026-10-26). The streamer's
      // culler fetches a geometry only when its box covers more than 50
      // pixels of an off-screen pass in which every box is opaque - so from
      // outside a whole building, small elements and everything behind the
      // outer walls never arrived: data/example_autcon.ifc showed 71 of
      // 2,425 meshes. This app ghosts the building and Refers inside it, so
      // it needs all of it. setStatic(ids, true, false) fetches each tile
      // once and keeps it out of culling: 2,425 meshes, the same triangles
      // as the parsed load, in 0.3 s - still without parsing the IFC.
      // After the handler above is attached, so these batches are coloured
      // and Referred like any other; not awaited, the panel need not wait.
      streamer.setStatic([...model.keyFragments.values()], true, false).catch((err) => {
        console.warn("Streaming: could not load the whole model:", err?.message ?? err);
      });
    }

    // --- Step 7: Initialize viewer-specific UI ---
    createViewerMenu({
      model,
      container,
      filterPanel,
      cameraPanel,
      classifier,
      hider,
      indexer,
      world,
    });
    createIntentPanel({
      components,
      model,
      world,
      intentPanel,
      fileKey: identity.key,
      fileName: file.name,
      file,
      intents,
    });
  } catch (e) {
    console.error("Bulk model load failed:", e);
    setViewerError(canvasArea, "Model could not be loaded: " + e.message);

    // A WASM-level trap (e.g. "memory access out of bounds" on malformed/
    // corrupt input) leaves the IfcLoader's underlying WEBIFC.IfcAPI instance
    // permanently unusable - verified empirically: every subsequent load
    // attempt into this same viewer fails too, even with a perfectly valid
    // file, with a DIFFERENT downstream error (GetIfcEntityList choking on
    // corrupted WASM state). Recover by resetting webIfc the same way
    // IfcLoader's own internal cleanUp() does after a normal unload.
    if (e instanceof WebAssembly.RuntimeError || e?.name === "RuntimeError") {
      const loader = components.get(OBC.IfcLoader);
      // The trap can leave WASM memory corrupted enough that even Dispose()
      // itself throws (confirmed empirically) - so its failure must NOT skip
      // replacing webIfc below, or the viewer stays stuck. Best-effort cleanup,
      // unconditional replacement.
      try {
        loader.webIfc?.Dispose();
      } catch (disposeErr) {
        console.warn(
          "⚠️ Could not cleanly dispose the crashed IFC engine (expected after a WASM trap):",
          disposeErr.message,
        );
      }
      loader.webIfc = new WEBIFC.IfcAPI();
      console.warn(
        "⚠️ Recovered from a WASM crash by resetting this viewer's IFC engine - please retry the upload.",
      );
    }
  } finally {
    setViewerLoading(canvasArea, false);
  }
}

// ======== First Viewer Auto-Setup on Load ========
// setupViewer() is async (WASM/GPU init - real wall-clock time, not
// instant), and this fires it without awaiting. Previously nothing else
// waited on it either: handleIncomingFiles read viewerData immediately on the
// first upload, so a user fast enough to pick a file before this promise
// resolved found viewerData still empty and had createViewer() spin up a
// SECOND container for that file - then, once this original viewerContainer1
// setup finally finished, it got pushed in after that stray one. Every later
// upload's "first empty viewer" search then hit viewerContainer1 before the
// stray container, so the next file landed in the big, visually-first tile
// instead of a new one - looking exactly like a replace. firstViewerReady
// (awaited at the top of handleIncomingFiles) closes that window.
const firstViewerReady =
  viewerData.length === 0
    ? setupViewer({ id: "viewerContainer1", lookAt: DEFAULT_LOOK_AT }).then((data) => {
        viewerData.push(data);
        applySingleViewerLayout();
      })
    : Promise.resolve();

// ======== Dev performance HUD (?hud) ========
// Lazy: the module is only fetched when asked for.
if (new URLSearchParams(location.search).has("hud")) {
  import("./hud.js")
    .then(({ startHud }) => startHud())
    .catch((err) => console.warn("⚠️ HUD failed to start:", err.message));
}

// ======== Initialize BIM UI Manager ========
// Initializes the BIM UI Manager from @thatopen/ui library
BUI.Manager.init();
