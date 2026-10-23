import { describe, it, expect } from "vitest";

import {
  ALIGNMENT_EXTEND_M,
  INTENT_LINE_COLORS,
  TERMINAL_RING_RADIUS_M,
  demoLineSpecs,
  floorRectangleSpec,
  lineIdForIntent,
  lineSpecFromIntent,
  lineSpecsFromIntents,
  shapeSpecsFromIntent,
  shapeSpecsFromIntents,
} from "../../views/intentLines.js";
import { normalizeLineSpec } from "../../views/lineSpec.js";

const members = (...guids) =>
  guids.map((guid) => ({ guid, role: "member", ifcClass: "IfcColumn" }));

const alignmentX = {
  id: "k-grid-x39179-s1",
  type: "alignment_column_group",
  label: "Aligned column grid line (X ≈ 39.179m, Floor 0)",
  members: members("A", "B", "C"),
  evidence: { metrics: { axis: "X", value: 39.179, toleranceM: 0.01 } },
};
const stack = {
  id: "k-colsupport-A-B",
  type: "structural_column_support",
  label: "Column support stack",
  members: [
    { guid: "A", role: "base" },
    { guid: "B", role: "intermediate" },
    { guid: "C", role: "top" },
  ],
  evidence: { metrics: { x: 39.179, y: 43.365 } },
};
const vertical = {
  id: "k-vertical-1",
  type: "vertical_space_connection",
  label: "Vertical connection across 3 storeys",
  members: [
    { guid: "R0", role: "member", ifcClass: "IfcSpace" },
    { guid: "R1", role: "member", ifcClass: "IfcSpace" },
    { guid: "R2", role: "member", ifcClass: "IfcSpace" },
  ],
  evidence: {
    metrics: {
      storeys: ["F0", "F1", "F2"],
      footprint: [39.279, 31.265, 43.949, 37.465],
      toleranceM: 0.3,
    },
  },
};
const corridor = {
  id: "k-circh-1",
  type: "circulation_horizontal_space",
  label: "Horizontal circulation: Floor 0 (3 spaces)",
  members: [
    { guid: "C1", role: "member", ifcClass: "IfcSpace" },
    { guid: "C2", role: "member", ifcClass: "IfcSpace" },
    { guid: "D1", role: "context", ifcClass: "IfcDoor" },
    { guid: "W9", role: "member", ifcClass: "IfcWall" },
  ],
  evidence: { metrics: { storey: "Floor 0" } },
};
const core = {
  id: "k-core-1",
  type: "syntax_integration_core",
  label: "Integration core",
  members: [
    { guid: "C2", role: "member", ifcClass: "IfcSpace" },
    { guid: "C7", role: "member", ifcClass: "IfcSpace" },
  ],
  evidence: { metrics: {} },
};
const room = {
  id: "k-room-1",
  type: "connection_boundary_adjacency",
  label: "Walls bounding space",
  members: [...members("W1", "W2"), { guid: "S", role: "context", ifcClass: "IfcSpace" }],
  evidence: { metrics: {} },
};

describe("lineSpecFromIntent", () => {
  it("an X alignment becomes a floor polyline through bottom anchors, sorted along scene z, extended", () => {
    const s = lineSpecFromIntent(alignmentX);
    expect(s.id).toBe(lineIdForIntent(alignmentX.id));
    expect(s.kind).toBe("polyline");
    expect(s.points).toEqual([
      { guid: "A", at: "bottom" },
      { guid: "B", at: "bottom" },
      { guid: "C", at: "bottom" },
    ]);
    expect(s.sortAlong).toBe("z");
    expect(s.flattenY).toBe("min"); // feet on several storeys become one floor line
    expect(s.extend).toBe(ALIGNMENT_EXTEND_M);
    expect(s.style.color).toBe(INTENT_LINE_COLORS.alignment);
    expect(s.meta).toEqual({
      source: "intent",
      intentId: alignmentX.id,
      type: alignmentX.type,
      label: alignmentX.label,
    });
    expect(() => normalizeLineSpec(s)).not.toThrow();
  });
  it("a Y alignment sorts along scene x; an axis without a letter does not sort", () => {
    const y = lineSpecFromIntent({ ...alignmentX, evidence: { metrics: { axis: "y", value: 1 } } });
    expect(y.sortAlong).toBe("x");
    const none = lineSpecFromIntent({ ...alignmentX, evidence: { metrics: {} } });
    expect(none.sortAlong).toBeNull();
  });
  it("a stack becomes a polyline through member centres sorted by height", () => {
    const s = lineSpecFromIntent(stack);
    expect(s.points.every((p) => p.at === "center")).toBe(true);
    expect(s.sortAlong).toBe("y");
    expect(s.flattenY).toBeUndefined(); // a stack is vertical by nature
    expect(s.extend).toBeUndefined();
    expect(s.style.color).toBe(INTENT_LINE_COLORS.stack);
  });
  it("any other record links its pattern members' centres and skips context members", () => {
    const s = lineSpecFromIntent(room);
    expect(s.points.map((p) => p.guid)).toEqual(["W1", "W2"]);
    expect(s.sortAlong).toBeUndefined();
    expect(s.style.color).toBe(INTENT_LINE_COLORS.link);
  });
  it("fewer than two members is no line", () => {
    expect(lineSpecFromIntent({ ...room, members: room.members.slice(0, 1) })).toBeNull();
    expect(lineSpecFromIntent({ id: "x", type: "t", members: [] })).toBeNull();
    expect(lineSpecFromIntent({ id: "x", type: "t" })).toBeNull();
  });
});

