// Minimal browser shims for modules that touch localStorage/fetch/location at
// import time. Kept deliberately tiny - a module that needs more than this
// belongs in an e2e harness, not a unit test.
class MemoryStorage {
  constructor() {
    this.map = new Map();
  }
  getItem(k) {
    return this.map.has(k) ? this.map.get(k) : null;
  }
  setItem(k, v) {
    this.map.set(k, String(v));
  }
  removeItem(k) {
    this.map.delete(k);
  }
  clear() {
    this.map.clear();
  }
  get length() {
    return this.map.size;
  }
  key(i) {
    return [...this.map.keys()][i] ?? null;
  }
}
globalThis.localStorage = new MemoryStorage();
if (!globalThis.location) globalThis.location = { search: "", href: "http://localhost/" };
// Relative fetches (./res/...) have no meaning here; modules must tolerate the rejection.
globalThis.fetch = () => Promise.reject(new Error("fetch is not available in unit tests"));
