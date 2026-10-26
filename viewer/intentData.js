// ======== Recognized Intent Data ========
// Fetching + shaping of everything scripts/recognize_intents.py produces:
// the global category manifest, and one model's recognized intent groups.
//
// Layout change (docs/architecture.md "The shard"). This used to be ONE file,
// res/intent_groups.json, holding every model's intents keyed by filename
// stem, fetched in full at module load before any model was even open. It had
// grown to 10.4MB / 28 entries - of which 21 (7.1MB) were orphaned upload
// snapshots of the same 7 models - and a session used exactly one entry
// (~200KB). Now each model has its own shard, res/intents/<fileKey>.json,
// fetched only when that model is actually loaded.
//
// The category manifest stays eager: it is a few KB, it is not per-file, and
// the intent panel needs it to group/color the first model that loads.

// [{id, label, intentTypes, domain, scope, maturity}], generated fresh every
// recognize_intents.py run from its CATEGORIES registry
// (src/recognition/registry.py) - NOT keyed per file, since categories are a
// fixed, global vocabulary. Drives the intent panel's per-category grouping/
// color assignment, so a newly-registered Python category shows up with no
// frontend change. Missing/empty is tolerated: the panel falls back to
// grouping by whatever provenance.detector values show up in the data.
let intentCategoriesList = [];

export const intentCategoriesReady = fetch("./res/intent_categories.json")
  .then((res) => (res.ok ? res.json() : []))
  .then((data) => {
    intentCategoriesList = Array.isArray(data) ? data : [];
  })
  .catch(() => {
    intentCategoriesList = [];
  });

export const getIntentCategories = () => intentCategoriesList;

// One entry per model key, so re-opening the same model in a second viewer
// (or rebuilding a panel) doesn't re-fetch. Stores the PROMISE so two viewers
// loading the same file concurrently share one request.
const shardCache = new Map();

function shardUrl(fileKey, bust) {
  const suffix = bust ? `?t=${bust}` : "";
  return `./res/intents/${encodeURIComponent(fileKey)}.json${suffix}`;
}

// Mirrors STORE_VERSION in src/recognition/writers.py. 2 since 2026-09-24,
// when the envelope's list key became `intents` (it was `patterns`). Checked
// rather than assumed because the failure is silent: a v1 shard holds exactly
// the right records under the old key, so the array check below would find no
// `intents`, return an empty list, and the panel would say "no recognized
// intents" for a model with hundreds of them.
const SHARD_STORE_VERSION = 2;

async function fetchShard(fileKey, bust) {
  const res = await fetch(shardUrl(fileKey, bust));
  if (res.status === 404) {
    // Not an error: most models simply have no recognition results yet. Said
    // out loud with the exact command that produces them, because the
    // previous store shape made "no intents" and "wrong key" look identical.
    console.info(
      `No intent shard for ${fileKey} (res/intents/${fileKey}.json). ` +
        `Run: uv run python scripts/recognize_intents.py --files <this file>`,
    );
    return { intents: [] };
  }
  if (!res.ok) throw new Error(`Intent shard request failed: ${res.status}`);
  const shard = await res.json();
  if (shard && shard.storeVersion !== undefined && shard.storeVersion !== SHARD_STORE_VERSION) {
    console.warn(
      `Intent shard for ${fileKey} is storeVersion ${shard.storeVersion}, expected ${SHARD_STORE_VERSION}. ` +
        `Re-run: uv run python scripts/recognize_intents.py --files <this file>`,
    );
  }
  return shard && Array.isArray(shard.intents) ? shard : { intents: [] };
}

/**
 * This model's recognized intents, with a stable per-CATEGORY colorIndex
 * already assigned. Fetched once per key and cached.
 *
 * @param {string} fileKey - content key from fileIdentity.js.
 * @param {{refresh?: boolean}} [options] - `refresh` bypasses and replaces the
 *   cache entry (used after a Compute run rewrites this exact shard on disk).
 */
export async function loadIntentsForModel(fileKey, { refresh = false } = {}) {
  if (refresh || !shardCache.has(fileKey)) {
    shardCache.set(
      fileKey,
      fetchShard(fileKey, refresh ? Date.now() : null).catch((err) => {
        console.warn(`⚠️ Could not load intent shard for ${fileKey}:`, err.message);
        // Carried on the cached shard so the panel can tell a FAILED request
        // from a model with no results (2026-10-01); getShardMeta exposes it.
        return { intents: [], error: err.message };
      }),
    );
  }
  const shard = await shardCache.get(fileKey);
  await intentCategoriesReady;
  return assignCategoryColorIndexes(
    shard.intents,
    intentCategoriesList.map((c) => c.id),
  );
}

/**
 * The shard's own envelope for a model already loaded through
 * loadIntentsForModel: today that is `preflight` ({signals, inapplicable} -
 * which categories cannot apply to this model and why, see
 * src/recognition/preflight.py). Resolves to {} when the shard is missing
 * or predates the field.
 */
export async function getShardMeta(fileKey) {
  const shard = shardCache.has(fileKey) ? await shardCache.get(fileKey) : { intents: [] };
  return { preflight: shard?.preflight ?? null, error: shard?.error ?? null };
}

/**
 * Re-fetches what a Compute run just wrote, for one model. Replaces the old
 * refreshIntentData(), which re-fetched the ENTIRE corpus (and the category
 * manifest) to pick up a change to one file.
 */
export async function refreshIntentsForModel(fileKey) {
  // The manifest can legitimately have gained a category in that same run.
  const categories = await fetch(`./res/intent_categories.json?t=${Date.now()}`)
    .then((res) => (res.ok ? res.json() : null))
    .catch(() => null);
  if (Array.isArray(categories)) intentCategoriesList = categories;

  return loadIntentsForModel(fileKey, { refresh: true });
}

// Assigns colorIndex per CATEGORY (provenance.detector), not per intent -
// every intent belonging to the same category shares one palette slot, so
// one hue always means one category, both in the panel's category icon and in
// visualizeIntentGroups' refer/highlight color (it just reads colorIndex,
// unchanged). `categoryOrder` should be the manifest's own id order when
// available, so a category's color is also stable ACROSS files, not just
// within one - falls back to first-seen order among this file's own intents
// if the manifest is missing/empty.
export function assignCategoryColorIndexes(intents, categoryOrder) {
  const order = categoryOrder.length
    ? categoryOrder
    : [...new Set(intents.map((p) => p.provenance?.detector ?? "uncategorized"))];

  return intents.map((intent) => {
    const categoryId = intent.provenance?.detector ?? "uncategorized";
    const known = order.indexOf(categoryId);
    return { ...intent, colorIndex: known === -1 ? order.length : known };
  });
}
