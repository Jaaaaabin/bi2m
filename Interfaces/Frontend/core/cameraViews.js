// ======== Camera Framing, Clipping & View Presets ========
// Extracted verbatim from ThatOpenCompanyLoader.js - the
// bounding-box helpers, the per-model near/far derivation, the seven view-
// direction presets and the whole-model fit that consumes them. Behavior is
// unchanged; this is code motion, so the original comments (which record real
// findings about camera-controls' fitToBox/fitToSphere behavior and about
// oversized site geometry) move with the code they explain.

import * as OBC from "@thatopen/components";
import * as THREE from "three";

// resolveGuidIndex is the app's single entry point for GUID -> element
// resolution (see its comment in highlighting.js); it lives there because the
// index builder does, not because it is a highlighting concept. Importing it
// here is acyclic - highlighting.js imports viewerModel/transparency/
// viewerRegistry, never this module.
import { resolveGuidIndex } from "./highlighting.js";
import { anglesFromOffset } from "./views/direction.js";
import { boxOfTileAssets } from "./tileBounds.js";
import { getModelContext } from "./viewerModel.js";

// Shared bounding-box helper - OBC.BoundingBoxer is stateful/reusable across
// calls, so it's reset both before AND after use here, otherwise a later
// unrelated bbox calculation elsewhere would silently include this one.
// Returns null for an empty box instead of a THREE.Box3 that callers would
// have to isEmpty()-check themselves.
export function computeModelBoundingBox(components, model) {
  const boundingBoxer = components.get(OBC.BoundingBoxer);
  boundingBoxer.reset();
  boundingBoxer.add(model);
  const box = boundingBoxer.get();
  boundingBoxer.reset();
  return box.isEmpty() ? null : box;
}

// IfcSite/IfcGeographicElement (terrain/topography surfaces, routine in
// Revit IFC exports) can be many times larger than the actual building and
// swamp a whole-model bounding-box fit if included - confirmed on a real
// test file (data/test_2.ifc): a single IFCGEOGRAPHICELEMENT's own
// bounding-box diagonal was ~99% of the entire model's, on its own
// determining what should have been a "fit to the BUILDING" view (the
// actual walls/slabs/roof were only ~half that size). Excluded here so
// camera framing represents the building, not incidental site context.
// Needs classifier.byEntity(model) to have already run (Step 5 in
// loadMultiIFCIntoViewer, which happens after first reveal - see its own
// comment) - falls back to the raw whole-model box if nothing's classified
// yet, or if every classified category happens to be excluded.
export const CAMERA_FIT_EXCLUDED_CLASSES = ["IFCSITE", "IFCGEOGRAPHICELEMENT"];

export function computeBuildingBoundingBox(components, classifier, model) {
  // A streamed model has only the tiles the culler has fetched in the scene,
  // so BoundingBoxer would measure a fraction of the building; its tile set
  // shipped the real extents, computed offline (tileBounds.js).
  const tiles = getModelContext(model)?.tileMetadata;
  if (tiles) return tiles.buildingBox ? tiles.buildingBox.clone() : null;
  const entityNames = Object.keys(classifier.list.entities || {});
  const includedNames = entityNames.filter((name) => !CAMERA_FIT_EXCLUDED_CLASSES.includes(name));
  if (includedNames.length === 0) return computeModelBoundingBox(components, model);

  const combined = {};
  for (const name of includedNames) {
    const fragMap = classifier.find({ entities: [name] });
    if (!fragMap) continue;
    for (const [fragmentID, expressIDs] of Object.entries(fragMap)) {
      const set = combined[fragmentID] || (combined[fragmentID] = new Set());
      for (const id of expressIDs) set.add(id);
    }
  }

  const boundingBoxer = components.get(OBC.BoundingBoxer);
  boundingBoxer.reset();
  boundingBoxer.addFragmentIdMap(combined);
  const box = boundingBoxer.get();
  boundingBoxer.reset();
  return box.isEmpty() ? null : box;
}

