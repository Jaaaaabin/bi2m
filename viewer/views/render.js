// ======== Offscreen render: a view at a fixed image size, without touching the tile ========
// Review pictures need a fixed image size, aspect ratio, pixel ratio and
// theme, so that plans and elevations from different models are comparable
// and a VLM judge sees one consistent format. The tile's canvas is whatever
// size the layout gives it, and resizing it would move the UI under the
// user. This renders the SAME scene with a camera of the requested aspect
// into an offscreen WebGLRenderTarget and reads the pixels back.
//
// Three things make this correct rather than merely plausible:
//
// - CULLING. ThatOpenCompanyLoader.js's frustum culling sets `mesh.visible`
//   from the LIVE camera, and only when that camera moves. An offscreen camera
//   at another pose would inherit the live frustum's decisions and render
//   with pieces missing. Every fragment mesh is forced visible for the pass
//   and restored afterwards; `visible` belongs to the culler alone (Hider
//   works through `mesh.count`), so the restore is exact.
// - COLOUR. three.js applies the output colour-space conversion from the
//   render target's texture colour space when one is bound (and from
//   `renderer.outputColorSpace` only for the canvas). Image targets are
//   created sRGB so a pixel here equals the canvas pixel; an ID pass (phase 4)
//   asks for a linear target and no background.
// - NO preserveDrawingBuffer. The viewer keeps it off; this never reads the
//   canvas, so the flag does not matter here. snapshot.js's render-then-read
//   trick stays for the button; this is for a size the canvas is not.
//
// `readRenderTargetPixels` returns rows bottom-up; `toImageData` flips them.

import * as THREE from "three";

import { findViewerByWorld } from "../viewerRegistry.js";
import { LINES_GROUP_NAME, setFatResolution, syncResolution } from "./lines.js";

/**
 * A copy of the active camera at a different aspect ratio: same pose, same
 * zoom, same near/far. For an orthographic camera the horizontal extent
 * follows the aspect while the vertical one - the half-height the framing
 * math is defined on (views/pose.js) - is kept.
 * @param {THREE.PerspectiveCamera | THREE.OrthographicCamera} camera
 * @param {number} aspect
 */
export function cameraForAspect(camera, aspect) {
  const copy = /** @type {THREE.PerspectiveCamera | THREE.OrthographicCamera} */ (camera.clone());
  copy.position.copy(camera.position);
  copy.quaternion.copy(camera.quaternion);
  if (/** @type {THREE.PerspectiveCamera} */ (copy).isPerspectiveCamera) {
    /** @type {THREE.PerspectiveCamera} */ (copy).aspect = aspect;
  } else {
    const ortho = /** @type {THREE.OrthographicCamera} */ (copy);
    const halfHeight = (ortho.top - ortho.bottom) / 2;
    ortho.left = -halfHeight * aspect;
    ortho.right = halfHeight * aspect;
  }
  copy.updateProjectionMatrix();
  copy.updateMatrixWorld(true);
  return copy;
}

/**
 * Renders the viewer's scene into an offscreen target and reads it back.
 *
 * @param {any} world - the viewer's @thatopen world
 * @param {{
 *   width: number, height: number, pixelRatio?: number,
 *   camera?: THREE.Camera | null,
 *   linear?: boolean,
 *   background?: THREE.Color | null | undefined,
 *   overrideMaterial?: THREE.Material | null,
 *   samples?: number,
 *   forceVisible?: boolean,
 * }} options - `camera` defaults to the active camera re-aspected to width/height;
 *   `linear: true` renders without the sRGB conversion (for an ID pass);
 *   `background: null` renders on transparent black; `overrideMaterial` is
 *   applied to the whole scene for the pass (an ID material); `samples` is
 *   the multisample count - default 4 for an image (the canvas renders with
 *   antialias on, measured 99.8% pixel-equal with 4 against 98.2% without),
 *   forced to 0 for a linear/ID pass, where blended edge colours would be
 *   ids that belong to nobody; `forceVisible: false` leaves `mesh.visible`
 *   alone, for a caller that hid meshes ON PURPOSE (the ID pass's
 *   "members alone" render) and takes the culling flags into its own hands.
 * @returns {{pixels: Uint8Array, width: number, height: number}} RGBA, rows bottom-up (WebGL order)
 */
