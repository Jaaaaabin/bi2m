// ======== Persisted UI settings ========
// One namespace (`bi2m:`) for the small per-browser preferences this app
// keeps: theme, sidebar collapsed, panels open by default.
// Before this there were three prefixes (`ifcviewer-theme`,
// `ifcviewer-sidebar-collapsed`, `bi2m:panelsOpenByDefault`); the two legacy
// keys are migrated on first read so nobody loses a choice.
//
// Verdicts (`bi2m:verdicts:<fileKey>`, verdicts.js) are NOT settings and are
// deliberately not touched by this module - they are review data with their
// own store shape.

const PREFIX = "bi2m:";

const LEGACY = {
  "ifcviewer-theme": "theme",
  "ifcviewer-sidebar-collapsed": "sidebarCollapsed",
};

function migrateLegacyKeys() {
  try {
    for (const [oldKey, newKey] of Object.entries(LEGACY)) {
      const value = localStorage.getItem(oldKey);
      if (value === null) continue;
      if (localStorage.getItem(PREFIX + newKey) === null)
        localStorage.setItem(PREFIX + newKey, value);
      localStorage.removeItem(oldKey);
    }
  } catch {
    // Storage unavailable (private mode, blocked) - settings just don't persist.
  }
}

migrateLegacyKeys();

/** Raw string value, or `fallback` (default null) when unset/unavailable. */
export function getSetting(key, fallback = null) {
  try {
    const value = localStorage.getItem(PREFIX + key);
    return value === null ? fallback : value;
  } catch {
    return fallback;
  }
}

/** Stores a string; `null`/`undefined` removes the key. */
export function setSetting(key, value) {
  try {
    if (value === null || value === undefined) localStorage.removeItem(PREFIX + key);
    else localStorage.setItem(PREFIX + key, String(value));
  } catch {
    // ignore - see above
  }
}
