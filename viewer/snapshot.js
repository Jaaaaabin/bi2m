// ======== Manual snapshot: one PNG of exactly what the viewer shows ========
// The hand-operated twin of scripts/autocamera.py. The
// batch driver walks the whole library from the outside with Playwright and
// writes <content_key>/snapshots/<view>.png into the vis directory; this
// takes ONE frame of ONE tile, on demand, from inside the page, and hands it
// to the browser as a download. Same subject, same framing rules, different
// operator - so the two stay describable as one feature.
//
// WHY THIS CAN'T JUST CALL toDataURL()
// The WebGL context is created WITHOUT `preserveDrawingBuffer` (the
// @thatopen SimpleRenderer default, confirmed live:
// getContextAttributes().preserveDrawingBuffer === false), and it stays
// that way on purpose - turning it on costs a full
// back-buffer copy on every composited frame, for every open tile, forever,
// to serve a button that is pressed once in a while. Without it the drawing
// buffer is cleared the moment the browser composites, so a bare
// `canvas.toDataURL()` reads back an empty frame. Measured on test_1.ifc:
// 25,930 characters for the cleared buffer against 88,946 for the same view
// re-rendered first, that canvas being 945 x 867. It is not
// blank-and-obvious - it is a valid, plausible, EMPTY png - which is exactly
// why this path is centralised here.
//
// The fix is to render and read in one synchronous block, before the browser
// gets a chance to composite: renderer.update() draws the frame,
// toDataURL() reads it back, and nothing may await between the two. That is
// the entire trick, and it is why capture() below has no `await` in it.
// `renderer.update()` rather than `renderer.three.render(...)` so this goes
// through the renderer's own draw path and cannot drift from what the tile
// normally shows.
//
// WHAT LANDS IN THE FILE
// Only the 3D render. Every overlay in the tile - the name label, the corner
// buttons, the docked panels - is DOM sitting ON TOP of the canvas, never
// drawn into it, so the capture excludes them for free. autocamera.py has to
// hide them by hand (its MASK_JS) because it photographs the page; this
// reads the canvas itself. The background is opaque without any compositing
// here: SimpleScene paints `scene.background`, which setupViewer keeps equal
// to the page background and re-syncs on every theme toggle, so a snapshot
// matches the theme it was taken in (measured: corner pixel #ffffff at
// alpha 255 in the light theme, despite the canvas element being transparent
// and the clear alpha being 0).
//
// Nothing here touches the camera. Re-rendering the frame is a read of the
// scene, not a move through it - the camera's semantics are
// untouched, and the pose is measurably identical before and after.

import { resolveGuidIndex } from "./highlighting.js";
import { getModelContext } from "./viewerModel.js";
import { captureViewRecord } from "./views/applyView.js";
import { frameToPngDataUrl, renderOffscreen } from "./views/render.js";
import { buildSnapshotMetadata } from "./views/snapshotMeta.js";
import { visibleElements } from "./views/visibility.js";

/** Longest slug taken from a user-typed view name, in characters. */
const MAX_SLUG = 48;

/**
 * Renders the current frame and reads it back as a PNG data URL.
 *
 * Synchronous ON PURPOSE - see the header. An `await` anywhere between the
 * render and the read hands control back to the browser, which composites,
 * which clears the drawing buffer, which silently produces an empty PNG.
 *
 * @param {object} world the viewer's @thatopen world
 * @returns {{dataUrl: string, width: number, height: number}}
 */
export function captureWorldPng(world) {
  const renderer = world.renderer;
  renderer.update();
  const canvas = renderer.three.domElement;
  return {
    dataUrl: canvas.toDataURL("image/png"),
    width: canvas.width,
    height: canvas.height,
  };
}

/**
 * The current view as a PNG: at the canvas's own size through captureWorldPng
 * above, or at a FIXED size through an offscreen render (views/render.js)
 * - same pose, a camera re-aspected to the requested
 * size, never touching the on-screen canvas. The fixed-size path has no
 * preserveDrawingBuffer concern at all: it reads a render target, not the
 * drawing buffer.
 *
 * @param {object} world
 * @param {{width: number, height: number, pixelRatio?: number} | null} [size]
 * @returns {{dataUrl: string, width: number, height: number}}
 */
