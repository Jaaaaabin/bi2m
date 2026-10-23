// ======== Camera Monitor (frustum culling + optional cross-viewer sync) ========
// One per viewer. Runs frustum culling for that viewer, and - when the
// sidebar's sync toggle is on - mirrors this viewer's camera pose onto every
// other open viewer. Lived in ThatOpenCompanyLoader.js until 2026-10-21; moved
// here so the two behaviours can be exercised against fake controls
// (tests/unit/cameraMonitor.test.js) - the loader cannot be imported without
// a browser.
//
// EVENT-DRIVEN, not polled (camera sync used to poll on every frame).
// camera-controls emits `update` ONLY when the camera actually changed
// (dispatched inside `if (updated)`, guarded by its own `_needsUpdate` flag),
// which is exactly the signal this wants. The rAF is kept as a COALESCER:
// several `update` events can fire between two painted frames, and culling
// more than once per frame is pure waste.
//
// Two defects fixed on 2026-10-21:
//
// 1. Culling went STALE after every animated move. The change test read
//    `getPosition()`/`getTarget()`, whose default is the transition's END
//    value, so an animated Refer or saved-view recall culled once, at frame
//    0, against a camera that had not moved yet - and never again, because
//    the end values did not change afterwards. Measured on example_autcon:
//    an instant close zoom left 815 fragments visible (exact), the animated
//    zoom back out left 1,923 where the exact answer is 2,425 - 500 fragments
//    in view and hidden. The test now reads the CURRENT pose (what the
//    frustum is built from), and `rest` / `sleep` force one exact pass so the
//    settled view is always right. A pass costs ~0.1 ms for 2,400 fragments,
//    so there is no cheap/full split - just a correct one.
//
// 2. The sync echo. A follower's monitor compared the pose it had just been
//    GIVEN against the pose it last BROADCAST, found them different, and
//    broadcast the received pose straight back - every viewer re-sending
//    every pose it received, with an animated transition on top. A received
//    pose now becomes the follower's "last sent" and is applied instantly, so
//    nothing is ever echoed, and projection + orthographic scale (as a
//    half-height in metres, so viewers of different canvas sizes agree) are
//    mirrored along with position and target.

import * as THREE from "three";

import { toggleProjection } from "./cameraViews.js";
import { zoomForHalfHeight } from "./views/pose.js";

// ======== Frustum Culling (large models) ========
// Hides fragments entirely outside the camera view so the renderer isn't
// asked to draw geometry the user can't see.
//
// Deliberately a plain `Object3D.visible` toggle, NOT routed through Hider/
// `mesh.count` (which referByGuids/grayOutExceptGuids/updateVisibility/the
// site-context checkbox/intent-panel Clear already own, per this app's "no
// shared mode state, later overrides win" philosophy). `visible` is a pure
// AND-gate on top of whatever Hider has already decided: culling can only
// hide a fragment further, never revive one Hider already excluded, and can
// never itself be silently undone by a later refer/gray-out call the way
// sharing Hider's own state would be.
//
// Geometric frustum-vs-bounding-box test only - NOT the pixel-count GPU
// occlusion pass @thatopen/components' own unused `Cullers`/
// `MeshCullerRenderer` component does. That approach can under-count and hide
// a single small, already-referred element that renders too few pixels to
// clear its threshold; a pure geometric test can't produce that false negative.
const _cullFrustum = new THREE.Frustum();
const _cullProjScreenMatrix = new THREE.Matrix4();
// Per-fragment-mesh world-space bounds, computed once and reused every check.
// THREE.Box3.setFromObject() calls InstancedMesh.computeBoundingBox()
// internally, which accounts for every instance's own transform - but only
// up to the mesh's CURRENT `count` (three.js source: `for (let i = 0; i <
// count; i++)`), not every allocated instance. If this ran its first,
// cached computation while Hider had already reduced `count` (hiding some
// instances), the box would wrongly exclude them forever, even after
// they're shown again later. Computed against the full allocated capacity
// instead (count temporarily restored), so the cached box is a true
// superset regardless of Hider's state at the time this first runs.
const _fragmentBoundsCache = new WeakMap();

