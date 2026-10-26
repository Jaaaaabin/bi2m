// ======== Fetching a model's bytes, with real transfer progress ========
// Both server-side model sources - the Examples flyout and the IFC library -
// used to `await res.arrayBuffer()`, which discards everything the browser
// knows about how far the transfer has got. The tile then sat silent until
// the bytes were in hand. Over the SSH port-forward this project is built
// around, an 18.5 MB model is a real part of the wait.
//
// This is the ONLY part of a load where a progress readout can honestly move.
// The parse that follows is a single blocking call into web-ifc with no
// progress event of its own (`OBC.IfcLoader` exposes `onIfcStartedLoading`
// and `onSetup`, nothing else), and it blocks the main thread hard enough
// that the CSS spinner stops rotating - measured 2026-09-24: during a
// test_5.ifc parse, three consecutive screenshot attempts timed out and the
// spinner produced one distinct frame in six seconds. A percentage that
// cannot repaint is worse than no percentage, so nothing here pretends to
// report on the parse.

/** `bytes` as "18.5 MB" / "820 KB" - the same rule the model lists use. */
export function formatFileSize(bytes) {
  return bytes < 1024 * 1024
    ? `${Math.round(bytes / 1024)} KB`
    : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** "3.2 / 18.5 MB · 17%", or just "3.2 MB" when the server sent no length. */
export function formatProgress(received, total) {
  if (!total) return formatFileSize(received);
  return `${formatFileSize(received)} / ${formatFileSize(total)} · ${Math.round((received / total) * 100)}%`;
}

/**
 * Fetches a model and returns it as a `File`, reporting transfer progress.
 *
 * @param {string} url
 * @param {string} fileName   what the returned File is called - the loader's
 *   intake only ever reads `.name`, so this is indistinguishable from a
 *   picker or drag-and-drop file.
 * @param {object} [options]
 * @param {(received: number, total: number) => void} [options.onProgress]
 *   called with bytes so far and the total (0 when the server sent no
 *   `Content-Length`). Called at most once per whole percent - a 20 MB body
 *   arrives in hundreds of chunks and a DOM write per chunk is pure waste.
 * @param {(res: Response) => void} [options.validate] runs on the response
 *   before the body is read, for header checks that should fail the load.
 * @param {(res: Response) => Promise<string>} [options.errorMessage] builds
 *   the thrown message for a non-OK response.
 */
export async function fetchModelFile(url, fileName, { onProgress, validate, errorMessage } = {}) {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(errorMessage ? await errorMessage(res) : `Server responded ${res.status}`);
  }
  validate?.(res);

  const total = Number(res.headers.get("Content-Length")) || 0;
  // No readable stream (an old browser, or a mocked Response in a test) means
  // no progress - but it must still load, so fall back to the previous path
  // rather than failing. The caller sees a single 100% report at the end.
  const reader = res.body?.getReader?.();
  if (!reader) {
    const bytes = await res.arrayBuffer();
    onProgress?.(bytes.byteLength, total || bytes.byteLength);
    return new File([bytes], fileName, { type: "application/octet-stream" });
  }

  const chunks = [];
  let received = 0;
  let lastPercent = -1;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value);
    received += value.length;
    const percent = total ? Math.round((received / total) * 100) : -1;
    if (percent !== lastPercent) {
      lastPercent = percent;
      onProgress?.(received, total);
    }
  }
  if (lastPercent !== 100) onProgress?.(received, total || received);
  return new File(chunks, fileName, { type: "application/octet-stream" });
}
