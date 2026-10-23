// views/snapshotMeta.js (2026-10-22): the id encoding of the whole-model ID
// pass and the metadata document written beside a snapshot.
import { describe, it, expect } from "vitest";

import { buildSnapshotMetadata, decodeId, encodeId, ID_NONE, ID_UNCOUNTED, SNAPSHOT_META_SCHEMA, VISIBLE_RULE } from "../../views/snapshotMeta.js";

const bytes = (rgb) => rgb.map((c) => Math.round(c * 255));

describe("encodeId / decodeId", () => {
  it("round-trips ids across the three colour bytes", () => {
    for (const id of [1, 255, 256, 65535, 65536, 1234567, ID_UNCOUNTED - 1]) {
      expect(decodeId(...bytes(encodeId(id)))).toBe(id);
    }
  });
  it("decodes the two sentinels to -1 and refuses them as ids", () => {
    expect(decodeId(0, 0, 0)).toBe(-1);
    expect(decodeId(255, 255, 255)).toBe(-1);
    expect(() => encodeId(ID_NONE)).toThrow(RangeError);
    expect(() => encodeId(ID_UNCOUNTED)).toThrow(RangeError);
    expect(() => encodeId(1.5)).toThrow(RangeError);
  });
});

describe("buildSnapshotMetadata", () => {
  const parts = {
    fileKey: "abc",
    image: { file: "m-view-20261022-120000.png", width: 800, height: 600 },
    pose: { projection: "Perspective", distance: 12.5 },
    selected: ["g2", "g1", "g3", "g1"],
    selectedContext: ["g8", "g1"],
    visible: [{ guid: "g9", px: 40 }, { guid: "g1", px: 12 }, { guid: "g2", px: 3 }],
    ghosted: [{ guid: "g7", px: 100 }],
    minPixels: 1,
    transparency: 90,
    capturedAt: "2026-10-22T12:00:00.000Z",
  };
  it("writes the schema, the rule and the picture join", () => {
    const meta = buildSnapshotMetadata(parts);
    expect(meta.schema).toBe(SNAPSHOT_META_SCHEMA);
    expect(meta.visibleRule).toEqual({ name: VISIBLE_RULE, minPixels: 1, ghost: "material opacity below 1", ghostedRule: "front-most ghost layer", transparency: 90, unresolved: 0 });
    expect(meta.image).toEqual(parts.image);
    expect(meta.model).toEqual({ fileKey: "abc", isStreamed: false });
    expect(meta.pose).toEqual(parts.pose);
    expect(meta.capturedAt).toBe(parts.capturedAt);
  });
  it("sorts and de-duplicates, and derives the selected/visible lists", () => {
    const meta = buildSnapshotMetadata(parts);
    expect(meta.selected).toEqual(["g1", "g2", "g3"]);
    expect(meta.visible.map((v) => v.guid)).toEqual(["g1", "g2", "g9"]);
    expect(meta.selectedVisible).toEqual(["g1", "g2"]);
    expect(meta.selectedHidden).toEqual(["g3"]);
    expect(meta.visibleOnly).toEqual(["g9"]);
    expect(meta.ghosted).toEqual([{ guid: "g7", px: 100 }]);
    expect(meta.selectedContext).toEqual(["g8"]); // a GUID that is also selected is never context
  });
  it("tolerates empty inputs", () => {
    const meta = buildSnapshotMetadata({ fileKey: null, image: parts.image, pose: null, selected: [], visible: [], ghosted: [], minPixels: 4 });
    expect(meta.selectedContext).toEqual([]);
    expect(meta.ghosted).toEqual([]);
    expect(meta.selected).toEqual([]);
    expect(meta.visibleOnly).toEqual([]);
    expect(meta.selectedHidden).toEqual([]);
    expect(typeof meta.capturedAt).toBe("string");
  });
});
