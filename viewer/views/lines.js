// ======== Lines in the scene: the live half of the line specs ========
// Owns one THREE.Group per world, named like views/labels.js's, and the
// registry of what is in it. Everything geometric is views/lineSpec.js; this
// module resolves anchors against the loaded model (bounding boxes for every
// anchor, floor outlines through views/outline.js for the anchors that ask),
// builds and disposes the THREE objects - one THREE.Line per polyline, so an
// outline with a hole is two objects under one id - and announces changes.
//
// Lines are MODEL state, not view state: views/scene.js's restoreScene leaves
// them alone, Unload clears them (ThatOpenCompanyLoader.js, right after the
// Refer is undone and before the fragments are disposed), and a closed viewer
// clears them before its components are disposed. They are plain scene
// children, so the loader's frustum culler (fragment meshes only) and the
// offscreen render (same scene) need no change; a storey cut's clipping planes
// are renderer-wide and would cut them too (not measured).
//
// WIDTH. WebGL ignores LineBasicMaterial.linewidth, so `style.width` 1 is a
// plain THREE.Line and anything wider is a Line2 from three/examples/jsm/lines:
// a triangle strip whose LineMaterial needs the canvas size in CSS pixels
// (`resolution`) to turn pixels into clip space. One Set of fat materials per
// world keeps that current through the renderer's onResize event; the
// offscreen render (views/render.js) sets its own target size for the pass
// through `setFatResolution` and restores the live one after, so a fat line
// is the same width in pixels in every picture. Dashes exist only on fat
// lines (`computeLineDistances`).
//
// AUTOMATION CONTRACT (additive): `data-overlay-lines="<count>"` on the viewer
// container, and an `overlay-lines-changed` CustomEvent bubbling from it with
// `{count, added, removed, skipped}`. Nothing is put on `window`.

import * as THREE from "three";
import { Line2 } from "three/examples/jsm/lines/Line2.js";
import { LineGeometry } from "three/examples/jsm/lines/LineGeometry.js";
import { LineMaterial } from "three/examples/jsm/lines/LineMaterial.js";

import { computeGuidsBoundingBox } from "../cameraViews.js";
import { resolveGuidIndex } from "../highlighting.js";
import { findViewerByWorld } from "../viewerRegistry.js";
import { anchorNeeds, normalizeLineSpec, resolveLinePoints } from "./lineSpec.js";
import { floorLoops, worldTrianglesOf } from "./outline.js";

export const LINES_GROUP_NAME = "bi2m-overlay-lines";
/** Below the numbered labels (10000), above everything else. */
const LINES_RENDER_ORDER = 9000;

function entryFor(world) {
  const entry = findViewerByWorld(world);
  if (!entry) throw new Error("lines: this world belongs to no open viewer");
  return entry;
}

function groupFor(world, create) {
  const scene = world.scene.three;
  let group = scene.getObjectByName(LINES_GROUP_NAME);
  if (!group && create) {
    group = new THREE.Group();
    group.name = LINES_GROUP_NAME;
    scene.add(group);
  }
  return group ?? null;
}

/** @returns {Map<string, {spec: any, points: number[][], polylines: number[][][], objects: THREE.Object3D[]}>} */
function registry(entry) {
  if (!entry.overlayLines) entry.overlayLines = new Map();
  return entry.overlayLines;
}

function announce(entry, detail) {
  const count = registry(entry).size;
  const container = entry.container;
  if (!container) return;
  container.dataset.overlayLines = String(count);
  container.dispatchEvent(
    new CustomEvent("overlay-lines-changed", { bubbles: true, detail: { count, ...detail } }),
  );
}

/** Per world: the fat-line materials whose `resolution` follows the canvas size. */
const fatMaterials = new WeakMap();

function fatMaterialsOf(world) {
  let set = fatMaterials.get(world);
  if (!set) {
    set = new Set();
    fatMaterials.set(world, set);
    world.renderer?.onResize?.add?.(() => syncResolution(world));
  }
  return set;
}

/** Writes a resolution onto every fat material of this world (views/render.js, for an offscreen pass). */
export function setFatResolution(world, width, height) {
  const set = fatMaterials.get(world);
  if (!set || set.size === 0) return 0;
  for (const material of set) material.resolution.set(width, height);
  return set.size;
}

/** Writes the canvas size (CSS pixels, what LineMaterial expects) onto every fat material of this world. */
export function syncResolution(world) {
  const set = fatMaterials.get(world);
  if (!set || set.size === 0) return;
  const size = world.renderer.three.getSize(new THREE.Vector2());
  setFatResolution(world, size.x, size.y);
}

function disposeLine(world, object) {
  object.geometry?.dispose();
  const material = object.material;
  const materials = Array.isArray(material) ? material : [material];
  for (const m of materials) {
    if (!m) continue;
    fatMaterials.get(world)?.delete(m);
    m.dispose();
  }
}

/** The coordinationMatrix translation of a loaded model, [0, 0, 0] when it has none. */
export function coordinationTranslation(model) {
  const e = model?.coordinationMatrix?.elements;
  return e ? [e[12], e[13], e[14]] : [0, 0, 0];
}

/**
 * Resolves each GUID once to its three anchor points - and, where a spec asks
 * for it, its floor outline - null when the element has no geometry loaded (a
 * streamed model's unfetched tiles - the anchors need the triangles, which the
 * tile metadata does not carry, so this is unchanged by the 2026-10-21 scope
 * fix; an aggregate such as IfcStair, whose parts carry the geometry).
 * @param {{components: any, fragments: any}} viewer
 * @param {any} model
 * @param {Map<string, {outline: boolean}>} needs
 */
