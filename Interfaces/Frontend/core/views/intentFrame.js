// ======== The intent frame: from a record's metrics to a scene frame ========
// The intent records already carry what the camera needs to measure
// directions against the intent itself - `axis`/`value` on alignments and
// grid lines, `x,y` on column and window stacks - and the members' own layout
// otherwise. This module turns those into a frame {yawDeg, origin, source}
// (views/frame.js) as pure arithmetic, so it is unit-tested in node and the
// live part (frame.js) only supplies inputs.
//
// COORDINATES. The detectors measure in the IFC file's own plan coordinates
// (ifc_units.placement_xy, metres). The viewer loads with a Y-up swap and a
// shift to the origin recorded on the group as `coordinationMatrix`.
// Measured in scripts/e2e/views.py (phase 0), with zero spread over three
// column stacks:
//
//     scene = (x_ifc + T.x,  z_ifc + T.y,  −y_ifc + T.z)
//
// where T is the coordination matrix's translation. So an "axis X" line
// (x_ifc = value) is the scene plane x = value + T.x and runs along scene z;
// an "axis Y" line (y_ifc = value) is z = −value + T.z and runs along scene x.
//
// YAW is the world azimuth of the frame's +Z (direction.js): along the line
// for a line, so az 0 looks along it and members stack; for a stack at
// (x, y) there is no direction in the record, so the building's yaw is used
// and the origin is the stack.

const PERIOD_DEG = 180; // a line has two directions; a frame needs one

/**
 * A plan point from the detectors into the scene, at a given scene height.
 * @param {number} xIfc
 * @param {number} yIfc
 * @param {number[]} T - coordinationMatrix translation [tx, ty, tz]
 * @param {number} sceneY
 * @returns {number[]}
 */
export function ifcPlanToScene(xIfc, yIfc, T, sceneY) {
  return [xIfc + T[0], sceneY, -yIfc + T[2]];
}

/**
 * Frame from a record's metrics, or null when they carry no geometry.
 * @param {Record<string, any> | null | undefined} metrics - `evidence.metrics`
 * @param {number[]} T - coordinationMatrix translation
 * @param {{centre: number[], yawDeg: number}} fallback - the scope's scene centre, and the building yaw
 * @returns {{yawDeg: number, origin: number[], source: string} | null}
 */
export function intentFrameFromMetrics(metrics, T, fallback) {
  if (!metrics) return null;
  const [cx, cy, cz] = fallback.centre;
  const finite = (v) => typeof v === "number" && Number.isFinite(v);
  if (typeof metrics.axis === "string" && finite(metrics.value)) {
    const axis = metrics.axis.toUpperCase();
    if (axis === "X") {
      // x_ifc = value: the line runs along scene z, frame +Z = world +Z.
      return { yawDeg: 0, origin: [metrics.value + T[0], cy, cz], source: "metrics.axis" };
    }
    if (axis === "Y") {
      // y_ifc = value: the line runs along scene x, frame +Z = world +X.
      return { yawDeg: 90, origin: [cx, cy, -metrics.value + T[2]], source: "metrics.axis" };
    }
  }
  if (finite(metrics.x) && finite(metrics.y)) {
    return { yawDeg: fallback.yawDeg, origin: ifcPlanToScene(metrics.x, metrics.y, T, cy), source: "metrics.xy" };
  }
  return null;
}

/**
 * Frame from the members' layout: the principal axis of their plan centres.
 * Null when there is no clear axis (fewer than two distinct points, or the
 * spread is nearly isotropic - a square of columns has no direction).
 * @param {Array<number[]>} centres - scene-space [x, y, z] per member
 * @param {{minRatio?: number}} [options] - how much longer the first axis must be than the second
 * @returns {{yawDeg: number, origin: number[], source: string, ratio: number} | null}
 */
export function frameFromMemberCentres(centres, { minRatio = 2 } = {}) {
  const pts = centres.filter((c) => Array.isArray(c) && c.length === 3 && c.every(Number.isFinite));
  if (pts.length < 2) return null;
  const n = pts.length;
  const mean = [0, 1, 2].map((k) => pts.reduce((s, p) => s + p[k], 0) / n);
  let sxx = 0;
  let szz = 0;
  let sxz = 0;
  for (const p of pts) {
    const dx = p[0] - mean[0];
    const dz = p[2] - mean[2];
    sxx += dx * dx;
    szz += dz * dz;
    sxz += dx * dz;
  }
  // Eigen-decomposition of the 2x2 plan covariance.
  const tr = sxx + szz;
  const det = sxx * szz - sxz * sxz;
  const disc = Math.sqrt(Math.max(0, (tr * tr) / 4 - det));
  const l1 = tr / 2 + disc;
  const l2 = tr / 2 - disc;
  if (!(l1 > 1e-12)) return null;
  const ratio = l2 > 1e-12 ? l1 / l2 : Infinity;
  if (ratio < minRatio) return null;
  // Principal eigenvector (vx, vz); bearing from +Z toward +X, folded to [0, 180).
  const vx = Math.abs(sxz) > 1e-12 ? l1 - szz : sxx >= szz ? 1 : 0;
  const vz = Math.abs(sxz) > 1e-12 ? sxz : sxx >= szz ? 0 : 1;
  let yawDeg = (Math.atan2(vx, vz) * 180) / Math.PI;
  yawDeg = ((yawDeg % PERIOD_DEG) + PERIOD_DEG) % PERIOD_DEG;
  if (PERIOD_DEG - yawDeg < 1e-9) yawDeg = 0;
  return { yawDeg, origin: mean, source: "members.pca", ratio };
}
