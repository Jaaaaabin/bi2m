// ======== Floor outlines: a room's exact footprint from its geometry ========
// The irregular shape the model already knows: an IfcSpace's floor is a
// polygon, often L-shaped or notched, and nothing in the intent records
// carries it. This reads it off the loaded fragments.
//
// Two halves. `worldTrianglesOf` is the live part: an item's triangles in
// world space, through each instance matrix and the mesh's matrixWorld (the
// same route views/frame.js takes for wall directions), skipping the (0,0,0)
// index triplets fragments use for removed triangles. `floorLoops` is pure
// and unit-tested: keep the faces that point DOWN (normal y below
// DOWN_NORMAL_Y), take the lowest of them, keep every downward face within
// FLOOR_BAND_M of it - that is the floor - and walk its boundary.
//
// The boundary of a set of triangles is the set of edges used by exactly one
// of them: a shared edge is counted twice and drops out, a diagonal from the
// triangulation with it. Edges are keyed undirected, so inconsistent winding
// cannot leave a false boundary, and vertices are keyed to VERTEX_KEY_DECIMALS
// (a millimetre): two triangles sharing an edge agree to that because they
// read the same index buffer. Chained, the boundary edges give one loop per
// ring - an outer ring and one more per hole (a column standing in the room).
// Loops come out longest first and lie at the floor's height, so a sloped or
// stepped underside still gives a flat line. Collinear vertices left by the
// triangulation (T-junctions) are dropped, so a rectangle is four points.
//
// ASSUMES A CONFORMING TRIANGULATION: two triangles that touch along a line
// share that whole edge, which holds inside one tessellated face. A floor
// made of several solids that merely touch (an IfcSpace with more than one
// representation item) shares no edge across the seam and comes out as one
// loop per solid - still correct outlines, just more of them.
//
// Measured on example_autcon.ifc before this module existed (session probe,
// 2026-10-01): 12 of 12 spaces gave exactly one closed loop - 4 vertices for
// the box-shaped rooms, 9 and 12 for the two irregular ones.

import * as THREE from "three";

/** A face counts as pointing down when its unit normal's y is below this. */
export const DOWN_NORMAL_Y = -0.7;
/** Downward faces this close (metres) to the lowest one are the floor. */
export const FLOOR_BAND_M = 0.3;
/** Vertex keys are rounded to this many decimals: a millimetre. */
export const VERTEX_KEY_DECIMALS = 3;
/** Two consecutive edges within this of parallel (dot of unit vectors) merge. */
const COLLINEAR_DOT = 0.99996;

const vertexKey = (p) => p.map((c) => c.toFixed(VERTEX_KEY_DECIMALS)).join(",");

/**
 * World-space triangles of the given items, across every fragment and
 * instance they occupy.
 * @param {{list: Map<string, any>}} fragments - the viewer's FragmentsManager
 * @param {any} model - the FragmentsGroup
 * @param {Iterable<number>} expressIDs
 * @returns {number[][][]} triangles as [[x,y,z], [x,y,z], [x,y,z]]
 */
export function worldTrianglesOf(fragments, model, expressIDs) {
  const triangles = [];
  const fragMap = model?.getFragmentMap?.(expressIDs) ?? {};
  const matrix = new THREE.Matrix4();
  const a = new THREE.Vector3();
  const b = new THREE.Vector3();
  const c = new THREE.Vector3();
  for (const [fragmentID, itemIDs] of Object.entries(fragMap)) {
    const fragment = fragments.list.get(fragmentID);
    const mesh = fragment?.mesh;
    const geometry = mesh?.geometry;
    const position = geometry?.attributes?.position;
    const index = geometry?.index;
    if (!position || !index) continue;
    mesh.updateWorldMatrix(true, false);
    for (const itemID of itemIDs) {
      const instances = fragment.getInstancesIDs(Number(itemID));
      if (!instances) continue;
      for (const instance of instances) {
        mesh.getMatrixAt(instance, matrix);
        matrix.premultiply(mesh.matrixWorld);
        for (let k = 0; k + 2 < index.count; k += 3) {
          const ia = index.getX(k);
          const ib = index.getX(k + 1);
          const ic = index.getX(k + 2);
          if (ia === 0 && ib === 0 && ic === 0) continue;
          a.fromBufferAttribute(position, ia).applyMatrix4(matrix);
          b.fromBufferAttribute(position, ib).applyMatrix4(matrix);
          c.fromBufferAttribute(position, ic).applyMatrix4(matrix);
          triangles.push([
            [a.x, a.y, a.z],
            [b.x, b.y, b.z],
            [c.x, c.y, c.z],
          ]);
        }
      }
    }
  }
  return triangles;
}

