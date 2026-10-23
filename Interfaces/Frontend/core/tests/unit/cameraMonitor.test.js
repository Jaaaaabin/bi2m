// cameraMonitor.js against fake camera-controls: the two 2026-10-21 fixes
// (culling tracks the current pose and settles on rest/sleep; a received
// sync pose is applied instantly and never echoed, projection and
// orthographic scale included). The real controls, worlds and fragments need
// a browser; scripts/e2e/camera_sync.py covers those.
import { describe, it, expect, vi } from "vitest";
import * as THREE from "three";

vi.mock("@thatopen/components", () => ({}));
vi.mock("../../highlighting.js", () => ({ resolveGuidIndex: async () => new Map() }));
vi.mock("../../viewerModel.js", () => ({ getModelContext: () => undefined }));

const { monitorCamera, readPose, poseChanged, POSE_EPSILON_M } = await import("../../cameraMonitor.js");
const { zoomForHalfHeight } = await import("../../views/pose.js");

// The slice of camera-controls 2.7.3 the monitor touches. `current` and `end`
// are kept apart exactly as the library keeps `_target`/`_targetEnd`:
// setLookAt(..., true) moves only the end, and every tick() walks the current
// value a step towards it and emits `update` - the library's own contract
// (dispatched only while something is still moving).
class FakeControls extends THREE.EventDispatcher {
  constructor() {
    super();
    this.current = { position: new THREE.Vector3(0, 0, 10), target: new THREE.Vector3() };
    this.end = { position: new THREE.Vector3(0, 0, 10), target: new THREE.Vector3() };
    this.zoom = 1;
    this.calls = { setLookAt: [], zoomTo: [] };
  }
  getPosition(out, receiveEndValue = true) {
    return out.copy(receiveEndValue ? this.end.position : this.current.position);
  }
  getTarget(out, receiveEndValue = true) {
    return out.copy(receiveEndValue ? this.end.target : this.current.target);
  }
  setLookAt(px, py, pz, tx, ty, tz, enableTransition = false) {
    this.calls.setLookAt.push({ position: [px, py, pz], target: [tx, ty, tz], enableTransition });
    this.end.position.set(px, py, pz);
    this.end.target.set(tx, ty, tz);
    this.pendingUpdate = true; // the library's _needsUpdate: the next update() emits `update` even for an instant move
    if (!enableTransition) {
      this.current.position.copy(this.end.position);
      this.current.target.copy(this.end.target);
    }
    return Promise.resolve();
  }
  zoomTo(zoom, enableTransition = false) {
    this.calls.zoomTo.push({ zoom, enableTransition });
    this.zoom = zoom;
    this.pendingUpdate = true;
    return Promise.resolve();
  }
  // One frame of the library's update(): advance a transition by half the
  // remaining distance and emit `update` if anything moved.
  tick() {
    const moved =
      this.current.position.distanceTo(this.end.position) > 1e-9 ||
      this.current.target.distanceTo(this.end.target) > 1e-9;
    this.current.position.lerp(this.end.position, 0.5);
    this.current.target.lerp(this.end.target, 0.5);
    if (moved || this.pendingUpdate) this.dispatchEvent({ type: "update" });
    this.pendingUpdate = false;
  }
  rest() {
    this.dispatchEvent({ type: "rest" });
  }
  sleep() {
    this.dispatchEvent({ type: "sleep" });
  }
}

function fakeWorld(projection = "Perspective", { top = 25, bottom = -25 } = {}) {
  const controls = new FakeControls();
  const world = {
    camera: {
      controls,
      projection: { current: projection },
      threeOrtho: { top, bottom, zoom: 1 },
      threePersp: { fov: 38 },
    },
  };
  // keep the fake ortho zoom in step with zoomTo, as update() does
  const zoomTo = controls.zoomTo.bind(controls);
  controls.zoomTo = (zoom, t) => {
    world.camera.threeOrtho.zoom = zoom;
    return zoomTo(zoom, t);
  };
  return world;
}

