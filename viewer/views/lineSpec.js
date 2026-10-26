// ======== Line specs: the data a viewer line or shape is made from ========
// A line in the viewer is a JSON record first and a THREE object second. This
// module is the record side: defaults, validation and the pure geometry
// (coordinate conversion, sorting, flattening, extension, and turning a kind
// into the polyline(s) that get drawn). It imports no viewer code, so it runs
// in node and is unit-tested; views/lines.js is the live half that resolves
// anchors against the loaded model and owns the scene objects.
//
// Two ways to say where a vertex is, mixable within one spec:
//
//   coordinates   [x, y, z] in `scene` space (three.js world, Y up), or
//                 [x, y] in `ifcPlan` space (the detectors' plan metres) with
//                 a `height` - a scene Y, an anchor whose y is used, or
//                 {ifcZ} in the file's own world metres;
//   anchors       {guid, at}: a point on an element, resolved at draw time
//                 from its bounding box - "link components".
//
// Seven kinds, each with its own vertex count and fields (KIND_RULES):
//
//   kind      vertices  extra fields                  sortAlong/extend  flattenY
//   segment   2         -                             yes               yes
//   polyline  2+        -                             yes               yes
//   polygon   3+        - (closed on draw)            no                yes
//   spline    2+        samples, closed               no                yes
//   circle    1 centre  radius, segments, plane       no                yes
//   arc       1 centre  radius, startDeg, endDeg,     no                yes
//                       segments, plane
//   outline   1 anchor  - (the element's floor        no                no
//                       outline, views/outline.js)
//
// A field a kind does not take is REJECTED, not ignored: a spec is authored
// data, and a silent default would hide the author's mistake.
//
// Pipeline, in this order: resolve vertices -> sort along `sortAlong`
// (segment, polyline) -> flatten to `flattenY` -> extend the ends (segment,
// polyline) -> expand the kind (close, sample, or take the outline).
//
// `ifcPlan` converts with the formula views/intentFrame.js measured (phase 0
// of scripts/e2e/views.py): scene = (x + T.x, height, −y + T.z), T the
// translation of the model's coordinationMatrix. The vertical part, scene
// Y = z + T.y, was measured 2026-10-06 against web-ifc 0.0.66's own column
// geometry (1 mm, on a millimetre model with its site rotated -9 degrees and
// on one more); that is what `height: {ifcZ}` uses. It exists because T is
// chosen when the model loads and depends on the host: web-ifc called
// directly gave T.y = 6.06 m, 4.10 m and 0 on three models, this viewer's
// loader and tile sets 1.90 m, -1.05 m and -1.04 m on the same files. So a
// file written before loading - a declared grid's sidecar,
// scripts/grid_lines.py - cannot give a scene Y. A 3D `ifc` space is still
// RESERVED, not offered.
//
// `sortAlong` exists because anchors arrive in member order, and `extend`
// lengthens whichever vertices come first and last: collinear points trace
// the same line in any order, but an interior point used as an end would
// extend sideways. Sorting along the line's scene axis makes the ends the
// real ends.
//
// `flattenY` exists because a grid-line record spans storeys: its members'
// feet sit at several heights, and a polyline through them sorted along the
// line climbs a floor, runs, drops and climbs again - a sawtooth, not a grid
// line (measured on example_autcon.ifc before this option existed: all 12
// grid_line_* records zigzagged, up to 13.1 m of vertical spread). Flattening
// every point to one height - the lowest foot, the highest, or a given metre -
// after the sort and before the extension makes it one plan line.

import * as THREE from "three";

import { ifcPlanToScene } from "./intentFrame.js";

export const LINE_SPEC_SCHEMA = 2;
export const LINE_SPACES = Object.freeze(["scene", "ifcPlan"]);
export const LINE_KINDS = Object.freeze([
  "segment",
  "polyline",
  "polygon",
  "spline",
  "circle",
  "arc",
  "outline",
]);
export const ANCHOR_AT = Object.freeze(["center", "bottom", "top"]);
export const SORT_AXES = Object.freeze(["x", "y", "z"]);
export const FLATTEN_MODES = Object.freeze(["min", "max"]);
/** Plane of a circle or arc: the two scene axes it spans. `xz` is the plan. */
export const PLANES = Object.freeze(["xz", "xy", "yz"]);
/**
 * `width` is in CSS pixels: 1 draws a plain THREE.Line (WebGL's only native
 * width), anything above it a fat line (three/examples/jsm/lines) that is
 * also the only kind that can be `dashed`; `dashSize` and `gapSize` are
 * metres along the line.
 */
