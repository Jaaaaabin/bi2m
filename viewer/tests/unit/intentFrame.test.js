import { describe, it, expect } from "vitest";

import { frameFromMemberCentres, ifcPlanToScene, intentFrameFromMetrics } from "../../views/intentFrame.js";

// The coordination translation measured on example_autcon.ifc (phase 0), and
// the two record values that were checked against the scene there.
const T = [-29.266, -2.035, 37.981];
const fallback = { centre: [10, 5, -6], yawDeg: 17 };

describe("intentFrame: the measured IFC -> scene mapping", () => {
  it("maps a plan point: x + T.x, -y + T.z, at the given height", () => {
    const [x, y, z] = ifcPlanToScene(39.179, 43.365, T, 5);
    expect(x).toBeCloseTo(9.913, 9); // the column stack's measured scene x
    expect(y).toBe(5);
    expect(z).toBeCloseTo(-5.384, 9); // and its measured scene z
  });
  it("an 'axis X' line becomes the plane x = value + T.x, running along scene z (yaw 0)", () => {
    const f = intentFrameFromMetrics({ axis: "X", value: 39.179, toleranceM: 0.01 }, T, fallback);
    expect(f.source).toBe("metrics.axis");
    expect(f.yawDeg).toBe(0);
    expect(f.origin[0]).toBeCloseTo(9.913, 9);
    expect(f.origin[1]).toBe(5);
    expect(f.origin[2]).toBe(-6); // the scope centre along the line
  });
  it("an 'axis Y' line becomes z = -value + T.z, running along scene x (yaw 90)", () => {
    const f = intentFrameFromMetrics({ axis: "y", value: 43.365 }, T, fallback);
    expect(f.yawDeg).toBe(90);
    expect(f.origin[2]).toBeCloseTo(-5.384, 9);
    expect(f.origin[0]).toBe(10);
  });
  it("a stack at (x, y) takes the building's yaw and the stack as origin", () => {
    const f = intentFrameFromMetrics({ x: 39.179, y: 43.365, storeys: ["Floor 0"] }, T, fallback);
    expect(f).toEqual({ yawDeg: 17, origin: [expect.closeTo(9.913, 9), 5, expect.closeTo(-5.384, 9)], source: "metrics.xy" });
  });
  it("metrics without geometry give null", () => {
    expect(intentFrameFromMetrics({ storey: "Floor 1", roomCount: 3 }, T, fallback)).toBeNull();
    expect(intentFrameFromMetrics(null, T, fallback)).toBeNull();
    expect(intentFrameFromMetrics({ axis: "Z", value: 1 }, T, fallback)).toBeNull();
  });
});

describe("intentFrame: principal axis of the members", () => {
  const line = (yawDeg, n = 6, step = 3) => {
    const a = (yawDeg * Math.PI) / 180;
    return Array.from({ length: n }, (_, i) => [i * step * Math.sin(a) + 1, 2, i * step * Math.cos(a) - 4]);
  };
  for (const yaw of [0, 30, 90, 150]) {
    it(`members along a ${yaw}° line read back as yaw ${yaw}`, () => {
      const f = frameFromMemberCentres(line(yaw));
      expect(f.source).toBe("members.pca");
      expect(f.yawDeg).toBeCloseTo(yaw, 6);
      expect(f.ratio).toBe(Infinity); // a perfect line has no second axis
    });
  }
  it("180° is 0°: a line has two directions, a frame needs one", () => {
    expect(frameFromMemberCentres(line(180)).yawDeg).toBeCloseTo(0, 6);
  });
  it("the origin is the members' mean", () => {
    const f = frameFromMemberCentres([
      [0, 0, 0],
      [4, 0, 0],
    ]);
    expect(f.origin).toEqual([2, 0, 0]);
    expect(f.yawDeg).toBeCloseTo(90, 9);
  });
  it("an isotropic layout (a square of columns) has no axis", () => {
    expect(
      frameFromMemberCentres([
        [0, 0, 0],
        [6, 0, 0],
        [0, 0, 6],
        [6, 0, 6],
      ]),
    ).toBeNull();
  });
  it("fewer than two distinct points: null", () => {
    expect(frameFromMemberCentres([[1, 2, 3]])).toBeNull();
    expect(frameFromMemberCentres([])).toBeNull();
    expect(
      frameFromMemberCentres([
        [1, 2, 3],
        [1, 2, 3],
      ]),
    ).toBeNull();
  });
});
