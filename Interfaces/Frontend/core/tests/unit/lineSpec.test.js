import { describe, it, expect } from "vitest";

import {
  anchorGuids,
  anchorNeeds,
  closeLoop,
  extendEnds,
  isAnchor,
  normalizeLineSpec,
  resolveLinePoints,
  sampleArc,
  sampleSpline,
  DEFAULT_CIRCLE_SEGMENTS,
  DEFAULT_LINE_STYLE,
  DEFAULT_SPLINE_SAMPLES,
} from "../../views/lineSpec.js";

// The coordination translation measured on example_autcon.ifc (views.py
// phase 0) and the column stack intentFrame.test.js checks with it.
const T = [-29.266, -2.035, 37.981];

describe("normalizeLineSpec: defaults", () => {
  it("a two-point scene spec becomes a segment with the default style and a generated id", () => {
    const s = normalizeLineSpec({
      points: [
        [0, 0, 0],
        [1, 0, 0],
      ],
    });
    expect(s.kind).toBe("segment");
    expect(s.space).toBe("scene");
    expect(s.id).toMatch(/^line-\d+$/);
    expect(s.style).toEqual(DEFAULT_LINE_STYLE);
    expect(s.extend).toBe(0);
    expect(s.sortAlong).toBeNull();
    expect(s.meta).toEqual({});
  });
  it("three or more points default to a polyline; a given id, style and meta are kept", () => {
    const s = normalizeLineSpec({
      id: "a",
      points: [
        [0, 0, 0],
        [1, 0, 0],
        [2, 0, 0],
      ],
      style: { color: "#123456" },
      meta: { source: "test" },
    });
    expect(s.kind).toBe("polyline");
    expect(s.id).toBe("a");
    expect(s.style).toEqual({ ...DEFAULT_LINE_STYLE, color: "#123456" });
    expect(s.meta).toEqual({ source: "test" });
  });
  it("copies points, so the caller's arrays are not shared", () => {
    const p = [0, 0, 0];
    const s = normalizeLineSpec({ points: [p, [1, 1, 1]] });
    s.points[0][0] = 9;
    expect(p[0]).toBe(0);
  });
  it("anchors default to the center", () => {
    const s = normalizeLineSpec({ points: [{ guid: "A" }, { guid: "B", at: "top" }] });
    expect(s.points).toEqual([
      { guid: "A", at: "center" },
      { guid: "B", at: "top" },
    ]);
    expect(isAnchor(s.points[0])).toBe(true);
    expect(isAnchor([0, 0, 0])).toBe(false);
  });
});

