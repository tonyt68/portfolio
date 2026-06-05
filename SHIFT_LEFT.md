# Shift-Left AI Engineering — HIPAA Bedrock PoC

> **TODO:** Build a CR skill for shift-left code review — runs on branch/working tree
> before PR is created. Security-focused, Zero Trust aware, OWASP-mapped.
> Evaluate existing skills first (Claude Code `/review`, `/ultrareview` multi-agent,
> community CR skills) before building from scratch. Goal: combine built-in CR skills
> with a custom Zero Trust / OWASP / HIPAA-aware skill — both working together.
> Pick up during Bedrock PoC deep dive.

Shift-left means catching problems early — before they reach production, before
they reach a user, before they reach an auditor. The same discipline applied to
code quality and security testing applies to AI systems. This document maps every
shift-left practice built into this PoC.

---

## 1. Prompt Evaluation Before Code

System prompts are tested before they go into `bedrock_agent.py`.

**What we test:**
- Scope limiting — off-topic prompts are declined before hitting the LLM
- Tool steering — `get_patient_records` is called consistently for valid physician requests
- Edge cases — ambiguous inputs, social engineering attempts, non-physician identities

**Why:** A prompt regression in a HIPAA system is a compliance event, not just a bug.
Catch it in eval, not in a demo or an audit.

```
Draft prompt → eval test suite → all assertions pass → merged into _SYSTEM
```

---

## 2. Prompt Guardrails (Input Safety Scan)

User input is scanned before it reaches the LLM — AWS Bedrock Guardrails or a
pre-flight eval gate sits in front of `converse_stream`.

```
User input → safety scan → PASS → LLM → tool call → Zero Trust
                         → FAIL → rejected, LLM never invoked
```

**Why:** Defense in depth. Even if a malicious prompt bypasses the guardrail,
Zero Trust enforcement fires downstream regardless. Every layer fails safe.

---

## 3. Scope-Limited System Prompt

The system prompt explicitly constrains Claude to hospital operations only.
Off-topic requests are declined at the model layer before any tool is invoked.

```python
"Only respond to requests related to patient records and hospital operations. "
"Politely decline any questions outside that scope."
```

**Why:** Reduces attack surface. A hospital AI assistant that answers car repair
questions is a prompt injection vector waiting to be exploited.

---

## 4. Tool Steering — No Ambiguity

Claude is told exactly which tool to call and when — no autonomous tool selection.

```python
"Use the get_patient_records tool when a physician requests patient information."
```

**Why:** Deterministic tool invocation is auditable. For HIPAA, every PHI access
must be traceable to an explicit, intentional tool call — not an LLM judgment call.

---

## 5. Temperature 0 — Deterministic Behavior

```python
inferenceConfig={"temperature": 0, "maxTokens": 512}
```

**Why:** Medical records retrieval must be consistent and predictable. Temperature 0
ensures the same input produces the same tool call every time — testable, auditable,
no creative variation in a PHI access path.

---

## 6. Zero Trust as the Safety Net

The LLM cannot grant access. Even if Claude's response says "here are the records,"
the enforcement stack decides:

```
JWT validation → ReBAC check → Vault PKI cert → PostgreSQL cert auth
```

**Why:** Prompt injection cannot escalate privilege. The model is the interface,
not the gatekeeper. Unauthorized access is impossible regardless of what the prompt says.

---

## 7. Structured Tool Parameters — No Free-Form Passthrough

Tool inputs are typed and validated — no raw string from user input reaches the
database or the enforcement stack.

```python
"required": ["requesting_physician_id"]
"type": "string"
```

**Why:** OWASP A03 — Injection. Free-form text from agent input to DB query is a
SQL injection vector. Typed parameters close that path entirely.

---

## 8. Audit Trail on Every Request

Every request — ALLOWED or DENIED — is logged with identity, resource, scope,
outcome, and timestamp. The audit log is written before the response returns.

**Why:** HIPAA requires an audit trail for every PHI access attempt. "We think it
was denied" is not a compliant answer. The log is the proof.

---

## 9. AI-Assisted Code Review — Shift-Left CR

**Shift-left CR means the AI reviews on the branch or working tree — before the
PR is created.** Not after. By the time the PR exists, issues are already found
and fixed.

```
working tree → AI CR skill → issues flagged → fixed → commit → PR created → human review
```

NOT this:
```
working tree → commit → PR created → AI CR → human review  ← not shift-left
```

The AI reviewer checks for security patterns, OWASP violations, prompt injection
vectors, and code quality — with full context of the codebase and the Zero Trust
enforcement model. Human reviewers see clean, pre-screened code and focus on
architecture and intent rather than finding basic issues.

**Why:** Same principle as linters and security scanners in CI — catch it earlier,
fix it cheaper. AI CR adds LLM-level understanding of context and security intent
that static analysis misses. Running it post-PR is useful but it is not shift-left.

---

## 10. AI-Generated Tests + Security Scanning on Branch

All on the branch, before the PR exists:

```
Code written → AI generates tests (directed by engineer)
             → run tests → AI debugs failures
             → security scan (Snyk, Bandit, OWASP)
             → code coverage gate (JaCoCo, Jest)
             → all green → PR created → human reviews clean, tested, scanned code
```

**The engineer directs, the AI does the volume work:**
- "Give me happy path, server error paths, and three corner cases"
- "Cover the JWT validation and ReBAC check paths"
- "Ensure 80% coverage on the enforcement stack"

AI generates the test suite, engineer reviews and validates. Same rigor, 3x the
coverage velocity. Security scanners and coverage tools run on the same branch
pass — nothing reaches PR that hasn't been tested and scanned.

**Debugging AI-generated tests — three outcomes:**