function getFragmentWorldBounds(mesh) {
  let box = _fragmentBoundsCache.get(mesh);
  if (!box) {
    const fullCount = mesh.instanceMatrix.count;
    const currentCount = mesh.count;
    mesh.count = fullCount;
    box = new THREE.Box3().setFromObject(mesh);
    mesh.count = currentCount;
    _fragmentBoundsCache.set(mesh, box);
  }
  return box;
}

// Per-viewer (each viewer already has its own isolated `world`/`fragments`
// via its own `OBC.Components()`). Only called when the camera actually
// moved (see monitorCamera), so an idle viewer costs nothing extra.
export function updateFrustumCulling(world, fragments) {
  const camera = world.camera.three;
  camera.updateMatrixWorld();
  _cullProjScreenMatrix.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse);
  _cullFrustum.setFromProjectionMatrix(_cullProjScreenMatrix);

  // Forces every fragment's matrixWorld current before the FIRST (cached)
  // bounds computation below - otherwise a fragment added since the
  // renderer's last frame (matrixWorld updates normally happen inside
  // renderer.render(), not on add()) would get its world-space box computed
  // from a stale/identity transform and wrongly cached that way forever.
  // Cheap: a scene-graph traversal, not per-fragment geometry work.
  world.scene.three.updateMatrixWorld(true);

  for (const group of fragments.groups.values()) {
    for (const fragment of group.items) {
      const mesh = fragment.mesh;
      if (!mesh) continue;
      mesh.visible = _cullFrustum.intersectsBox(getFragmentWorldBounds(mesh));
    }
  }
}

// ======== Camera pose, as the sync sends it ========
// A move below this (metres, position or target) is noise, not a change -
// the same threshold the culling change test has always used.
export const POSE_EPSILON_M = 0.01;

/**
 * The viewer's CURRENT camera pose (not a transition's destination):
 * position and target in scene metres, the projection, and - orthographic
 * only - the half-height of the view in metres (what `toggleProjection`
 * carries across a switch, and what two canvases of different heights can
 * agree on where a raw `zoom` cannot).
 */
export function readPose(world) {
  const camera = world.camera;
  const controls = camera.controls;
  const projection = camera.projection.current;
  let halfHeight = null;
  if (projection === "Orthographic") {
    const ortho = camera.threeOrtho;
    halfHeight = (ortho.top - ortho.bottom) / 2 / (ortho.zoom || 1);
  }
  return {
    position: controls.getPosition(new THREE.Vector3(), false),
    target: controls.getTarget(new THREE.Vector3(), false),
    projection,
    halfHeight,
  };
}

export function poseChanged(a, b, epsilon = POSE_EPSILON_M) {
  if (!a || !b) return true;
  if (a.projection !== b.projection) return true;
  if (a.position.distanceTo(b.position) > epsilon) return true;
  if (a.target.distanceTo(b.target) > epsilon) return true;
  if (a.projection === "Orthographic" && a.halfHeight > 0 && b.halfHeight > 0) {
    return Math.abs(a.halfHeight - b.halfHeight) > 1e-6 * Math.max(a.halfHeight, b.halfHeight);
  }
  return false;
}

/**
 * Starts watching one viewer's camera. Returns `{stop, receive}`:
 * `stop()` must be called when the viewer is removed (removeViewerById) -
 * without it, the listeners (and everything they close over: the world,
 * camera, controls) outlive the closed viewer for the page's lifetime;
 * `receive(pose)` is what the OTHER viewers' monitors call on this one when
 * sync is on (stored on the viewer entry as `receiveCameraSync`).
 *
 * `deps` exist for the unit test: `peers()` lists the viewer entries to
 * mirror onto (viewerRegistry's viewerData), `syncEnabled()` is the sidebar
 * flag, `cull`/`applyProjection`/`schedule` default to the real thing.
 */
