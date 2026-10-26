// ======== Saved views: persisted per model, as full view records ========
// Until now a saved view was `{name, pos, target}` in createViewerMenu's
// closure: gone on reload, and blind to projection, zoom, scope, context and
// everything else that defines a camera view. A saved view is now a VIEW
// RECORD (applyView.js) under a name, stored the way verdicts are
// (verdicts.js): localStorage, one key per model content key, so it survives
// a reload and joins the same model after the library is renumbered.
//
// Pure and dependency-free like verdicts.js, so the unit tests run in node.
// `bi2m:` is the namespace settings.js owns; this key sits next to
// `bi2m:verdicts:<fileKey>` and, like it, is review data rather than a
// setting - settings.js's migrate/get/set never touch it.

export const SAVED_VIEWS_SCHEMA = 1;

const storageKey = (fileKey) => `bi2m:views:${fileKey}`;

function readAll(fileKey) {
  try {
    const stored = JSON.parse(localStorage.getItem(storageKey(fileKey)) || "null");
    return Array.isArray(stored?.views) ? stored.views : [];
  } catch {
    return [];
  }
}

function writeAll(fileKey, views) {
  try {
    localStorage.setItem(storageKey(fileKey), JSON.stringify({ schema: SAVED_VIEWS_SCHEMA, views }));
  } catch {
    // Storage unavailable (private mode, quota) - the view still exists for this session's caller.
  }
}

const newId = () => `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;

/**
 * This model's saved views, oldest first.
 * @param {string} fileKey
 * @returns {Array<{id: string, name: string, savedAt: string, record: object}>}
 */
export function listSavedViews(fileKey) {
  return readAll(fileKey);
}

/**
 * Saves a record under a name. Names need not be unique; ids are.
 * @param {string} fileKey
 * @param {{name: string, record: object}} view
 */
export function saveView(fileKey, { name, record }) {
  const views = readAll(fileKey);
  const entry = { id: newId(), name: String(name || "").trim() || `View ${views.length + 1}`, savedAt: new Date().toISOString(), record };
  views.push(entry);
  writeAll(fileKey, views);
  return entry;
}

/**
 * @param {string} fileKey
 * @param {string} id
 * @returns {boolean} whether something was removed
 */
export function deleteSavedView(fileKey, id) {
  const views = readAll(fileKey);
  const remaining = views.filter((v) => v.id !== id);
  if (remaining.length === views.length) return false;
  writeAll(fileKey, remaining);
  return true;
}

/**
 * Everything about this model's saved views, for a JSON download. The
 * fileKey travels with the data for the same reason verdict exports carry it:
 * the file is the join key, nothing else is.
 * @param {string} fileKey
 */
export function exportViewsPayload(fileKey) {
  return { schema: SAVED_VIEWS_SCHEMA, fileKey, exportedAt: new Date().toISOString(), views: readAll(fileKey) };
}

/**
 * Imports an exported payload into a model's store. Entries whose id already
 * exists are skipped; `replace` empties the store first. Entries without a
 * record are refused.
 * @param {string} fileKey
 * @param {Record<string, any>} payload
 * @param {{replace?: boolean}} [options]
 * @returns {number} how many views were added
 */
export function importViews(fileKey, payload, { replace = false } = {}) {
  const incoming = Array.isArray(payload?.views) ? payload.views : [];
  const views = replace ? [] : readAll(fileKey);
  const known = new Set(views.map((v) => v.id));
  let added = 0;
  for (const view of incoming) {
    if (!view || typeof view !== "object" || !view.record || typeof view.record !== "object") continue;
    if (typeof view.id === "string" && known.has(view.id)) continue; // already here: skipped, not duplicated
    const entry = {
      id: typeof view.id === "string" ? view.id : newId(),
      name: String(view.name || "").trim() || `View ${views.length + 1}`,
      savedAt: typeof view.savedAt === "string" ? view.savedAt : new Date().toISOString(),
      record: view.record,
    };
    known.add(entry.id);
    views.push(entry);
    added += 1;
  }
  writeAll(fileKey, views);
  return added;
}
