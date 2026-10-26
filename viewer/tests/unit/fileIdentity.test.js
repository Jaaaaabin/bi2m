import { describe, it, expect } from "vitest";
import { createHash } from "node:crypto";
import { computeContentKey, legacyNameKey, readIfcLineage } from "../../fileIdentity.js";

const enc = new TextEncoder();

describe("content-addressed file identity", () => {
  it("computeContentKey = first 16 hex chars of SHA-256 over the bytes (matches src/file_identity.py and vite.config.js)", async () => {
    const bytes = enc.encode(
      "ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;\n",
    );
    const expected = createHash("sha256").update(bytes).digest("hex").slice(0, 16);
    expect(await computeContentKey(bytes.buffer)).toBe(expected);
  });
  it("the same bytes under two names give one key", async () => {
    const a = enc.encode("same bytes").buffer;
    expect(await computeContentKey(a)).toBe(
      await computeContentKey(enc.encode("same bytes").buffer),
    );
  });
  it("legacyNameKey strips the extension only", () => {
    expect(legacyNameKey("test_1.ifc")).toBe("test_1");
    expect(legacyNameKey("1_00000001_AR.IFC")).toBe("1_00000001_AR");
    expect(legacyNameKey(".ifc")).toBe(".ifc");
    expect(legacyNameKey("")).toBe("model");
  });
  it("readIfcLineage tolerates a file with no readable header", () => {
    const lineage = readIfcLineage(enc.encode("not an ifc file at all"), "x.ifc");
    expect(lineage).toMatchObject({ fileName: "x.ifc" });
  });
});
