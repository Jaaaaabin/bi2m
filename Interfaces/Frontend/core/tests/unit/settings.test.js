import { describe, it, expect, beforeEach, vi } from "vitest";

describe("settings (one bi2m: namespace with legacy migration)", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetModules();
  });

  it("migrates ifcviewer-* keys on import and removes them", async () => {
    localStorage.setItem("ifcviewer-theme", "dark");
    localStorage.setItem("ifcviewer-sidebar-collapsed", "1");
    const { getSetting } = await import("../../settings.js");
    expect(getSetting("theme")).toBe("dark");
    expect(getSetting("sidebarCollapsed")).toBe("1");
    expect(localStorage.getItem("ifcviewer-theme")).toBeNull();
  });
  it("does not overwrite an existing bi2m: value with a legacy one", async () => {
    localStorage.setItem("bi2m:theme", "light");
    localStorage.setItem("ifcviewer-theme", "dark");
    const { getSetting } = await import("../../settings.js");
    expect(getSetting("theme")).toBe("light");
  });
  it("get/set/remove round-trip with a fallback", async () => {
    const { getSetting, setSetting } = await import("../../settings.js");
    expect(getSetting("panelsOpenByDefault", "x")).toBe("x");
    setSetting("panelsOpenByDefault", "0");
    expect(getSetting("panelsOpenByDefault")).toBe("0");
    setSetting("panelsOpenByDefault", null);
    expect(getSetting("panelsOpenByDefault")).toBeNull();
  });
  it("never touches verdict keys", async () => {
    localStorage.setItem("bi2m:verdicts:abc", "{}");
    await import("../../settings.js");
    expect(localStorage.getItem("bi2m:verdicts:abc")).toBe("{}");
  });
});
