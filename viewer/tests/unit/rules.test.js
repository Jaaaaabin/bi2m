import { describe, it, expect } from "vitest";

import { PLAN_CUT_HEIGHT_M, STOREY_PLAN_MPP, viewsForIntent } from "../../views/rules.js";
import { resolveViewSpec } from "../../views/viewSpec.js";

const intent = (type, metrics, id = "k-1") => ({ id, type, members: [], evidence: { metrics } });

// Every spec a rule returns must be a valid spec, cut and intent frame included.
const validate = (spec) => resolveViewSpec(spec);

describe("rules: the seven camera-rule families", () => {
  it("an alignment line: a plan with the line level, plus a low view along it", () => {
    const views = viewsForIntent(intent("alignment_column_group", { axis: "X", value: 39.179, toleranceM: 0.01, count: 8 }));
    expect(views.map((v) => v.name)).toEqual(["plan", "along"]);
    expect(views[0].rule).toBe("line");
    expect(views[0].spec.direction).toEqual({ azimuthDeg: 180, elevationDeg: 90 });
    expect(views[0].spec.frame).toEqual({ kind: "intent" });
    expect(views[0].spec.lens.projection).toBe("orthographic");
    expect(views[1].spec.direction.azimuthDeg).toBe(0); // along the line
    expect(views[1].spec.direction.elevationDeg).toBeLessThan(15);
    for (const v of views) validate(v.spec);
  });
  it("a grid line with storeysPresent cuts the plan at its first storey", () => {
    const [plan] = viewsForIntent(intent("grid_line_consistency", { axis: "Y", value: 3.2, storeysPresent: ["Floor 1", "Floor 2"] }));
    expect(plan.spec.cut).toEqual({ kind: "storeyPlan", storey: "Floor 1", heightM: PLAN_CUT_HEIGHT_M });
  });
  it("a column stack at (x, y): a level view across and along, framed base to top", () => {
    const views = viewsForIntent(intent("structural_column_support", { x: 39.179, y: 43.365, storeys: ["Floor 0", "Floor 1"] }));
    expect(views.map((v) => v.rule)).toEqual(["stack", "stack"]);
    expect(views[0].spec.framing).toEqual({ mode: "fill", fill: 0.8 });
    expect(views[0].spec.direction.elevationDeg).toBeLessThan(10);
    for (const v of views) validate(v.spec);
  });
  it("stack terminations and vertical links are stacks too (no x,y in their metrics)", () => {
    expect(viewsForIntent(intent("structural_stack_termination", { stackStoreys: ["Floor 0", "Floor 1"] }))[0].rule).toBe("stack");
    // Rolled up per storey since 2026-10-09: the record is a
    // storey-level fact and carries `storey` + `stackIds`, so it takes the storey plan, not the stack views.
    expect(viewsForIntent(intent("structural_stack_termination", { storey: "Floor 2", stackIds: ["k-colsupport-a-b"], stackCount: 1 }))[0].rule).toBe("storey");
    expect(viewsForIntent(intent("circulation_vertical_link", { storeys: ["Floor 0", "Floor 1"], totalStoreys: 2 }))[0].rule).toBe("stack");
  });
  it("one storey: an orthographic storey plan at the shared scale, cut at eye height", () => {
    const [plan] = viewsForIntent(intent("access_isolated_space", { storey: "Floor 2", isolatedCount: 3 }));
    expect(plan.rule).toBe("storey");
    expect(plan.spec.direction).toEqual({ azimuthDeg: 180, elevationDeg: 90 });
    expect(plan.spec.frame).toEqual({ kind: "building" });
    expect(plan.spec.lens).toEqual({ projection: "orthographic", metresPerPixel: STOREY_PLAN_MPP });
    expect(plan.spec.cut).toEqual({ kind: "storeyPlan", storey: "Floor 2", heightM: PLAN_CUT_HEIGHT_M, keep: "below" });
    validate(plan.spec);
  });
  it("several storeys with a footprint: one plan per storey, all at the same scale", () => {
    const views = viewsForIntent(intent("vertical_space_connection", { storeys: ["Floor 0", "Floor 1", "Floor 2"], footprint: [1, 2] }));
    expect(views.map((v) => v.name)).toEqual(["plan-Floor 0", "plan-Floor 1", "plan-Floor 2"]);
    expect(new Set(views.map((v) => v.spec.lens.metresPerPixel)).size).toBe(1);
    expect(views[1].spec.cut.storey).toBe("Floor 1");
  });
  it("repeated units are storeys too, by type", () => {
    const views = viewsForIntent(intent("unit_type_recurrence", { storeys: ["Floor 1", "Floor 2"], instanceCount: 2 }));
    expect(views).toHaveLength(2);
    expect(views[0].rule).toBe("storeys");
  });
  it("envelope and facade types: an exterior perspective in the building frame", () => {
    for (const type of ["envelope_setback", "curtainwall_assembly", "egress_external_access", "window_lighting_cluster"]) {
      const [v] = viewsForIntent(intent(type, { storey: "Floor 0" }));
      expect(v.rule).toBe("envelope");
      expect(v.spec.frame).toEqual({ kind: "building" });
      expect(v.spec.lens.projection).toBe("perspective");
      expect(v.spec.direction.elevationDeg).toBeGreaterThan(15);
      validate(v.spec);
    }
  });
  it("beam modules: a reflected ceiling plan, looked at from below", () => {
    const [v] = viewsForIntent(intent("beam_framing_module", { spanM: 6.0, storey: "Floor 1", count: 4 }));
    expect(v.rule).toBe("ceiling");
    expect(v.spec.direction.elevationDeg).toBe(-90);
    expect(v.spec.cut).toMatchObject({ kind: "storeyPlan", storey: "Floor 1", keep: "above" });
  });
  it("a property outlier: a close-up", () => {
    const [v] = viewsForIntent(intent("convention_outlier", { property: "FireRating", outlierCount: 2 }));
    expect(v.rule).toBe("outlier");
    expect(v.spec.framing).toEqual({ mode: "fill", fill: 0.7 });
    validate(v.spec);
  });
  it("no rule: today's behaviour, as one default view", () => {
    expect(viewsForIntent(intent("something_new", { foo: 1 }))).toEqual([{ name: "default", spec: {}, rule: "default" }]);
    expect(viewsForIntent({ id: "k" })).toEqual([{ name: "default", spec: {}, rule: "default" }]);
  });
  it("every rule scopes to the intent by id", () => {
    const all = [
      ...viewsForIntent(intent("alignment_column_group", { axis: "X", value: 1 }, "A")),
      ...viewsForIntent(intent("structural_column_support", { x: 1, y: 2 }, "B")),
      ...viewsForIntent(intent("fire_compartment", { storey: "F" }, "C")),
    ];
    for (const v of all) expect(v.spec.scope).toEqual({ kind: "intent", intentId: expect.stringMatching(/^[ABC]$/) });
  });
});
