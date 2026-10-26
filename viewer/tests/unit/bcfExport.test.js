// The pure half of views/bcfExport.js (2026-10-21): the BCF 3.0 camera
// element and its placement in the library's VisualizationInfo. The live
// camera read (readBcfCamera) and the whole export run in
// scripts/e2e/views.py against the real viewer, with the xsd.
import { describe, it, expect, vi } from "vitest";

vi.mock("@thatopen/components", () => ({}));
vi.mock("../../highlighting.js", () => ({ resolveGuidIndex: async () => new Map() }));

const { bcfCameraXml, fixComponentTags, replaceCameraBlock } = await import("../../views/bcfExport.js");

const tags = (xml) => [...xml.matchAll(/<([A-Za-z]+)[\s>]/g)].map((m) => m[1]);

const camera = { position: [1, 2, 3], direction: [0, 1, 0], up: [0, 0, 1], aspectRatio: 1.5 };

describe("bcfCameraXml", () => {
  it("writes a perspective camera in the 3.0 sequence, AspectRatio last", () => {
    const xml = bcfCameraXml({ ...camera, fov: 38 });
    expect(tags(xml)).toEqual([
      "PerspectiveCamera", "CameraViewPoint", "X", "Y", "Z", "CameraDirection", "X", "Y", "Z",
      "CameraUpVector", "X", "Y", "Z", "FieldOfView", "AspectRatio",
    ]);
    expect(xml).toContain("<FieldOfView>38</FieldOfView>");
  });
  it("writes an orthogonal camera with the scale where the perspective one has its FOV", () => {
    const xml = bcfCameraXml({ ...camera, viewToWorldScale: 12.5 });
    expect(tags(xml).slice(-2)).toEqual(["ViewToWorldScale", "AspectRatio"]);
    expect(xml.startsWith("<OrthogonalCamera>")).toBe(true);
    expect(xml).toContain("<ViewToWorldScale>12.5</ViewToWorldScale>");
    expect(xml).not.toContain("FieldOfView");
  });
});

describe("fixComponentTags", () => {
  it("moves the library's AuthoringToolId attribute into the schema's child element", () => {
    const xml = `<Selection><Component IfcGuid="2UoYwZCKj77ACNiiPcyLM7" AuthoringToolId="2563608" />
<Component IfcGuid="0nfJAfls9FHwWUEPKYw3Bm" /></Selection>`;
    expect(fixComponentTags(xml)).toBe(`<Selection><Component IfcGuid="2UoYwZCKj77ACNiiPcyLM7"><AuthoringToolId>2563608</AuthoringToolId></Component>
<Component IfcGuid="0nfJAfls9FHwWUEPKYw3Bm" /></Selection>`);
  });
  it("is applied by replaceCameraBlock", () => {
    const out = replaceCameraBlock(`<VisualizationInfo Guid="g"><Components><Selection><Component IfcGuid="a" AuthoringToolId="1" /></Selection></Components></VisualizationInfo>`, "<PerspectiveCamera></PerspectiveCamera>");
    expect(out).toContain("<AuthoringToolId>1</AuthoringToolId>");
    expect(out).not.toContain('AuthoringToolId="');
  });
});

describe("replaceCameraBlock", () => {
  const ours = bcfCameraXml({ ...camera, fov: 38 });
  it("drops the library's camera and puts ours right after the components", () => {
    const xml = `<?xml version="1.0"?>
    <VisualizationInfo Guid="g">
      <Components>
        <Visibility DefaultVisibility="true"></Visibility>
      </Components>
      <PerspectiveCamera>
        <CameraViewPoint><X>9</X><Y>9</Y><Z>9</Z></CameraViewPoint>
        <AspectRatio>2</AspectRatio>
        <FieldOfView>60</FieldOfView>
      </PerspectiveCamera>
    </VisualizationInfo>`;
    const out = replaceCameraBlock(xml, ours);
    expect(out.match(/<PerspectiveCamera>/g).length).toBe(1);
    expect(out).not.toContain("<X>9</X>");
    expect(out.indexOf("</Components>")).toBeLessThan(out.indexOf("<PerspectiveCamera>"));
    expect(out.indexOf("</PerspectiveCamera>")).toBeLessThan(out.indexOf("</VisualizationInfo>"));
  });
  it("inserts a camera where the library wrote none (the orthographic case)", () => {
    const xml = `<VisualizationInfo Guid="g">
      <Components></Components>
    </VisualizationInfo>`;
    const out = replaceCameraBlock(xml, bcfCameraXml({ ...camera, viewToWorldScale: 3 }));
    expect(tags(out).slice(0, 3)).toEqual(["VisualizationInfo", "Components", "OrthogonalCamera"]);
  });
  it("copes with no components at all", () => {
    const out = replaceCameraBlock(`<VisualizationInfo Guid="g"></VisualizationInfo>`, ours);
    expect(tags(out).slice(0, 2)).toEqual(["VisualizationInfo", "PerspectiveCamera"]);
  });
});
