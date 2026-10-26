// ESLint flat config. Recommended rules only, plus
// the few adjustments the existing code style needs. Run: npm run lint
import js from "@eslint/js";
import globals from "globals";

export default [
  {
    ignores: [
      "dist/**",
      "node_modules/**",
      "public/**",
      "scripts/e2e/**",
      "tests/unit/out/**",
    ],
  },
  js.configs.recommended,
  {
    files: ["**/*.js", "**/*.mjs", "**/*.jsx"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      parserOptions: { ecmaFeatures: { jsx: true } },
      globals: { ...globals.browser, ...globals.es2021 },
    },
    rules: {
      // `_`-prefixed and destructured-away names are deliberate here.
      "no-unused-vars": [
        "warn",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_", caughtErrors: "none" },
      ],
      // Empty catch blocks are used on purpose for storage/network fallbacks.
      "no-empty": ["error", { allowEmptyCatch: true }],
    },
  },
  {
    files: [
      "vite.config.js",
      "server/**/*.mjs",
      "scripts/**/*.mjs",
      "vitest.config.js",
      "eslint.config.js",
    ],
    languageOptions: { globals: { ...globals.node } },
  },
  {
    files: ["inspector/*.worker.js"],
    languageOptions: { globals: { ...globals.worker } },
  },
  {
    files: ["tests/unit/**/*.js"],
    languageOptions: { globals: { ...globals.node, ...globals.browser } },
  },
];