describe("lineSpecsFromIntents / demoLineSpecs", () => {
  it("drops records without a line and honours a filter", () => {
    const all = lineSpecsFromIntents([
      alignmentX,
      stack,
      room,
      { id: "e", type: "t", members: [] },
    ]);
    expect(all.map((s) => s.id)).toEqual([
      "line:k-grid-x39179-s1",
      "line:k-colsupport-A-B",
      "line:k-room-1",
    ]);
    expect(
      lineSpecsFromIntents([alignmentX, stack], (i) => i.type === "structural_column_support"),
    ).toHaveLength(1);
  });
  it("the demo set is alignments and stacks only", () => {
    expect(demoLineSpecs([alignmentX, stack, room]).map((s) => s.id)).toEqual([
      "line:k-grid-x39179-s1",
      "line:k-colsupport-A-B",
    ]);
    expect(demoLineSpecs([room])).toEqual([]);
  });
});

describe("shapeSpecsFromIntent", () => {
  it("a vertical space connection gives its footprint rectangle in ifcPlan, floored on the first member", () => {
    const [fp] = shapeSpecsFromIntent(vertical);
    expect(fp.id).toBe("line:k-vertical-1:footprint");
    expect(fp.kind).toBe("polygon");
    expect(fp.space).toBe("ifcPlan");
    expect(fp.height).toEqual({ guid: "R0", at: "bottom" });
    expect(fp.points).toEqual([
      [39.279, 31.265],
      [43.949, 31.265],
      [43.949, 37.465],
      [39.279, 37.465],
    ]);
    expect(fp.style).toEqual({ color: INTENT_LINE_COLORS.footprint, width: 2 });
    expect(fp.meta.shape).toBe("footprint");
    expect(() => normalizeLineSpec(fp)).not.toThrow();
  });
  it("a circulation record gives one outline per IfcSpace member, skipping walls and context", () => {
    const specs = shapeSpecsFromIntent(corridor);
    expect(specs.map((s) => s.id)).toEqual([
      "line:k-circh-1:outline:C1",
      "line:k-circh-1:outline:C2",
    ]);
    expect(specs.every((s) => s.kind === "outline" && s.points.length === 1)).toBe(true);
    expect(specs[0].points[0]).toEqual({ guid: "C1" });
    expect(() => normalizeLineSpec(specs[0])).not.toThrow();
  });
  it("an all-rated fire record outlines every room of the storey, not the doors", () => {
    const singletons = {
      id: "k-fire-1",
      type: "fire_compartment_singletons",
      label: "Every room its own fire compartment: Floor 0",
      members: [
        { guid: "R1", role: "member", ifcClass: "IfcSpace" },
        { guid: "R2", role: "member", ifcClass: "IfcSpace" },
      ],
      evidence: { relatedGuids: ["S0", "D1"], metrics: { rooms: 2, ratedDoors: 1 } },
    };
    const specs = shapeSpecsFromIntent(singletons);
    expect(specs.map((s) => s.id)).toEqual([
      "line:k-fire-1:outline:R1",
      "line:k-fire-1:outline:R2",
    ]);
    expect(
      specs.every((s) => s.kind === "outline" && s.style.color === INTENT_LINE_COLORS.outline),
    ).toBe(true);
  });
  it("records of other types, or a footprint that is not four numbers, give no shape", () => {
    expect(shapeSpecsFromIntent(alignmentX)).toEqual([]);
    expect(shapeSpecsFromIntent(room)).toEqual([]);
    expect(
      shapeSpecsFromIntent({ ...vertical, evidence: { metrics: { footprint: [1, 2, 3] } } }),
    ).toEqual([]);
    expect(shapeSpecsFromIntent({ ...vertical, members: [] })).toEqual([]);
  });
  it("shapeSpecsFromIntents draws a room named by two records once, under the first", () => {
    const ids = shapeSpecsFromIntents([corridor, core]).map((s) => s.id);
    expect(ids).toEqual([
      "line:k-circh-1:outline:C1",
      "line:k-circh-1:outline:C2",
      "line:k-core-1:outline:C7",
    ]);
  });
  it("the demo set is lines first, then shapes", () => {
    const ids = demoLineSpecs([alignmentX, vertical, corridor, room]).map((s) => s.id);
    expect(ids).toEqual([
      "line:k-grid-x39179-s1",
      "line:k-vertical-1:footprint",
      "line:k-circh-1:outline:C1",
      "line:k-circh-1:outline:C2",
    ]);
  });
});

