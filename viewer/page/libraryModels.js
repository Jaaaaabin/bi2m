// ======== Model library (the corpus this dev server exposes) ========
// The lightning-bolt button in the sidebar's third row (2026-09-23). A sibling
// of page/exampleModels.js, not an extension of it: the example-models button,
// flyout and route are left exactly as they were. Same idea, other source -
// /api/library-models lists the corpus vis index (content key -> current file
// name, see scripts/build_vis_index.py) and streams one model's bytes by key;
// the bytes become a File and go through the loader's normal intake, so the
// content key, the shard lookup, verdicts and tiles all behave as for any other
// file. Read-only by design: nothing here uploads, tiles or runs recognition.
// Dev-only like the example route (a production build has no such endpoint).
import { fetchModelFile, formatFileSize, formatProgress } from "./fetchFile.js";
import { dismissOnOutsideInteraction } from "./popover.js";

// One request per page for the list; a rejected promise is not cached so a
// later click can retry. The server re-reads the index on every request, so
// a renumbering pass shows up after a reload, not a restart.
let listPromise = null;
export function fetchLibraryModels() {
  if (!listPromise) {
    listPromise = fetch("/api/library-models")
      .then(async (res) => {
        const contentType = res.headers.get("Content-Type") || "";
        if (res.status === 404 && !contentType.includes("json"))
          return { ok: false, devOnly: true, files: [] };
        const payload = await res.json();
        if (res.status === 404) return { ...payload, missing: true, files: [] };
        return payload;
      })
      .catch((err) => {
        listPromise = null;
        throw err;
      });
  }
  return listPromise;
}

// Fetches one library model's bytes and wraps them as a real File. The server
// re-hashes what it serves and names the key in X-Content-Key; a mismatch
// (a stale index after a renumber) is an error here, never a silently wrong
// model under a familiar number.
export async function fetchLibraryModelFile(fileKey, fileName, onProgress) {
  return fetchModelFile(`/api/library-models?fileKey=${encodeURIComponent(fileKey)}`, fileName, {
    onProgress,
    // Checked BEFORE the body is read, so a stale index after a renumber
    // fails immediately instead of after a 20 MB download.
    validate: (res) => {
      const served = res.headers.get("X-Content-Key");
      if (served && served !== fileKey) {
        throw new Error(`Server served ${served}, expected ${fileKey}.`);
      }
    },
    errorMessage: async (res) => {
      try {
        const body = await res.json();
        if (body?.error) return body.error;
      } catch {
        // not JSON - keep the status text
      }
      return `Server responded ${res.status}`;
    },
  });
}

const VERDICT_TEXT = {
  "storey-split": "rooms exist, but on another storey object",
  frame: "door placements far from every room",
};

function badgeMarkup(text, className = "") {
  return `<span class="library-models-badge ${className}">${text}</span>`;
}

function itemMarkup(f) {
  const a = f.annotation;
  const badges = [];
  let title = `content key ${f.fileKey}`;
  if (a?.unit && a.unit !== "m") badges.push(badgeMarkup(a.unit, "is-unit"));
  if (a?.residual) {
    const verdict = a.verdict || "residual";
    badges.push(badgeMarkup(verdict, "is-residual"));
    const reach = a.reach_after
      ? Object.entries(a.reach_after)
          .map(([k, v]) => `${v} door${v === 1 ? "" : "s"} reach ${k}`)
          .join(", ")
      : "";
    title = `${VERDICT_TEXT[verdict] || verdict}${reach ? ` - ${reach}` : ""}${
      a.median_door_to_room_m != null
        ? ` - median door to nearest room ${a.median_door_to_room_m.toFixed(2)} m`
        : ""
    }`;
  }
  return `
    <button type="button" class="library-models-item" data-file-key="${f.fileKey}" data-file-name="${f.fileName}" title="${title}">
      <span class="library-models-item-name">${f.fileName}</span>
      <span class="library-models-item-key">${f.fileKey}</span>
      ${badges.join("")}
      <span class="library-models-item-size">${formatFileSize(f.sizeBytes)}</span>
    </button>`;
}

