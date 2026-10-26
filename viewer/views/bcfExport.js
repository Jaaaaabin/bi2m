// ======== BCF export of a view ========
// A view record doubles as a BCF viewpoint, since BCF already stores pose,
// field of view or orthographic scale, visibility and colouring (clipping
// planes are in the schema but NOT written by this export, see below).
// `OBC.Viewpoints` (installed, unused until 2026-10-01) does the
// serialisation of the components, so this module is the ONE place the
// library is called for it - the ThatOpen v3 migration is planned per module.
//
// The viewpoint is the EXPORT of a record, not its store: BCF has no frame,
// no in-frame azimuth, no fill target and no log, which is why the record
// exists in the first place. The camera serialised is the LIVE one, so a
// caller replays the record first (applyView.js, replayViewRecord) when the
// camera has moved since.
//
// THE CAMERA BLOCK IS WRITTEN HERE, NOT BY THE LIBRARY (2026-10-21).
// Read in components 2.4.3's installed dist:
//  - Viewpoint.updateCamera stores the orthographic scale under
//    `viewToWorldScale` while serialize() tests `"viewToWorld" in camera`
//    (index.mjs 26161 / 26291): the key never matches, so an orthographic
//    view was exported with NO camera element at all - not a wrong scale, as
//    previously assumed.
//  - The scale it meant to write was `top - bottom`, ignoring `zoom`, where
//    BCF 3.0's visinfo.xsd defines ViewToWorldScale as the "view's visible
//    vertical size in meters": `(top - bottom) / zoom`.
//  - The up vector was `direction` rotated 90° about X (26270), which is only
//    the camera's up when it looks along three's -Z. Side 45 exported an up
//    vector that was not even perpendicular to the direction.
//  - <AspectRatio> was written BEFORE <FieldOfView>, which fails the 3.0
//    schema (sequence: ViewPoint, Direction, UpVector, scale or FOV,
//    AspectRatio), and was written at all under the manager's default
//    version 2.1, which has no AspectRatio element.
// So the export now sets the manager to BCF 3 for the call, lets the library
// serialise the components, and replaces whatever camera block it produced
// with one built from the live camera's own matrix: position through the
// inverse base coordination matrix (the library's own rule, which
// scripts/e2e/views.py checks against the detectors' plan coordinates),
// direction and up from the camera's world matrix, IFC's Z-up axes
// (x, -z, y), scale divided by zoom, AspectRatio last.
//
// Not written, deliberately (review, 2026-10-21): the library's
// serialize() has no <ClippingPlanes> output, so a cut view loses its cut in
// BCF. A follow-up item for the owner, not part of this fix.

import * as OBC from "@thatopen/components";
import * as THREE from "three";

import { resolveGuidIndex } from "../highlighting.js";

/**
 * The live camera in BCF terms, in the IFC file's own frame (scene
 * coordinates un-shifted by the loader's coordination, IFC Z-up axes):
 * {position, direction, up: [X, Y, Z], aspectRatio, fov?: deg (perspective),
 * viewToWorldScale?: m (orthographic)}.
 */
export function readBcfCamera(components, world) {
  const camera = world.camera;
  const three = camera.three;
  three.updateMatrixWorld(true);
  const fragments = components.get(OBC.FragmentsManager);
  // scene -> IFC frame, the inverse of what coordinate:true applied on load
  // (the same matrix OBC.Viewpoint.updateCamera uses).
  const toIfc = fragments.baseCoordinationMatrix.clone().invert();
  const toIfcRotation = new THREE.Matrix4().extractRotation(toIfc);
  const position = camera.controls.getPosition(new THREE.Vector3()).applyMatrix4(toIfc);
  const direction = new THREE.Vector3().setFromMatrixColumn(three.matrixWorld, 2).negate().applyMatrix4(toIfcRotation).normalize();
  const up = new THREE.Vector3().setFromMatrixColumn(three.matrixWorld, 1).applyMatrix4(toIfcRotation).normalize();
  const { width, height } = world.renderer.getSize();
  const aspectRatio = width > 0 && height > 0 ? width / height : 1;
  const zUp = (v) => [v.x, -v.z, v.y];
  const out = { position: zUp(position), direction: zUp(direction), up: zUp(up), aspectRatio };
  if (camera.projection.current === "Orthographic") {
    const ortho = camera.threeOrtho;
    out.viewToWorldScale = (ortho.top - ortho.bottom) / (ortho.zoom || 1);
  } else {
    out.fov = camera.threePersp.fov;
  }
  return out;
}

const point = (tag, [x, y, z]) => `<${tag}>
        <X>${x}</X>
        <Y>${y}</Y>
        <Z>${z}</Z>
      </${tag}>`;

