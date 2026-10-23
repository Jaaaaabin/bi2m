import { describe, it, expect, vi } from "vitest";
import * as THREE from "three";

import {
  anglesFromOffset,
  azimuthDegFromThetaRad,
  elevationDegFromPolarRad,
  normalizeAzimuthDeg,
  offsetFromAngles,
  polarRadFromElevationDeg,
  thetaRadFromAzimuthDeg,
} from "../../views/direction.js";

// The seven presets are read from cameraViews.js itself, not retyped here:
// the point of this file is that the angle convention reproduces the vectors
// the app has always used, to float precision. Same mocks as
// cameraViews.test.js - the framing module pulls in @thatopen for
// BoundingBoxer, which the constants never touch.
vi.mock("@thatopen/components", () => ({}));
vi.mock("../../highlighting.js", () => ({ resolveGuidIndex: async () => new Map() }));
const cv = await import("../../cameraViews.js");

const PRESETS = {
  TOP_VIEW_OFFSET: cv.TOP_VIEW_OFFSET,
  SIDE_VIEW_OFFSET: cv.SIDE_VIEW_OFFSET,
  PLAN_VIEW_OFFSET: cv.PLAN_VIEW_OFFSET,
  DEFAULT_VIEW_OFFSET: cv.DEFAULT_VIEW_OFFSET,
  FRONT_VIEW_OFFSET: cv.FRONT_VIEW_OFFSET,
  BACK_VIEW_OFFSET: cv.BACK_VIEW_OFFSET,
  LEFT_VIEW_OFFSET: cv.LEFT_VIEW_OFFSET,
  RIGHT_VIEW_OFFSET: cv.RIGHT_VIEW_OFFSET,
};

// Expected angles DERIVED from each constant (never hardcoded): elevation is
// the angle above the XZ plane, azimuth the bearing from +Z toward +X.
const derive = (v) => {
  const u = v.clone().normalize();
  return {
    elevationDeg: THREE.MathUtils.radToDeg(Math.asin(u.y)),
    azimuthDeg: normalizeAzimuthDeg(THREE.MathUtils.radToDeg(Math.atan2(u.x, u.z))),
  };
};

const expectVector = (got, want, digits = 12) => {
  expect(got.x).toBeCloseTo(want.x, digits);
  expect(got.y).toBeCloseTo(want.y, digits);
  expect(got.z).toBeCloseTo(want.z, digits);
};

describe("direction: the seven presets are (azimuth, elevation) pairs", () => {
  for (const [name, vector] of Object.entries(PRESETS)) {
    it(`${name} round-trips through offsetFromAngles / anglesFromOffset`, () => {
      const unit = vector.clone().normalize();
      const angles = anglesFromOffset(unit);
      const want = derive(unit);
      expect(angles.elevationDeg).toBeCloseTo(want.elevationDeg, 10);
      expect(angles.azimuthDeg).toBeCloseTo(want.azimuthDeg, 10);
      expectVector(offsetFromAngles(angles.azimuthDeg, angles.elevationDeg), unit);
    });
  }

  it("names the presets the way the panel describes them", () => {
    // The +X/+Z corner every diagonal preset shares is a round 45°.
    expect(anglesFromOffset(cv.SIDE_VIEW_OFFSET)).toMatchObject({
      azimuthDeg: expect.closeTo(45, 9),
      elevationDeg: expect.closeTo(45, 9),
    });
    expect(anglesFromOffset(cv.DEFAULT_VIEW_OFFSET).elevationDeg).toBeCloseTo(20, 9);
    expect(anglesFromOffset(cv.DEFAULT_VIEW_OFFSET).azimuthDeg).toBeCloseTo(45, 9);
    // The old aerial was recorded as "~49.7°": derived here, not typed in.
    const top = anglesFromOffset(cv.TOP_VIEW_OFFSET);
    expect(top.azimuthDeg).toBeCloseTo(45, 9);
    expect(Math.abs(top.elevationDeg - 49.7)).toBeLessThan(0.1);
    // Level views along the world axes.
    expect(anglesFromOffset(cv.FRONT_VIEW_OFFSET)).toEqual({ azimuthDeg: 0, elevationDeg: 0 });
    expect(anglesFromOffset(cv.RIGHT_VIEW_OFFSET).azimuthDeg).toBeCloseTo(90, 9);
    expect(anglesFromOffset(cv.BACK_VIEW_OFFSET).azimuthDeg).toBeCloseTo(180, 9);
    expect(anglesFromOffset(cv.LEFT_VIEW_OFFSET).azimuthDeg).toBeCloseTo(270, 9);
  });

  it("at the pole the vector carries no azimuth, so it reports 0 - like camera-controls", () => {
    expect(anglesFromOffset(cv.PLAN_VIEW_OFFSET)).toEqual({ azimuthDeg: 0, elevationDeg: 90 });
    // Any azimuth at el 90 produces the same vector: the azimuth has become
    // the roll, and is applied through controls.rotateTo, not the vector.
    expectVector(offsetFromAngles(45, 90), cv.PLAN_VIEW_OFFSET);
    expectVector(offsetFromAngles(300, 90), cv.PLAN_VIEW_OFFSET);
  });
});

