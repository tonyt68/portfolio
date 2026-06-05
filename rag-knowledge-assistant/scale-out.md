# Scale-out Strategy

## Table of Contents
- [Current PoC](#current-poc)
- [Why flat files first](#why-flat-files-first)
- [The real meat: map/reduce + active learning](#the-real-meat-mapreduce--active-learning)
- [Token cost control](#token-cost-control)
- [Enterprise knowledge sources](#enterprise-knowledge-sources)
- [Where MCP comes in](#where-mcp-comes-in)
- [Future architecture](#future-architecture)
- [Validation & quality](#validation--quality)
- [Rollout path](#rollout-path)
- [Success criteria](#success-criteria)

## Current PoC
- storage: flat files in `/knowledge/`
- retrieval: keyword match against `knowledge.json` — checked first on every question
- LLM call: only made when knowledge base entries are found to ground the answer
- learning log: manual — answers Claude generates do not feed back automatically
- scope: one developer asking real questions at SDLC runtime

## Why flat files first
- fast to build and inspect
- easy to validate and trace
- `knowledge.json` acts as a cache — questions answered here cost zero tokens
- proves the architecture before adding complexity

## The real meat: map/reduce + active learning

MCP plumbing (SSE, stdio, streamable HTTP) is boilerplate — standards exist, implementation is straightforward. The hard problems are:

### 1. Map/reduce on source data
Raw source docs (Confluence pages, OpenAPI specs, GitHub files) are too large to send to Claude directly — you hit token limits and costs explode.

**Map:** chunk each source into meaningful pieces
- OpenAPI spec → one chunk per endpoint
- Confluence page → one chunk per section or heading
- GitHub file → one chunk per function or component

**Reduce:** at query time, retrieve only the chunks relevant to the question
- embed the question → find nearest chunks via vector search
- send only those chunks to Claude as context
- Claude never sees the full doc — only what's relevant

### 2. Active learning knowledge base
`knowledge.json` is not just seed data — it is a living cache of validated answers to real SDLC questions.

**The flywheel:**
```
Dev asks question at runtime
  → check knowledge.json first (zero tokens, instant)
  → cache hit: return answer directly, no LLM call
  → cache miss: retrieve relevant chunks via MCP sources
      → send chunks + question to Claude
      → Claude generates grounded answer
      → log Q&A pair to learning log
      → human review: is this answer good?
      → if yes: promote to knowledge.json
      → next dev asking same question hits the cache
```

Over time most questions hit the cache. LLM calls become the exception, not the rule. The knowledge base gets smarter from real usage — not manual curation.

### 3. Staleness detection
Cached answers go stale when source docs change. Need a strategy:
- tag each knowledge entry with its source and a timestamp
- when source changes (Confluence page updated, API spec bumped), flag dependent entries for re-validation
- don't serve stale answers silently — surface them for review

## Token cost control

Token costs are a real constraint. In high-usage AI deployments costs have been known to outpace developer salaries. The architecture is designed to keep costs in check at every layer:

| Strategy | How | Impact |
|---|---|---|
| **Knowledge cache first** | Check `knowledge.json` before any LLM call | Cache hit = zero tokens |
| **Chunk and reduce** | Only send relevant chunks, not full docs | Cuts context size by 80-90% |
| **Prompt caching** | Anthropic caches repeated system prompts | Reduces cost on repeated similar calls |
| **Model tiering** | Use Haiku for retrieval/classification, Sonnet for reasoning | Haiku is ~20x cheaper than Sonnet |
| **Cache promotion** | Validated answers never need a Claude call again | Cost amortized to zero over time |
| **Token budget per query** | Set `max_tokens` limits per call | Prevents runaway responses |
| **Running cost policy** | Configurable daily cap (`COST_DAILY_CAP_USD`) — warns at 80%, blocks at 100% | Hard ceiling on spend per environment |
| **Team/user quotas** | Track cost per user, alert before allocation is exhausted | Prevents one team burning shared budget |

**Rule of thumb:** a question answered from `knowledge.json` costs nothing. A question requiring a fresh Claude call costs ~1 cent. At scale, cache hit rate is the primary cost lever.

## Enterprise knowledge sources

| Source | What lives there | Priority |
|---|---|---|
| Confluence | architecture docs, runbooks, onboarding guides, process docs | High |
| Swagger / OpenAPI specs | API contracts, endpoint definitions, request/response shapes | High |
| GitHub / codebase | file names, component ownership, validation logic, recent changes | High |
| Support docs | known issues, escalation paths, customer-facing edge cases | Medium |
| Internal API responses | live service behavior, error codes, runtime data | Medium |
| Slack (select channels) | tribal knowledge, recent decisions, incident context | Low — noisy, use carefully |

## Where MCP comes in

MCP is the plumbing that connects Claude to live Enterprise sources at query time. Standards exist for transport (SSE, stdio, streamable HTTP) — implementation is straightforward.

Without MCP:
```
Question → search knowledge.json → Claude reasons over static entries → Answer
```

With MCP:
```
Question → cache miss → Claude calls MCP tools to fetch live chunks → Claude reasons → Answer → log → review → promote to cache
```

Each source becomes an MCP server:

| MCP server | Fetches from |
|---|---|
| `confluence-mcp` | Enterprise Confluence spaces |
| `openapi-mcp` | Swagger / OpenAPI specs for Luna, 1-800 Contacts, Framery |
| `github-mcp` | Codebase — files, components, recent changes |
| `support-mcp` | Support docs and known issue database |

Claude decides which tools to call based on the question. No hard-coded routing needed.

## Future architecture

| Phase | What | Cost profile |
|---|---|---|
| Phase 1 (now) | Flat JSON cache + Claude API | ~1 cent per question, all questions hit LLM |
| Phase 2 | Connect Confluence + OpenAPI via MCP | Real answers, still ~1 cent per cache miss |
| Phase 3 | Vector store for semantic chunk retrieval | Better retrieval, lower hallucination risk |
| Phase 4 | Active learning loop + review workflow | Cache hit rate climbs, cost drops over time |
| Phase 5 | Full RAG pipeline, team-wide | Most questions hit cache, LLM calls are exceptions |

## Validation & quality
- every answer tied to a named source with timestamp
- new entries promoted to cache only after human review
- MCP servers expose read-only access — no write, no side effects
- stale entries flagged when source docs change
- if Claude can't answer, it returns "here's where to look" — never hallucinate

## Rollout path
1. **Collect real SDLC questions** — what do Enterprise devs actually ask day-to-day?
2. **Map questions to sources** — which system holds each answer? (Confluence, OpenAPI, GitHub)
3. **Chunk the sources** — map large docs into retrieval-sized pieces by section, endpoint, or component
4. **Connect first MCP server** — Confluence or OpenAPI, whichever covers the most real questions
5. **Run active learning loop** — log every cache miss, review answers, promote good ones
6. **Add model tiering** — Haiku for classification and retrieval, Sonnet for final answer generation
7. **Expand sources and team** — only after cache hit rate proves quality and cost are under control

## Success criteria
- cache hit rate above 70% within 30 days of real usage (most questions answered at zero token cost)
- engineers stop asking "where is that documented?"
- answers are traceable to a named source
- token costs are predictable and declining as the cache matures
- the knowledge base grows from real usage, not manual curation
