import { describe, expect, it } from "vitest";
import { expandMembersToParts, geometryGuidsFor } from "../../aggregateParts.js";

// A stair (10) made of two flights (11, 12) and a railing assembly (13) whose
// own geometry is in two bars (14, 15); a column (20) with geometry; a storey
// (30) that decomposes into a space (31) with geometry; a proxy (40) with
// neither geometry nor parts.
const ENTITIES = {
  10: { guid: "stair", parts: [11, 12, 13] },
  11: { guid: "flight-a", geometry: true },
  12: { guid: "flight-b", geometry: true },
  13: { guid: "railing", parts: [14, 15] },
  14: { guid: "bar-1", geometry: true },
  15: { guid: "bar-2", geometry: true },
  20: { guid: "column", geometry: true },
  30: { guid: "storey", parts: [31], spatial: true },
  31: { guid: "space", geometry: true, spatial: true },
  40: { guid: "proxy" },
};
const byGuid = Object.fromEntries(Object.entries(ENTITIES).map(([id, e]) => [e.guid, Number(id)]));
const lookup = {
  hasGeometry: (guid) => Boolean(ENTITIES[byGuid[guid]]?.geometry),
  expressIdOf: (guid) => byGuid[guid],
  isSpatial: (id) => Boolean(ENTITIES[id]?.spatial),
  partsOf: (id) => ENTITIES[id]?.parts ?? [],
  guidOf: (id) => ENTITIES[id]?.guid,
};

describe("geometryGuidsFor", () => {
  it("keeps an element that has geometry", () => {
    expect(geometryGuidsFor("column", lookup)).toEqual(["column"]);
  });
  it("replaces an aggregate by its parts with geometry, at any depth", () => {
    expect(geometryGuidsFor("stair", lookup)).toEqual(["bar-1", "bar-2", "flight-a", "flight-b"]);
  });
  it("never expands a spatial element", () => {
    expect(geometryGuidsFor("storey", lookup)).toEqual([]);
  });
  it("returns nothing for an element with neither geometry nor parts, or an unknown GUID", () => {
    expect(geometryGuidsFor("proxy", lookup)).toEqual([]);
    expect(geometryGuidsFor("nope", lookup)).toEqual([]);
  });
  it("survives a decomposition cycle", () => {
    const cyclic = { ...lookup, partsOf: (id) => (id === 40 ? [40] : lookup.partsOf(id)) };
    expect(geometryGuidsFor("proxy", cyclic)).toEqual([]);
  });
});

describe("expandMembersToParts", () => {
  it("returns the same array when nothing needs expanding", () => {
    const members = [
      { guid: "column", role: "member" },
      { guid: "storey", role: "context" },
    ];
    expect(expandMembersToParts(members, lookup)).toBe(members);
  });
  it("gives each part the aggregate's role and records where it came from", () => {
    const members = [
      { guid: "stair", role: "base", ifcClass: "IfcStair" },
      { guid: "column", role: "context" },
    ];
    expect(expandMembersToParts(members, lookup)).toEqual([
      { guid: "bar-1", role: "base", ifcClass: "IfcStair", partOf: "stair" },
      { guid: "bar-2", role: "base", ifcClass: "IfcStair", partOf: "stair" },
      { guid: "flight-a", role: "base", ifcClass: "IfcStair", partOf: "stair" },
      { guid: "flight-b", role: "base", ifcClass: "IfcStair", partOf: "stair" },
      { guid: "column", role: "context" },
    ]);
  });
});
