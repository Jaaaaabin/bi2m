// ======== Per-type default views, from the record alone ========
// Seven rules, keyed on what an intent record's `evidence.metrics` carries
// rather than on individual detector names, so a new detector in a known
// family gets a sensible starting view for free. Each rule returns a LIST of
// named view specs (viewSpec.js): some intents need several shots - one
// plan per storey at the same scale for repeated units, a plan plus a view
// along the line for an alignment. The intent panel's Refer applies the
// first when the owner's opt-in is on; the batch driver applies them all.
//
// Nothing here touches the camera. It is a pure table from record to spec,
// unit-tested in tests/unit/rules.test.js, and every spec it returns goes
// through resolveViewSpec like a hand-written one. The specs only set a
// STARTING view; refining them by visibility score is phase 4.
//
// Conventions used below (views/direction.js, views/frame.js):
//   - in the INTENT frame of an alignment line, az 0 looks ALONG the line
//     (members stack up), az 90 looks across it; a plan at az 180 puts the
//     line level on screen, because at the pole azimuth is the roll and a
//     positive theta rolls clockwise (scripts/e2e/views.py, phase 0);
//   - in the BUILDING frame az 180 at el 90 is a grid-aligned plan.
//   - a cut keeps what is BELOW its height unless `keep: "above"` (a
//     reflected ceiling plan, looked at from below with a negative elevation).

/** Metres per pixel for "the same scale" across the storeys of one intent. */
export const STOREY_PLAN_MPP = 0.05;
/** Eye height of a storey plan cut above the storey's floor, in metres. */
export const PLAN_CUT_HEIGHT_M = 1.2;
/** A ceiling plan is cut just under the ceiling; above this the next slab hides it. */
export const CEILING_CUT_HEIGHT_M = 2.6;

const ENVELOPE_TYPES = new Set([
  "envelope_footprint_continuity",
  "envelope_setback",
  "envelope_thermal_boundary",
  "curtainwall_assembly",
  "egress_external_access",
  "window_lighting_cluster",
]);

const has = (metrics, ...keys) => keys.every((k) => metrics?.[k] !== undefined && metrics?.[k] !== null);
const isName = (v) => typeof v === "string" && v.length > 0;

const intentScope = (intent) => ({ kind: "intent", intentId: intent.id });

const storeyPlan = (intent, storey, { name = "plan", keep = "below" } = {}) => ({
  name,
  spec: {
    scope: intentScope(intent),
    frame: { kind: "building" },
    direction: { azimuthDeg: 180, elevationDeg: keep === "above" ? -90 : 90 },
    lens: { projection: "orthographic", metresPerPixel: STOREY_PLAN_MPP },
    cut: isName(storey)
      ? { kind: "storeyPlan", storey, heightM: keep === "above" ? CEILING_CUT_HEIGHT_M : PLAN_CUT_HEIGHT_M, keep }
      : { kind: "none" },
  },
});

/**
 * The starting views for an intent, oldest rule first. Always at least one
 * entry; with no matching rule it is `{name: "default", spec: {}}`, which is
 * today's behaviour (keep the direction, Context slider, no cut).
 *
 * @param {{id: string, type?: string, members?: Array<{guid: string, role?: string}>, evidence?: {metrics?: Record<string, any>}}} intent
 * @returns {Array<{name: string, spec: Record<string, any>, rule: string}>}
 */
export function viewsForIntent(intent) {
  const m = intent?.evidence?.metrics ?? {};
  const type = intent?.type ?? "";
  const tag = (rule, views) => views.map((v) => ({ ...v, rule }));

  // 1. A line: alignments and grid lines (`axis` + `value`).
  if (has(m, "axis", "value")) {
    const storey = isName(m.storey) ? m.storey : Array.isArray(m.storeysPresent) ? m.storeysPresent[0] : null;
    return tag("line", [
      {
        name: "plan",
        spec: {
          scope: intentScope(intent),
          frame: { kind: "intent" },
          direction: { azimuthDeg: 180, elevationDeg: 90 },
          lens: { projection: "orthographic" },
          framing: { mode: "fill", fill: 0.8 },
          cut: isName(storey) ? { kind: "storeyPlan", storey, heightM: PLAN_CUT_HEIGHT_M } : { kind: "none" },
        },
      },
      {
        name: "along",
        spec: {
          scope: intentScope(intent),
          frame: { kind: "intent" },
          direction: { azimuthDeg: 0, elevationDeg: 8 },
          framing: { mode: "fill", fill: 0.7 },
        },
      },
    ]);
  }

  // 2. A vertical stack at (x, y): column/wall support, window stacks, vertical links.
  if (has(m, "x", "y") || has(m, "stackStoreys") || type === "circulation_vertical_link") {
    return tag("stack", [
      {
        name: "stack",
        spec: {
          scope: intentScope(intent),
          frame: { kind: "intent" },
          direction: { azimuthDeg: 90, elevationDeg: 5 },
          framing: { mode: "fill", fill: 0.8 },
        },
      },
      {
        name: "stack-across",
        spec: {
          scope: intentScope(intent),
          frame: { kind: "intent" },
          direction: { azimuthDeg: 0, elevationDeg: 5 },
          framing: { mode: "fill", fill: 0.8 },
        },
      },
    ]);
  }

  // 6. Beam modules: a reflected ceiling plan, several spans in frame.
  if (has(m, "spanM")) {
    return tag("ceiling", [
      {
        ...storeyPlan(intent, m.storey, { name: "ceiling", keep: "above" }),
      },
    ]);
  }

  // 4. Several storeys sharing a footprint: one plan per storey, same scale.
  if (Array.isArray(m.storeys) && m.storeys.length > 0 && (has(m, "footprint") || type.startsWith("unit_"))) {
    return tag(
      "storeys",
      m.storeys.filter(isName).map((storey) => storeyPlan(intent, storey, { name: `plan-${storey}` })),
    );
  }

  // 5. Envelope and facade: an exterior perspective in the building frame.
  if (ENVELOPE_TYPES.has(type)) {
    return tag("envelope", [
      {
        name: "exterior",
        spec: {
          scope: intentScope(intent),
          frame: { kind: "building" },
          direction: { azimuthDeg: 45, elevationDeg: 25 },
          framing: { mode: "context", context: 0.35 },
          lens: { projection: "perspective" },
        },
      },
    ]);
  }

  // 7. A property outlier: a close-up on the deviating elements.
  if (type === "convention_outlier") {
    return tag("outlier", [
      {
        name: "closeup",
        spec: {
          scope: intentScope(intent),
          frame: { kind: "building" },
          direction: { azimuthDeg: 45, elevationDeg: 20 },
          framing: { mode: "fill", fill: 0.7 },
          lens: { projection: "perspective" },
        },
      },
    ]);
  }

  // 3. Anything on one storey: rooms, access, egress, syntax, services, daylight.
  if (isName(m.storey)) {
    return tag("storey", [storeyPlan(intent, m.storey)]);
  }

  return tag("default", [{ name: "default", spec: {} }]);
}
