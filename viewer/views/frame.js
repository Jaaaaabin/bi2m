// ======== Reference frames: what a view's azimuth is measured against ========
// Three frames, all yaw-only rotations about +Y (buildings stand upright, so
// "elevation" keeps its meaning in every frame):
//
//   world     the scene's own axes - what every preset meant until now;
//   building  the dominant wall direction, so "front" faces a facade and a
//             plan view lines up with the grid;
//   intent    from the intent record (alignment line, stack position) - a
//             later phase.
//
// A frame is {kind, yawDeg, origin, source}. `yawDeg` is the world azimuth of
// the frame's +Z (direction.js: az 0 = +Z, growing toward +X), so a frame
// azimuth becomes a world azimuth by one addition. `source` says what defined
// it, and goes into the view record - a frame nobody can audit is a frame
// nobody can trust.
//
// THE BUILDING FRAME IS ONLY DETERMINED MODULO 90°. Walls run along two
// perpendicular directions, and nothing in an IFC says which of the four
// resulting "fronts" is the real one (no reliable orientation signal
// exists). So the yaw is reported in [0, 90): the frame
// aligns the grid, it does not pick a facade.
//
// WHY INSTANCE MATRICES, NOT BOUNDING BOXES. An axis-aligned box of a wall
// rotated 30° has no orientation left in it - a histogram of box long-axes
// only ever "finds" 0° or 90°. Fragments keep each item's placement as an
// instance matrix (the culling code already relies on that), so a wall's
// direction here is its local long axis carried through that matrix. When
// the matrix is the identity because the exporter baked the geometry in
// world coordinates, the local box IS the world box and the fallback above
// applies; the record's `source` then says "walls" all the same, and the
// phase-3 PCA fallback is where a baked rotated building gets its yaw.

import * as THREE from "three";

import { getModelContext } from "../viewerModel.js";
import { frameFromMemberCentres, intentFrameFromMetrics } from "./intentFrame.js";

/** Entity names the classifier files walls under (classifier.byEntity, uppercase). */
export const WALL_ENTITIES = ["IFCWALL", "IFCWALLSTANDARDCASE"];

const PERIOD_DEG = 90;

/**
 * Dominant direction of a set of horizontal directions, modulo 90°.
 * Pure: `directions` is [{x, z, weight}] in world XZ, weight = length.
 *
 * Histogram at `binDeg`, take the peak, then refine with a weighted circular
 * mean (period 90°, so 89° and 1° average to 0°, not 45°) over everything
 * within `refineWindowDeg` of the peak.
 *
 * @param {Array<{x: number, z: number, weight?: number}>} directions
 * @param {{binDeg?: number, refineWindowDeg?: number}} [options]
 * @returns {{yawDeg: number, share: number, count: number} | null} null when nothing to measure.
 *   `share` is the peak's weight as a fraction of the total: 1 means every wall agrees.
 */
