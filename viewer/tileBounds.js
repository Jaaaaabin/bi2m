// ======== Bounding boxes from a tile set's own metadata ========
// A streamed model's extents, without any geometry in the scene. Shared by
// the offline tiler (scripts/tileIfc.mjs, the whole-model box it ships in
// tileset.json) and the viewer (cameraViews.js, the scope box of a Refer on a
// streamed model, since 2026-10-21).
//
// The tile set describes every placed geometry twice over: `assets.json`
// lists, per element (expressID), its geometry instances `{geometryID,
// transformation}`, and `geometries.json` carries, per geometry, a
// `boundingBox`: the oriented bounding box of that geometry's vertices, as a
// 4x4 transform of a UNIT CUBE WHOSE CORNERS LIE AT 0 AND 1 on each axis,
// composed with the instance's own placement. Read in the installed
// @thatopen/components-front 2.4.3: the tiler builds the box as
// T(centre) x R x T(-halfSizes) x S(2 x halfSizes) (the OBB fitter, dist
// index.js `$h`), and the streaming culler draws it with a BoxGeometry(1, 1,
// 1) whose every vertex it shifts by +0.5 (GeometryCullerRenderer's
// constructor) under instance matrix `transformation x boundingBox`. A cube
// at +/-0.5 - what scripts/tileIfc.mjs assumed until 2026-10-21 - lands every
// box half an element off along its own axes; the whole-model box was close
// enough to frame by, the per-element boxes were not.
// Tile sets written since carry `boxConvention` (TILE_BOX_CONVENTION)
// in tileset.json; the viewer recomputes the boxes of older sets from the
// metadata at load time rather than trusting the shipped ones. Both matrices
// arrive column-major, as an array or as the `{"0": .., "15": ..}` object
// JSON makes of a typed array.
//
// All EIGHT corners are transformed, not just min and max: a rotated
// instance's box is the box of its rotated corners, and transforming two
// opposite corners under-measures it. The OBB is the box of the geometry's
// vertices, so this box contains the parsed path's (OBC.BoundingBoxer,
// vertex-exact) and can be larger on a rotated or hollow element - a
// superset, never a miss.

export const TILE_BOX_CONVENTION = "unit-cube-0-1";

import * as THREE from "three";

export function toMatrix4(value) {
  const array = Array.isArray(value)
    ? value
    : Object.keys(value)
        .sort((a, b) => Number(a) - Number(b))
        .map((k) => value[k]);
  return new THREE.Matrix4().fromArray(array);
}

const _corner = new THREE.Vector3();
const _world = new THREE.Matrix4();
const _box = new THREE.Matrix4();

/**
 * Grows `box` by one placed geometry: `transformation` (the instance's
 * placement) x `boundingBox` (the geometry's unit-cube transform), both in
 * the tile set's column-major form, optionally under `worldMatrix` (the
 * model group's matrixWorld in the scene; identity for a viewer's first
 * model, kept for the day a second one is coordinated against it).
 */
export function expandByTileInstance(box, transformation, boundingBox, worldMatrix = null) {
  _world.copy(toMatrix4(transformation)).multiply(_box.copy(toMatrix4(boundingBox)));
  if (worldMatrix) _world.premultiply(worldMatrix);
  for (const x of [0, 1]) {
    for (const y of [0, 1]) {
      for (const z of [0, 1]) {
        box.expandByPoint(_corner.set(x, y, z).applyMatrix4(_world));
      }
    }
  }
  return box;
}

/**
 * The tile set's own precomputed extents (tileset.json, written by
 * scripts/tileIfc.mjs from the same metadata) as a THREE.Box3, or null if the
 * descriptor carries none (an older tile set).
 *
 * `buildingBoundingBox` excludes IfcSite/IfcGeographicElement, matching what
 * cameraViews.js's computeBuildingBoundingBox() does for a parsed model;
 * `worldBoundingBox` is everything. Framing uses the former, clipping planes
 * the latter, so a far plane derived from it can never clip terrain the user
 * has chosen to show. `worldMatrix` (the model group's matrixWorld) is
 * applied when given.
 */
export function tileSetBoundingBox(descriptor, which = "buildingBoundingBox", worldMatrix = null) {
  const raw = descriptor?.[which] ?? descriptor?.worldBoundingBox;
  if (!raw?.min || !raw?.max) return null;
  const box = new THREE.Box3(new THREE.Vector3().fromArray(raw.min), new THREE.Vector3().fromArray(raw.max));
  return worldMatrix ? box.applyMatrix4(worldMatrix) : box;
}

/**
 * The box of the given assets ({id, geometries: [{geometryID,
 * transformation}]}) over `geometries` ({[geometryID]: {boundingBox}}).
 * Returns null when nothing had a box - an asset whose geometry carries no
 * `boundingBox` contributes nothing, and an empty box is "nothing to frame",
 * never a point at the origin.
 */
export function boxOfTileAssets(assets, geometries, worldMatrix = null) {
  const box = new THREE.Box3();
  for (const asset of assets) {
    for (const instance of asset.geometries ?? []) {
      const geometry = geometries[instance.geometryID];
      if (!geometry?.boundingBox) continue;
      expandByTileInstance(box, instance.transformation, geometry.boundingBox, worldMatrix);
    }
  }
  return box.isEmpty() ? null : box;
}