export function captureViewerPng(world, size = null) {
  if (!size) return captureWorldPng(world);
  const frame = renderOffscreen(world, { width: size.width, height: size.height, pixelRatio: size.pixelRatio ?? 1 });
  return { dataUrl: frameToPngDataUrl(frame), width: frame.width, height: frame.height };
}

/** "Ground Floor 2!" -> "ground-floor-2"; "" -> "" (never a stray dash). */
function slugify(text) {
  return String(text ?? "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, MAX_SLUG)
    .replace(/-+$/g, "");
}

/** YYYYMMDD-HHMMSS in local time: sorts, and has nothing a file system rejects. */
export function downloadStamp(date = new Date()) {
  const p = (n) => String(n).padStart(2, "0");
  const ymd = `${date.getFullYear()}${p(date.getMonth() + 1)}${p(date.getDate())}`;
  return `${ymd}-${p(date.getHours())}${p(date.getMinutes())}${p(date.getSeconds())}`;
}

/** The model's file name without ".ifc" - the stem every download starts with. */
export function modelStem(model) {
  const name = getModelContext(model)?.fileName || "";
  return name.replace(/\.ifc$/i, "") || "viewer";
}

/**
 * The download's file name: "<model stem>-<view>-<YYYYMMDD-HHMMSS>.png".
 *
 * The model's own file name first (2026-10-01, owner's decision), so the PNG
 * reads in a Downloads folder without a lookup - the convention the verdicts
 * export already used. This reverses the 2026-09-23 key-first scheme: a
 * snapshot no longer carries the content key, so joining one back to a
 * renumbered library model is by name and date only.
 *
 * The middle part is whatever the user typed in the camera panel's view-name
 * box - the field right next to this button - so naming a view and
 * snapshotting it produce matching names; with the box empty it is just
 * "snapshot". The stamp keeps repeated captures apart without the browser's
 * "(1)" suffix.
 */
export function snapshotFileName(model, viewName, date = new Date()) {
  const slug = slugify(viewName) || "snapshot";
  return `${modelStem(model)}-${slug}-${downloadStamp(date)}.png`;
}

/** A data: URL to a Blob, without a round trip through fetch(). */
function dataUrlToBlob(dataUrl) {
  const bytes = atob(dataUrl.slice(dataUrl.indexOf(",") + 1));
  const buffer = new Uint8Array(bytes.length);
  for (let i = 0; i < bytes.length; i += 1) buffer[i] = bytes.charCodeAt(i);
  return new Blob([buffer], { type: "image/png" });
}

/**
 * Captures the tile's current render and downloads it as a PNG.
 *
 * A Blob and an object URL rather than putting the data: URL straight on the
 * anchor: a maximised tile on a large display encodes to several megabytes,
 * and a multi-megabyte data: URL is where browsers start quietly refusing
 * the download. The object URL is revoked on the next turn of the event
 * loop, once the click has been dispatched.
 *
 * @param {object} viewer
 * @param {string} viewName
 * @param {{width: number, height: number, pixelRatio?: number} | null} [size] -
 *   a fixed image size (offscreen render); omitted = the canvas as it is.
 * @returns {{fileName: string, width: number, height: number} | null} null
 *   when there is nothing to photograph (no model loaded), which the caller
 *   treats as "do nothing" - the same inert-with-no-model behaviour as the
 *   Unload button.
 */
export async function downloadViewerSnapshot(viewer, viewName, size = null, { metadata = false } = {}) {
  const shot = await captureViewWithMetadata(viewer, viewName, { size, metadata });
  if (!shot) return null;
  downloadBlob(shot.fileName, dataUrlToBlob(shot.dataUrl));
  if (shot.metadata) downloadTextFile(shot.metadataFileName, JSON.stringify(shot.metadata, null, 2));
  return { fileName: shot.fileName, width: shot.width, height: shot.height, metadataFileName: shot.metadata ? shot.metadataFileName : null };
}

// ======== Snapshot with metadata (2026-10-22) ========
// The picture plus the GUIDs it shows, as one function the Snapshot button
// consumes today and a batch driver (an export on every Refer, the next step)
// consumes without the downloads. With `metadata` off this is exactly the
// capture above. With it on: the model's GUID index is awaited FIRST, then
// the pose, the picture and the whole-model ID pass (views/visibility.js,
// visibleElements) run in one synchronous block, so all three describe the
// same frame; the document (views/snapshotMeta.js) is named like the PNG
// with `.json`. `selected` is what the viewer has referred as the subject:
// every non-context member of the scoped intent (roles member, base, top,
// intermediate: the judged elements), with its role-"context" members (a
// Neufert facet's related elements) in `selectedContext`; a pasted GUID
// list refers without a scope, so every split item is selected.
/** Default: one pixel of its own is enough for an element to count as visible. */
export const SNAPSHOT_MIN_PIXELS = 1;

export async function captureViewWithMetadata(viewer, viewName, { size = null, metadata = false, minPixels = SNAPSHOT_MIN_PIXELS } = {}) {
  if (!viewer?.hasModel) return null;
  const model = viewer.getCurrentModel?.();
  const world = viewer.world;
  const index = metadata ? await resolveGuidIndex(model) : null;
  // ---- synchronous from here: pose, picture and ID pass are one frame ----
  const fileName = snapshotFileName(model, viewName);
  const record = metadata ? captureViewRecord(world) : null; // settles the camera (controls.update(0)) first
  const { dataUrl, width, height } = captureViewerPng(world, size);
  let meta = null;
  if (metadata) {
    const pass = visibleElements(world, { index, width, height, minPixels });
    const context = getModelContext(model);
    const { selected, selectedContext } = selectedGuids(viewer, context, index);
    meta = buildSnapshotMetadata({
      fileKey: context?.key ?? null,
      isStreamed: !!context?.isStreamed,
      image: { file: fileName, width, height },
      pose: poseSummary(record),
      selected,
      selectedContext,
      visible: pass.visible,
      ghosted: pass.ghosted,
      minPixels,
      transparency: currentTransparency(),
      unresolved: pass.unresolved,
    });
  }
  return { fileName, dataUrl, width, height, metadata: meta, metadataFileName: fileName.replace(/\.png$/, ".json") };
}

/**
 * What is referred, by role. With an intent in the camera scope its members
 * split into non-context (member, base, top, intermediate: judged) and
 * "context" (the facet's related elements, painted base grey). Without one
 * (a pasted GUID list) every item the Refer split carries is selected and
 * nothing is context.
 */
function selectedGuids(viewer, modelContext, index) {
  const intentId = viewer.cameraScope?.intentId ?? null;
  const intent = intentId ? (modelContext?.intents ?? []).find((i) => i.id === intentId) : null;
  if (intent) {
    const members = intent.members.filter((m) => m.role !== "context").map((m) => m.guid);
    const context = intent.members.filter((m) => m.role === "context").map((m) => m.guid);
    return { selected: members, selectedContext: context };
  }
  const guids = new Set(viewer.cameraScope?.guids ?? []);
  const guidOf = new Map();
  for (const [guid, location] of index) guidOf.set(`${location.fragmentID}:${location.expressID}`, guid);
  for (const split of viewer.referSplits ?? []) {
    for (const itemID of split.itemIds) {
      const guid = guidOf.get(`${split.fragment.id}:${itemID}`);
      if (guid) guids.add(guid);
    }
  }
  return { selected: [...guids], selectedContext: [] };
}

/** The part of a view record a reader of the metadata needs to re-aim a camera. */
function poseSummary(record) {
  if (!record) return null;
  const r = record.resolved;
  return {
    intentId: record.intentId ?? null,
    position: r.position,
    target: r.target,
    worldDirection: r.worldDirection,
    distance: r.distance,
    worldAzimuthDeg: r.worldAzimuthDeg,
    worldElevationDeg: r.worldElevationDeg,
    projection: r.projection,
    fovDeg: r.fovDeg,
    zoom: r.zoom,
    halfHeightM: r.halfHeightM,
    canvas: r.canvas,
  };
}

/** The global transparency slider's value (0-100) at capture, or null without the slider. */
function currentTransparency() {
  const slider = document.getElementById("global-opacity-slider");
  const value = slider ? parseInt(slider.value, 10) : NaN;
  return Number.isFinite(value) ? value : null;
}

/** Hands a Blob to the browser as a download, revoking the object URL on the next turn. */
export function downloadBlob(fileName, blob) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

/** A text download (a Blob, not a data: URL, which browsers refuse past a few hundred KB). */
export function downloadTextFile(fileName, text, type = "application/json") {
  downloadBlob(fileName, new Blob([text], { type }));
}