// SimpleCamera/OrthoPerspectiveCamera default to a generic near/far tuned
// for nothing in particular (persp: 1-1000, ortho: 0.1-1000, both library
// defaults) - too tight a near plane clips into geometry on close zoom for a
// small model or element; too shallow a far plane could clip a very large
// federated model. Derives both from the loaded model's own bounding-box
// diagonal instead.
export function applyAutoClippingPlanes(world, box) {
  const diagonal = box.getSize(new THREE.Vector3()).length();
  const near = Math.max(0.01, diagonal / 1000);
  const far = Math.max(1000, diagonal * 10);

  // Both threePersp and threeOrtho need this, independent of which one is
  // currently active - the OrthoPerspectiveCamera swap keeps both alive
  // simultaneously so switching projection later doesn't reset clipping.
  for (const cam of [world.camera.threePersp, world.camera.threeOrtho]) {
    cam.near = near;
    cam.far = far;
    cam.updateProjectionMatrix();
  }
}

// Camera-angle presets for fitCameraToWholeModel below. `.normalize()` in the
// function itself means only the RATIO between components matters, not the
// scale used to write them here.
// - SIDE_VIEW_OFFSET: exactly 45 degrees above horizontal (Y component
//   equals the horizontal-plane magnitude, X/Z corner) - an
//   elevation/isometric look at the building from the side. It was briefly
//   the opening default on 2026-09-24; the opening pose is now
//   DEFAULT_VIEW_OFFSET below, a lower 20 degrees.
// - TOP_VIEW_OFFSET: steep aerial angle (~50 degrees above horizontal, same
//   X/Z corner) - the default until 2026-09-24. Nothing imports it now; kept
//   exported because it is the pose every reference measurement before that
//   date was taken at, and for anyone who wants the steeper aerial back.
// - PLAN_VIEW_OFFSET: literal straight down (pure +Y) - a true architectural
//   plan view, not an approximation of one. Safe to pass as-is despite
//   sitting exactly on the polar-angle singularity: camera-controls' own
//   `update()` loop calls `Spherical.makeSafe()` on every frame before
//   deriving camera position (confirmed in its source), which clamps phi
//   just off the pole - no NaN/degenerate roll, confirmed live.
// The default a model opens on was TOP_VIEW_OFFSET until 2026-09-24. It is
// SIDE_VIEW_OFFSET now, at the owner's request and because the measurement
// said the change is free. Six library models spanning 24-61 m in plan were
// framed at nine elevations from 30 degrees to straight down, and the share
// of the viewport the building actually covers moved only from 21.9% to
// 26.0% across that whole range - nothing clipped at any angle. Going from
// the old 49.7 degrees to 45 therefore costs 0.3 of a percentage point
// (23.9% -> 23.6%), which is nothing, and buys a view that shows two walls
// and a roof instead of a near-aerial one. Azimuth was swept too, at four
// corners: the means came out 23.6 / 23.6 / 24.8 / 24.2%, with a different
// corner winning on each model, so there is no generic best and the existing
// +X/+Z corner stays.
// Worth knowing before trying to improve this: the low coverage is NOT slack
// in the fit. Dollying in until the building's bounding-box corners sit at
// the frame edge made coverage WORSE on all six models (-2.6 points on
// average) - the box already nearly fills the frame, and the empty three
// quarters is space inside the box that the building's own sprawling shape
// does not occupy. No camera distance recovers it.
export const TOP_VIEW_OFFSET = new THREE.Vector3(0.6, 1, 0.6).normalize();
export const SIDE_VIEW_OFFSET = new THREE.Vector3(1, Math.SQRT2, 1).normalize();
export const PLAN_VIEW_OFFSET = new THREE.Vector3(0, 1, 0);

// The pose a model OPENS on: 20 degrees above horizontal at the same X/Z
// corner - someone standing across the street, not a drone. Its own constant
// rather than one of the presets above, because the presets are named things
// the user asks for and this is a default nobody asked for.
const OPENING_ELEVATION_DEG = 20;
const openingRad = THREE.MathUtils.degToRad(OPENING_ELEVATION_DEG);
export const DEFAULT_VIEW_OFFSET = new THREE.Vector3(
  Math.cos(openingRad) / Math.SQRT2,
  Math.sin(openingRad),
  Math.cos(openingRad) / Math.SQRT2,
).normalize();

