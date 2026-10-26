// ======== Numbered labels in the scene ========
// VLM judges count badly (door/window counts 40-55 %); a number drawn on
// each member turns counting into reading. The labels are
// THREE sprites IN the scene - not DOM markers - so they are in every
// picture the scene produces: the live canvas, captureWorldPng, and the
// offscreen render (views/render.js). `sizeAttenuation: false` keeps them
// one screen size at any distance; depth test off puts them over geometry.

import * as THREE from "three";

const GROUP_NAME = "bi2m-view-labels";
const LABEL_PX = 64; // texture size; the sprite is scaled in screen units below
const SPRITE_SCREEN_FRACTION = 0.045; // of the viewport's height

function numberTexture(text, { fill = "#ffffff", background = "#1f2937" } = {}) {
  const canvas = document.createElement("canvas");
  canvas.width = LABEL_PX;
  canvas.height = LABEL_PX;
  const g = canvas.getContext("2d");
  g.fillStyle = background;
  g.beginPath();
  g.arc(LABEL_PX / 2, LABEL_PX / 2, LABEL_PX / 2 - 2, 0, Math.PI * 2);
  g.fill();
  g.fillStyle = fill;
  g.font = `bold ${text.length > 2 ? 26 : 34}px system-ui, sans-serif`;
  g.textAlign = "center";
  g.textBaseline = "middle";
  g.fillText(text, LABEL_PX / 2, LABEL_PX / 2 + 2);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

/** Removes any labels this module added to the scene. */
export function clearNumberLabels(world) {
  const scene = world.scene.three;
  const existing = scene.getObjectByName(GROUP_NAME);
  if (!existing) return 0;
  let n = 0;
  existing.traverse((o) => {
    if (o.isSprite) {
      o.material.map?.dispose();
      o.material.dispose();
      n++;
    }
  });
  scene.remove(existing);
  return n;
}

/**
 * Puts a numbered sprite at each point, 1-based, in the given order.
 * @param {any} world
 * @param {Array<{position: THREE.Vector3 | number[], label?: string}>} items
 * @param {{background?: string, fill?: string}} [style]
 * @returns {number} how many labels were added
 */
export function addNumberLabels(world, items, style = {}) {
  clearNumberLabels(world);
  const group = new THREE.Group();
  group.name = GROUP_NAME;
  const aspect = world.camera.three.aspect || 1;
  items.forEach((item, i) => {
    const material = new THREE.SpriteMaterial({
      map: numberTexture(item.label ?? String(i + 1), style),
      sizeAttenuation: false,
      depthTest: false,
      depthWrite: false,
      transparent: true,
    });
    const sprite = new THREE.Sprite(material);
    const p = Array.isArray(item.position) ? new THREE.Vector3().fromArray(item.position) : item.position;
    sprite.position.copy(p);
    // Screen-space scale: with sizeAttenuation off, scale is in NDC-ish units
    // where 2 spans the viewport; keep the sprite square on screen.
    sprite.scale.set((SPRITE_SCREEN_FRACTION * 2) / aspect, SPRITE_SCREEN_FRACTION * 2, 1);
    sprite.renderOrder = 10000;
    group.add(sprite);
  });
  world.scene.three.add(group);
  return items.length;
}
