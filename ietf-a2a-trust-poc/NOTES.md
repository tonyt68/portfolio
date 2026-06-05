# A2A Trust Enforcement PoC
## First public implementation of draft-tonyai-a2a-trust-00

**Goal:** Two Claude agents that must authenticate to each other before exchanging data — JWT chain + HMAC + audit trail. IETF draft made real.

**Timeline:** ~1 week (complete Vertex AI course first, then build)

---

## AI-Partnered Design: Reference Implementation Architecture & Design Specification for IETF A2A Trust Draft

**Principle:** Reason about architecture, security, services, and implementation **before writing 1 line of code.**

This document is the **design phase** — comprehensive thinking on:
- Service architecture (MCP, Admin Bootstrap, Demo web)
- Security model (fail-closed, scope constraints, federated audit)
- Technology decisions with trade-offs (Cedar vs Redis, Docker vs K8s, ngrok vs AWS)
- 11 demo scenarios with acceptance criteria
- 7-phase implementation plan
- Infrastructure-as-code (Terraform, Docker Compose)
- Deployment strategy (local dev → public)

**Result:** When Phase 1 begins, the blueprint is complete. Build with confidence, no mid-stream architecture rework.

---

## Why This PoC Is Rare

- No public working implementation of A2A trust standards exists yet
- Tony authored the IETF Internet-Draft — this is the canonical reference implementation
- Most agent frameworks assume agents trust each other by default — this inverts that assumption
- Direct proof point for every AI security / AI platform job application

---

## Architecture Plan

### Agents
- **Agent A (Requester):** Initiates a request to Agent B for data/action
- **Agent B (Responder):** Validates Agent A's identity before responding

### Trust Stack (per draft-tonyai-a2a-trust-00)
1. **mTLS** — mutual TLS between agents (self-signed certs for PoC/testing)
2. **JWT Chain** — Agent A presents a signed JWT; Agent B validates issuer, audience, expiry
3. **HMAC** — message integrity check on every payload exchange
4. **Cedar (Policy as Code)** — Agent A's scopes and spawn rules evaluated against Cedar policies before any action is permitted
5. **Audit Trail** — every request logged: agent identity, action, ALLOWED or DENIED

### Self-Signed Certs (Testing)
- Use OpenSSL to generate CA + agent certs for local mTLS testing
- Perfectly valid for PoC — documents the pattern even if not prod CA
- Note in README: "replace with HashiCorp Vault PKI or AWS ACM for production"

---

## Tech Stack (tentative)
- Python + FastAPI (Agent A and Agent B as separate services)
- **GCP Vertex AI** (Claude as the reasoning engine — ties to Vertex AI course)
- **Vertex AI SDK for Python** (`google-cloud-aiplatform`) — the GCP SDK used to call Claude via Vertex AI
- JWT RS256 (asymmetric signing)
- HMAC-SHA256 (message integrity)
- **Cedar SDK (local, Python)** — policy as code, replaces Redis ReBAC entirely
- **CloudWatch Logs** (primary tamper-evident audit log — outside agent ecosystem, KMS encrypted, hash-chained entries)
- **DynamoDB** — Template Registry (agent cert metadata, state: ACTIVE/DISABLED/DELETED)
- PostgreSQL — optional local mirror for dev/debug only; CloudWatch is the authoritative audit store
- Docker Compose (local multi-agent environment)
- OpenSSL / Python `cryptography` lib (self-managed CA + agent certs for mTLS)
- MCP (agent-to-agent communication protocol)
- **GitHub (private repo)** — private for now, make public when ready for IETF submission. Required for IETF reference implementation link.
- **Cedar (Policy as Code)** — use Cedar SDK (local, Python) as the policy engine. Replaces Redis ReBAC BFS. Every spawn rule, scope constraint, and cross-org grant is a Cedar policy file — versioned, testable, auditable, human-readable. Maps directly to the IETF draft's dynamic policy lane. Cedar SDK is free, runs in-process, no AWS dependency. Same Cedar language as Amazon Verified Permissions — hiring managers recognize it. Drop Redis ReBAC for this PoC.
- **Terraform (IaC for everything)** — use Terraform for all AWS and GCP infrastructure provisioning. No manual console clicks. Covers both clouds from one IaC layer.
- **Google Cloud Logging** — captures Vertex AI agent calls natively. Free tier covers PoC volume. Adds GCP observability to resume.
- **AWS CloudWatch** — audit trail side (dual-write with PostgreSQL, same pattern as existing PoCs).
- **Federated Audit:** Google Cloud Logging (GCP/Vertex AI side) + CloudWatch (AWS side) = two independent audit trails per org. Proves the IETF draft federated audit requirement — each org's records are independent.
- **Correlation ID (UUID v7)** — ONE correlation ID per demo scenario lifecycle. Traces the full request across Agent A → mTLS → Agent B → ReBAC → audit → both cloud logs. Every layer stamps the same ID. Full end-to-end traceability from first byte to final audit record.

### Python Dependencies (requirements.txt)

**Core (all services):**
```
fastapi==0.109.0
uvicorn==0.27.0
pydantic==2.5.0
python-dotenv==1.0.0
pyjwt==2.8.1
cryptography==41.0.7
requests==2.31.0
```

**AWS/GCP:**
```
boto3==1.34.0  # AWS SDK
google-cloud-aiplatform==1.40.0  # Vertex AI Claude calls
google-cloud-logging==3.8.0  # Google Cloud Logging
```

**Policy Engine:**
```
cedar-py==0.1.0  # Cedar SDK (policy as code)
```

**Security/Crypto:**
```
pycryptodome==3.19.0  # Additional crypto operations
pyopenssl==23.3.0  # OpenSSL wrapper for cert generation
```

**Local Development:**
```
pytest==7.4.3  # Testing
pytest-asyncio==0.21.1  # Async test support
docker-compose==1.29.2  # Local orchestration (optional, if not using Docker CLI)
```

---

## High-Level Build Plan

### Phase 1 — Foundation (Day 1-2)
- Set up Docker Compose with Agent A and Agent B as separate FastAPI services
- Generate self-signed CA + agent certs with OpenSSL (mTLS)
- Set up DynamoDB local + CloudWatch logging (audit trail authoritative store)
- Initialize Cedar SDK + write first policy files (agent identity, allowed scopes)
- Verify agents can talk to each other over mTLS — no auth yet, just connectivity
- Create private GitHub repo: tonyai/a2a-trust-poc

