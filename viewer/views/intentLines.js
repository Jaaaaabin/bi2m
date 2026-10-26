// ======== Intent records -> line specs ========
// The pure adapter between the detectors' output and views/lineSpec.js. It
// never looks at geometry: every point is an anchor on a member, resolved by
// views/lines.js at draw time, so this runs in node and is unit-tested.
//
// Three shapes, keyed on detector families the way views/rules.js keys the
// camera rules, so a new detector gets a line without a new case here:
//
//   alignment   `axis` + `value`: a polyline through the members' BOTTOM
//               anchors - columns stand on the storey floor, so the line
//               lies on the floor like a grid line - sorted along the line's
//               scene axis (an X line runs along scene z, a Y line along
//               scene x; intentFrame.js), FLATTENED to the lowest foot -
//               a grid_line_consistency record spans up to five storeys, and
//               a polyline through feet at five heights is a sawtooth, not a
//               grid line - and extended 1 m past both ends;
//   stack       `x`, `y` + storeys: a polyline through member centres, bottom
//               to top (a per-storey stack-failure record is drawn as rings
//               instead, see TERMINAL_TYPES);
//   anything    two or more members: a polyline linking their centres, the
//               general "link components" case.
//
// And two SHAPES, from `shapeSpecsFromIntent`:
//
//   footprint   vertical_space_connection carries the recurring room's plan
//               rectangle `footprint` = [xmin, ymin, xmax, ymax] in IFC plan
//               metres (detectors/vertical.py, `anchor_bbox`): a polygon in
//               `ifcPlan` space whose height is the first member's foot;
//   outline     the exact floor polygon of every IfcSpace member of a
//               circulation, space-syntax or all-rated fire-compartment
//               record (views/outline.js reads it off the fragments) - the
//               irregular rooms.
//
// Ids derive from the intent id (`line:<intent id>`, plus `:footprint` or
// `:outline:<guid>` for the shapes), so toggling, replacing and the e2e
// assertion all name the same line.

export const INTENT_LINE_PREFIX = "line:";
export const ALIGNMENT_TYPES = Object.freeze(
  new Set(["alignment_column_group", "grid_line_consistency", "grid_line_gap"]),
);
export const STACK_TYPES = Object.freeze(
  new Set([
    "structural_column_support",
    "structural_wall_support",
    "structural_unsupported_base",
    "structural_stack_termination",
    "window_vertical_alignment",
    "circulation_vertical_link",
  ]),
);
// The two negative companions of Vertical Placement Continuity, and where a
// ring marks the failure on each member. Since 2026-10-09 they are one record
// per storey transition: the members are the terminal element of each stack
// (role "top" or "base", all on one storey) and `metrics.stackIds` names the
// positive stack records. A stack polyline through such members would be a
// zigzag across the floor, so a record that carries `stackIds` gets a ring per
// member instead - and, on a Refer, the stacks it names. A record without
// `stackIds` (an older shard: one record per stack) is still drawn as a stack.
export const TERMINAL_TYPES = Object.freeze(
  new Map([
    ["structural_stack_termination", "top"],
    ["structural_unsupported_base", "bottom"],
  ]),
);
export const TERMINAL_RING_RADIUS_M = 0.6;
export const FOOTPRINT_TYPES = Object.freeze(new Set(["vertical_space_connection"]));
export const OUTLINE_TYPES = Object.freeze(
  // fire_compartment_singletons (2026-10-08): one record per storey whose
  // members are all its rooms; their outlines say "every room is its own
  // compartment" better than a polyline zigzagging through them.
  new Set([
    "circulation_horizontal_space",
    "syntax_integration_core",
    "fire_compartment_singletons",
  ]),
);
export const ALIGNMENT_EXTEND_M = 1;
export const INTENT_LINE_COLORS = Object.freeze({
  alignment: "#e5484d",
  stack: "#1e90ff",
  link: "#ff6a00",
  footprint: "#8e44ad",
  outline: "#16a34a",
  terminal: "#b00020",
});

