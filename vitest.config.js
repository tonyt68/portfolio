import { defineConfig } from "vitest/config";

// This repo's git root is ~/dev, which is also the parent directory of
// every other project on disk (a2a-trust-playground, aws-obo-permissions,
// etc. — see .gitignore). Vitest crawls recursively by default and will
// pick up every one of their test suites, most of which need config this
// project doesn't have. Scope discovery to just the site's own test file.
export default defineConfig({
  test: {
    include: ["tab-deep-link.test.js"],
  },
});
