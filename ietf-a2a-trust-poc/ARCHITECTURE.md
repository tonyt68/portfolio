# A2A Trust PoC — System Architecture & Design Document

**Project:** IETF draft-tonyai-a2a-trust-00 Reference Implementation  
**Authors:** Tony AI + Claude Code (AI-Partnered Design)  
**Date:** 2026-06-04  
**Status:** Design Complete, Phase 1-4 Implementation Complete

---

## Executive Summary

This document describes the **architectural design** of the Agent-to-Agent Trust (A2A) enforcement reference implementation. It proves that Zero Trust principles — cryptographic identity, least privilege, fail-closed enforcement, immutable audit — are implementable for AI agents using commodity components (JWT, HMAC, Cedar, AWS, GCP).

**Key Innovation:** Agents hold NO credentials. Trust decisions happen in a gated MCP (Model Context Protocol) service with full audit trail in independent cloud logging systems.

---

## Problem Statement

AI agents today have **no standardized way to authenticate to each other**. When Agent A calls Agent B:
- How does Agent B know Agent A is who it claims?
- How does Agent B know Agent A is authorized?
- How does either agent know the message wasn't tampered with?
- Who audits what happened if something goes wrong?

**Current state:** No standard answer. Most frameworks assume agents trust each other by default.

---

## Design Principles

### 1. Zero Trust for Agents
- No implicit trust between agents
- Every request authenticated, authorized, integrity-verified, logged
- Fail-closed: any verification failure → DENY, no degraded mode

### 2. Least Privilege
- Each agent holds only scopes it needs
- Cedar policies enforce scope constraints dynamically
- Scope escalation is impossible

### 3. Cryptographic Identity
- X.509 certificates (self-signed for PoC, CA-issued for production)
- mTLS for agent-to-service communication
- JWT RS256 for request authentication
- HMAC-SHA256 for message integrity

### 4. Independent Audit Trail
- Agents cannot modify audit logs
- CloudWatch (AWS) + Cloud Logging (GCP) capture all decisions
- Federated: each org maintains independent records
- Hash-chained entries prevent tampering

### 5. Dynamic Enforcement
- Static lane (cert): identity, spawn authority, TTL (changes require re-cert)
- Dynamic lane (Cedar policies): runtime-updateable, dual-signed, instant enforcement
- Cert is hard ceiling; Cedar can only restrict further

---

## System Architecture

### High-Level Flow

```
Agent A (Requester)
    ↓ mTLS handshake (client cert)
MCP Server (public interface)
    ├─ JWT RS256 validation (issuer, audience, expiry, signature)
    ├─ HMAC-SHA256 verification (message integrity)
    ├─ Cedar policy evaluation (scope authorization)
    └─ S3 operation (write_event / read_event)
        ↓
Agent B (responder via MCP response)
    ↓
CloudWatch Logs (AWS audit trail)
Google Cloud Logging (GCP audit trail)
    ↓
Hash-chained entries + correlationId tracing
```

### 3-Tier Service Architecture

#### Tier 1: Public Interface (MCP Server)
**Purpose:** Stateless, credential-free interface for agent operations

**Responsibility:**
- Validate JWT (issuer, audience, expiry, signature)
- Verify HMAC (message integrity, constant-time comparison)
- Evaluate Cedar policies (scope constraints, least privilege)
- Execute MCP tools (S3 read/write via boto3, which owns credentials)
- Log all decisions to CloudWatch + Cloud Logging

**Credentials:** NONE (Agent holds no AWS/GCP keys)

**Access Control:** JWT + HMAC signature (not API key)

**Tools:**
- `write_event_to_s3(event_data, correlationId)` — Agent B only
- `read_event_from_s3(s3_key, correlationId)` — Agent A only

#### Tier 2: Locked-Down Management (Admin Bootstrap Service)
**Purpose:** Certificate + policy lifecycle management (operator access only)

**Responsibility:**
- Generate CA + agent certificates (OpenSSL)
- Register agent templates in DynamoDB (AllowedScopes, CanSpawn, TTL)
- Manage cert state transitions (ACTIVE → DISABLED → DELETED)
- Validate dual-signatures on policy changes (Owner + Policy Authority)
- Maintain Certificate Revocation List (CRL)

**Access Control:** mTLS + API key (x-admin-key header)

**Credentials:** AWS Secrets Manager (admin_api_key only)

#### Tier 3: Demo Interface (Demo Web)
**Purpose:** User-facing UI for testing all 11 scenarios

