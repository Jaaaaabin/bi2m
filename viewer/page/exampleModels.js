// ======== Example Models (server-side data/test_*.ifc fixtures) ========
// Moved out of ThatOpenCompanyLoader.js 2026-09-21 (code motion only). Lets
// the viewer load one of THIS SERVER's test fixtures directly - the mirror
// image of the intent panel's Run button (which uploads a browser-local
// file TO the server): here, a file that's already on the server comes back
// INTO the browser. Both exist for the same reason - over an SSH port-
// forward, the browser and this dev server can be different machines, so the
// native file picker only ever sees whatever's local to the browser's own
// device, never this server's data/. Dev-only (see vite.config.js's
// /api/example-models) - a production build has no such endpoint, so the
// button reports that plainly and the empty-tile list simply does not render.

import { dismissOnOutsideInteraction } from "./popover.js";
import { fetchModelFile, formatFileSize, formatProgress } from "./fetchFile.js";

// Moved to ./fetchFile.js 2026-09-24, next to formatProgress, which builds
// on it. Re-exported so existing importers keep working.
export { formatFileSize };

// One request per page for the list (both the sidebar flyout and every empty
// tile show the same six files); a rejected promise is not cached so a later
// click can retry.
let listPromise = null;
export function fetchExampleModels() {
  if (!listPromise) {
    listPromise = fetch("/api/example-models")
      .then(async (res) => {
        if (res.status === 404) return { ok: false, devOnly: true, files: [] };
        return res.json();
      })
      .catch((err) => {
        listPromise = null;
        throw err;
      });
  }
  return listPromise;
}

// Fetches one example model's bytes and wraps them as a real File - the
// loader's intake only ever looks at .name, so it is indistinguishable from
// a picker or drag-and-drop file.
export async function fetchExampleModelFile(fileKey, fileName, onProgress) {
  return fetchModelFile(`/api/example-models?fileKey=${encodeURIComponent(fileKey)}`, fileName, {
    onProgress,
  });
}

function itemMarkup(f, className) {
  return `
    <button type="button" class="${className}" data-file-key="${f.fileKey}" data-file-name="${f.fileName}">
      <span class="example-models-item-name">${f.fileName}</span>
      <span class="example-models-item-size">${formatFileSize(f.sizeBytes)}</span>
    </button>`;
}

// The sidebar's cloud button and its popover. `onFile(file)` receives the
// fetched File; the loader routes it like any other incoming file.
export function initExampleModelsButton({ onFile }) {
  const btn = document.getElementById("example-models-btn");
  const flyout = document.getElementById("example-models-flyout");
  if (!btn || !flyout) return;

  const close = () => {
    flyout.hidden = true;
  };
  // Closes on a pointerdown outside the flyout and its button, and on Escape
  // (2026-09-23, page/popover.js).
  dismissOnOutsideInteraction({ flyout, trigger: btn, close });

  btn.addEventListener("click", async () => {
    if (!flyout.hidden) {
      close();
      return;
    }

    // Positioned via JS (not CSS top/left) against live rects - the flyout
    // lives outside #sidebar-panel specifically so its position:fixed
    // placement can't be clipped by that panel's own overflow-x:hidden (see
    // index.html). Top-aligned with the button, but opening to the right of
    // the whole button ROW (2026-09-23): this button shares its row with the
    // library button, and a flyout hung off the button's own right edge
    // covered the neighbour, so it could not be clicked while this was open.
    const rect = btn.getBoundingClientRect();
    const rowRect = btn.closest(".sidebar-buttons-group")?.getBoundingClientRect() ?? rect;
    flyout.style.top = `${rect.top}px`;
    flyout.style.left = `${rowRect.right + 8}px`;
    flyout.hidden = false;
    flyout.innerHTML = `<div class="example-models-status">Loading…</div>`;

    let payload;
    try {
      payload = await fetchExampleModels();
      if (payload.devOnly) {
        flyout.innerHTML = `<div class="example-models-status">Needs the bi2m server (\`npm run dev\`, \`npm start\` or Docker), not a static host.</div>`;
        return;
      }
    } catch (err) {
      flyout.innerHTML = `<div class="example-models-status">Could not reach the dev server: ${err.message}</div>`;
      return;
    }

    if (!payload.ok || !payload.files?.length) {
      flyout.innerHTML = `<div class="example-models-status">No example models found in data/test_*.ifc.</div>`;
      return;
    }

    flyout.innerHTML = `
      <div class="example-models-hint">Load a model already on the server:</div>
      <div class="example-models-list">${payload.files.map((f) => itemMarkup(f, "example-models-item")).join("")}</div>
    `;

    flyout.querySelectorAll(".example-models-item").forEach((itemBtn) => {
      const nameEl = itemBtn.querySelector(".example-models-item-name");
      const originalName = nameEl.textContent;
      itemBtn.addEventListener("click", async () => {
        const { fileKey, fileName } = itemBtn.dataset;
        itemBtn.disabled = true;
        nameEl.textContent = "Loading…";
        try {
          const file = await fetchExampleModelFile(fileKey, fileName, (received, total) => {
            nameEl.textContent = formatProgress(received, total);
          });
          close();
          await onFile(file);
        } catch (err) {
          console.error("Could not load example model:", err);
          nameEl.textContent = originalName;
          itemBtn.disabled = false;
        }
      });
    });
  });
}

// The empty tile's own list of example models: the
// same files the sidebar's cloud button offers, but right where a first-time
// user is looking, and loading into THIS tile (`loadFile`, a closure over the
// tile supplied by the loader). Renders nothing against a production build
// or when the list is empty, so the placeholder stays exactly as it was.
export async function attachExampleModelsToPlaceholder(placeholder, { loadFile }) {
  let payload;
  try {
    payload = await fetchExampleModels();
  } catch {
    return;
  }
  if (!payload?.ok || !payload.files?.length || !placeholder.isConnected) return;

  const list = document.createElement("div");
  list.className = "viewer-empty-examples";
  // Own class (styled together with .example-models-item in style.css), so a
  // script selecting the sidebar flyout's items never matches these as well.
  list.innerHTML = `
    <div class="viewer-empty-examples-hint">or open an example from the server</div>
    ${payload.files.map((f) => itemMarkup(f, "viewer-empty-example-item")).join("")}
  `;
  placeholder.appendChild(list);

  list.querySelectorAll(".viewer-empty-example-item").forEach((itemBtn) => {
    const nameEl = itemBtn.querySelector(".example-models-item-name");
    const originalName = nameEl.textContent;
    itemBtn.addEventListener("click", async () => {
      const { fileKey, fileName } = itemBtn.dataset;
      list.querySelectorAll("button").forEach((b) => {
        b.disabled = true;
      });
      nameEl.textContent = "Loading…";
      try {
        await loadFile(
          await fetchExampleModelFile(fileKey, fileName, (received, total) => {
            nameEl.textContent = formatProgress(received, total);
          }),
        );
      } catch (err) {
        console.error("Could not load example model:", err);
        nameEl.textContent = originalName;
        list.querySelectorAll("button").forEach((b) => {
          b.disabled = false;
        });
      }
    });
  });
}
