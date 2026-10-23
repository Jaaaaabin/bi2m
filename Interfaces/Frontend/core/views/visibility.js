// ======== Visibility score: how much of each member a view actually shows ========
// The label-free reward: render every member in a unique flat colour into an
// offscreen target and count its pixels. Two passes:
//
//   A  members + everything else      -> pixels of each member that survive occlusion
//   B  members alone                  -> pixels each member would have unoccluded
//
// so per member: visible = A, unoccluded = B, occluded fraction = 1 − A/B;
// and for the view: frame fill = ΣA / pixels, members told apart = those with
// at least a few pixels. This is the measure that lets a batch reject a bad
// packet, a search rank candidate views, and a policy be rewarded - none of
// it needs a label.
//
// HOW THE IDS GET INTO THE PICTURE. The pass renders with
// `scene.overrideMaterial`, an unlit white MeshBasicMaterial. three.js keeps
// an InstancedMesh's per-instance colour in the shader whatever material is
// overriding (the define comes from the object, not the material), so a
// member's id is written into its instance colour for the pass and the
// material multiplies white by it: the output IS the id. Everything else
// keeps the identity colour the base gray leaves in every instance
// (highlighting.js, applyBaseGrayToFragments: `instanceColor.fill(1)`), so
// non-members read back white, and the cleared background black. Ids use a
// fixed blue byte so neither can be mistaken for one.
//
// A member's instance is written where it currently lives: in the Refer
// split's CLONE when a Refer is active (the origin instance is hidden), in
// its origin fragment otherwise. Every instance-colour buffer touched is
// copied first and restored after, byte for byte.
//
// The render is linear, un-multisampled, with no background (views/render.js
// `linear: true`), so an id is never blended with a neighbour. Number labels
// (views/labels.js) are hidden for the passes: an overridden sprite would be
// a white blob counted as "other".
//
// WHAT A ZERO MEANS. The pass makes everything opaque, so a member inside the
// building is occluded by its walls and slabs however transparent they are on
// screen: at a Refer's own view of a column stack all four columns score 0
// visible against hundreds of unoccluded pixels (measured, 2026-10-01). That
// is the measure doing its job - interiors need a cut - and a section box
// around the intent brings visible up to unoccluded. Pass B renders with
// `forceVisible: false`: render.js's culling workaround would otherwise
// re-show every mesh this pass hides.

import * as THREE from "three";

import { resolveGuidIndex } from "../highlighting.js";
import { findViewerByWorld } from "../viewerRegistry.js";
import { renderOffscreen } from "./render.js";
import { decodeId, encodeId } from "./snapshotMeta.js";

/** Blue byte every member id carries; white (non-member) and black (nothing) never have it. */
const ID_BLUE = 64;
/** A member with fewer visible pixels than this is not "told apart" in the image. */
export const MIN_DISTINCT_PIXELS = 4;
/** Default size of the scoring render; the aspect follows the canvas. */
export const DEFAULT_SCORE_HEIGHT = 512;

const idColor = (index) => new THREE.Color((index & 0xff) / 255, ((index >> 8) & 0xff) / 255, ID_BLUE / 255);
const idFromPixel = (r, g, b) => (b === ID_BLUE ? r + (g << 8) : -1);

/**
 * Where each GUID's instances currently render: the clone fragment during a
 * Refer, the origin fragment otherwise.
 * @returns {Promise<Array<{guid: string, fragment: any, expressID: number} | null>>}
 */
async function locateMembers(entry, model, guids) {
  const index = await resolveGuidIndex(model);
  const splits = entry.referSplits ?? [];
  return guids.map((guid) => {
    const location = index.get(guid);
    if (!location) return null;
    for (const split of splits) {
      if (split.fragment.id === location.fragmentID && split.itemIds.includes(location.expressID)) {
        return { guid, fragment: split.referredFragment, expressID: location.expressID };
      }
    }
    const fragment = entry.fragments.list.get(location.fragmentID);
    return fragment ? { guid, fragment, expressID: location.expressID } : null;
  });
}

