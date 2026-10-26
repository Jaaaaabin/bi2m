// ======== Debug-gated logging ========
// `log()` is console.log that only speaks when debugging is on: the
// transparency slider used to log on every `input`
// event, and visibility/highlight code on every recompute. Warnings and
// errors stay on `console.warn`/`console.error`, unconditionally - this is
// only for the chatter.
//
// Turn on with `?debug` in the URL, or once per browser with
// `localStorage.setItem("bi2m:debug", "1")`. Read once at load: a
// localStorage read per log call would put the cost back into the hot paths.

function readFlag() {
  try {
    if (new URLSearchParams(location.search).has("debug")) return true;
    return localStorage.getItem("bi2m:debug") === "1";
  } catch {
    return false;
  }
}

export const DEBUG = readFlag();

export function log(...args) {
  if (DEBUG) console.log(...args);
}
