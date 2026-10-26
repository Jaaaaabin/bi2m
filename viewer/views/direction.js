// ======== View direction: (azimuth, elevation) in a frame <-> world offset ========
// The first of the view modules. Every direction the camera code knew until
// now was a hardcoded world-space unit vector (`*_VIEW_OFFSET` in
// cameraViews.js). This module names the two angles those vectors encode and
// measures them against a REFERENCE FRAME, so "front" can mean the main
// facade (building frame) or "along the alignment line" (intent frame)
// instead of only the world +Z axis.
//
// Convention, chosen to match camera-controls exactly so nothing has to be
// converted at the pole (see below):
//
//   offset = (cos el · sin az,  sin el,  cos el · cos az)      in frame axes
//
//   az   0° -> frame +Z (Front)     90° -> +X (Right)
//      180° -> −Z (Back)           270° -> −X (Left)
//   el   0° = level, 90° = straight down (plan), negative = looking up
//
// camera-controls derives its own spherical angles from the same vector:
// theta = atan2(x, z) and phi = angle from +Y, so theta IS this azimuth in
// radians and phi = 90° − elevation. The seven existing presets are special
// cases: FRONT = (0, 0), RIGHT = (90, 0), SIDE_VIEW_OFFSET = (45, 45),
// DEFAULT_VIEW_OFFSET = (45, 20), PLAN_VIEW_OFFSET = (·, 90), pinned by
// tests/unit/direction.test.js against the constants themselves.
//
// A frame is a yaw-only rotation about +Y (buildings stand upright; a tilted
// frame would make "elevation" ambiguous). Frame +Z sits at world azimuth
// `frameYawDeg`, so converting a frame azimuth to the world is one addition.
//
// THE POLE. At el = 90° the offset is exactly (0, 1, 0) whatever the azimuth,
// and camera-controls then gets theta = atan2(0, 0) = 0 from a setLookAt. The
// azimuth is not lost, it has become the ROLL: at the pole, camera-controls'
// theta decides which world direction is "up" on screen (screen-up = minus the
// azimuth direction, after Spherical.makeSafe nudges phi off the pole). So a
// plan view aligned to a rotated grid is an azimuth choice, applied with
// controls.rotateTo(theta, 0) after the look-at. `camera.up` is never touched:
// rebasing it would move the pole, break the elevation readout, and shift the
// singularity. `anglesFromOffset` reports azimuth 0 at the pole for the same
// reason camera-controls does - the vector carries none.

import * as THREE from "three";

/** Below this horizontal magnitude a unit vector is "at the pole". */
const POLE_EPSILON = 1e-9;

/**
 * Wraps an azimuth into [0, 360). NaN stays NaN.
 * camera-controls' `azimuthAngle` accumulates whole turns, so every readout
 * goes through here.
 * @param {number} deg
 * @returns {number}
 */
export function normalizeAzimuthDeg(deg) {
  const d = deg % 360;
  return d < 0 ? d + 360 : d === 0 ? 0 : d; // `d === 0 ? 0` folds -0 into 0
}

/**
 * Unit offset from the camera's target to the camera, in WORLD axes, for
 * angles measured in a frame whose +Z sits at world azimuth `frameYawDeg`.
 * @param {number} azimuthDeg
 * @param {number} elevationDeg
 * @param {number} [frameYawDeg=0]
 * @returns {THREE.Vector3}
 */
export function offsetFromAngles(azimuthDeg, elevationDeg, frameYawDeg = 0) {
  const az = THREE.MathUtils.degToRad(azimuthDeg + frameYawDeg);
  const el = THREE.MathUtils.degToRad(elevationDeg);
  const c = Math.cos(el);
  return new THREE.Vector3(c * Math.sin(az), Math.sin(el), c * Math.cos(az)).normalize();
}

/**
 * The inverse of offsetFromAngles. Azimuth is reported in the frame and
 * wrapped into [0, 360); at the pole it is 0 in the world (then shifted into
 * the frame), because the vector carries none - see the header.
 * @param {{x: number, y: number, z: number}} offset - any non-zero vector; normalized here
 * @param {number} [frameYawDeg=0]
 * @returns {{azimuthDeg: number, elevationDeg: number}}
 */
export function anglesFromOffset(offset, frameYawDeg = 0) {
  const length = Math.hypot(offset.x, offset.y, offset.z) || 1;
  const x = offset.x / length;
  const y = offset.y / length;
  const z = offset.z / length;
  const elevationDeg = THREE.MathUtils.radToDeg(Math.asin(THREE.MathUtils.clamp(y, -1, 1)));
  const atPole = Math.hypot(x, z) < POLE_EPSILON;
  const worldAzimuthDeg = atPole ? 0 : THREE.MathUtils.radToDeg(Math.atan2(x, z));
  return { azimuthDeg: normalizeAzimuthDeg(worldAzimuthDeg - frameYawDeg), elevationDeg };
}

/**
 * camera-controls' theta for a WORLD azimuth. Same angle, radians, unwrapped
 * into (−π, π] so it is the value `rotateTo` expects.
 * @param {number} worldAzimuthDeg
 * @returns {number}
 */
export function thetaRadFromAzimuthDeg(worldAzimuthDeg) {
  const wrapped = normalizeAzimuthDeg(worldAzimuthDeg);
  return THREE.MathUtils.degToRad(wrapped > 180 ? wrapped - 360 : wrapped);
}

/**
 * World azimuth from camera-controls' accumulating theta.
 * @param {number} thetaRad
 * @returns {number}
 */
export function azimuthDegFromThetaRad(thetaRad) {
  return normalizeAzimuthDeg(THREE.MathUtils.radToDeg(thetaRad));
}

/**
 * camera-controls' polar angle (0 = straight down at the target from above)
 * for an elevation in degrees above horizontal.
 * @param {number} elevationDeg
 * @returns {number}
 */
export function polarRadFromElevationDeg(elevationDeg) {
  return THREE.MathUtils.degToRad(90 - elevationDeg);
}

/**
 * Degrees above horizontal from camera-controls' polar angle - the
 * conversion the camera panel's readout has always made.
 * @param {number} polarRad
 * @returns {number}
 */
export function elevationDegFromPolarRad(polarRad) {
  return 90 - THREE.MathUtils.radToDeg(polarRad);
}