// Vertical field of view for the perspective camera, in degrees. 38, not the
// 60 that OBC's OrthoPerspectiveCamera inherits from three.js and that
// nothing in this app had ever chosen: 60 vertical is 70 HORIZONTAL at a
// normal tile aspect, a 26 mm-equivalent lens, and no one photographs a
// building at 26 mm unless they are pressed against it - verticals splay and
// the near corner bulges. 38 is about a 45 mm equivalent, the range
// architectural exteriors are actually shot at.
// It is not a trade against framing, which is the surprising part: measured
// on four library models, narrowing the lens RAISED the share of the viewport
// the building fills, from 23.5% to 28.0% at a 45-degree view. fitToSphere
// dollies back to keep the angular size, so less foreshortening simply stops
// the far half of the building from shrinking. That gain is what pays for the
// lower opening angle: 38 degrees at 20 degrees elevation covers 23.7%, a
// shade MORE than the old 60-at-45 default's 23.5%.
export const DEFAULT_FOV = 38;
// FRONT/BACK/LEFT/RIGHT: pure horizontal (Y=0) elevation views along the
// model's own X/Z axes - IFC files carry no reliable "which way is the
// building's own front" convention this app can read, so these just name
// the four world-axis directions, not an architectural facade. Unlike
// PLAN_VIEW_OFFSET these sit at the spherical-coordinate EQUATOR (Y=0), not
// a pole, so they don't need makeSafe()'s pole-clamping at all; confirmed
// live (Playwright, data/test_3.ifc) that fitCameraToWholeModel resolves
// each to a stable, correctly-oriented level view with no NaN/degenerate
// roll - the "different edge case" gimbal concern the camera review
// flagged as unverified turned out not to apply to a level (as opposed to
// straight-up/down) axis-aligned offset.
export const FRONT_VIEW_OFFSET = new THREE.Vector3(0, 0, 1);
export const BACK_VIEW_OFFSET = new THREE.Vector3(0, 0, -1);
export const LEFT_VIEW_OFFSET = new THREE.Vector3(-1, 0, 0);
export const RIGHT_VIEW_OFFSET = new THREE.Vector3(1, 0, 0);

// The same presets as (azimuth, elevation) pairs - the `direction` of a view
// spec (views/viewSpec.js). DERIVED from the vectors above rather than typed
// in, so the two can never disagree: `top` is (0, 90) because a straight-down
// vector carries no azimuth and camera-controls reads theta 0 from it
// (views/direction.js, "the pole"); `side45` is (45, 45); the four level
// views are (0 / 180 / 270 / 90, 0). `opening` and `aerial` are here for
// completeness and for scripts; no button uses them.
export const VIEW_PRESETS = Object.freeze({
  top: Object.freeze(anglesFromOffset(PLAN_VIEW_OFFSET)),
  side45: Object.freeze(anglesFromOffset(SIDE_VIEW_OFFSET)),
  front: Object.freeze(anglesFromOffset(FRONT_VIEW_OFFSET)),
  back: Object.freeze(anglesFromOffset(BACK_VIEW_OFFSET)),
  left: Object.freeze(anglesFromOffset(LEFT_VIEW_OFFSET)),
  right: Object.freeze(anglesFromOffset(RIGHT_VIEW_OFFSET)),
  opening: Object.freeze(anglesFromOffset(DEFAULT_VIEW_OFFSET)),
  aerial: Object.freeze(anglesFromOffset(TOP_VIEW_OFFSET)),
});

