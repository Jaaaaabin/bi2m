import { describe, it, expect, vi } from "vitest";
import * as THREE from "three";

// cameraViews.js imports @thatopen/components for BoundingBoxer and
// highlighting.js for resolveGuidIndex; neither is exercised by the pure
// framing math under test.
vi.mock("@thatopen/components", () => ({}));
vi.mock("../../highlighting.js", () => ({ resolveGuidIndex: async () => new Map() }));

const { clampContext, scopeFitSphere, DEFAULT_CONTEXT_AMOUNT, SCOPE_EDGE_PADDING } =
  await import("../../cameraViews.js");

const box = (cx, cy, cz, half) =>
  new THREE.Box3(
    new THREE.Vector3(cx - half, cy - half, cz - half),
    new THREE.Vector3(cx + half, cy + half, cz + half),
  );

describe("clampContext", () => {
  it("clamps into [0, 1]", () => {
    expect(clampContext(-1)).toBe(0);
    expect(clampContext(2)).toBe(1);
    expect(clampContext(0.35)).toBe(0.35);
  });
  it("falls back to the default for non-finite input", () => {
    expect(clampContext(NaN)).toBe(DEFAULT_CONTEXT_AMOUNT);
    expect(clampContext(undefined)).toBe(DEFAULT_CONTEXT_AMOUNT);
  });
});

describe("scopeFitSphere (blend, never max())", () => {
  const scope = box(10, 0, 10, 2); // a small intent
  const building = box(0, 0, 0, 50); // the whole building around it
  const scopeSphere = scope.getBoundingSphere(new THREE.Sphere());
  const buildingSphere = building.getBoundingSphere(new THREE.Sphere());

  it("at context 0 frames the intent with the edge padding", () => {
    const s = scopeFitSphere(scope, building, 0);
    expect(s.radius).toBeCloseTo(scopeSphere.radius * (1 + SCOPE_EDGE_PADDING), 6);
    expect(s.center.distanceTo(scopeSphere.center)).toBeCloseTo(0, 6);
  });
  it("at context 1 is exactly the whole-building sphere", () => {
    const s = scopeFitSphere(scope, building, 1);
    expect(s.radius).toBeCloseTo(buildingSphere.radius, 6);
    expect(s.center.distanceTo(buildingSphere.center)).toBeCloseTo(0, 6);
  });
  it("radius is strictly monotonic in context (the control never goes dead)", () => {
    let last = -Infinity;
    for (const t of [0, 0.1, 0.25, 0.5, 0.75, 0.9, 1]) {
      const r = scopeFitSphere(scope, building, t).radius;
      expect(r).toBeGreaterThan(last);
      last = r;
    }
  });
  it("keeps the intent inside the frame at every context", () => {
    for (const t of [0, 0.2, 0.5, 0.8, 1]) {
      const s = scopeFitSphere(scope, building, t);
      expect(s.center.distanceTo(scopeSphere.center) + scopeSphere.radius).toBeLessThanOrEqual(
        s.radius + 1e-9,
      );
    }
  });
  it("a building-sized scope still moves with the slider (the max() regression)", () => {
    const big = box(1, 0, 1, 48);
    const r0 = scopeFitSphere(big, building, 0).radius;
    const r1 = scopeFitSphere(big, building, 1).radius;
    expect(r1).not.toBeCloseTo(r0, 6);
  });
  it("without a building box returns the padded scope sphere", () => {
    const s = scopeFitSphere(scope, null, 0.7);
    expect(s.radius).toBeCloseTo(scopeSphere.radius * (1 + SCOPE_EDGE_PADDING), 6);
  });
});
