# FedRAMP Control Alignment — Sentinel FIPS

How Sentinel FIPS addresses each applicable FedRAMP control. Companion to [EXECUTIVE-BRIEF.md](EXECUTIVE-BRIEF.md).

---

## AC-3 — Access Enforcement

**What it means:** The system must automatically enforce who is allowed to do what — on every action, every time, without relying on the caller to self-report their own authorization.

**Why AI agents make this harder:** A traditional application has a fixed set of actions. An AI agent decides what to do at runtime. Without enforcement independent of the AI, the AI becomes the judge of its own authority.

**How Sentinel addresses it:** An independent policy engine (Amazon Verified Permissions, Cedar) evaluates every request before any action is taken. The AI receives the decision — it does not make it.

---

## AC-6 — Least Privilege

**What it means:** Every user, service, and system should have only the minimum access needed to do its job. Excess privilege expands blast radius if a component is compromised.

**Why AI agents make this harder:** AI agents are general-purpose by design. Left ungoverned, they accumulate access far beyond what any single operation requires.

**How Sentinel addresses it:** Each component is independently scoped. The AI agent cannot authorize, cannot sign, cannot alter the audit trail. It can only request — purpose-built controls decide.

---

## AU-9 — Audit Protection

**What it means:** Audit logs are only useful if they cannot be altered. A log that an insider or compromised administrator can delete is not evidence. FedRAMP requires audit records be protected against modification and deletion.

**Why AI agents make this harder:** If an AI agent makes a bad decision, the audit trail is the only way to prove what happened. A mutable log defeats that entirely.

**How Sentinel addresses it:** Every action is written to tamper-proof storage under compliance-mode write-once retention. Not even administrators can alter or delete records until retention elapses. The audit trail is permanent.

---

## IA-3 — Service Identity

**What it means:** When one service calls another, the receiving service must verify who is calling. A shared API key is not identity — it is a credential anyone with the key can use. True service identity means the caller proves who they are.

**Why AI agents make this harder:** AI agents act on behalf of people and teams — their identity is relational, not static. Proving that an AI agent is authorized to act on behalf of a specific engineer on a specific team requires more than a role assignment.

**How Sentinel addresses it:** The AI agent operates as a named, verified identity in a live Relationship-Based Access Control (ReBAC) graph. Authority is derived from verified relationships — not assumed from a credential.

---

## SC-8 — Transmission Protection

**What it means:** Data moving between services must be encrypted and protected against tampering in transit. This applies to service-to-service calls, not just user-facing traffic.

**Why AI agents make this harder:** AI agents call many services — authorization systems, cryptographic services, alerting systems. Each call is a potential interception point.

**How Sentinel addresses it:** All service-to-service calls use HTTPS with FIPS-validated TLS endpoints enforced at the infrastructure level (`AWS_USE_FIPS_ENDPOINT=true`).

---

## SI-7 — Integrity Verification

**What it means:** For sensitive operations, the organization must be able to prove that what was processed is exactly what was authorized — that nothing was altered between the authorization decision and the execution.

**Why AI agents make this harder:** An AI agent's output is text — inherently alterable without a cryptographic check. Without a signature on the operation it triggered, there is no proof the output was not modified.

**How Sentinel addresses it:** Every sensitive operation produces a cryptographic signature using a FIPS 140-2 Level 3 validated key (RSA-PSS). The signature is independently verifiable and permanently on record.

---

## FIPS 140-2/3

**What it means:** Every cryptographic operation — signing, encryption, key management — must use a module independently tested and validated by the National Institute of Standards and Technology (NIST). Not any encryption library — a certified one.

**How Sentinel addresses it:** All cryptographic operations use AWS KMS with FIPS-validated HSMs, accessed via FIPS endpoints. The gap between FIPS 140-2 Level 3 (current) and FIPS 140-3 Level 3 (federal contractual requirement) is documented with a defined upgrade path.

---

*Full gap analysis and upgrade path: [FIPS-140-3.md](FIPS-140-3.md)*
*Executive summary: [EXECUTIVE-BRIEF.md](EXECUTIVE-BRIEF.md)*
