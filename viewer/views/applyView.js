// ======== applyView: resolve a ViewSpec against the live viewer, move, record ========
// The view pipeline, in the order the data flows:
//
//   spec ─► scope      what to frame: an active Refer, the building, an intent, GUIDs
//        ─► frame      what azimuth is measured against (views/frame.js)
//        ─► lens       projection and field of view, BEFORE the fit so the fit
//                      happens in the projection the view asks for
//        ─► scene      transparency, hidden classes, colour mode, theme (views/scene.js)
//        ─► direction  (azimuth, elevation) in the frame -> world offset (views/direction.js)
//        ─► move       the SAME two calls the presets and Refer have always made:
//                      fitCameraToWholeModel for the building, fitCameraToScope otherwise
//        ─► scale      optionally re-scale by frame fill or metres per pixel (views/framing.js, views/pose.js)
//        ─► cut        section planes (views/cuts.js), after the move - they never change a fit
//        ─► image      optionally render at a fixed size, offscreen (views/render.js)
//        ─► score      optionally the visibility score of the members (views/visibility.js)
//        ─► record     what the camera actually did (captureViewRecord), kept on the
//                      viewer entry and announced as a `view-applied` event
//
// NOTHING HERE CHANGES A DEFAULT. A preset is `{direction: VIEW_PRESETS.top}`;
// a Refer is `{scope: {kind: "intent", intentId}, transition: true}`. Every
// field they leave unset resolves to what those two paths did before this
// module existed (viewSpec.js, "every default is today's behaviour"), and
// scripts/e2e/views.py pins their poses against the pre-change baseline to
// 1e-6. The camera system's behaviour is locked; this module is how it
// stays locked while gaining parameters.
//
// THE POLE. At elevation 90 the offset carries no azimuth (direction.js), and
// a setLookAt straight down gives camera-controls theta 0 - which is what the
// Top preset has always produced, and what its azimuth 0 means. A non-zero
// azimuth at the pole is a ROLL and is applied with controls.rotateTo after
// the fit (measured: theta survives fitToSphere, polar stays at makeSafe's
// epsilon, the elevation readout still says 90.0; a positive theta rolls the
// picture clockwise). Azimuth 0 skips the call, so Top's path is the
// unchanged one.
//
// INSTANT MOVES LAND ON THE NEXT FRAME. With `transition: false`,
// camera-controls stores the end state and writes it onto the camera in its
// next update(); `controls.distance` is already the end value, the camera's
// matrix is not. Anything here that reads the camera's matrix - the fill
// measure, the record, an offscreen render - calls `settleCamera` first,
// which is one `controls.update(0)`: idempotent, and exactly what the next
// frame would have done.
//
// AUTOMATION CONTRACT (additive): `data-view-status` on the
// viewer container goes "pending" -> "done" | "error", and `view-applied`
// bubbles from it with `detail.record`. Nothing is put on `window`.

import * as THREE from "three";

import {
  DEFAULT_CONTEXT_AMOUNT,
  computeBuildingBoundingBox,
  computeGuidsBoundingBox,
  fitCameraToScope,
  fitCameraToWholeModel,
  toggleProjection,
} from "../cameraViews.js";
import { getModelContext, getModelKey } from "../viewerModel.js";
import { findViewerByWorld, getCameraContext, setLastViewRecord } from "../viewerRegistry.js";
import {
  azimuthDegFromThetaRad,
  elevationDegFromPolarRad,
  normalizeAzimuthDeg,
  offsetFromAngles,
  thetaRadFromAzimuthDeg,
} from "./direction.js";
import { applyCut } from "./cuts.js";
import { resolveFrame } from "./frame.js";
import { boxFill, fillStep } from "./framing.js";
import { applyScene } from "./scene.js";
import { measureVisibility } from "./visibility.js";
import {
  distanceForHalfHeight,
  halfHeightAtTarget,
  halfHeightForMetresPerPixel,
  metresPerPixel,
  pixelsForTolerance,
  zoomForHalfHeight,
} from "./pose.js";
import { frameToPngDataUrl, renderOffscreen } from "./render.js";
import { describeViewSpec, resolveViewSpec } from "./viewSpec.js";

export const VIEW_RECORD_SCHEMA = 1;