/** A per-storey stack-failure record (2026-10-09 shape), drawn as rings. */
function isTerminalRecord(intent) {
  return TERMINAL_TYPES.has(intent?.type) && Array.isArray(intent?.evidence?.metrics?.stackIds);
}

/** The line id an intent's line carries. */
export function lineIdForIntent(intentId) {
  return `${INTENT_LINE_PREFIX}${intentId}`;
}

/** Members that are part of the pattern, not context (the labels make the same cut). */
function patternMembers(intent) {
  return (intent?.members ?? []).filter(
    (m) => m && typeof m.guid === "string" && m.role !== "context",
  );
}

/**
 * One line spec for an intent record, or null when the record has fewer than
 * two members to link.
 * @param {Record<string, any>} intent - an intent record as the shards hold it
 * @returns {Record<string, any> | null} a line spec for views/lineSpec.js
 */
export function lineSpecFromIntent(intent) {
  const members = patternMembers(intent);
  if (members.length < 2) return null;
  const type = intent.type;
  const meta = { source: "intent", intentId: intent.id, type, label: intent.label };
  if (isTerminalRecord(intent)) return null; // rings, from shapeSpecsFromIntent
  if (ALIGNMENT_TYPES.has(type)) {
    const axis = String(intent.evidence?.metrics?.axis ?? "").toUpperCase();
    return {
      id: lineIdForIntent(intent.id),
      kind: "polyline",
      points: members.map((m) => ({ guid: m.guid, at: "bottom" })),
      sortAlong: axis === "X" ? "z" : axis === "Y" ? "x" : null,
      flattenY: "min",
      extend: ALIGNMENT_EXTEND_M,
      style: { color: INTENT_LINE_COLORS.alignment },
      meta,
    };
  }
  if (STACK_TYPES.has(type)) {
    return {
      id: lineIdForIntent(intent.id),
      kind: "polyline",
      points: members.map((m) => ({ guid: m.guid, at: "center" })),
      sortAlong: "y",
      style: { color: INTENT_LINE_COLORS.stack },
      meta,
    };
  }
  return {
    id: lineIdForIntent(intent.id),
    kind: "polyline",
    points: members.map((m) => ({ guid: m.guid, at: "center" })),
    style: { color: INTENT_LINE_COLORS.link },
    meta,
  };
}

/**
 * Specs for a list of intents, records without a line dropped.
 * @param {Array<Record<string, any>>} intents
 * @param {(intent: Record<string, any>) => boolean} [keep] - optional filter
 */
export function lineSpecsFromIntents(intents, keep = () => true) {
  return (intents ?? []).filter(keep).map(lineSpecFromIntent).filter(Boolean);
}

/**
 * Shape specs for an intent record: a footprint polygon, outline polygons,
 * rings on the members of a stack-failure record, or nothing. Pure data; the
 * engine resolves the geometry.
 * @param {Record<string, any>} intent
 * @param {{intents?: Array<Record<string, any>> | null}} [options] - with the
 *   model's records, a stack-failure record also yields the stacks it names
 * @returns {Array<Record<string, any>>}
 */
