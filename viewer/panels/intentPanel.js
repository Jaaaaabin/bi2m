// ======== Per-Viewer Intent Validation Panel ========
// Lists recognized intent groups for this viewer's loaded model so a human
// can review each one (Refer to see it in 3D, then Accept/Reject/Reset).
// Extracted from ThatOpenCompanyLoader.js.
//
// 2026-09-21: the review workflow grew a verdict
// ledger in every header, keyboard review, a filter strip, denser rows and a
// one-shot pulse when a Refer's camera transition lands. The AUTOMATION
// CONTRACT is unchanged on purpose: every class name, data
// attribute (`data-intent-id`, `data-refer-status`, `aria-busy`) and event
// (`intent-refer-complete`) the existing harnesses and the batch
// driver read is still produced by the same elements. Keyboard shortcuts call
// the very same handlers the buttons call, so a script and a reviewer produce
// identical state.

import * as OBC from "@thatopen/components";

import { getIntentCategories, getShardMeta, loadIntentsForModel } from "../intentData.js";
import { computeBuildingBoundingBox, computeGuidsBoundingBox } from "../cameraViews.js";
import {
  INTENT_COLOR_SLOTS,
  clearIntentHighlights,
  clearReferForViewer,
  visualizeIntentGroups,
  withGeometryMembers,
} from "../highlighting.js";
import { enqueueViewerWork, findViewerByWorld, setCameraScope } from "../viewerRegistry.js";
import { getModelContext } from "../viewerModel.js";
import { applyView } from "../views/applyView.js";
import { clearVerdict, exportVerdictsPayload, getVerdicts, setVerdict } from "../verdicts.js";
import { createComputeSection } from "./computeSection.js";
import { toggleShortcutsPanel } from "./shortcutsPanel.js";

const DOMAIN_LABELS = {
  structural: "Structural",
  spatial: "Spatial",
  daylight: "Daylight",
  circulation: "Circulation",
};
const DOMAIN_ORDER = ["structural", "spatial", "daylight", "circulation"];
// Since 2026-10-08 the top-level sections are the spatial LEVEL a category's
// claim reaches (registry.py `level`: room, storey, building, small to
// large; docs/detectors.md "How categories are organised"). The domain tables above
// stay as the fallback for a manifest written before `level` existed; the
// "domain" names below (variables, CSS classes) now mean "top-level section".
// A manifest entry may carry `section` (the Neufert Topic categories,
// 2026-10-18): it is grouped under that section, after the levels, instead
// of under its level.
const LEVEL_LABELS = { room: "Room", storey: "Storey", building: "Building", neufert: "Neufert" };
const LEVEL_ORDER = ["room", "storey", "building", "neufert"];

const domainLabel = (domain) =>
  LEVEL_LABELS[domain] ??
  DOMAIN_LABELS[domain] ??
  (domain ? domain[0].toUpperCase() + domain.slice(1) : "Other");

// Keys the review shortcuts must ignore - typing in the filter or the GUID
// textarea must never accept an intent.
const isTypingTarget = (el) =>
  el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement || el?.isContentEditable;

const escapeHtml = (s) =>
  String(s ?? "").replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
  );

// Tooltip for the "↔ N" chip: which other-detector intents share this one's
// elements (src/recognition/corroboration.py; docs/architecture.md "Recognition"). Referenced by id,
// shown by the current display index and label.
function describeCorroboration(intent, allIntents, categoryMeta) {
  const byId = new Map(allIntents.map((p) => [p.id, p]));
  const lines = intent.corroborates.map((c) => {
    const other = byId.get(c.id);
    const category = categoryMeta[c.detector]?.label ?? c.detector;
    const handle = other?.index ? `${other.index} · ` : "";
    return `${handle}${category}${other ? `: ${other.label}` : ""} (${c.sharedGuids} shared element${c.sharedGuids === 1 ? "" : "s"})`;
  });
  return `Also found independently by:\n${lines.join("\n")}`;
}

// ---- Verdict ledger ----
// One thin bar per header: accepted = solid fill, rejected = dashed,
// pending = the empty track. State is carried by fill and texture in the
// header's own colour, never by a second hue - same rule the strikethrough on
// rejected rows already follows, so a colour-blind reviewer reads it the same.
function countVerdicts(intentIds, verdictOf) {
  let accepted = 0;
  let rejected = 0;
  for (const id of intentIds) {
    const v = verdictOf(id);
    if (v === "accepted") accepted++;
    else if (v === "rejected") rejected++;
  }
  return {
    accepted,
    rejected,
    pending: intentIds.length - accepted - rejected,
    total: intentIds.length,
  };
}

function ledgerMarkup() {
  return `
    <span class="intent-ledger" role="img">
      <span class="intent-ledger-seg intent-ledger-accepted"></span>
      <span class="intent-ledger-seg intent-ledger-rejected"></span>
    </span>`;
}

function paintLedger(headerEl, counts) {
  const ledger = headerEl.querySelector(".intent-ledger");
  if (!ledger) return;
  const pct = (n) => (counts.total ? (n / counts.total) * 100 : 0);
  ledger.querySelector(".intent-ledger-accepted").style.width = `${pct(counts.accepted)}%`;
  ledger.querySelector(".intent-ledger-rejected").style.width = `${pct(counts.rejected)}%`;
  ledger.setAttribute(
    "aria-label",
    `${counts.accepted} accepted, ${counts.rejected} rejected, ${counts.pending} pending of ${counts.total}`,
  );
  ledger.title = `${counts.accepted} accepted · ${counts.rejected} rejected · ${counts.pending} pending`;
  headerEl.classList.toggle("is-complete", counts.total > 0 && counts.pending === 0);
}