/** Elevations this close to ±90° are treated as the pole: azimuth becomes roll. */
const POLE_MARGIN_DEG = 1e-6;
/** Components this close to 0 or ±1 are snapped, so axis views are exact vectors. */
const AXIS_SNAP = 1e-12;
/** Below this many pixels a claimed tolerance cannot be seen. */
export const MIN_TOLERANCE_PIXELS = 3;
/** Fill is solved in this many measure-and-step rounds (exact for orthographic after one). */
const FILL_ROUNDS = 2;

const setStatus = (container, status) => {
  if (container) container.dataset.viewStatus = status;
};

/** Writes camera-controls' end state onto the camera now (see the header). */
function settleCamera(world) {
  world.camera.controls.update(0);
  world.camera.three.updateMatrixWorld(true);
  world.camera.three.updateProjectionMatrix();
}

/**
 * Applies a view spec to a viewer and returns the record of what happened.
 *
 * @param {any} world - the viewer's @thatopen world
 * @param {Record<string, any>} [partialSpec] - a ViewSpec, possibly partial (viewSpec.js)
 * @param {{chosenBy?: string, rule?: string | null, viewName?: string | null, score?: boolean}} [options] - who
 *   chose this view, for the record's log ("preset" | "refer" | "manual" | "rule" | "search" | "policy"), for a
 *   rule-chosen view (views/rules.js) which rule and which of its named views, and whether to attach the
 *   visibility score of the scope's members (two offscreen ID renders; off for the presets and Refer)
 * @returns {Promise<Record<string, any>>} the view record
 */
