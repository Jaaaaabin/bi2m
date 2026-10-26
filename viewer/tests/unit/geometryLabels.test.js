import { describe, expect, it } from "vitest";
import {
  buildGeometryLabels,
  friendlyTypeLabel,
  refsIn,
  splitArgs,
} from "../../inspector/geometryLabels.js";

const encode = (text) => new TextEncoder().encode(text);

// A wall with a Body and an Axis representation, a door whose Body is a mapped
// (instanced) B-rep, a slab with only a non-Body representation, a string
// argument holding ";" and an escaped quote, and a header entity that must
// never be read as data.
const IFC = `ISO-10303-21;
HEADER;
FILE_NAME('x;y.ifc','2026-10-26',(''),(''),'','','');
FILE_SCHEMA(('IFC4'));
ENDSEC;
DATA;
#1=IFCWALL('wall',$,'Wall; with ''quotes''',$,$,#2,#10,$,$);
#10=IFCPRODUCTDEFINITIONSHAPE($,$,(#11,#12));
#11=IFCSHAPEREPRESENTATION(#99,'Axis','Curve2D',(#20));
#12=IFCSHAPEREPRESENTATION(#99,'Body','SweptSolid',(#21));
#20=IFCPOLYLINE((#30,#31));
#21=IFCEXTRUDEDAREASOLID(#40,#41,#42,3.);
#50=IFCPRODUCTDEFINITIONSHAPE($,$,(#51));
#51=IFCSHAPEREPRESENTATION(#99,'Body','MappedRepresentation',(#52));
#52=IFCMAPPEDITEM(#53,#54);
#53=IFCREPRESENTATIONMAP(#55,#56);
#56=IFCSHAPEREPRESENTATION(#99,'Body','Brep',(#57,#58));
#57=IFCFACETEDBREP(#60);
#58=IFCFACETEDBREP(#61);
#70=IFCPRODUCTDEFINITIONSHAPE($,$,(#71));
#71=IFCSHAPEREPRESENTATION(#99,'FootPrint','Curve2D',(#72));
/* a comment */ #72=IFCINDEXEDPOLYCURVE(#73,$,.F.);
#80=IFCPRODUCTDEFINITIONSHAPE($,$,());
ENDSEC;
END-ISO-10303-21;
`;

describe("buildGeometryLabels", () => {
  const labels = buildGeometryLabels(encode(IFC));

  it("prefers the Body representation", () => {
    expect(labels.get(10)).toEqual({
      identifier: "Body",
      type: "SweptSolid",
      itemClasses: ["IFCEXTRUDEDAREASOLID"],
    });
  });
  it("follows a mapped item to the shape it instances", () => {
    expect(labels.get(50)).toEqual({
      identifier: "Body",
      type: "MappedRepresentation",
      itemClasses: ["IFCFACETEDBREP+IFCFACETEDBREP"],
    });
  });
  it("falls back to the first representation when there is no Body", () => {
    expect(labels.get(70)).toEqual({
      identifier: "FootPrint",
      type: "Curve2D",
      itemClasses: ["IFCINDEXEDPOLYCURVE"],
    });
  });
  it("has no label for a shape without representations, or for non-shapes", () => {
    expect(labels.has(80)).toBe(false);
    expect(labels.has(1)).toBe(false);
    expect(labels.size).toBe(3);
  });
});

describe("argument helpers", () => {
  it("splits top-level arguments, keeping strings and lists whole", () => {
    expect(splitArgs("'a,b',(#1,#2),$,'it''s');")).toEqual(["'a,b'", "(#1,#2)", "$", "'it''s'"]);
  });
  it("finds references in order", () => {
    expect(refsIn("(#3,#12)")).toEqual([3, 12]);
    expect(refsIn("$")).toEqual([]);
  });
  it("names representation types for people", () => {
    expect(friendlyTypeLabel("SweptSolid")).toBe("Swept Solid");
    expect(friendlyTypeLabel("Curve2D")).toBe("Curve2D");
    expect(friendlyTypeLabel(undefined)).toBeUndefined();
  });
});