export function shapeSpecsFromIntent(intent, { intents = null } = {}) {
  const out = [];
  const type = intent?.type;
  const members = patternMembers(intent);
  const meta = (shape) => ({
    source: "intent",
    intentId: intent.id,
    type,
    label: intent.label,
    shape,
  });
  const fp = intent?.evidence?.metrics?.footprint;
  const fpOk = Array.isArray(fp) && fp.length === 4 && fp.every(Number.isFinite);
  if (FOOTPRINT_TYPES.has(type) && members.length > 0 && fpOk) {
    const [x0, y0, x1, y1] = fp;
    out.push({
      id: `${lineIdForIntent(intent.id)}:footprint`,
      kind: "polygon",
      space: "ifcPlan",
      height: { guid: members[0].guid, at: "bottom" },
      points: [
        [x0, y0],
        [x1, y0],
        [x1, y1],
        [x0, y1],
      ],
      style: { color: INTENT_LINE_COLORS.footprint, width: 2 },
      meta: meta("footprint"),
    });
  }
  if (OUTLINE_TYPES.has(type)) {
    for (const m of members) {
      if (m.ifcClass !== "IfcSpace") continue;
      out.push({
        id: `${lineIdForIntent(intent.id)}:outline:${m.guid}`,
        kind: "outline",
        points: [{ guid: m.guid }],
        style: { color: INTENT_LINE_COLORS.outline, width: 2 },
        meta: meta("outline"),
      });
    }
  }
  if (isTerminalRecord(intent)) {
    const at = TERMINAL_TYPES.get(type);
    for (const m of members) {
      out.push({
        id: `${lineIdForIntent(intent.id)}:ring:${m.guid}`,
        kind: "circle",
        radius: TERMINAL_RING_RADIUS_M,
        points: [{ guid: m.guid, at }],
        style: { color: INTENT_LINE_COLORS.terminal, width: 2 },
        meta: meta("ring"),
      });
    }
    // The stacks it ends, when the caller has the model's intents (a Refer).
    if (Array.isArray(intents)) {
      for (const stackId of intent.evidence.metrics.stackIds) {
        const stack = intents.find((i) => i?.id === stackId);
        const line = stack ? lineSpecFromIntent(stack) : null;
        if (!line) continue;
        out.push({
          ...line,
          id: `${lineIdForIntent(intent.id)}:stack:${stackId}`,
          meta: { ...meta("stack"), stackId },
        });
      }
    }
  }
  return out;
}

/**
 * Shape specs for a list of intents. A room that several records name gets
 * one outline, under the first record's id.
 * @param {Array<Record<string, any>>} intents
 * @param {(intent: Record<string, any>) => boolean} [keep]
 */
export function shapeSpecsFromIntents(intents, keep = () => true) {
  const seenOutline = new Set();
  const out = [];
  for (const intent of (intents ?? []).filter(keep)) {
    for (const spec of shapeSpecsFromIntent(intent)) {
      if (spec.kind === "outline") {
        const guid = spec.points[0].guid;
        if (seenOutline.has(guid)) continue;
        seenOutline.add(guid);
      }
      out.push(spec);
    }
  }
  return out;
}

/**
 * The test button's set: every alignment line and stack of the model, plus
 * the footprints and room outlines its records describe.
 */
export function demoLineSpecs(intents) {
  return [
    ...lineSpecsFromIntents(intents, (i) => ALIGNMENT_TYPES.has(i.type) || STACK_TYPES.has(i.type)),
    ...shapeSpecsFromIntents(
      intents,
      (i) => FOOTPRINT_TYPES.has(i.type) || OUTLINE_TYPES.has(i.type) || TERMINAL_TYPES.has(i.type),
    ),
  ];
}

/**
 * A closed rectangle on the floor of a box, in scene space: the fallback the
 * test button draws when a model has no alignment or stack records, and the
 * one place the raw-coordinate path is exercised live.
 * @param {{min: {x: number, y: number, z: number}, max: {x: number, y: number, z: number}}} box
 * @param {number} [lift] - metres above the floor, so the line is not z-fighting the slab
 */
export function floorRectangleSpec(box, lift = 0.02) {
  const y = box.min.y + lift;
  return {
    id: "demo:floor",
    kind: "polyline",
    space: "scene",
    points: [
      [box.min.x, y, box.min.z],
      [box.max.x, y, box.min.z],
      [box.max.x, y, box.max.z],
      [box.min.x, y, box.max.z],
      [box.min.x, y, box.min.z],
    ],
    style: { color: "#8b8b8b" },
    meta: { source: "demo", label: "Model footprint" },
  };
}