export async function applyView(
  world,
  partialSpec = {},
  { chosenBy = "manual", rule = null, viewName = null, score = false } = {},
) {
  const entry = findViewerByWorld(world);
  if (!entry) throw new Error("applyView: this world has no viewer entry");
  const container = entry.container;
  setStatus(container, "pending");
  let spec;
  try {
    // Inside the try: a spec that fails validation is an "error" outcome of
    // this apply like any other, so a script waiting on data-view-status
    // sees it land instead of waiting forever.
    spec = resolveViewSpec(partialSpec);
    const model = entry.getCurrentModel?.() ?? null;
    if (!model) throw new Error("applyView: no model is loaded in this viewer");
    const ctx = {
      components: world.components,
      classifier: entry.classifier,
      fragments: entry.fragments,
      model,
    };

    const scope = await resolveScope(spec.scope, entry, ctx);
    const intent = scope.intentId ? findIntent(model, scope.intentId) : null;
    // The intent frame's last resort is the members' principal axis, which
    // needs their boxes - the one asynchronous input, measured here so
    // resolveFrame can stay synchronous for the panel.
    const memberCentres = spec.frame.kind === "intent" && intent ? await measureMemberCentres(ctx, intent) : null;
    const frame = resolveFrame(spec.frame, {
      ...ctx,
      buildingBox: scope.buildingBox ?? scope.box ?? null,
      scopeBox: scope.box ?? null,
      intent,
      memberCentres,
    });
    await applyLens(world, spec.lens);
    const sceneApplied = await applyScene(world, spec.scene, { entry, model, classifier: entry.classifier, scope });
    const direction = spec.direction ? resolveDirection(spec.direction, frame) : null;

    const controls = world.camera.controls;
    let fillAchieved = null;
    if (scope.box) {
      if (scope.kind === "building") {
        // The load/Reset path, unchanged: it always
        // sets a direction, so "keep the current one" means passing it in.
        // It is instant by design; `transition` does not apply to it.
        const offset = direction ? direction.offset : currentOffset(controls);
        await fitCameraToWholeModel(world, scope.box, offset);
      } else {
        await fitCameraToScope(world, scope.box, {
          buildingBox: scope.buildingBox ?? null,
          context: spec.framing.context ?? getCameraContext(world, DEFAULT_CONTEXT_AMOUNT),
          direction: direction?.offset ?? null,
          transition: spec.transition,
          padding: spec.framing.padding,
        });
      }
      if (direction?.atPole) {
        const theta = thetaRadFromAzimuthDeg(direction.worldAzimuthDeg);
        if (Math.abs(theta) > 1e-9) {
          await controls.rotateTo(theta, direction.elevationDeg > 0 ? 0 : Math.PI, spec.transition);
        }
      }
      // Scale, after the fit: frame fill or metres per pixel re-dolly / re-zoom
      // from the pose the fit produced. viewSpec.js refuses both at once.
      if (spec.framing.mode === "fill") {
        fillAchieved = await applyFill(world, scope.box, spec.framing.fill, spec.transition);
      }
      if (spec.lens.metresPerPixel !== null) {
        await applyMetresPerPixel(world, spec.lens.metresPerPixel, imagePixelHeight(world, spec.image), spec.transition);
      }
    }

    // Cuts after the move: a plane never changes a bounding box, so the fit
    // is the same with or without it, and the record and image see it.
    const cutApplied = applyCut(world, spec.cut, {
      components: world.components,
      classifier: entry.classifier,
      indexer: entry.indexer,
      model,
      scope,
      frame,
    });

    settleCamera(world);
    const record = captureViewRecord(world, { spec, scope, frame, chosenBy, rule, viewName });
    if (fillAchieved !== null) record.resolved.boxFill = fillAchieved;
    record.resolved.resolution = resolutionCheck(record.resolved.metresPerPixel, scope, model);
    record.resolved.cut = cutApplied;
    record.resolved.scene = sceneApplied;

    if (spec.image) {
      // Fixed-size render, kept off the record itself: a
      // PNG data URL is hundreds of KB, and records travel through events and
      // into localStorage with saved views. The bytes sit on the viewer entry
      // until the next image; the record says what was rendered.
      const frameImage = renderOffscreen(world, {
        width: spec.image.width,
        height: spec.image.height,
        pixelRatio: spec.image.pixelRatio ?? 1,
      });
      entry.lastViewImage = {
        dataUrl: frameToPngDataUrl(frameImage),
        width: frameImage.width,
        height: frameImage.height,
        pixelRatio: spec.image.pixelRatio ?? 1,
      };
      record.image = { width: frameImage.width, height: frameImage.height, pixelRatio: spec.image.pixelRatio ?? 1 };
      record.resolved.metresPerPixel = metresPerPixel(record.resolved.halfHeightM, frameImage.height);
      record.resolved.resolution = resolutionCheck(record.resolved.metresPerPixel, scope, model);
    }

    if (score) {
      // The members: an intent's non-context members, or the scope's GUIDs.
      const guids = intent
        ? intent.members.filter((m) => m.role !== "context").map((m) => m.guid)
        : (scope.guids ?? []);
      record.log.scores = guids.length ? await measureVisibility(world, { guids }) : null;
    }

    setLastViewRecord(world, record);
    if (entry.cameraScope && scope.kind !== "building") entry.cameraScope.spec = spec;
    setStatus(container, "done");
    container?.dispatchEvent(new CustomEvent("view-applied", { bubbles: true, detail: { record } }));
    return record;
  } catch (err) {
    setStatus(container, "error");
    container?.dispatchEvent(
      new CustomEvent("view-error", { bubbles: true, detail: { message: err?.message ?? String(err) } }),
    );
    throw err;
  }
}

const findIntent = (model, intentId) => (getModelContext(model)?.intents ?? []).find((i) => i.id === intentId) ?? null;

/** Up to this many member boxes are measured for the intent frame's PCA fallback. */
const MAX_PCA_MEMBERS = 64;

/** Scene-space centres of an intent's non-context members, for frameFromMemberCentres. */
async function measureMemberCentres(ctx, intent) {
  const guids = intent.members.filter((m) => m.role !== "context").map((m) => m.guid).slice(0, MAX_PCA_MEMBERS);
  const centres = [];
  for (const guid of guids) {
    const box = await computeGuidsBoundingBox(ctx.components, ctx.model, [guid]);
    if (box) centres.push(box.getCenter(new THREE.Vector3()).toArray());
  }
  return centres;
}

/** Unit vector from the camera's target to its position. */
function currentOffset(controls) {
  const p = controls.getPosition(new THREE.Vector3());
  const t = controls.getTarget(new THREE.Vector3());
  const d = p.sub(t);
  return d.lengthSq() > 0 ? d.normalize() : new THREE.Vector3(0, 0, 1);
}