// "Top"/"Side 45°": frames the WHOLE model from a chosen
// angle - replaces the old fixed DEFAULT_LOOK_AT pose, which had no idea how
// big the loaded model actually was or where it sat in world space (a small
// model looked like a lost speck; a large one could load mostly out of
// frame). Shared by (a) auto-framing right after a model loads, (b) the
// top-left "Reset camera view" button, and (c) the camera panel's own view
// buttons - (a) and (b) always use the default (SIDE_VIEW_OFFSET, a 45-degree
// angle) since a literal top-down first view reads as flat before the user
// has any other context on the model; the camera panel's own buttons each ask
// for a specific angle explicitly instead.
//
// Also sets the dolly (zoom) range from the model's own scale - this replaces
// the old FOV slider (removed: "how zoomed in the lens is" was a poor proxy
// for "how much of the building can I see", which is what people actually
// wanted control over). maxDistance keeps the user from dollying out past
// roughly "whole building fits" (with a little slack - fitToBox's own
// distance is the *tightest* possible fit, zero margin); minDistance caps the
// closest zoom at roughly room-scale. Both diagonal-relative, same approach
// as applyAutoClippingPlanes's near/far above.
/**
 * Switches projection while keeping the framing, in both directions.
 *
 * `camera.projection.toggle()` on its own loses half of what the user did.
 * Reproduced 2026-09-24: zoom to 5.16x in orthographic, switch back, and the
 * pan survives while the zoom is thrown away and the distance snaps to
 * whatever it was before you ever left perspective - so you land somewhere
 * that is neither where you started nor where you were looking.
 *
 * Two library facts behind that, both read out of the installed source:
 *
 *  - The two projections frame by different variables and nothing reconciles
 *    them. Perspective frames by `controls.distance`; `setOrthoCamera()` pins
 *    that to a hardcoded **200** and frames by `threeOrtho.zoom` instead, so a
 *    zoom done in orthographic lives only in `zoom`, which perspective never
 *    reads. There IS a `matchOrthoDistanceEnabled` flag that would convert it
 *    back, and it defaults to false.
 *  - That conversion would be wrong anyway. Both `getPerspectiveDims()` and
 *    `getDistance()` compute the frustum height as
 *    `2 * Math.atan(fov * Math.PI / 180 / 2)` where the trigonometry calls for
 *    `2 * Math.tan(...)`. At this app's 38-degree lens that makes the
 *    orthographic frustum ~7% too small - which is why the model visibly
 *    jumps larger the instant you switch to Ortho.
 *
 * So the conversion is done here instead, on one invariant: the world-space
 * half-height visible at the camera's target plane. Perspective expresses it
 * as `distance * tan(fov/2)`; orthographic as
 * `(top - bottom) / 2 / zoom`. Carrying that across the switch makes the
 * round trip lossless AND fixes the jump, because the zoom this sets
 * supersedes the frustum the library got wrong.
 *
 * The resulting distance is clamped to the controls' own min/max, so a wild
 * zoom-out in orthographic comes back to the edge of what perspective allows
 * rather than flying past it.
 */
export async function toggleProjection(world) {
  const camera = world.camera;
  const controls = camera.controls;
  const persp = camera.threePersp;
  const ortho = camera.threeOrtho;
  const halfFov = THREE.MathUtils.degToRad(persp.fov) / 2;
  const goingOrtho = camera.projection.current === "Perspective";

  // Measured BEFORE the switch: the library rewrites both cameras during it.
  const halfHeight = goingOrtho
    ? controls.distance * Math.tan(halfFov)
    : (ortho.top - ortho.bottom) / 2 / (ortho.zoom || 1);

  await camera.projection.toggle();

  if (!Number.isFinite(halfHeight) || halfHeight <= 0) return;
  if (goingOrtho) {
    const frustumHalfHeight = (ortho.top - ortho.bottom) / 2;
    if (frustumHalfHeight > 0) {
      // controls.zoomTo, NOT `ortho.zoom = …`. camera-controls owns the
      // orthographic zoom: it keeps its own `_zoom` and writes it onto the
      // camera in every `update()`, so a direct assignment survives exactly
      // until the next frame. Measured while building this: a plain
      // double-toggle came back 7% short (72.633 -> 67.543, the atan ratio
      // above), because the zoom set on the way out had already been
      // overwritten by the time the way back read it.
      await controls.zoomTo(frustumHalfHeight / halfHeight, false);
    }
  } else {
    const wanted = halfHeight / Math.tan(halfFov);
    if (Number.isFinite(wanted) && wanted > 0) {
      await controls.dollyTo(
        THREE.MathUtils.clamp(wanted, controls.minDistance, controls.maxDistance),
        false,
      );
    }
  }
}

export async function fitCameraToWholeModel(world, box, offsetDirection = DEFAULT_VIEW_OFFSET) {
  const controls = world.camera.controls;
  const center = box.getCenter(new THREE.Vector3());
  const diagonal = box.getSize(new THREE.Vector3()).length();

  // Reset to permissive limits first - a previous, differently-scaled model
  // loaded earlier into this same viewer could otherwise leave stale
  // min/maxDistance values that clamp the fit below for the new one.
  controls.minDistance = Number.EPSILON;
  controls.maxDistance = Infinity;

  // Sets the viewing DIRECTION only - the exact distance here doesn't
  // matter, fitToSphere() below recomputes it from the box itself.
  const aerialOffset = offsetDirection.clone().multiplyScalar(diagonal);
  const camPos = center.clone().add(aerialOffset);
  await controls.setLookAt(camPos.x, camPos.y, camPos.z, center.x, center.y, center.z, false);
  // fitToBox() is documented to snap the camera to the NEAREST WORLD AXIS,
  // discarding whatever direction setLookAt just established - confirmed
  // directly (both TOP_VIEW_OFFSET and SIDE_VIEW_OFFSET collapsed to a
  // pure straight-down or pure-horizontal view respectively, never the
  // intended diagonal angle, despite this function's own long-standing
  // comments claiming an "aerial 3/4 angle"). fitToSphere() has no axis to
  // snap to - a sphere is rotationally symmetric - so it just dollies along
  // whatever direction the camera is ALREADY facing, correctly preserving
  // the arbitrary diagonal angle set above. Slightly less tight a fit than
  // fitToBox for a very elongated building (worst case: as if it were a
  // sphere of radius = half the diagonal), an accepted trade-off for
  // actually honoring the requested viewing angle.
  await controls.fitToSphere(box.getBoundingSphere(new THREE.Sphere()), false);

  controls.maxDistance = controls.distance * 1.15;
  controls.minDistance = Math.max(0.5, diagonal / 30);
}