export const DEFAULT_LINE_STYLE = Object.freeze({
  color: "#ff6a00",
  opacity: 1,
  depthTest: false,
  width: 1,
  dashed: false,
  dashSize: 0.5,
  gapSize: 0.25,
});
export const DEFAULT_CIRCLE_SEGMENTS = 64;
export const DEFAULT_SPLINE_SAMPLES = 8;

/**
 * What each kind takes: vertex count, and which optional fields are its own.
 * `line`: sortAlong/extend apply; `round`: radius/segments/plane; `arc`:
 * startDeg/endDeg; `spline`: samples/closed; `outline`: one anchor, no flatten.
 */
export const KIND_RULES = Object.freeze({
  segment: { min: 2, max: 2, line: true },
  polyline: { min: 2, max: Infinity, line: true },
  polygon: { min: 3, max: Infinity },
  spline: { min: 2, max: Infinity, spline: true },
  circle: { min: 1, max: 1, round: true },
  arc: { min: 1, max: 1, round: true, arc: true },
  outline: { min: 1, max: 1, outline: true },
});

/** Axis indices a plane spans: [first, second]; the angle runs from the first toward the second. */
const PLANE_AXES = Object.freeze({ xz: [0, 2], xy: [0, 1], yz: [2, 1] });

let sequence = 0;
/** A fresh id for a spec that names none: `line-<n>`, unique within the page. */
export function nextLineId() {
  sequence += 1;
  return `line-${sequence}`;
}

/** True for a height in the file's world metres ({ifcZ}), turned into scene Y at draw time. */
export function isIfcHeight(height) {
  return !!height && typeof height === "object" && !Array.isArray(height) && "ifcZ" in height;
}

/** True for an anchor vertex ({guid, at}), false for a coordinate vertex. */
export function isAnchor(vertex) {
  return (
    !!vertex &&
    typeof vertex === "object" &&
    !Array.isArray(vertex) &&
    typeof vertex.guid === "string"
  );
}

const finite = (v) => typeof v === "number" && Number.isFinite(v);
const isInt = (v, min) => Number.isInteger(v) && v >= min;
const fail = (msg) => {
  throw new Error(`line spec: ${msg}`);
};

function normalizeAnchor(a, what) {
  const at = a.at ?? "center";
  if (!ANCHOR_AT.includes(at)) fail(`${what} has unknown anchor "${at}" (${ANCHOR_AT.join(", ")})`);
  return { guid: a.guid, at };
}

/**
 * Fills defaults and validates one spec. Throws on a malformed one.
 *
 * @param {Record<string, any>} spec
 * @returns {{id: string, kind: string, space: string, points: any[],
 *            height: number | {guid: string, at: string} | {ifcZ: number} | null,
 *            sortAlong: string | null, flattenY: string | number | null, extend: number,
 *            radius: number | null, startDeg: number | null, endDeg: number | null, segments: number | null,
 *            plane: string | null, samples: number | null, closed: boolean | null,
 *            style: {color: string, opacity: number, depthTest: boolean, width: number, dashed: boolean,
 *                    dashSize: number, gapSize: number}, meta: Record<string, any>}}
 */
