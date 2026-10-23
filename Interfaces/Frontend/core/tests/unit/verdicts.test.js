import { describe, it, expect, beforeEach } from "vitest";
import { clearVerdict, exportVerdictsPayload, getVerdicts, setVerdict } from "../../verdicts.js";

const intent = {
  id: "k-grid-x1",
  type: "alignment_column_group",
  provenance: { detector: "alignment", rule: "column_axis_alignment" },
  members: [{ guid: "g1", role: "member", ifcClass: "IfcColumn" }],
};

describe("verdicts (localStorage store, VISION §4)", () => {
  beforeEach(() => localStorage.clear());

  it("stores under bi2m:verdicts:<fileKey> keyed by intent id", () => {
    setVerdict("abc", intent, "accepted");
    expect(JSON.parse(localStorage.getItem("bi2m:verdicts:abc"))["k-grid-x1"].verdict).toBe(
      "accepted",
    );
  });
  it("a verdict is self-contained: members, detector, rule, timestamp", () => {
    const v = setVerdict("abc", intent, "rejected");
    expect(v).toMatchObject({
      intentId: "k-grid-x1",
      detector: "alignment",
      rule: "column_axis_alignment",
      verdict: "rejected",
    });
    expect(v.members).toEqual(intent.members);
    expect(Date.parse(v.reviewedAt)).not.toBeNaN();
  });
  it("clearVerdict removes the entry, not the file", () => {
    setVerdict("abc", intent, "accepted");
    setVerdict("abc", { ...intent, id: "other" }, "rejected");
    clearVerdict("abc", "k-grid-x1");
    expect(Object.keys(getVerdicts("abc"))).toEqual(["other"]);
  });
  it("export carries the fileKey and a flat list", () => {
    setVerdict("abc", intent, "accepted");
    expect(exportVerdictsPayload("abc")).toEqual({
      fileKey: "abc",
      verdicts: [expect.objectContaining({ intentId: "k-grid-x1" })],
    });
  });
  it("tolerates corrupt storage", () => {
    localStorage.setItem("bi2m:verdicts:bad", "{not json");
    expect(getVerdicts("bad")).toEqual({});
  });
  // Verdicts recorded before the 2026-09-24 pattern -> intent rename are
  // still under the same store key and the same map key; only the two field
  // names inside the record moved. Read-time normalisation is what keeps an
  // export from carrying two vocabularies at once.
  it("reads a pre-rename record and reports it under the new field names", () => {
    localStorage.setItem(
      "bi2m:verdicts:old",
      JSON.stringify({
        "k-grid-x1": {
          patternId: "k-grid-x1",
          patternType: "alignment_column_group",
          detector: "alignment",
          verdict: "accepted",
          members: [],
        },
      }),
    );
    expect(getVerdicts("old")["k-grid-x1"]).toMatchObject({
      intentId: "k-grid-x1",
      intentType: "alignment_column_group",
      detector: "alignment",
      verdict: "accepted",
    });
    expect(getVerdicts("old")["k-grid-x1"].patternId).toBeUndefined();
    expect(exportVerdictsPayload("old").verdicts).toEqual([
      expect.objectContaining({ intentId: "k-grid-x1" }),
    ]);
  });
});
