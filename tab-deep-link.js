/**
 * Deep-link tab resolution — the single source of truth for which tab a
 * page load lands on, whether from a shared link or the bare URL.
 *
 * The query param (?tab=slug) is checked first, then the hash (#slug) — a
 * shared link still works in mail clients that strip query strings. An
 * unrecognized or absent slug resolves to DEFAULT_TAB: a malformed or
 * stale link is never worse than the plain root URL, and the page markup
 * carries no hardcoded "active" tab of its own — this function is the only
 * place default-tab selection is decided.
 */

export const DEFAULT_TAB = "cat-agentops";

export function resolveTab(search, hash, validSlugs) {
  const fromQuery = new URLSearchParams(search).get("tab");
  const fromHash = (hash || "").replace(/^#/, "");
  const requested = fromQuery || fromHash;
  return requested && validSlugs.includes(requested) ? requested : DEFAULT_TAB;
}

if (typeof window !== "undefined") {
  window.resolveTab = resolveTab;
  window.DEFAULT_TAB = DEFAULT_TAB;
}
