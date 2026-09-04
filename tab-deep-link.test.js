import { describe, it, expect } from "vitest";
import { resolveTab, DEFAULT_TAB } from "./tab-deep-link.js";

const VALID_SLUGS = [
  "cat-payments",
  "cat-iam",
  "cat-zero-trust",
  "cat-agentic-rag",
  "cat-ietf",
  "cat-agentops",
  "cat-tools",
];

describe("resolveTab", () => {
  it("resolves a known tab from the ?tab= query param", () => {
    expect(resolveTab("?tab=cat-ietf", "", VALID_SLUGS)).toBe("cat-ietf");
  });

  it("falls back to the default tab for an unknown slug", () => {
    expect(resolveTab("?tab=not-a-real-tab", "", VALID_SLUGS)).toBe(DEFAULT_TAB);
  });
});