### Phase 2 — Identity Layer (Day 3)
- Implement JWT RS256 issuer — Agent A requests a token from a lightweight token service
- Agent B validates JWT: issuer, audience, expiry, signature
- Hard reject any request without a valid JWT — fail closed
- Write first audit log entry: agent ID, action, JWT claims, ALLOWED or DENIED

### Phase 3 — Message Integrity (Day 4)
- Add HMAC-SHA256 to every request payload
- Agent B verifies HMAC before processing — tampered payload = rejected
- Audit log records HMAC verification result

### Phase 4 — Cedar Policy Enforcement (Day 5)
- Write Cedar policies: spawn rules, scope constraints, cross-org grant structure
- Agent B evaluates Cedar policy after JWT validation — authorization is a separate check from authentication
- Update a Cedar policy file → enforcement changes immediately — demo the revocation story
- All policy files versioned in GitHub — auditable change history

### Phase 5 — Claude Integration + Demo Script (Day 6)
- Wire Claude via Vertex AI SDK (`google-cloud-aiplatform`) as the reasoning engine inside each agent
- Agent A invokes Claude to formulate a request; Agent B invokes Claude to process the response
- Build a simple demo script: authorized request → allowed; unauthorized → denied; tampered payload → rejected
- Show audit trail for all three scenarios

### Phase 6 — Polish + Demo Startup (Day 7)
- Write README: what this is, why it matters, how to run it, production notes (Vault PKI, AWS ACM)
- Create `demo/start.sh` — starts MCP server + Admin Bootstrap + Demo web service, opens browser to prep.html
  - Pattern: reuse from `/Users/tonyai/dev/last-mile-zero-trust/secure-rag-zero-trust-demo/demo/start.sh`
  - Activates venv, starts Docker Compose, opens http://localhost:8765 (A2A PoC demo port)
- All 11 demo scenarios working end-to-end
- Audit trail verified: hash chain unbroken, correlationId traces across both clouds

### Phase 7 — Code Hardening / SOLID Review (before going public)
- Full SOLID review pass — every class has one reason to change, dependencies injected, no hidden coupling
- Red team / hacker pass — prompt injection, scope escalation edge cases, replay attack hardening
- No dead code, no debug backdoors, no hardcoded values
- All secrets in `.env`, all infra in Terraform, no manual console state
- Code must reflect the TonyAI brand — clean, production-quality, no shortcuts visible
- Peer review checklist before flipping repo public

---

## Service Architecture & Directory Structure

```
a2a-trust-poc/
├── services/
│   ├── mcp_server/                    # MCP tools for agents (public interface)
│   │   ├── main.py                    # FastAPI app + MCP endpoint
│   │   ├── jwt_validator.py           # JWT RS256 validation
│   │   ├── hmac_verifier.py           # HMAC-SHA256 message integrity
│   │   ├── cedar_policy_eval.py       # Cedar policy evaluation engine
│   │   ├── s3_tools.py                # write_event_to_s3, read_event_from_s3 tools
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── __init__.py
│   │
│   ├── admin_bootstrap/               # Admin-only service (locked down)
│   │   ├── main.py                    # FastAPI app for admin endpoints (mTLS + API key)
│   │   ├── cert_generator.py          # Agent cert generation (OpenSSL, cryptography lib)
│   │   ├── cert_manager.py            # DynamoDB Template Registry CRUD
│   │   ├── policy_authority.py        # Dual-sig validation (Owner + PA)
│   │   ├── crl_manager.py             # Certificate Revocation List updates
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── __init__.py
│   │
│   └── cert_authority/                # CA library (imported by admin_bootstrap)
│       ├── ca.py                      # Self-managed CA (OpenSSL wrapper for PoC)
│       └── __init__.py
│
├── demo/
│   ├── start.sh                       # Start demo: starts both services + opens browser
│   ├── prep.html                      # Architecture + context (same pattern as flagship RAG PoC)
│   ├── demo.html                      # 11 runnable scenarios + live audit table
│   ├── app.py                         # Demo backend (FastAPI, orchestrates scenarios)
│   ├── scenario_runner.py             # Scenario execution logic
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css              # Styling (reuse from flagship RAG PoC)
│   │   └── js/
│   │       └── app.js                 # Frontend logic (audit table, scenario buttons)
│   └── requirements.txt
│
├── terraform/
│   ├── main.tf                        # AWS + GCP provider setup
│   ├── s3.tf                          # S3 bucket (events storage)
│   ├── dynamodb.tf                    # DynamoDB (Template Registry)
│   ├── cloudwatch.tf                  # CloudWatch Logs (audit trail)
│   ├── gcp_logging.tf                 # Google Cloud Logging (audit trail)
│   ├── iam.tf                         # IAM roles/policies (scoped access)
│   └── outputs.tf
│
├── docker-compose.yml                 # Starts: mcp_server + admin_bootstrap + demo web service
├── .env.example                       # Template (no values)
├── .env                               # Secrets (gitignored)
├── .gitignore                         # Exclude: .env, *.pem, *.key, *.tfstate
├── .claudeignore                      # Exclude from Claude context
├── NOTES.md                           # This file
├── PITCH.md                           # Elevator pitch
├── SCALE_OUT.md                       # Production scale-out paths
└── README.md                          # How to run, architecture overview
```

### Service Responsibilities (Clear Separation)

| Service | Responsibility | Access |
|---------|-----------------|--------|
| **mcp_server** | Validate JWT, HMAC, Cedar policies; execute S3 operations | Public (agents call it) |
| **admin_bootstrap** | Create/modify certs, dual-sig policies, Template Registry updates | Admin only (mTLS + API key) |
| **cert_authority** | CA operations (self-signed certs for PoC) | Library (imported by admin_bootstrap) |
| **demo (web)** | Orchestrate 11 scenarios, show audit trail | Public (browser UI) |

---

## Docker Compose Best Practices

### Volumes: Bind Mounts (Dev) + Named Volume (Persistence)

**Bind Mounts** — Local source code mounted into containers (hot reload):
```yaml
services:
  mcp_server:
    volumes:
      - ./services/mcp_server:/app           # source code (live changes)
      - ./policies:/app/policies             # Cedar policies (external, updateable)
  
  admin_bootstrap:
    volumes:
      - ./services/admin_bootstrap:/app      # source code
      - ./ca:/app/ca                         # CA certs (gitignored, local)
  
  demo_web:
    volumes:
      - ./demo:/app                          # demo source code
```