export function yawFromDirections(directions, { binDeg = 1, refineWindowDeg = 3 } = {}) {
  const angles = [];
  let total = 0;
  for (const d of directions) {
    const length = Math.hypot(d.x, d.z);
    if (!(length > 0)) continue;
    const weight = d.weight ?? length;
    if (!(weight > 0)) continue;
    // Bearing from +Z toward +X (direction.js's azimuth), folded to [0, 90).
    const bearing = ((THREE.MathUtils.radToDeg(Math.atan2(d.x, d.z)) % PERIOD_DEG) + PERIOD_DEG) % PERIOD_DEG;
    angles.push({ bearing, weight });
    total += weight;
  }
  if (angles.length === 0) return null;

  const bins = Math.ceil(PERIOD_DEG / binDeg);
  const histogram = new Float64Array(bins);
  for (const { bearing, weight } of angles) histogram[Math.min(bins - 1, Math.floor(bearing / binDeg))] += weight;
  let peak = 0;
  for (let i = 1; i < bins; i++) if (histogram[i] > histogram[peak]) peak = i;
  const peakCentre = (peak + 0.5) * binDeg;

  // Circular mean around the peak: multiply by 4 so the 90° period becomes a
  // full turn, average unit vectors, divide back.
  let sx = 0;
  let sy = 0;
  let inWindow = 0;
  for (const { bearing, weight } of angles) {
    let delta = bearing - peakCentre;
    if (delta > PERIOD_DEG / 2) delta -= PERIOD_DEG;
    if (delta < -PERIOD_DEG / 2) delta += PERIOD_DEG;
    if (Math.abs(delta) > refineWindowDeg) continue;
    const phase = THREE.MathUtils.degToRad(bearing * 4);
    sx += Math.cos(phase) * weight;
    sy += Math.sin(phase) * weight;
    inWindow += weight;
  }
  let yawDeg = inWindow > 0 ? THREE.MathUtils.radToDeg(Math.atan2(sy, sx)) / 4 : peakCentre;
  yawDeg = ((yawDeg % PERIOD_DEG) + PERIOD_DEG) % PERIOD_DEG;
  if (PERIOD_DEG - yawDeg < 1e-9) yawDeg = 0;
  return { yawDeg, share: inWindow / total, count: angles.length };
}

/**
 * Bounds of an indexed fragment geometry, skipping the (0,0,0) index triplets
 * fragments use for removed triangles - the same rule OBC.BoundingBoxer's
 * getFragmentBounds applies, so a padded buffer does not stretch the box.
 * @param {THREE.BufferGeometry} geometry
 * @returns {THREE.Box3 | null}
 */
export function localBoundsOfFragmentGeometry(geometry) {
  const position = geometry.attributes.position;
  const index = geometry.index;
  if (!position || !index) return null;
  const box = new THREE.Box3();
  const v = new THREE.Vector3();
  const arr = index.array;
  for (let i = 0; i + 2 < arr.length; i += 3) {
    if (arr[i] === 0 && arr[i + 1] === 0 && arr[i + 2] === 0) continue;
    for (let k = 0; k < 3; k++) box.expandByPoint(v.fromBufferAttribute(position, arr[i + k]));
  }
  return box.isEmpty() ? null : box;
}

/**
 * The world-space horizontal direction and length of one item's longest
 * local edge, read through one instance matrix. Returns null for an item
 * whose longest edge is vertical (a column-like wall segment) or degenerate.
 * @param {THREE.Box3} localBox
 * @param {THREE.Matrix4} matrix
 * @returns {{x: number, z: number, weight: number} | null}
 */
export function horizontalAxisThroughMatrix(localBox, matrix) {
  const size = localBox.getSize(new THREE.Vector3());
  const origin = new THREE.Vector3().applyMatrix4(matrix);
  let best = null;
  for (const [axis, length] of [
    [new THREE.Vector3(1, 0, 0), size.x],
    [new THREE.Vector3(0, 1, 0), size.y],
    [new THREE.Vector3(0, 0, 1), size.z],
  ]) {
    if (!(length > 0)) continue;
    const edge = axis.multiplyScalar(length).applyMatrix4(matrix).sub(origin);
    const horizontal = Math.hypot(edge.x, edge.z);
    if (horizontal < Math.abs(edge.y)) continue; // mostly vertical: not a plan direction
    if (!best || horizontal > best.weight) best = { x: edge.x, z: edge.z, weight: horizontal };
  }
  return best;
}

/**
 * Measures the building frame from the loaded walls. Not cached here; see
 * resolveFrame, which caches per model.
 *
 * @param {{classifier: any, fragments: any}} ctx
 * @returns {{yawDeg: number, source: string, share?: number, count?: number}}
 */