/**
 * Unit normal of a triangle, or null when it is degenerate.
 * @param {number[][]} tri
 */
function unitNormal(tri) {
  const [p, q, r] = tri;
  const ux = q[0] - p[0];
  const uy = q[1] - p[1];
  const uz = q[2] - p[2];
  const vx = r[0] - p[0];
  const vy = r[1] - p[1];
  const vz = r[2] - p[2];
  const n = [uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx];
  const len = Math.hypot(n[0], n[1], n[2]);
  return len > 0 ? n.map((c) => c / len) : null;
}

/**
 * Drops vertices that lie on the straight line between their neighbours (the
 * loop is treated as closed), and consecutive duplicates.
 * @param {number[][]} loop
 * @returns {number[][]}
 */
export function simplifyLoop(loop) {
  const pts = loop.filter((p, i) => i === 0 || vertexKey(p) !== vertexKey(loop[i - 1]));
  if (pts.length > 1 && vertexKey(pts[0]) === vertexKey(pts[pts.length - 1])) pts.pop();
  let changed = true;
  while (changed && pts.length > 3) {
    changed = false;
    for (let i = 0; i < pts.length; i++) {
      const prev = pts[(i - 1 + pts.length) % pts.length];
      const cur = pts[i];
      const next = pts[(i + 1) % pts.length];
      const d1 = [cur[0] - prev[0], cur[1] - prev[1], cur[2] - prev[2]];
      const d2 = [next[0] - cur[0], next[1] - cur[1], next[2] - cur[2]];
      const l1 = Math.hypot(...d1);
      const l2 = Math.hypot(...d2);
      if (!(l1 > 0) || !(l2 > 0)) continue;
      const dot = (d1[0] * d2[0] + d1[1] * d2[1] + d1[2] * d2[2]) / (l1 * l2);
      if (dot > COLLINEAR_DOT) {
        pts.splice(i, 1);
        changed = true;
        break;
      }
    }
  }
  return pts;
}

/**
 * The floor outline(s) of a set of triangles.
 * @param {number[][][]} triangles - world-space, as worldTrianglesOf returns them
 * @returns {{y: number, loops: number[][][]} | null} loops longest first, each an
 *   open ring of [x, y, z] at the floor height `y`; null when nothing points down
 */
export function floorLoops(triangles) {
  const down = [];
  let minY = Infinity;
  for (const tri of triangles) {
    const n = unitNormal(tri);
    if (!n || n[1] >= DOWN_NORMAL_Y) continue;
    down.push(tri);
    for (const p of tri) if (p[1] < minY) minY = p[1];
  }
  if (down.length === 0) return null;
  const floor = down.filter((tri) => tri.every((p) => p[1] <= minY + FLOOR_BAND_M));

  /** @type {Map<string, {a: number[], b: number[], ka: string, kb: string, count: number}>} */
  const edges = new Map();
  for (const tri of floor) {
    for (let e = 0; e < 3; e++) {
      const p = tri[e];
      const q = tri[(e + 1) % 3];
      const kp = vertexKey(p);
      const kq = vertexKey(q);
      if (kp === kq) continue;
      const key = kp < kq ? `${kp}|${kq}` : `${kq}|${kp}`;
      const rec = edges.get(key);
      if (rec) rec.count += 1;
      else edges.set(key, { a: p, b: q, ka: kp, kb: kq, count: 1 });
    }
  }
  const boundary = [...edges.values()].filter((e) => e.count === 1);
  /** @type {Map<string, typeof boundary>} */
  const adjacency = new Map();
  /** @type {Map<string, number[]>} */
  const vertexOf = new Map();
  for (const e of boundary) {
    (adjacency.get(e.ka) ?? adjacency.set(e.ka, []).get(e.ka)).push(e);
    (adjacency.get(e.kb) ?? adjacency.set(e.kb, []).get(e.kb)).push(e);
    vertexOf.set(e.ka, e.a);
    vertexOf.set(e.kb, e.b);
  }

  const used = new Set();
  const loops = [];
  for (const start of boundary) {
    if (used.has(start)) continue;
    used.add(start);
    const ring = [vertexOf.get(start.ka)];
    let cursor = start.kb;
    let guard = 0;
    while (cursor !== start.ka && guard++ < 1_000_000) {
      ring.push(vertexOf.get(cursor));
      const next = (adjacency.get(cursor) ?? []).find((e) => !used.has(e));
      if (!next) break;
      used.add(next);
      cursor = next.ka === cursor ? next.kb : next.ka;
    }
    const flat = simplifyLoop(ring.map((p) => [p[0], minY, p[2]]));
    if (flat.length >= 3) loops.push(flat);
  }
  loops.sort((p, q) => q.length - p.length);
  return { y: minY, loops };
}
