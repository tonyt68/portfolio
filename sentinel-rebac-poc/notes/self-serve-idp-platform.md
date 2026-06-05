# Self-Serve IDP Platform — Idea & Flows

## The Problem

At 300+ microservices the platform team becomes a bottleneck:
- Teams file DevOps tickets for every deploy
- Security configuration is inconsistent across teams
- FedRAMP controls applied manually per audit
- No visibility into drift after deployment
- Platform team can't scale to the demand

**The goal: Developer self-service with security guardrails baked in — not bolted on.**

---

## The Core Idea

Remove the platform team from the deploy path entirely.
Security is enforced by the platform, not requested from it.

```
Today:
  Developer → DevOps ticket → Platform team → Manual review → Deploy
  (days to weeks, inconsistent, doesn't scale)

Future:
  Developer → IDP Portal → Pick template → Fill intent config → Deploy
  (minutes, consistent, scales infinitely)
```

---

## The Identity Layer — Cognito RBAC Security Trimming

Cognito groups drive what each developer sees and can deploy.
The portal renders only what the user is authorized for.

```
Developer logs in →
Cognito token:
  groups: [java-team, ecs-allowed, internal-tier]
  custom:bounded_context: payment-service
  custom:tier: internal

Portal trims to:
  ✅ ECS Fargate template
  ✅ RDS Aurora template
  ✅ Internal ALB template
  ❌ FedRAMP regulated template  (not in their group)
  ❌ Lambda@Edge CSP template    (public tier only)
  ❌ Platform admin controls     (not their role)
```

**Roles**

| Role | Portal Access | Can Deploy | Environments |
|------|-------------|------------|--------------|
| platform-admin | Everything | All templates | All |
| security-team | Read all + approve | FedRAMP templates | All |
| java-team-lead | Internal tier only | Internal templates | All |
| java-team-dev | View only | Dev environment only | Dev |
| fedramp-team | Regulated tier only | Regulated templates | Regulated |

---

## Bounded Contexts — IAM Boundaries Per Service

> Full architecture, isolation layers, and breadcrumbs → [bounded-context-isolation.md](bounded-context-isolation.md)

Each service owns its IAM boundary. No shared roles. No lateral movement.

**Bounded context definition**
```yaml
service:
  name: payment-service
  bounded_context: payments
  tier: internal
  fedramp: false
```

Platform generates automatically:
```
IAM Role: PaymentServiceRole
  → S3: payment-bucket only
  → KMS: payment-keys only
  → Secrets Manager: /payments/* only
  → DynamoDB: payment-table only
  → nothing else

IRSA binding:
  Kubernetes ServiceAccount: payment-service-account
  Annotation: eks.amazonaws.com/role-arn: PaymentServiceRole
```

**Result: Pod level isolation. Breach of payment-service
cannot reach identity-service, document-service, or any other context.**

---

## Intent-Based Template Config

Teams declare intent — platform handles complexity.

**What teams fill out**
```yaml
app:
  name: my-service
  tier: public          # public | internal | regulated
  bounded_context: payments
  fedramp: false
  language: java
```

**What the platform generates based on tier**

| Control | public | internal | regulated |
|---------|--------|----------|-----------|
| CloudFront + WAF | ✅ | ❌ | ✅ |
| CSP Nonce Lambda@Edge | ✅ | ❌ | ✅ |
| Shield Advanced | ✅ | ❌ | ✅ |
| Internal ALB only | ❌ | ✅ | ❌ |
| VPC private subnets | ✅ | ✅ | ✅ |
| FedRAMP Config Rules | ❌ | ❌ | ✅ |
| Enhanced audit logging | ❌ | ❌ | ✅ |
| IRSA bounded context role | ✅ | ✅ | ✅ |
| AWS Config drift watching | ✅ | ✅ | ✅ |

Teams never configure WAF rules, CSP headers, or FedRAMP controls directly.
They pick a tier. Platform handles the rest.

---

## The Self-Serve Deploy Flow

```
Developer opens IDP Portal
     │
     ▼
Cognito authenticates → RBAC trims portal view
     │
     ▼
Developer picks approved template (only sees what they're allowed)
     │
     ▼
Fills out intent config:
  name, tier, bounded_context, fedramp
     │
     ▼
Platform generates:
  ├── CloudFormation stack (tier-appropriate controls)
  ├── IRSA role scoped to bounded context
  ├── AWS Config rules baseline captured
  ├── WAF + CSP if public tier
  └── FedRAMP controls if regulated tier
     │
     ▼
Deploy button — no ticket, no review, no waiting
     │
     ▼
AWS Config captures baseline state
     │
     ▼
Sentinel drift detection watching
```

---

## Drift Detection Closes the Loop

Self-serve deploys establish the baseline.
Sentinel watches for anything that drifts from it.

```
Deployed via portal → Config baseline captured
     │
Someone manually changes security group outside portal
     │
     ▼
AWS Config detects drift →
EventBridge →
Sentinel AI agent →
  reasons about severity →
  GOVERNANCE_MISSING if critical control changed →
  auto-remediate OR escalate to security team
```

**The full governance loop**
```
Identity → RBAC → Self-serve → Deploy → Baseline → Drift Detection → Remediate
```

No manual step anywhere in the chain.

---

## The Delivery Stack

| Layer | Technology |
|-------|-----------|
| Portal | Backstage (Spotify IDP) or AWS Service Catalog |
| Identity + RBAC | Cognito User Pools + Groups |
| Templates | CloudFormation + CDK L3 Constructs |
| Bounded Context IAM | IRSA (EKS) or ECS Task Roles |
| Edge Security | Lambda@Edge + CloudFront + WAF |
| Drift Detection | AWS Config + EventBridge + Sentinel AI |
| Audit | CloudTrail + CloudWatch + S3 archival |

---

## Why This Matters at NetDocuments

- 300+ microservices — platform team cannot manually govern at this scale
- FedRAMP requirements — controls must be consistent and auditable
- Akamai migration — edge security layer needs to be rebuilt as golden path
- Developer velocity — teams should deploy in minutes not days
- Security by design — guardrails built into the platform, not requested from it

---

## Status

Idea / proposal — not yet implemented.
Built on patterns from Henry Schein One:
- JIT provisioning + RBAC Support Tool
- Auth0 golden path libraries
- Automated quality gates in Harness/GitHub Actions
- Session Kill Switch + Magic Mint security primitives

This platform is the natural evolution of those patterns at AWS scale.