```
Test fails → bad test (AI error)     → fix the test, rerun
           → real bug (code error)   → fix the code, rerun
Test passes → verify code logic      → test is documentation of intent
```

Debugging with AI identifies which failure mode it is. Either way you win — a
corrected test or a caught bug, both found on the branch before any human sees
the code. Even passing tests have value: reading them verifies the code logic is
doing what was intended. If the test says one thing and the code does another,
something is wrong even when it passes.

**Why:** Bugs, security findings, and coverage gaps are caught and fixed before
any human reviewer touches the code. Human review focuses on architecture and
intent — not finding what the toolchain already caught.

---

## 11. Small Branch + Small Context Window Strategy

One small task per branch, one chat session per branch — even one session per commit
for independent tasks:

```
small task → new branch → new chat session → small focused context
→ AI writes focused code → review → test → commit → done
→ next task → new branch → new session → repeat
```

**Why this wins:**
- Small context = better AI output, less hallucination, more focused responses
- Small branch = easy rollback, minimal blast radius if approach fails
- One session per task = no context pollution between unrelated features
- Parallel branches = multitask efficiently across independent tasks simultaneously
- Rollback = throw away one small branch, not weeks of tangled work

This is YAGNI + shift-left + risk management at the code level. Each commit is
small, tested, reviewed, and independently reversible.

---

## 12. Sub-Task Decomposition — AI as Force Multiplier

Large features are never handed to AI in one shot. Break the feature into focused
sub-tasks, one clear prompt per sub-task, review each piece, then assemble.

```
Large feature → sub-tasks → one focused AI prompt per task → review → assemble
```

Smaller, focused context produces better AI output. The engineer directs like a
senior dev directing a junior — one clear task at a time, review at each step,
move to the next only when it's right.

This is the discipline behind a 0.04% escaped defect rate. Problems are caught
at the sub-task level, not after the whole feature is assembled and tangled
together. AI as a force multiplier only works when the engineer is in control
of every step.

---

## 13. Claude Code Hooks — Automated Shift-Left Enforcement

Claude Code hooks fire shell commands automatically in response to events — no manual trigger required. This is shift-left enforcement built into the AI coding loop itself.

```
Claude edits a file → PostToolUse hook fires automatically
                    → linter / syntax check
                    → unit tests
                    → security scan (Bandit, Snyk, OWASP)
                    → code review skill
                    → results fed back to Claude → self-correct before you see the code
```

**Hook events available:**
- `PreToolUse` — fires before Claude calls a tool (Read, Edit, Bash, etc.) — block dangerous actions before they happen
- `PostToolUse` — fires after Claude edits a file — run linter, tests, security scan immediately
- `Stop` — fires when Claude finishes a turn — run full test suite, coverage check, final security scan

**Example hooks to configure:**
- After any file edit → run `bandit` (Python security scan) or `eslint` (JS syntax)
- After any file edit → run unit tests for the changed module
- After any Bash command → log what was run (audit your own AI assistant)
- Before any file edit → block writes to `.env`, `*.pem`, `*.key` (defense in depth on top of `.claudeignore`)
- On stop → run `/code-review` or `/security-review` skill automatically

**Why:** The AI catches its own mistakes before you review. Linter errors, test failures, and security findings are resolved in the same turn — not in a follow-up prompt. The engineer reviews code that has already passed automated gates, same as CI but local and instant.

Configure in: `Claude Code Settings → Hooks`

---

## Summary — Shift-Left Stack

| # | Practice | Catches |
|---|----------|---------|
| 1 | Prompt eval before code | Prompt regressions |
| 2 | Input guardrail (Bedrock Guardrails) | Malicious / off-topic prompts |
| 3 | Scope-limited system prompt | Off-topic requests at model layer |
| 4 | Tool steering | Ambiguous or unintended tool selection |
| 5 | Temperature 0 | Non-deterministic tool calls |
| 6 | Zero Trust downstream enforcement | Anything the LLM misses |
| 7 | Structured typed tool parameters | Injection attacks |
| 8 | Audit trail on every request | Untracked PHI access |
| 9 | AI CR on branch before PR | Security issues, code quality |
| 10 | AI-generated tests + security scan on branch | Bugs, coverage gaps, OWASP violations |
| 11 | Small branch + small context window | Context drift, large blast radius |
| 12 | Sub-task decomposition | Hallucination, loss of focus, integration bugs |
| 13 | Claude Code hooks (PostToolUse/Stop) | Linter errors, test failures, security findings — caught in same turn |

Every layer catches what the layer above might miss. The LLM is the first line,
Zero Trust is the last line, audit log is the receipt.

---

## Preventing Rogue Agents

Most agent hacks exploit the same gaps. Here's what closes them:

| Gap | How We Close It |
|-----|----------------|
| No scope limiting | System prompt constrains to hospital operations only |
| Free-form text to DB/shell | Typed structured tool parameters — no raw passthrough |
| Agent pushes instructions to LLM | One direction only — LLM decides, agent executes, never reversed |
| Unknown tool executed anyway | `_execute_tool` default deny — unknown tool returns error, nothing runs |
| LLM decision is the only access control | Zero Trust enforces downstream regardless of what LLM says |
| No audit trail | Every request logged ALLOWED or DENIED before response returns |
| Non-deterministic tool selection | Temperature 0 — same input, same tool call, every time |
| Prompt injection escalates privilege | JWT is system-signed, not derived from user input — injection cannot grant access |

**The principle:** The LLM is the interface, not the gatekeeper. Every layer
below it enforces independently. A rogue or compromised LLM cannot bypass
Zero Trust, cannot forge a JWT, cannot skip the audit log.