async function resolveAnchors(viewer, model, needs) {
  const anchors = new Map();
  const wantsOutline = [...needs.values()].some((n) => n.outline);
  const index = model && wantsOutline ? await resolveGuidIndex(model) : null;
  for (const [guid, need] of needs) {
    const box = model ? await computeGuidsBoundingBox(viewer.components, model, [guid]) : null;
    if (!box) {
      anchors.set(guid, null);
      continue;
    }
    const c = box.getCenter(new THREE.Vector3());
    const entry = {
      center: [c.x, c.y, c.z],
      bottom: [c.x, box.min.y, c.z],
      top: [c.x, box.max.y, c.z],
      outline: null,
    };
    if (need.outline && index) {
      const location = index.get(guid);
      if (location) {
        const found = floorLoops(worldTrianglesOf(viewer.fragments, model, [location.expressID]));
        entry.outline = found?.loops.length ? found.loops : null;
      }
    }
    anchors.set(guid, entry);
  }
  return anchors;
}

function buildLine(world, spec, points, suffix = "") {
  const common = {
    color: new THREE.Color(spec.style.color),
    transparent: true,
    opacity: spec.style.opacity,
    depthTest: spec.style.depthTest,
    depthWrite: false,
  };
  let line;
  if (spec.style.width > 1) {
    const geometry = new LineGeometry();
    geometry.setPositions(points.flat());
    const material = new LineMaterial({
      ...common,
      linewidth: spec.style.width,
      worldUnits: false,
      dashed: spec.style.dashed,
      dashSize: spec.style.dashSize,
      gapSize: spec.style.gapSize,
    });
    fatMaterialsOf(world).add(material);
    line = new Line2(geometry, material);
    if (spec.style.dashed) line.computeLineDistances();
  } else {
    const geometry = new THREE.BufferGeometry().setFromPoints(
      points.map((p) => new THREE.Vector3(...p)),
    );
    line = new THREE.Line(geometry, new THREE.LineBasicMaterial(common));
  }
  line.name = spec.id + suffix;
  line.renderOrder = LINES_RENDER_ORDER;
  line.userData.lineId = spec.id;
  line.userData.meta = spec.meta;
  return line;
}

/**
 * Adds lines and shapes to a viewer's scene. Specs are normalized
 * (views/lineSpec.js, throws on a malformed one), anchors resolved against
 * the viewer's current model, and a spec whose id is already drawn replaces
 * it. A spec left with too few points for its kind is skipped and reported,
 * never thrown: a GUID without geometry is data, not a bug.
 *
 * @param {any} world - the viewer's @thatopen world
 * @param {Array<Record<string, any>>} specs
 * @param {{model?: any}} [options] - the model to resolve anchors against; defaults to the viewer's current one
 * @returns {Promise<{added: string[], skipped: Array<{id: string, reason: string}>}>}
 */
export async function addLines(world, specs, { model } = {}) {
  const entry = entryFor(world);
  const normalized = specs.map(normalizeLineSpec);
  const target =
    model ?? entry.getCurrentModel?.() ?? entry.fragments?.groups?.values().next().value ?? null;
  const anchors = await resolveAnchors(
    { components: world.components, fragments: entry.fragments },
    target,
    anchorNeeds(normalized),
  );
  const T = coordinationTranslation(target);
  const group = groupFor(world, true);
  const reg = registry(entry);
  const added = [];
  const skipped = [];
  for (const spec of normalized) {
    const { points, polylines, dropped } = resolveLinePoints(spec, { T, anchors });
    if (polylines.length === 0 || points.length < 2) {
      const why = dropped.length ? ` (no geometry for ${dropped.join(", ")})` : "";
      skipped.push({
        id: spec.id,
        reason:
          spec.kind === "outline"
            ? `no floor outline${why}`
            : `${points.length} of ${spec.points.length} points resolved${why}`,
      });
      continue;
    }
    const existing = reg.get(spec.id);
    if (existing) {
      for (const object of existing.objects) {
        group.remove(object);
        disposeLine(world, object);
      }
    }
    const objects = polylines.map((poly, i) => buildLine(world, spec, poly, i ? `#${i}` : ""));
    for (const object of objects) group.add(object);
    reg.set(spec.id, { spec, points, polylines, objects });
    added.push(spec.id);
  }
  syncResolution(world);
  announce(entry, { added, removed: [], skipped });
  return { added, skipped };
}

/**
 * Removes the named lines; unknown ids are ignored.
 * @returns {string[]} the ids actually removed
 */
export function removeLines(world, ids) {
  const entry = entryFor(world);
  const reg = registry(entry);
  const group = groupFor(world, false);
  const removed = [];
  for (const id of ids) {
    const hit = reg.get(id);
    if (!hit) continue;
    for (const object of hit.objects) {
      group?.remove(object);
      disposeLine(world, object);
    }
    reg.delete(id);
    removed.push(id);
  }
  if (group && group.children.length === 0) world.scene.three.remove(group);
  announce(entry, { added: [], removed, skipped: [] });
  return removed;
}

/** Removes every line of this viewer. @returns {number} how many there were */
export function clearLines(world) {
  const entry = findViewerByWorld(world);
  if (!entry) return 0;
  return removeLines(world, [...registry(entry).keys()]).length;
}

/** What is drawn, as data: `{id, spec, points, polylines}` per spec, in insertion order. */
export function listLines(world) {
  const entry = findViewerByWorld(world);
  if (!entry) return [];
  return [...registry(entry).values()].map(({ spec, points, polylines }) => ({
    id: spec.id,
    spec,
    points,
    polylines,
  }));
}
