import { describe, it, expect } from "vitest";

import {
  DEFAULT_PADDING,
  VIEW_SPEC_SCHEMA,
  defaultViewSpec,
  describeViewSpec,
  resolveViewSpec,
} from "../../views/viewSpec.js";

describe("viewSpec: an empty spec is today's behaviour", () => {
  it("resolves {} to the defaults", () => {
    expect(resolveViewSpec({})).toEqual(defaultViewSpec());
    expect(resolveViewSpec()).toEqual(defaultViewSpec());
  });
  it("keeps the orbit direction, the Context slider's value and the current lens by default", () => {
    const s = resolveViewSpec({});
    expect(s.direction).toBeNull();
    expect(s.framing).toMatchObject({ mode: "context", context: null, padding: DEFAULT_PADDING });
    expect(s.lens).toEqual({ projection: "current", fovDeg: null, metresPerPixel: null });
    expect(s.scope.kind).toBe("current");
    expect(s.frame.kind).toBe("world");
    expect(s.cut.kind).toBe("none");
    expect(s.image).toBeNull();
    expect(s.transition).toBe(false);
  });
  it("carries the schema number", () => {
    expect(resolveViewSpec({}).schema).toBe(VIEW_SPEC_SCHEMA);
    expect(() => resolveViewSpec({ schema: 99 })).toThrow(/schema 99/);
  });
});

describe("viewSpec: merging and validation", () => {
  it("merges a partial group over its defaults", () => {
    const s = resolveViewSpec({ direction: { azimuthDeg: 135, elevationDeg: 30 }, framing: { context: 0.5 } });
    expect(s.direction).toEqual({ azimuthDeg: 135, elevationDeg: 30 });
    expect(s.framing).toEqual({ mode: "context", context: 0.5, fill: null, padding: DEFAULT_PADDING, fit: "sphere" });
  });
  it("reports every problem at once, by field", () => {
    const run = () =>
      resolveViewSpec({
        scope: { kind: "nowhere" },
        direction: { azimuthDeg: "x", elevationDeg: 120 },
        framing: { context: 2 },
        bogus: 1,
      });
    expect(run).toThrow(/scope\.kind/);
    expect(run).toThrow(/direction\.azimuthDeg/);
    expect(run).toThrow(/direction\.elevationDeg/);
    expect(run).toThrow(/framing\.context/);
    expect(run).toThrow(/bogus is not a known field/);
  });
  it("rejects unknown fields inside a group", () => {
    expect(() => resolveViewSpec({ lens: { zoom: 2 } })).toThrow(/lens\.zoom is not a known field/);
    expect(() => resolveViewSpec({ direction: { azimuthDeg: 0, elevationDeg: 0, roll: 5 } })).toThrow(/direction\.roll/);
  });
  it("needs an intent id for an intent scope and GlobalIds for a guids scope", () => {
    expect(() => resolveViewSpec({ scope: { kind: "intent" } })).toThrow(/scope\.intentId is required/);
    expect(resolveViewSpec({ scope: { kind: "intent", intentId: "k-1" } }).scope.intentId).toBe("k-1");
    expect(() => resolveViewSpec({ scope: { kind: "guids", guids: [] } })).toThrow(/scope\.guids/);
    expect(resolveViewSpec({ scope: { kind: "guids", guids: ["a", "b"] } }).scope.guids).toEqual(["a", "b"]);
  });
  it("accepts the whole elevation range including looking up, and any azimuth", () => {
    expect(resolveViewSpec({ direction: { azimuthDeg: -45, elevationDeg: -90 } }).direction).toEqual({ azimuthDeg: -45, elevationDeg: -90 });
    expect(resolveViewSpec({ direction: { azimuthDeg: 720, elevationDeg: 90 } }).direction.azimuthDeg).toBe(720);
  });
  it("lens: projection and fov are checked, fov stays null unless asked", () => {
    expect(resolveViewSpec({ lens: { projection: "orthographic" } }).lens.projection).toBe("orthographic");
    expect(() => resolveViewSpec({ lens: { projection: "fisheye" } })).toThrow(/lens\.projection/);
    expect(() => resolveViewSpec({ lens: { fovDeg: 5 } })).toThrow(/lens\.fovDeg/);
    expect(resolveViewSpec({ lens: { fovDeg: 60 } }).lens.fovDeg).toBe(60);
  });
  it("transition must be a boolean", () => {
    expect(resolveViewSpec({ transition: true }).transition).toBe(true);
    expect(() => resolveViewSpec({ transition: "yes" })).toThrow(/transition/);
  });
});

