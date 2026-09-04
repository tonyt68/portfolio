# phalanxaisec.com

Static site — PhalanxAI Security portfolio. Deployed via GitHub Pages behind Cloudflare.

## Tab deep-linking

The PoC grid supports linking directly to a tab via a URL parameter or hash, instead of always landing on the default (`cat-agentops`). Useful for outreach links pointed at a specific solution category.

**Usage:**

```
https://phalanxaisec.com/?tab=<slug>
https://phalanxaisec.com/#<slug>
```

Either form works; the hash form is a safer bet in some email clients that mangle query strings.

**Slugs:**

| Tab | Slug |
|---|---|
| Zero Trust Payments & HITL | `cat-payments` |
| IAM & Access | `cat-iam` |
| Zero Trust | `cat-zero-trust` |
| Agentic AI & RAG | `cat-agentic-rag` |
| IETF / Agent-to-Agent Trust | `cat-ietf` |
| Agent Governance & Autonomy | `cat-agentops` (default landing tab — no param needed) |
| Tools | `cat-tools` |

An unrecognized slug is silently ignored and the page falls back to the default tab — a malformed or stale link never breaks the page.

**Implementation:** `window.addEventListener("load", ...)` near the bottom of `index.html`, calling the existing `switchPocTab(slug)` function. No new switching logic — just reads the requested slug from `URLSearchParams` or `location.hash` and validates it against the real `.poc-tab-panel` ids before applying it.
