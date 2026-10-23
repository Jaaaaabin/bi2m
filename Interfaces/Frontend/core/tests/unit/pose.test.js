import { describe, it, expect } from "vitest";

import {
  distanceForHalfHeight,
  distanceToFitSphere,
  halfHeightAtTarget,
  halfHeightForMetresPerPixel,
  metresPerPixel,
  pixelsForTolerance,
  zoomForHalfHeight,
  zoomToFitSphere,
} from "../../views/pose.js";

const deg = (d) => (d * Math.PI) / 180;

describe("pose: fit distance mirrors camera-controls' getDistanceToFitSphere", () => {
  it("at the library's old 60° lens on a landscape canvas the fit is exactly 2r", () => {
    expect(distanceToFitSphere(10, 60, 1.5)).toBeCloseTo(20, 10);
  });
  it("at this app's 38° lens it is r / sin(19°)", () => {
    expect(distanceToFitSphere(10, 38, 1.45)).toBeCloseTo(10 / Math.sin(deg(19)), 10);
  });
  it("a portrait canvas is limited by the horizontal field of view instead", () => {
    const aspect = 0.5;
    const hFov = 2 * Math.atan(Math.tan(deg(19)) * aspect);
    expect(distanceToFitSphere(10, 38, aspect)).toBeCloseTo(10 / Math.sin(hFov / 2), 10);
    // and is further back than the landscape fit for the same sphere
    expect(distanceToFitSphere(10, 38, aspect)).toBeGreaterThan(distanceToFitSphere(10, 38, 1.5));
  });
  it("orthographic zoom is the tighter of the two frustum ratios", () => {
    expect(zoomToFitSphere(10, 100, 50)).toBeCloseTo(2.5, 12);
    expect(zoomToFitSphere(10, 30, 50)).toBeCloseTo(1.5, 12);
  });
});

describe("pose: the half-height invariant (toggleProjection's, cameraViews.js)", () => {
  it("perspective: distance · tan(fov/2), and back", () => {
    const h = halfHeightAtTarget({ projection: "Perspective", distance: 50, fovDeg: 38 });
    expect(h).toBeCloseTo(50 * Math.tan(deg(19)), 12);
    expect(distanceForHalfHeight(h, 38)).toBeCloseTo(50, 10);
  });
  it("orthographic: (top − bottom) / 2 / zoom, and back", () => {
    const h = halfHeightAtTarget({ projection: "Orthographic", frustumHeight: 120, zoom: 3 });
    expect(h).toBeCloseTo(20, 12);
    expect(zoomForHalfHeight(h, 120)).toBeCloseTo(3, 12);
  });
  it("metres per pixel follows from the half-height and the canvas height", () => {
    // 20 m half-height on an 800 px tall canvas: 40 m over 800 px = 5 cm/px
    expect(metresPerPixel(20, 800)).toBeCloseTo(0.05, 12);
    expect(halfHeightForMetresPerPixel(0.05, 800)).toBeCloseTo(20, 12);
  });
  it("the resolution check: a 1 cm tolerance at 5 cm/px is a fifth of a pixel", () => {
    expect(pixelsForTolerance(0.01, 0.05)).toBeCloseTo(0.2, 12);
    expect(pixelsForTolerance(0.05, 0.01)).toBeCloseTo(5, 12);
  });
});
