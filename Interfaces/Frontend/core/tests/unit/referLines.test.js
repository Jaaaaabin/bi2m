import { describe, it, expect, vi } from "vitest";

// referLines.js imports the live engine for its event handlers; the pure
// part under test needs none of it.
vi.mock("../../views/lines.js", () => ({
  addLines: async () => ({ added: [] }),
  listLines: () => [],
  removeLines: () => [],
}));
vi.mock("../../viewerModel.js", () => ({ getModelContext: () => null }));

const { REFER_LINE_PREFIX, REFER_LINE_WIDTH, referSpecsForIntent } =
  await import("../../views/referLines.js");
const { tooltipText } = await import("../../views/linePicker.js");

const stack = {
  id: "k-colsupport-A-B",
  type: "structural_column_support",
  label: "Column support stack",
  members: [
    { guid: "A", role: "base" },
    { guid: "B", role: "top" },
  ],
  evidence: { metrics: { x: 1, y: 2 } },
};
const corridor = {
  id: "k-circh-1",
  type: "circulation_horizontal_space",
  label: "Horizontal circulation",
  members: [
    { guid: "C1", role: "member", ifcClass: "IfcSpace" },
    { guid: "W1", role: "member", ifcClass: "IfcWall" },
  ],
  evidence: { metrics: {} },
};

describe("referSpecsForIntent", () => {
  it("re-keys the record's line under the refer prefix and widens it", () => {
    const [s] = referSpecsForIntent(stack);
    expect(s.id).toBe(`${REFER_LINE_PREFIX}line:k-colsupport-A-B`);
    expect(s.style.width).toBe(REFER_LINE_WIDTH);
    expect(s.meta.intentId).toBe("k-colsupport-A-B");
  });
  it("includes the record's shapes, each under the prefix", () => {
    const ids = referSpecsForIntent(corridor).map((s) => s.id);
    expect(ids).toEqual([
      `${REFER_LINE_PREFIX}line:k-circh-1`,
      `${REFER_LINE_PREFIX}line:k-circh-1:outline:C1`,
    ]);
    expect(referSpecsForIntent(corridor).every((s) => s.style.width >= REFER_LINE_WIDTH)).toBe(
      true,
    );
  });
  it("gives nothing for a record with nothing to draw", () => {
    expect(referSpecsForIntent({ id: "x", type: "t", members: [{ guid: "A" }] })).toEqual([]);
  });
});

describe("tooltipText", () => {
  it("prefers the author's label, falls back to the id, and names the kind", () => {
    expect(
      tooltipText({
        id: "sidecar:circle",
        spec: { kind: "circle", meta: { label: "Circle on a foot" } },
      }),
    ).toBe("Circle on a foot · circle");
    expect(tooltipText({ id: "line-7", spec: { kind: "segment", meta: {} } })).toBe(
      "line-7 · segment",
    );
    expect(tooltipText({ id: "x", spec: null })).toBe("x");
  });
});

describe("referSpecsForIntent with the model's intents", () => {
  it("a stack-failure Refer draws its rings and the stacks it names, all refer-prefixed", () => {
    const col = (guid, role) => ({ guid, role, ifcClass: "IfcColumn" });
    const stack = {
      id: "k-stack-a",
      type: "structural_column_support",
      members: [col("A0", "member"), col("A1", "member")],
      evidence: { metrics: { x: 1, y: 2 } },
    };
    const stop = {
      id: "k-columnstop-S1",
      type: "structural_stack_termination",
      members: [col("A1", "top")],
      evidence: { metrics: { stackIds: ["k-stack-a"] } },
    };
    const specs = referSpecsForIntent(stop, [stack, stop]);
    expect(specs.map((s) => s.id)).toEqual([
      `${REFER_LINE_PREFIX}line:k-columnstop-S1:ring:A1`,
      `${REFER_LINE_PREFIX}line:k-columnstop-S1:stack:k-stack-a`,
    ]);
    expect(specs.every((s) => s.style.width >= REFER_LINE_WIDTH)).toBe(true);
  });
});
