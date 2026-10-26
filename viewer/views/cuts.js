// ======== Cuts: section planes as camera actions ========
// 18 of the 35 intent types are room- or circulation-level and cannot be seen
// from outside, however transparent the rest of the model is. A cut is what
// makes "generic over intent" reach interiors: a storey plan cut (storey +
// height above its floor), a section plane (point + normal, or through the
// intent frame's line), a section box around the scope with a margin.
//
// One module for every library call: `OBC.Clipper` creates the planes and
// `SimpleRenderer.setPlane` registers them renderer-wide, so the refer
// split's cloned materials are clipped too (measured in scripts/e2e/views.py,
// phase 0). `Plans`/`Sections` have no ThatOpen v3 equivalent and both own
// the camera; neither is used. Helper quads are hidden so no plane is
// ever in a picture.
//
// Sign convention, measured: a plane with normal (0,−1,0) through a point
// removes everything ABOVE it (three.js clips the half-space the normal
// points away from). `keep: "below"` is the ordinary plan; `keep: "above"` is
// a reflected ceiling plan, looked at from below with a negative elevation.
//
// Storey elevation = min Y of the storey's children's boxes, in scene units
// (`indexer.getEntityChildren`, the same walk updateVisibility makes). The
// IFC `Elevation` property is in IFC units under the building placement and
// is the cross-check, not the source. Storey groups whose fragment map is
// empty are ghosts of a model unloaded earlier and are
// not offered.

import * as OBC from "@thatopen/components";
import * as THREE from "three";

/** Storeys of the loaded model, in classifier order, ghosts of earlier models excluded. */
export function storeyNames(classifier) {
  return Object.entries(classifier?.list?.spatialStructures ?? {})
    .filter(([, group]) => group?.map && Object.keys(group.map).length > 0)
    .map(([name]) => name);
}

/**
 * The floor level of a storey: the lowest point of anything filed under it.
 * @param {{components: any, classifier: any, indexer: any, model: any}} ctx
 * @param {string} name - the storey as the Floors list names it
 * @returns {{name: string, floorY: number, box: THREE.Box3}}
 */
export function measureStorey(ctx, name) {
  const group = ctx.classifier?.list?.spatialStructures?.[name];
  if (!group || group.id == null || !group.map || Object.keys(group.map).length === 0) {
    throw new Error(`cut: storey "${name}" is not in this model (known: ${storeyNames(ctx.classifier).join(", ") || "none"})`);
  }
  const children = ctx.indexer.getEntityChildren(ctx.model, group.id);
  const boundingBoxer = ctx.components.get(OBC.BoundingBoxer);
  boundingBoxer.reset();
  boundingBoxer.addFragmentIdMap(ctx.model.getFragmentMap(Array.from(children)));
  const box = boundingBoxer.get();
  boundingBoxer.reset();
  if (box.isEmpty()) throw new Error(`cut: storey "${name}" has no geometry loaded to measure`);
  return { name, floorY: box.min.y, box };
}

/** Removes every plane this module (or anyone) created on this world's components. */
export function clearCuts(world) {
  const clipper = world.components.get(OBC.Clipper);
  const n = clipper.list.length;
  clipper.deleteAll();
  return n;
}

/**
 * Applies a resolved `cut` spec. Always clears first: the spec is the whole
 * state of the view, so `kind: "none"` means no planes.
 *
 * @param {any} world
 * @param {Record<string, any>} cutSpec - resolved (viewSpec.js)
 * @param {{components: any, classifier: any, indexer: any, model: any,
 *          scope?: {box?: THREE.Box3 | null, buildingBox?: THREE.Box3 | null} | null,
 *          frame?: {yawDeg: number, origin: number[]} | null}} ctx
 * @returns {Record<string, any>} what was cut, for the record
 */
export function applyCut(world, cutSpec, ctx) {
  const clipper = world.components.get(OBC.Clipper);
  clipper.deleteAll();
  if (!cutSpec || cutSpec.kind === "none") return { kind: "none", planes: [] };

  const planes = [];
  const add = (normal, point) => {
    const plane = clipper.createFromNormalAndCoplanarPoint(world, normal.clone().normalize(), point.clone());
    plane.visible = false;
    planes.push({ normal: normal.clone().normalize().toArray(), point: point.toArray() });
  };
  const box = ctx.scope?.box ?? null;
  const around = ctx.scope?.buildingBox ?? box;
  const centre = around ? around.getCenter(new THREE.Vector3()) : new THREE.Vector3();

  switch (cutSpec.kind) {
    case "storeyPlan": {
      const storey = measureStorey(ctx, cutSpec.storey);
      const keep = cutSpec.keep ?? "below";
      const cutY = storey.floorY + cutSpec.heightM;
      const point = new THREE.Vector3(centre.x, cutY, centre.z);
      add(new THREE.Vector3(0, keep === "above" ? 1 : -1, 0), point);
      return { kind: "storeyPlan", planes, storey: storey.name, floorY: storey.floorY, cutY, heightM: cutSpec.heightM, keep };
    }
    case "sectionPlane": {
      // Explicit point/normal, else through the frame's line: the frame's
      // origin, cut across by the frame's +X (perpendicular to the line).
      const yaw = THREE.MathUtils.degToRad(ctx.frame?.yawDeg ?? 0);
      const normal = cutSpec.normal
        ? new THREE.Vector3().fromArray(cutSpec.normal)
        : new THREE.Vector3(Math.cos(yaw), 0, -Math.sin(yaw));
      if (cutSpec.flip) normal.negate();
      const point = cutSpec.point
        ? new THREE.Vector3().fromArray(cutSpec.point)
        : ctx.frame?.origin
          ? new THREE.Vector3().fromArray(ctx.frame.origin)
          : centre.clone();
      if (cutSpec.offsetM) point.addScaledVector(normal.clone().normalize(), cutSpec.offsetM);
      add(normal, point);
      return { kind: "sectionPlane", planes, source: cutSpec.normal ? "spec" : "frame" };
    }
    case "sectionBox": {
      if (!box) throw new Error("cut: a section box needs a measurable scope");
      const m = cutSpec.marginM ?? 0.5;
      const c = box.getCenter(new THREE.Vector3());
      add(new THREE.Vector3(1, 0, 0), new THREE.Vector3(box.min.x - m, c.y, c.z));
      add(new THREE.Vector3(-1, 0, 0), new THREE.Vector3(box.max.x + m, c.y, c.z));
      add(new THREE.Vector3(0, 1, 0), new THREE.Vector3(c.x, box.min.y - m, c.z));
      add(new THREE.Vector3(0, -1, 0), new THREE.Vector3(c.x, box.max.y + m, c.z));
      add(new THREE.Vector3(0, 0, 1), new THREE.Vector3(c.x, c.y, box.min.z - m));
      add(new THREE.Vector3(0, 0, -1), new THREE.Vector3(c.x, c.y, box.max.z + m));
      return { kind: "sectionBox", planes, marginM: m, box: { min: box.min.toArray(), max: box.max.toArray() } };
    }
    default:
      throw new Error(`cut: unknown kind ${cutSpec.kind}`);
  }
}
