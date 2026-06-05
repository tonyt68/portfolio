# TonyAI Enterprise Assistant

## Table of Contents
- [Executive Summary](#executive-summary)
- [Getting Started](#getting-started)
- [Notes](#notes)
Powered by TonyAI · Built with Claude

## Executive Summary

### Problem
Enterprise engineers working across 1-800 Contacts, Luna, and Framery face domain knowledge gaps and high cognitive load. They often need to hunt through scattered docs or interrupt teammates to understand brand-specific workflows, UI ownership, and validation rules.

### Opportunity
A focused internal knowledge assistant can speed feature work and reduce overhead by answering real developer questions with grounded, validated answers. This is a strong way to demonstrate AI-enabled engineering adoption without overpromising.

### Solution
**TonyAI Enterprise Assistant** is a PoC knowledge base that:
- stores real developer questions and validated answers for the three brands
- returns short, accurate summaries instead of long, generic responses
- cites source context and suggests next steps
- grows organically as devs ask new questions
- records learning in a simple log

### Demo Focus
Real engineering questions:
- “I’m on the Luna returns team — what are the current order return steps and where can I reduce latency without breaking validation?”
- “I need to extend the 1-800 Contacts web UI for ABC flow — which components own the form state and what are the existing UX/validation rules?”

### Impact
- faster onboarding and cross-brand work
- reduced doc hunting and context-switching
- safer AI adoption with grounded responses and fallback behavior
- proven momentum for rollout strategy and engineering adoption

### What’s Next
1. build the PoC design doc
2. create the demo knowledge base
3. validate answers from Enterprise docs
4. share the artifact as a living repo and learning log
5. extend to a scale-out strategy

---

## Getting Started

1. Install dependencies:
   ```bash
   npm install
   ```
2. Build the project:
   ```bash
   npm run build
   ```
3. Run the tool with a question:
   ```bash
   npm run ask -- "How can I improve Luna return order processing?"
   ```

## How it works

```
Question
  → check knowledge.json first (zero tokens, instant)
  → cache hit: return answer, no LLM call
  → cache miss: retrieve relevant entries → Claude API → grounded answer
  → log Q&A → human review → promote to knowledge.json
```

The knowledge base is a living cache of validated SDLC answers. Over time, most questions hit the cache and cost nothing. LLM calls become the exception.

## Token cost strategy
- `knowledge.json` cache hit = zero tokens
- Only relevant chunks sent to Claude — not full docs
- Validated answers never need a Claude call again
- Target: 70%+ cache hit rate within 30 days of real usage

## Notes
- This PoC uses local flat-file knowledge for now — seed data only, no real Enterprise docs yet.
- The hard problems are map/reduce on source data and the active learning loop — not MCP plumbing.
- See `scale-out.md` for the full architecture and rollout path.
- `learning-log.md` tracks questions the PoC has learned from.
