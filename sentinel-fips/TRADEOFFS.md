# Sentinel FIPS — Tradeoffs Cheat Sheet

Every "why X and not Y?" question for this POC, structured the same way the system itself works: **enumerate the chain, name the decision, log the why, declare the alarm condition.**

> **The formula** — four lines, ~30 seconds spoken:
>
> 1. **Considered:** alternatives I actually weighed
> 2. **Picked:** the choice
> 3. **Why:** the deciding factor (a constraint or a property, not a preference)
> 4. **Swap when:** the condition that flips the answer
>
> The `Swap when:` line is the escape valve. When you blank on the *why*, fall back to *"if [condition] didn't hold, I'd reach for Y"* — that's **alerting on the constraint** instead of bluffing. Same posture as the POC: when the chain breaks, you don't sign, you alert.

---

## Authorization layer

### 1. Cedar vs OPA

1. **Considered:** OPA (Rego), Cedar.
2. **Picked:** Cedar.
3. **Why:** Cedar's evaluator has formal verification (OPA's does not); Verified Permissions is a managed AWS control plane that returns audit-grade `determiningPolicies` per call without standing up Rego servers; Cedar's principal/action/resource/context model maps cleanly onto IAM, which already authenticates into KMS.
4. **Swap when:** the policy surface goes multi-cloud or escapes AWS. OPA is correct when policy lives next to Kubernetes admission control or in front of non-AWS services.

### 2. Verified Permissions (managed) vs self-hosted Cedar

1. **Considered:** self-hosted Cedar in a Lambda layer or sidecar; Amazon Verified Permissions.
2. **Picked:** Verified Permissions.
3. **Why:** managed control plane gives policy versioning, audit-grade `determiningPolicies` in API responses, and direct integration with IAM principals — saves us standing up policy distribution and signing.
4. **Swap when:** very high RPS where AVP's per-call latency bites, air-gapped environments where you can't call out, or when policy must live inside a Nitro Enclave attestation chain.

### 3. ReBAC vs RBAC vs ABAC