export function measureBuildingFrame({ classifier, fragments }) {
  const directions = [];
  const present = WALL_ENTITIES.filter((name) => classifier?.list?.entities?.[name]);
  if (present.length) {
    const fragMap = classifier.find({ entities: present }) || {};
    const matrix = new THREE.Matrix4();
    for (const [fragmentID, itemIDs] of Object.entries(fragMap)) {
      const fragment = fragments.list.get(fragmentID);
      const mesh = fragment?.mesh;
      if (!mesh?.geometry) continue;
      const localBox = localBoundsOfFragmentGeometry(mesh.geometry);
      if (!localBox) continue;
      for (const itemID of itemIDs) {
        const instances = fragment.getInstancesIDs(Number(itemID));
        if (!instances) continue;
        for (const instance of instances) {
          mesh.getMatrixAt(instance, matrix);
          const axis = horizontalAxisThroughMatrix(localBox, matrix);
          if (axis) directions.push(axis);
        }
      }
    }
  }
  const yaw = yawFromDirections(directions);
  if (!yaw) {
    // No walls to read: the frame is the world's, said so explicitly. The
    // origin still comes from the building box resolveFrame is handed.
    return { yawDeg: 0, source: "bbox" };
  }
  return { yawDeg: yaw.yawDeg, source: "walls", share: yaw.share, count: yaw.count };
}

/** The loader's shift-to-origin, as the translation the record coordinates need (views/intentFrame.js). */
export function coordinationTranslation(model) {
  const e = model?.coordinationMatrix?.elements;
  return e ? [e[12], e[13], e[14]] : [0, 0, 0];
}

/**
 * Resolves a spec's frame for a loaded model. The building frame is measured
 * once per model and kept on the model context (viewerModel.js), the same
 * place the GUID index lives, so a second view costs nothing. An intent
 * frame comes from the record's metrics (views/intentFrame.js), else from
 * the members' principal axis when the caller measured their centres, else
 * it is the building frame with the scope as origin - and says so.
 *
 * Synchronous on purpose: the camera panel reads frames on input events. The
 * one asynchronous input, the member centres, is measured by the caller
 * (applyView.js) and passed in.
 *
 * @param {{kind: string}} frameSpec
 * @param {{components: any, classifier: any, fragments: any, model: any, buildingBox?: THREE.Box3 | null,
 *          scopeBox?: THREE.Box3 | null, intent?: Record<string, any> | null, memberCentres?: number[][] | null}} ctx
 * @returns {{kind: string, yawDeg: number, origin: number[], source: string, share?: number, count?: number, ratio?: number}}
 */
export function resolveFrame(frameSpec, ctx) {
  const origin = ctx.buildingBox ? ctx.buildingBox.getCenter(new THREE.Vector3()).toArray() : [0, 0, 0];
  if (frameSpec.kind === "world") return { kind: "world", yawDeg: 0, origin, source: "world" };
  const building = () => {
    const context = ctx.model ? getModelContext(ctx.model) : null;
    let measured = context?.buildingFrame;
    if (!measured) {
      measured = measureBuildingFrame(ctx);
      if (context) context.buildingFrame = measured;
    }
    return measured;
  };
  if (frameSpec.kind === "building") return { kind: "building", origin, ...building() };
  if (frameSpec.kind === "intent") {
    if (!ctx.intent) {
      throw new Error("frame.kind 'intent' needs an intent in scope (scope.kind 'intent', or an active Refer)");
    }
    const b = building();
    const centre = (ctx.scopeBox ?? ctx.buildingBox)?.getCenter(new THREE.Vector3()).toArray() ?? origin;
    const fromMetrics = intentFrameFromMetrics(ctx.intent.evidence?.metrics, coordinationTranslation(ctx.model), {
      centre,
      yawDeg: b.yawDeg,
    });
    if (fromMetrics) return { kind: "intent", ...fromMetrics };
    if (ctx.memberCentres?.length) {
      const pca = frameFromMemberCentres(ctx.memberCentres);
      if (pca) return { kind: "intent", yawDeg: pca.yawDeg, origin: pca.origin, source: pca.source, ratio: pca.ratio };
    }
    return { kind: "intent", yawDeg: b.yawDeg, origin: centre, source: "building (record carries no geometry, members have no axis)" };
  }
  throw new Error(`frame.kind '${frameSpec.kind}' is not implemented`);
}