/**
 * Scores the current camera for a set of members.
 *
 * @param {any} world
 * @param {{guids: string[], height?: number, camera?: THREE.Camera | null}} options - `guids` are the
 *   members to score (context-role members excluded by the caller); `camera` defaults to the live one.
 * @returns {Promise<{
 *   members: Array<{guid: string, visiblePx: number, unoccludedPx: number, visibleFraction: number, occludedFraction: number, distinct: boolean}>,
 *   membersTotal: number, membersLocated: number, membersDistinct: number,
 *   frameFill: number, otherPx: number, unknownPx: number, image: {width: number, height: number}
 * }>}
 */
export async function measureVisibility(world, { guids, height = DEFAULT_SCORE_HEIGHT, camera = null }) {
  const entry = findViewerByWorld(world);
  if (!entry) throw new Error("measureVisibility: this world has no viewer entry");
  const model = entry.getCurrentModel?.();
  if (!model) throw new Error("measureVisibility: no model is loaded");

  const canvas = world.renderer.three.domElement;
  const aspect = canvas.width / Math.max(1, canvas.height);
  const width = Math.max(1, Math.round(height * aspect));

  const located = await locateMembers(entry, model, guids);
  const snapshots = new Map(); // mesh -> original instanceColor array
  const touched = new Set();
  const labels = world.scene.three.getObjectByName("bi2m-view-labels");
  const labelsWereVisible = labels ? labels.visible : false;

  const overrideMaterial = new THREE.MeshBasicMaterial({ color: 0xffffff, toneMapped: false });
  overrideMaterial.side = THREE.DoubleSide;

  const count = (frame) => {
    const px = frame.pixels;
    const perId = new Map();
    let other = 0;
    let unknown = 0;
    for (let i = 0; i < px.length; i += 4) {
      const r = px[i];
      const g = px[i + 1];
      const b = px[i + 2];
      if (r === 0 && g === 0 && b === 0) continue; // nothing
      if (r === 255 && g === 255 && b === 255) {
        other++;
        continue;
      }
      const id = idFromPixel(r, g, b);
      if (id < 0) unknown++;
      else perId.set(id, (perId.get(id) ?? 0) + 1);
    }
    return { perId, other, unknown, total: frame.width * frame.height };
  };

  try {
    located.forEach((loc, i) => {
      if (!loc) return;
      const mesh = loc.fragment.mesh;
      if (!mesh?.instanceColor) return;
      if (!snapshots.has(mesh)) snapshots.set(mesh, mesh.instanceColor.array.slice());
      loc.fragment.setColor(idColor(i + 1), [loc.expressID], true);
      touched.add(mesh);
    });
    if (labels) labels.visible = false;

    const passA = count(renderOffscreen(world, { width, height, linear: true, background: null, overrideMaterial, camera }));

    // Pass B: members alone - every other fragment mesh off, the touched
    // meshes on even if the live frustum culled them (a touched origin
    // fragment also carries non-members, which then read back white and are
    // not counted for anyone). `forceVisible: false`, see the header.
    const hidden = [];
    const shown = [];
    for (const group of entry.fragments.groups.values()) {
      for (const fragment of group.items) {
        const mesh = fragment.mesh;
        if (!mesh) continue;
        if (touched.has(mesh)) {
          if (!mesh.visible) {
            shown.push(mesh);
            mesh.visible = true;
          }
        } else if (mesh.visible) {
          hidden.push(mesh);
          mesh.visible = false;
        }
      }
    }
    for (const split of entry.referSplits ?? []) {
      const mesh = split.referredFragment.mesh;
      if (mesh && !touched.has(mesh) && mesh.visible) {
        hidden.push(mesh);
        mesh.visible = false;
      }
    }
    let passB;
    try {
      passB = count(
        renderOffscreen(world, { width, height, linear: true, background: null, overrideMaterial, camera, forceVisible: false }),
      );
    } finally {
      for (const mesh of hidden) mesh.visible = true;
      for (const mesh of shown) mesh.visible = false;
    }

    const members = located.map((loc, i) => {
      const id = i + 1;
      const visiblePx = passA.perId.get(id) ?? 0;
      const unoccludedPx = passB.perId.get(id) ?? 0;
      return {
        guid: guids[i],
        located: !!loc,
        visiblePx,
        unoccludedPx,
        visibleFraction: unoccludedPx > 0 ? visiblePx / unoccludedPx : 0,
        occludedFraction: unoccludedPx > 0 ? 1 - visiblePx / unoccludedPx : 1,
        distinct: visiblePx >= MIN_DISTINCT_PIXELS,
      };
    });
    const memberPx = members.reduce((s, m) => s + m.visiblePx, 0);
    return {
      members,
      membersTotal: guids.length,
      membersLocated: located.filter(Boolean).length,
      membersDistinct: members.filter((m) => m.distinct).length,
      frameFill: memberPx / passA.total,
      otherPx: passA.other,
      unknownPx: passA.unknown,
      image: { width, height },
    };
  } finally {
    for (const [mesh, array] of snapshots) {
      mesh.instanceColor.array.set(array);
      mesh.instanceColor.needsUpdate = true;
    }
    if (labels) labels.visible = labelsWereVisible;
    overrideMaterial.dispose();
  }
}

