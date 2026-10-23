// ======== Pose solver: the framing arithmetic, with no camera attached ========
// camera-controls decides how far back a fit lands (`fitToSphere`) and what
// an orthographic zoom means, but only for the live canvas, and only by
// moving the real camera. Two things need the same numbers without a canvas:
// a fixed-size offscreen render and any search over many candidate views.
// This module is those formulas as pure functions.
//
// They are transcribed from the installed camera-controls 2.7.3 source
// (`getDistanceToFitSphere`, `fitToSphere`), and the live harness
// (scripts/e2e/views.py) checks them against the real controls on the real
// canvas, so a library upgrade that changes the fit shows up as a failed check
// rather than a silent drift between the two paths.
//
// The one invariant this module adds is the WORLD HALF-HEIGHT visible at the
// target plane. `toggleProjection` (cameraViews.js) already carries it across
// a projection switch; here it is also what "metres per pixel" is defined
// from, so an orthographic scale never depends on the library's own frustum
// arithmetic (measured ~7% off at this lens).

/**
 * Distance from the target at which a sphere of `radius` just fits the
 * perspective frustum. Mirrors camera-controls: the limiting field of view is
 * the vertical one on a landscape canvas and the horizontal one on a portrait
 * canvas.
 * @param {number} radius
 * @param {number} fovDeg - vertical field of view
 * @param {number} aspect - width / height
 * @returns {number}
 */
export function distanceToFitSphere(radius, fovDeg, aspect) {
  const vFov = (fovDeg * Math.PI) / 180;
  const hFov = Math.atan(Math.tan(vFov * 0.5) * aspect) * 2;
  const fov = aspect > 1 ? vFov : hFov;
  return radius / Math.sin(fov * 0.5);
}

/**
 * Orthographic zoom at which a sphere of `radius` just fits a frustum of the
 * given world size (right − left, top − bottom at zoom 1). Mirrors
 * camera-controls' `fitToSphere` for orthographic cameras.
 * @param {number} radius
 * @param {number} frustumWidth
 * @param {number} frustumHeight
 * @returns {number}
 */
export function zoomToFitSphere(radius, frustumWidth, frustumHeight) {
  const diameter = 2 * radius;
  return Math.min(frustumWidth / diameter, frustumHeight / diameter);
}

/**
 * World half-height visible at the target plane - the invariant that makes
 * perspective and orthographic framings comparable.
 * @param {{projection: "Perspective" | "Orthographic", distance?: number, fovDeg?: number, frustumHeight?: number, zoom?: number}} view
 * @returns {number}
 */
export function halfHeightAtTarget(view) {
  if (view.projection === "Orthographic") {
    return (view.frustumHeight ?? 0) / 2 / (view.zoom || 1);
  }
  return (view.distance ?? 0) * Math.tan(((view.fovDeg ?? 0) * Math.PI) / 360);
}

/**
 * Perspective distance that shows a given half-height at the target plane.
 * @param {number} halfHeight
 * @param {number} fovDeg
 * @returns {number}
 */
export function distanceForHalfHeight(halfHeight, fovDeg) {
  return halfHeight / Math.tan((fovDeg * Math.PI) / 360);
}

/**
 * Orthographic zoom that shows a given half-height at the target plane.
 * @param {number} halfHeight
 * @param {number} frustumHeight - top − bottom at zoom 1
 * @returns {number}
 */
export function zoomForHalfHeight(halfHeight, frustumHeight) {
  return frustumHeight / 2 / halfHeight;
}

/**
 * Metres per image pixel for a view with the given half-height on a canvas of
 * `canvasHeightPx` device pixels. Exact for orthographic views; at the target
 * plane only for perspective ones.
 * @param {number} halfHeight
 * @param {number} canvasHeightPx
 * @returns {number}
 */
export function metresPerPixel(halfHeight, canvasHeightPx) {
  return (2 * halfHeight) / canvasHeightPx;
}

/**
 * The half-height that produces a wanted scale on a canvas - the inverse of
 * metresPerPixel, for `lens.metresPerPixel` in a view spec.
 * @param {number} mpp
 * @param {number} canvasHeightPx
 * @returns {number}
 */
export function halfHeightForMetresPerPixel(mpp, canvasHeightPx) {
  return (mpp * canvasHeightPx) / 2;
}

/**
 * How many pixels a tolerance spans at a given scale - the resolution check.
 * Below a few pixels the image cannot show the claim.
 * @param {number} toleranceM
 * @param {number} mpp
 * @returns {number}
 */
export function pixelsForTolerance(toleranceM, mpp) {
  return toleranceM / mpp;
}
