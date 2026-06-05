# Bounded Context Isolation — Architecture & Breadcrumbs

## The Core Principle

**Isolation + Decoupling = Contained Blast Radius**

```
Domain boundary drives everything →
  Each bounded context is fully isolated →
  Breach of one context cannot reach another →
  Blast radius contained by design not by luck
```

---

## The Org Structure

Get the org structure right first — everything else flows from it.

```
Domain     → the business capability (Payments, Identity, Documents)
Context    → the technical boundary within the domain
Isolation  → enforced at every layer automatically
```

**Wrong org structure = leaky boundaries**
**Right org structure = blast radius contained everywhere**

---

## The Full Architecture

```
IAM Identity Center (global layer)
  └── Enterprise SSO connections (SAML/OIDC)
  └── SCIM provisioning (user lifecycle)
  └── Global policies
       │
       ├── Bounded Context: Payments
       │     └── Cognito User Pool: payments
       │     └── Kubernetes Namespace: payments
       │     └── IRSA Role: PaymentServiceRole
       │     └── Log Index: /netdocs/payments/*
       │     └── Network Policy: payments-only egress
       │     └── AWS Config Rules: payments baseline
       │
       ├── Bounded Context: Identity
       │     └── Cognito User Pool: identity
       │     └── Kubernetes Namespace: identity
       │     └── IRSA Role: IdentityServiceRole
       │     └── Log Index: /netdocs/identity/*
       │     └── Network Policy: identity-only egress
       │     └── AWS Config Rules: identity baseline
       │
       └── Bounded Context: Documents
             └── Cognito User Pool: documents
             └── Kubernetes Namespace: documents
             └── IRSA Role: DocumentServiceRole
             └── Log Index: /netdocs/documents/*
             └── Network Policy: documents-only egress
             └── AWS Config Rules: documents baseline
```

---

## Isolation Layers — Decoupled by Design

Each layer enforces the boundary independently.
No single layer is the only defense.

| Layer | Technology | What it isolates |
|-------|-----------|-----------------|
| Identity | Cognito User Pool per context | Auth scope |
| Runtime | IRSA Role per context | AWS resource access |
| Network | Kubernetes NetworkPolicy | Pod-to-pod traffic |
| Namespace | Kubernetes Namespace | Workload visibility |
| Logging | CloudWatch index per context | Audit trail |
| Config | AWS Config Rules per context | Drift detection |
| Secrets | Secrets Manager path per context `/payments/*` | Credential access |
| KMS | KMS key per context | Encryption boundary |

**Decoupled means:**
Each layer enforces isolation independently.
Removing one layer doesn't collapse the others.

---

## Blast Radius Guarantee

```
Breach in payments context →
  Cognito User Pool isolated  ✅ can't auth to identity/documents
  IRSA Role scoped            ✅ can't reach identity/documents AWS resources
  Network Policy blocks       ✅ can't call identity/documents pods
  Namespace isolated          ✅ can't see identity/documents workloads
  Log Index separated         ✅ can't read identity/documents logs
  Secrets path scoped         ✅ can't read /identity/* or /documents/*
  KMS key separate            ✅ can't decrypt identity/documents data
  Config baseline separate    ✅ drift detected per context independently

Result: payments breach stays in payments
```

---

## The IRSA Breadcrumb

```
EKS Pod needs AWS resource →
  Kubernetes Service Account annotated with IAM Role ARN →
  OIDC token exchanged with STS →
  STS vends temp credentials scoped to that role →
  Pod accesses only what the role allows →
  Credentials expire automatically →
  No shared credentials across contexts
```

**Setup**
```yaml
# Kubernetes Service Account
apiVersion: v1
kind: ServiceAccount
metadata:
  name: payment-service-account
  namespace: payments
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::ACCOUNT:role/PaymentServiceRole
```

```hcl
# IAM Role trust policy (Terraform)
trust_policy = {
  Effect = "Allow"
  Principal = {
    Federated = "arn:aws:iam::ACCOUNT:oidc-provider/oidc.eks.REGION.amazonaws.com/..."
  }
  Action = "sts:AssumeRoleWithWebIdentity"
  Condition = {
    StringEquals = {
      "oidc:sub" = "system:serviceaccount:payments:payment-service-account"
    }
  }
}
```

---

## The Cognito → Bounded Context Flow

```
Developer logs in →
Cognito token:
  custom:bounded_context = payments
  groups: [payments-team]
       │
       ▼
Portal RBAC trims to payments templates only
       │
       ▼
Deploys to payments namespace only
       │
       ▼
IRSA role scoped to payments resources only
       │
       ▼
Logs flow to /netdocs/payments/* only
```

**One identity decision enforced at every layer.**

---

## The Multi-PMS / Multi-Tenant Breadcrumb

```
Auth0 pattern (Henry Schein):
  Global tenant → shared settings
  Per PMS tenant → custom settings
  Problem → drift between tenants, manual sync

AWS pattern:
  IAM Identity Center → global SSO + SCIM (replaces global tenant)
  Cognito User Pool per bounded context → replaces per PMS tenant
  Terraform module → no drift, consistent config every time
```

---

## The Namespace → Log Index Connection

```
Kubernetes Namespace: payments →
  All pod logs tagged with namespace →
  CloudWatch Log Group: /netdocs/payments/* →
  Kinesis Firehose →
    Splunk/Datadog index: payments

Query single context:
  index=payments | where level=ERROR

Query across contexts (ops/security):
  index=netdocs-* | where user_id="suspicious-user"

FedRAMP audit query:
  index=regulated-* | where action=data_access
```

**Collect isolated. Query flexible. RBAC controls who queries what.**

---

## The Network Policy Breadcrumb

```yaml
# isolate.yaml pattern — per bounded context
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: payments-isolation
  namespace: payments        # scoped to payments namespace
spec:
  podSelector: {}            # applies to all pods in namespace
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: payments     # only accept traffic from payments namespace
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          name: payments     # only send traffic to payments namespace
  - to:
    - namespaceSelector:
        matchLabels:
          name: aws-system   # allow AWS service calls
```

---

## The Terraform Golden Path

Teams declare intent — platform enforces isolation automatically.

```hcl
module "bounded_context" {
  source          = "netdocs-platform/modules//bounded-context"
  name            = "payments"
  domain          = "financial"
  tier            = "internal"
  fedramp         = false
}
```

Module creates automatically:
- Cognito User Pool
- Kubernetes Namespace
- IRSA Role + trust policy
- IAM permissions (scoped to context)
- Network Policy
- CloudWatch Log Group
- AWS Config Rules baseline
- Secrets Manager path `/payments/*`
- KMS key

**One module call. Full isolation. Zero drift.**

---

## Why This Matters at NetDocuments

- 300+ microservices without bounded contexts = shared blast radius
- FedRAMP requires demonstrable isolation between workloads
- Legal document management = breach isolation is not optional
- Akamai migration = opportunity to rebuild boundaries correctly from scratch

---

## Status

Idea / proposal — not yet implemented.
Pattern proven at Henry Schein One:
- JIT + SCIM + user mapping across multiple PMS tenants
- Auth0 global tenant + per PMS tenant architecture
- Namespace-level isolation concepts applied to identity layer

AWS primitives make this cleaner, more automated, and FedRAMP compliant
out of the box compared to the manual Auth0 multi-tenant approach.