// Two viewers wired the way the loader wires them: a shared `peers` list of
// {world, receiveCameraSync}, the sync flag, a synchronous scheduler and a
// culling spy. `applyProjection` flips the fake's projection the way
// toggleProjection does, without the real camera.
function pair({ sync = true, projections = ["Perspective", "Perspective"] } = {}) {
  const peers = [];
  const culls = [];
  const make = (projection) => {
    const world = fakeWorld(projection);
    const entry = { world, receiveCameraSync: null };
    peers.push(entry);
    const monitor = monitorCamera(world, { groups: new Map() }, {
      peers: () => peers,
      syncEnabled: () => sync,
      cull: (w) => culls.push(w),
      applyProjection: async (w) => {
        w.camera.projection.current = w.camera.projection.current === "Perspective" ? "Orthographic" : "Perspective";
      },
      schedule: (fn) => fn(),
    });
    entry.receiveCameraSync = monitor.receive;
    entry.monitor = monitor;
    return entry;
  };
  const [a, b] = projections.map(make);
  const cullsOf = (entry) => culls.filter((w) => w === entry.world).length;
  return { a, b, culls, cullsOf };
}

const flush = () => new Promise((r) => setTimeout(r, 0));

describe("poseChanged", () => {
  it("ignores moves under the epsilon and reads the orthographic half-height", () => {
    const base = readPose(fakeWorld());
    const nudged = { ...base, position: base.position.clone().setX(POSE_EPSILON_M / 2) };
    expect(poseChanged(base, nudged)).toBe(false);
    const moved = { ...base, position: base.position.clone().setX(1) };
    expect(poseChanged(base, moved)).toBe(true);
    const ortho = readPose(fakeWorld("Orthographic"));
    expect(ortho.halfHeight).toBe(25);
    expect(poseChanged(ortho, { ...ortho, halfHeight: 12.5 })).toBe(true);
    expect(poseChanged(ortho, { ...ortho, projection: "Perspective" })).toBe(true);
  });
});

describe("culling", () => {
  it("runs once up front, then only when the CURRENT pose moves", () => {
    const { a, cullsOf } = pair({ sync: false });
    expect(cullsOf(a)).toBe(1);
    const c = a.world.camera.controls;
    c.setLookAt(0, 0, 40, 0, 0, 0, true); // animated: end moves, current does not yet
    c.tick(); // current halfway (15 m): a pass
    c.tick(); // 7.5 m further: a pass
    expect(cullsOf(a)).toBe(3);
    // the old end-value test would have passed once here and gone quiet
    c.tick(); // 3.75 m
    expect(cullsOf(a)).toBe(4);
  });
  it("runs when only the orthographic scale or the projection changed", () => {
    const { a, cullsOf } = pair({ sync: false, projections: ["Orthographic", "Perspective"] });
    const c = a.world.camera.controls;
    a.world.camera.threeOrtho.zoom = 2; // a wheel zoom: position and target untouched
    c.pendingUpdate = true;
    c.tick();
    expect(cullsOf(a)).toBe(2);
    a.world.camera.projection.current = "Perspective";
    c.pendingUpdate = true;
    c.tick();
    expect(cullsOf(a)).toBe(3);
  });
  it("forces an exact pass on rest and on sleep even when nothing moved", () => {
    const { a, cullsOf } = pair({ sync: false });
    const c = a.world.camera.controls;
    c.pendingUpdate = true;
    c.tick(); // an `update` without movement: no pass
    expect(cullsOf(a)).toBe(1);
    c.rest();
    expect(cullsOf(a)).toBe(2);
    c.sleep();
    expect(cullsOf(a)).toBe(3);
  });
  it("stops cleanly", () => {
    const { a, cullsOf } = pair({ sync: false });
    a.monitor.stop();
    a.world.camera.controls.rest();
    expect(cullsOf(a)).toBe(1);
  });
});