describe("direction: beyond the presets", () => {
  it("negative elevation looks up from below", () => {
    const v = offsetFromAngles(0, -30);
    expect(v.y).toBeCloseTo(-0.5, 12);
    expect(v.z).toBeCloseTo(Math.cos(THREE.MathUtils.degToRad(30)), 12);
  });
  it("a frame yaw rotates the whole compass: frame Front at yaw 90 is world +X", () => {
    expectVector(offsetFromAngles(0, 0, 90), new THREE.Vector3(1, 0, 0));
    expect(anglesFromOffset(new THREE.Vector3(1, 0, 0), 90).azimuthDeg).toBeCloseTo(0, 9);
    // and world +Z, read in that frame, is 270 (its Left).
    expect(anglesFromOffset(new THREE.Vector3(0, 0, 1), 90).azimuthDeg).toBeCloseTo(270, 9);
  });
  it("normalizes azimuths into [0, 360) and never returns -0", () => {
    expect(normalizeAzimuthDeg(-90)).toBe(270);
    expect(normalizeAzimuthDeg(725)).toBe(5);
    expect(Object.is(normalizeAzimuthDeg(-360), 0)).toBe(true);
    expect(Object.is(normalizeAzimuthDeg(0), 0)).toBe(true);
    expect(normalizeAzimuthDeg(NaN)).toBeNaN();
  });
  it("converts to and from camera-controls' own angles", () => {
    expect(thetaRadFromAzimuthDeg(90)).toBeCloseTo(Math.PI / 2, 12);
    expect(thetaRadFromAzimuthDeg(270)).toBeCloseTo(-Math.PI / 2, 12); // unwrapped for rotateTo
    expect(azimuthDegFromThetaRad(-Math.PI / 2)).toBeCloseTo(270, 9);
    expect(azimuthDegFromThetaRad(5 * Math.PI)).toBeCloseTo(180, 9); // accumulated turns fold
    expect(polarRadFromElevationDeg(90)).toBeCloseTo(0, 12);
    expect(polarRadFromElevationDeg(0)).toBeCloseTo(Math.PI / 2, 12);
    expect(elevationDegFromPolarRad(Math.PI / 2)).toBeCloseTo(0, 9);
    expect(elevationDegFromPolarRad(0)).toBeCloseTo(90, 9);
  });
  it("tolerates an unnormalized input vector", () => {
    const a = anglesFromOffset(new THREE.Vector3(10, 10 * Math.SQRT2, 10));
    expect(a.azimuthDeg).toBeCloseTo(45, 9);
    expect(a.elevationDeg).toBeCloseTo(45, 9);
  });
});