**Why bind mounts:** Change local file → restart container → immediate effect. No rebuild needed. Perfect for development velocity.

**Named Volume** — Persistent data storage across `docker-compose down/up`:
```yaml
volumes:
  dynamodb_data:
    driver: local

services:
  dynamodb_local:
    volumes:
      - dynamodb_data:/home/dynamodblocal/data  # DynamoDB data survives restarts
```

**Why named volume:** DynamoDB test data persists when you restart containers (don't lose test state).

### Environment Variables in docker-compose.yml

Only non-secret config in environment (secrets come from AWS Secrets Manager at startup):
```yaml
services:
  mcp_server:
    environment:
      - AWS_REGION=${AWS_REGION}                    # from .env
      - AWS_SECRETS_NAME=a2a-trust-poc/secrets      # static
      - S3_BUCKET=${S3_BUCKET}                      # from .env
      - DYNAMODB_TABLE=${DYNAMODB_TABLE}            # from .env
      - CEDAR_POLICY_PATH=/app/policies             # internal path
      - LOG_LEVEL=${LOG_LEVEL:-INFO}                # default to INFO
  
  admin_bootstrap:
    environment:
      - AWS_REGION=${AWS_REGION}
      - AWS_SECRETS_NAME=a2a-trust-poc/secrets
      - DYNAMODB_TABLE=${DYNAMODB_TABLE}
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
  
  demo_web:
    environment:
      - AWS_REGION=${AWS_REGION}
      - AWS_SECRETS_NAME=a2a-trust-poc/secrets
      - MCP_URL=http://mcp_server:8001
      - ADMIN_URL=http://admin_bootstrap:8002
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
```

**Why:** 
- Secrets fetch from Secrets Manager at startup (not environment vars)
- Config-only env vars can be logged safely (no secrets exposed)
- Same code path local and deployed (boto3 handles both)

### Docker Compose Networking

All services communicate over a shared Docker network (`a2a_network`):

```yaml
networks:
  a2a_network:
    driver: bridge

services:
  mcp_server:
    networks:
      - a2a_network
    # Accessible to demo_web as: http://mcp_server:8001
  
  admin_bootstrap:
    networks:
      - a2a_network
    # Accessible to demo_web as: http://admin_bootstrap:8002
  
  demo_web:
    networks:
      - a2a_network
    # Calls other services via: http://mcp_server:8001, http://admin_bootstrap:8002
  
  dynamodb_local:
    networks:
      - a2a_network
    # All services access via: http://dynamodb_local:8000
```

**Service-to-Service Communication:**
- Demo web → MCP: `http://mcp_server:8001`
- Demo web → Admin: `http://admin_bootstrap:8002`
- MCP/Admin → DynamoDB: `http://dynamodb_local:8000`
- All services use shared network DNS names (no localhost references internally)

**External Access (from host machine):**
- Demo web: `http://localhost:8765`
- MCP server: `http://localhost:8001`
- Admin Bootstrap: `http://localhost:8002`
- DynamoDB: `http://localhost:8000`

### Docker Desktop Visibility

When running `docker-compose up`, all containers visible in Docker Desktop:
- Container status (running/stopped)
- Port mappings (8001, 8002, 8765, 8000)
- Live logs (filter by service)
- Resource usage (CPU, memory)
- Named volumes (Volumes tab)
- Network connections (Services tab → Networks)

---

## Dynamic Policy Lane — Demo UI Requirements

The demo must show both the static and dynamic trust lanes in action.

### Static Lane (Agent Certificate)
- Agent cert fields are fixed at issuance — identity, CanSpawn whitelist, AllowedScopes, TTL
- If the cert does NOT include a spawn permission → spawn is DENIED, period. No policy can override it.
- If the cert does NOT include a scope → that action is DENIED at the cert level before Cedar even runs
- Cert is the hard ceiling — Cedar can only restrict further, never grant beyond what the cert allows

### Dynamic Lane (Cedar Policies)
- Cedar policy files are runtime-updateable — no cert rotation required
- Every policy change requires dual signatures (Owner + Policy Authority) — simulated in demo
- Enforcement changes immediately on next request after policy update

### Demo UI — Policy Management Section
- **View current Cedar policies** — show active rules in human-readable form
- **Update a policy** — simulate dual-signature approval flow, update Cedar policy file
- **Show enforcement change** — same agent, updated policy, different outcome on next request
- **Deny scenarios from cert level** — show agent attempting spawn/action not in cert → DENIED before Cedar runs
- **Deny scenarios from policy level** — show agent with valid cert but Cedar policy blocks action → DENIED

### The Money Shot
Same agent. Policy changes. Behavior changes instantly. No cert rotation. No restart. That's the dynamic lane in action.

---

## Workflow Orchestration Breadcrumb — LangGraph vs Prompt Flow

**Context:** LinkedIn post comparing Azure Prompt Flow vs LangGraph for AI agent workflows. Relevant to A2A PoC agent orchestration layer.

**Prompt Flow (Azure AI Foundry)**
- Visual designer, good for rapid prototyping and linear workflows
- Auditors love the diagrams — compliance-friendly
- Limited trace visibility — bad for debugging complex agent interactions
- 3 silent failures vs LangGraph's 0 in the comparison

**LangGraph**
- Stateful, deterministic workflows with checkpointing (resume on failure)
- Handles complex branching (10+ decision points)
- Auditable reasoning-level tracing via Logfire
- 8x faster debug time, 0 audit findings, FedRAMP accepted in the comparison

**How this improves the A2A PoC:**
- **LangGraph for agent orchestration** — Agent A and Agent B can use LangGraph for stateful workflow execution. If a trust check fails mid-flow, the workflow checkpoints and resumes without losing state.
- **Durable workflows via Temporal** — wrap the A2A trust handshake in a Temporal durable workflow. If the JWT validation or Cedar policy check fails transiently, Temporal retries without re-authenticating from scratch.
- **Logfire for reasoning traces** — add Logfire alongside Google Cloud Logging and CloudWatch for auditable agent reasoning traces. Three-layer observability: what the agent did, why it decided, and what the audit trail says.
- **FedRAMP angle** — LangGraph + Temporal + Cedar policies = a FedRAMP-acceptable agent architecture. Worth noting in the IETF draft and the scale-out doc.

**Decision for PoC:** Start with custom FastAPI orchestration (simpler, fewer dependencies). Document LangGraph + Temporal as the production scale-out path in SCALE_OUT.md.

---

## MCP (Model Context Protocol) — Agent Tools Without Cloud Credentials

**Principle:** Agents never hold cloud credentials (AWS keys, GCP service accounts). All cloud operations go through an MCP server that validates authority before executing.

### Architecture
- **MCP Server** (Python, runs in Docker) — owns AWS credentials from `.env`
- **Tool 1: `write_event_to_s3`** — Agent B calls this tool via Claude
  - Input: `event_data` (string), `correlationId` (UUID), `timestamp` (ISO8601)
  - MCP server validates: "Is this request from Agent B?" (via JWT in tool call context)
  - MCP server checks: "Does Agent B have `write:events` scope?" (from Cedar policy)
  - If yes: writes to S3, returns success + path
  - If no: DENIED, logged with reason
- **Tool 2: `read_event_from_s3`** — Agent A calls this tool via Claude
  - Input: `s3_path` (string), `correlationId` (UUID)
  - MCP server validates: "Is this request from Agent A?"
  - MCP server checks: "Does Agent A have `read:events` scope?"
  - If yes: reads from S3, returns content
  - If no: DENIED, logged with reason

### Why This Design
- **Zero-trust for credentials** — agents never see AWS keys, can't misuse them
- **Tool-level authorization** — MCP server re-validates Cedar policy on every call (defense in depth)
- **Auditability** — every tool call logged with agent ID, scope, decision, outcome
- **Fail-closed** — if MCP server unreachable or scope check fails, tool call is DENIED

### Implementation Notes
- MCP server endpoints (`/write_event`, `/read_event`) require:
  - JWT in Authorization header (Agent A or B's token)
  - HMAC signature on request body
  - correlationId in headers for trace linking
- MCP server validates token + signature before executing any cloud operation
- All tool calls logged to CloudWatch + Google Cloud Logging with correlationId
- Agent's Claude instance receives tool response (success/failure), not error details (no infrastructure leakage)

### .env Structure
```
# Credentials for MCP server ONLY — agents never see these
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
S3_BUCKET=a2a-trust-poc-events
GCP_PROJECT_ID=...
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json  # for Cloud Logging
```

---

## Admin/Bootstrap Service — Cert & Policy Lifecycle (Locked Down)

**Principle:** Certificate creation, modification, and policy management are operator-controlled. MCP server uses immutable certs; it does not create them.

### Service Responsibilities

#### Admin/Bootstrap Service Owns:
- **Agent cert creation** — generates X.509 certs with IETF-required fields (AllowedScopes, CanSpawn, MaxChildren, TTL)
- **Cert modification** — scope changes, TTL rotation, owner updates
- **Revocation lifecycle** — cert state transitions: ACTIVE → DISABLED → DELETED
- **CRL management** — Certificate Revocation List updates when certs are deleted
- **Template Registry** — DynamoDB CRUD for agent certificate metadata
- **Policy Authority dual-sig** — validates owner sig + Policy Authority sig on policy changes
- **Cedar policy updates** — applies policy changes (requires dual signatures)
- **Audit logging** — who changed what cert/policy, when, why, timestamp

#### MCP Server DOES NOT:
- Create or modify agent certs
- Change Cedar policies
- Update Template Registry
- Revoke certs
- Only validates and uses existing, immutable certs

### Access Control
- **Admin/Bootstrap endpoints** secured by:
  - mTLS (mutual TLS with operator certificate)
  - API key (from `.env`, rotated regularly)
  - OAuth2 bearer token (for IETF draft compliance, if using production CA)
  - Audit log of all requests (who, what, when, where, outcome)
- **No token-based access** to cert creation (only human operators + approved services)

### Why This Separation
- **Reproducibility** — Others testing IETF spec use the same fixed agent certs
- **Security** — Cert creation can't be done via API token (can't be stolen/leaked)
- **Auditability** — Cert changes are operator actions, all logged
- **Compliance** — Matches real-world CA operations (separate from application layer)

### Service Structure
```
services/
  mcp_server/
    - jwt_validator.py
    - hmac_verifier.py
    - cedar_policy_eval.py
    - s3_tools.py (write_event, read_event)
    - main.py (FastAPI + MCP endpoints)
    
  admin_bootstrap/
    - cert_generator.py (OpenSSL + cryptography lib)
    - cert_manager.py (CRUD on DynamoDB Template Registry)
    - policy_authority.py (dual-sig validation)
    - crl_manager.py (revocation list updates)
    - main.py (FastAPI admin endpoints, mTLS + API key secured)
    
  cert_authority/
    - ca.py (self-managed CA for PoC; Vault PKI for prod)
```

### Bootstrap Flow (One-Time Setup)
1. Operator runs admin bootstrap service
2. Admin service generates CA (root cert) — stored in secure location
3. Admin service generates Agent A cert (with scopes, CanSpawn list, TTL)
4. Admin service generates Agent B cert (with scopes, CanSpawn list, TTL)
5. Certs stored in DynamoDB Template Registry
6. Bootstrap service exits (only needed for cert creation, not runtime)
7. MCP server starts, loads certs from Registry, validates incoming requests

### Policy Updates (Runtime)
1. Operator submits policy change request to Admin service
2. Admin service creates unsigned policy document
3. Operator signs with private key (Owner sig)
4. Admin service requests Policy Authority to sign (dual-sig)
5. Policy Authority validates owner sig, adds PA sig
6. Admin service writes updated Cedar policy to file + DynamoDB
7. Cedar policy engine in MCP server picks up change on next request

---

## Course Breadcrumbs (add as you go through Vertex AI course)
- TBD

---

## LinkedIn Post (after Phase 7 + draft v2 + webpage live)
**Hook:** "I wrote the IETF draft. Then I built the demo. Here's the audit trail."

**Angles:**
- Agent authentication gap: most frameworks skip it entirely
- Zero Trust for AI agents — same principles, new attack surface
- 11 scenarios (1 golden path + 1 dynamic policy demo + 9 attack/edge cases), all fail-closed, all logged with correlationId chain
- Multi-cloud (GCP Vertex AI + AWS) — not vendor-locked
- Link to demo page + IETF draft v2

**Post AFTER:** repo public + draft v2 submitted + demo page live. Not before.

---

## IETF Draft Reference
draft-tonyai-a2a-trust-00
https://datatracker.ietf.org/doc/draft-tonyai-a2a-trust/

---

## How the PoC Proves the IETF Draft

Every demo scenario maps directly to a requirement in draft-tonyai-a2a-trust-00.

### Agent Identity — X.509 Template Certificate Fields to Implement
These are the required fields from the draft. Each must appear in our agent certs (self-signed for PoC, CA-signed for prod):

| Field | Description | PoC Implementation |
|---|---|---|
| Subject | Unique template identifier | agent-a / agent-b |
| Owner | Verified template creator | Tony / TonyAI org |
| OrgID | Organization identifier | tonyai-org |
| KeyUsage | Permitted operations | sign, verify |
| AllowedScopes | Max scopes the agent may hold | read:patient, write:audit |
| CanSpawn | Whitelist of permitted child templates | agent-b can spawn agent-c |
| MaxChildren | Max concurrent child agents | 2 |
| ScopeInherit | Scope inheritance constraints | child <= parent |
| PolicyRef | Reference to dynamic policy store | Cedar policy file path |
| TTL | Maximum agent lifetime | 3600s |

### Static vs Dynamic Trust Lanes
- **Static Lane** — certificate-based identity and spawn authority. Changes require re-certification. Implemented via OpenSSL self-signed certs.
- **Dynamic Lane** — operational permissions bounded by static template. Fast-path policy changes require dual signatures (Owner + Policy Authority).

### Spawn Chain Validation (Two-Check Rule)
Both checks must pass — either failure = DENY:
1. **Static Check** — child template must appear in parent's CanSpawn list
2. **Dynamic Check** — template must be currently registered, signed by CA (self-signed for PoC, prod CA for production), owned by authorized party, not on CRL

**Demo scenario:** Agent A tries to spawn Agent C (not in CanSpawn list) → DENY logged

### Scope Constraint Principle
Child scopes must be a strict subset of parent scopes. Scope escalation across agent hops is **explicitly prohibited**.

**Demo scenario:** Agent A requests a scope it doesn't hold → DENY logged

### Cross-Org Agent Interaction
Explicit grant structure required — no implicit trust between organizations.
Grant must contain: grantor + grantee orgs, template ID, AllowedScopes, TTL, MaxSpawns, dual signatures.

**Demo scenario:** Agent from Org B attempts access without explicit grant → DENY logged

### Fail-Closed Enforcement
Any verification step that cannot be completed MUST result in DENY. Includes:
- CA/registry/CRL unreachable
- Certificate expired
- Scope escalation attempt
- Invalid or unsigned policy

### Audit Trail Requirements (per draft)
Every spawn/access event MUST log:
- Spawning agent identity
- Child template identity
- Requested scope
- Granted scope
- Timestamp
- Outcome: ALLOWED or DENIED
- Denial reason (if denied)
- **Correlation ID** — UUID v7, traces request across all layers
- **spanId** — unique to this hop
- **parentSpanId** — links to spawning agent's spanId
- **prevEntryHash** — SHA-256 of previous log entry (hash-chaining for tamper-evidence)

**Federated audit:** Each org maintains independent audit trail. Records MUST NOT depend on the other org's systems.

### Spec Gap — correlationId (next draft revision)
The current draft (draft-tonyai-a2a-trust-00) defines *what* to log but does not specify *how* to correlate events across multi-hop chains. The PoC will implement correlationId + spanId + parentSpanId per the OpenTelemetry trace/span model. This must be surfaced as a spec addition in the next draft revision — without it, tamper-evident audit is operationally useless across multi-hop chains.

### Replay Attack Prevention
Every request includes timestamp + nonce. Agent B rejects replayed requests.

---

## Demo HTML Page Plan (Flagship Style)

Reference implementation: `/Users/tonyai/dev/last-mile-zero-trust/secure-rag-zero-trust-demo`
Reuse: page structure (prep.html + demo.html), CSS/styling, audit table pattern, UUID v7 correlation ID wiring.

Two pages:

### prep.html — Context Before the Demo
- Architecture diagram: Orchestrator → mTLS → Agent A → spawn validator (two-check rule) → Agent B → Cedar (policy eval) → DynamoDB (registry) → CloudWatch + GCP Cloud Logging (federated audit)
- Trust stack explanation: mTLS → JWT RS256 chain → HMAC-SHA256 → two-check spawn rule → Cedar policy → hash-chained tamper-evident audit
- IETF draft field mapping table (AllowedScopes, CanSpawn, TTL, etc.)
- Static lane vs Dynamic lane explanation — cert is the hard ceiling, Cedar operates within it
- Correlation ID explanation — UUID v7, what it traces, why it matters for multi-hop chains
- Spec gap callout — correlationId not in current draft, PoC proposes it as next revision

### demo.html — Live Scenarios + Audit Log

#### Demo Flows (11 scenarios, each runnable via button)
1. **Golden path (E2E task completion with scope separation)** — Agent A (certs: `read:events` scope) and Agent B (cert: `write:events` scope). Flow demonstrates least privilege + chain of custody without agents tampering with audit:
   - **Step 1: Agent B writes event to S3**
     - Agent A requests Agent B to write event: `POST /write-event` with event data + HMAC-SHA256 signature + correlationId
     - Agent B validates mTLS cert chain → valid
     - Agent B validates JWT signature + expiry → valid
     - Agent B checks cert scopes: "Agent B has `write:events`?" → ✓
     - Agent B evaluates Cedar policy: "Agent B (template=agent-b, org=tonyai-org) can write:events" → ✓
     - Agent B verifies HMAC on payload → ✓
     - Agent B writes markdown doc to S3: `event_${correlationId}_${timestamp}.md` (immutable, timestamped)
     - Agent B returns success + S3 path to Agent A (but cannot read what it wrote — no `read:events` scope)
   - **Step 2: Agent A reads event from S3 to verify**
     - Agent A requests Agent B to help verify: Agent A directly reads from S3 using its own S3 credentials (Agent A has `read:events` scope, Agent B does not)
     - S3 GetObject call → returns file content + metadata (timestamp, ETag)
     - Demo displays: "✓ ALLOWED — Event written by Agent B, verified by Agent A"
   - **Audit trail** (independent of agents):
     - S3 PutObject event → CloudTrail → CloudWatch + Google Cloud Logging
     - S3 GetObject event → CloudTrail → CloudWatch + Google Cloud Logging
     - Audit table records: correlationId chain unbroken, Agent B decision=ALLOWED (write), Agent A decision=ALLOWED (read), grantedScopes=[write:events] for B, [read:events] for A
     - Hash chain intact, prevEntryHash valid
   - **Key security properties:**
     - Neither agent can exceed assigned scopes (Agent B can't read, Agent A can't write)
     - Artifact is immutable (S3, timestamped, CloudTrail-audited)
     - Audit trail is external and independent (agents don't control what gets logged)
     - Chain of custody proven: Agent B wrote it (scope: write), Agent A verified it (scope: read)
2. **Dynamic policy update (Static vs Dynamic lanes)** — Shows real-time policy enforcement without cert rotation:
   - **Prep Phase (Admin Bootstrap):** Create Agent B cert with `write:events` scope + Cedar policy allowing `write:events`
   - **Demo Part 1 (Before policy change):**
     - Agent B attempts to write event → Cedar policy allows it → ✓ ALLOWED (green row)
     - Audit: decision=ALLOWED, grantedScopes=[write:events]
   - **Demo Part 2 (Policy update in real-time):**
     - Operator/Admin removes `write:events` from Cedar policy (dual-sig: Owner + Policy Authority)
     - Cedar policy updated in DynamoDB — no cert rotation required
     - Enforcement changes immediately on next request
   - **Demo Part 3 (After policy change):**
     - Same Agent B attempts to write event → Cedar policy denies it → ✗ DENIED (red row)
     - Audit: decision=DENIED, reason="scope write:events not granted by policy"
   - **Money shot:** Same agent, same cert (static lane unchanged), but Cedar policy changed (dynamic lane) = instant enforcement change
3. **Rogue spawn** — not in CanSpawn list → DENY
4. **Dual-sig missing** — only owner sig present → DENY
5. **Dual-sig tampered** — PA sig invalid → DENY
6. **Scope escalation** — child exceeds parent scopes → DENY
7. **Revocation lifecycle** — ACTIVE → DISABLED → DELETED state walk
8. **CRL check failure** — revoked cert mid-chain → DENY
9. **TTL expiry** — expired template → DENY
10. **Cross-org grant** — grant ALLOW then revoke → DENY
11. **Replay attack** — reused nonce → DENY

Each scenario button triggers the backend flow and appends a row to the live audit table.

#### Audit Log Visualization (live table)
Columns: `correlationId` | `spanId` | `parentSpanId` | `agentId` | `action` | `requestedScopes` | `grantedScopes` | `decision` | `reason` | `timestamp` | `prevEntryHash`

- Rows append in real time as scenarios run
- ALLOWED rows green, DENIED rows red
- Click any row to expand full JSON entry
- Hash chain integrity indicator — shows if prevEntryHash chain is unbroken

---

## Post-PoC Release Sequence

**Order matters — do not skip steps or reorder:**

1. **PoC working** — all 11 demo scenarios pass, audit trail verified
2. **Phase 7 SOLID/hardening pass** — code reflects TonyAI brand before anyone sees it
3. **Flip GitHub repo public** — tonyai/a2a-trust-poc goes public
4. **IETF draft v2** — two specific additions:
   - Add correlationId + spanId + parentSpanId to audit trail section (spec gap fix)
   - Add "Reference Implementation" section with GitHub repo link + test vectors
5. **Update demo webpage** — prep.html + demo.html live on GitHub Pages with working demo link
6. **LinkedIn post** — "I wrote the IETF draft. Then I built the demo. Here's the audit trail." + link to demo page + draft v2

---

## TODO: Present to IETF Committees
Once demo is complete and RFC is drafted:

1. **Update Internet-Draft (v2)** — correlationId spec addition + "Reference Implementation" section with GitHub repo link and test vectors
2. **Target Working Groups:**
   - SAAG (Security Area Advisory Group) — already on mailing list
   - OAuth WG — OAuth2/OIDC patterns in the draft make this relevant
3. **Submit for WG discussion** — working demo + test vectors is what gets chairs to schedule a presentation slot
4. **IETF Plenary sessions** — 3x per year; interim virtual meetings also available
5. **Path to RFC** — WG adoption → review cycles → RFC. Career-defining credential.

**What strengthens the presentation:**
- Working demo with all 11 scenarios (see Live Demo Scenarios above)
- GCP + AWS coverage — not vendor-locked
- Correlation IDs + federated audit trail — addresses operability concerns reviewers raise
- Test vectors for valid/invalid chains — required for conformance

---

## TODO: Write RFC for PoC
Once the working demo is complete, write an RFC (or update the IETF Internet-Draft) that references this PoC as the canonical reference implementation. The RFC should:
- Link to the GitHub repo as the reference implementation
- Document the test vectors (valid chain, invalid chain, revoked cert, scope escalation attempt)
- Reference each demo scenario as a conformance test case
- Position this as the implementation guide for anyone building to draft-tonyai-a2a-trust-00

---

## GCP / Vertex AI Integration

### Agent → Claude via Vertex AI Pattern

Each agent (Agent A, Agent B, Demo backend) invokes Claude through Vertex AI for reasoning:

```python
# In Agent A or Agent B service
from google.cloud import aiplatform

def invoke_claude(prompt: str) -> str:
    """Invoke Claude 3.5 Sonnet via Vertex AI"""
    client = aiplatform.gapic.PredictionServiceClient()
    endpoint = f"projects/{GCP_PROJECT_ID}/locations/{GCP_REGION}/endpoints/{VERTEX_ENDPOINT_ID}"
    
    request = {
        "endpoint": endpoint,
        "instances": [{"prompt": prompt}],
    }
    
    response = client.predict(request=request)
    return response.predictions[0]["content"]
```

**Example Usage:**

1. **Agent A formulating request:**
   ```python
   prompt = f"""
   I need to request Agent B to write an event to S3.
   Event: {event_data}
   Scopes requested: {requested_scopes}
   Formulate the request with proper JWT + HMAC signing.
   """
   request_json = invoke_claude(prompt)
   # Claude returns: {"method": "POST", "endpoint": "/write-event", "payload": {...}, "hmac": "..."}
   ```

2. **Agent B processing response:**
   ```python
   prompt = f"""
   Agent A requests: {request_json}
   My scopes: {agent_b_scopes}
   Cedar policy decision: {cedar_decision}
   Process this request and return the result.
   """
   result = invoke_claude(prompt)
   # Claude returns: {"status": "success", "file_path": "...", "timestamp": "..."}
   ```

### Key Points:

- **Credentials:** GCP service account (from `GOOGLE_APPLICATION_CREDENTIALS` in `.env`)
- **Model:** Claude 3.5 Sonnet via Vertex AI (not Bedrock)
- **Reasoning:** Claude decides HOW to invoke MCP tools, WHAT to request, based on scopes
- **Stateless:** Each invocation is independent; no session state
- **Correlation ID:** Pass correlationId in prompt so Claude includes it in response (traceability)

### Closes GCP Gap on Resume

- Built A2A trust PoC on Vertex AI (Google Cloud)
- Complements existing Bedrock PoCs (AWS)
- Multi-cloud capability: GCP + AWS
- Demonstrates vendor neutrality and cloud-agnostic architecture

---

## Flagship PoC Reference (reuse patterns from)
- `/Users/tonyai/dev/last-mile-zero-trust/secure-rag-zero-trust-demo`
- Reuse: JWT RS256 validator pattern, audit log structure, UUID v7 correlation ID, fail-closed error handling, demo HTML page structure (prep.html + demo.html), Docker Compose setup
- DO NOT reuse: Redis ReBAC (Cedar replaces it in this PoC)

---

## Secret Management — AWS Secrets Manager

**No secrets in code, .env, or containers. All secrets in AWS Secrets Manager + encrypted at rest.**

### Secret Storage (AWS Secrets Manager)

All secrets stored securely in AWS Secrets Manager (KMS encrypted):

```json
{
  "jwt_secret": "your-secret-key-here",
  "jwt_algorithm": "RS256",
  "hmac_secret": "your-hmac-secret-here",
  "gcp_service_account_json": "{...full GCP service account JSON...}",
  "admin_api_key": "your-admin-api-key-here"
}
```

**Location:** `a2a-trust-poc/secrets` (AWS Secrets Manager)

**Access:** Services fetch at startup via boto3, cached in memory
**Audit:** CloudTrail logs every secret access with timestamp, principal, result
**Rotation:** AWS Secrets Manager rotation policies (automatic or manual)

### .env Configuration (NO SECRETS)

Create `.env.example` (committed) and `.env` (gitignored, config only — NO SECRETS):

```
# Non-secret configuration only

# AWS
AWS_REGION=us-east-1
AWS_SECRETS_NAME=a2a-trust-poc/secrets
S3_BUCKET=a2a-trust-poc-events
DYNAMODB_TABLE=template_registry
DYNAMODB_REGION=us-east-1

# GCP
GCP_PROJECT_ID=your-gcp-project-id
GCP_REGION=us-central1
VERTEX_AI_MODEL=claude-3-5-sonnet@20241022

# Service Configuration (non-secret)
MCP_PORT=8001
ADMIN_PORT=8002
DEMO_PORT=8765

# Logging & Monitoring
LOG_LEVEL=INFO
CLOUDWATCH_LOG_GROUP=/a2a-trust-poc/audit
CLOUDWATCH_REGION=us-east-1

# Policy Management
CEDAR_POLICY_PATH=./policies
CEDAR_SCHEMA_PATH=./policies/schema.json

# GitHub (non-secret)
GITHUB_REPO=tonyt68/a2a-trust-poc
```

### Service Startup Pattern (Secure)

```python
# services/mcp_server/config.py
import boto3
import json
from functools import lru_cache
import logging

log = logging.getLogger(__name__)

@lru_cache(maxsize=1)
def load_secrets() -> dict:
    """
    Load all secrets from AWS Secrets Manager at startup.
    Cached in memory (single fetch, reused for all requests).
    Audit logged to CloudTrail.
    """
    client = boto3.client('secretsmanager', region_name=os.getenv('AWS_REGION'))
    secret_name = os.getenv('AWS_SECRETS_NAME')
    
    try:
        response = client.get_secret_value(SecretId=secret_name)
        secrets = json.loads(response['SecretString'])
        
        log.info("Secrets loaded from AWS Secrets Manager",
                 extra={"secret_name": secret_name, "keys": list(secrets.keys())})
        
        return secrets
    
    except Exception as e:
        log.error("Failed to load secrets from AWS Secrets Manager",
                  extra={"error": str(e), "secret_name": secret_name})
        raise  # Fail-closed: no secrets = cannot start

@lru_cache(maxsize=1)
def get_settings():
    """Get all configuration (secrets + non-secrets)"""
    from pydantic import BaseSettings
    
    secrets = load_secrets()
    
    class Settings(BaseSettings):
        # Secrets (from AWS Secrets Manager)
        jwt_secret: str = secrets.get('jwt_secret')
        hmac_secret: str = secrets.get('hmac_secret')
        admin_api_key: str = secrets.get('admin_api_key')
        gcp_service_account_json: str = secrets.get('gcp_service_account_json')
        
        # Config (from .env)
        aws_region: str = os.getenv('AWS_REGION', 'us-east-1')
        s3_bucket: str = os.getenv('S3_BUCKET')
        mcp_port: int = int(os.getenv('MCP_PORT', 8001))
        log_level: str = os.getenv('LOG_LEVEL', 'INFO')
        
        class Config:
            env_file = ".env"
    
    return Settings()
```

### Terraform: Secrets Manager Setup

```hcl
# terraform/secrets.tf

resource "aws_kms_key" "secrets" {
  description             = "KMS key for a2a-trust-poc secrets encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true
}

resource "aws_kms_alias" "secrets" {
  name          = "alias/a2a-trust-poc-secrets"
  target_key_id = aws_kms_key.secrets.key_id
}

resource "aws_secretsmanager_secret" "a2a_poc" {
  name                    = "a2a-trust-poc/secrets"
  description             = "Secrets for A2A Trust PoC (encrypted with KMS)"
  kms_key_id              = aws_kms_key.secrets.id
  recovery_window_in_days = 7  # Allow recovery if deleted
}

resource "aws_secretsmanager_secret_version" "a2a_poc" {
  secret_id = aws_secretsmanager_secret.a2a_poc.id
  
  secret_string = jsonencode({
    jwt_secret              = var.jwt_secret              # Inject via tfvars (CI/CD)
    hmac_secret             = var.hmac_secret             # Inject via tfvars (CI/CD)
    admin_api_key           = var.admin_api_key           # Inject via tfvars (CI/CD)
    gcp_service_account_json = var.gcp_service_account_json # Full GCP service account JSON
  })
}

# IAM policy: only services with this role can read secrets
resource "aws_iam_policy" "read_secrets" {
  name = "a2a-trust-poc-read-secrets"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = aws_secretsmanager_secret.a2a_poc.arn
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey"
        ]
        Resource = aws_kms_key.secrets.arn
      }
    ]
  })
}

# Audit logging: CloudTrail captures all secret access
resource "aws_cloudtrail" "secrets_audit" {
  name           = "a2a-trust-poc-secrets-audit"
  s3_bucket_name = aws_s3_bucket.audit_logs.id
  
  depends_on = [aws_s3_bucket_policy.audit_logs]
  
  event_selector {
    read_write_type           = "All"
    include_management_events = true
    
    data_resource {
      type   = "AWS::SecretsManager::Secret"
      values = ["arn:aws:secretsmanager:*:*:secret:a2a-trust-poc/*"]
    }
  }
}
```

### Security Properties

✅ **No secrets in .env** — config only  
✅ **No secrets in code** — all from Secrets Manager  
✅ **No secrets in containers** — fetched at startup, not injected  
✅ **Encryption at rest** — KMS AES-256  
✅ **Encryption in transit** — TLS to Secrets Manager  
✅ **Audit trail** — CloudTrail logs every access  
✅ **Least privilege** — IAM roles scoped per service  
✅ **Rotation support** — AWS handles key rotation  
✅ **Fail-closed** — no secrets = service fails to start  
✅ **Same code dev/prod** — boto3 works locally (via AWS CLI creds) and deployed

## Repo Setup Checklist

**Security-first setup:**
- Copy `.claudeignore` from `/Users/tonyai/dev/last-mile-zero-trust/secure-rag-zero-trust-demo/`
- Copy `.gitignore` from flagship — ensure `.env`, `*.pem`, `*.key`, `*.tfstate`, `service-account.json` are excluded
- Create `.env.example` (non-secret config only) — committed, template
- Create `.env` (gitignored, config only) — fill with AWS_REGION, S3_BUCKET, etc. (NO SECRETS)
- Create AWS Secrets Manager secret: `a2a-trust-poc/secrets` (via Terraform)
- Create `.pem` and `.key` files locally (CA + agent certs) — gitignored
- Create `service-account.json` (GCP service account) locally — gitignored

**What goes where:**
- **Git (committed):** Source code, Terraform IaC, `.env.example`, `.gitignore`
- **Local only (gitignored):** `.env`, `*.pem`, `*.key`, `service-account.json`
- **AWS Secrets Manager (encrypted):** JWT secret, HMAC secret, Admin API key, GCP service account JSON
- **Never anywhere:** Hardcoded secrets, credentials in code, tokens in git history

---

## GitHub & Deployment

**Note:** Demo runs **locally only** during Phase 1-7 (http://localhost:8765). GitHub Pages deployment happens **post-Phase 7**, when repo goes public and IETF draft v2 is submitted.

### One-Time Setup (Tony's responsibility)
1. Create private GitHub repo manually: `tonyt68/a2a-trust-poc` (GitHub UI)
2. Create fine-grained API token: Settings → Developer settings → Personal access tokens (GitHub UI)
   - Scoped to: tonyai/a2a-trust-poc only
   - Permissions: Contents (read/write), Actions (read)
3. Fill `.env`:
   ```
   GITHUB_TOKEN=ghp_xxxxxxxxxxxx
   GITHUB_REPO=tonyt68/a2a-trust-poc
   ```

### Repo Maintenance (Claude Code's responsibility)
- Use `gh` CLI for all commits, branches, pushes (handles auth via `.env` token)
- `gh` command: `gh auth login` (one-time), then `git push` works automatically

### Repository Structure (Two-Repo Pattern — Post-Phase 7)

**1. Private GitHub Repo (tonyai/a2a-trust-poc)**
- Source code: FastAPI services (mcp_server, admin_bootstrap, demo web)
- Infrastructure: Terraform (AWS + GCP resources)
- Configuration: docker-compose.yml, Cedar policies
- Documentation: NOTES.md, PITCH.md, SCALE_OUT.md, README.md
- **Visibility:** Private until IETF draft v2 submitted + reference impl link added
- **Credentials:** `.env` (gitignored), `.env.example` (template only)

**2. Public GitHub Pages Deployment**
- Source: `/docs` branch or `gh-pages` branch
- Content: `prep.html`, `demo.html`, `static/` (CSS, JS)
- Live URL: `https://tonyt68.github.io/a2a-trust-poc/` (or via custom domain)
- **Visibility:** Public from day 1 (once basic structure ready)
- **Updates:** Deployed via GitHub Actions on push to main

### GitHub Pages Deployment (Post-Phase 7 — Deferred)

When demo goes public (after IETF draft v2 + Phase 7 hardening), set up:

- GitHub Pages: deploy from `docs/` branch
- GitHub Actions workflow: validates HTML, deploys demo files on push to main
- Terraform: GitHub provider for repo config (branch protection, Pages settings)
- Security: Checksum validation, audit trail logging

Details in NOTES.md Phase 7+ section (when deploying to GitHub Pages).

### Release Timeline

1. **Phase 1-6** — Develop in private repo, demo runs locally only (http://localhost:8765)
   - Source code hidden
   - Commit/push via `gh` CLI (Claude Code handles)
   
2. **Phase 7** — Security hardening, peer review (still private, demo still local)
   - SOLID review pass
   - Red team hacker pass
   - Code reflects TonyAI brand standards
   
3. **Post-Phase 7: Make Demo Public**
   - Deploy GitHub Pages (prep.html + demo.html live)
   - Flip GitHub repo public
   - IETF draft v2 submitted (add "Reference Implementation" section + GitHub repo link)
   - LinkedIn post: "I wrote the IETF draft. Then I built the demo. Here's the audit trail."

**Why this order matters:**
- Phase 1-7: local dev (fast iteration, no deployment overhead)
- Phase 7: hardening before anyone sees code (TonyAI brand standard)
- Post-Phase 7: public demo + public repo + IETF draft v2 (legitimacy + traceability)