export function renderOffscreen(world, options) {
  const {
    width,
    height,
    pixelRatio = 1,
    linear = false,
    overrideMaterial = null,
    forceVisible = true,
  } = options;
  const samples = linear ? 0 : (options.samples ?? 4);
  const renderer = world.renderer.three;
  const scene = world.scene.three;
  const w = Math.max(1, Math.round(width * pixelRatio));
  const h = Math.max(1, Math.round(height * pixelRatio));
  const camera = options.camera ?? cameraForAspect(world.camera.three, width / height);

  const target = new THREE.WebGLRenderTarget(w, h, {
    depthBuffer: true,
    stencilBuffer: false,
    samples,
    colorSpace: linear ? THREE.LinearSRGBColorSpace : THREE.SRGBColorSpace,
  });
  // An sRGB texture gets an SRGB8_ALPHA8 internal format (three r160,
  // WebGLTextures.getInternalFormat), so the GPU encodes on write and the
  // bytes read back equal the canvas's for opaque geometry (measured: 99.8%
  // of pixels identical with 4x MSAA, 98.2% without). ONE known difference
  // remains, by construction: the shader writes LINEAR values to a render
  // target and the GPU blends transparent geometry in linear space, while
  // the canvas blends sRGB-encoded values. With a Refer active (the model
  // ghosted to 90%) that is a mean error of 4.5/255 at a whole-building view
  // and 8.6/255 tight on an intent, every pixel within 48 - visually nil,
  // and arguably the more correct blend. Three's own way
  // to make a target behave like the canvas (`isXRRenderTarget`) renders
  // garbage outside WebXR here, so it is not used; the harness pins both
  // numbers instead (scripts/e2e/views.py, phase 2).

  // Force every fragment mesh visible for this pass (see the header).
  const entry = findViewerByWorld(world);
  const forced = [];
  if (forceVisible && entry?.fragments) {
    for (const group of entry.fragments.groups.values()) {
      for (const fragment of group.items) {
        const mesh = fragment.mesh;
        if (mesh && !mesh.visible) {
          forced.push(mesh);
          mesh.visible = true;
        }
      }
    }
  }
  // The refer split's clones live directly in the scene, outside the
  // fragments registry; they are never culled, so nothing to force there.

  // An override pass is an ID or mask pass (views/visibility.js), and the
  // drawn lines (views/lines.js) are annotation, not model: a 3 px line
  // across a member would write "nobody" pixels into its count. Hidden for
  // such a pass and restored below; visibility.js does the same for its
  // number labels itself.
  const linesGroup = overrideMaterial ? scene.getObjectByName(LINES_GROUP_NAME) : null;
  const linesWereVisible = linesGroup ? linesGroup.visible : false;
  if (linesGroup) linesGroup.visible = false;

  const previousBackground = scene.background;
  const previousOverride = scene.overrideMaterial;
  const previousTarget = renderer.getRenderTarget();
  const pixels = new Uint8Array(w * h * 4);
  try {
    if (options.background !== undefined) scene.background = options.background;
    if (overrideMaterial) scene.overrideMaterial = overrideMaterial;
    // Fat lines (views/lines.js) size themselves in pixels through a
    // resolution uniform that normally equals the canvas; for this pass it
    // is the target, and restored below, so a 2 px line is 2 px here too.
    setFatResolution(world, w, h);
    renderer.setRenderTarget(target);
    renderer.render(scene, camera);
    renderer.readRenderTargetPixels(target, 0, 0, w, h, pixels);
  } finally {
    syncResolution(world);
    if (linesGroup) linesGroup.visible = linesWereVisible;
    renderer.setRenderTarget(previousTarget);
    scene.background = previousBackground;
    scene.overrideMaterial = previousOverride;
    for (const mesh of forced) mesh.visible = false;
    target.dispose();
  }
  return { pixels, width: w, height: h };
}

/**
 * Bottom-up RGBA rows (WebGL) to a top-down ImageData.
 * @param {{pixels: Uint8Array, width: number, height: number}} frame
 * @returns {ImageData}
 */
export function toImageData({ pixels, width, height }) {
  const out = new Uint8ClampedArray(width * height * 4);
  const row = width * 4;
  for (let y = 0; y < height; y++) {
    out.set(pixels.subarray((height - 1 - y) * row, (height - y) * row), y * row);
  }
  return new ImageData(out, width, height);
}

/**
 * A PNG data URL of a rendered frame.
 * @param {{pixels: Uint8Array, width: number, height: number}} frame
 * @returns {string}
 */
export function frameToPngDataUrl(frame) {
  const canvas = document.createElement("canvas");
  canvas.width = frame.width;
  canvas.height = frame.height;
  canvas.getContext("2d").putImageData(toImageData(frame), 0, 0);
  return canvas.toDataURL("image/png");
}
