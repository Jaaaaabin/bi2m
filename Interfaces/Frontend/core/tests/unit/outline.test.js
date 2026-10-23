import { describe, it, expect } from "vitest";

import { DOWN_NORMAL_Y, FLOOR_BAND_M, floorLoops, simplifyLoop } from "../../views/outline.js";

// Helpers build triangles with a DOWNWARD normal: with y up, the corner order
// below makes (b-a) x (c-a) point to -y (checked by hand: u=(dx,0,0),
// v=(dx,0,dz) gives n_y = -dx*dz).
const down = (a, b, c) => [a, b, c];
/** Two downward triangles covering the rectangle [x0,x1] x [z0,z1] at height y. */
const quad = (x0, z0, x1, z1, y) => [
  down([x0, y, z0], [x1, y, z0], [x1, y, z1]),
  down([x0, y, z0], [x1, y, z1], [x0, y, z1]),
];
const xz = (loop) => loop.map((p) => [p[0], p[2]]);
const sortedXZ = (loop) => xz(loop).sort((a, b) => a[0] - b[0] || a[1] - b[1]);

describe("floorLoops: a rectangle", () => {
  it("is one loop of four corners at the floor height; the diagonal drops out", () => {
    const r = floorLoops(quad(0, 0, 4, 3, -2));
    expect(r.y).toBe(-2);
    expect(r.loops).toHaveLength(1);
    expect(r.loops[0]).toHaveLength(4);
    expect(sortedXZ(r.loops[0])).toEqual([
      [0, 0],
      [0, 3],
      [4, 0],
      [4, 3],
    ]);
    expect(r.loops[0].every((p) => p[1] === -2)).toBe(true);
  });
  it("ignores faces that point up or sideways: a closed box keeps only its bottom", () => {
    const bottom = quad(0, 0, 2, 2, 0);
    const top = quad(0, 0, 2, 2, 3).map(([a, b, c]) => [a, c, b]); // flipped: points up
    const wall = [
      [
        [0, 0, 0],
        [0, 3, 0],
        [0, 3, 2],
      ],
      [
        [0, 0, 0],
        [0, 3, 2],
        [0, 0, 2],
      ],
    ];
    const r = floorLoops([...top, ...wall, ...bottom]);
    expect(r.loops).toHaveLength(1);
    expect(r.loops[0]).toHaveLength(4);
    expect(r.y).toBe(0);
  });
  it("returns null when nothing points down", () => {
    const up = quad(0, 0, 1, 1, 0).map(([a, b, c]) => [a, c, b]);
    expect(floorLoops(up)).toBeNull();
    expect(floorLoops([])).toBeNull();
  });
});

describe("floorLoops: irregular shapes", () => {
  it("keeps a concave L-shape as one six-vertex loop", () => {
    // The L polygon (0,0) (4,0) (4,1) (1,1) (1,4) (0,4), fanned from its first corner:
    // one conforming triangulation, as a mesh of one face is.
    const v = [
      [0, 0, 0],
      [4, 0, 0],
      [4, 0, 1],
      [1, 0, 1],
      [1, 0, 4],
      [0, 0, 4],
    ];
    const tris = [1, 2, 3, 4].map((i) => down(v[0], v[i], v[i + 1]));
    const r = floorLoops(tris);
    expect(r.loops).toHaveLength(1);
    expect(sortedXZ(r.loops[0])).toEqual([
      [0, 0],
      [0, 4],
      [1, 1],
      [1, 4],
      [4, 0],
      [4, 1],
    ]);
  });
  it("gives an outer ring and a hole as two loops, longest first", () => {
    // A 6x6 square with the square [2,4]x[2,4] cut out, as a ring of eight
    // triangles between matching outer and inner corners (conforming).
    const O = [
      [0, 0, 0],
      [6, 0, 0],
      [6, 0, 6],
      [0, 0, 6],
    ];
    const I = [
      [2, 0, 2],
      [4, 0, 2],
      [4, 0, 4],
      [2, 0, 4],
    ];
    const tris = [];
    for (let i = 0; i < 4; i++) {
      const j = (i + 1) % 4;
      tris.push(down(O[i], O[j], I[j]), down(O[i], I[j], I[i]));
    }
    const r = floorLoops(tris);
    expect(r.loops).toHaveLength(2);
    expect(r.loops[0].length).toBeGreaterThanOrEqual(r.loops[1].length);
    expect(sortedXZ(r.loops[0])).toEqual([
      [0, 0],
      [0, 6],
      [6, 0],
      [6, 6],
    ]);
    expect(sortedXZ(r.loops[1])).toEqual([
      [2, 2],
      [2, 4],
      [4, 2],
      [4, 4],
    ]);
  });
  it("a floor made of two solids that only touch gives one loop per solid (no conforming edge to cancel)", () => {
    const tris = [...quad(0, 0, 4, 1, 0), ...quad(0, 1, 1, 4, 0)];
    expect(floorLoops(tris).loops).toHaveLength(2);
  });
  it("takes only the lowest downward faces: a step higher than the band is not the floor", () => {
    const low = quad(0, 0, 2, 2, 0);
    const high = quad(2, 0, 4, 2, FLOOR_BAND_M + 0.5);
    const r = floorLoops([...low, ...high]);
    expect(r.y).toBe(0);
    expect(r.loops).toHaveLength(1);
    expect(sortedXZ(r.loops[0])).toEqual([
      [0, 0],
      [0, 2],
      [2, 0],
      [2, 2],
    ]);
  });
  it("drops T-junction vertices the triangulation left on a straight edge", () => {
    // A 2x2 floor cut into three triangles, one vertex sitting mid-way along the z=0 edge.
    const tris = [
      down([0, 0, 0], [1, 0, 0], [2, 0, 2]),
      down([1, 0, 0], [2, 0, 0], [2, 0, 2]),
      down([0, 0, 0], [2, 0, 2], [0, 0, 2]),
    ];
    const r = floorLoops(tris);
    expect(r.loops).toHaveLength(1);
    expect(sortedXZ(r.loops[0])).toEqual([
      [0, 0],
      [0, 2],
      [2, 0],
      [2, 2],
    ]);
    expect(DOWN_NORMAL_Y).toBeLessThan(0);
  });
});

describe("simplifyLoop", () => {
  it("drops collinear vertices and consecutive duplicates, treating the loop as closed", () => {
    const loop = [
      [0, 0, 0],
      [1, 0, 0],
      [2, 0, 0],
      [2, 0, 0],
      [2, 0, 2],
      [0, 0, 2],
      [0, 0, 1],
    ];
    expect(simplifyLoop(loop)).toEqual([
      [0, 0, 0],
      [2, 0, 0],
      [2, 0, 2],
      [0, 0, 2],
    ]);
  });
  it("never reduces below three vertices", () => {
    expect(
      simplifyLoop([
        [0, 0, 0],
        [1, 0, 0],
        [2, 0, 0],
      ]),
    ).toHaveLength(3);
  });
});
