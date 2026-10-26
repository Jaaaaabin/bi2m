import { describe, it, expect } from "vitest";
import { assignCategoryColorIndexes } from "../../intentData.js";

const p = (detector, id = detector) => ({ id, provenance: { detector } });

describe("assignCategoryColorIndexes", () => {
  it("assigns one slot per CATEGORY in manifest order, not per intent", () => {
    const out = assignCategoryColorIndexes(
      [p("structural", "a"), p("alignment", "b"), p("structural", "c")],
      ["alignment", "connection", "structural"],
    );
    expect(out.map((x) => x.colorIndex)).toEqual([2, 0, 2]);
  });
  it("gives an unknown category the slot after the manifest", () => {
    const out = assignCategoryColorIndexes([p("mystery")], ["alignment", "connection"]);
    expect(out[0].colorIndex).toBe(2);
  });
  it("falls back to first-seen order when the manifest is empty", () => {
    const out = assignCategoryColorIndexes([p("b"), p("a"), p("b")], []);
    expect(out.map((x) => x.colorIndex)).toEqual([0, 1, 0]);
  });
  it("does not mutate the input records", () => {
    const input = [p("alignment")];
    assignCategoryColorIndexes(input, ["alignment"]);
    expect(input[0].colorIndex).toBeUndefined();
  });
});
