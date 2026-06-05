# CLAUDE.md — Sentinel FIPS

Session primer for any Claude Code instance opening this directory.

## Status: v1 LOCKED

v1 = current state on disk. **Bug fixes only** in code and docs. No scope expansion, no new features, no refactors. If Tony asks for something that smells like scope creep, push back and ask whether it should land in v2 instead.

## Tagline (Tony's, verbatim)

> TonyAI + Claude === rock solid / safe / secure / haste

Four pillars. Every doc and code change should defend at least one of them. AI-GOVERNANCE.md maps artifacts → pillars.

## Where things live

- **Document index**: see [README.md](README.md) "Document Index" section — points at SETUP.md, DEMO.md, FIPS-140-3.md, TRADEOFFS.md, AI-GOVERNANCE.md.
- **Code**: [functions/orchestrator/](functions/orchestrator/), [functions/authorizer/](functions/authorizer/), [functions/sign/](functions/sign/), [template.yaml](template.yaml).
- **Auto-memory** (persists across sessions): `/Users/tonyai/.claude/projects/-Users-tonyai-dev-sentinel-fips/memory/MEMORY.md` — read it before assuming anything about Tony, the project, or how he wants to work.

## Working agreements (load-bearing)

- **Verify by doing.** No AI hype, no hand-waving. Every claim must be empirically demonstrable. Both reputations are on the line.
- **High-level first, then depth.** Orient on flow/architecture before drilling in.
- **Stealth mode.** This work is confidential IP. Never suggest public sharing without explicit ask.
- **Cost-conscious.** Tony funds this personally. Default to smallest thing that works. Mention $-cost on non-trivial changes.
- **Docs as interview receipts.** Structured, citation-rich, speakable cold.

## Context behind the work

This POC is portfolio armor for a NetDocs rematch (Tony got hit hardest on tradeoffs in the prior interview). Calibrate prep accordingly — TRADEOFFS.md is a priority artifact, not decoration.

## When opening a fresh session

1. Read this file.
2. Read MEMORY.md (auto-loaded).
3. Read README.md → confirm v1 status hasn't changed.
4. Then take the task.
