// ======== Framing by scale: how much of the frame a box occupies ========
// Scale instead of metres: a target share of the image works for one door and
// for a whole building, where a distance in metres cannot do both. This
// module measures that share for a bounding box through a camera, as pure
// functions on THREE cameras (unit-tested in node).
//
// The measure is `boxFill`: the larger of the projected box's width and
// height, as a fraction of the frame (1 = the box's projection touches two
// opposite frame edges). It is deliberately named for what it is: measured, a
// building's bounding box can nearly fill the frame while the building itself
// covers ~24% of it - the box is not the pixels. The pixel share comes from
// the phase-4 ID pass; this one is what a camera can be SOLVED for in closed
// form, which is why framing uses it.

import * as THREE from "three";

const corner = new THREE.Vector3();

/**
 * The projected extent of a box through a camera, in normalized device
 * coordinates. The camera's matrices must be current (call
 * `updateMatrixWorld()` / `updateProjectionMatrix()` after moving it).
 *
 * @param {THREE.Box3} box
 * @param {THREE.Camera} camera
 * @returns {{minX: number, maxX: number, minY: number, maxY: number, width: number, height: number, behind: number}}
 *   width/height are in NDC units (2 = the full frame); `behind` counts
 *   corners behind the camera, whose projections are meaningless.
 */
export function projectedBoxExtent(box, camera) {
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;
  let behind = 0;
  const view = new THREE.Vector3();
  for (let i = 0; i < 8; i++) {
    corner.set(i & 1 ? box.max.x : box.min.x, i & 2 ? box.max.y : box.min.y, i & 4 ? box.max.z : box.min.z);
    view.copy(corner).applyMatrix4(camera.matrixWorldInverse);
    if (view.z > 0) behind += 1; // in camera space the view direction is -Z
    corner.project(camera);
    if (corner.x < minX) minX = corner.x;
    if (corner.x > maxX) maxX = corner.x;
    if (corner.y < minY) minY = corner.y;
    if (corner.y > maxY) maxY = corner.y;
  }
  return { minX, maxX, minY, maxY, width: maxX - minX, height: maxY - minY, behind };
}

/**
 * The share of the frame the box's projection spans, by its larger side.
 * 1 means edge to edge; 0.6 means 60% of the frame's width or height.
 * @param {THREE.Box3} box
 * @param {THREE.Camera} camera
 * @returns {number}
 */
export function boxFill(box, camera) {
  const e = projectedBoxExtent(box, camera);
  return Math.max(e.width, e.height) / 2;
}

/**
 * How to change the framing to move from one fill to another:
 *   perspective: multiply the camera's distance by `distanceFactor`;
 *   orthographic: multiply the zoom by `zoomFactor`.
 * Exact for orthographic cameras (projection is linear in zoom); for
 * perspective it is the first-order step - a box has depth, so the caller
 * re-measures and steps again (two passes land within a percent).
 * @param {number} currentFill
 * @param {number} targetFill
 * @returns {{distanceFactor: number, zoomFactor: number}}
 */
export function fillStep(currentFill, targetFill) {
  if (!(currentFill > 0) || !(targetFill > 0)) return { distanceFactor: 1, zoomFactor: 1 };
  return { distanceFactor: currentFill / targetFill, zoomFactor: targetFill / currentFill };
}