describe("sync", () => {
  it("mirrors a move onto the peer instantly and never echoes it back", async () => {
    const { a, b } = pair();
    const ca = a.world.camera.controls;
    const cb = b.world.camera.controls;
    ca.setLookAt(10, 5, 20, 1, 2, 3, false);
    ca.tick();
    await flush();
    expect(cb.calls.setLookAt).toEqual([{ position: [10, 5, 20], target: [1, 2, 3], enableTransition: false }]);
    // the follower's own monitor sees its camera at the received pose ...
    cb.tick();
    cb.rest();
    await flush();
    // ... and sends nothing back: the leader was called exactly once (by the test)
    expect(ca.calls.setLookAt.length).toBe(1);
    expect(cb.calls.setLookAt.length).toBe(1);
  });
  it("sends the settled pose on rest even when the last step was below the epsilon", async () => {
    const { a, b } = pair();
    const ca = a.world.camera.controls;
    const cb = b.world.camera.controls;
    ca.setLookAt(10, 5, 20, 1, 2, 3, false);
    ca.tick();
    ca.setLookAt(10.004, 5, 20, 1, 2, 3, false); // a damping tail: 4 mm
    ca.tick();
    await flush();
    expect(cb.calls.setLookAt.length).toBe(1); // below POSE_EPSILON_M: not sent ...
    ca.rest();
    await flush();
    expect(cb.calls.setLookAt.length).toBe(2); // ... until the camera rests
    expect(cb.calls.setLookAt[1].position[0]).toBe(10.004);
  });
  it("does not broadcast while sync is off", () => {
    const { a, b } = pair({ sync: false });
    a.world.camera.controls.setLookAt(10, 5, 20, 1, 2, 3, false);
    a.world.camera.controls.tick();
    expect(b.world.camera.controls.calls.setLookAt.length).toBe(0);
  });
  it("mirrors the projection and the orthographic half-height, not the raw zoom", async () => {
    const { a, b } = pair({ projections: ["Orthographic", "Perspective"] });
    a.world.camera.threeOrtho.zoom = 2; // half-height 12.5 m on a 50 m frustum
    b.world.camera.threeOrtho.top = 40; // a taller follower canvas: 80 m frustum
    b.world.camera.threeOrtho.bottom = -40;
    const ca = a.world.camera.controls;
    const cb = b.world.camera.controls;
    ca.setLookAt(0, 0, 200, 0, 0, 0, false);
    ca.tick();
    await flush();
    expect(b.world.camera.projection.current).toBe("Orthographic");
    expect(cb.calls.zoomTo).toEqual([{ zoom: zoomForHalfHeight(12.5, 80), enableTransition: false }]);
    expect(readPose(b.world).halfHeight).toBeCloseTo(12.5, 9);
    // switching back on the leader switches the follower back
    a.world.camera.projection.current = "Perspective";
    ca.pendingUpdate = true;
    ca.tick();
    await flush();
    expect(b.world.camera.projection.current).toBe("Perspective");
  });
  it("applies the latest pose when several arrive during an apply", async () => {
    const { a, b } = pair({ projections: ["Orthographic", "Perspective"] });
    const cb = b.world.camera.controls;
    const pose1 = { ...readPose(a.world), position: new THREE.Vector3(1, 0, 0) };
    const pose2 = { ...readPose(a.world), position: new THREE.Vector3(2, 0, 0) };
    const pose3 = { ...readPose(a.world), position: new THREE.Vector3(3, 0, 0) };
    b.receiveCameraSync(pose1); // starts an async apply (projection switch)
    b.receiveCameraSync(pose2);
    b.receiveCameraSync(pose3);
    await flush();
    await flush();
    const positions = cb.calls.setLookAt.map((c) => c.position[0]);
    expect(positions).toEqual([1, 3]); // pose2 was superseded before it was applied
  });
});
