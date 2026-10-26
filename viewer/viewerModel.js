// ======== Per-Model Context ========
// Everything the viewer derives ONCE per loaded model and then needs again
// later, in one place - replacing the ad-hoc properties once set on the model and
// the several independent re-derivations of a file key from a file name.
//
// Held in a WeakMap keyed by the FragmentsGroup itself, not as properties on
// it: the model is owned by @thatopen/components, and a WeakMap keeps this
// app's own bookkeeping off a foreign object while still being collected
// automatically when that viewer is disposed.
//
// Fields:
//   key        content-addressed file key (see fileIdentity.js) - the join
//              key for intent shards, verdicts, uploads and the extraction
//              cache. THE identity; nothing else re-derives one.
//   keySource  "content" | "filename" - which path produced `key`.
//   fileName   the file's local name, for display only.
//   lineage    {fileName, ifcFileName, projectGuid} - provenance, never joined on.
//   geometryLabels  Promise<Map<shape id, label>> for the inspector's Geometry
//              row (inspector/describeElement.js), or undefined.
//   guidIndex  lazily built Map<GlobalId, {fragmentID, expressID}> - see
//              getGuidIndex() below.
//   intents   this model's recognized intent groups, colorIndex already assigned.

const contexts = new WeakMap();

export function setModelContext(model, context) {
  contexts.set(model, context);
  return context;
}

export function getModelContext(model) {
  return contexts.get(model);
}

/** The content key for a loaded model, or undefined if it has no context. */
export function getModelKey(model) {
  return contexts.get(model)?.key;
}

/**
 * The model's GUID -> {fragmentID, expressID} index, built at most once per
 * model and reused by every later call.
 *
 * This used to be rebuilt from scratch on every single call: highlightGUIDs,
 * referByGuids and grayOutExceptGuids each called buildGuidIndex()
 * independently, and visualizeIntentGroups calls the first two in sequence -
 * so one click of an intent row's "Refer" button walked the ENTIRE model
 * twice (getFragmentMap() x getLocalProperties(), O(elements)), every click,
 * on top of the same walk already paid at load time. Caching it here makes
 * every call after the first free, and costs nothing when a model is never
 * referred at all, since it is still built lazily on first use.
 *
 * The cache is safe because the index maps a STABLE identity (an element's
 * IFC GlobalId) to a STABLE location (which fragment holds it, under which
 * expressID). Nothing this app does afterwards changes either: Hider only
 * flips per-instance visibility, the Highlighter only writes instance
 * colors, and the refer split (splitReferredItems) clones items into a new
 * fragment while leaving the originals in place. A genuinely new model gets
 * its own context and therefore its own index.
 *
 * @param {object} model
 * @param {(model: object) => Promise<Map>} build - the builder to use on a miss.
 */
export async function getGuidIndex(model, build) {
  const context = contexts.get(model);
  if (!context) return build(model); // no context (shouldn't happen) - stay correct, just uncached
  if (!context.guidIndex) {
    // Store the PROMISE, not the resolved Map, so two concurrent callers
    // (highlightGUIDs and referByGuids are called back-to-back) share one
    // build instead of racing into two.
    context.guidIndex = build(model);
  }
  return context.guidIndex;
}