export function normalizeLineSpec(spec) {
  if (!spec || typeof spec !== "object") fail("not an object");
  const points = Array.isArray(spec.points) ? spec.points : null;
  if (!points || points.length === 0) fail("needs points");
  let kind = spec.kind ?? null;
  if (kind === null) {
    if (points.length === 1) fail("a single point needs an explicit kind (circle, arc or outline)");
    kind = points.length === 2 ? "segment" : "polyline";
  }
  if (!LINE_KINDS.includes(kind)) fail(`unknown kind "${kind}" (${LINE_KINDS.join(", ")})`);
  const rules = KIND_RULES[kind];
  if (points.length < rules.min)
    fail(
      `a ${kind} needs at least ${rules.min} point${rules.min === 1 ? "" : "s"} (got ${points.length})`,
    );
  if (points.length > rules.max)
    fail(
      `a ${kind} takes at most ${rules.max} point${rules.max === 1 ? "" : "s"} (got ${points.length})`,
    );

  const space = spec.space ?? "scene";
  if (!LINE_SPACES.includes(space)) fail(`unknown space "${space}" (${LINE_SPACES.join(", ")})`);

  const normalizedPoints = points.map((p, i) => {
    if (isAnchor(p)) return normalizeAnchor(p, `point ${i}`);
    if (rules.outline) fail("an outline takes one anchor {guid}, not coordinates");
    const n = space === "ifcPlan" ? 2 : 3;
    if (!Array.isArray(p) || p.length !== n || !p.every(finite)) {
      fail(`point ${i} must be ${n} finite numbers in ${space} space, or an anchor {guid, at}`);
    }
    return [...p];
  });

  let height = spec.height ?? null;
  if (height !== null) {
    if (isAnchor(height)) height = normalizeAnchor(height, "height");
    else if (isIfcHeight(height)) {
      if (!finite(height.ifcZ)) fail("height.ifcZ must be a number of metres");
      height = { ifcZ: height.ifcZ };
    } else if (!finite(height))
      fail("height must be a number (scene Y), an anchor {guid, at} or {ifcZ}");
  }
  const needsHeight = space === "ifcPlan" && normalizedPoints.some((p) => Array.isArray(p));
  if (needsHeight && height === null)
    fail("ifcPlan coordinates need a `height` (scene Y, an anchor, or {ifcZ})");

  const sortAlong = spec.sortAlong ?? null;
  const extend = spec.extend ?? 0;
  if (rules.line) {
    if (sortAlong !== null && !SORT_AXES.includes(sortAlong)) fail("sortAlong must be x, y or z");
    if (!finite(extend) || extend < 0) fail("extend must be a non-negative number of metres");
  } else if (sortAlong !== null || extend !== 0) {
    fail(`sortAlong and extend apply to segment and polyline, not ${kind}`);
  }

  const flattenY = spec.flattenY ?? null;
  if (flattenY !== null) {
    if (rules.outline) fail("flattenY does not apply to an outline (it is already at its floor)");
    if (!FLATTEN_MODES.includes(flattenY) && !finite(flattenY))
      fail('flattenY must be "min", "max" or a scene height in metres');
  }

  let radius = null;
  let segments = null;
  let plane = null;
  let startDeg = null;
  let endDeg = null;
  if (rules.round) {
    radius = spec.radius;
    if (!finite(radius) || radius <= 0) fail(`a ${kind} needs a radius > 0 (metres)`);
    plane = spec.plane ?? "xz";
    if (!PLANES.includes(plane)) fail(`plane must be ${PLANES.join(", ")}`);
    if (rules.arc) {
      startDeg = spec.startDeg;
      endDeg = spec.endDeg;
      if (!finite(startDeg) || !finite(endDeg)) fail("an arc needs startDeg and endDeg");
      if (startDeg === endDeg) fail("an arc needs startDeg and endDeg to differ");
    } else if (spec.startDeg !== undefined || spec.endDeg !== undefined) {
      fail("startDeg and endDeg apply to an arc, not a circle");
    }
    const span = rules.arc ? Math.abs(endDeg - startDeg) : 360;
    segments = spec.segments ?? Math.max(8, Math.round((DEFAULT_CIRCLE_SEGMENTS * span) / 360));
    if (!isInt(segments, rules.arc ? 1 : 3))
      fail(`segments must be an integer >= ${rules.arc ? 1 : 3}`);
  } else {
    for (const f of ["radius", "segments", "plane", "startDeg", "endDeg"]) {
      if (spec[f] !== undefined) fail(`${f} applies to circle and arc, not ${kind}`);
    }
  }

  let samples = null;
  let closed = null;
  if (rules.spline) {
    samples = spec.samples ?? DEFAULT_SPLINE_SAMPLES;
    if (!isInt(samples, 1)) fail("samples must be an integer >= 1");
    closed = Boolean(spec.closed ?? false);
  } else if (spec.samples !== undefined || spec.closed !== undefined) {
    fail(`samples and closed apply to a spline, not ${kind}`);
  }

  const style = { ...DEFAULT_LINE_STYLE, ...(spec.style ?? {}) };
  if (typeof style.color !== "string") fail("style.color must be a CSS colour string");
  if (!finite(style.opacity) || style.opacity < 0 || style.opacity > 1)
    fail("style.opacity must be in [0, 1]");
  style.depthTest = Boolean(style.depthTest);
  if (!finite(style.width) || style.width < 1) fail("style.width must be a number of pixels >= 1");
  style.dashed = Boolean(style.dashed);
  if (style.dashed && style.width <= 1) fail("style.dashed needs style.width above 1 (a fat line)");
  if (
    !finite(style.dashSize) ||
    style.dashSize <= 0 ||
    !finite(style.gapSize) ||
    style.gapSize <= 0
  ) {
    fail("style.dashSize and style.gapSize must be positive metres");
  }

  return {
    id: typeof spec.id === "string" && spec.id ? spec.id : nextLineId(),
    kind,
    space,
    points: normalizedPoints,
    height,
    sortAlong: rules.line ? sortAlong : null,
    flattenY,
    extend: rules.line ? extend : 0,
    radius,
    startDeg,
    endDeg,
    segments,
    plane,
    samples,
    closed,
    style,
    meta: spec.meta && typeof spec.meta === "object" ? { ...spec.meta } : {},
  };
}