// ======== Whole-model ID pass: every element the picture shows (2026-10-22) ========
// The snapshot metadata's "visible" and "ghosted" lists (views/snapshotMeta.js,
// snapshot.js captureViewWithMetadata). Same machinery as measureVisibility
// above, over EVERY instance of EVERY fragment instead of a member list, with
// a 24-bit id per element (encodeId) written straight into each mesh's
// instance-colour bytes through the fragment's `instanceToItem` map - which
// covers every allocated slot, hidden ones included (they sit past
// `mesh.count` and are simply not drawn), and never through
// `fragment.setColor`, whose per-item "original colour" bookkeeping would
// then remember id colours. Buffers are restored byte for byte.
//
// The picture-faithful rule (owner's choice, 2026-10-22): an element drawn
// through a transparent material - the Refer's 90 % ghost, or any
// transparency slider setting - neither occludes nor counts as visible, and
// is listed as `ghosted` instead when it has pixels of its own on screen.
// Two renders: V, with every ghost mesh hidden, counts `visible`; C, the
// scene as the picture shows it with the ghost meshes drawn SOLID, counts
// `ghosted` among the ghost meshes' ids - the front-most ghost layer only: an
// opaque element in front of a ghost hides it in both, and a ghost behind
// another ghost is not listed although the picture shows it faintly. The ghost is
// a property of the MESH's material, so the Refer's opaque clones (which
// live outside fragments.groups, transparency.js) count as visible for the
// referred elements while their hidden origin instances are never drawn.
//
// Synchronous on purpose, like captureWorldPng: the caller resolves the GUID
// index first, then takes the picture and this pass in one block so both
// describe one frame.

/**
 * @param {any} world
 * @param {{index: Map<string, {fragmentID: string, expressID: number}>, width: number, height: number,
 *   camera?: THREE.Camera | null, minPixels?: number}} options - `index` is the model's GUID index
 *   (highlighting.resolveGuidIndex, awaited by the caller); width/height the picture's size.
 * @returns {{visible: Array<{guid: string, px: number}>, ghosted: Array<{guid: string, px: number}>,
 *   unresolved: number, ghostMeshes: number, meshesWithoutInstanceColor: number, image: {width: number, height: number}}}
 */