function clusterMarkup({ id, label, note, groups, open }) {
  const total = groups.reduce((n, g) => n + g.files.length, 0);
  const body = groups
    .map(
      (g) =>
        (g.label
          ? `<div class="library-models-subhead">${g.label} · ${g.files.length}</div>`
          : "") + g.files.map(itemMarkup).join(""),
    )
    .join("");
  return `
    <details class="library-models-cluster" data-cluster="${id}"${open ? " open" : ""}>
      <summary>${label}<span class="library-models-cluster-count" data-total="${total}">${total}</span></summary>
      ${note ? `<div class="library-models-cluster-note">${note}</div>` : ""}
      <div class="library-models-cluster-body">${body}</div>
    </details>`;
}

// Clusters when annotations exist (scripts/library_annotations.py): the models
// whose doors still reach no room after the unit fix, the non-metre models by
// unit, and the metre rest. A model can sit in the first two at once - that is
// the point, they are two different reasons to look. A cluster with nothing in
// it is not rendered, and when only one cluster would remain there is nothing
// to tell apart, so the list is flat - the state since 2026-09-23, when the 148
// non-metre models left the corpus (370 metre models, none residual). In the
// clustered state the residual and non-metre clusters open and Metre, the rest,
// stays folded. Returns the markup and whether it is clustered, so the hint
// can mention the annotation date only when it shows.
function clusteredListMarkup(files, summary) {
  const residual = files.filter((f) => f.annotation?.residual);
  const byVerdict = (v) => residual.filter((f) => (f.annotation.verdict || "unclassified") === v);
  const unitOrder = ["mm", "cm", "dm", "ft", "in"];
  const nonMetre = files.filter((f) => f.annotation?.unit && f.annotation.unit !== "m");
  const units = [...new Set(nonMetre.map((f) => f.annotation.unit))].sort(
    (a, b) => ((unitOrder.indexOf(a) + 99) % 100) - ((unitOrder.indexOf(b) + 99) % 100),
  );
  const metre = files.filter((f) => !f.annotation?.unit || f.annotation.unit === "m");
  const verdicts = summary?.residual_by_verdict || {};
  const clusters = [
    {
      id: "residual",
      label: "Residual after the unit fix",
      note: `Doors still reach no room with placements in metres: ${verdicts["storey-split"] ?? byVerdict("storey-split").length} storey-split (rooms exist, on another storey object), ${verdicts.frame ?? byVerdict("frame").length} frame (placements far from every room). ${summary?.swept ?? "?"} models swept so far.`,
      groups: [
        { label: "storey-split", files: byVerdict("storey-split") },
        { label: "frame", files: byVerdict("frame") },
        { label: "unclassified", files: byVerdict("unclassified") },
      ].filter((g) => g.files.length),
      open: true,
    },
    {
      id: "nonmetre",
      label: "Non-metre units",
      note: "Authored in millimetres, centimetres or feet - the models the placement-reading detectors used to get wrong.",
      groups: units.map((u) => ({
        label: u,
        files: nonMetre.filter((f) => f.annotation.unit === u),
      })),
      open: true,
    },
    {
      id: "metre",
      label: "Metre",
      note: "",
      groups: [{ label: "", files: metre }],
      open: false,
    },
  ].filter((c) => c.groups.some((g) => g.files.length));
  if (clusters.length < 2) return { markup: files.map(itemMarkup).join(""), clustered: false };
  return { markup: clusters.map(clusterMarkup).join(""), clustered: true };
}