function snapToAxes(v) {
  for (const axis of ["x", "y", "z"]) {
    const c = v[axis];
    if (Math.abs(c) < AXIS_SNAP) v[axis] = 0;
    else if (Math.abs(c - 1) < AXIS_SNAP) v[axis] = 1;
    else if (Math.abs(c + 1) < AXIS_SNAP) v[axis] = -1;
  }
  return v;
}

function resolveDirection(dirSpec, frame) {
  const worldAzimuthDeg = normalizeAzimuthDeg(dirSpec.azimuthDeg + frame.yawDeg);
  const atPole = Math.abs(dirSpec.elevationDeg) >= 90 - POLE_MARGIN_DEG;
  return {
    offset: snapToAxes(offsetFromAngles(dirSpec.azimuthDeg, dirSpec.elevationDeg, frame.yawDeg)),
    worldAzimuthDeg,
    elevationDeg: dirSpec.elevationDeg,
    atPole,
  };
}

async function applyLens(world, lens) {
  const camera = world.camera;
  if (lens.fovDeg !== null && Math.abs(camera.threePersp.fov - lens.fovDeg) > 1e-9) {
    camera.threePersp.fov = lens.fovDeg;
    camera.threePersp.updateProjectionMatrix();
  }
  const current = camera.projection.current;
  const wanted =
    lens.projection === "perspective" ? "Perspective" : lens.projection === "orthographic" ? "Orthographic" : current;
  // toggleProjection, never camera.projection.toggle(): it carries the
  // visible half-height across the switch (cameraViews.js).
  if (wanted !== current) await toggleProjection(world);
}

/** Dolly (perspective) or zoom (orthographic) to a new scale, inside the controls' limits. */
async function rescale(world, { distanceFactor, zoomFactor }, transition) {
  const camera = world.camera;
  const controls = camera.controls;
  if (camera.projection.current === "Orthographic") {
    await controls.zoomTo(camera.threeOrtho.zoom * zoomFactor, transition);
  } else {
    const wanted = controls.distance * distanceFactor;
    await controls.dollyTo(THREE.MathUtils.clamp(wanted, controls.minDistance, controls.maxDistance), transition);
  }
}

/**
 * Frame fill: measure the scope box's projected extent,
 * step the scale toward the target, repeat. Linear in zoom for orthographic
 * (one round is exact); a box has depth in perspective, so the second round
 * takes up the first-order error. Returns the fill achieved.
 */
async function applyFill(world, box, target, transition) {
  for (let round = 0; round < FILL_ROUNDS; round++) {
    settleCamera(world);
    const current = boxFill(box, world.camera.three);
    const step = fillStep(current, target);
    if (Math.abs(step.distanceFactor - 1) < 1e-4) break;
    await rescale(world, step, transition);
  }
  settleCamera(world);
  return boxFill(box, world.camera.three);
}

/** The pixel height the metres-per-pixel scale refers to: the image's when one is requested, else the canvas's. */
function imagePixelHeight(world, image) {
  if (image) return Math.max(1, Math.round(image.height * (image.pixelRatio ?? 1)));
  return world.renderer.three.domElement.height;
}

/**
 * Metres per pixel: exact in orthographic (zoom), at the
 * target plane in perspective (distance). Defined on the half-height
 * invariant toggleProjection carries, never the library's own frustum
 * arithmetic (views/pose.js).
 */
async function applyMetresPerPixel(world, mpp, pixelHeight, transition) {
  const camera = world.camera;
  const controls = camera.controls;
  const halfHeight = halfHeightForMetresPerPixel(mpp, pixelHeight);
  if (camera.projection.current === "Orthographic") {
    const ortho = camera.threeOrtho;
    await controls.zoomTo(zoomForHalfHeight(halfHeight, ortho.top - ortho.bottom), transition);
  } else {
    const wanted = distanceForHalfHeight(halfHeight, camera.threePersp.fov);
    await controls.dollyTo(THREE.MathUtils.clamp(wanted, controls.minDistance, controls.maxDistance), transition);
  }
}