export function visibleElements(world, { index, width, height, camera = null, minPixels = 1 }) {
  const entry = findViewerByWorld(world);
  if (!entry) throw new Error("visibleElements: this world has no viewer entry");
  const model = entry.getCurrentModel?.();
  if (!model) throw new Error("visibleElements: no model is loaded");

  const guidOf = new Map();
  for (const [guid, location] of index) guidOf.set(location.expressID, guid);

  const meshes = [];
  for (const group of entry.fragments.groups.values()) {
    for (const fragment of group.items) if (fragment.mesh) meshes.push({ fragment, mesh: fragment.mesh });
  }
  for (const split of entry.referSplits ?? []) {
    if (split.referredFragment?.mesh) meshes.push({ fragment: split.referredFragment, mesh: split.referredFragment.mesh });
  }
  const isGhost = (mesh) => {
    const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
    return materials.some((m) => m && m.transparent && m.opacity < 1);
  };

  const expressOfId = [null]; // id -> expressID; one id per element, origin and clone alike
  const idOfExpress = new Map();
  const snapshots = new Map(); // mesh -> original instanceColor bytes
  const ghosts = new Set();
  const ghostIds = new Set();
  let meshesWithoutInstanceColor = 0;
  const labels = world.scene.three.getObjectByName("bi2m-view-labels");
  const labelsWereVisible = labels ? labels.visible : false;
  const overrideMaterial = new THREE.MeshBasicMaterial({ color: 0xffffff, toneMapped: false });
  overrideMaterial.side = THREE.DoubleSide;

  const count = (frame) => {
    const px = frame.pixels;
    const perId = new Map();
    for (let i = 0; i < px.length; i += 4) {
      const id = decodeId(px[i], px[i + 1], px[i + 2]);
      if (id < 0) continue;
      perId.set(id, (perId.get(id) ?? 0) + 1);
    }
    return perId;
  };

  try {
    for (const { fragment, mesh } of meshes) {
      const attribute = mesh.instanceColor;
      if (!attribute) {
        meshesWithoutInstanceColor++; // renders white under the override: uncounted, still occludes
        continue;
      }
      snapshots.set(mesh, attribute.array.slice());
      const array = attribute.array;
      const stride = attribute.itemSize;
      const ghost = isGhost(mesh);
      if (ghost) ghosts.add(mesh);
      for (const [instance, itemID] of fragment.instanceToItem) {
        let id = idOfExpress.get(itemID);
        if (id === undefined) {
          id = expressOfId.length;
          expressOfId.push(itemID);
          idOfExpress.set(itemID, id);
        }
        const [r, g, b] = encodeId(id);
        array[instance * stride] = r;
        array[instance * stride + 1] = g;
        array[instance * stride + 2] = b;
        if (ghost) ghostIds.add(id);
      }
      attribute.needsUpdate = true;
    }
    if (labels) labels.visible = false;

    const hiddenGhosts = [];
    for (const mesh of ghosts) {
      if (mesh.visible) {
        mesh.visible = false;
        hiddenGhosts.push(mesh);
      }
    }
    let passV;
    try {
      passV = count(renderOffscreen(world, { width, height, linear: true, background: null, overrideMaterial, camera, forceVisible: false }));
    } finally {
      for (const mesh of hiddenGhosts) mesh.visible = true;
    }
    const passC = ghosts.size
      ? count(renderOffscreen(world, { width, height, linear: true, background: null, overrideMaterial, camera, forceVisible: false }))
      : new Map();

    let unresolved = 0;
    const visible = [];
    const visibleGuids = new Set();
    for (const [id, px] of passV) {
      if (px < minPixels) continue;
      const guid = guidOf.get(expressOfId[id]);
      if (!guid) {
        unresolved++;
        continue;
      }
      visible.push({ guid, px });
      visibleGuids.add(guid);
    }
    const ghosted = [];
    for (const [id, px] of passC) {
      if (px < minPixels || !ghostIds.has(id)) continue;
      const guid = guidOf.get(expressOfId[id]);
      if (!guid) {
        unresolved++;
        continue;
      }
      if (!visibleGuids.has(guid)) ghosted.push({ guid, px });
    }
    return { visible, ghosted, unresolved, ghostMeshes: ghosts.size, meshesWithoutInstanceColor, image: { width, height } };
  } finally {
    for (const [mesh, array] of snapshots) {
      mesh.instanceColor.array.set(array);
      mesh.instanceColor.needsUpdate = true;
    }
    if (labels) labels.visible = labelsWereVisible;
    overrideMaterial.dispose();
  }
}
