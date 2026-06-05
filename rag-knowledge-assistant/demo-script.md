# PoC Demo Script

## Table of Contents
- [Product name](#product-name)
- [Purpose](#purpose)
- [Before the demo](#before-the-demo)
- [Demo commands](#demo-commands)
- [Demo flow](#demo-flow)
- [What's scripted vs live](#whats-scripted-vs-live)

## Product name
**TonyAI Enterprise Assistant**
Powered by TonyAI · Built with Claude

## Purpose
Show a live internal developer assistant that answers domain-specific Enterprise questions with grounded, short summaries and source references.

## Prerequisites

1. Node 20+ required:
   ```bash
   node --version
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Create a `.env` file in the project root with your Anthropic API key:
   ```
   ANTHROPIC_API_KEY=your-key-here
   ```

4. Build the project:
   ```bash
   npm run build
   ```

## Before the demo

Open the demo command panel in your browser:
```
file:///Users/tonyai/dev/rag-knowledge-assistant/demo.html
```

Then reset the cost log:
```bash
npm run costs:reset
```

## Demo commands

**Question 1 — Luna returns latency**
```bash
npm run ask -- "I'm on the Luna returns team — what are the current order return steps and where can I reduce latency without breaking validation?"
```

**Question 2 — 1-800 Contacts ABC flow**
```bash
npm run ask -- "I need to extend the 1-800 Contacts web UI for ABC flow — which components own the form state and what are the existing UX/validation rules?"
```

**Question 3 — Salary guardrail (graceful decline)**
```bash
npm run ask -- "What does a Principal Software Engineer make at 1-800 Contacts?"
```

**Question 4 — Financial guardrail (free block, $0.00)**
```bash
npm run ask -- "What is Enterprise's private financial forecast?"
```

**Show cost dashboard**
```bash
npm run costs
```

## Demo flow

### 1. Introduce the tool
“This is a live Enterprise developer knowledge assistant built on RAG — it grounds every answer in real domain knowledge and calls Claude only when needed. Watch the cost at the end.”

### 2. Question 1 — Luna returns latency
Run the Question 1 command above.

Expected: numbered return flow, latency hotspot called out, specific file names, sources listed.

### 3. Question 2 — 1-800 Contacts ABC flow
Run the Question 2 command above.

Expected: component ownership, form state model named, no-Redux decision explained, sources listed.

### 4. Question 3 — Salary guardrail
Run the Question 3 command above.

Expected: graceful decline, points to HR and team lead, stays scoped to technical questions.

### 5. Question 4 — Financial forecast guardrail
Run the Question 4 command above.

Expected: instant hard block — “I’m not authorized to provide information on that topic.” No LLM call made.

### 6. Show cost dashboard
Run the costs command above.

Expected: 4 total calls, 3 LLM calls (~1 cent total), 1 free guardrail block on the financial forecast (shown as CACHE — $0.00). Point out: the salary question still hit Claude for a graceful decline, but the hard financial block cost nothing. As the knowledge base grows, more answers hit the cache and costs decline.

---

## What's scripted vs live

### Static / hand-written (seed data)

| What | File | Reality |
|---|---|---|
| Knowledge entries | `knowledge/knowledge.json` | 4 fake Q&A pairs — invented file names and service names |
| Restricted topics | `knowledge/restricted-topics.json` | Hand-written list of blocked keywords |
| Learning log | `learning-log.md` | Manually edited — nothing auto-populates it |
| Demo questions | This file | Written after the knowledge entries to guarantee a match |

### Live / real

| What | Reality |
|---|---|
| Claude reasoning | Real — LLM synthesizes answers from whatever context it receives |
| Restricted topic guardrail | Real — fires on any question matching blocked keywords |
| "No answer" fallback | Real — Claude honestly states when something isn't documented |
| Claude API call | Real — Anthropic Sonnet model, ~1 cent per run |

### The key gap
Demo questions were crafted to match the knowledge entries. A real Enterprise dev asking a random question would likely get "I don't have that documented yet" with only 4 entries. Replacing the seed data with even a few real Confluence pages or internal docs would make the assistant immediately useful.

---

## Related docs

- [Scale-out Strategy](scale-out.md) — map/reduce pipeline, active learning, MCP integration, token cost controls, and rollout phases
- [Learning Log](learning-log.md) — questions the assistant has learned from