// ======== Scoped Framing (zoom to recognized intents, keep the building) ========
// fitCameraToWholeModel above parameterizes exactly one of the
// three degrees of freedom a view actually has - direction - while the SCOPE
// (what to frame) is hardcoded to the whole building at every call site and
// the MARGIN is fixed at zero by fitToSphere itself. These two additions make
// scope and margin parameters too, without touching the whole-model path:
// fitCameraToWholeModel is the load/Reset path and stays exactly as it was.

// Bounding box of just the elements named by `guidList`, in model space.
// Reuses both halves that already existed separately: the GUID resolution
// referByGuids does (highlighting.js) and the addFragmentIdMap measurement
// computeBuildingBoundingBox does above.
//
// Call this BEFORE referring the same GUIDs, not after: referByGuids splits
// the referred items into a cloned fragment and hides them in their origin
// fragment, while BoundingBoxer resolves a fragment map through those ORIGIN
// fragments (FragmentsManager.list, which the clone is never added to).
// Measuring first keeps the box independent of that surgery instead of
// depending on setVisibility's instance-slot bookkeeping surviving it.
export async function computeGuidsBoundingBox(components, model, guidList) {
  // Streamed model (handled since 2026-10-21): the
  // referred fragments are mostly NOT in the scene yet - the culler fetches
  // them only once the camera looks their way, which is exactly what this
  // box is needed for. The tile set's metadata describes every element's
  // placed geometries and their boxes, so the scope is measured from that,
  // with nothing streamed. Elements the tile set has no geometry for
  // contribute nothing, and null means nothing could be measured.
  const tiles = getModelContext(model)?.tileMetadata;
  if (tiles) return tileScopeBox(tiles, model, guidList);
  const guidToLocation = await resolveGuidIndex(model);
  const expressIDs = [];
  for (const guid of guidList) {
    const location = guidToLocation.get(guid);
    if (location) expressIDs.push(location.expressID);
  }
  if (expressIDs.length === 0) return null;

  const boundingBoxer = components.get(OBC.BoundingBoxer);
  boundingBoxer.reset();
  boundingBoxer.addFragmentIdMap(model.getFragmentMap(expressIDs));
  const box = boundingBoxer.get();
  boundingBoxer.reset();
  return box.isEmpty() ? null : box;
}

function tileScopeBox(tiles, model, guidList) {
  const assets = [];
  for (const guid of guidList) {
    const expressID = tiles.guidSeed[guid];
    const asset = expressID === undefined ? undefined : tiles.assetsById.get(expressID);
    if (asset) assets.push(asset);
  }
  model.updateMatrixWorld?.(true);
  return boxOfTileAssets(assets, tiles.geometries, model.matrixWorld);
}

// How much building the scoped fit keeps in frame, as a blend from "tight on
// the intent" (0) to "the whole building" (1). This is the knob that resolves
// "zoomed in" against "still show the rest of the building".
//
// An earlier version took the MAX of the scope's own padded sphere and a
// fraction of the building's, which is why this is a blend instead: with a
// max(), an intent whose own sphere already exceeded that fraction pinned the
// result, and the control became completely dead - confirmed live on a
// building-sized "room" intent, where every slider position produced the
// identical 71.2m distance. A blend always moves, monotonically, for every
// scope size, and lands on exactly the whole-model framing at 1.
export const DEFAULT_CONTEXT_AMOUNT = 0.2;
// Keeps an intent off the frame edge at context 0, where the fit would
// otherwise be flush against its own bounding sphere.
export const SCOPE_EDGE_PADDING = 0.15;