/** Every distinct GUID the specs' anchors name (points and heights), so the live side resolves each once. */
export function anchorGuids(specs) {
  return new Set(anchorNeeds(specs).keys());
}

/**
 * What the live side must resolve per GUID: every anchor needs its bounding
 * box; an outline's anchor also needs its floor outline, which is heavier.
 * @returns {Map<string, {outline: boolean}>}
 */
export function anchorNeeds(specs) {
  const needs = new Map();
  const want = (guid, outline) => {
    const cur = needs.get(guid) ?? { outline: false };
    cur.outline = cur.outline || outline;
    needs.set(guid, cur);
  };
  for (const spec of specs) {
    for (const p of spec.points) if (isAnchor(p)) want(p.guid, spec.kind === "outline");
    if (isAnchor(spec.height)) want(spec.height.guid, false);
  }
  return needs;
}

/**
 * Lengthens a polyline by `metres` beyond its first and last vertex, along
 * the direction of its first and last segment. Degenerate ends are left alone.
 * @param {number[][]} points
 * @param {number} metres
 * @returns {number[][]}
 */
export function extendEnds(points, metres) {
  if (!(metres > 0) || points.length < 2) return points;
  const out = points.map((p) => [...p]);
  const push = (from, to, target) => {
    const d = [to[0] - from[0], to[1] - from[1], to[2] - from[2]];
    const len = Math.hypot(d[0], d[1], d[2]);
    if (!(len > 0)) return;
    for (let k = 0; k < 3; k++) target[k] += (d[k] / len) * metres;
  };
  push(out[1], out[0], out[0]);
  const n = out.length;
  push(out[n - 2], out[n - 1], out[n - 1]);
  return out;
}

const samePoint = (a, b) => a.length === b.length && a.every((c, i) => c === b[i]);

/** The ring with its first vertex repeated at the end, so a line through it closes. */
export function closeLoop(points) {
  if (points.length < 2 || samePoint(points[0], points[points.length - 1]))
    return points.map((p) => [...p]);
  return [...points.map((p) => [...p]), [...points[0]]];
}

/**
 * Points on a circle or arc in a plane: `segments + 1` points, the angle
 * running from the plane's first axis toward its second (xz: from +x toward
 * +z). A full circle ends where it starts.
 * @param {number[]} centre
 * @param {number} radius
 * @param {number} startDeg
 * @param {number} endDeg
 * @param {number} segments
 * @param {string} plane
 * @returns {number[][]}
 */
export function sampleArc(centre, radius, startDeg, endDeg, segments, plane) {
  const [u, v] = PLANE_AXES[plane];
  const out = [];
  for (let i = 0; i <= segments; i++) {
    const deg = startDeg + ((endDeg - startDeg) * i) / segments;
    const rad = THREE.MathUtils.degToRad(deg);
    const p = [...centre];
    p[u] += radius * Math.cos(rad);
    p[v] += radius * Math.sin(rad);
    out.push(p);
  }
  // A full turn ends exactly where it starts (sin(2π) is -2.4e-16, not 0).
  if (Math.abs(endDeg - startDeg) === 360) out[out.length - 1] = [...out[0]];
  return out;
}

