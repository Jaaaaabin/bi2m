import { describe, it, expect, afterEach } from "vitest";
import { fetchModelFile, formatFileSize, formatProgress } from "../../page/fetchFile.js";

const body = (chunks) =>
  new ReadableStream({
    start(controller) {
      for (const c of chunks) controller.enqueue(c);
      controller.close();
    },
  });

/** A Response carrying `chunks`, optionally announcing a Content-Length. */
function streamed(chunks, { length = null, headers = {}, ok = true, status = 200 } = {}) {
  const total = length ?? chunks.reduce((n, c) => n + c.length, 0);
  return new Response(ok ? body(chunks) : "{}", {
    status,
    headers: { ...(total === 0 ? {} : { "Content-Length": String(total) }), ...headers },
  });
}

const original = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = original;
});

describe("formatProgress", () => {
  it("reports received, total and a whole percent", () => {
    expect(formatProgress(3.2 * 1024 * 1024, 18.5 * 1024 * 1024)).toBe("3.2 MB / 18.5 MB · 17%");
  });
  it("falls back to a bare size when the server sent no length", () => {
    expect(formatProgress(820 * 1024, 0)).toBe("820 KB");
  });
  it("uses KB below a megabyte, like the model lists", () => {
    expect(formatFileSize(500 * 1024)).toBe("500 KB");
  });
});

describe("fetchModelFile", () => {
  const chunks = [new Uint8Array(400), new Uint8Array(400), new Uint8Array(224)];

  it("streams the body and reports progress against Content-Length", async () => {
    globalThis.fetch = async () => streamed(chunks);
    const seen = [];
    const file = await fetchModelFile("/x", "0216.ifc", {
      onProgress: (received, total) => seen.push([received, total]),
    });
    expect(file.name).toBe("0216.ifc");
    expect(file.size).toBe(1024);
    expect(seen.at(-1)).toEqual([1024, 1024]);
    expect(seen.length).toBeGreaterThan(1); // not one report at the end
    expect(seen.map(([r]) => r)).toEqual([...seen.map(([r]) => r)].sort((a, b) => a - b));
  });

  it("reports at most once per whole percent", async () => {
    // 1000 one-byte chunks against a 1000-byte total: 100 percent steps, not 1000.
    globalThis.fetch = async () => streamed(Array.from({ length: 1000 }, () => new Uint8Array(1)));
    let calls = 0;
    await fetchModelFile("/x", "a.ifc", { onProgress: () => (calls += 1) });
    expect(calls).toBeLessThanOrEqual(101);
  });

  it("fails the load when a header check rejects the response", async () => {
    // Only the outcome is asserted, not the ordering. `fetchModelFile` calls
    // `validate(res)` before `res.body.getReader()`, which in a browser means
    // a stale key fails once the HEADERS are in rather than after a 20 MB
    // download - but Node's Response primes its stream on construction, so a
    // test here cannot tell the two apart. Verified in the browser instead.
    globalThis.fetch = async () =>
      streamed([new Uint8Array(8)], { headers: { "X-Content-Key": "wrong" } });
    await expect(
      fetchModelFile("/x", "a.ifc", {
        validate: (res) => {
          if (res.headers.get("X-Content-Key") !== "right") throw new Error("served wrong model");
        },
      }),
    ).rejects.toThrow("served wrong model");
  });

  it("uses the caller's message for a failed response", async () => {
    globalThis.fetch = async () => streamed([], { ok: false, status: 404 });
    await expect(
      fetchModelFile("/x", "a.ifc", { errorMessage: async () => "no such key" }),
    ).rejects.toThrow("no such key");
  });

  it("still loads when the response has no readable stream", async () => {
    globalThis.fetch = async () => ({
      ok: true,
      headers: new Headers({ "Content-Length": "8" }),
      body: null,
      arrayBuffer: async () => new ArrayBuffer(8),
    });
    const seen = [];
    const file = await fetchModelFile("/x", "a.ifc", {
      onProgress: (r, t) => seen.push([r, t]),
    });
    expect(file.size).toBe(8);
    expect(seen).toEqual([[8, 8]]);
  });
});