1. **Considered:** Role-based (RBAC), attribute-based (ABAC), relationship-based (ReBAC).
2. **Picked:** ReBAC.
3. **Why:** relationships compose — *"service A is delegate of person B who is member of team C which can sign resource D"* expresses real organizational structure that RBAC flattens into role explosion; revoking the **relationship** (B's membership in C) is the right granularity, more precise than swapping a role or mutating an attribute.
4. **Swap when:** the org is flat and static (RBAC is faster and simpler); or when authorization is governed by **data attributes** (PHI, classification level, geo) rather than org structure (ABAC).

### 4. DynamoDB vs Neptune (for the graph)

1. **Considered:** DynamoDB single-table, Amazon Neptune (openCypher/Gremlin/SPARQL).
2. **Picked:** DynamoDB for v1.
3. **Why:** ReBAC tuples at POC scale fit a `(subject#relation) → objects` key/value pattern; on-demand billing is $0 idle; SAM template manages it natively; BFS in 20 lines of Python is faster than provisioning Neptune for three tuples.
4. **Swap when:** graph traversals exceed ~5 hops, query patterns require a graph query language, or graph size exceeds DynamoDB's per-item limits — Neptune is correct at IDP/enterprise scale (📦 PROD-GAP #1 in [README.md](README.md)).

   What the swap buys — the entire BFS in v1 collapses to one Cypher query on Neptune:
   ```cypher
   MATCH (a:Service {id:'sentinel-agent'})-[:delegate_of]->(b)
         -[:member_of]->(c)-[:can_sign]->(d:Bundle {id:'idp-config-bundle'})
   RETURN a, b, c, d
   ```
   Neptune handles the traversal, depth, and path validity natively. No hand-rolled BFS, no `BatchGetItem`, no visited-set bookkeeping. At enterprise scale (thousands of matters, nested team hierarchies), this is the correct tool.

---

## Crypto layer

### 5. KMS vs CloudHSM

1. **Considered:** AWS KMS default keys, KMS Custom Key Store backed by CloudHSM, direct CloudHSM via PKCS#11.
2. **Picked:** KMS for v1.
3. **Why:** $1/mo per CMK, FIPS endpoints available out of the box, validated FIPS 140-2 Level 3 HSMs underneath, IAM-native access control, no cluster to manage.
4. **Swap when:** **140-3 L3 cert** is a literal contractual requirement (federal), single-tenant HSM is mandated, or you need direct PKCS#11 from a Nitro Enclave. CloudHSM with Marvell LiquidSecurity2 cards is the path — 🔒 FIPS-3-GAP #1 in [FIPS-140-3.md](FIPS-140-3.md#poc--true-l3-consolidated-swap-list).

### 6. RSA-PSS vs ECDSA

1. **Considered:** RSA-2048 with PSS padding, ECDSA over P-256.
2. **Picked:** RSA-PSS.
3. **Why:** broadly supported by federal verifiers; PSS is **probabilistic** (each signature is unique even on identical input — better than PKCS#1 v1.5 deterministic padding); 2048-bit RSA meets NIST SP 800-131A through 2030.
4. **Swap when:** signature size matters on the wire (ECDSA P-256 sigs are ~2-3× smaller); embedded/mobile verifier ecosystems where ECDSA is the norm; or when post-quantum migration is imminent (both have PQC paths but ECDSA is more common in hybrid schemes).

### 7. Object Lock COMPLIANCE vs GOVERNANCE

1. **Considered:** S3 Object Lock GOVERNANCE mode, S3 Object Lock COMPLIANCE mode.
2. **Picked:** COMPLIANCE.
3. **Why:** matches the **adversarial-audit posture** required by FIPS § 7.11 — *"audit must be tamper-evident even against insider threat including the root account."* GOVERNANCE permits `s3:BypassGovernanceRetention` for high-privilege users; a malicious admin (or compromised root key) could redact the audit trail. COMPLIANCE locks it for everyone, including AWS root, until retention elapses.
4. **Swap when:** the audit isn't adversarial — short-retention dev environments where ops needs to delete on cleanup and there's no compliance bond.

---

## Orchestration layer

### 8. LLM agent vs Step Functions

1. **Considered:** AWS Step Functions (ASL state machine), an LLM-driven tool-use loop.
2. **Picked:** LLM (Claude Opus 4.7).
3. **Why:** **extensibility** — adding a new tool (`rotate_key`, `quarantine_principal`, `open_ticket`) is system prompt + handler, not a state-graph rewrite; the protocol description reads like a runbook in English, which is also the right artifact for SOC reviewers; the audit value is identical (tool trace == execution history).
4. **Swap when:** state space is **closed and known** (deterministic ETL, retry-heavy pipelines), or when an auditor demands bit-for-bit determinism on the orchestration path itself (not just the security decision). Step Functions earn their complexity at fully-enumerated flows.

### 9. Anthropic API vs Bedrock

1. **Considered:** Anthropic API direct (`api.anthropic.com`), Bedrock + Claude on AWS.
2. **Picked:** Anthropic API for v1.
3. **Why:** free-tier accessibility, no Bedrock model-access provisioning friction, identical model behavior at the inference level.
4. **Swap when:** **data residency** matters (FedRAMP, FIPS L3 posture — request payloads must not leave AWS), or IAM-native auth is preferred over API-key-in-Secrets-Manager. Bedrock is the production swap, called out as 🔒 FIPS-3-GAP #5.

   The swap is one parameter override — `AnthropicBaseUrl` is configurable in `template.yaml` (default `https://api.anthropic.com`). Pointing it at a Bedrock-compatible endpoint or proxy requires no code change.

### 10. Anthropic SDK tool-use vs MCP server

1. **Considered:** MCP (Model Context Protocol) server to expose tools to Claude, Anthropic SDK native tool-use.
2. **Picked:** Anthropic SDK native tool-use.
3. **Why:** MCP requires a running server the AI client connects to — another service to deploy, secure, and keep inside the FedRAMP boundary. The Anthropic SDK's `tool_use` / `tool_result` message format delivers identical capability natively inside the Lambda with no extra infrastructure. Three fixed tools in one Lambda is not the problem MCP solves.
4. **Swap when:** the toolset is large, shared across multiple AI clients, or needs to be dynamically discoverable at runtime — MCP earns its complexity there. Also correct when building developer tooling (Claude Desktop, Claude Code, IDE integrations) where MCP is the standard integration pattern.

### 11. Lambda vs ECS / EKS

1. **Considered:** AWS Lambda, Fargate (ECS), EKS pods.
2. **Picked:** Lambda.
3. **Why:** signing requests are low-volume and event-driven; Lambda's per-invoke billing means $0 idle cost; cold-start cost (~500ms) is acceptable for a security-gate workload that already includes a Cedar call and a KMS sign; tight IAM integration; no cluster ops.
4. **Swap when:** sustained high RPS makes per-invoke pricing worse than running pods (~hundreds of req/sec sustained), long-running operations exceed 15-minute Lambda max, or running inside Nitro Enclaves for L3 (then it's EC2-on-Enclaves or Fargate-on-Enclaves, not Lambda).

---

## IaC, audit, identity

### 11. SAM vs CDK vs Terraform

1. **Considered:** AWS SAM, AWS CDK, HashiCorp Terraform.
2. **Picked:** SAM.
3. **Why:** native CloudFormation transform — same engine AWS uses internally, no additional language layer between intent and what deploys; SAM-specific shorthand for Lambda/API Gateway saves boilerplate; works in CloudShell with zero extra tooling install.
4. **Swap when:** the stack spans many AWS services where SAM's serverless focus pinches (CDK's L2 constructs win); multi-cloud (Terraform); or a team strongly prefers TypeScript/Python over YAML for IaC (CDK).

### 12. CloudTrail + S3 Object Lock vs CloudWatch Logs (for audit)

1. **Considered:** CloudWatch Logs only, CloudTrail → S3 with Object Lock.
2. **Picked:** CloudTrail + S3 Object Lock COMPLIANCE.
3. **Why:** **WORM is a compliance bond.** CloudWatch Logs are mutable by anyone with `logs:DeleteLogStream`; Object Lock COMPLIANCE makes deletion impossible until retention expires, including by root. The audit trail is the artifact a regulator subpoenas — it has to be unambiguously immutable.
4. **Swap when:** the audit isn't compliance-bound — CloudWatch Logs Insights is a friendlier query surface for ops debugging, and you can pair it with retention policies for cost.

---

## Cross-cutting / methodology

### 13. AI orchestration vs hand-written orchestration code

1. **Considered:** Python state machine, AWS Step Functions, LLM agent.
2. **Picked:** LLM agent.
3. **Why:** the **methodology** matters as much as the artifact. AI as a force multiplier means the orchestration layer is *editable in English* — operators, auditors, and new engineers can read the system prompt and understand the protocol without reading Python. The AI doesn't make security decisions (Cedar does) and isn't inside the cryptographic boundary (KMS is) — it only orchestrates. See [AI-GOVERNANCE.md](AI-GOVERNANCE.md) for the bounded-autonomy story.
4. **Swap when:** the team isn't AI-comfortable yet, or compliance demands deterministic orchestration code in addition to deterministic security decisions. (Note: Sentinel FIPS already has a *dry-run mode* — see [AI-GOVERNANCE.md § Dry-Run Mode](AI-GOVERNANCE.md#dry-run-mode) — that lets skeptics observe AI behavior without risk before going live.)

### 14. v1 today vs wait-for-perfect

1. **Considered:** ship v1 dev-testable today, hold for full FIPS 140-3 L3 hardening.
2. **Picked:** v1 today, with explicit gap analysis.
3. **Why:** **leadership decides the FIPS posture, engineering advises** — see [FIPS-140-3.md § Leadership Decision Matrix](FIPS-140-3.md#leadership-decision-matrix). v1 demonstrates the architectural pattern at ~$1/mo and is deployable to dev/internal-pilot accounts immediately. Tier 2 (FedRAMP-aligned) and Tier 3 (true L3) are deliberate engineering investments with quantified cost and timeline. Holding v1 until Tier 3 is gold-plating.
4. **Swap when:** the contract or regulator requires Tier 2/3 from day one — then v1 is study material, not deployment, and we go straight to the full hardening track.

---

## Drilling these

Read top to bottom once. Then practice from the **question only**, with the doc closed. Score yourself on three dimensions per answer:

| Pass | Fail |
|---|---|
| Named the alternative (Considered) | "I just used X" |
| Gave a property/constraint (Why) | "X is better" |
| Named a flip condition (Swap when) | "X is always right" |

Three passes per answer = ready. Anything less, re-read the entry.

If the verifying engineer asks something not on this list, fall back to the formula structure live: *"Let me think — alternatives would be Y or Z; I'd weigh them on [property]; my default would be X because [reason]; I'd swap to Y if [condition]."* The structure beats the specific content.

---

## Footnotes

**OPA (Open Policy Agent):** General-purpose policy engine used heavily in Kubernetes/multi-cloud environments. Policies are written in Rego — a custom query language. Self-hosted, no formal verification. Dominant outside AWS. Correct choice when policy lives next to Kubernetes admission control or in front of non-AWS services. Cedar wins inside AWS because it has formal verification, managed control plane via Verified Permissions, and maps directly to the IAM principal/action/resource model.

**Nitro Enclave attestation chain:** AWS Nitro Enclaves are hardware-isolated compute environments inside EC2 — no persistent storage, no network, no SSH access, memory encrypted. The attestation chain works as follows: the Nitro card signs a cryptographic measurement of the enclave image → produces an attestation document → KMS verifies the document → only then releases the key material. This means KMS will only decrypt or sign for code that can cryptographically prove it is the exact expected image running on verified hardware. AWS publishes FIPS 140-2 Level 3 validation certificates on the NIST CMVP database for their KMS HSMs. Whether AWS uses Nitro internally for FIPS endpoints is not published — we consume the validated boundary via the FIPS endpoint (`kms-fips.<region>.amazonaws.com`), same posture as any federal customer. The soundbite: *"Nitro Enclaves close the gap between 'I trust AWS' and 'I can cryptographically prove what code touched the key material.'"*