describe("normalizeLineSpec: validation", () => {
  it("rejects too few points for the kind, and a lone point without a kind", () => {
    expect(() => normalizeLineSpec({ points: [[0, 0, 0]] })).toThrow(
      /single point needs an explicit kind/,
    );
    expect(() => normalizeLineSpec({ kind: "polyline", points: [[0, 0, 0]] })).toThrow(
      /at least 2 points/,
    );
    expect(() =>
      normalizeLineSpec({
        kind: "polygon",
        points: [
          [0, 0, 0],
          [1, 0, 0],
        ],
      }),
    ).toThrow(/at least 3 points/);
    expect(() =>
      normalizeLineSpec({
        kind: "circle",
        radius: 1,
        points: [
          [0, 0, 0],
          [1, 0, 0],
        ],
      }),
    ).toThrow(/at most 1 point/);
    expect(() => normalizeLineSpec({})).toThrow(/needs points/);
  });
  it("rejects unknown spaces, including the reserved 3D ifc space", () => {
    expect(() =>
      normalizeLineSpec({
        space: "ifc",
        points: [
          [0, 0, 0],
          [1, 1, 1],
        ],
      }),
    ).toThrow(/unknown space "ifc"/);
  });
  it("a segment with three points is a contradiction", () => {
    expect(() =>
      normalizeLineSpec({
        kind: "segment",
        points: [
          [0, 0, 0],
          [1, 0, 0],
          [2, 0, 0],
        ],
      }),
    ).toThrow(/at most 2 points/);
  });
  it("rejects a field the kind does not take, instead of ignoring it", () => {
    const tri = [
      [0, 0, 0],
      [1, 0, 0],
      [1, 0, 1],
    ];
    expect(() => normalizeLineSpec({ kind: "polygon", sortAlong: "z", points: tri })).toThrow(
      /sortAlong and extend apply to segment and polyline/,
    );
    expect(() => normalizeLineSpec({ kind: "spline", extend: 1, points: tri })).toThrow(
      /sortAlong and extend/,
    );
    expect(() => normalizeLineSpec({ kind: "polyline", radius: 1, points: tri })).toThrow(
      /radius applies to circle and arc/,
    );
    expect(() =>
      normalizeLineSpec({ kind: "circle", radius: 1, startDeg: 0, points: [[0, 0, 0]] }),
    ).toThrow(/startDeg and endDeg apply to an arc/);
    expect(() => normalizeLineSpec({ kind: "polygon", samples: 4, points: tri })).toThrow(
      /samples and closed apply to a spline/,
    );
    expect(() =>
      normalizeLineSpec({ kind: "outline", flattenY: "min", points: [{ guid: "S" }] }),
    ).toThrow(/flattenY does not apply to an outline/);
    expect(() => normalizeLineSpec({ kind: "outline", points: [[0, 0, 0]] })).toThrow(
      /outline takes one anchor/,
    );
  });
  it("needs the fields a round kind requires", () => {
    expect(() => normalizeLineSpec({ kind: "circle", points: [[0, 0, 0]] })).toThrow(/radius > 0/);
    expect(() => normalizeLineSpec({ kind: "circle", radius: -1, points: [[0, 0, 0]] })).toThrow(
      /radius > 0/,
    );
    expect(() => normalizeLineSpec({ kind: "arc", radius: 1, points: [[0, 0, 0]] })).toThrow(
      /startDeg and endDeg/,
    );
    expect(() =>
      normalizeLineSpec({ kind: "arc", radius: 1, startDeg: 10, endDeg: 10, points: [[0, 0, 0]] }),
    ).toThrow(/differ/);
    expect(() =>
      normalizeLineSpec({ kind: "circle", radius: 1, plane: "zz", points: [[0, 0, 0]] }),
    ).toThrow(/plane/);
    expect(() =>
      normalizeLineSpec({ kind: "circle", radius: 1, segments: 2, points: [[0, 0, 0]] }),
    ).toThrow(/segments/);
  });
  it("fills the round and spline defaults", () => {
    const c = normalizeLineSpec({ kind: "circle", radius: 2, points: [[0, 0, 0]] });
    expect([c.segments, c.plane, c.startDeg, c.endDeg]).toEqual([
      DEFAULT_CIRCLE_SEGMENTS,
      "xz",
      null,
      null,
    ]);
    const a = normalizeLineSpec({
      kind: "arc",
      radius: 2,
      startDeg: 0,
      endDeg: 90,
      points: [[0, 0, 0]],
    });
    expect(a.segments).toBe(16); // a quarter of the circle's 64
    const tiny = normalizeLineSpec({
      kind: "arc",
      radius: 2,
      startDeg: 0,
      endDeg: 5,
      points: [[0, 0, 0]],
    });
    expect(tiny.segments).toBe(8); // never fewer than 8 by default
    const sp = normalizeLineSpec({
      kind: "spline",
      points: [
        [0, 0, 0],
        [1, 1, 1],
      ],
    });
    expect([sp.samples, sp.closed]).toEqual([DEFAULT_SPLINE_SAMPLES, false]);
  });
  it("accepts an anchor as the ifcPlan height", () => {
    const s = normalizeLineSpec({
      space: "ifcPlan",
      height: { guid: "C" },
      points: [
        [0, 0],
        [1, 1],
      ],
    });
    expect(s.height).toEqual({ guid: "C", at: "center" });
    expect(() =>
      normalizeLineSpec({
        space: "ifcPlan",
        height: "low",
        points: [
          [0, 0],
          [1, 1],
        ],
      }),
    ).toThrow(/height must be a number/);
  });
  it("accepts {ifcZ} as the ifcPlan height, in the file's world metres", () => {
    const s = normalizeLineSpec({
      space: "ifcPlan",
      height: { ifcZ: -0.8, extra: 1 },
      points: [
        [0, 0],
        [1, 1],
      ],
    });
    expect(s.height).toEqual({ ifcZ: -0.8 });
    for (const ifcZ of [null, "3", Number.NaN, Infinity]) {
      expect(() =>
        normalizeLineSpec({
          space: "ifcPlan",
          height: { ifcZ },
          points: [
            [0, 0],
            [1, 1],
          ],
        }),
      ).toThrow(/height.ifcZ must be a number/);
    }
  });
  it("ifcPlan coordinates need a height; anchors alone do not", () => {
    expect(() =>
      normalizeLineSpec({
        space: "ifcPlan",
        points: [
          [0, 0],
          [1, 1],
        ],
      }),
    ).toThrow(/need a `height`/);
    expect(() =>
      normalizeLineSpec({ space: "ifcPlan", points: [{ guid: "A" }, { guid: "B" }] }),
    ).not.toThrow();
  });
  it("checks the dimension of a coordinate for its space", () => {
    expect(() =>
      normalizeLineSpec({
        points: [
          [0, 0],
          [1, 1],
        ],
      }),
    ).toThrow(/3 finite numbers in scene/);
    expect(() =>
      normalizeLineSpec({
        space: "ifcPlan",
        height: 0,
        points: [
          [0, 0, 0],
          [1, 1, 1],
        ],
      }),
    ).toThrow(/2 finite numbers in ifcPlan/);
    expect(() =>
      normalizeLineSpec({
        points: [
          [0, 0, NaN],
          [1, 1, 1],
        ],
      }),
    ).toThrow(/finite/);
  });
  it("validates the fat-line style fields", () => {
    const seg = [
      [0, 0, 0],
      [1, 0, 0],
    ];
    expect(normalizeLineSpec({ points: seg, style: { width: 3, dashed: true } }).style).toEqual({
      ...DEFAULT_LINE_STYLE,
      width: 3,
      dashed: true,
    });
    expect(() => normalizeLineSpec({ points: seg, style: { width: 0.5 } })).toThrow(/width/);
    expect(() => normalizeLineSpec({ points: seg, style: { dashed: true } })).toThrow(
      /dashed needs style.width/,
    );
    expect(() => normalizeLineSpec({ points: seg, style: { width: 2, gapSize: 0 } })).toThrow(
      /dashSize and style.gapSize/,
    );
  });
  it("rejects a bad anchor placement, sort axis, extension or style", () => {
    expect(() =>
      normalizeLineSpec({ points: [{ guid: "A", at: "middle" }, { guid: "B" }] }),
    ).toThrow(/unknown anchor "middle"/);
    expect(() =>
      normalizeLineSpec({
        sortAlong: "w",
        points: [
          [0, 0, 0],
          [1, 1, 1],
        ],
      }),
    ).toThrow(/sortAlong/);
    expect(() =>
      normalizeLineSpec({
        extend: -1,
        points: [
          [0, 0, 0],
          [1, 1, 1],
        ],
      }),
    ).toThrow(/extend/);
    expect(() =>
      normalizeLineSpec({
        style: { opacity: 2 },
        points: [
          [0, 0, 0],
          [1, 1, 1],
        ],
      }),
    ).toThrow(/opacity/);
  });
});

