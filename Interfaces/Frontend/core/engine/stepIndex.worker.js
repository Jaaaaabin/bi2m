/**
 * Runs `StepFileIndex.build()` (see stepIndex.js) off the main thread. Only
 * ever driven via stepIndexClient.js's `buildStepIndexAsync()` - see that
 * file for why a plain-data response (not a StepFileIndex instance) is
 * posted back, and why a fresh worker is spawned per call.
 */
import { StepFileIndex } from "./stepIndex.js";

self.onmessage = (event) => {
  const { buf } = event.data;
  try {
    const index = StepFileIndex.build(buf);
    self.postMessage(
      {
        ok: true,
        buf: index.buf,
        headerEndOffset: index.headerEndOffset,
        startById: index.startById,
        relBuckets: index.relBuckets,
        schema: index.schema,
        projectId: index.projectId,
      },
      [index.buf.buffer],
    );
  } catch (err) {
    self.postMessage({ ok: false, error: err.message });
  }
};
