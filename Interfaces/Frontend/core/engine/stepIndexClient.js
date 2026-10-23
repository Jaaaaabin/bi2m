/**
 * Browser-only Worker wrapper around `StepFileIndex.build()` (see
 * stepIndex.js), so its synchronous byte scan (~76-126ms measured on 5-20MB
 * files) no longer blocks the main thread. Kept out of stepIndex.js itself
 * so that file stays pure JS/Node-testable per its own header comment -
 * `Worker` is a browser-only API.
 *
 * A fresh worker is spawned per call and terminated once it resolves/
 * rejects. `StepFileIndex.build()` runs once per file load, not a hot path,
 * so per-call spawn cost isn't worth a persistent/shared worker's added
 * message-routing bookkeeping across concurrent viewers/uploads.
 *
 * The worker can only post back plain, structured-cloneable data - it can't
 * hand back a real StepFileIndex instance (structured clone drops the class
 * prototype and the private #childrenByParent field), so this reconstructs
 * one from the returned fields via the same constructor `StepFileIndex.
 * build()` itself uses. The constructor does no re-parsing, so reconstruction
 * is effectively free.
 */
import { StepFileIndex } from "./stepIndex.js";

/** @returns {Promise<StepFileIndex>} */
export function buildStepIndexAsync(buf) {
  return new Promise((resolve, reject) => {
    const worker = new Worker(new URL("./stepIndex.worker.js", import.meta.url), {
      type: "module",
    });

    worker.onmessage = (event) => {
      worker.terminate();
      const data = event.data;
      if (!data.ok) {
        reject(new Error(data.error));
        return;
      }
      resolve(
        new StepFileIndex(
          data.buf,
          data.headerEndOffset,
          data.startById,
          data.relBuckets,
          data.schema,
          data.projectId,
        ),
      );
    };

    worker.onerror = (event) => {
      worker.terminate();
      reject(new Error(event.message || "StepFileIndex worker failed"));
    };

    // Transfer, not clone: `buf` is never read again on the main thread after
    // this call (the caller's copy is only used up through this point), so a
    // zero-copy transfer avoids doubling memory on large files - the whole
    // point of moving this work off-thread. This also detaches `buf` on the
    // main thread as a side effect; callers must not read it after calling.
    worker.postMessage({ buf }, [buf.buffer]);
  });
}
