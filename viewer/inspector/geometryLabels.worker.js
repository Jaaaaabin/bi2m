// Runs buildGeometryLabels (geometryLabels.js) off the main thread. Receives
// the file's bytes (transferred, not copied) and posts back the labels as
// [shapeId, label] pairs; the bytes die with the worker.
import { buildGeometryLabels } from "./geometryLabels.js";

self.onmessage = (event) => {
  try {
    const labels = buildGeometryLabels(new Uint8Array(event.data.buffer));
    self.postMessage({ ok: true, labels: [...labels] });
  } catch (err) {
    self.postMessage({ ok: false, error: err?.message ?? String(err) });
  }
};
