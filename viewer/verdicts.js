// ======== Intent Validation Verdicts ========
// Pure, dependency-free storage for human accept/reject verdicts on
// recognized intent groups - no OBC/THREE dependency. Backed by localStorage so verdicts
// survive a page reload; see docs/roadmap.md "Not built yet" for the
// eventual real store, whose batch-pipeline shape this is designed to match.

const storageKey = (fileKey) => `bi2m:verdicts:${fileKey}`;

/**
 * Records written before the 2026-09-24 pattern -> intent rename carry
 * `patternId`/`patternType`. The STORE KEY is unchanged
 * (`bi2m:verdicts:<fileKey>`, deliberately frozen) and so is the map
 * key (the intent's own id), so nothing was orphaned - but an export would
 * otherwise hand out two field vocabularies in one payload, one per era of
 * the review. Normalised on read rather than migrated on load: a read is
 * where the inconsistency would show, and this way a browser that never
 * writes again is never rewritten behind the user's back.
 */
function normalizeRecord(record) {
  if (!record || typeof record !== "object") return record;
  if (record.intentId !== undefined) return record;
  const { patternId, patternType, ...rest } = record;
  return { intentId: patternId, intentType: patternType, ...rest };
}

export function getVerdicts(fileKey) {
  try {
    const stored = JSON.parse(localStorage.getItem(storageKey(fileKey)) || "{}");
    return Object.fromEntries(Object.entries(stored).map(([id, v]) => [id, normalizeRecord(v)]));
  } catch {
    return {};
  }
}

export function setVerdict(fileKey, intent, verdict) {
  const all = getVerdicts(fileKey);
  all[intent.id] = {
    intentId: intent.id,
    intentType: intent.type,
    detector: intent.provenance?.detector ?? null,
    rule: intent.provenance?.rule ?? null,
    verdict, // "accepted" | "rejected"
    reviewedAt: new Date().toISOString(),
    // {guid, role, ifcClass}[] - copied straight from the intent already in
    // hand here, not recomputed - makes the verdict self-contained (which
    // exact elements/classes this judged) even if intent_groups.json is
    // later regenerated with different ids.
    members: intent.members ?? [],
  };
  localStorage.setItem(storageKey(fileKey), JSON.stringify(all));
  return all[intent.id];
}

export function clearVerdict(fileKey, intentId) {
  const all = getVerdicts(fileKey);
  delete all[intentId];
  localStorage.setItem(storageKey(fileKey), JSON.stringify(all));
}

export function exportVerdictsPayload(fileKey) {
  return { fileKey, verdicts: Object.values(getVerdicts(fileKey)) };
}