describe("resolveLinePoints", () => {
  const pd = (r) => ({ points: r.points, dropped: r.dropped }); // the old two-field view of a result
  it("passes scene coordinates through", () => {
    const s = normalizeLineSpec({
      points: [
        [1, 2, 3],
        [4, 5, 6],
      ],
    });
    expect(pd(resolveLinePoints(s))).toEqual({
      points: [
        [1, 2, 3],
        [4, 5, 6],
      ],
      dropped: [],
    });
  });
  it("converts ifcPlan with the measured formula: x + T.x, height, -y + T.z", () => {
    const s = normalizeLineSpec({
      space: "ifcPlan",
      height: 5,
      points: [
        [39.179, 43.365],
        [39.179, 50],
      ],
    });
    const { points } = resolveLinePoints(s, { T });
    expect(points[0][0]).toBeCloseTo(9.913, 9);
    expect(points[0][1]).toBe(5);
    expect(points[0][2]).toBeCloseTo(-5.384, 9);
    expect(points[1][2]).toBeCloseTo(-12.019, 9);
  });
  it("turns an {ifcZ} height into scene Y with the translation: z + T.y", () => {
    const s = normalizeLineSpec({
      space: "ifcPlan",
      height: { ifcZ: 3.3 },
      points: [
        [39.179, 43.365],
        [39.179, 50],
      ],
    });
    const { points } = resolveLinePoints(s, { T: [1, 6.0625, 2] });
    expect(points.map((p) => p[1])).toEqual([3.3 + 6.0625, 3.3 + 6.0625]);
    expect(points[0][0]).toBeCloseTo(40.179, 9);
    expect(points[0][2]).toBeCloseTo(-41.365, 9);
    expect(resolveLinePoints(s).points[0][1]).toBe(3.3);
  });
  it("takes anchors from the resolved map and drops the ones without geometry", () => {
    const s = normalizeLineSpec({
      points: [{ guid: "A", at: "bottom" }, { guid: "gone" }, { guid: "B", at: "top" }],
    });
    const anchors = new Map([
      ["A", { center: [0, 1, 0], bottom: [0, 0, 0], top: [0, 2, 0] }],
      ["gone", null],
      ["B", { center: [3, 1, 0], bottom: [3, 0, 0], top: [3, 2, 0] }],
    ]);
    expect(pd(resolveLinePoints(s, { anchors }))).toEqual({
      points: [
        [0, 0, 0],
        [3, 2, 0],
      ],
      dropped: ["gone"],
    });
  });
  it("mixes anchors and coordinates in one spec", () => {
    const s = normalizeLineSpec({ points: [{ guid: "A" }, [5, 5, 5]] });
    const anchors = new Map([["A", { center: [1, 1, 1], bottom: [1, 0, 1], top: [1, 2, 1] }]]);
    expect(resolveLinePoints(s, { anchors }).points).toEqual([
      [1, 1, 1],
      [5, 5, 5],
    ]);
  });
  it("sorts along the named scene axis before extending, so an interior point is never an end", () => {
    // Members in record order: the middle column first. Without the sort,
    // extend would push the first point (the middle one) sideways.
    const s = normalizeLineSpec({
      sortAlong: "z",
      extend: 1,
      points: [
        [9.9, 0, -5],
        [9.9, 0, -1],
        [9.9, 0, -9],
      ],
    });
    const { points } = resolveLinePoints(s);
    expect(points).toEqual([
      [9.9, 0, -10],
      [9.9, 0, -5],
      [9.9, 0, 0],
    ]);
  });
  it("extendEnds lengthens along the end segments and leaves degenerate ends alone", () => {
    expect(
      extendEnds(
        [
          [0, 0, 0],
          [3, 4, 0],
        ],
        5,
      ),
    ).toEqual([
      [-3, -4, 0],
      [6, 8, 0],
    ]);
    expect(
      extendEnds(
        [
          [0, 0, 0],
          [0, 0, 0],
        ],
        1,
      ),
    ).toEqual([
      [0, 0, 0],
      [0, 0, 0],
    ]);
    expect(
      extendEnds(
        [
          [0, 0, 0],
          [1, 0, 0],
        ],
        0,
      ),
    ).toEqual([
      [0, 0, 0],
      [1, 0, 0],
    ]);
  });
});

