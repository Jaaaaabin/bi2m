// ======== Intent Panel: Compute Section ========
// The panel's top "Compute" flyout - a category checklist and one button,
// "Compute": it uploads the bytes currently open in this browser to the dev
// server, then spawns scripts/recognize_intents.py server-side. The copyable
// command box and its "Copy" button (the manual fallback for a production or
// preview build, where that middleware does not exist) were removed on
// 2026-10-09 at the owner's request; a preview build has no Compute path from
// the panel.
//
// Identity fix (docs/architecture.md "One key for everything"). This
// used to upload under a fresh "<fileKey>-<Date.now()>" id and then
// REBUILD the whole panel under that new id, which had two consequences that
// were only visible after a reload: the computed intents were stored under a
// key the next session never looked up (so the panel showed the stale
// pre-Run results forever), and every verdict recorded afterwards went to
// localStorage under that same throwaway key and was likewise unreachable. It
// also compounded - the new id became the next Run's input, producing real
// keys four timestamps deep.
//
// With content-addressed identity there is nothing to re-key: the server
// stores the bytes under the same content key this browser already computed,
// recognition writes its shard under that key, and the panel refreshes in
// place under the key it already had. Uploading the same file twice is now a
// no-op on the server rather than a new 20MB copy.

import { getIntentCategories, refreshIntentsForModel } from "../intentData.js";

const FALLBACK_CATEGORIES = [
  { id: "alignment", label: "Alignment" },
  { id: "connection", label: "Connection" },
];

