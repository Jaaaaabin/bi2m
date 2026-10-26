// ======== Viewer Registry ========
// The list of open viewers, and the one cross-viewer flag, in a module of
// their own so the pieces that need them (camera sync, transparency, refer/
// highlight teardown) can import them without importing the whole
// ThatOpenCompanyLoader.js orchestrator - which would be circular, since
// that file drives all of them.
//
// Deliberately a plain mutable array rather than an event emitter or store:
// this is exactly what it was as a module-level `const viewerData = []`
// before, and every reader already treats it as a live list. Extracting it
// changes where it lives, not how it behaves.

// Each entry is the object setupViewer() returns - see its `return` for the
// full shape (world, container, panels, fragments, classifier, hider,
// indexer, highlighter, teardown handles, hasModel, referSplits), plus two
// fields added lazily rather than at construction, both camera scope state
// and both accessed through the helpers below:
//   cameraScope  {guids, box, buildingBox, intentId?, spec?} - what is
//                currently framed instead of the whole building, or
//                null/absent for "the whole building". Set by the intent
//                panel's Refer, cleared by clearReferForViewer. buildingBox is
//                the snapshot taken when the scope was set, so the Context
//                slider and the view presets all frame against one
//                measurement. intentId (2026-10-01) names the referred intent
//                so a view spec scoped to it can reuse this measurement; spec
//                is the last view spec applied to this scope (views/applyView.js).
//   lastViewRecord  the record of the last view applied to this viewer
//                (views/applyView.js) - read by Save, Copy
//                and the batch driver through the accessors below.
//   cameraContext how much of the building the scoped fit keeps in frame, as a
//                blend from tight-on-the-intent (0) to whole-building (1). Absent
//                until the Context control moves it off its default.
export const viewerData = [];

// Monotonic counter for unique viewer container IDs - never decremented.
// viewerData.length is the source of truth for "how many are open."
let nextViewerIndex = 1;

export function nextViewerContainerId() {
  nextViewerIndex++;
  return `viewerContainer${nextViewerIndex}`;
}

export function findViewerByWorld(world) {
  return viewerData.find((entry) => entry.world === world);
}

export function findViewerById(id) {
  return viewerData.findIndex((entry) => entry.container.id === id);
}

// Whether camera movement in one viewer is broadcast to the others. Read
// every tick by the camera monitor, toggled by the sidebar button. A module
// -level boolean needs an accessor pair to stay live across an import
// boundary (importing the binding directly would read a snapshot in some
// bundler/TDZ situations, and can't be assigned from outside at all).
let syncCamera = false;

export const isCameraSyncEnabled = () => syncCamera;

export function toggleCameraSync() {
  syncCamera = !syncCamera;
  return syncCamera;
}

// ======== Camera Scope ========
// "view = (scope, direction, context)": the view-preset buttons supply the
// direction, and this is the scope they apply it to. Kept on the viewer entry
// next to referSplits - the same lifetime and the same clearing paths - rather
// than in the intent panel, because the CAMERA panel is the other reader.

export function setCameraScope(world, scope) {
  const entry = findViewerByWorld(world);
  if (!entry) return scope;
  entry.cameraScope = scope;
  // Emitted on the viewer container so the camera panel's Context control can
  // mirror a scope set (intent panel's Refer) or cleared (its Reset/Clear
  // Selection) from the other panel entirely. Both paths go through here,
  // which is why clearReferForViewer calls this rather than nulling the field.
  entry.container?.dispatchEvent(
    new CustomEvent("camera-scope-change", { bubbles: true, detail: { scope } }),
  );
  return scope;
}

/**
 * Runs `task` after every task queued on this viewer before it, whether or
 * not those succeeded, and returns its promise. Everything that paints or
 * clears a Refer goes through here - the intent panel's Refer / Show all /
 * Clear / Reset, and the loader's re-apply of a Refer to streamed batches -
 * so two fragment splits never run on one model at once and the LAST user
 * action is what ends up on screen (review, 2026-10-21).
 */
export function enqueueViewerWork(entry, task) {
  const run = () => task();
  entry.workChain = (entry.workChain ?? Promise.resolve()).then(run, run);
  return entry.workChain;
}

export function getCameraScope(world) {
  return findViewerByWorld(world)?.cameraScope ?? null;
}

export function setCameraContext(world, value) {
  const entry = findViewerByWorld(world);
  if (entry) entry.cameraContext = value;
  return value;
}

export function getCameraContext(world, fallback) {
  const stored = findViewerByWorld(world)?.cameraContext;
  return stored === undefined ? fallback : stored;
}

// ======== Last applied view (views/applyView.js) ========
// The record of the most recent applyView on this viewer. Kept here, next to
// the scope it was framed against, rather than in the views module, because
// the camera panel (Save, Copy), the intent panel (the Refer completion
// event) and the batch driver's hook all read it.

export function setLastViewRecord(world, record) {
  const entry = findViewerByWorld(world);
  if (entry) entry.lastViewRecord = record;
  return record;
}

export function getLastViewRecord(world) {
  return findViewerByWorld(world)?.lastViewRecord ?? null;
}