/**
 * Can the image show the claim? Alignments and stacks carry `toleranceM`
 * (1-5 cm); below MIN_TOLERANCE_PIXELS the picture cannot distinguish a
 * member that meets it from one that does not. Null when the scope is not an
 * intent with a tolerance.
 */
function resolutionCheck(mpp, scope, model) {
  if (!scope?.intentId || !Number.isFinite(mpp) || !(mpp > 0)) return null;
  const intent = findIntent(model, scope.intentId);
  const toleranceM = intent?.evidence?.metrics?.toleranceM;
  if (!Number.isFinite(toleranceM)) return null;
  const pixels = pixelsForTolerance(toleranceM, mpp);
  return { toleranceM, pixels, ok: pixels >= MIN_TOLERANCE_PIXELS, minPixels: MIN_TOLERANCE_PIXELS };
}

/**
 * What to frame. `current` is what the preset buttons have always framed: the
 * active Refer's scope if there is one, else the building. An intent scope
 * reuses the Refer's own measurement when it is the referred intent - the box
 * was measured BEFORE the fragment split, which is the only safe moment
 * (cameraViews.js, computeGuidsBoundingBox) - and measures fresh otherwise.
 */
async function resolveScope(scopeSpec, entry, ctx) {
  const live = entry.cameraScope;
  const measureBuilding = () => computeBuildingBoundingBox(ctx.components, ctx.classifier, ctx.model);
  const fromLive = () => ({
    kind: "scope",
    guids: live.guids ?? null,
    intentId: live.intentId ?? null,
    box: live.box,
    buildingBox: live.buildingBox ?? null,
    unmeasurable: null,
  });
  const buildingScope = () => {
    const box = measureBuilding();
    return {
      kind: "building",
      guids: null,
      intentId: null,
      box,
      buildingBox: box,
      unmeasurable: box ? null : "the building's bounding box could not be measured",
    };
  };
  const measuredScope = async (guids, intentId) => {
    const box = await computeGuidsBoundingBox(ctx.components, ctx.model, guids);
    return {
      kind: "guids",
      guids,
      intentId,
      box,
      buildingBox: box ? measureBuilding() : null,
      unmeasurable: box
        ? null
        : "none of these elements has geometry, so there is nothing to frame",
    };
  };

  switch (scopeSpec.kind) {
    case "current":
      return live?.box ? fromLive() : buildingScope();
    case "building":
      return buildingScope();
    case "intent": {
      if (live?.box && live.intentId === scopeSpec.intentId) return fromLive();
      const intents = getModelContext(ctx.model)?.intents ?? [];
      const intent = intents.find((i) => i.id === scopeSpec.intentId);
      if (!intent) throw new Error(`applyView: intent ${scopeSpec.intentId} is not among this model's recognized intents`);
      return measuredScope(
        intent.members.map((m) => m.guid),
        intent.id,
      );
    }
    case "guids":
      return measuredScope(scopeSpec.guids, null);
    default:
      throw new Error(`applyView: unknown scope kind ${scopeSpec.kind}`);
  }
}

const boxToArrays = (box) => (box ? { min: box.min.toArray(), max: box.max.toArray() } : null);

/**
 * Measures the camera as it is NOW into a view record.
 * Called by applyView after a move, and on its own by Save / Copy for a
 * camera the user has orbited by hand - `spec` is then whatever was applied
 * last (or null), `scope` is absent, and `resolved` is the truth.
 *
 * @param {any} world
 * @param {{spec?: Record<string, any> | null, scope?: Record<string, any> | null, frame?: Record<string, any> | null,
 *          chosenBy?: string, rule?: string | null, viewName?: string | null}} [parts]
 */
