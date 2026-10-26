// ======== Per-Viewer Filter Panel (Floors + Categories + GUID) and Camera Panel ========
// Populates the docked filter panel and the full-span camera strip for one
// viewer's model. Each viewer gets its own panels and its own classifier/
// hider/indexer, so there's no shared state across viewers here - unlike the
// old floating popover, whose visibility logic queried checkboxes page-wide
// (see updateVisibility below).
//
// Extracted from ThatOpenCompanyLoader.js. The one
// non-mechanical change: the GUID section's Clear handler now asks
// viewerModel.js for this model's key instead of re-deriving one from the
// file name - see getModelKey().

import * as BUI from "@thatopen/ui";
import * as THREE from "three";

import { CAMERA_FIT_EXCLUDED_CLASSES, VIEW_PRESETS, toggleProjection } from "../cameraViews.js";
import {
  clearReferForViewer,
  getGuidMapFor,
  grayOutExceptGuids,
  highlightGUIDs,
  referByGuids,
} from "../highlighting.js";
import { getModelKey } from "../viewerModel.js";
import { iconSvg } from "../icons.js";
import { log } from "../debug.js";
import { enqueueViewerWork, findViewerByWorld, getCameraScope, getLastViewRecord } from "../viewerRegistry.js";
import { applyView, captureViewRecord, replayViewRecord } from "../views/applyView.js";
import { currentViewToBcfXml } from "../views/bcfExport.js";
import { downloadStamp, downloadTextFile, modelStem } from "../snapshot.js";
import { getSetting, setSetting } from "../settings.js";
import {
  azimuthDegFromThetaRad,
  elevationDegFromPolarRad,
  polarRadFromElevationDeg,
  thetaRadFromAzimuthDeg,
} from "../views/direction.js";
import { deleteSavedView, listSavedViews, saveView } from "../views/viewStore.js";

/** The browser preference the camera panel's Meta switch toggles (settings.js, `bi2m:` prefix). */
export const SNAPSHOT_METADATA_SETTING = "snapshotMetadata";
export const snapshotMetadataOn = () => getSetting(SNAPSHOT_METADATA_SETTING) === "1";