// The sidebar's bolt button and its popover. `onFile(file)` receives the
// fetched File; the loader routes it like any other incoming file.
export function initLibraryModelsButton({ onFile }) {
  const btn = document.getElementById("library-models-btn");
  const flyout = document.getElementById("library-models-flyout");
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

    // Positioned via JS against live rects, for the same reasons as the
    // example-models flyout (body-level, never clipped by the sidebar's
    // overflow; opens to the right of the whole button row so it never
    // covers a neighbouring button).
    const rect = btn.getBoundingClientRect();
    const rowRect = btn.closest(".sidebar-buttons-group")?.getBoundingClientRect() ?? rect;
    flyout.style.top = `${rect.top}px`;
    flyout.style.left = `${rowRect.right + 8}px`;
    flyout.hidden = false;
    flyout.innerHTML = `<div class="library-models-status">Loading…</div>`;

    let payload;
    try {
      payload = await fetchLibraryModels();
    } catch (err) {
      flyout.innerHTML = `<div class="library-models-status">Could not reach the dev server: ${err.message}</div>`;
      return;
    }
    if (payload.devOnly) {
      flyout.innerHTML = `<div class="library-models-status">Needs the bi2m server (\`npm run dev\`, \`npm start\` or Docker), not a static host.</div>`;
      return;
    }
    if (payload.missing) {
      flyout.innerHTML = `<div class="library-models-status">${payload.error || "No library index on this server."}</div>`;
      return;
    }
    if (!payload.ok || !payload.files?.length) {
      flyout.innerHTML = `<div class="library-models-status">The library index lists no models.</div>`;
      return;
    }

    const list = payload.summary
      ? clusteredListMarkup(payload.files, payload.summary)
      : { markup: payload.files.map(itemMarkup).join(""), clustered: false };
    flyout.innerHTML = `
      <div class="library-models-hint">${payload.corpus}: ${payload.files.length} models · number = current name, key = identity${
        list.clustered ? ` · annotations ${payload.summary.built_at?.slice(0, 10) ?? "?"}` : ""
      }</div>
      <input type="search" class="library-models-search" placeholder="Filter by number or key" aria-label="Filter library models" />
      <div class="library-models-list">${list.markup}</div>
    `;

    const search = flyout.querySelector(".library-models-search");
    const items = [...flyout.querySelectorAll(".library-models-item")];
    const clusters = [...flyout.querySelectorAll(".library-models-cluster")];
    const defaultOpen = new Map(clusters.map((c) => [c, c.open]));
    search.addEventListener("input", () => {
      const query = search.value.trim().toLowerCase();
      for (const item of items) {
        const { fileName, fileKey } = item.dataset;
        item.hidden =
          Boolean(query) && !(fileName.toLowerCase().includes(query) || fileKey.startsWith(query));
      }
      // While filtering, every cluster with a hit is open and shows "hits / total";
      // clearing the box restores the designed open/closed state and the totals.
      for (const cluster of clusters) {
        const visible = [...cluster.querySelectorAll(".library-models-item")].filter(
          (i) => !i.hidden,
        ).length;
        const count = cluster.querySelector(".library-models-cluster-count");
        cluster.hidden = Boolean(query) && visible === 0;
        cluster.open = query ? visible > 0 : defaultOpen.get(cluster);
        count.textContent = query ? `${visible} / ${count.dataset.total}` : count.dataset.total;
        for (const head of cluster.querySelectorAll(".library-models-subhead")) {
          let node = head.nextElementSibling;
          let any = false;
          while (node && !node.classList.contains("library-models-subhead")) {
            if (!node.hidden) any = true;
            node = node.nextElementSibling;
          }
          head.hidden = Boolean(query) && !any;
        }
      }
    });
    search.focus();

    items.forEach((itemBtn) => {
      const nameEl = itemBtn.querySelector(".library-models-item-name");
      const originalName = nameEl.textContent;
      itemBtn.addEventListener("click", async () => {
        const { fileKey, fileName } = itemBtn.dataset;
        itemBtn.disabled = true;
        nameEl.textContent = "Loading…";
        try {
          // The row the user just clicked is the progress readout - the flyout
          // stays open for the whole transfer, and it is the only thing on
          // screen that can still repaint (the parse that follows blocks the
          // main thread; see page/fetchFile.js).
          const file = await fetchLibraryModelFile(fileKey, fileName, (received, total) => {
            nameEl.textContent = formatProgress(received, total);
          });
          close();
          await onFile(file);
        } catch (err) {
          console.error("Could not load library model:", err);
          nameEl.textContent = originalName;
          itemBtn.disabled = false;
          const status = document.createElement("div");
          status.className = "library-models-status";
          status.textContent = err.message;
          flyout.prepend(status);
        }
      });
    });
  });
}
