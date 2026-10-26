import { describe, it, expect } from "vitest";
import * as THREE from "three";

import { boxFill, fillStep, projectedBoxExtent } from "../../views/framing.js";

const cube = (half) => new THREE.Box3(new THREE.Vector3(-half, -half, -half), new THREE.Vector3(half, half, half));

const orthoCamera = (halfHeight, aspect, zoom = 1) => {
  const cam = new THREE.OrthographicCamera(-halfHeight * aspect, halfHeight * aspect, halfHeight, -halfHeight, 0.1, 100);
  cam.zoom = zoom;
  cam.position.set(0, 0, 10);
  cam.lookAt(0, 0, 0);
  cam.updateProjectionMatrix();
  cam.updateMatrixWorld(true);
  return cam;
};

const perspCamera = (fovDeg, aspect, distance) => {
  const cam = new THREE.PerspectiveCamera(fovDeg, aspect, 0.1, 1000);
  cam.position.set(0, 0, distance);
  cam.lookAt(0, 0, 0);
  cam.updateProjectionMatrix();
  cam.updateMatrixWorld(true);
  return cam;
};

describe("framing: projected box extent and boxFill", () => {
  it("orthographic: a 1 m cube in a 2 m tall frame fills half of it", () => {
    const e = projectedBoxExtent(cube(0.5), orthoCamera(1, 1.5));
    expect(e.height).toBeCloseTo(1, 9); // NDC: 1 of 2
    expect(e.width).toBeCloseTo(1 / 1.5, 9); // narrower in x on a wide frame
    expect(e.behind).toBe(0);
    expect(boxFill(cube(0.5), orthoCamera(1, 1.5))).toBeCloseTo(0.5, 9);
  });
  it("orthographic: fill is linear in zoom", () => {
    expect(boxFill(cube(0.5), orthoCamera(1, 1.5, 1.6))).toBeCloseTo(0.8, 9);
  });
  it("perspective: moving the camera back shrinks the fill, monotonically", () => {
    let last = Infinity;
    for (const d of [3, 5, 10, 20, 40]) {
      const f = boxFill(cube(0.5), perspCamera(60, 1.5, d));
      expect(f).toBeLessThan(last);
      last = f;
    }
  });
  it("perspective: at distance 2r/sin(fov/2) the projected box is inside the frame", () => {
    // camera-controls' fit distance for the cube's bounding sphere (views/pose.js)
    const r = Math.sqrt(3) * 0.5;
    const fov = 60;
    const d = r / Math.sin((fov * Math.PI) / 360);
    const f = boxFill(cube(0.5), perspCamera(fov, 1.5, d));
    expect(f).toBeLessThan(1);
    expect(f).toBeGreaterThan(0.4);
  });
  it("counts corners behind the camera instead of projecting them silently", () => {
    const e = projectedBoxExtent(cube(5), perspCamera(60, 1.5, 1)); // camera inside the box
    expect(e.behind).toBeGreaterThan(0);
  });
});

describe("framing: fillStep", () => {
  it("doubles the zoom, halves the distance, to double the fill", () => {
    expect(fillStep(0.3, 0.6)).toEqual({ distanceFactor: 0.5, zoomFactor: 2 });
  });
  it("is a no-op for a degenerate measurement", () => {
    expect(fillStep(0, 0.6)).toEqual({ distanceFactor: 1, zoomFactor: 1 });
    expect(fillStep(0.3, 0)).toEqual({ distanceFactor: 1, zoomFactor: 1 });
  });
  it("orthographic round trip: one step lands exactly on the target", () => {
    const cam = orthoCamera(1, 1.5);
    const f0 = boxFill(cube(0.5), cam);
    cam.zoom *= fillStep(f0, 0.8).zoomFactor;
    cam.updateProjectionMatrix();
    expect(boxFill(cube(0.5), cam)).toBeCloseTo(0.8, 9);
  });
});