describe("flattenY", () => {
  // One X line's column feet on three storeys, in record order.
  const feet = [
    [9.9, -2, -5],
    [9.9, 1.7, -1],
    [9.9, 5.4, -9],
    [9.9, -2, -7],
  ];
  it("is off by default: a multi-storey line keeps its heights (the sawtooth)", () => {
    const { points } = resolveLinePoints(normalizeLineSpec({ sortAlong: "z", points: feet }));
    expect(points.map((p) => p[1])).toEqual([5.4, -2, -2, 1.7]);
  });
  it('"min" puts every point on the lowest foot, after the sort and before the extension', () => {
    const { points } = resolveLinePoints(
      normalizeLineSpec({ sortAlong: "z", flattenY: "min", extend: 1, points: feet }),
    );
    expect(points.every((p) => p[1] === -2)).toBe(true);
    expect(points[0]).toEqual([9.9, -2, -10]); // extended along the flat line, not the old slope
    expect(points.at(-1)).toEqual([9.9, -2, 0]);
  });
  it('"max" and a number are the other two heights', () => {
    const max = resolveLinePoints(normalizeLineSpec({ flattenY: "max", points: feet })).points;
    expect(max.every((p) => p[1] === 5.4)).toBe(true);
    const fixed = resolveLinePoints(normalizeLineSpec({ flattenY: 0.25, points: feet })).points;
    expect(fixed.every((p) => p[1] === 0.25)).toBe(true);
  });
  it("rejects anything else", () => {
    expect(() => normalizeLineSpec({ flattenY: "floor", points: feet })).toThrow(/flattenY/);
    expect(() => normalizeLineSpec({ flattenY: NaN, points: feet })).toThrow(/flattenY/);
  });
});

