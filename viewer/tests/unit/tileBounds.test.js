// tileBounds.js (2026-10-21): boxes from a tile set's metadata, the shape
// scripts/tileIfc.mjs writes and cameraViews.js reads for a streamed Refer.
import { describe, it, expect } from "vitest";
import * as THREE from "three";

import { boxOfTileAssets, expandByTileInstance, toMatrix4 } from "../../tileBounds.js";

const identity = new THREE.Matrix4().toArray();
const translation = (x, y, z) => new THREE.Matrix4().makeTranslation(x, y, z).toArray();
const scaled = (sx, sy, sz) => new THREE.Matrix4().makeScale(sx, sy, sz).toArray();
const asObject = (array) => Object.fromEntries(array.map((v, i) => [String(i), v]));

describe("toMatrix4", () => {
  it("reads both the array and the {'0': .., '15': ..} object form, in index order", () => {
    const m = translation(1, 2, 3);
    const obj = asObject(m);
    // key order scrambled on purpose: JSON.parse keeps insertion order, not numeric
    const scrambled = Object.fromEntries(Object.entries(obj).reverse());
    expect(toMatrix4(scrambled).toArray()).toEqual(m);
    expect(toMatrix4(m).toArray()).toEqual(m);
  });
});

describe("expandByTileInstance", () => {
  it("places the library's 0..1 unit cube by its boundingBox transform and the instance placement", () => {
    const box = new THREE.Box3();
    // a 2 x 4 x 6 geometry whose box starts at the origin, moved to (10, 0, 0)
    expandByTileInstance(box, translation(10, 0, 0), scaled(2, 4, 6));
    expect(box.min.toArray()).toEqual([10, 0, 0]);
    expect(box.max.toArray()).toEqual([12, 4, 6]);
  });
  it("reads the OBB fitter's own composition: centre, rotation, -halfSizes, 2 x halfSizes", () => {
    // what components-front's `$h` returns for a 2 x 4 x 6 box centred at (1, 2, 3), unrotated
    const obb = new THREE.Matrix4()
      .multiply(new THREE.Matrix4().makeTranslation(1, 2, 3))
      .multiply(new THREE.Matrix4().makeTranslation(-1, -2, -3))
      .multiply(new THREE.Matrix4().makeScale(2, 4, 6));
    const box = new THREE.Box3();
    expandByTileInstance(box, identity, obb.toArray());
    expect(box.min.toArray()).toEqual([0, 0, 0]);
    expect(box.max.toArray()).toEqual([2, 4, 6]);
  });
  it("transforms all eight corners, so a rotated instance is not under-measured", () => {
    const rot = new THREE.Matrix4().makeRotationZ(Math.PI / 4).toArray();
    const box = new THREE.Box3();
    expandByTileInstance(box, rot, scaled(2, 2, 2)); // a 2 m cube from the origin, rotated 45° about Z
    expect(box.max.x).toBeCloseTo(Math.SQRT2, 9); // the corner (2, 0) swung out
    expect(box.min.x).toBeCloseTo(-Math.SQRT2, 9); // the corner (0, 2)
    expect(box.max.y).toBeCloseTo(2 * Math.SQRT2, 9);
    expect(box.max.z).toBeCloseTo(2, 9);
  });
  it("applies the model's world matrix last", () => {
    const box = new THREE.Box3();
    expandByTileInstance(box, identity, scaled(2, 2, 2), new THREE.Matrix4().makeTranslation(0, 100, 0));
    expect(box.min.y).toBe(100);
    expect(box.max.y).toBe(102);
  });
});

describe("boxOfTileAssets", () => {
  const geometries = { a: { boundingBox: asObject(scaled(2, 2, 2)) }, b: { hasHoles: false } };
  it("unions every placed geometry of every asset and skips geometries without a box", () => {
    const assets = [
      { id: 1, geometries: [{ geometryID: "a", transformation: translation(0, 0, 0) }] },
      { id: 2, geometries: [{ geometryID: "a", transformation: translation(5, 0, 0) }, { geometryID: "b", transformation: identity }] },
    ];
    const box = boxOfTileAssets(assets, geometries);
    expect(box.min.toArray()).toEqual([0, 0, 0]);
    expect(box.max.toArray()).toEqual([7, 2, 2]);
  });
  it("returns null, not an empty box, when nothing can be measured", () => {
    expect(boxOfTileAssets([{ id: 3, geometries: [{ geometryID: "b", transformation: identity }] }], geometries)).toBeNull();
    expect(boxOfTileAssets([], geometries)).toBeNull();
  });
});