/**
 * A centripetal Catmull-Rom spline through the points: `samples` points per
 * segment, passing through every input point; closed splines end where they
 * start.
 * @param {number[][]} points
 * @param {number} samples
 * @param {boolean} closed
 * @returns {number[][]}
 */
export function sampleSpline(points, samples, closed) {
  if (points.length < 2) return points.map((p) => [...p]);
  const curve = new THREE.CatmullRomCurve3(
    points.map((p) => new THREE.Vector3(p[0], p[1], p[2])),
    closed,
    "centripetal",
  );
  const n = samples * (closed ? points.length : points.length - 1);
  return curve.getPoints(n).map((v) => [v.x, v.y, v.z]);
}

/**
 * The scene polyline(s) of a normalized spec. Pure: anchors are looked up in
 * the `anchors` map the live side built (guid -> {center, bottom, top} as
 * [x, y, z], plus `outline` loops for anchors that asked for them; null when
 * the element has no geometry). Missing anchors are dropped and listed; a
 * spec left with fewer points than its kind needs gives no polyline, and the
 * caller decides what that means.
 *
 * @param {ReturnType<typeof normalizeLineSpec>} spec
 * @param {{T?: number[], anchors?: Map<string, Record<string, any> | null>}} ctx - `T` the
 *   coordinationMatrix translation (needed for ifcPlan), `anchors` the resolved anchor data
 * @returns {{points: number[][], polylines: number[][][], dropped: string[]}} `points` is the
 *   first polyline (every kind but outline has exactly one); `dropped` the GUIDs without data
 */
export function resolveLinePoints(spec, { T = [0, 0, 0], anchors = new Map() } = {}) {
  const dropped = [];
  const none = () => ({ points: [], polylines: [], dropped });
  const rules = KIND_RULES[spec.kind];

  if (rules.outline) {
    const a = spec.points[0];
    const loops = anchors.get(a.guid)?.outline;
    if (!loops || loops.length === 0) {
      dropped.push(a.guid);
      return none();
    }
    const polylines = loops.map((loop) => closeLoop(loop));
    return { points: polylines[0], polylines, dropped };
  }

  let height = null;
  if (spec.height !== null) {
    if (isAnchor(spec.height)) {
      const anchor = /** @type {{guid: string, at: string}} */ (spec.height);
      const hit = anchors.get(anchor.guid)?.[anchor.at];
      if (hit) height = hit[1];
      else dropped.push(anchor.guid);
    } else if (isIfcHeight(spec.height)) {
      height = /** @type {{ifcZ: number}} */ (spec.height).ifcZ + T[1];
    } else {
      height = /** @type {number} */ (spec.height);
    }
  }

  let points = [];
  for (const p of spec.points) {
    if (isAnchor(p)) {
      const hit = anchors.get(p.guid)?.[p.at];
      if (hit) points.push([...hit]);
      else dropped.push(p.guid);
      continue;
    }
    if (spec.space === "ifcPlan") {
      if (height === null) continue; // the height anchor is already in `dropped`
      points.push(ifcPlanToScene(p[0], p[1], T, height));
    } else {
      points.push([...p]);
    }
  }
  if (points.length < rules.min) return none();

  if (rules.line && spec.sortAlong) {
    const k = SORT_AXES.indexOf(spec.sortAlong);
    points.sort((a, b) => a[k] - b[k]);
  }
  if (spec.flattenY !== null) {
    const ys = points.map((p) => p[1]);
    const y =
      spec.flattenY === "min"
        ? Math.min(...ys)
        : spec.flattenY === "max"
          ? Math.max(...ys)
          : spec.flattenY;
    for (const p of points) p[1] = y;
  }
  if (rules.line) points = extendEnds(points, spec.extend);

  let out = points;
  if (spec.kind === "polygon") out = closeLoop(points);
  else if (spec.kind === "spline") out = sampleSpline(points, spec.samples, spec.closed);
  else if (spec.kind === "circle")
    out = sampleArc(points[0], spec.radius, 0, 360, spec.segments, spec.plane);
  else if (spec.kind === "arc")
    out = sampleArc(points[0], spec.radius, spec.startDeg, spec.endDeg, spec.segments, spec.plane);
  return { points: out, polylines: [out], dropped };
}