describe("floorRectangleSpec", () => {
  it("is a closed rectangle just above the box floor, in scene space", () => {
    const box = { min: { x: -5, y: -2, z: -9 }, max: { x: 15, y: 12, z: 30 } };
    const s = floorRectangleSpec(box);
    expect(s.space).toBe("scene");
    expect(s.points).toHaveLength(5);
    expect(s.points[0]).toEqual(s.points[4]);
    expect(s.points.every((p) => p[1] === -1.98)).toBe(true);
    expect(s.points[2]).toEqual([15, -1.98, 30]);
    expect(() => normalizeLineSpec(s)).not.toThrow();
  });
});

// 2026-10-09: the two negative companions of Vertical Placement Continuity are
// one record per storey transition, members = the terminal element of each
// stack, metrics.stackIds = the positive stacks they end.
const col = (guid, role) => ({ guid, role, ifcClass: "IfcColumn" });
const stackA = {
  id: "k-stack-a",
  type: "structural_column_support",
  label: "stack A",
  members: [col("A0", "member"), col("A1", "member")],
  evidence: { metrics: { x: 1, y: 2 } },
};
const stackB = {
  ...stackA,
  id: "k-stack-b",
  label: "stack B",
  members: [col("B0", "member"), col("B1", "member")],
};
const termination = {
  id: "k-columnstop-S1",
  type: "structural_stack_termination",
  label: "2 column stacks end on Floor 1",
  members: [col("A1", "top"), col("B1", "top")],
  evidence: { relatedGuids: ["S1"], metrics: { stackIds: ["k-stack-a", "k-stack-b"] } },
};
const noBase = {
  id: "k-columnnobase-S2",
  type: "structural_unsupported_base",
  label: "1 column stack starts unsupported on Floor 2",
  members: [col("C2", "base")],
  evidence: { relatedGuids: ["S2"], metrics: { stackIds: ["k-stack-c"] } },
};
const oldTermination = {
  id: "k-old-term",
  type: "structural_stack_termination",
  label: "stack ends",
  members: members("D0", "D1"),
  evidence: { metrics: { x: 3, y: 4, stackStoreys: ["F0", "F1"] } },
};

describe("stack failures, one record per storey transition", () => {
  it("draw no line of their own, so no zigzag across the storey", () => {
    expect(lineSpecFromIntent(termination)).toBeNull();
    expect(lineSpecFromIntent(noBase)).toBeNull();
  });
  it("an old per-stack record (no stackIds) is still a vertical stack", () => {
    const s = lineSpecFromIntent(oldTermination);
    expect(s.kind).toBe("polyline");
    expect(s.sortAlong).toBe("y");
    expect(s.style.color).toBe(INTENT_LINE_COLORS.stack);
  });
  it("ring each stack's top where it ends", () => {
    const specs = shapeSpecsFromIntent(termination);
    expect(specs.map((s) => s.id)).toEqual([
      "line:k-columnstop-S1:ring:A1",
      "line:k-columnstop-S1:ring:B1",
    ]);
    for (const s of specs) {
      expect(s.kind).toBe("circle");
      expect(s.radius).toBe(TERMINAL_RING_RADIUS_M);
      expect(s.style.color).toBe(INTENT_LINE_COLORS.terminal);
      expect(() => normalizeLineSpec(s)).not.toThrow();
    }
    expect(specs[0].points).toEqual([{ guid: "A1", at: "top" }]);
  });
  it("ring each unsupported stack's base", () => {
    const [s] = shapeSpecsFromIntent(noBase);
    expect(s.points).toEqual([{ guid: "C2", at: "bottom" }]);
  });
  it("with the model's intents, also draw the stacks named in stackIds", () => {
    const intents = [stackA, stackB, termination];
    const ids = shapeSpecsFromIntent(termination, { intents }).map((s) => s.id);
    expect(ids).toEqual([
      "line:k-columnstop-S1:ring:A1",
      "line:k-columnstop-S1:ring:B1",
      "line:k-columnstop-S1:stack:k-stack-a",
      "line:k-columnstop-S1:stack:k-stack-b",
    ]);
    const stackLine = shapeSpecsFromIntent(termination, { intents }).find((s) =>
      s.id.endsWith(":stack:k-stack-a"),
    );
    expect(stackLine.points).toEqual([
      { guid: "A0", at: "center" },
      { guid: "A1", at: "center" },
    ]);
    expect(stackLine.style.color).toBe(INTENT_LINE_COLORS.stack);
  });
  it("the demo set rings the failures and does not draw the stacks twice", () => {
    const ids = demoLineSpecs([stackA, termination]).map((s) => s.id);
    expect(ids).toContain(lineIdForIntent("k-stack-a"));
    expect(ids).toContain("line:k-columnstop-S1:ring:A1");
    expect(ids.some((id) => id.includes(":stack:"))).toBe(false);
    expect(ids).not.toContain(lineIdForIntent("k-columnstop-S1"));
  });
});
