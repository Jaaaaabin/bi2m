// ======== IFC file intake: upload button + drag-and-drop (page chrome) ========
// Moved out of ThatOpenCompanyLoader.js 2026-09-21 (code motion only). Both
// entry points hand a FileList to the loader's own routing (`onFiles`), which
// sends each .ifc to an empty viewer or opens a new one.

export function initIntake({ wrapper, onFiles }) {
  // Opens file picker for uploading multiple IFC files and assigns each one
  // to a separate viewer.
  document.getElementById("bulk-upload-btn").addEventListener("click", () => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".ifc";
    input.multiple = true;
    input.addEventListener("change", (event) => onFiles(event.target.files));
    input.click();
  });

  // Drop .ifc files anywhere on the viewer area as an alternative to the
  // upload button.
  for (const evt of ["dragenter", "dragover"]) {
    wrapper.addEventListener(evt, (e) => {
      e.preventDefault();
      wrapper.classList.add("drag-active");
    });
  }
  for (const evt of ["dragleave", "drop"]) {
    wrapper.addEventListener(evt, (e) => {
      e.preventDefault();
      wrapper.classList.remove("drag-active");
    });
  }
  wrapper.addEventListener("drop", (e) => {
    if (e.dataTransfer?.files?.length) onFiles(e.dataTransfer.files);
  });
}