/** One BCF 3.0 camera element from readBcfCamera's shape, elements in the schema's order. */
export function bcfCameraXml(camera) {
  const ortho = Number.isFinite(camera.viewToWorldScale);
  const tag = ortho ? "OrthogonalCamera" : "PerspectiveCamera";
  const scale = ortho
    ? `<ViewToWorldScale>${camera.viewToWorldScale}</ViewToWorldScale>`
    : `<FieldOfView>${camera.fov}</FieldOfView>`;
  return `<${tag}>
      ${point("CameraViewPoint", camera.position)}
      ${point("CameraDirection", camera.direction)}
      ${point("CameraUpVector", camera.up)}
      ${scale}
      <AspectRatio>${camera.aspectRatio}</AspectRatio>
    </${tag}>`;
}

const CAMERA_BLOCK = /\s*<(OrthogonalCamera|PerspectiveCamera)>[\s\S]*?<\/\1>/g;
// `includeSelectionTag` makes the library write the element's Tag as an
// AuthoringToolId ATTRIBUTE; in BCF 3.0 (and 2.1) AuthoringToolId is a child
// ELEMENT of Component, with IfcGuid the only attribute (visinfo.xsd, type
// Component). xmllint rejected every export with a selection.
const COMPONENT_TAG = /<Component IfcGuid="([^"]*)" AuthoringToolId="([^"]*)" \/>/g;

/** The library's `<Component IfcGuid AuthoringToolId/>` as the schema's element form. */
export function fixComponentTags(xml) {
  return xml.replace(COMPONENT_TAG, '<Component IfcGuid="$1"><AuthoringToolId>$2</AuthoringToolId></Component>');
}

/**
 * `xml` with any camera element the library wrote removed and `cameraXml`
 * put where BCF 3.0 wants it: after <Components>, before anything else.
 */
export function replaceCameraBlock(xml, cameraXml) {
  const stripped = fixComponentTags(xml).replace(CAMERA_BLOCK, "");
  const anchor = stripped.indexOf("</Components>");
  if (anchor === -1) {
    // No components (nothing selected and the library wrote none): the camera
    // is then the first child of VisualizationInfo.
    const open = stripped.indexOf(">", stripped.indexOf("<VisualizationInfo")) + 1;
    return `${stripped.slice(0, open)}\n      ${cameraXml}${stripped.slice(open)}`;
  }
  const cut = anchor + "</Components>".length;
  return `${stripped.slice(0, cut)}\n      ${cameraXml}${stripped.slice(cut)}`;
}

/**
 * The current camera as a BCF 3.0 'VisualizationInfo' XML document, with the
 * given elements as the viewpoint's selection.
 *
 * @param {any} components - the viewer's OBC.Components
 * @param {any} world
 * @param {{title?: string, model?: any, guids?: string[]}} [options]
 * @returns {Promise<string>} XML text (a `.bcfv` file's content)
 */
export async function currentViewToBcfXml(components, world, { title = "view", model = null, guids = [] } = {}) {
  const viewpoints = components.get(OBC.Viewpoints);
  // Library quirk (components 2.4.3, Viewpoint.createComponentTags): with
  // BCFTopics' default `includeSelectionTag: false` the tag builder ignores
  // which list it was asked for and emits the SELECTION for both the
  // <Selection> and the <Exceptions> blocks - every selected member came out
  // hidden as well (measured: 4 exceptions for 4 members). With the flag on,
  // each block is built from its own list, and components gain the element's
  // Tag as AuthoringToolId. Set for this export only, restored after - and
  // so is the BCF version: the manager defaults to 2.1, whose camera has no
  // AspectRatio and whose FieldOfView must lie in 45-60° (this viewer's lens
  // is 38°); the export is BCF 3.0.
  const topics = components.get(OBC.BCFTopics);
  const previousIncludeTag = topics.config.includeSelectionTag;
  const previousVersion = topics.config.version;
  topics.config.includeSelectionTag = true;
  topics.config.version = "3";
  // Passing `data` keeps the viewpoint out of the manager's list; the camera
  // is still captured (setCamera defaults to true).
  const viewpoint = viewpoints.create(world, { title });
  try {
    // The viewpoint snapshots the scene's visibility, and a Refer HIDES the
    // referred items' origin instances (their opaque clones carry them,
    // highlighting.js). Exported as-is, the members would be the viewpoint's
    // "exceptions" - hidden in any BCF reader. The app's visibility model is
    // not BCF-expressible, so the export says: everything visible, these
    // selected (measured: 4 exceptions for 4 members before this).
    viewpoint.exceptionComponents.clear();
    viewpoint.defaultVisibility = true;
    if (model && guids.length) {
      const guidToLocation = await resolveGuidIndex(model);
      const expressIDs = guids.map((g) => guidToLocation.get(g)?.expressID).filter((id) => id !== undefined);
      if (expressIDs.length) viewpoint.addComponentsFromMap(model.getFragmentMap(expressIDs));
    }
    const xml = await viewpoint.serialize();
    return replaceCameraBlock(xml, bcfCameraXml(readBcfCamera(components, world)));
  } finally {
    viewpoints.list.delete(viewpoint.guid);
    topics.config.includeSelectionTag = previousIncludeTag;
    topics.config.version = previousVersion;
  }
}
