import { describe, it, expect, vi } from "vitest";
import * as THREE from "three";

// frame.js imports cameraViews.js for the bbox fallback; the pure yaw math
// under test never reaches @thatopen.
vi.mock("@thatopen/components", () => ({}));
vi.mock("../../highlighting.js", () => ({ resolveGuidIndex: async () => new Map() }));
const { yawFromDirections, horizontalAxisThroughMatrix, localBoundsOfFragmentGeometry } = await import("../../views/frame.js");

// A rectangular building rotated by `yawDeg`: four walls, two long and two
// short, as world XZ directions with their lengths as weights.
const rotatedBuilding = (yawDeg, long = 30, short = 12) => {
  const a = THREE.MathUtils.degToRad(yawDeg);
  const along = { x: Math.sin(a), z: Math.cos(a) }; // bearing yaw from +Z toward +X
  const across = { x: Math.cos(a), z: -Math.sin(a) };
  return [
    { x: along.x * long, z: along.z * long },
    { x: -along.x * long, z: -along.z * long },
    { x: across.x * short, z: across.z * short },
    { x: -across.x * short, z: -across.z * short },
  ];
};

describe("frame: yawFromDirections recovers the grid direction modulo 90°", () => {
  for (const yaw of [0, 17, 45, 60, 89.5]) {
    it(`a building rotated ${yaw}° reads back as ${yaw % 90}°`, () => {
      const r = yawFromDirections(rotatedBuilding(yaw));
      expect(r).not.toBeNull();
      expect(r.yawDeg).toBeCloseTo(yaw % 90, 6);
      expect(r.share).toBeCloseTo(1, 9); // all four walls agree (mod 90)
      expect(r.count).toBe(4);
    });
  }
  it("90° is 0°: the frame aligns the grid, it does not pick a facade", () => {
    expect(yawFromDirections(rotatedBuilding(90)).yawDeg).toBeCloseTo(0, 6);
    expect(yawFromDirections(rotatedBuilding(180)).yawDeg).toBeCloseTo(0, 6);
  });
  it("averages across the 0/90 seam instead of landing on 45", () => {
    const r = yawFromDirections([
      { x: Math.sin(THREE.MathUtils.degToRad(89)), z: Math.cos(THREE.MathUtils.degToRad(89)) },
      { x: Math.sin(THREE.MathUtils.degToRad(1)), z: Math.cos(THREE.MathUtils.degToRad(1)) },
    ]);
    expect(Math.min(r.yawDeg, 90 - r.yawDeg)).toBeLessThan(0.01);
  });
  it("is weighted by length: a few long walls beat many short partitions", () => {
    const dirs = [
      ...rotatedBuilding(30, 40, 40),
      ...Array.from({ length: 20 }, () => ({ x: 0, z: 1.0 })), // 20 one-metre partitions on the world grid
    ];
    const r = yawFromDirections(dirs);
    expect(r.yawDeg).toBeCloseTo(30, 6);
    expect(r.share).toBeCloseTo(160 / 180, 6);
  });
  it("returns null with nothing to measure", () => {
    expect(yawFromDirections([])).toBeNull();
    expect(yawFromDirections([{ x: 0, z: 0 }])).toBeNull();
  });
});

describe("frame: a wall's direction read through its instance matrix", () => {
  const box = new THREE.Box3(new THREE.Vector3(0, 0, 0), new THREE.Vector3(8, 3, 0.3)); // 8 m long, 3 m high, 30 cm thick, along local X
  it("identity matrix: the long local edge is world X", () => {
    const axis = horizontalAxisThroughMatrix(box, new THREE.Matrix4());
    expect(axis.weight).toBeCloseTo(8, 9);
    expect(axis.x).toBeCloseTo(8, 9);
    expect(axis.z).toBeCloseTo(0, 9);
  });
  it("a 30° yaw in the matrix rotates the direction with it", () => {
    const m = new THREE.Matrix4().makeRotationY(THREE.MathUtils.degToRad(30)).setPosition(5, 0, -2);
    const axis = horizontalAxisThroughMatrix(box, m);
    expect(axis.weight).toBeCloseTo(8, 9);
    const bearing = THREE.MathUtils.radToDeg(Math.atan2(axis.x, axis.z));
    // three.js makeRotationY(+30°) takes +X to (cos 30, 0, -sin 30): the
    // bearing from +Z toward +X grows from 90 to 120.
    expect(bearing).toBeCloseTo(120, 6);
  });
  it("ignores a vertical long edge (a column-like piece)", () => {
    const tall = new THREE.Box3(new THREE.Vector3(0, 0, 0), new THREE.Vector3(0.4, 6, 0.4));
    const axis = horizontalAxisThroughMatrix(tall, new THREE.Matrix4());
    expect(axis.weight).toBeCloseTo(0.4, 9);
  });
});

describe("frame: fragment geometry bounds skip removed (0,0,0) triangles", () => {
  it("does not let padding at the origin stretch the box", () => {
    const g = new THREE.BufferGeometry();
    // vertex 0 is the fragment's unused origin vertex; the real quad is far away
    const pos = new Float32Array([0, 0, 0, 10, 0, 10, 12, 0, 10, 12, 3, 10, 10, 3, 10]);
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    g.setIndex([0, 0, 0, 1, 2, 3, 1, 3, 4]);
    const box = localBoundsOfFragmentGeometry(g);
    expect(box.min.toArray()).toEqual([10, 0, 10]);
    expect(box.max.toArray()).toEqual([12, 3, 10]);
  });
  it("returns null for a geometry without an index", () => {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(new Float32Array([0, 0, 0]), 3));
    expect(localBoundsOfFragmentGeometry(g)).toBeNull();
  });
});