describe("viewSpec: the fields that landed after phase 1", () => {
  it("frame fill, metres per pixel and image size are accepted (phase 2) and checked", () => {
    expect(resolveViewSpec({ framing: { mode: "fill", fill: 0.6 } }).framing).toMatchObject({ mode: "fill", fill: 0.6 });
    expect(() => resolveViewSpec({ framing: { mode: "fill" } })).toThrow(/framing\.fill must be a number in \(0, 1\.5\]/);
    expect(() => resolveViewSpec({ framing: { fill: 2 } })).toThrow(/framing\.fill/);
    expect(resolveViewSpec({ lens: { metresPerPixel: 0.02 } }).lens.metresPerPixel).toBe(0.02);
    expect(() => resolveViewSpec({ lens: { metresPerPixel: 0 } })).toThrow(/lens\.metresPerPixel/);
    expect(() => resolveViewSpec({ framing: { mode: "fill", fill: 0.5 }, lens: { metresPerPixel: 0.02 } })).toThrow(/both set the scale/);
    expect(resolveViewSpec({ image: { width: 1024, height: 768 } }).image).toEqual({ width: 1024, height: 768, pixelRatio: 1 });
    expect(() => resolveViewSpec({ image: { width: 10, height: 768 } })).toThrow(/image\.width and image\.height/);
    expect(() => resolveViewSpec({ image: { width: 640, height: 480, pixelRatio: 9 } })).toThrow(/image\.pixelRatio/);
    expect(() => resolveViewSpec({ image: { width: 640, height: 480, format: "jpg" } })).toThrow(/image\.format is not a known field/);
  });
  it("cuts are accepted per kind, with defaults, and checked field by field (phase 3)", () => {
    expect(resolveViewSpec({ cut: { kind: "storeyPlan", storey: "Floor 1" } }).cut).toEqual({ kind: "storeyPlan", storey: "Floor 1", heightM: 1.2, keep: "below" });
    expect(resolveViewSpec({ cut: { kind: "storeyPlan", storey: "Roof", heightM: 2.6, keep: "above" } }).cut.keep).toBe("above");
    expect(() => resolveViewSpec({ cut: { kind: "storeyPlan" } })).toThrow(/cut\.storey must name a storey/);
    expect(() => resolveViewSpec({ cut: { kind: "storeyPlan", storey: "F", keep: "sideways" } })).toThrow(/cut\.keep/);
    expect(() => resolveViewSpec({ cut: { kind: "storeyPlan", storey: "F", marginM: 1 } })).toThrow(/cut\.marginM is not a field of cut\.kind 'storeyPlan'/);
    expect(resolveViewSpec({ cut: { kind: "sectionPlane" } }).cut).toEqual({ kind: "sectionPlane", point: null, normal: null, offsetM: 0, flip: false });
    expect(() => resolveViewSpec({ cut: { kind: "sectionPlane", normal: [0, 0, 0] } })).toThrow(/cut\.normal/);
    expect(resolveViewSpec({ cut: { kind: "sectionBox" } }).cut).toEqual({ kind: "sectionBox", marginM: 0.5 });
    expect(() => resolveViewSpec({ cut: { kind: "sectionBox", marginM: -1 } })).toThrow(/cut\.marginM/);
    expect(() => resolveViewSpec({ cut: { kind: "guillotine" } })).toThrow(/cut\.kind must be one of/);
  });
  it("scene settings are accepted and checked; outlines stay refused by name", () => {
    const s = resolveViewSpec({ scene: { hiddenClasses: ["IFCROOF", "IFCSLAB"], colorMode: "numbered", theme: "light", nonMemberTransparency: 95 } });
    expect(s.scene).toMatchObject({ hiddenClasses: ["IFCROOF", "IFCSLAB"], colorMode: "numbered", theme: "light", nonMemberTransparency: 95, color: null });
    expect(resolveViewSpec({ scene: { colorMode: "single", color: "#FF6A00" } }).scene.color).toBe("#FF6A00");
    expect(() => resolveViewSpec({ scene: { color: "orange" } })).toThrow(/scene\.color/);
    expect(() => resolveViewSpec({ scene: { nonMemberTransparency: 120 } })).toThrow(/scene\.nonMemberTransparency/);
    expect(() => resolveViewSpec({ scene: { hiddenClasses: [""] } })).toThrow(/scene\.hiddenClasses/);
    expect(() => resolveViewSpec({ scene: { outlines: true } })).toThrow(/PostproductionRenderer/);
    expect(() => resolveViewSpec({ scene: { colorMode: "rainbow" } })).toThrow(/scene\.colorMode must be one of/);
    expect(() => resolveViewSpec({ scene: { theme: "sepia" } })).toThrow(/scene\.theme must be one of/);
  });
  it("intent frames are accepted; unknown frame kinds are not", () => {
    expect(resolveViewSpec({ frame: { kind: "intent" } }).frame.kind).toBe("intent");
    expect(() => resolveViewSpec({ frame: { kind: "galactic" } })).toThrow(/frame\.kind must be one of/);
  });
});

describe("describeViewSpec", () => {
  it("names the common cases", () => {
    expect(describeViewSpec(resolveViewSpec({}))).toBe("keep direction");
    expect(describeViewSpec(resolveViewSpec({ direction: { azimuthDeg: 45, elevationDeg: 20 } }))).toBe("az 45° · el 20°");
    expect(describeViewSpec(resolveViewSpec({ direction: { azimuthDeg: 0, elevationDeg: 90 } }))).toBe("plan");
    expect(describeViewSpec(resolveViewSpec({ direction: { azimuthDeg: 180, elevationDeg: 90 }, frame: { kind: "building" } }))).toBe(
      "plan (roll 180°) · building frame",
    );
    expect(describeViewSpec(resolveViewSpec({ cut: { kind: "storeyPlan", storey: "Floor 2" } }))).toBe("keep direction · plan cut at Floor 2");
    expect(
      describeViewSpec(
        resolveViewSpec({ scope: { kind: "building" }, direction: { azimuthDeg: 0, elevationDeg: 0 }, lens: { projection: "orthographic" } }),
      ),
    ).toBe("az 0° · el 0° · whole building · orthographic");
  });
});
