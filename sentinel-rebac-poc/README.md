# Sentinel AI — ReBAC Security Governance POC

An agentic security response system for Identity Platform (IDP) teams. Sentinel detects threats, traverses a live ReBAC (Relationship-Based Access Control) graph to verify its own authorization, issues remediations, and logs every decision to an audit trail — autonomously, with no human in the loop.

---

## Table of Contents

- [What It Does](#what-it-does)
- [ReBAC Authorization Model](#rebac-authorization-model)
- [Architecture](#architecture)
- [Component Breakdown](#component-breakdown)
- [Agentic Flow](#agentic-flow)
- [The Revoked Access Scenario](#the-revoked-access-scenario)
- [Demo Flows](#demo-flows)
- [Setup](#setup)
- [Infrastructure](#infrastructure)
- [Production Scale (AWS)](#production-scale-aws)
- [Stack](#stack)

### Project Folders
- [skills/](skills/README.md) — reusable code patterns and techniques
- [knowledge/](knowledge/README.md) — concepts, notes, and study material
- [resources/](resources/README.md) — links, docs, references, cheat sheets
- [notes/](notes/README.md) — architecture plans, interview prep, decisions
- [resume/](resume/) — tailored resume and cover letter assets

---

## What It Does

When a security finding arrives (e.g. a crypto-mining process detected on an IDP node), Sentinel:

1. **Verifies authorization** — traverses the ReBAC graph to confirm it has the right to act
2. **Reasons** about the threat using Claude Opus 4.7
3. **Acts** — executes remediation and logs to the audit trail
4. **Escalates** — if the authorization chain is broken, it raises a CRITICAL incident instead of acting

The key insight: Sentinel doesn't just classify threats — it **checks its own authorization chain before every action**. A revoked relationship in the graph stops Sentinel cold, just like it would stop any human operator.

---

## ReBAC Authorization Model

Access is governed by **relationship chains**, not flat roles. Sentinel must find an unbroken path through the graph before it can act.

```
sentinel-agent  --delegate_of-->  tony
tony            --member_of-->    platform-team
platform-team   --can_remediate-> CryptoMining
```

**ALLOWED:** Full chain intact → Sentinel remediates the threat.

**DENIED:** Any link revoked (e.g. tony's membership removed) → chain breaks → CRITICAL escalation.

This models real-world service-to-service trust: an agent's authorization is only as strong as the relationship chain behind it.

---

## Architecture

```
┌──────────────────────┐
│   Security Finding   │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────────────┐
│  client.py                   │
│  Claude Opus 4.7             │
└──────────┬───────────────────┘
           │  stdio (MCP)
           ▼
┌──────────────────────────────┐
│  mcp_server.py               │
│  MCP Server (3 tools)        │
└───────┬──────────┬───────────┘
        │          │            │
        ▼          ▼            ▼
┌──────────────┐ ┌───────────┐ ┌────────────────┐
│    Redis     │ │  MailHog  │ │  webhook.site  │
│  ReBAC Graph │ │  Audit    │ │  Live Alerts   │
└──────┬───────┘ └───────────┘ └────────────────┘
       │ ALLOWED / DENIED
       └──────────────────┐
                          ▼
               ┌─────────────────────┐
               │  Terminal Output    │
               │  Verdict + Chain   │
               └─────────────────────┘
```

---

## Component Breakdown

### `client.py` — The AI Agent
Uses the **Anthropic SDK** with Claude Opus 4.7 and the **MCP tool runner**. Spawns the MCP server as a subprocess over stdio, then drives an agentic loop:
- Adaptive thinking (`display: summarized`) so reasoning is visible
- System prompt is **prompt-cached** — second run onwards gets a cache hit, reducing token cost
- Claude must check ReBAC authorization before any remediation action

### `mcp_server.py` — The MCP Server
A [Model Context Protocol](https://modelcontextprotocol.io) server exposing three tools to Claude:

| Tool | What it does |
|------|-------------|
| `check_rebac_permission` | Traverses the Redis ReBAC graph to find an authorization chain |
| `send_audit_email` | Sends a structured audit report to the security team via SMTP |
| `send_alert_webhook` | POSTs a live JSON alert to webhook.site for real-time visibility |

### Redis — The ReBAC Graph Store
Stores relationship tuples as Redis Sets:

| Key | Value | Meaning |
|-----|-------|---------|
| `rebac:sentinel-agent:delegate_of` | `tony` | Sentinel acts on behalf of Tony |
| `rebac:tony:member_of` | `platform-team` | Tony is a member of platform-team |
| `rebac:platform-team:can_remediate` | `CryptoMining, Ransomware` | Team has remediation rights |

The `_check_rebac()` function in `mcp_server.py` traverses these sets recursively using BFS to find an authorization chain from subject → action → resource.

### MailHog — Audit Trail
Captures all outbound audit emails locally. Accessible via option **6** (Status Check).

### webhook.site — Live Alerts
Every finding fires a JSON POST visible in real-time in the browser:

```bash
export SENTINEL_WEBHOOK_URL="https://webhook.site/your-unique-id"
```

---

## Agentic Flow

```
Finding       Claude            MCP Server        Redis         Audit    Webhook
   │              │                  │               │             │        │
   │─ CryptoMining ────────────────▶│               │             │        │
   │              │─ check_rebac_permission ────────▶│             │        │
   │              │                  │◀── ALLOWED ───│             │        │
   │              │◀─ Chain: agent→tony→team→threat ─│             │        │
   │              │─ send_audit_email ──────────────────────────▶│        │
   │              │─ send_alert_webhook ───────────────────────────────▶│
   │◀─ Verdict: QUARANTINE, chain verified ──────────│             │        │
```

---

## The Revoked Access Scenario

```
Admin         Redis Graph      Claude            Audit Trail
   │               │               │                  │
   │─ REVOKE tony's membership ───▶│                  │
   │               │ [chain broken] │                  │
   │               │─ REBAC_DENIED ──────────────────▶│
   │               │               │─ CRITICAL: Auth chain broken ──▶│
   │◀──────────────│── ESCALATE: no authorization path found ─────────│
```

Sentinel detects when its own authorization has been revoked and escalates — it never bypasses the check or acts without a valid chain.

---

## Demo Flows

### ALLOWED Flow
```
1 → Start & seed ReBAC graph
2 → Run Sentinel  →  REBAC_ALLOWED ✅  →  threat remediated
5 → Verify graph  →  chain INTACT 🟢
```

### DENIED Flow
```
1 → Start & seed ReBAC graph
2 → Run Sentinel  →  REBAC_ALLOWED ✅
3 → Revoke Tony's membership
2 → Run Sentinel  →  REBAC_DENIED 🔴  →  CRITICAL escalation
4 → Restore Tony's membership
2 → Run Sentinel  →  REBAC_ALLOWED ✅  →  threat remediated
```

---

## Setup

```bash
# Prerequisites: Docker Desktop running, Minikube, kubectl, ANTHROPIC_API_KEY set

# Install Python dependencies
source venv/bin/activate && pip install "anthropic[mcp]"

# Optional: live webhook alerts (get your URL from webhook.site)
export SENTINEL_WEBHOOK_URL="https://webhook.site/your-unique-id"

# Run the demo menu
bash sentinel.sh
```

---

## Infrastructure

All backend services run locally inside a Minikube single-node Kubernetes cluster.

```
Minikube (Docker driver)
└── Kubernetes cluster
    ├── Deployment: redis        (image: redis:alpine)
    │   └── Service: redis-service   port 6379
    │       └── kubectl port-forward → localhost:6379
    │           └── ReBAC Graph Store (relationship tuples as Redis Sets)
    │
    └── Deployment: mailhog      (image: mailhog/mailhog:latest)
        └── Service: mail-service
            ├── port 1025 (SMTP)  → localhost:1025  (audit email ingestion)
            └── port 8025 (HTTP)  → localhost:8025  (web UI for audit review)
```

---

## Production Scale (AWS)

This POC runs locally on Minikube with Redis as the graph store. Here is the v2 production mapping.

```
POC (v1 — Minikube / Redis)          Production (v2 — AWS)
───────────────────────────────────  ────────────────────────────────────────────
Redis ReBAC graph (Sets)          →  Amazon Neptune (property graph, Gremlin)
_check_rebac() Python traversal   →  Neptune Gremlin queries + Lambda Authorizer
MCP check_rebac_permission tool   →  Lambda → Amazon Verified Permissions (Cedar)
Minikube single-node cluster      →  Amazon EKS (multi-AZ, managed node groups)
MailHog (local SMTP sink)         →  Amazon SES + S3 (audit archival)
webhook.site (manual HTTP sink)   →  Amazon EventBridge → Lambda fan-out
stdio MCP transport               →  MCP over SSE/HTTP (containerized EKS pod)
python client.py (local script)   →  EKS Deployment behind SQS trigger queue
ANTHROPIC_API_KEY env var         →  AWS Secrets Manager + IRSA (pod IAM role)
Manual revoke demo                →  AWS Config Rule + Lambda auto-remediation
```

**ReBAC at Scale (Neptune + Verified Permissions)**
Neptune stores entity relationships as a property graph. A Lambda authorizer queries Neptune via Gremlin to resolve the full relationship chain for any principal, then passes the resolved entities into Amazon Verified Permissions for a Cedar policy decision (`permit` / `forbid`). Decision results are cached with short TTL to address graph traversal latency at scale.

**Why not a managed ReBAC vendor?**
Cedar is open source (donated by AWS to the community). Neptune is swappable for any graph DB. The Lambda authorizer is your own code. No vendor lock-in — same architecture, open standards.

---

## Stack

| Layer | Technology |
|-------|-----------|
| AI Model | Claude Opus 4.7 (Anthropic) |
| Agent Protocol | Model Context Protocol (MCP) over stdio |
| Authorization Model | ReBAC — Relationship-Based Access Control |
| Graph Store | Redis Sets (v1) → Amazon Neptune (v2) |
| Policy Engine | Python BFS traversal (v1) → Amazon Verified Permissions / Cedar (v2) |
| Audit Trail | MailHog (v1) → Amazon SES + S3 (v2) |
| Live Alerts | webhook.site (v1) → Amazon EventBridge (v2) |
| Orchestration | Minikube + kubectl (v1) → Amazon EKS (v2) |
| IaC | — (v1) → CloudFormation (v2) |
| Runtime | Python 3.10+ |

---

## Built By

Powered by **TonyAI** — architecture, vision, ReBAC design, and AWS domain expertise.
Assisted by **Claude** — code generation and implementation.