export function monitorCamera(world, fragments, deps = {}) {
  const {
    peers = () => [],
    syncEnabled = () => false,
    cull = updateFrustumCulling,
    applyProjection = toggleProjection,
    schedule = (fn) => requestAnimationFrame(fn),
  } = deps;
  const controls = world.camera.controls;
  let stopped = false;
  let framePending = false;
  let forceCull = false;
  let forceSync = false;
  let lastCulled = null; // the pose of the last culling pass
  // The last pose this viewer SENT or RECEIVED: a received pose counts as
  // sent, which is what stops the echo (defect 2 above).
  let lastSynced = null;
  // > 0 while a received pose is being applied (a projection switch takes a
  // frame and emits its own `update`s on the way): nothing is broadcast
  // meanwhile. Culling still runs.
  let applying = 0;
  let pending = null;

  function runPass() {
    framePending = false;
    if (stopped) return;
    const pose = readPose(world);

    // Frustum culling - its own change-detection, independent of the sync
    // branch below: that flag is only about cross-viewer camera-pose
    // broadcast and is off by default, but culling must run for every viewer
    // regardless of it. Compares the CURRENT pose (defect 1 above), whole:
    // an orthographic wheel zoom and a projection switch change the frustum
    // without moving position or target (review, 2026-10-21).
    if (forceCull || poseChanged(pose, lastCulled)) {
      forceCull = false;
      lastCulled = pose;
      cull(world, fragments);
    }

    if (applying) return;
    if (!syncEnabled() || !lastSynced) {
      // Sync off, or the first pass ever: record, never send. Tracking while
      // off is what makes the first move AFTER the toggle a change worth
      // sending; recording on the first pass is what keeps a viewer added
      // while sync is on from yanking every other viewer to its opening pose.
      lastSynced = pose;
      return;
    }
    // The tail of a damped move is below the epsilon and would never go
    // out: on `rest` any difference at all is sent once, so the followers
    // land exactly - while a follower, whose settled pose IS the pose it was
    // given, still sends nothing. "Any difference" is relative to the
    // coordinates' size: getPosition rebuilds the pose from spherical
    // coordinates, and the round-off of a georeferenced, un-recentred model
    // (~5e6 m) reaches the metres-absolute 1e-9.
    const settled = forceSync;
    forceSync = false;
    const tolerance = settled ? 1e-9 * Math.max(1, pose.position.length()) : POSE_EPSILON_M;
    if (!poseChanged(pose, lastSynced, tolerance)) return;
    lastSynced = pose;
    for (const peer of peers()) {
      if (peer.world !== world) peer.receiveCameraSync?.(pose);
    }
  }

  function onCameraUpdate() {
    if (stopped || framePending) return;
    framePending = true;
    schedule(runPass);
  }

  // The settled view must be exact whether or not the last `update` landed
  // on a frame boundary: `rest` (an animated transition or a damped drag
  // coming to a stop) and `sleep` (the first idle tick after a jump).
  function onCameraSettled() {
    forceCull = true;
    forceSync = true;
    onCameraUpdate();
  }

  async function applyPose(pose) {
    lastSynced = pose;
    // Projection first, so the switch's own re-framing (toggleProjection
    // carries the half-height across) is overwritten by the exact pose.
    if (pose.projection !== world.camera.projection.current) await applyProjection(world);
    const { position: p, target: t } = pose;
    controls.setLookAt(p.x, p.y, p.z, t.x, t.y, t.z, false);
    if (pose.projection === "Orthographic" && pose.halfHeight > 0) {
      const ortho = world.camera.threeOrtho;
      await controls.zoomTo(zoomForHalfHeight(pose.halfHeight, ortho.top - ortho.bottom), false);
    }
  }

  async function receive(pose) {
    if (stopped) return;
    pending = pose; // latest wins: a pose arriving mid-apply replaces the queue
    if (applying) return;
    applying++;
    try {
      while (pending && !stopped) {
        const next = pending;
        pending = null;
        await applyPose(next);
      }
    } finally {
      applying--;
    }
  }

  controls.addEventListener("update", onCameraUpdate);
  controls.addEventListener("rest", onCameraSettled);
  controls.addEventListener("sleep", onCameraSettled);
  // One pass up front: a model can be added and framed before the camera
  // itself ever moves again, and culling must be correct for that first view
  // rather than waiting for the user to nudge the camera.
  onCameraUpdate();

  return {
    stop() {
      stopped = true;
      controls.removeEventListener("update", onCameraUpdate);
      controls.removeEventListener("rest", onCameraSettled);
      controls.removeEventListener("sleep", onCameraSettled);
    },
    receive,
  };
}