export function clampContext(value) {
  return Math.min(1, Math.max(0, Number.isFinite(value) ? value : DEFAULT_CONTEXT_AMOUNT));
}

// The sphere fitCameraToScope will frame, exposed separately so a live
// control can derive it without moving the camera.
//
// The CENTER blends on context^2 rather than linearly, so the view stays
// centred on the intent at ordinary settings and only drifts to the
// building's centre as the slider approaches 1. That curve is also what keeps
// the intent inside the frame throughout: the scope's sphere sits inside the
// building's, so |buildingCentre - scopeCentre| + scopeRadius <= buildingRadius,
// and a centre shift of context^2 (<= context) is always within the radius
// growth of context * (buildingRadius - scopeRadius) that the blend below buys.
// `padding` is the edge margin at context 0; it defaults to the constant it
// used to be, and only a view spec (views/viewSpec.js, framing.padding) ever
// passes anything else. The blend itself is unchanged.
export function scopeFitSphere(
  scopeBox,
  buildingBox,
  context = DEFAULT_CONTEXT_AMOUNT,
  padding = SCOPE_EDGE_PADDING,
) {
  const t = clampContext(context);
  const scopeSphere = scopeBox.getBoundingSphere(new THREE.Sphere());
  const tightRadius = scopeSphere.radius * (1 + padding);
  if (!buildingBox) return new THREE.Sphere(scopeSphere.center.clone(), tightRadius);

  const buildingSphere = buildingBox.getBoundingSphere(new THREE.Sphere());
  const radius = THREE.MathUtils.lerp(tightRadius, buildingSphere.radius, t);
  const center = scopeSphere.center.clone().lerp(buildingSphere.center, t * t);
  return new THREE.Sphere(center, radius);
}

// Frames `scopeBox` (a subset of the model) with enough margin that the rest
// of the building stays visible around it.
//
// `direction` omitted = KEEP the camera's current orbit angle, which is the
// right default for zoom-on-Refer: fitToSphere on its own is moveTo(center) +
// dollyTo(distance) with no setLookAt (camera-controls 1751-1754), so it
// re-targets and dollies without yanking the user's viewpoint to a preset.
// Passing a direction reproduces fitCameraToWholeModel's setLookAt-then-fit
// behavior, which is what the view-preset buttons want once they are
// scope-aware.
export async function fitCameraToScope(
  world,
  scopeBox,
  {
    buildingBox = null,
    context = DEFAULT_CONTEXT_AMOUNT,
    direction = null,
    transition = false,
    padding = SCOPE_EDGE_PADDING,
  } = {},
) {
  const controls = world.camera.controls;
  const sphere = scopeFitSphere(scopeBox, buildingBox, context, padding);

  // Lift BOTH clamps for the duration of the fit. minDistance is the one that
  // actually bites: fitCameraToWholeModel leaves it at diagonal/30 of the
  // WHOLE building, and a perspective fitToSphere resolves through dollyTo(),
  // which clamps to it (camera-controls 1497) - so a scope tighter than ~3.3%
  // of the building's bounding sphere would silently stop short.
  // maxDistance is lifted only so an unusually
  // large scope can't be clamped on the way there; it is RESTORED, never
  // recomputed, because its whole-model value is exactly what lets the user
  // wheel back out to the building after a zoom.
  const previousMaxDistance = controls.maxDistance;
  controls.minDistance = Number.EPSILON;
  controls.maxDistance = Infinity;

  if (direction) {
    const offset = direction.clone().multiplyScalar(Math.max(sphere.radius, 1) * 2);
    const camPos = sphere.center.clone().add(offset);
    await controls.setLookAt(
      camPos.x,
      camPos.y,
      camPos.z,
      sphere.center.x,
      sphere.center.y,
      sphere.center.z,
      transition,
    );
  }
  await controls.fitToSphere(sphere, transition);

  // Scope-relative floor so the user can still zoom in on the intent itself,
  // with the same absolute 0.5m backstop fitCameraToWholeModel uses to keep
  // minDistance clear of the near plane.
  const scopeDiagonal = scopeBox.getSize(new THREE.Vector3()).length();
  controls.minDistance = Math.max(0.5, scopeDiagonal / 30);
  controls.maxDistance = previousMaxDistance;
}
