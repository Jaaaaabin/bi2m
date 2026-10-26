// ======== Popover dismissal (page chrome) ========
// Shared by the sidebar's two popovers - the cloud button's example list
// (page/exampleModels.js) and the bolt button's library (page/libraryModels.js).
// A popover opened from a button closes when the pointer goes down anywhere
// outside it and its own button, and on Escape. Registered once per popover at
// init, in the capture phase, so a canvas or control that swallows the event
// further down cannot keep the popover open. The button is excluded on
// purpose: its own click keeps toggling, and a pointerdown that closed the
// popover would otherwise be followed by a click that reopens it. Opening one
// popover therefore closes the other - its button is "outside" the first.
export function dismissOnOutsideInteraction({ flyout, trigger, close }) {
  document.addEventListener(
    "pointerdown",
    (event) => {
      if (flyout.hidden) return;
      const { target } = event;
      if (flyout.contains(target) || trigger.contains(target)) return;
      close();
    },
    { capture: true },
  );
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !flyout.hidden) close();
  });
}
