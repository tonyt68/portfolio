# A2A Trust PoC — Scale Out & Trade-offs

---

## Current PoC Scope (Local / Demo)
- Two agents (Agent A, Agent B) as local FastAPI services
- Cedar SDK running in-process (local policy evaluation)
- Docker Compose for local multi-agent environment
- Self-signed certs for mTLS (OpenSSL)
- PostgreSQL + Google Cloud Logging + CloudWatch for audit
- Terraform for AWS + GCP infrastructure

---

## Scale Out Path

### Phase 1 — Cloud Native (Single Org)
- Deploy Agent A and Agent B to AWS ECS or GCP Cloud Run via Terraform
- Replace self-signed certs with HashiCorp Vault PKI or AWS ACM (managed CA)
- Replace Cedar SDK local with Amazon Verified Permissions (AVP) for managed policy evaluation
- PostgreSQL → AWS RDS or GCP Cloud SQL (managed, HA)
- Add horizontal scaling: multiple Agent B instances behind API Gateway

### Phase 2 — Multi-Org Federation
- Introduce Template Registry service — central CA that signs agent certificates
- Cross-org grant flow: Org A issues signed grant to Org B via Template Registry
- Each org maintains independent audit trail — no shared audit DB
- Federated CRL (Certificate Revocation List) — revoke across org boundaries
- mTLS with org-issued certs replacing self-signed

### Phase 3 — Enterprise / FedRAMP
- Replace AVP with OPA or Cedar + Styra (enterprise policy management)
- KMS-signed audit records (tamper-evident, S3 Object Lock COMPLIANCE mode)
- FIPS 140-3 compliant crypto throughout (AWS GovCloud or equivalent)
- SOC2 / FedRAMP High control mapping documented

---

## Trade-offs

### Cedar SDK Local vs Amazon Verified Permissions
| | Cedar SDK Local | Amazon Verified Permissions |
|---|---|---|
| Cost | Free | Pay per authorization request |
| Latency | In-process (~1ms) | API call (~10-50ms) |
| Audit | Manual | Built-in AVP audit trail |
| Scale | Single process | Managed, multi-tenant |
| PoC fit | Perfect | Overkill for demo |
| Prod fit | Limited | Recommended |

**Decision:** Cedar SDK local for PoC. Document AVP as the production path.

### Self-Signed Certs vs Managed CA
| | Self-Signed (OpenSSL) | HashiCorp Vault PKI / AWS ACM |
|---|---|---|
| Cost | Free | Vault: free OSS; ACM: free for AWS services |
| Setup | Minutes | Hours (Vault) / Minutes (ACM) |
| Rotation | Manual | Automatic |
| CRL | Manual | Automatic |
| PoC fit | Perfect | Overkill |
| Prod fit | Never | Required |

**Decision:** OpenSSL self-signed for PoC. Document Vault PKI as production path.

### Docker Compose vs Kubernetes
| | Docker Compose | Kubernetes (EKS/GKE) |
|---|---|---|
| Complexity | Low | High |
| Cost | Free (local) | $$$  |
| Demo portability | High | Low |
| Scale | Single host | Multi-node |
| PoC fit | Perfect | Overkill |

**Decision:** Docker Compose for PoC. Note EKS/GKE as production path.

### Single Correlation ID Strategy
- UUID v7 (time-ordered) generated at Agent A request initiation
- Stamped on every layer: JWT claims, HMAC payload, Cedar policy decision, audit log entry, GCP log, CloudWatch log
- Enables full end-to-end trace across both clouds from a single ID
- Trade-off: if correlation ID is lost at any layer, traceability breaks — every layer MUST propagate it

---

## Resume Keywords This PoC Adds
- Cedar (Policy as Code)
- Amazon Verified Permissions (scale-out path)
- Google Cloud Logging
- Vertex AI (GCP)
- Terraform (multi-cloud IaC)
- mTLS
- JWT chain validation
- HMAC-SHA256
- Federated audit
- IETF Internet-Draft reference implementation
- HashiCorp Vault PKI (scale-out path)