export function captureViewRecord(
  world,
  { spec = null, scope = null, frame = null, chosenBy = "manual", rule = null, viewName = null } = {},
) {
  const entry = findViewerByWorld(world);
  const camera = world.camera;
  const controls = camera.controls;
  settleCamera(world);
  const position = controls.getPosition(new THREE.Vector3());
  const target = controls.getTarget(new THREE.Vector3());
  const offset = position.clone().sub(target);
  const distance = offset.length();
  const projection = camera.projection.current;
  const fovDeg = camera.threePersp.fov;
  const ortho = camera.threeOrtho;
  const zoom = ortho.zoom;
  const worldAzimuthDeg = azimuthDegFromThetaRad(controls.azimuthAngle);
  const worldElevationDeg = elevationDegFromPolarRad(controls.polarAngle);
  const halfHeightM = halfHeightAtTarget(
    projection === "Orthographic"
      ? { projection, frustumHeight: ortho.top - ortho.bottom, zoom }
      : { projection, distance: controls.distance, fovDeg },
  );
  const canvasEl = world.renderer?.three?.domElement;
  const canvas = canvasEl
    ? { width: canvasEl.width, height: canvasEl.height, pixelRatio: world.renderer.three.getPixelRatio?.() ?? 1 }
    : null;
  const yawDeg = frame?.yawDeg ?? 0;
  const model = entry?.getCurrentModel?.() ?? null;
  // The active Refer's intent is the record's intent only for a measurement
  // taken with no scope resolved (Save/Copy of whatever is on screen); a
  // building-scoped apply during a Refer is about the building.
  const intentId = scope ? (scope.intentId ?? null) : (entry?.cameraScope?.intentId ?? null);
  const scopeBox = scope?.box ?? null;

  return {
    schema: VIEW_RECORD_SCHEMA,
    createdAt: new Date().toISOString(),
    model: { fileKey: (model && getModelKey(model)) ?? null },
    intentId,
    label: spec ? describeViewSpec(spec) : "manual",
    spec,
    resolved: {
      frame: frame
        ? { kind: frame.kind, yawDeg: frame.yawDeg, origin: frame.origin, source: frame.source, share: frame.share ?? null, count: frame.count ?? null }
        : { kind: "world", yawDeg: 0, origin: [0, 0, 0], source: "world", share: null, count: null },
      scope: scope
        ? {
            kind: scope.kind,
            guidCount: scope.guids?.length ?? null,
            box: boxToArrays(scope.box),
            buildingBox: boxToArrays(scope.buildingBox),
            unmeasurable: scope.unmeasurable ?? null,
          }
        : null,
      position: position.toArray(),
      target: target.toArray(),
      worldDirection: distance > 0 ? offset.divideScalar(distance).toArray() : [0, 0, 1],
      distance,
      worldAzimuthDeg,
      worldElevationDeg,
      azimuthDeg: normalizeAzimuthDeg(worldAzimuthDeg - yawDeg),
      elevationDeg: worldElevationDeg,
      projection,
      fovDeg,
      zoom: projection === "Orthographic" ? zoom : null,
      halfHeightM,
      metresPerPixel: canvas ? metresPerPixel(halfHeightM, canvas.height) : null,
      // The scope box's projected share of the frame (views/framing.js) -
      // informational unless framing.mode was "fill", when applyView
      // overwrites it with the value the solve achieved.
      boxFill: scopeBox ? boxFill(scopeBox, camera.three) : null,
      resolution: null,
      cut: /** @type {Record<string, any>} */ ({ kind: "none", planes: [] }),
      scene: /** @type {Record<string, any> | null} */ (null),
      canvas,
      context: entry ? getCameraContext(world, DEFAULT_CONTEXT_AMOUNT) : null,
    },
    image: null,
    log: { chosenBy, rule, viewName, scores: /** @type {Record<string, any> | null} */ (null) },
  };
}

/**
 * Puts the camera exactly where a record says it was: position and target,
 * plus the projection and the orthographic zoom the old `{pos, target}` saved
 * views dropped. For a perspective record in a perspective viewer this is the
 * one setLookAt saved-view recall has always made.
 *
 * @param {any} world
 * @param {Record<string, any>} record
 * @param {{transition?: boolean}} [options]
 */
export async function replayViewRecord(world, record, { transition = true } = {}) {
  const r = record?.resolved;
  if (!Array.isArray(r?.position) || !Array.isArray(r?.target)) throw new Error("replayViewRecord: the record has no pose");
  const camera = world.camera;
  if (r.projection && r.projection !== camera.projection.current) await toggleProjection(world);
  await camera.controls.setLookAt(r.position[0], r.position[1], r.position[2], r.target[0], r.target[1], r.target[2], transition);
  if (r.projection === "Orthographic" && Number.isFinite(r.zoom)) await camera.controls.zoomTo(r.zoom, transition);
}
