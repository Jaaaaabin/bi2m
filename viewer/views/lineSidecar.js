// ======== Line sidecars: authored shapes beside a model ========
// A spatial intent grid is data the designer writes, not something a
// detector finds. This is where it lives: one JSON file per model under
// public/res/lines/<content key>.json, holding line specs (views/lineSpec.js)
// in the model's own plan metres or anchored to its elements, so it survives
// re-exports that keep the content key.
//
// Discovery goes through public/res/lines/index.json, which lists the keys
// that have a file, so a model without one costs no request and logs no 404 -
// the intents' res/intents/index.json plays the same role. Both fetches are
// cached as promises, the way intentData.js caches shards, so two viewers on
// the same model share one request.

export const LINE_SIDECAR_SCHEMA = 1;

let indexPromise = null;
const sidecarCache = new Map();

async function loadIndex() {
  if (!indexPromise) {
    indexPromise = fetch("./res/lines/index.json")
      .then(async (res) => (res.ok ? res.json() : {}))
      .catch(() => ({}));
  }
  return indexPromise;
}

/**
 * The authored line specs for a model, `[]` when it has none. Malformed
 * files are reported once and treated as empty; the viewer never breaks on a
 * sidecar.
 * @param {string} fileKey - the model's content key (fileIdentity.js)
 * @param {{refresh?: boolean}} [options]
 * @returns {Promise<Array<Record<string, any>>>}
 */
export async function loadLineSidecar(fileKey, { refresh = false } = {}) {
  if (!fileKey) return [];
  if (refresh) {
    indexPromise = null;
    sidecarCache.delete(fileKey);
  }
  if (!sidecarCache.has(fileKey)) {
    sidecarCache.set(
      fileKey,
      (async () => {
        const index = await loadIndex();
        if (!index?.files?.[fileKey]) return [];
        const suffix = refresh ? `?t=${Date.now()}` : "";
        const res = await fetch(`./res/lines/${encodeURIComponent(fileKey)}.json${suffix}`);
        if (!res.ok) {
          console.warn(`Line sidecar for ${fileKey} is listed but failed to load: ${res.status}`);
          return [];
        }
        const doc = await res.json();
        if (!doc || doc.schema !== LINE_SIDECAR_SCHEMA || !Array.isArray(doc.lines)) {
          console.warn(
            `Line sidecar for ${fileKey} is not {schema: ${LINE_SIDECAR_SCHEMA}, lines: [...]}; ignoring it.`,
          );
          return [];
        }
        return doc.lines;
      })(),
    );
  }
  return sidecarCache.get(fileKey);
}
