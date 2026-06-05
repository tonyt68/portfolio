# A2A Trust Enforcement PoC

Reference implementation of [draft-tonyai-a2a-trust-00](https://datatracker.ietf.org/doc/draft-tonyai-a2a-trust/) — Agent-to-Agent Trust enforcement via cryptographic identity, least privilege, and fail-closed enforcement.

## What This PoC Proves

Every demo scenario maps directly to an IETF requirement:
- **Golden Path:** Full authentication + authorization chain validates → ALLOWED
- **Dynamic Policy:** Cedar policy changes → enforcement changes instantly (no cert rotation)
- **11 Attack Scenarios:** Rogue spawn, dual-sig tampering, scope escalation, revocation, CRL failure, TTL expiry, cross-org grants, replay attacks — all FAIL CLOSED

## Quick Start

### Prerequisites
- macOS / Linux
- Docker + Docker Compose
- Python 3.12+ (for local development)
- AWS credentials (for secrets + CloudWatch)
- GCP credentials (for Vertex AI + Cloud Logging)

### 1. Setup

```bash
cd /Users/tonyai/dev/ietf-a2a-trust-poc

# Copy template config
cp .env.example .env

# Fill in .env with your AWS_REGION, S3_BUCKET, GCP_PROJECT_ID, etc.
# (Config only — secrets come from AWS Secrets Manager)
```

### 2. Create AWS Secrets Manager Secret

```bash
aws secretsmanager create-secret \
  --name a2a-trust-poc/secrets \
  --secret-string '{
    "jwt_secret": "your-secret",
    "hmac_secret": "your-secret",
    "admin_api_key": "your-secret",
    "gcp_service_account_json": "{...full service account JSON...}"
  }' \
  --region us-east-1
```

### 3. Run Demo

```bash
cd demo
./start.sh

# Starts all 4 services + opens http://localhost:8765
```

### 4. Explore

- **Architecture:** http://localhost:8765/prep
- **Live Demo:** http://localhost:8765
  - Click scenario buttons
  - Watch audit trail populate in real-time
  - Verify hash chain integrity

## Architecture

```
Agent A (Requester)
    ↓ mTLS
Agent B (Responder)
    ↓ JWT RS256 validation
    ↓ HMAC-SHA256 verification
    ↓ Cedar policy evaluation
MCP Server (public interface)
    ↓ S3 write/read operations
Federated Audit Trail
    ├─ CloudWatch Logs (AWS)
    └─ Google Cloud Logging (GCP)
```

## Services

| Service | Port | Purpose |
|---------|------|---------|
| **mcp_server** | 8001 | Public MCP tools (JWT, HMAC, Cedar, S3) |
| **admin_bootstrap** | 8002 | Locked-down cert/policy management (mTLS + API key) |
| **demo_web** | 8765 | Demo UI + scenario orchestration |
| **dynamodb_local** | 8000 | DynamoDB Template Registry |

## Tech Stack

- **Backend:** Python + FastAPI
- **Agents:** Claude via Vertex AI SDK
- **Security:** mTLS, JWT RS256, HMAC-SHA256, Cedar SDK
- **Secrets:** AWS Secrets Manager (KMS encrypted)
- **Infrastructure:** Docker Compose (local) + Terraform (AWS + GCP)
- **Audit:** CloudWatch Logs + Google Cloud Logging
- **Frontend:** HTML + CSS + JavaScript (no build step)

## Key Design Decisions

- **No secrets in .env** — all secrets in AWS Secrets Manager
- **No PostgreSQL** — DynamoDB + CloudWatch authoritative
- **Cedar SDK** — local policy engine, replaces Redis ReBAC
- **Self-signed certs** — PoC only; Vault PKI for production
- **Agents credential-free** — MCP server owns all AWS/GCP keys
- **Fail-closed** — any verification failure = DENY, no degraded mode
- **Federated audit** — CloudWatch (AWS) + Cloud Logging (GCP) independent

## Security Properties

✅ No secrets in code/git/containers  
✅ KMS encryption at rest (AWS Secrets Manager)  
✅ TLS in transit (mTLS + HTTPS)  
✅ Audit trail outside agent control (CloudWatch, Cloud Logging)  
✅ Least privilege (Cedar policies per agent)  
✅ Fail-closed (any verification failure = DENY)  
✅ Tamper-evident (hash-chained audit entries)  
✅ Correlation ID traces (multi-hop request chains)  

## Production Scale-Out Paths

| Component | PoC | Production |
|-----------|-----|-----------|
| CA | Self-signed (OpenSSL) | HashiCorp Vault PKI |
| Policy Engine | Cedar SDK (local) | Amazon Verified Permissions |
| Orchestration | FastAPI | LangGraph + Temporal |
| Deployment | Docker Compose | ECS/GKE |
| Secrets | Secrets Manager | Vault / Cloud Secrets |
| Audit | CloudWatch + Cloud Logging | S3 (Object Lock) + Cloud Audit Logs |

## 11 Demo Scenarios

1. **Golden Path** → ALLOWED (full chain validates)
2. **Dynamic Policy** → ALLOWED (policy updated, enforcement changes)
3. **Rogue Spawn** → DENIED (not in CanSpawn list)
4. **Dual-Sig Missing** → DENIED (owner sig only)
5. **Dual-Sig Tampered** → DENIED (PA sig invalid)
6. **Scope Escalation** → DENIED (child > parent)
7. **Revocation Lifecycle** → DENIED (ACTIVE → DISABLED → DELETED)
8. **CRL Check Failure** → DENIED (revoked cert)
9. **TTL Expiry** → DENIED (expired template)
10. **Cross-Org Grant** → DENIED (grant revoked)
11. **Replay Attack** → DENIED (reused nonce)

## Files

```
a2a-trust-poc/
├── services/
│   ├── mcp_server/          # MCP tools + JWT/HMAC/Cedar validation
│   ├── admin_bootstrap/     # Cert generation + policy management
│   └── cert_authority/      # CA library
├── demo/
│   ├── app.py              # FastAPI backend
│   ├── prep.html           # Architecture context
│   ├── demo.html           # 11 scenarios + audit table
│   ├── static/             # CSS/JS
│   └── start.sh            # Docker Compose starter
├── terraform/              # AWS + GCP IaC
├── policies/               # Cedar policy files
├── ca/                     # CA certs (gitignored)
├── docker-compose.yml      # 4 services
├── .env                    # Config (gitignored, secrets separate)
└── README.md              # This file
```

## NOTES.md

Full architecture & implementation details in [NOTES.md](NOTES.md):
- 7-phase build plan
- Service architecture
- Secret management
- Testing strategy
- Production scale-out paths

## License

Reference implementation for IETF draft-tonyai-a2a-trust-00.

---

**Status:** Phase 1-6 implementation complete. Phase 7 (hardening) pending.

**Next Steps:**
1. Populate AWS Secrets Manager secret
2. Run `demo/start.sh`
3. Test all 11 scenarios
4. Phase 7: Security hardening + red team pass