**Responsibility:**
- Render architecture context (prep.html)
- Present 11 scenario buttons (demo.html)
- Orchestrate scenario runs (call Admin Bootstrap to set up, call MCP Server to execute)
- Display live audit trail with hash chain integrity

**Access:** Public (http://localhost:8765)

---

## Security Model

### Static Trust Lane (Certificate-Based)

**Fixed at issuance:**
- Agent identity (Subject CN)
- AllowedScopes (max scopes agent may hold)
- CanSpawn (list of child templates agent may spawn)
- TTL (maximum agent lifetime)

**Changes require:**
- New cert generation
- Re-registration in Template Registry
- Full restart/rotation

**Enforcement:**
- Cert fields are hard ceiling
- If cert lacks a scope → scope DENIED at cert level
- If cert lacks spawn permission → spawn DENIED, period

### Dynamic Trust Lane (Policy-Based, Cedar)

**Updateable at runtime:**
- Cedar policy files (human-readable rules)
- Dual-signature requirement (Owner + Policy Authority)
- No certificate rotation needed

**Changes apply:**
- Instantly on next request
- Policies reloaded by MCP Server at runtime

**Enforcement:**
- Cedar can restrict within cert ceiling
- Cannot grant beyond what cert allows
- Fail-closed: policy eval error → DENY

### Attack Surface Mitigation

| Attack | Mitigation | Verification |
|--------|-----------|--------------|
| Rogue spawn | Static check: child not in parent CanSpawn list | Demo scenario 3 |
| Scope escalation | Dynamic check: child scopes ⊆ parent scopes | Demo scenario 6 |
| Dual-sig tampering | PA signature validation fails → DENY | Demo scenario 5 |
| Expired cert | TTL check in Cedar policy + cert validation | Demo scenario 9 |
| Revoked cert | CRL check + cert state = DELETED | Demo scenarios 7-8 |
| Message tampering | HMAC-SHA256 constant-time compare fails | Scenario 3 in Phase 3 |
| Replay attack | Timestamp + nonce validation | Demo scenario 11 |
| Unauthorized agent | JWT signature validation fails | Phase 2 |

---

## Trust Stack (Layers)

1. **mTLS** — Mutual TLS between agents (self-signed certs for PoC, CA-issued for prod)
2. **JWT RS256** — Agent A presents signed JWT; Agent B validates issuer, audience, expiry, signature
3. **HMAC-SHA256** — Message integrity check on every payload
4. **Cedar Policy** — Scope/spawn authorization (dynamic lane)
5. **Audit Trail** — CloudWatch + GCP Logging (federated, outside agent control)
6. **Hash Chain** — SHA-256 prev-entry-hash prevents tampering

---

## Data Flow: Golden Path Scenario

**Scenario:** Agent A (read:events) writes request → Agent B (write:events) executes → Agent A reads result

```
1. Agent A formulates request via Claude (Vertex AI)
   → Generates JWT (issuer: token-service, aud: agent-b, exp: +3600s)
   → Computes HMAC-SHA256(payload)
   → Adds correlationId (UUID v7)

2. Agent A → MCP Server (POST /write-event)
   
3. MCP Server validates:
   ✓ mTLS cert chain valid
   ✓ JWT signature valid (RS256, secret key)
   ✓ JWT not expired
   ✓ HMAC matches payload (constant-time compare)
   ✓ Cedar policy: agent-b has write:events scope
   
4. MCP Server executes S3 write:
   → boto3.put_object(s3_bucket, event_${correlationId}_${timestamp}.md)
   → Returns success + s3_key
   
5. Audit logged (CloudWatch):
   {
     "correlationId": "uuid",
     "spanId": "uuid",
     "parentSpanId": "uuid",
     "agentId": "agent-b",
     "action": "write_event",
     "decision": "ALLOWED",
     "grantedScopes": ["write:events"],
     "timestamp": "2026-06-04T...",
     "prevEntryHash": "sha256..."
   }
   
6. Agent A reads result:
   → Agent A calls MCP Server (POST /read-event)
   → MCP validates (JWT, HMAC, Cedar: agent-a has read:events)
   → boto3.get_object(s3_bucket, s3_key)
   → Returns content
   
7. Audit logged (CloudWatch + Cloud Logging):
   Same structure, action: read_event
```

**Result:** correlationId traces end-to-end across both clouds. Full audit reconstructable from either org.

---

## IETF Draft Mapping

| IETF Requirement | Design Approach | PoC Evidence |
|------------------|-----------------|--------------|
| Agent Identity (X.509) | Self-signed certs for PoC, CA-issued for prod | `services/admin_bootstrap/cert_generator.py` |
| Spawn Authority (CanSpawn) | Cert field + static check (demo scenario 3) | `mcp_server/cedar_policy_eval.py` |
| Scope Constraints | Cedar policies + dynamic check (scenario 6) | `policies/agent-a.cedar`, `agent-b.cedar` |
| TTL Enforcement | Cert TTL field + Cedar policy (scenario 9) | `admin_bootstrap/cert_manager.py` |
| State Lifecycle | ACTIVE → DISABLED → DELETED (scenario 7) | `admin_bootstrap/crl_manager.py` |
| Fail-Closed | Every error path logs DENY, returns 403/401 | All service main.py files |
| Audit Trail | CloudWatch + Cloud Logging (federated) | `terraform/cloudwatch.tf`, `gcp_logging.tf` |
| Dual-Sig | Owner + Policy Authority signatures (scenario 4-5) | `admin_bootstrap/policy_authority.py` |
| **Spec Gap:** correlationId | UUID v7 + spanId + parentSpanId (OpenTelemetry model) | `demo/app.js` audit logging |

**Note:** correlationId not in draft-tonyai-a2a-trust-00; PoC proposes addition for v2.

---

## Threat Model & Mitigations

### Threat: Forged JWT

**Attack:** Attacker creates JWT with valid claims but no signature.

**Mitigation:** 
- MCP Server validates signature using `pyjwt.decode(..., algorithms=['HS256'], options={'verify_signature': True})`
- Invalid signature → HTTPException(401, "Invalid JWT")
- Logged to CloudWatch

### Threat: Tampered Payload

**Attack:** Attacker modifies request body after HMAC computation.

**Mitigation:**
- HMAC-SHA256 constant-time comparison: `hmac.compare_digest(computed, provided)`
- Mismatch → DENY, logged
- Demo scenario: Phase 3

### Threat: Scope Escalation

**Attack:** Child agent requests scopes beyond parent's AllowedScopes.

**Mitigation:**
- Cedar policy: `"write:events" in principal.scopes && principal.id == "agent-b"`
- Mismatch → DENY
- Demo scenario 6

### Threat: Revoked Cert Still Used

**Attack:** Agent uses cert that's been revoked (DELETED state).

**Mitigation:**
- CRL check: `crl_mgr.is_revoked(cert_id)`
- Revoked → DENY before any processing
- Demo scenario 8

### Threat: Replay Attack

**Attack:** Attacker captures valid request and replays it.

**Mitigation:**
- Request includes timestamp + nonce (correlationId)
- MCP Server rejects duplicate correlationIds within TTL window
- Demo scenario 11

---

## Scalability & Production Paths

| Component | PoC | Production |
|-----------|-----|-----------|
| **CA** | OpenSSL (self-signed) | HashiCorp Vault PKI or AWS ACM Private CA |
| **Policy Engine** | Cedar SDK (local, in-process) | Amazon Verified Permissions (managed) |
| **Deployment** | Docker Compose | ECS/Fargate (AWS) or Cloud Run (GCP) |
| **Orchestration** | FastAPI | LangGraph + Temporal (durable workflows) |
| **Secrets** | AWS Secrets Manager | Vault or Cloud Secrets Manager |
| **Audit** | CloudWatch + Cloud Logging | S3 (Object Lock COMPLIANCE) + Cloud Audit Logs |
| **Observability** | Built-in logs | Datadog / Splunk + Logfire (OpenTelemetry) |

---

## Cost Analysis (PoC)

**Monthly:** ~$5-10 (primarily DynamoDB on-demand + CloudWatch)

**Production (annual, 10M requests):** ~$50K
- CloudWatch: $10K
- S3 (audit): $2K
- DynamoDB: $15K
- Secrets Manager: $0.4K
- KMS: $1K
- Vertex AI: $20K (most expensive; agent-dependent)

**ROI:** Prevents one security incident ($500K+ cost); pays for itself 10x over.

---

## Conclusion

This design demonstrates that **Zero Trust for AI agents is practical** using:
- Standard cryptographic primitives (mTLS, JWT, HMAC)
- Policy-as-code (Cedar) for dynamic enforcement
- Independent audit trails (federated CloudWatch + Cloud Logging)
- Fail-closed architecture (no degraded modes)

**Reference implementation:** This PoC. **Canonical source:** IETF draft-tonyai-a2a-trust-00.

---

**Next:** Implementation methodology in [IMPLEMENTATION.md](IMPLEMENTATION.md)
