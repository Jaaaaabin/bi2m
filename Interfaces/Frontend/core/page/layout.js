// ======== Single viewer fills the screen (page chrome) ========
// Moved out of ThatOpenCompanyLoader.js 2026-09-21 (code motion only). With
// exactly one viewer open there is nothing to tile against, so the 30%-wide
// flex default just wastes the page: the tile takes 95% of the wrapper's
// width and 95% of the screen height left below the wrapper's top edge
// instead (2026-09-20). Written as the same inline width/height the resize
// handle and "Match sizes" write, so everything that already reacts to a
// tile changing size (the canvas aspect observer, panel min-width bumps)
// needs no extra wiring. Three rules keep it from fighting the user:
//   - a tile the user has dragged (`data-user-sized`) is never touched;
//   - only sizes THIS code set (`data-auto-sized`) are cleared again when a
//     second viewer appears, so a dragged size survives the add/remove;
//   - the observer re-applies on wrapper/window/sidebar changes but only
//     writes when the numbers actually differ, so it converges instead of
//     ping-ponging with its own effect on the wrapper's height.

import { viewerData } from "../viewerRegistry.js";

export const SINGLE_VIEWER_FILL = 0.95;

let wrapperNode = null;

export function applySingleViewerLayout() {
  if (!wrapperNode) return;
  if (viewerData.length !== 1) {
    for (const { container } of viewerData) {
      if (container.dataset.autoSized) {
        container.style.width = "";
        container.style.height = "";
        delete container.dataset.autoSized;
      }
    }
    return;
  }
  const container = viewerData[0].container;
  if (container.dataset.userSized) return;

  const wrapperStyle = getComputedStyle(wrapperNode);
  const padX = parseFloat(wrapperStyle.paddingLeft) + parseFloat(wrapperStyle.paddingRight);
  const padY = parseFloat(wrapperStyle.paddingTop) + parseFloat(wrapperStyle.paddingBottom);
  const availableWidth = wrapperNode.clientWidth - padX;
  const availableHeight = window.innerHeight - wrapperNode.getBoundingClientRect().top - padY;
  const width = Math.max(280, Math.floor(availableWidth * SINGLE_VIEWER_FILL));
  const height = Math.max(200, Math.floor(availableHeight * SINGLE_VIEWER_FILL));
  const nextWidth = `${width}px`;
  const nextHeight = `${height}px`;
  if (container.style.width !== nextWidth) container.style.width = nextWidth;
  if (container.style.height !== nextHeight) container.style.height = nextHeight;
  container.dataset.autoSized = "1";
}

// Wrapper size changes cover window resizes AND the sidebar collapsing (the
// grid column animates, so the wrapper's width changes over a few frames).
export function initSingleViewerLayout(wrapper) {
  wrapperNode = wrapper;
  new ResizeObserver(() => applySingleViewerLayout()).observe(wrapper);
  window.addEventListener("resize", applySingleViewerLayout);
}
