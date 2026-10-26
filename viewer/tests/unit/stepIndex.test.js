import { describe, it, expect } from "vitest";
import { StepFileIndex, collectRefs, splitTopLevelArgs } from "../../engine/stepIndex.js";

const STEP = `ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('ViewDefinition [CoordinationView]'),'2;1');
FILE_NAME('t.ifc','2026-01-01T00:00:00',(''),(''),'','','');
FILE_SCHEMA(('IFC4'));
ENDSEC;
DATA;
#1=IFCPROJECT('0YvctVUKr0kugbFTf53O9L',$,'Project',$,$,$,$,(#3),#2);
#2=IFCUNITASSIGNMENT((#4));
#3=IFCGEOMETRICREPRESENTATIONCONTEXT($,'Model',3,1.E-05,#5,$);
#4=IFCSIUNIT(*,.LENGTHUNIT.,$,.METRE.);
#5=IFCAXIS2PLACEMENT3D(#6,$,$);
#6=IFCCARTESIANPOINT((0.,0.,0.));
#7=IFCWALL('2O2Fr$t4X7Zf8NOew3FLOH',$,'Wall A',$,$,#5,$,$,$);
ENDSEC;
END-ISO-10303-21;
`;

describe("StepFileIndex (engine/, byte-level STEP index)", () => {
  const index = StepFileIndex.build(new TextEncoder().encode(STEP));

  it("indexes every top-level instance by express id", () => {
    expect(index.instanceCount).toBe(7);
    expect(index.hasId(7)).toBe(true);
    expect(index.hasId(99)).toBe(false);
  });
  it("resolves types and references", () => {
    expect(index.getType(7)).toBe("IFCWALL");
    expect(index.getType(1)).toBe("IFCPROJECT");
    expect(index.refsOf(7)).toContain(5);
    expect(index.refsOf(5)).toEqual([6]);
  });
  it("slices the exact instance text back out of the bytes", () => {
    expect(index.sliceInstance(6)).toContain("IFCCARTESIANPOINT((0.,0.,0.))");
  });
  it("reads the schema and project id", () => {
    expect(index.schema).toBe("IFC4");
    expect(index.projectId).toBe(1);
  });
});

describe("STEP text helpers", () => {
  it("splitTopLevelArgs respects nested parentheses and strings", () => {
    expect(splitTopLevelArgs("'a,b',(1,(2,3)),$,#4")).toEqual(["'a,b'", "(1,(2,3))", "$", "#4"]);
  });
  it("collectRefs finds every #id", () => {
    expect(collectRefs("(#3,#12),#7")).toEqual([3, 12, 7]);
  });
});
