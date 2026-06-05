# A2A Trust Enforcement PoC — Pitch Document
## draft-tonyai-a2a-trust-00 — Canonical Reference Implementation

---

## The Problem

AI agents today have no standardized way to authenticate to each other.

Every major AI platform — AWS, Google, Anthropic, Microsoft — is building multi-agent systems. None of them have solved agent identity between agents. Agents trust each other by default, or not at all. There is no standard.

When Agent A calls Agent B:
- How does Agent B know Agent A is who it claims to be?
- How does Agent B know Agent A is authorized to make this request?
- How does either agent know the message wasn't tampered with in transit?
- Who audits what happened if something goes wrong?

Today: nobody has a standard answer. This PoC proves one exists.

---

## The Solution

Agent-to-agent trust built on the same principles as Zero Trust for humans — cryptographic identity, least privilege, fail-closed enforcement, and immutable audit.

No implicit trust. Every agent interaction is authenticated, authorized, integrity-verified, and logged — before any data is exchanged.

---

## What This PoC Proves

Every demo scenario maps to a requirement in IETF Internet-Draft draft-tonyai-a2a-trust-00.

| Scenario | Draft Requirement Proven |
|---|---|
| Authorized request → ALLOWED | JWT chain validation + Cedar policy evaluation |
| Unauthorized scope → DENIED | Scope constraint principle — child cannot exceed parent |
| Tampered payload → DENIED | HMAC-SHA256 message integrity |
| Invalid spawn → DENIED | Two-check spawn rule (static + dynamic) |
| Edge revocation → DENIED immediately | Cedar policy update = instant enforcement |

All five scenarios produce a correlation-ID-linked audit trail across GCP (Google Cloud Logging) and AWS (CloudWatch). Federated, independent, tamper-evident.

---

## Why This Is Rare

- Tony authored the IETF Internet-Draft — this is the canonical reference implementation
- No public working implementation of A2A trust standards exists today
- Most agent frameworks assume agents trust each other — this inverts that assumption
- Cedar policy-as-code makes every rule human-readable, versionable, and testable
- Multi-cloud (GCP Vertex AI + AWS) proves the framework is portable — not vendor-locked

---

## Who This Is For

- **AI Platform engineers** — the enforcement layer your agent platform is missing
- **Security engineers** — Zero Trust extended to AI agents, not just humans
- **IETF reviewers** — working code that proves the spec is implementable
- **Hiring managers** — live demo with five scenarios, full audit trail, Cedar policies, Terraform IaC

---

## The One-Liner

*"I wrote the IETF draft. Then I built the demo. Here's the audit trail."*