describe("resolveLinePoints: shapes", () => {
  const anchors = new Map([
    ["A", { center: [0, 1, 0], bottom: [0, 0, 0], top: [0, 2, 0] }],
    ["B", { center: [4, 1, 0], bottom: [4, 0, 0], top: [4, 2, 0] }],
    ["C", { center: [4, 1, 3], bottom: [4, 0, 3], top: [4, 2, 3] }],
    [
      "S",
      {
        center: [1, 0.5, 1],
        bottom: [1, 0, 1],
        top: [1, 1, 1],
        outline: [
          [
            [0, 0, 0],
            [2, 0, 0],
            [2, 0, 2],
            [0, 0, 2],
          ],
        ],
      },
    ],
    [
      "H",
      {
        center: [1, 0.5, 1],
        bottom: [1, 0, 1],
        top: [1, 1, 1],
        outline: [
          [
            [0, 0, 0],
            [6, 0, 0],
            [6, 0, 6],
            [0, 0, 6],
          ],
          [
            [2, 0, 2],
            [3, 0, 2],
            [3, 0, 3],
            [2, 0, 3],
          ],
        ],
      },
    ],
  ]);
  const r9 = (p) => p.map((c) => +c.toFixed(9) + 0); // + 0 turns -0 into 0
  it("a polygon closes on itself, through anchors too", () => {
    const { points, polylines } = resolveLinePoints(
      normalizeLineSpec({
        kind: "polygon",
        points: [
          { guid: "A", at: "bottom" },
          { guid: "B", at: "bottom" },
          { guid: "C", at: "bottom" },
        ],
      }),
      { anchors },
    );
    expect(points).toEqual([
      [0, 0, 0],
      [4, 0, 0],
      [4, 0, 3],
      [0, 0, 0],
    ]);
    expect(polylines).toEqual([points]);
    expect(
      closeLoop([
        [0, 0, 0],
        [1, 0, 0],
        [0, 0, 0],
      ]),
    ).toHaveLength(3); // already closed: unchanged
  });
  it("a spline passes through its points and has samples per segment", () => {
    const { points } = resolveLinePoints(
      normalizeLineSpec({
        kind: "spline",
        samples: 4,
        points: [{ guid: "A" }, { guid: "B" }, { guid: "C" }],
      }),
      { anchors },
    );
    expect(points).toHaveLength(4 * 2 + 1);
    expect(points[0]).toEqual([0, 1, 0]);
    expect(r9(points[4])).toEqual([4, 1, 0]);
    expect(r9(points.at(-1))).toEqual([4, 1, 3]);
    const closed = sampleSpline(
      [
        [0, 0, 0],
        [2, 0, 0],
        [2, 0, 2],
      ],
      3,
      true,
    );
    expect(closed).toHaveLength(3 * 3 + 1);
    expect(r9(closed.at(-1))).toEqual([0, 0, 0]);
  });
  it("a circle is segments + 1 points at the radius in the plane, ending where it starts", () => {
    const { points } = resolveLinePoints(
      normalizeLineSpec({
        kind: "circle",
        radius: 1.5,
        segments: 12,
        points: [{ guid: "A", at: "bottom" }],
      }),
      { anchors },
    );
    expect(points).toHaveLength(13);
    for (const p of points) {
      expect(Math.hypot(p[0], p[2])).toBeCloseTo(1.5, 9);
      expect(p[1]).toBe(0); // the xz plane keeps y
    }
    expect(r9(points.at(-1))).toEqual(r9(points[0]));
    const xy = sampleArc([0, 0, 5], 2, 0, 360, 4, "xy");
    expect(xy.every((p) => p[2] === 5)).toBe(true);
    expect(r9(xy[1])).toEqual([0, 2, 5]); // 90°: from +x toward +y
  });
  it("an arc spans its angles and flattens with the rest", () => {
    const { points } = resolveLinePoints(
      normalizeLineSpec({
        kind: "arc",
        radius: 2,
        startDeg: 0,
        endDeg: 90,
        segments: 2,
        flattenY: 7,
        points: [[1, 3, 1]],
      }),
    );
    expect(points.map(r9)).toEqual([[3, 7, 1], r9([1 + Math.SQRT2, 7, 1 + Math.SQRT2]), [1, 7, 3]]);
  });
  it("an ifcPlan shape takes its height from an anchor", () => {
    const T = [-29.266, -2.035, 37.981];
    const s = normalizeLineSpec({
      kind: "polygon",
      space: "ifcPlan",
      height: { guid: "A", at: "bottom" },
      points: [
        [39.279, 31.265],
        [43.949, 31.265],
        [43.949, 37.465],
        [39.279, 37.465],
      ],
    });
    const { points, dropped } = resolveLinePoints(s, { T, anchors });
    expect(dropped).toEqual([]);
    expect(points).toHaveLength(5);
    expect(points.every((p) => p[1] === 0)).toBe(true);
    expect(points[0][0]).toBeCloseTo(10.013, 9);
    expect(points[0][2]).toBeCloseTo(6.716, 9);
    const missing = resolveLinePoints(
      normalizeLineSpec({
        kind: "polygon",
        space: "ifcPlan",
        height: { guid: "gone" },
        points: s.points,
      }),
      { T, anchors },
    );
    expect(missing).toEqual({ points: [], polylines: [], dropped: ["gone"] });
  });
  it("an outline takes the element's floor loops, each closed, and reports a missing one", () => {
    const one = resolveLinePoints(normalizeLineSpec({ kind: "outline", points: [{ guid: "S" }] }), {
      anchors,
    });
    expect(one.polylines).toEqual([
      [
        [0, 0, 0],
        [2, 0, 0],
        [2, 0, 2],
        [0, 0, 2],
        [0, 0, 0],
      ],
    ]);
    expect(one.points).toBe(one.polylines[0]);
    const two = resolveLinePoints(normalizeLineSpec({ kind: "outline", points: [{ guid: "H" }] }), {
      anchors,
    });
    expect(two.polylines).toHaveLength(2);
    expect(two.polylines[1]).toEqual([
      [2, 0, 2],
      [3, 0, 2],
      [3, 0, 3],
      [2, 0, 3],
      [2, 0, 2],
    ]);
    const none = resolveLinePoints(
      normalizeLineSpec({ kind: "outline", points: [{ guid: "A" }] }),
      { anchors },
    );
    expect(none).toEqual({ points: [], polylines: [], dropped: ["A"] });
  });
});

describe("anchorNeeds", () => {
  it("names the height anchor too, and flags which GUIDs need an outline", () => {
    const specs = [
      normalizeLineSpec({
        space: "ifcPlan",
        height: { guid: "H" },
        points: [
          [0, 0],
          [1, 1],
        ],
      }),
      normalizeLineSpec({ kind: "outline", points: [{ guid: "S" }] }),
      normalizeLineSpec({ points: [{ guid: "S", at: "top" }, { guid: "A" }] }),
    ];
    expect([...anchorGuids(specs)]).toEqual(["H", "S", "A"]);
    expect(anchorNeeds(specs).get("S")).toEqual({ outline: true });
    expect(anchorNeeds(specs).get("A")).toEqual({ outline: false });
    expect(anchorNeeds(specs).get("H")).toEqual({ outline: false });
  });
});

describe("anchorGuids", () => {
  it("collects each GUID once across specs, ignoring coordinates", () => {
    const specs = [
      normalizeLineSpec({ points: [{ guid: "A" }, { guid: "B" }] }),
      normalizeLineSpec({ points: [{ guid: "B", at: "top" }, [0, 0, 0]] }),
    ];
    expect([...anchorGuids(specs)]).toEqual(["A", "B"]);
  });
});