export function createComputeSection({ fileKey, file, intents, onRecomputed }) {
  const wrap = document.createElement("div");
  wrap.className = "intent-compute-section";

  const toggleBtn = document.createElement("button");
  toggleBtn.type = "button";
  toggleBtn.className = "bulk-toggle-btn intent-compute-toggle-btn";
  toggleBtn.textContent = "Compute";
  wrap.appendChild(toggleBtn);

  const flyout = document.createElement("div");
  flyout.className = "intent-compute-flyout";
  flyout.hidden = true;
  wrap.appendChild(flyout);

  function renderFlyout() {
    // Prefer the fetched manifest; if this model has real intents but the
    // manifest is missing, fall back to whatever categories already show up
    // in its own data (still real, just not future categories with 0 intents
    // yet); only the static list above is a last resort, for a totally fresh
    // checkout before recognize_intents.py has ever run.
    const manifest = getIntentCategories();
    // A tombstone (a registry entry retired into another category, `retired`
    // set) keeps its manifest position for the colours but is nothing to run.
    const categories = manifest.length
      ? manifest.filter((c) => !c.retired)
      : [...new Set((intents ?? []).map((p) => p.provenance?.detector))]
          .filter(Boolean)
          .map((id) => ({ id, label: id }));
    const options = categories.length ? categories : FALLBACK_CATEGORIES;

    flyout.innerHTML = `
      <div class="intent-compute-hint">Categories to compute for this file:</div>
      <div class="intent-compute-categories">
        ${options
          .map(
            (c) => `
          <label class="intent-compute-category">
            <input type="checkbox" value="${c.id}" checked /> ${c.label}
          </label>
        `,
          )
          .join("")}
      </div>
      <div class="intent-compute-actions">
        <button type="button" class="bulk-toggle-btn intent-compute-run-btn">Compute</button>
      </div>
      <div class="intent-compute-status" hidden></div>
      <div class="intent-compute-stream" hidden>
        <span class="intent-compute-stream-text"></span>
        <button type="button" class="bulk-toggle-btn intent-compute-prepare-btn" hidden>Prepare</button>
      </div>
    `;

    const checkboxes = () => Array.from(flyout.querySelectorAll('input[type="checkbox"]'));
    const runBtn = flyout.querySelector(".intent-compute-run-btn");
    const statusEl = flyout.querySelector(".intent-compute-status");

    const setStatus = (kind, text) => {
      statusEl.hidden = false;
      statusEl.textContent = text;
      statusEl.className = `intent-compute-status intent-compute-status-${kind}`;
    };

    // Compute needs at least one category.
    const updateCommand = () => {
      runBtn.disabled = !checkboxes().some((cb) => cb.checked);
    };

    checkboxes().forEach((cb) => cb.addEventListener("change", updateCommand));

    runBtn.addEventListener("click", async () => {
      const selected = checkboxes()
        .filter((cb) => cb.checked)
        .map((cb) => cb.value);
      if (!selected.length) return;

      const originalRunLabel = runBtn.textContent;
      runBtn.disabled = true;
      runBtn.classList.add("is-running");
      runBtn.textContent = "Running…";
      runBtn.setAttribute("aria-busy", "true");

      try {
        // Upload the bytes currently open in THIS browser - recognize_intents.py
        // runs server-side and can only see its own filesystem, which, over an
        // SSH-forwarded dev server, is a different machine than whatever the
        // browser's file picker showed. Re-read straight off the original File
        // object (not the ArrayBuffer used earlier for the STEP index - that
        // one gets transferred/detached into a Worker and can't be read
        // twice). The server keys the folder by content, so re-running against
        // an unchanged file writes nothing and returns `deduplicated: true`.
        setStatus("running", "Uploading file to server…");
        const fileBytes = await file.arrayBuffer();
        const uploadRes = await fetch(`/api/upload-ifc?fileKey=${encodeURIComponent(fileKey)}`, {
          method: "POST",
          headers: { "Content-Type": "application/octet-stream" },
          body: fileBytes,
        });

        if (uploadRes.status === 404) {
          setStatus(
            "error",
            "Upload endpoint unavailable - Compute needs the bi2m server (`npm run dev`, `npm start` or Docker), not a static host; recompute with the CLI (README).",
          );
          return;
        }

        const uploadResult = await uploadRes.json();
        if (!uploadResult.ok) {
          setStatus(
            "error",
            `Could not upload file to server: ${uploadResult.error || "unknown error"}`,
          );
          return;
        }

        // The server independently hashes what it received. A mismatch means
        // the bytes that arrived are not the bytes this browser hashed, which
        // would silently write results for the wrong model - refuse rather
        // than proceed.
        if (uploadResult.fileKey && uploadResult.fileKey !== fileKey) {
          setStatus(
            "error",
            `Upload integrity check failed: server stored ${uploadResult.fileKey}, expected ${fileKey}.`,
          );
          return;
        }

        setStatus(
          "running",
          uploadResult.deduplicated ? "Already on server - running…" : "Running…",
        );
        const res = await fetch("/api/recognize-intents", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ fileKey, categories: selected }),
        });

        if (res.status === 404) {
          setStatus(
            "error",
            "Run endpoint unavailable - Compute needs the bi2m server (`npm run dev`, `npm start` or Docker), not a static host; recompute with the CLI (README).",
          );
          return;
        }

        const result = await res.json();
        if (result.ok) {
          setStatus("success", "Done - intents updated.");
          // Re-fetch just THIS model's shard (not, as before, the entire
          // corpus) and rebuild the panel under the SAME key it already had.
          const refreshed = await refreshIntentsForModel(fileKey);
          onRecomputed(refreshed);
          return; // panel was just torn down and rebuilt - this instance is gone
        }

        setStatus(
          "error",
          `Failed (exit ${result.code ?? "?"}): ${(result.stderr || result.error || "unknown error").trim().slice(-500)}`,
        );
      } catch (err) {
        setStatus("error", `Request failed: ${err.message}`);
      } finally {
        runBtn.disabled = false;
        runBtn.classList.remove("is-running");
        runBtn.textContent = originalRunLabel;
        runBtn.removeAttribute("aria-busy");
      }
    });

    updateCommand();

    // ---- Streaming status. The server tiles an upload only when asked
    // (this line's button) or, with BI2M_AUTO_TILE=1, for a large model
    // (server/api.mjs); this line says whether THIS model already streams on
    // its next open, and offers to upload + tile it if not. A 404 (a static
    // host, no server) hides the line. ----
    const streamEl = flyout.querySelector(".intent-compute-stream");
    const streamText = flyout.querySelector(".intent-compute-stream-text");
    const prepareBtn = flyout.querySelector(".intent-compute-prepare-btn");
    let pollTimer = null;

    const describe = (status) =>
      ({
        ready: "Streaming: ready - the next open of this model streams its tiles.",
        building: "Streaming: building tiles on the server…",
        failed: "Streaming: tiling failed on the server (see its console).",
        none: "Streaming: not prepared - this model re-parses on every open.",
      })[status] ?? `Streaming: ${status}`;

    const refreshStreamStatus = async () => {
      clearTimeout(pollTimer);
      if (flyout.hidden) return;
      let status;
      try {
        const res = await fetch(`/api/tile-status?fileKey=${encodeURIComponent(fileKey)}`);
        if (res.status === 404) return; // production build - no dev server
        status = (await res.json()).status;
      } catch {
        return;
      }
      streamEl.hidden = false;
      streamText.textContent = describe(status);
      prepareBtn.hidden = status !== "none" && status !== "failed";
      if (status === "building") pollTimer = setTimeout(refreshStreamStatus, 2500);
    };

    prepareBtn.addEventListener("click", async () => {
      prepareBtn.disabled = true;
      streamText.textContent = "Streaming: uploading file to server…";
      try {
        const fileBytes = await file.arrayBuffer();
        const res = await fetch(`/api/upload-ifc?fileKey=${encodeURIComponent(fileKey)}&tile=1`, {
          method: "POST",
          headers: { "Content-Type": "application/octet-stream" },
          body: fileBytes,
        });
        const result = await res.json();
        if (!result.ok) throw new Error(result.error || `server responded ${res.status}`);
      } catch (err) {
        streamText.textContent = `Streaming: could not upload (${err.message}).`;
      } finally {
        prepareBtn.disabled = false;
      }
      refreshStreamStatus();
    });

    refreshStreamStatus();
  }

  toggleBtn.addEventListener("click", () => {
    flyout.hidden = !flyout.hidden;
    if (!flyout.hidden) renderFlyout();
  });

  return wrap;
}
