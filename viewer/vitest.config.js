// Unit tests for the pure modules: no browser, no
// WebGL, no ThatOpen. Anything that needs a real viewer is an e2e harness in
// scripts/e2e/ instead. Run: npm run test:unit
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    include: ["tests/unit/**/*.test.js"],
    setupFiles: ["tests/unit/setup.js"],
  },
});