/** "Ground Floor 2!" -> "ground-floor-2" (snapshot.js's rule), capped. */
const slugify = (text) =>
  String(text ?? "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48)
    .replace(/-+$/g, "");

// ======== Bulk checkbox toggle (Select All / None per section) ========
// updateVisibility() below reads the "checked" ATTRIBUTE (via hasAttribute),
// not the live DOM property, so bulk-toggling has to write that same attribute
// to stay consistent with it. Callers recompute visibility ONCE after the bulk
// change instead of once per checkbox - flipping 8 checkboxes previously meant
// 8 full DOM rescans + fragment-map rebuilds for a single logical action.
function setSectionChecked(sectionEl, checked) {
  sectionEl.querySelectorAll("bim-checkbox").forEach((cb) => {
    if (checked) cb.setAttribute("checked", "");
    else cb.removeAttribute("checked");
  });
}

function addBulkToggleButtons(sectionEl, onSetAll) {
  const wrapper = document.createElement("div");
  wrapper.className = "section-bulk-toggle";

  const allBtn = document.createElement("button");
  allBtn.type = "button";
  allBtn.textContent = "All";
  allBtn.className = "bulk-toggle-btn";
  allBtn.addEventListener("click", () => onSetAll(true));

  const noneBtn = document.createElement("button");
  noneBtn.type = "button";
  noneBtn.textContent = "None";
  noneBtn.className = "bulk-toggle-btn";
  noneBtn.addEventListener("click", () => onSetAll(false));

  wrapper.append(allBtn, noneBtn);
  sectionEl.prepend(wrapper);
}

// Recomputes and applies floor/category visibility for ONE viewer's model.
// Scoped to that viewer's own `container` - critical, since two viewers very
// commonly share floor/category names ("Floor 0", "IFCWALL", ...). Querying
// checkboxes page-wide (the old behavior) meant toggling a box in one
// viewer's panel could pick up checked/unchecked state from an identically-
// labeled checkbox in a DIFFERENT viewer's panel, silently showing/hiding
// the wrong elements.
export function updateVisibility({ container, model, classifier, hider, indexer }) {
  if (!model || !classifier || !hider || !indexer) {
    console.warn("❗ Missing required components for updateVisibility");
    return;
  }

  const activeFloors = new Set();
  const activeCategories = new Set();

  // Collect currently checked floor and category checkboxes - scoped to this
  // viewer's own container, not the whole page.
  container.querySelectorAll("bim-checkbox[label]").forEach((checkbox) => {
    const label = checkbox.getAttribute("label");
    const isChecked = checkbox.hasAttribute("checked");

    const isFloor = Object.hasOwn(classifier.list.spatialStructures ?? {}, label);
    const isCategory = Object.hasOwn(classifier.list.entities ?? {}, label);

    if (isChecked) {
      if (isFloor) activeFloors.add(label);
      if (isCategory) activeCategories.add(label);
    }
  });

  const floorCategoryIDs = new Set();

  // If either set is empty, hide everything
  if (activeFloors.size === 0 || activeCategories.size === 0) {
    // OBC.Hider has no clear() method - set(false) with no items hides everything.
    hider.set(false);
    log("🚫 No active floor or category selections. All hidden.");
    return;
  }

  // Loop through all selected floors
  for (const floorName of activeFloors) {
    const floor = classifier.list.spatialStructures[floorName];
    if (!floor || floor.id == null) continue;

    // Set<number> of expressIDs - matches classifier.find()'s output below.
    const floorChildren = indexer.getEntityChildren(model, floor.id);

    // For each floor, filter only category items.
    // NOTE: classifier.find() returns a FragmentIdMap ({fragmentID: Set<expressID>}),
    // not a list of {id}-shaped elements - the previous version assumed the latter
    // and threw "categoryElements is not iterable" the moment both a floor and a
    // category were active at once (i.e. on first real use with a loaded model).
    for (const categoryName of activeCategories) {
      const categoryFragmentMap = classifier.find({ entities: [categoryName] }) || {};

      for (const expressIDs of Object.values(categoryFragmentMap)) {
        for (const expressID of expressIDs) {
          if (floorChildren.has(expressID)) {
            floorCategoryIDs.add(expressID);
          }
        }
      }
    }
  }

  log(
    `✅ Showing ${floorCategoryIDs.size} elements in intersection of selected floors and categories.`,
  );

  // isolate() hides everything else and shows only fragMap - the real OBC.Hider
  // equivalent of the old (nonexistent) clear() + set("name", fragMap) pair.
  const fragMap = model.getFragmentMap(Array.from(floorCategoryIDs));
  hider.isolate(fragMap);
}

export function createViewerMenu({
  model,
  container,
  filterPanel,
  cameraPanel,
  classifier,
  hider,
  indexer,
  world,
}) {
  filterPanel.innerHTML = "";

  const inner = document.createElement("div");
  inner.className = "viewer-filter-panel-inner";
  filterPanel.appendChild(inner);

  const floorSection = document.createElement("div");
  floorSection.className = "viewer-filter-section";
  floorSection.innerHTML = `<h3 class="viewer-filter-heading">Floors</h3>`;
  inner.appendChild(floorSection);

  const spatialStructures = classifier.list.spatialStructures;
  const storeyNames = Object.keys(spatialStructures);

  for (const name of storeyNames) {
    const checkbox = BUI.Component.create(
      () => BUI.html`
        <bim-checkbox checked label="${name}"
          @change="${() => updateVisibility({ container, model, classifier, hider, indexer })}">
        </bim-checkbox>
      `,
    );
    floorSection.append(checkbox);
  }

  const categorySection = document.createElement("div");
  categorySection.className = "viewer-filter-section";
  categorySection.innerHTML = `<h3 class="viewer-filter-heading">Categories</h3>`;
  inner.appendChild(categorySection);

  const classNames = Object.keys(classifier.list.entities || {});

  for (const name of classNames) {
    // IfcSite/IfcGeographicElement (terrain/topography - see
    // computeBuildingBoundingBox's comment on why the camera fit excludes
    // these) start unchecked and hidden by default - on a real test file
    // one of these was ~2x the building's own footprint in each direction
    // and made "see the whole building" impossible regardless of camera
    // distance, since it's still rendered even when the camera ignores it
    // for framing purposes. Toggled independently of the shared
    // updateVisibility()/floor-intersection logic below (a direct
    // hider.set on just this category) rather than going through
    // updateVisibility - these elements routinely aren't children of any
    // IfcBuildingStorey, so the floor-AND-category intersection that
    // updateVisibility relies on could never show them again once checked.
    const isSiteContext = CAMERA_FIT_EXCLUDED_CLASSES.includes(name);
    const checkbox = BUI.Component.create(
      () => BUI.html`
        <bim-checkbox ?checked="${!isSiteContext}" label="${name}"
          @change="${(e) => {
            if (isSiteContext) {
              const fragMap = classifier.find({ entities: [name] }) || {};
              hider.set(e.target.hasAttribute("checked"), fragMap);
            } else {
              updateVisibility({ container, model, classifier, hider, indexer });
            }
          }}">
        </bim-checkbox>
      `,
    );
    categorySection.append(checkbox);
    if (isSiteContext) hider.set(false, classifier.find({ entities: [name] }) || {});
  }

  addBulkToggleButtons(floorSection, (checked) => {
    setSectionChecked(floorSection, checked);
    updateVisibility({ container, model, classifier, hider, indexer });
  });
  addBulkToggleButtons(categorySection, (checked) => {
    setSectionChecked(categorySection, checked);
    updateVisibility({ container, model, classifier, hider, indexer });
  });

  // ---- GUID refer / gray-out: paste a GUID list, then either hide
  // everything else (Refer) or keep it visible but recolor it to a neutral
  // gray as spatial context (Gray rest). Both read the same textarea and
  // are independent of the Floors/Categories checkboxes above - either one
  // overrides whatever those currently show; Clear returns to the checkboxes'
  // current selection (re-running updateVisibility(), the same call their own
  // @change handlers make) AND removes any gray-out styling. No shared "mode"
  // state is tracked - toggling a checkbox while GUID refer/gray-out is
  // active simply overrides it too, same as any other hider/highlighter call.
  const guidSection = document.createElement("div");
  guidSection.className = "viewer-filter-section viewer-guid-section";
  guidSection.innerHTML = `
    <h3 class="viewer-filter-heading">Refer by GUID</h3>
    <textarea class="viewer-guid-textarea" rows="3" aria-label="GlobalIds to refer"
      placeholder="Paste GlobalIds - one per line or comma-separated"></textarea>
    <div class="viewer-guid-actions">
      <button type="button" class="bulk-toggle-btn viewer-guid-refer-btn">Refer</button>
      <button type="button" class="bulk-toggle-btn viewer-guid-gray-btn">Gray rest</button>
      <button type="button" class="bulk-toggle-btn viewer-guid-clear-btn">Clear</button>
    </div>
    <div class="viewer-guid-status"></div>
  `;
  inner.appendChild(guidSection);

  const guidTextarea = guidSection.querySelector(".viewer-guid-textarea");
  const guidStatus = guidSection.querySelector(".viewer-guid-status");

  function readGuidList() {
    return guidTextarea.value
      .split(/[\s,]+/)
      .map((s) => s.trim())
      .filter(Boolean);
  }

  // Every paint or clear here runs through the viewer's work queue, after
  // whatever the intent panel or the loader's streamed-batch re-apply is
  // doing (viewerRegistry.js, enqueueViewerWork), and drops the intent
  // panel's streamed Refer registration first: a hand-pasted GUID Refer is a
  // manual tool and is not re-applied as tiles stream in, and the batch
  // watch must not paint the previous intent back over it (review,
  // 2026-10-22).
  const queued = (task) => {
    const entry = findViewerByWorld(world);
    if (!entry) return task();
    entry.streamedRefer = null;
    return enqueueViewerWork(entry, task);
  };

  guidSection.querySelector(".viewer-guid-refer-btn").addEventListener("click", async () => {
    const guidList = readGuidList();
    if (guidList.length === 0) {
      guidStatus.textContent = "Paste at least one GUID first.";
      return;
    }
    guidStatus.textContent = "Referring…";
    const { matchedCount, totalCount, unmatched } = await queued(() => referByGuids(model, world, guidList));
    guidStatus.textContent =
      matchedCount === totalCount
        ? `${matchedCount} of ${totalCount} GUID(s) found and referred.`
        : `${matchedCount} of ${totalCount} GUID(s) found (${unmatched.length} not in this model).`;
  });

  guidSection.querySelector(".viewer-guid-gray-btn").addEventListener("click", async () => {
    const guidList = readGuidList();
    if (guidList.length === 0) {
      guidStatus.textContent = "Paste at least one GUID first.";
      return;
    }
    guidStatus.textContent = "Applying context gray…";
    const { matchedCount, totalCount, unmatched } = await queued(() =>
      grayOutExceptGuids(world.components, model, guidList),
    );
    guidStatus.textContent =
      matchedCount === totalCount
        ? `${matchedCount} of ${totalCount} GUID(s) found; the rest are grayed out.`
        : `${matchedCount} of ${totalCount} GUID(s) found (${unmatched.length} not in this model); the rest are grayed out.`;
  });

  guidSection.querySelector(".viewer-guid-clear-btn").addEventListener("click", async () => {
    guidStatus.textContent = "";
    await queued(() => clearReferForViewer(world));
    updateVisibility({ container, model, classifier, hider, indexer });
    // Gray rest only ever CLEARS highlighter styles (see
    // grayOutExceptGuids) - it never paints its own gray layer, since gray is
    // already the base material. Undoing it means restoring whatever color
    // highlighting this model's map_visualization.json entry specifies, if
    // any - the base gray underneath was never touched either way.
    const colorMap = getGuidMapFor(getModelKey(model));
    if (colorMap) {
      highlightGUIDs(world.components, model, colorMap, model.name);
    }
  });

  // ---- Camera: view presets, Orthographic/Perspective toggle, saved views ----
  // Lives in the .viewer-camera-panel (toggled by the bottom-right camera
  // icon), not the docked right-side filter panel. Rows, top to bottom
  // (layout decided by the owner 2026-09-23, amended 2026-10-01): the two
  // whole-building presets; the two cycling switchers (elevation view,
  // projection); THREE NUMBER INPUTS on one line - elevation, azimuth,
  // distance (zoom in orthographic) - each a readout you can also type into or
  // step with its spinner; a status line; saved views; and the bottom row - the view-name input, a BCF button, an
  // archive-glyph Save button, and room at its right end for TWO canvas-corner
  // buttons that complete the row, Snapshot then the camera toggle. Neither is
  // a child of this panel: both stay at one fixed corner position whether the
  // panel is open or shut (ThatOpenCompanyLoader.js), and the panel reaches
  // down to line up with them (see .viewer-camera-panel in style.css).
  // Snapshot reads the view-name input for the downloaded file's name, which
  // is why that box is its neighbour.
  //
  // Gone on 2026-10-01 at the owner's request: the Context slider (context is
  // a view-spec parameter now, and Refer's default), the frame select, the
  // View-JSON box with Apply / Copy / Export - scripts apply specs through
  // views/applyView.js directly - and an "Auto view on Refer"
  // opt-in (the rule views of views/rules.js serve the batch driver only).
  // The BCF export stayed.
  // world.camera is an OBC.OrthoPerspectiveCamera - .three always points at
  // whichever of .threePersp/.threeOrtho is currently active.
  const camera = world.camera;
  cameraPanel.innerHTML = "";
  const cameraInner = document.createElement("div");
  cameraInner.className = "viewer-camera-panel-inner";
  cameraInner.innerHTML = `
    <div class="viewer-camera-actions viewer-camera-row">
      <button type="button" class="bulk-toggle-btn viewer-fit-max-btn" title="Top view of the whole building">Top</button>
      <button type="button" class="bulk-toggle-btn viewer-side-view-btn" title="Side view of the whole building, 45° up">Side 45°</button>
    </div>
    <div class="viewer-camera-actions viewer-camera-row">
      <button type="button" class="bulk-toggle-btn viewer-elevation-view-btn"
              title="Applies the view named on the button, then advances: Front → Back → Left → Right">Front</button>
      <button type="button" class="bulk-toggle-btn viewer-projection-toggle-btn" title="Switch to orthographic projection">Ortho</button>
    </div>
    <div class="viewer-camera-readout-row viewer-camera-readouts">
      <label class="viewer-camera-readout" title="Degrees above horizontal: 90 is a plan view, negative looks up. Type or step to orbit">
        <span>Elevation</span>
        <input type="number" class="viewer-camera-angle-value" step="1" min="-90" max="90" />
      </label>
      <label class="viewer-camera-readout" title="Horizontal direction the camera looks from: 0 = front (+Z), 90 = right (+X). Type or step to orbit">
        <span>Azimuth</span>
        <input type="number" class="viewer-camera-azimuth-value" step="1" min="-1" max="360" />
      </label>
      <label class="viewer-camera-readout" title="Camera distance to the target in metres (the zoom factor in orthographic). Type or step to dolly">
        <span class="viewer-camera-distance-label">Distance</span>
        <input type="number" class="viewer-camera-distance-value" step="1" min="0" />
      </label>
    </div>
    <div class="viewer-view-status" aria-live="polite"></div>
    <div class="viewer-saved-views-list"></div>
    <div class="viewer-camera-bottom-row">
      <input type="text" class="viewer-view-name-input" placeholder="View name" aria-label="View name" />
      <button type="button" class="viewer-icon-btn viewer-snapshot-meta-btn" title="Snapshot metadata: also export the selected and visible GUIDs as JSON beside the PNG" aria-label="Snapshot metadata" aria-pressed="${snapshotMetadataOn() ? "true" : "false"}">Meta</button>
      <button type="button" class="viewer-icon-btn viewer-view-bcf-btn" title="Download the current view as a BCF viewpoint (.bcfv)" aria-label="BCF">BCF</button>
      <button type="button" class="viewer-icon-btn viewer-save-view-btn" title="Save" aria-label="Save">${iconSvg("archive")}</button>
    </div>
  `;
  cameraPanel.appendChild(cameraInner);

  // Live readouts, each an <input type="number"> (owner's layout, 2026-10-01):
  // the value shows where the camera is, typing or stepping it moves the
  // camera there. Elevation is camera-controls' polarAngle converted to
  // degrees above horizontal; azimuth is its azimuthAngle wrapped to [0, 360)
  // (views/direction.js - theta accumulates whole turns); distance is the
  // controls' own camera-to-target distance in metres, or the orthographic
  // zoom factor, because controls.distance is meaningless in orthographic and
  // actively misleading there (OBC's setOrthoCamera()
  // pins it to a literal 200). Updates come off camera-controls' own 'update'
  // event (every orbit/pan/zoom/dolly/fit - not a polling loop), and skip an
  // input the user is typing in.
  const angleValueEl = cameraInner.querySelector(".viewer-camera-angle-value");
  const azimuthValueEl = cameraInner.querySelector(".viewer-camera-azimuth-value");
  const distanceValueEl = cameraInner.querySelector(".viewer-camera-distance-value");
  const distanceLabelEl = cameraInner.querySelector(".viewer-camera-distance-label");
  const typing = (el) => document.activeElement === el;
  const fmt = (n, digits) => String(Math.round(n * 10 ** digits) / 10 ** digits);
  function updateCameraAngleReadout() {
    if (!typing(angleValueEl)) angleValueEl.value = fmt(elevationDegFromPolarRad(camera.controls.polarAngle), 1);
    if (!typing(azimuthValueEl)) azimuthValueEl.value = fmt(azimuthDegFromThetaRad(camera.controls.azimuthAngle), 1);
    if (camera.projection.current === "Orthographic") {
      distanceLabelEl.textContent = "Zoom";
      distanceValueEl.step = "0.1";
      if (!typing(distanceValueEl)) distanceValueEl.value = fmt(camera.three.zoom, 2);
    } else {
      distanceLabelEl.textContent = "Distance";
      distanceValueEl.step = "1";
      if (!typing(distanceValueEl)) distanceValueEl.value = fmt(camera.controls.distance, 1);
    }
  }
  camera.controls.addEventListener("update", updateCameraAngleReadout);
  updateCameraAngleReadout();

  // Typing or stepping a readout moves the camera - a pure orbit or dolly,
  // no re-fit, so a hand-framed view keeps everything else. Animated like
  // saved-view recall; the readout follows the motion through 'update'.
  const numberOf = (el) => {
    const n = Number(el.value);
    return Number.isFinite(n) ? n : null;
  };
  angleValueEl.addEventListener("change", async () => {
    const v = numberOf(angleValueEl);
    if (v === null) return;
    await camera.controls.rotatePolarTo(polarRadFromElevationDeg(THREE.MathUtils.clamp(v, -90, 90)), true);
    angleValueEl.blur();
  });
  azimuthValueEl.addEventListener("change", async () => {
    const v = numberOf(azimuthValueEl);
    if (v === null) return;
    // Wraps, so stepping past 359 lands on 0 and below 0 on 359.
    await camera.controls.rotateAzimuthTo(thetaRadFromAzimuthDeg(v), true);
    azimuthValueEl.blur();
  });
  distanceValueEl.addEventListener("change", async () => {
    const v = numberOf(distanceValueEl);
    if (v === null || v <= 0) return;
    if (camera.projection.current === "Orthographic") {
      await camera.controls.zoomTo(v, true);
    } else {
      await camera.controls.dollyTo(
        THREE.MathUtils.clamp(v, camera.controls.minDistance, camera.controls.maxDistance),
        true,
      );
    }
    distanceValueEl.blur();
  });

  // One line for messages: what a view resolved to, why one was refused,
  // what the BCF export did. Empty = hidden (style.css).
  const viewStatusEl = cameraInner.querySelector(".viewer-view-status");
  const showViewStatus = (text, isError = false) => {
    viewStatusEl.textContent = text;
    viewStatusEl.classList.toggle("is-error", isError);
  };
  const describeRecord = (record) => {
    const r = record.resolved;
    const scale = r.projection === "Orthographic" ? `${r.zoom.toFixed(2)}×` : `${r.distance.toFixed(1)} m`;
    const frame = r.frame.kind === "world" ? "" : ` · ${r.frame.kind} frame ${r.frame.yawDeg.toFixed(1)}° (${r.frame.source})`;
    const s = record.log?.scores;
    const scores = s
      ? ` · ${s.membersDistinct}/${s.membersTotal} members seen, fill ${(s.frameFill * 100).toFixed(1)}%`
      : "";
    const reso = r.resolution && !r.resolution.ok ? ` · tolerance ${r.resolution.toleranceM} m is ${r.resolution.pixels.toFixed(1)} px` : "";
    return `${record.label} → az ${r.worldAzimuthDeg.toFixed(1)}° el ${r.worldElevationDeg.toFixed(1)}° · ${scale}${frame}${scores}${reso}`;
  };
  const applySpec = async (spec, chosenBy, score = false) => {
    try {
      const record = await applyView(world, spec, { chosenBy, score });
      const problem = record.resolved.scope?.unmeasurable;
      showViewStatus(problem ?? (chosenBy === "preset" ? "" : describeRecord(record)), !!problem);
      return record;
    } catch (err) {
      showViewStatus(err?.message ?? String(err), true);
      return null;
    }
  };

  // Each preset frames the current scope from its own angle. Since
  // 2026-10-01 a preset is a VIEW SPEC (views/applyView.js): a direction from
  // VIEW_PRESETS (cameraViews.js, derived from the offset constants), framing
  // whatever scope is current - exactly the two calls this used to make by
  // hand, fitCameraToScope against the Refer's own snapshot of the building
  // box when a scope exists, fitCameraToWholeModel otherwise; scripts/e2e/
  // views.py pins the poses to the pre-change baseline.
  const applyPreset = (name) => applySpec({ direction: VIEW_PRESETS[name] }, "preset");
  const fitFromButton = (selector, preset) => {
    cameraInner.querySelector(selector).addEventListener("click", () => applyPreset(preset));
  };
  // "Top" (Top until 2026-09-23) - a true top (plan) view of the whole building, not
  // the shallower aerial angle auto-framing/Reset use.
  fitFromButton(".viewer-fit-max-btn", "top");
  // "Side 45°" - same whole-model framing, shallower/elevation-like.
  fitFromButton(".viewer-side-view-btn", "side45");
  // Front/Back/Left/Right - level (non-diagonal) elevation views along the
  // world X/Z axes; see the offsets' own comment in cameraViews.js for why
  // these have no architectural "facade" meaning. Because they are four
  // variants of ONE choice rather than four independent actions, they
  // collapse into a single cycling switcher, on exactly the contract the
  // projection toggle below already uses: the label names what the NEXT click
  // does, so clicking "Front" gives you the front view and the button then
  // offers "Back". Cheapest four-to-one width saving in this panel.
  const ELEVATION_VIEWS = [
    { label: "Front", preset: "front" },
    { label: "Back", preset: "back" },
    { label: "Left", preset: "left" },
    { label: "Right", preset: "right" },
  ];
  const elevationBtn = cameraInner.querySelector(".viewer-elevation-view-btn");
  let elevationIndex = 0;
  elevationBtn.addEventListener("click", async () => {
    // Read the preset BEFORE advancing: the label the user just clicked is
    // the view they asked for.
    const chosen = ELEVATION_VIEWS[elevationIndex];
    elevationIndex = (elevationIndex + 1) % ELEVATION_VIEWS.length;
    elevationBtn.textContent = ELEVATION_VIEWS[elevationIndex].label;
    await applyPreset(chosen.preset);
  });

  const viewNameInput = cameraInner.querySelector(".viewer-view-name-input");
  const projectionBtn = cameraInner.querySelector(".viewer-projection-toggle-btn");
  projectionBtn.addEventListener("click", async () => {
    // Not camera.projection.toggle(): that loses an orthographic zoom on the
    // way back and jumps the framing on the way out (cameraViews.js).
    await toggleProjection(world);
    // Label shows the action the NEXT click performs, not the current state
    // (short names since 2026-09-23; the tooltip carries the full word).
    const nextIsPersp = camera.projection.current === "Orthographic";
    projectionBtn.textContent = nextIsPersp ? "Persp" : "Ortho";
    projectionBtn.title = nextIsPersp
      ? "Switch to perspective projection"
      : "Switch to orthographic projection";
    // Explicit, not left to the controls' 'update' event: the readout swaps
    // between metres and a zoom factor across this toggle, and a projection
    // switch on its own need not move the camera.
    updateCameraAngleReadout();
  });

  // Meta (2026-10-22): the Snapshot button exports the picture's GUID
  // metadata beside the PNG while this is pressed (snapshot.js,
  // captureViewWithMetadata). A browser preference, not a per-model one, so
  // it survives a reload and applies to every tile; the Snapshot handler in
  // the loader reads it at click time.
  const metaBtn = cameraInner.querySelector(".viewer-snapshot-meta-btn");
  metaBtn.addEventListener("click", () => {
    const next = !snapshotMetadataOn();
    setSetting(SNAPSHOT_METADATA_SETTING, next ? "1" : "0");
    metaBtn.setAttribute("aria-pressed", next ? "true" : "false");
    showViewStatus(next ? "Snapshot exports GUID metadata." : "Snapshot exports the picture only.");
  });

  // BCF: the current view as a BCF viewpoint (views/bcfExport.js), named
  // after the view-name box, the last applied view, or "view"; the active
  // Refer's members are the viewpoint's selection.
  cameraInner.querySelector(".viewer-view-bcf-btn").addEventListener("click", async () => {
    const name = viewNameInput.value.trim() || getLastViewRecord(world)?.label || "view";
    try {
      const xml = await currentViewToBcfXml(world.components, world, {
        title: name,
        model,
        guids: getCameraScope(world)?.guids ?? [],
      });
      // Same shape as the snapshot name (2026-10-01): stem, view, stamp.
      downloadTextFile(
        `${modelStem(model)}-${slugify(name) || "view"}-${downloadStamp()}.bcfv`,
        xml,
        "application/xml",
      );
      showViewStatus("BCF viewpoint downloaded.");
    } catch (err) {
      showViewStatus(`BCF: ${err?.message ?? err}`, true);
    }
  });

  // Saved views: persisted per model (views/viewStore.js, under
  // bi2m:views:<content key>) as full view records, so they survive a reload
  // and carry projection, zoom, scope and frame - everything the old
  // `{pos, target}` closure state dropped. A fresh
  // createViewerMenu() call on every load re-reads the store for THAT model's
  // key, so another model's views never show here.
  const viewsList = cameraInner.querySelector(".viewer-saved-views-list");
  const savedFileKey = getModelKey(model) || "viewer";

  const renderSavedView = (saved) => {
    const row = document.createElement("div");
    row.className = "viewer-saved-view-row";
    row.dataset.viewId = saved.id;
    row.innerHTML = `
      <button type="button" class="viewer-saved-view-name"></button>
      <button type="button" class="viewer-saved-view-delete" title="Delete" aria-label="Delete">×</button>
    `;
    const nameBtn = row.querySelector(".viewer-saved-view-name");
    nameBtn.textContent = saved.name;
    nameBtn.title = saved.record?.label ? `${saved.record.label} · saved ${saved.savedAt?.slice(0, 16).replace("T", " ")}` : saved.name;
    nameBtn.addEventListener("click", async () => {
      // Awaited - the batch driver's constraint too: unawaited + animated (enableTransition
      // =true, unlike the preset buttons' instant fitCameraToWholeModel calls)
      // left the angle readout reading a stale mid-transition value for
      // ~1000ms after a click, confirmed directly. Awaiting here makes the
      // click resolve only once the transition has actually finished - but
      // that alone does NOT fix automation: a Playwright `.click()` returns as
      // soon as the click event dispatches, never waiting on a promise an
      // unawaited-from-the-outside handler happens to return. Same
      // observable-completion intent as the Refer button's `referStatus` is
      // the actual fix for a script.
      nameBtn.dataset.recallStatus = "pending";
      nameBtn.setAttribute("aria-busy", "true");
      try {
        // Exact pose replay: the same animated setLookAt as before, plus the
        // projection and orthographic zoom the record carries.
        await replayViewRecord(world, saved.record, { transition: true });
      } catch (err) {
        showViewStatus(`Saved view: ${err?.message ?? err}`, true);
      }
      nameBtn.dataset.recallStatus = "done";
      nameBtn.removeAttribute("aria-busy");
      nameBtn.dispatchEvent(
        new CustomEvent("saved-view-recall-complete", {
          bubbles: true,
          detail: { name: saved.name, id: saved.id },
        }),
      );
    });
    row.querySelector(".viewer-saved-view-delete").addEventListener("click", () => {
      deleteSavedView(savedFileKey, saved.id);
      row.remove();
    });
    viewsList.appendChild(row);
  };
  for (const saved of listSavedViews(savedFileKey)) renderSavedView(saved);

  cameraInner.querySelector(".viewer-save-view-btn").addEventListener("click", () => {
    // The camera as it is now - the user may have orbited since the last
    // applied view - under whatever spec was applied last, so the saved view
    // remembers its scope and frame as well as its pose.
    const record = captureViewRecord(world, { spec: getLastViewRecord(world)?.spec ?? null, chosenBy: "manual" });
    const saved = saveView(savedFileKey, { name: viewNameInput.value.trim(), record });
    viewNameInput.value = "";
    renderSavedView(saved);
  });
}