export function createIntentPanel({
  components,
  model,
  world,
  intentPanel,
  fileKey,
  fileName,
  file,
  intents,
}) {
  intentPanel.innerHTML = "";

  const inner = document.createElement("div");
  inner.className = "viewer-intent-panel-inner";
  intentPanel.appendChild(inner);

  // Panel order (user request 2026-09-21): the working controls first -
  // filter + chips, Show all / Clear selection, progress - then the
  // categories, and the identity/tooling block (heading, Compute, Export
  // Verdicts) as a footer at the very bottom, where it no longer costs three
  // rows before the first intent.
  const heading = document.createElement("h2");
  heading.className = "viewer-filter-heading";
  heading.textContent = "Intent Information Recognition";
  const footer = document.createElement("div");
  footer.className = "intent-panel-footer";
  footer.appendChild(heading);

  // A recompute rebuilds this whole panel - the same teardown/rebuild it
  // already does on every model load, so there's no separate incremental-
  // update path to maintain. Crucially it rebuilds under the SAME fileKey:
  // the key is the file's content, which a recompute cannot change.
  const rebuild = (nextIntents) =>
    createIntentPanel({
      components,
      model,
      world,
      intentPanel,
      fileKey,
      fileName,
      file,
      intents: nextIntents,
    });

  footer.appendChild(
    createComputeSection({ fileKey, fileName, file, intents, onRecomputed: rebuild }),
  );

  // Review progress for the whole model. Also announced as one bubbling
  // event (`intent-review-progress`) so a script or a future consumer can
  // read it without walking the DOM; the panel itself never reaches outside
  // its own viewer. (A page-level status strip consumed this 2026-09-21 and
  // was removed the same day at the user's request - redundant next to the
  // panel's own line.)
  const progress = document.createElement("div");
  progress.className = "intent-progress";
  progress.innerHTML = `<span class="intent-progress-text"></span>${ledgerMarkup()}`;

  const emitProgress = (counts) => {
    progress.querySelector(".intent-progress-text").textContent = counts.total
      ? `${counts.accepted + counts.rejected} of ${counts.total} reviewed`
      : "No recognized intents";
    paintLedger(progress, counts);
    intentPanel.dispatchEvent(
      new CustomEvent("intent-review-progress", {
        bubbles: true,
        detail: { fileKey, fileName, ...counts },
      }),
    );
  };

  // Pre-flight (src/recognition/preflight.py): categories that cannot apply
  // to THIS model, and why - a statement about the model, not a zero count.
  // Async, so it never delays the rows; the line simply appears when known.
  // Folded to one line by default (user request 2026-09-21): on a model where
  // many categories cannot apply (test_7: 12) the full list was the tallest
  // block above the first category. A native <details> gives the click-to-
  // expand for free; the summary carries the count.
  const preflightEl = document.createElement("details");
  preflightEl.className = "intent-preflight";
  preflightEl.hidden = true;
  getShardMeta(fileKey).then(({ preflight }) => {
    if (!preflight?.inapplicable?.length) return;
    const byWhy = new Map();
    for (const entry of preflight.inapplicable) {
      const why = entry.missing
        .map((sig) =>
          sig.startsWith("prop:") ? `no ${sig.slice(5)} values` : `no ${sig.replace(/\|/g, " / ")}`,
        )
        .join(", ");
      if (!byWhy.has(why)) byWhy.set(why, []);
      byWhy.get(why).push(entry.label);
    }
    const n = preflight.inapplicable.length;
    preflightEl.innerHTML = `
      <summary class="intent-preflight-summary">${n} ${n === 1 ? "category" : "categories"} not applicable to this model</summary>
      <div class="intent-preflight-body">${[...byWhy]
        .map(
          ([why, labels]) =>
            `<div><span class="intent-preflight-why">${escapeHtml(why)}:</span> ${escapeHtml(labels.join(", "))}</div>`,
        )
        .join("")}</div>`;
    preflightEl.hidden = false;
  });

  // Unlikely (src/recognition/preflight.py soft signals, 2026-10-08): the
  // category applies, but a soft input is missing - "no door or wall tagged
  // IsExternal" - so it probably produces nothing here. Same fold and shape
  // as the block above; a shard written before the field existed has no
  // `unlikely` and the line stays hidden.
  const unlikelyEl = document.createElement("details");
  unlikelyEl.className = "intent-preflight intent-preflight-unlikely";
  unlikelyEl.hidden = true;
  getShardMeta(fileKey).then(({ preflight }) => {
    if (!preflight?.unlikely?.length) return;
    const byWhy = new Map();
    for (const entry of preflight.unlikely) {
      const why = (entry.why ?? []).join(", ");
      if (!byWhy.has(why)) byWhy.set(why, []);
      byWhy.get(why).push(entry.label);
    }
    const n = preflight.unlikely.length;
    unlikelyEl.innerHTML = `
      <summary class="intent-preflight-summary">${n} ${n === 1 ? "category" : "categories"} unlikely to produce output here</summary>
      <div class="intent-preflight-body">${[...byWhy]
        .map(
          ([why, labels]) =>
            `<div><span class="intent-preflight-why">${escapeHtml(why)}:</span> ${escapeHtml(labels.join(", "))}</div>`,
        )
        .join("")}</div>`;
    unlikelyEl.hidden = false;
  });

  if (!intents.length) {
    inner.appendChild(progress);
    inner.appendChild(preflightEl);
    inner.appendChild(unlikelyEl);
    emitProgress({ accepted: 0, rejected: 0, pending: 0, total: 0 });
    const empty = document.createElement("div");
    empty.className = "intent-empty";
    empty.textContent = "No recognized intents for this file.";
    inner.appendChild(empty);
    // A shard request that FAILED (anything but 200 or 404) is not "no
    // intents" (2026-10-01): say so, with the reason and a Retry that
    // re-fetches under the same key and rebuilds, instead of the line a
    // model with no results gets. getShardMeta() already carries the error.
    getShardMeta(fileKey).then(({ error }) => {
      if (!error) return;
      empty.className = "intent-empty intent-load-error";
      empty.setAttribute("role", "alert");
      // The progress line above is driven by counts alone, so it would still
      // read "No recognized intents"; make it agree with the error below.
      progress.querySelector(".intent-progress-text").textContent = "Intents not loaded";
      empty.textContent = `Could not load recognized intents: ${error}.`;
      const retry = document.createElement("button");
      retry.type = "button";
      retry.className = "bulk-toggle-btn intent-retry-btn";
      retry.textContent = "Retry";
      retry.addEventListener("click", async () => {
        retry.disabled = true;
        rebuild(await loadIntentsForModel(fileKey, { refresh: true }));
      });
      empty.appendChild(retry);
    });
    inner.appendChild(footer);
    return;
  }

  const bulkRow = document.createElement("div");
  bulkRow.className = "section-bulk-toggle";
  bulkRow.innerHTML = `
    <button type="button" class="bulk-toggle-btn intent-show-all-btn">Show all</button>
    <button type="button" class="bulk-toggle-btn intent-clear-btn">Clear selection</button>
  `;

  // ---- Filter strip: one text field (label, index, evidence) and four chips.
  // Filtering only sets `hidden` on rows; the DOM stays complete, so a batch
  // driver that walks every `.intent-row` still sees them all. ----
  const filterStrip = document.createElement("div");
  filterStrip.className = "intent-filter-strip";
  filterStrip.innerHTML = `
    <input type="search" class="intent-filter-input" placeholder="Filter intents  ( / )" aria-label="Filter intents by label, index or evidence" autocomplete="off" spellcheck="false" />
    <div class="intent-filter-chips" role="group" aria-label="Show only">
      <button type="button" class="intent-chip" data-chip="pending" aria-pressed="false">Pending</button>
      <button type="button" class="intent-chip" data-chip="accepted" aria-pressed="false">Accepted</button>
      <button type="button" class="intent-chip" data-chip="rejected" aria-pressed="false">Rejected</button>
      <button type="button" class="intent-chip" data-chip="draft" aria-pressed="false">Draft only</button>
    </div>
  `;
  inner.appendChild(filterStrip);
  inner.appendChild(bulkRow);
  inner.appendChild(progress);
  inner.appendChild(preflightEl);
  inner.appendChild(unlikelyEl);

  // The keyboard cheat sheet is a floating panel over the viewport
  // (panels/shortcutsPanel.js), opened from the corner button next to this
  // panel's toggle or with `?` here.
  const viewerContainer = intentPanel.closest(".viewer-container");
  const toggleShortcuts = () => {
    if (viewerContainer) toggleShortcutsPanel(viewerContainer);
  };

  // ---- Group by category (manifest order first, then any category not in
  // the manifest but present in this file's own data) - "to be expanded":
  // a newly-registered Python category needs no frontend change to appear
  // here, it just needs intents whose provenance.detector matches its id. ----
  const intentCategoriesList = getIntentCategories();
  const categoryMeta = Object.fromEntries(intentCategoriesList.map((c) => [c.id, c]));
  const knownOrder = intentCategoriesList.map((c) => c.id);
  const grouped = new Map();
  for (const intent of intents) {
    const categoryId = intent.provenance?.detector ?? "uncategorized";
    if (!grouped.has(categoryId)) grouped.set(categoryId, []);
    grouped.get(categoryId).push(intent);
  }
  const orderedCategoryIds = [
    ...knownOrder.filter((id) => grouped.has(id)),
    ...[...grouped.keys()].filter((id) => !knownOrder.includes(id)),
  ];

  // ---- Group categories into top-level sections (registry.py's level/domain/
  // maturity taxonomy). A category missing from the manifest (stale cache, or
  // the "uncategorized" fallback above) falls into "other" rather than being
  // dropped. ----
  const domainGroups = new Map();
  for (const categoryId of orderedCategoryIds) {
    const domain =
      categoryMeta[categoryId]?.section ?? categoryMeta[categoryId]?.level ?? categoryMeta[categoryId]?.domain ?? "other";
    if (!domainGroups.has(domain)) domainGroups.set(domain, []);
    domainGroups.get(domain).push(categoryId);
  }
  const sectionRank = (d) =>
    LEVEL_ORDER.includes(d)
      ? LEVEL_ORDER.indexOf(d)
      : LEVEL_ORDER.length + (DOMAIN_ORDER.includes(d) ? DOMAIN_ORDER.indexOf(d) : DOMAIN_ORDER.length);
  const orderedDomains = [...domainGroups.keys()].sort((a, b) => sectionRank(a) - sectionRank(b));

  // In-memory mirror of this file's verdicts. localStorage stays the store;
  // this only saves re-parsing it on every ledger repaint.
  // Every write below goes through setVerdict/clearVerdict first.
  const verdictState = new Map(
    Object.entries(getVerdicts(fileKey)).map(([id, v]) => [id, v.verdict]),
  );
  const verdictOf = (id) => verdictState.get(id) ?? "pending";

  // The building box a scoped fit measures its context against. Same
  // classifier singleton the loader and the camera panel use (one per this
  // viewer's own OBC.Components), resolved here rather than threaded through
  // createIntentPanel's signature.
  //
  // Measured fresh on each Refer and then SNAPSHOTTED into the scope, rather
  // than memoized for the panel's lifetime. A cache would be wrong for
  // streamed models: their fragments arrive in batches long after this panel
  // is built (Step 6.9 in loadMultiIFCIntoViewer), so the first measurement
  // only covers what had streamed in by then, and caching it would freeze a
  // partial building box for the rest of the session. Re-measuring per Refer
  // is cheap enough (a click, not a drag) and keeps the camera panel's
  // Context slider - which CANNOT afford a re-measure per drag tick - reading
  // one consistent snapshot out of the scope instead of recomputing its own.
  const classifier = components.get(OBC.Classifier);

  // Tracks whichever row's Refer button is currently "on" (color-filled) -
  // shared across every row/category, not per-row, because referring is a
  // single global 3D-view state (referByGuids hides everything except one
  // intent's members at a time): only one row can honestly be "the referred
  // one" at once, so activating a new row's Refer must switch this off on
  // whichever row held it before, and any action that changes what's visible
  // for a reason other than "refer to this one intent" (Show all, Clear
  // Selection, or this row's own Reset) must clear it too.
  let activeReferBtn = null;
  // The active Refer as the loader's streamed-batch watch needs it (null on
  // a parsed model, or when nothing is referred). Set at CLICK time, before
  // the paint below is even queued, so a batch landing meanwhile re-applies
  // the new Refer, not the old one.
  const setStreamedRefer = (value) => {
    const entry = findViewerByWorld(world);
    if (entry) entry.streamedRefer = value;
  };
  // Every paint or clear of a Refer runs through the viewer's work queue
  // (viewerRegistry.js, enqueueViewerWork), in click order, after whatever
  // the loader's streamed-batch re-apply is doing.
  const queued = (task) => {
    const entry = findViewerByWorld(world);
    return entry ? enqueueViewerWork(entry, task) : task();
  };

  // Per-category and per-domain bookkeeping for the ledgers and the filter.
  const categoryEntries = []; // {id, section, header, countEl, intentIds, rows, isDraft, domainEntry}
  const domainEntries = []; // {section, header, intentIds}
  const allRows = []; // {row, intent, categoryEntry, evidenceEl, haystack}

  const repaintLedgers = () => {
    for (const c of categoryEntries) paintLedger(c.header, countVerdicts(c.intentIds, verdictOf));
    for (const d of domainEntries) paintLedger(d.header, countVerdicts(d.intentIds, verdictOf));
    emitProgress(
      countVerdicts(
        intents.map((p) => p.id),
        verdictOf,
      ),
    );
  };

  for (const domain of orderedDomains) {
    const domainCategoryIds = domainGroups.get(domain);
    const domainIntentCount = domainCategoryIds.reduce(
      (sum, id) => sum + grouped.get(id).length,
      0,
    );

    const domainSection = document.createElement("details");
    domainSection.className = "intent-domain-section";
    domainSection.open = true;

    const domainSummary = document.createElement("summary");
    domainSummary.className = "intent-domain-header";
    domainSummary.innerHTML = `
      <span class="intent-domain-label">${domainLabel(domain)}</span>
      <span class="intent-domain-count">${domainIntentCount}</span>
      ${ledgerMarkup()}
    `;
    domainSection.appendChild(domainSummary);

    const domainBody = document.createElement("div");
    domainBody.className = "intent-domain-body";
    domainSection.appendChild(domainBody);
    inner.appendChild(domainSection);

    const domainEntry = {
      section: domainSection,
      header: domainSummary,
      intentIds: domainCategoryIds.flatMap((id) => grouped.get(id).map((p) => p.id)),
    };
    domainEntries.push(domainEntry);

    for (const categoryId of domainCategoryIds) {
      // Most-elements-first within each category, so the biggest/most
      // substantial recognized intent sits at the top of its section.
      const categoryIntents = [...grouped.get(categoryId)].sort(
        (a, b) => (b.members?.length ?? 0) - (a.members?.length ?? 0),
      );
      const categoryInfo = categoryMeta[categoryId];
      const categoryLabel = categoryInfo?.label ?? categoryId;
      const isDraft = categoryInfo?.maturity === "draft";
      // colorIndex is shared by every intent in this category (see
      // assignCategoryColorIndexes) - any member's value works as the
      // section's own color. Must use the same INTENT_COLOR_SLOTS modulus
      // getIntentColorPalette()/visualizeIntentGroups do - this used a
      // hardcoded "% 8" until a 9th category (circulation_horizontal) exposed
      // the mismatch: colorIndex 8 % 8 wrapped to slot 1 (maroon) here while
      // Refer's own %-palette.length correctly resolved slot 9 (teal), so the
      // panel's swatch dot and the actual 3D highlight color silently
      // disagreed for that one category.
      const colorVar = `var(--intent-color-${(categoryIntents[0].colorIndex % INTENT_COLOR_SLOTS) + 1})`;

      const section = document.createElement("details");
      section.className = "intent-category-section";
      section.open = false;
      section.dataset.categoryId = categoryId;

      const summary = document.createElement("summary");
      summary.className = "intent-category-header";
      // The ledger sits on the header itself (the whole header is the
      // sticky element), coloured through the same --icon-color the rows use.
      summary.style.setProperty("--icon-color", colorVar);
      summary.innerHTML = `
        <span class="intent-category-icon"></span>
        <span class="intent-category-label">${escapeHtml(categoryLabel)}</span>
        ${isDraft ? '<span class="intent-category-draft-badge" title="Heuristic - needs more human validation before being trusted like this panel’s other categories">Draft</span>' : ""}
        <span class="intent-category-count">${categoryIntents.length}</span>
        ${ledgerMarkup()}
      `;
      section.appendChild(summary);

      const body = document.createElement("div");
      body.className = "intent-category-body";
      section.appendChild(body);
      domainBody.appendChild(section);

      // Folding a long section from its stuck header collapses hundreds of
      // pixels above the current scroll position, which would otherwise drop
      // the viewport onto whatever unrelated rows happen to follow. Bring the
      // header the user just clicked back into view instead.
      section.addEventListener("toggle", () => {
        if (!section.open) summary.scrollIntoView({ block: "nearest" });
      });

      const categoryEntry = {
        id: categoryId,
        section,
        header: summary,
        countEl: summary.querySelector(".intent-category-count"),
        intentIds: categoryIntents.map((p) => p.id),
        rows: [],
        isDraft,
        domainEntry,
      };
      categoryEntries.push(categoryEntry);

      for (const intent of categoryIntents) {
        const row = document.createElement("div");
        row.className = "intent-row";
        row.dataset.intentId = intent.id;
        // Roving focus: rows are reachable by the keyboard shortcuts and by
        // click, not by Tab (that would put 250 stops before the buttons).
        row.tabIndex = -1;

        const initialVerdict = verdictOf(intent.id);
        row.dataset.verdict = initialVerdict;
        if (initialVerdict === "rejected") row.classList.add("verdict-rejected");
        // Set once on the row (not the icon span) so it inherits down to both
        // the status icon AND the row-actions buttons below - one color-fill
        // source for everything in this row, matching the category's color.
        row.style.setProperty("--icon-color", colorVar);

        const evidenceText = intent.evidence?.summary ?? "";
        row.innerHTML = `
          <div class="intent-row-header">
            <span class="intent-status-icon ${initialVerdict === "accepted" ? "status-accepted" : ""}"
                  title="Category: ${escapeHtml(categoryLabel)} · Verdict: ${initialVerdict}"></span>
            <span class="intent-index" title="Display handle - re-numbered when this category's set changes; the durable key is the intent id">${escapeHtml(intent.index ?? "")}</span>
            <span class="intent-label" title="${escapeHtml(intent.label)}">${escapeHtml(intent.label)}</span>
            ${intent.corroborates?.length ? `<span class="intent-corroborates" title="${escapeHtml(describeCorroboration(intent, intents, categoryMeta))}">↔ ${intent.corroborates.length}</span>` : ""}
          </div>
          <div class="intent-evidence" title="Click to expand">${escapeHtml(evidenceText)}</div>
          <div class="intent-row-actions">
            <button type="button" class="bulk-toggle-btn intent-refer-btn">Refer</button>
            <button type="button" class="bulk-toggle-btn intent-accept-btn${initialVerdict === "accepted" ? " is-active" : ""}">Accept</button>
            <button type="button" class="bulk-toggle-btn intent-reject-btn${initialVerdict === "rejected" ? " is-active" : ""}">Reject</button>
            <button type="button" class="bulk-toggle-btn intent-reset-btn">Reset</button>
          </div>
        `;
        body.appendChild(row);

        const iconEl = row.querySelector(".intent-status-icon");
        const evidenceEl = row.querySelector(".intent-evidence");
        const referBtn = row.querySelector(".intent-refer-btn");
        const acceptBtn = row.querySelector(".intent-accept-btn");
        const rejectBtn = row.querySelector(".intent-reject-btn");
        const resetBtn = row.querySelector(".intent-reset-btn");

        // Evidence is clamped to two lines (CSS); the full text is one click
        // (or `e`) away. Only rows whose text actually overflows get the
        // affordance, decided after layout (see markOverflowingEvidence).
        evidenceEl.addEventListener("click", () => row.classList.toggle("is-expanded"));

        // Clicking anywhere on the row makes it the keyboard's current row,
        // so mouse and keyboard review can be mixed freely.
        row.addEventListener("mousedown", (event) => {
          if (event.target.closest("button")) return;
          setActiveRow(row, { focus: true, scroll: false });
        });

        referBtn.addEventListener("click", async () => {
          activeReferBtn?.classList.remove("is-active");
          referBtn.classList.add("is-active");
          activeReferBtn = referBtn;
          setActiveRow(row, { focus: false, scroll: false });
          // Observable completion, for the batch snapshot pipeline -
          // this used to be fire-and-forget, which only "happened" to be safe
          // under Playwright because its own click-actionability overhead
          // outlasted the highlight work, not a guaranteed contract.
          // `referStatus`/`aria-busy` are pollable (waitForSelector); the
          // event is for a script already holding a listener rather than
          // polling.
          row.dataset.referStatus = "pending";
          referBtn.setAttribute("aria-busy", "true");

          // Zoom to this intent while leaving the rest of the building
          // exactly as visualizeIntentGroups leaves it - ghosted at 90%, not
          // hidden. The box is measured BEFORE
          // referring:
          // referByGuids splits these very items out of their origin
          // fragments, and BoundingBoxer measures through those origins.
          // Through the members' parts where a member has no geometry of its
          // own (a stair is drawn by its flights; highlighting.js).
          const [viewIntent] = await withGeometryMembers(components, model, [intent]);
          const scopeGuids = viewIntent.members.map((member) => member.guid);
          // On a STREAMED model the members' tiles arrive after the camera
          // moves (below); the loader re-applies this Refer to each batch
          // that carries one of them (ThatOpenCompanyLoader.js, Step 6.9).
          setStreamedRefer(getModelContext(model)?.isStreamed ? { intent, fileName, guids: scopeGuids } : null);
          // Measure and paint as ONE queued task: on a parsed model the box is
          // measured through the origin fragments, so a Refer clicked while a
          // previous one's split is still running must not measure mid-split.
          const scopeBox = await queued(async () => {
            const box = await computeGuidsBoundingBox(components, model, scopeGuids);
            await visualizeIntentGroups(components, model, world, [intent], fileName);
            return box;
          });

          let viewRecord = null;
          if (scopeBox) {
            // After visualizeIntentGroups, never before: referByGuids calls
            // clearReferForViewer on its way in, which nulls the old scope.
            const buildingBox = computeBuildingBoundingBox(components, classifier, model);
            setCameraScope(world, { guids: scopeGuids, box: scopeBox, buildingBox, intentId: intent.id });
            // The fit is a view spec (views/applyView.js): scope = this
            // intent, which reuses the box measured above; direction kept;
            // context = the slider. Every unset field falls through to what
            // the fitCameraToScope call this replaced did, so the pose is the
            // same (scripts/e2e/views.py pins it). Animated, like Saved View
            // recall and unlike the instant preset buttons - this one follows
            // a click on a list row, so the motion is what tells the user
            // where in the model they just landed. Awaited, so referStatus
            // below still means done.
            // Refer keeps the current direction, as it always has. (An opt-in
            // that applied the type's rule view here - views/rules.js - was
            // built and removed on 2026-10-01 at the owner's request; the rule
            // views serve the batch driver only.)
            try {
              viewRecord = await applyView(
                world,
                { scope: { kind: "intent", intentId: intent.id }, transition: true },
                { chosenBy: "refer" },
              );
            } catch (err) {
              console.warn(`Refer: the view for "${intent.label}" could not be applied:`, err?.message ?? err);
            }
          } else {
            // Say so. Until 2026-09-24 this branch did not exist, and a Refer
            // that could not be measured simply did nothing: no scope, no
            // Context row, no camera move, no message - `referStatus` still
            // reached "done" because the highlight itself had succeeded.
            // That is how the streamed-model Refer gap stayed invisible for six
            // days. The known cause is a STREAMED model: `getFragmentMap`
            // answers from the tile-set manifest, so the ids resolve, but the
            // fragments themselves are only fetched by the culler when they
            // come into view - so BoundingBoxer has nothing to measure and
            // returns an empty box. Measured on 0206.ifc: 6 of 6 member GUIDs
            // resolved, 6 fragment ids returned, 0 of those 6 fragments
            // present in `fragments.list`.
            console.warn(
              `Refer: could not measure "${intent.label}" - none of its ${scopeGuids.length} element(s) ` +
                `has geometry (parsed: nothing loaded for them; streamed: the tile set carries no ` +
                `geometry for them), so there is nothing to frame. The highlight was applied, the ` +
                `camera was not moved.`,
            );
          }

          // NOTE: this signal now also means "camera
          // settled", not just "highlight applied" - it is awaited past the
          // fit above. A batch driver needs no second signal, but it does get
          // a later "done" than before.
          row.dataset.referStatus = "done";
          referBtn.removeAttribute("aria-busy");
          // The one animation in this panel: the status ring pulses once in
          // the category colour exactly when the camera has landed, so "the
          // view you are looking at is this row" needs no reading. CSS-only,
          // skipped under prefers-reduced-motion (style.css).
          iconEl.classList.remove("is-pulsing");
          void iconEl.offsetWidth; // restart the animation if it is still running
          iconEl.classList.add("is-pulsing");
          // `record` (2026-10-01, additive): the view record the fit produced,
          // null when nothing could be framed. The id was
          // always here and stays first.
          row.dispatchEvent(
            new CustomEvent("intent-refer-complete", {
              bubbles: true,
              detail: { intentId: intent.id, record: viewRecord },
            }),
          );
        });
        iconEl.addEventListener("animationend", () => iconEl.classList.remove("is-pulsing"));

        const setRowVerdict = (verdict) => {
          setVerdict(fileKey, intent, verdict);
          verdictState.set(intent.id, verdict);
          row.dataset.verdict = verdict;
          iconEl.classList.toggle("status-accepted", verdict === "accepted");
          row.classList.toggle("verdict-rejected", verdict === "rejected");
          acceptBtn.classList.toggle("is-active", verdict === "accepted");
          rejectBtn.classList.toggle("is-active", verdict === "rejected");
          iconEl.title = `Category: ${categoryLabel} · Verdict: ${verdict}`;
          repaintLedgers();
          refilterKeepingPlace(row);
        };

        acceptBtn.addEventListener("click", () => setRowVerdict("accepted"));
        rejectBtn.addEventListener("click", () => setRowVerdict("rejected"));

        // Clears all three "clicked" statuses for THIS row: un-does the
        // verdict (back to pending, removed from storage - not just visually
        // hidden), and un-refers the 3D view if this row was the one
        // currently referred (restores full visibility, since there's no
        // "what was visible right before this row's Refer" to go back to -
        // same as the panel-wide Clear selection button below).
        resetBtn.addEventListener("click", () => {
          clearVerdict(fileKey, intent.id);
          verdictState.delete(intent.id);
          row.dataset.verdict = "pending";
          iconEl.classList.remove("status-accepted");
          row.classList.remove("verdict-rejected");
          acceptBtn.classList.remove("is-active");
          rejectBtn.classList.remove("is-active");
          iconEl.title = `Category: ${categoryLabel} · Verdict: pending`;

          if (referBtn.classList.contains("is-active")) {
            referBtn.classList.remove("is-active");
            activeReferBtn = null;
            setStreamedRefer(null);
            queued(() => {
              clearIntentHighlights(components);
              clearReferForViewer(world);
            });
          }
          repaintLedgers();
          refilterKeepingPlace(row);
        });

        const entry = {
          row,
          intent,
          categoryEntry,
          evidenceEl,
          haystack: `${intent.index ?? ""} ${intent.label} ${evidenceText}`.toLowerCase(),
        };
        categoryEntry.rows.push(entry);
        allRows.push(entry);
      }
    }
  }

  // ---- Filter ----
  const filterInput = filterStrip.querySelector(".intent-filter-input");
  const chips = [...filterStrip.querySelectorAll(".intent-chip")];
  const chipOn = (name) =>
    chips.find((c) => c.dataset.chip === name)?.getAttribute("aria-pressed") === "true";

  function applyFilter() {
    const needle = filterInput.value.trim().toLowerCase();
    const verdictChips = ["pending", "accepted", "rejected"].filter(chipOn);
    const draftOnly = chipOn("draft");
    const filtering = Boolean(needle) || verdictChips.length > 0 || draftOnly;
    inner.classList.toggle("is-filtering", filtering);

    for (const c of categoryEntries) {
      let shown = 0;
      const categoryHidden = draftOnly && !c.isDraft;
      for (const { row, intent, haystack } of c.rows) {
        const verdict = verdictOf(intent.id);
        const hide =
          categoryHidden ||
          (needle && !haystack.includes(needle)) ||
          (verdictChips.length && !verdictChips.includes(verdict));
        row.hidden = Boolean(hide);
        if (!hide) shown++;
      }
      c.countEl.textContent = filtering ? `${shown} / ${c.rows.length}` : String(c.rows.length);
      c.section.classList.toggle("is-filtered-empty", filtering && shown === 0);
      // A text search that hits inside a folded category opens it - the
      // match is the reason the user typed; making them also click is noise.
      if (needle && shown > 0 && !c.section.open) c.section.open = true;
    }
  }

  // A verdict can hide the row it was given to (Pending chip on: "judge,
  // next, judge" is the whole point of that filter). Re-filter, and if the
  // current row just vanished, hand the keyboard to the row that followed it
  // - measured BEFORE the filter ran, since afterwards it has no neighbours.
  function refilterKeepingPlace(row) {
    const wasCurrent = activeRow === row;
    const before = wasCurrent ? visibleRows() : null;
    const i = before ? before.findIndex((r) => r.row === row) : -1;
    applyFilter();
    if (!wasCurrent || !row.hidden) return;
    const after =
      before.slice(i + 1).find((r) => !r.row.hidden) ??
      [...before.slice(0, i)].reverse().find((r) => !r.row.hidden);
    if (after)
      setActiveRow(after.row, {
        focus: document.activeElement === row || document.activeElement === document.body,
        scroll: true,
      });
    else {
      row.classList.remove("is-current");
      activeRow = null;
    }
  }

  filterInput.addEventListener("input", applyFilter);
  filterInput.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      if (filterInput.value) {
        filterInput.value = "";
        applyFilter();
      } else filterInput.blur();
      event.stopPropagation();
    }
  });
  for (const chip of chips) {
    chip.addEventListener("click", () => {
      chip.setAttribute(
        "aria-pressed",
        chip.getAttribute("aria-pressed") === "true" ? "false" : "true",
      );
      applyFilter();
    });
  }

  // ---- Keyboard review ----
  // The "current row" is one roving focus target. Navigation walks rows that
  // are visible right now: not filtered out, inside an open category. `]`/`[`
  // hop categories (opening the target), so a reviewer never needs the mouse
  // to get from the last row of one category to the first of the next.
  let activeRow = null;

  const visibleRows = () =>
    allRows.filter(({ row, categoryEntry }) => !row.hidden && categoryEntry.section.open);

  function setActiveRow(row, { focus = true, scroll = true } = {}) {
    if (activeRow && activeRow !== row) activeRow.classList.remove("is-current");
    activeRow = row;
    if (!row) return;
    row.classList.add("is-current");
    if (focus) row.focus({ preventScroll: true });
    // scroll-margin-top (style.css) keeps it clear of the two sticky headers.
    if (scroll) row.scrollIntoView({ block: "nearest" });
  }

  function moveRow(delta) {
    const rows = visibleRows();
    if (!rows.length) return;
    const i = rows.findIndex((r) => r.row === activeRow);
    const next =
      i === -1
        ? delta > 0
          ? 0
          : rows.length - 1
        : Math.min(rows.length - 1, Math.max(0, i + delta));
    setActiveRow(rows[next].row);
  }

  function moveCategory(delta) {
    const cats = categoryEntries.filter((c) => !c.section.classList.contains("is-filtered-empty"));
    if (!cats.length) return;
    const currentIndex = activeRow ? cats.findIndex((c) => c.section.contains(activeRow)) : -1;
    const next =
      currentIndex === -1
        ? delta > 0
          ? 0
          : cats.length - 1
        : (currentIndex + delta + cats.length) % cats.length;
    const target = cats[next];
    target.section.open = true;
    target.domainEntry.section.open = true;
    const first = target.rows.find(({ row }) => !row.hidden);
    if (first) setActiveRow(first.row);
    else target.header.scrollIntoView({ block: "nearest" });
  }

  const clickIn = (row, selector) => row?.querySelector(selector)?.click();

  inner.addEventListener("keydown", (event) => {
    if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey) return;
    if (isTypingTarget(event.target)) return;
    const key = event.key;
    let handled = true;
    switch (key) {
      case "ArrowDown":
        moveRow(1);
        break;
      case "ArrowUp":
        moveRow(-1);
        break;
      case "]":
        moveCategory(1);
        break;
      case "[":
        moveCategory(-1);
        break;
      case "Enter":
      case " ":
        // A focused button or <summary> keeps its native activation.
        if (event.target instanceof HTMLButtonElement || event.target?.tagName === "SUMMARY") {
          handled = false;
          break;
        }
        clickIn(activeRow, ".intent-refer-btn");
        break;
      case "a":
        clickIn(activeRow, ".intent-accept-btn");
        break;
      case "r":
        clickIn(activeRow, ".intent-reject-btn");
        break;
      case "u":
        clickIn(activeRow, ".intent-reset-btn");
        break;
      case "e":
        activeRow?.classList.toggle("is-expanded");
        break;
      case "/":
        filterInput.focus();
        filterInput.select();
        break;
      case "?":
        toggleShortcuts();
        break;
      case "Escape":
        bulkRow.querySelector(".intent-clear-btn").click();
        break;
      default:
        handled = false;
    }
    if (handled) event.preventDefault();
  });

  // Make the panel itself focusable so the shortcuts work as soon as the
  // reviewer clicks anywhere in it, before any row is current.
  inner.tabIndex = -1;

  bulkRow.querySelector(".intent-show-all-btn").addEventListener("click", () => {
    activeReferBtn?.classList.remove("is-active");
    activeReferBtn = null;
    setStreamedRefer(null);
    queued(() => visualizeIntentGroups(components, model, world, intents, fileName));
  });
  // Simply reveals everything, rather than restoring the Floors/Categories
  // checkbox state the way the GUID section's own Clear does - consistent
  // with this app's existing "no shared mode state, later overrides win"
  // philosophy.
  bulkRow.querySelector(".intent-clear-btn").addEventListener("click", () => {
    activeReferBtn?.classList.remove("is-active");
    activeReferBtn = null;
    setStreamedRefer(null);
    queued(() => {
      clearIntentHighlights(components);
      clearReferForViewer(world);
    });
  });

  const exportBtn = document.createElement("button");
  exportBtn.type = "button";
  exportBtn.className = "bulk-toggle-btn intent-export-btn";
  exportBtn.textContent = "Export";
  exportBtn.title = "Export verdicts (JSON)";
  exportBtn.addEventListener("click", () => {
    const payload = exportVerdictsPayload(fileKey);
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    // Named by the human-facing file name, not the content key - the key is
    // inside the payload, where a downstream tool reads it.
    a.download = `${fileName.replace(/\.ifc$/i, "")}_verdicts.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  });
  footer.appendChild(exportBtn);
  inner.appendChild(footer);

  // Only evidence that really overflows its two lines gets the "expandable"
  // affordance. Measured lazily, once per category open (rows inside a closed
  // <details> have no layout to measure).
  function markOverflowingEvidence(categoryEntry) {
    for (const { row, evidenceEl } of categoryEntry.rows) {
      if (row.classList.contains("is-expanded")) continue;
      row.classList.toggle("has-more", evidenceEl.scrollHeight > evidenceEl.clientHeight + 1);
    }
  }
  for (const c of categoryEntries) {
    c.section.addEventListener("toggle", () => {
      if (c.section.open) markOverflowingEvidence(c);
    });
  }

  repaintLedgers();
}
