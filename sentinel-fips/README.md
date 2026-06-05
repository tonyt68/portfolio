# Sentinel FIPS — ReBAC + FIPS 140-3 Boundary POC on AWS

An agentic security response system that gates **cryptographic operations** behind a live ReBAC (Relationship-Based Access Control) authorization chain — running entirely on AWS, with every component earmarked for the path to true FIPS 140-3 Level 3.

Successor to the [Sentinel AI ReBAC POC](https://github.com/tonyai-portfolio/sentinel-ai). Sentinel proved the chain-check pattern locally on Minikube + Redis. **Sentinel FIPS** moves it to AWS-native services and adds a FIPS-validated cryptographic boundary as the thing being protected.

---

## The Big Value — Why ReBAC Wins

> **The enterprise authorization problem is not authentication. It is policy sprawl.**

Every org eventually hits the same wall: thousands of IDP users, hundreds of services, and a flat IAM role for every combination. N users × M resources = N×M roles, N×M policy documents, N×M places to forget to revoke access when someone changes teams or a service is deprecated.

**ReBAC replaces that explosion with a graph.**

| Scenario | Flat IAM (RBAC) | ReBAC (Sentinel) |
|---|---|---|
| Tony moves from platform-team to infra-team | Edit 3 roles, detach 2 policies, hope nothing was missed | Delete 1 graph edge: `tony#member_of → platform-team` |
| New service onboards and needs signing rights | Create new role, write new policy, attach to service identity | Add 1 graph edge: `new-svc#delegate_of → tony` |
| Revoke all access after an incident | Hunt every role across every account | Delete the subject's edges — chain breaks everywhere simultaneously |
| Audit who had access at 2am last Tuesday | Parse IAM policy versions across accounts | CloudTrail timestamp on the DynamoDB write that added or removed the edge |

**One authorization system covers both IDP user access and service-to-service:**

```
# Human → resource (IDP user access)
tony  →  member_of  →  platform-team  →  can_sign  →  idp-config-bundle

# Service → service (workload identity)
payment-svc  →  delegate_of  →  auth-svc  →  member_of  →  infra-team  →  can_sign  →  cert-bundle
```

Same graph. Same Cedar policy. Same KMS boundary. Same audit trail. The authorization system doesn't care whether the principal is a human, a Lambda, or a Kubernetes pod — it walks the graph.

**The policy doesn't change when the org changes. The graph does.**
And every graph change is a single DynamoDB write with a CloudTrail timestamp.

---

## Table of Contents

- [The Big Value — Why ReBAC Wins](#the-big-value--why-rebac-wins)
- [Versioning & Leadership Decision](#versioning--leadership-decision)
- [Document Index](#document-index)
- [What It Does](#what-it-does)
- [FIPS 140-3 Level 3 — Why It Matters](#fips-140-3-level-3--why-it-matters)
- [The Earmark Legend](#the-earmark-legend)
- [ReBAC Authorization Model](#rebac-authorization-model)
- [Service Identity — How a Service Proves Who It Is](#service-identity--how-a-service-proves-who-it-is)
- [Architecture](#architecture)
- [Component Breakdown](#component-breakdown)
- [Agentic Flow](#agentic-flow)
- [Revoked Access Scenario](#revoked-access-scenario)
- [Demo Flows](#demo-flows)
- [Setup (CloudShell)](#setup-cloudshell)
- [Path to True FIPS 140-3 Level 3](#path-to-true-fips-140-3-level-3)
- [Stack](#stack)

---

## Versioning & Leadership Decision

**This is v1.** Status: deployable to dev/internal-pilot accounts today. Stack-at-rest cost ~$1/month.

**Engineering advises; leadership decides the FIPS posture.** The hardening level is a tiered investment — not a binary "compliant / not compliant." See the four-tier decision matrix in [FIPS-140-3.md § Leadership Decision Matrix](FIPS-140-3.md#leadership-decision-matrix). v1 corresponds to **Tier 0** (POC/demo) with hooks already in place for **Tier 1** (internal pilot): dry-run mode, sign-Lambda re-check, structural assertions, pattern alarms.

**Roadmap shape (not a timeline — a menu):**

| Tier | What | Cost/mo | Effort |
|---|---|---|---|
| 0 (this v1) | Architectural pattern, fail-closed posture, audit immutability | ~$1 | done |
| 1 | Internal pilot — PrivateLink, Bedrock, Identity Center MFA | ~$50–150 | 2–4 weeks |
| 2 | FedRAMP Moderate — GovCloud, hardware MFA, AWS-LC FIPS, ATO docs | ~$500–2k | 3–6 months |
| 3 | True FIPS 140-3 L3 — CloudHSM, Nitro Enclaves, YubiKey FIPS | ~$3k–10k | 6–12 months |

**AI in the loop?** The orchestrator uses Claude Opus 4.7 — bounded, observed, replaceable. See [AI-GOVERNANCE.md](AI-GOVERNANCE.md) for the full bounded-autonomy / observability / dry-run / replaceability story. Skeptics can verify every claim by running it in dry-run.

---

## Document Index

| Doc | Purpose | Audience |
|---|---|---|
| **[README.md](README.md)** | This file. Architecture and POC overview. | Everyone |
| **[SETUP.md](SETUP.md)** | CloudShell deployment steps for AWS. | Operator deploying the stack |
| **[DEMO.md](DEMO.md)** | 2:15 video script for the demo. | Tony recording the demo |
| **[FIPS-140-3.md](FIPS-140-3.md)** | Section-by-section FIPS 140-3 study companion + Leadership Decision Matrix. | Tony studying / interview prep / leadership scoping |
| **[TRADEOFFS.md](TRADEOFFS.md)** | "Why X and not Y?" cheat sheet — 14 design decisions in formula structure. | Tony for interview drilling / skeptics asking *"why this stack?"* |
| **[AI-GOVERNANCE.md](AI-GOVERNANCE.md)** | Bounded autonomy, observability, dry-run, prompt-injection defense, skeptic Q&A. | Senior managers / anyone uneasy about AI in security pipeline |
| **[EXECUTIVE-BRIEF.md](EXECUTIVE-BRIEF.md)** | Why this is needed, FedRAMP driver, what we built, what production looks like, the ask. | Executives, decision-makers, budget holders |
| **[FEDRAMP-ALIGNMENT.md](FEDRAMP-ALIGNMENT.md)** | Plain-language FedRAMP control descriptions and how Sentinel meets each one. | Compliance officers, security architects, auditors |
| **[sentinel-mcp-poc](../sentinel-mcp-poc/MCP-TOOLKIT.md)** | Companion PoC — AWS MCP server setup, Sentinel audit tools, security model, interview Q&A. Lives in its own project. | AI enablement engineers, interview prep |

---

## What It Does

When a security finding arrives (e.g. an IDP service requests a signature on a privileged config bundle), Sentinel FIPS:

1. **Verifies authorization** — Lambda authorizer traverses the ReBAC graph in DynamoDB and asks Verified Permissions (Cedar) for a `permit` / `forbid` decision.
2. **Reasons** about the request using Claude Opus 4.7 (Anthropic API key in Secrets Manager).
3. **Acts inside the cryptographic boundary** — KMS performs the sign/decrypt op via a FIPS-validated endpoint. Key material never leaves the HSM (Hardware Security Module).
4. **Audits** — every decision streams to CloudTrail → S3 (Object Lock).
5. **Escalates** — if the authorization chain is broken, EventBridge fires a `CRITICAL` alert via SNS instead of executing the op.

The key insight: the cryptographic operation is **gated by a relationship chain in a graph**. A revoked edge stops Sentinel cold — no signature, no decryption, no key release. Same posture as the predecessor (a local Minikube proof-of-concept that validated the chain-check pattern), but the boundary is now AWS-validated cryptographic hardware.

---

## FIPS 140-3 Level 3 — Why It Matters

FIPS 140-3 is the U.S. government standard for cryptographic modules. **Level 3** adds:

- **Physical tamper-evidence and tamper-response** — opening the box wipes the keys (zeroization).
- **Identity-based authentication** — operators authenticate as themselves, not generic roles.
- **Strict separation of plaintext keys and unprotected data paths** — key material never crosses an unprotected boundary.

This POC demonstrates the **architectural pattern** — ReBAC chain → policy decision → crypto op inside a validated boundary → tamper-evident audit trail — using AWS services that are accessible on a free-tier account. Every component that falls short of true Level 3 is flagged with **🔒 FIPS-3-GAP** so the production path is documented inline.

---

## The Earmark Legend

Two earmark tags are used throughout this README and the CloudFormation comments:

| Tag | Meaning |
|---|---|
| **🔒 FIPS-3-GAP** | What this v1 component is missing to hit true FIPS 140-3 Level 3, and the AWS service that would close the gap. |
| **📦 PROD-GAP** | What's missing for production scale (not L3 — just realism). |

A consolidated list is at the bottom: [Path to True FIPS 140-3 Level 3](#path-to-true-fips-140-3-level-3).

---

## ReBAC Authorization Model

Access is governed by **relationship chains**, not flat roles. The authorizer must find an unbroken path through the graph before KMS will be invoked.

```
sentinel-agent  --delegate_of-->  tony
tony            --member_of-->    platform-team
platform-team   --can_sign-->     idp-config-bundle
```

**ALLOWED:** Full chain intact → KMS signs the bundle inside the FIPS boundary.
**DENIED:** Any link revoked (e.g. tony's membership removed) → chain breaks → CRITICAL escalation, no signature issued.

Cedar policies live alongside the graph: relationship traversal answers *who is connected to what*, Cedar answers *what they're allowed to do*.

**Production provisioning (v2 path):** Graph nodes are service identities — IAM roles (Lambda execution roles, ECS task roles, IRSA for Kubernetes pods), not human users. The same IaC template (CloudFormation / Terraform) that provisions a service also writes its ReBAC tuple to DynamoDB via a Custom Resource Lambda. Decommission the service → stack deleted → tuple gone → chain broken on the next request. No SCIM, no user directory — service identity comes from IAM, relationship authorization comes from the graph.

---

## Service Identity — How a Service Proves Who It Is

ReBAC answers *"are you allowed?"* — but first the system must answer *"who are you?"* These are two separate concerns.

**On AWS (v1 and v2):**
Every Lambda, ECS task, and Kubernetes pod has an **IAM execution role**. AWS automatically signs every API call with that role's credentials — no passwords, no API keys, no secrets to rotate. IAM is the identity layer.

**The two-step check:**
```
Service calls API Gateway
  → IAM verifies the execution role (who are you?)
    → Authorizer walks the ReBAC graph (are you allowed?)
      → Cedar issues permit / forbid
        → KMS signs or escalates
```

**Service-to-service patterns (v2):**

| Pattern | How identity is proven |
|---|---|
| **IAM role** | Lambda/ECS assumes a role — AWS signs every call automatically |
| **JWT / OIDC** | Service presents a signed token — receiver validates the signature |
| **mTLS** | Both sides present certificates — mutual proof of identity |
| **SPIFFE / SPIRE** | Workload identity standard for Kubernetes — cryptographic identity per pod |

**The key insight:** IAM answers *"who are you?"* ReBAC answers *"what are you allowed to do?"* Both must pass. One without the other is incomplete.

---

## Architecture

```
┌────────────────────────┐
│   Security Finding     │
│   (IDP signing req.)   │
└───────────┬────────────┘
            │
            ▼
   ┌──────────────────┐
   │   CloudShell     │   ← human surface, runs demo.sh + client.py
   └────────┬─────────┘
            │ HTTPS (FIPS endpoint)
            ▼
   ┌──────────────────────┐
   │   API Gateway        │   🔒 FIPS-3-GAP: regional endpoint
   └────────┬─────────────┘
            ▼
   ┌──────────────────────────────────────────┐
   │   Lambda: orchestrator                   │
   │   Anthropic API (Claude Opus 4.7)        │   🔒 FIPS-3-GAP: AI inference
   │   Tool-use loop                          │
   └────┬──────────────┬──────────────┬───────┘
        │              │              │
        ▼              ▼              ▼
  ┌───────────┐  ┌───────────┐  ┌───────────────┐
  │  Lambda:  │  │  Lambda:  │  │ EventBridge   │
  │authorizer │  │   sign    │  │ → SNS (alert) │
  └─────┬─────┘  └─────┬─────┘  └───────────────┘
        │              │
        ▼              ▼
  ┌───────────┐  ┌───────────────┐
  │ DynamoDB  │  │ KMS           │   🔒 FIPS-3-GAP: 140-2 L3 → CloudHSM
  │ ReBAC     │  │ (FIPS endpt.) │
  └───────────┘  └───────────────┘
        │              │
        ▼              ▼
  ┌────────────────────────────┐
  │ Verified Permissions       │   ← Cedar policy decision
  └────────────────────────────┘
            │
            ▼
  ┌────────────────────────────┐
  │ CloudTrail → S3 (Object    │   ← tamper-evident audit
  │ Lock, COMPLIANCE mode)     │
  └────────────────────────────┘
```

---

## Component Breakdown

### `client.py` + `demo.sh` — The Human Surface
Runs in **AWS CloudShell** (free, browser, pre-authenticated to your account). `demo.sh` is a numbered menu for exercising all scenarios end-to-end (allow, deny, revoke, alert); `client.py` invokes the orchestrator Lambda over HTTPS.

### Lambda: `orchestrator` — The AI Agent
Anthropic SDK with Claude Opus 4.7 driving a tool-use loop. Tools are AWS-side (`check_authorization`, `sign_bundle`, `emit_alert`). API key fetched at cold-start from Secrets Manager. System prompt is **prompt-cached**.
- 🔒 **FIPS-3-GAP:** Inference happens at `api.anthropic.com`. For true L3 posture, swap to **Amazon Bedrock + Claude on AWS** with private endpoints and earmarked data residency.

### Lambda: `authorizer` — The ReBAC Chain Checker
Traverses DynamoDB ReBAC tuples via BFS (Breadth-First Search — fans out level by level through the relationship graph to find the shortest valid authorization chain), then submits the resolved entities to **Amazon Verified Permissions** for a Cedar `permit` / `forbid` decision. Returns the full chain in the response so the audit trail captures the *why*.
- 📦 **PROD-GAP:** DynamoDB single-table for relationship tuples is fine for a POC. Real ReBAC graphs at IDP scale belong in **Neptune** with Gremlin traversal.

### Lambda: `sign` — The Cryptographic Operation
Performs `kms:Sign` on a SHA-256 digest of the request payload using a CMK with FIPS-pinned `boto3` (`use_fips_endpoint=True`). Returns the signature. **The CMK never leaves KMS — only the signature crosses the boundary.**
- 🔒 **FIPS-3-GAP:** AWS KMS today uses FIPS 140-2 Level 3 validated HSMs (140-3 in progress). For true 140-3 L3 → **AWS CloudHSM** cluster (Marvell LiquidSecurity2, FIPS 140-3 L3 validated) backing a KMS Custom Key Store, or direct PKCS#11 from the Lambda.
- 🔒 **FIPS-3-GAP:** Lambda runtime uses the standard AWS-managed Python OpenSSL. For validated cryptography in the data path → **Nitro Enclaves** with attested enclaves and the **AWS-LC FIPS** module.

### DynamoDB — The ReBAC Graph Store
A single table `sentinel-rebac` keyed by `(subject, relation)` with `objects` as a string set. Mirrors the Redis Set layout used in the predecessor proof-of-concept; DynamoDB replaces Redis for managed, serverless scaling.

| PK (`subject#relation`) | `objects` (StringSet) |
|---|---|
| `sentinel-agent#delegate_of` | `["tony"]` |
| `tony#member_of` | `["platform-team"]` |
| `platform-team#can_sign` | `["idp-config-bundle"]` |

- 📦 **PROD-GAP:** Replace with **Neptune** for v2.

### Verified Permissions + Cedar — The Policy Engine
`PolicyStore` holds Cedar policies. The authorizer calls `IsAuthorized` with the principal/action/resource resolved from the graph. Cedar is open source (donated by AWS) — no vendor lock-in.

### S3 + CloudTrail — The Audit Trail
CloudTrail trail captures all `kms:*`, `verifiedpermissions:*`, and `lambda:Invoke*` events. Bucket has **Object Lock in COMPLIANCE mode** so audit logs are write-once-read-many.
- 🔒 **FIPS-3-GAP:** Object Lock COMPLIANCE mode satisfies tamper-evidence. For full L3 audit posture → also enable **CloudTrail log file integrity validation** (SHA-256 hash chain) and store digests in a separate account.

### EventBridge + SNS — The Escalation Channel
On `REBAC_DENIED` or `CHAIN_BROKEN`, the orchestrator emits a `Sentinel.AuthChainBroken` event. EventBridge rule routes to SNS, which emails the on-call subscriber.

### KMS — The Cryptographic Boundary (v1)
Customer-managed CMK with key policy restricting `kms:Sign` to the `sign` Lambda's role. SDK calls forced to `kms-fips.<region>.amazonaws.com`.
- 🔒 **FIPS-3-GAP** (canonical): Swap KMS for **CloudHSM**. See [Path to True FIPS 140-3 Level 3](#path-to-true-fips-140-3-level-3) below.

### Region
**us-east-1** for service breadth and free-tier coverage.
- 🔒 **FIPS-3-GAP:** True L3 production → **AWS GovCloud (us-gov-west-1 / us-gov-east-1)** with FedRAMP High alignment and US-persons-only operator access.

---

## Agentic Flow

```
Finding         Claude          authorizer       DynamoDB      Verified     KMS       CloudTrail
  │              │                  │              │            Perm.        │             │
  ├─ sign req. ─→│                  │              │              │          │             │
  │              ├─ check_auth ────→│              │              │          │             │
  │              │                  ├─ BFS chain ─→│              │          │             │
  │              │                  ├─ IsAuthorized ─────────────→│          │             │
  │              │                  │              │          ALLOW          │             │
  │              │←─ chain + permit ┤              │              │          │             │
  │              ├─ sign_bundle ────────────────────────────────────────────→│             │
  │              │                  │              │              │      sign│             │
  │              │←──────────────────── signature ────────────────────────--─┤             │
  │              │                  │              │              │          │             │
  │              ├─ emit_audit ───────────────────────────────────────────────────────────→│
  │←─ verdict ───┤                  │              │              │          │             │
```

---

## Revoked Access Scenario

```
Admin         DynamoDB      authorizer        Claude        EventBridge → SNS
  │               │              │              │                  │
  ├─ REVOKE tony's membership ──→│              │                  │
  │               │ [chain broken]               │                 │
  │               │              ├─ FORBID ────→│                  │
  │               │              │              ├─ emit_alert ────→│
  │               │              │              │                  ├─→ on-call email
  │←──────────────── CRITICAL: auth chain broken — no signature issued ─┤
```

<span style="background-color: #ffdddd; display: block; padding: 4px 8px;">KMS is **never invoked** when the chain is broken. The Lambda role for `sign` only allows `kms:Sign` when called by the orchestrator with a successful authorizer response — defense in depth.</span>

---

## Demo Flows

### ALLOWED Flow
```
1 → Deploy stack
2 → Seed ReBAC graph
3 → Run Sentinel  →  REBAC_ALLOWED ✓  →  signature issued
6 → Verify graph  →  chain INTACT 🟢
```

### DENIED Flow
```
1 → Deploy stack
2 → Seed ReBAC graph
3 → Run Sentinel  →  REBAC_ALLOWED ✓  →  signature issued
4 → Revoke Tony's membership
3 → Run Sentinel  →  REBAC_DENIED 🔴  →  CRITICAL alert, no signature
5 → Restore Tony's membership
3 → Run Sentinel  →  REBAC_ALLOWED ✓  →  signature issued
```

**Production equivalent:** Step 4 (revoke) maps to decommissioning a service — the IaC stack is deleted, the DynamoDB tuple is removed by the Custom Resource Lambda, and the next request is denied immediately. No redeploy, no code change, no waiting for a cache to expire.

---

## Setup (CloudShell)

```bash
# 1. Open AWS CloudShell in the AWS Console (us-east-1)

# 2. Upload the project (no git repo required)
#    CloudShell → Actions → Upload file → upload sentinel-fips.zip → then:
unzip sentinel-fips.zip && cd sentinel-fips

# 3a. Store the Anthropic API key in Secrets Manager BEFORE deploying
#     (keeps the key out of samconfig.toml and terminal history)
aws secretsmanager create-secret \
  --name sentinel-fips/anthropic-api-key \
  --secret-string "<paste key here — delete from history after>"

# 3b. Deploy the stack — key is already in Secrets Manager, no prompt needed
sam build
sam deploy --guided
#   Stack name:    sentinel-fips
#   Region:        us-east-1
#   AnthropicApiKey: (leave blank — stack reads from Secrets Manager by ARN)
#   AlertEmail:    <your email — confirm SNS subscription>
#   DryRun:        true   ← recommended for first deploy: see what would happen, no KMS/SNS side effects

# 4. Run the demo menu — choose 2 to seed, then 3 to run
bash demo.sh

# 6. When done, tear it all down
sam delete
```

**Cost:** Stack at rest is ~$0/month (KMS CMK is $1/mo, DynamoDB on-demand is $0 idle, Lambda + API GW free tier). The expensive components (CloudHSM, Neptune) are **not** in the v1 stack — they're earmarked.

---

## Path to True FIPS 140-3 Level 3

> 👉 **For the tiered investment view (cost / effort / scope per tier), see [FIPS-140-3.md § Leadership Decision Matrix](FIPS-140-3.md#leadership-decision-matrix).** The list below is the per-component reference; the matrix is the leadership-facing view.

Consolidated list of every 🔒 FIPS-3-GAP and the production swap.

| # | v1 Component | 🔒 FIPS-3-GAP | True L3 Swap |
|---|---|---|---|
| 1 | KMS CMK | HSMs are FIPS 140-2 L3 validated (140-3 in progress) | **CloudHSM** cluster (Marvell LiquidSecurity2, 140-3 L3) backing a KMS Custom Key Store |
| 2 | Lambda runtime | Standard AWS-managed Python crypto stack | **Nitro Enclaves** with attestation + **AWS-LC FIPS** module |
| 3 | Region | us-east-1 (commercial) | **AWS GovCloud** (us-gov-west-1) with FedRAMP High |
| 4 | API Gateway | Regional endpoint, public TLS | **VPC endpoint** + private API + AWS PrivateLink |
| 5 | Anthropic API | Inference at `api.anthropic.com` (off-AWS) | **Bedrock + Claude on AWS** with private endpoints |
| 6 | CloudTrail | Object Lock COMPLIANCE | + **log file integrity validation** + cross-account digest archive |
| 7 | Operator auth | IAM roles | **IAM Identity Center** + hardware MFA (FIPS 140-3 L3 token, e.g. YubiKey FIPS) |
| 8 | SDK build | Standard `boto3` over OpenSSL | `boto3` over **AWS-LC FIPS** validated build |

📦 **PROD-GAP** (not L3 — just scale realism):

| # | v1 Component | 📦 PROD-GAP | Production Swap |
|---|---|---|---|
| 1 | DynamoDB ReBAC | Single-table key/value | **Neptune** with Gremlin |
| 2 | SAM stack | Single-region, single-account | Multi-region active-active, separate audit account |
| 3 | Demo entrypoint | CloudShell + bash menu | EKS workload behind SQS trigger |

---

## Stack

| Layer | v1 (this POC, free tier) | v2 (true FIPS 140-3 L3) |
|---|---|---|
| AI Model | Claude Opus 4.7 (Anthropic API) | Bedrock + Claude on AWS |
| AI Auth | Anthropic API key in Secrets Manager | IAM (Bedrock) |
| Authorization | DynamoDB + Verified Permissions / Cedar | Neptune + Verified Permissions / Cedar |
| Crypto Boundary | KMS (FIPS 140-2 L3 HSMs, FIPS endpoints) | CloudHSM (FIPS 140-3 L3 HSMs) + Nitro Enclaves |
| Audit Trail | CloudTrail → S3 Object Lock COMPLIANCE | + log file integrity + separate audit account |
| Live Alerts | EventBridge → SNS | + Security Hub + GuardDuty integration |
| Orchestration | Lambda + API Gateway | EKS + Step Functions, SQS-triggered |
| Region | us-east-1 | GovCloud (us-gov-west-1) |
| IaC | CloudFormation / SAM | CloudFormation / SAM (same template, different account) |
| Demo Surface | CloudShell + bash + Python | Internal portal + ServiceNow integration |
| Runtime | Python 3.12 | Python 3.12 on Nitro Enclave + AWS-LC FIPS |

---

## Built By

Powered by **TonyAI** — assisted by **Claude**
