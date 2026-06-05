# CSP Nonce Golden Path — Lambda@Edge Idea

## The Problem

Most teams either skip Content-Security-Policy headers entirely or implement them
inconsistently at the application layer. At 300+ microservices this means:

- XSS exposure varies by team
- Malicious browser extensions can inject scripts into unprotected apps
- FedRAMP Moderate/High requires CSP enforcement — no standard = audit finding

There is no AWS native plugin or extension that solves this automatically.
Every team is on their own today.

---

## The Idea

Standardize CSP nonce generation and injection at the CloudFront edge via
Lambda@Edge — one implementation, every React app protected automatically.

**This is a golden path, not a per-app feature.**

---

## How It Works

```
User Request
     │
     ▼
CloudFront Edge (nearest to user)
     │
     ├── Viewer Request hook
     │     └── Lambda@Edge generates cryptographic nonce (uuid/crypto.randomBytes)
     │         Attaches nonce to request context
     │
     ├── Origin Request → S3 / ALB (React app)
     │
     ├── Origin Response ← HTML returned from origin
     │
     └── Viewer Response hook
           └── Lambda@Edge injects:
                 1. Content-Security-Policy header
                    script-src 'nonce-{nonce}' 'strict-dynamic'
                    style-src 'nonce-{nonce}'
                    object-src 'none'
                    base-uri 'none'
                 2. Nonce value into all <script> and <style> tags in HTML
                 3. Additional security headers:
                    X-Frame-Options: DENY
                    X-Content-Type-Options: nosniff
                    Referrer-Policy: strict-origin-when-cross-origin
                    Permissions-Policy: geolocation=(), camera=()
     │
     ▼
User receives HTML with matching nonce in headers and script tags
Browser enforces — any script without the nonce is blocked
```

---

## Why Nonces vs Static CSP Hashes

Static hashes require recalculating every time a script changes — breaks on
every deploy. Nonces are generated fresh per request — deploy-agnostic and
more secure (unique per response, can't be replayed).

---

## The Browser Extension / Injection Attack This Blocks

```
User installs malicious browser extension →
Extension attempts to inject <script>stealCredentials()</script> into page →
Injected script has no nonce →
Browser CSP policy rejects execution →
Attack neutralized at the browser level
```

Without CSP a valid user with a compromised browser extension is
indistinguishable from a legitimate user — the request comes from their
browser with their valid session. CSP is the last line of defense.

This was a real threat vector identified at Henry Schein One — DPoP was
implemented to bind tokens to the legitimate UI, CSP nonces block the
script injection that enables the attack in the first place.

---

## The Golden Path Delivery

```
CloudFormation Template
  └── CloudFront Distribution
        ├── Lambda@Edge (Viewer Request + Viewer Response)
        │     └── nonce generation + header injection
        ├── AWS WAF
        │     ├── Managed rule groups (OWASP Top 10)
        │     ├── Bot Control
        │     └── Rate limiting rules
        └── Shield Advanced (DDoS)
```

Teams deploy one CloudFormation template — they get:
- CSP nonce handling
- WAF protection
- DDoS mitigation
- Security headers

No per-app implementation. No inconsistency. One audit finding closed
across the entire platform.

---

## FedRAMP Relevance

FedRAMP Moderate and High require:

- SI-3: Malicious Code Protection
- SC-18: Mobile Code (CSP enforces this)
- AC-17: Remote Access controls

CSP at the edge satisfies SC-18 across all apps automatically.
Without it every app needs individual review during FedRAMP audit.

---

## Migration from Akamai

Akamai provides edge security logic today. Moving to CloudFront means
this protection needs to be re-implemented. Lambda@Edge is the direct
replacement for Akamai EdgeWorkers/Edge Logic.

This template should be part of the Akamai → CloudFront migration plan.

---

## Status

Idea / proposal — not yet implemented.
Prior art: CSP + nonce implemented manually at application layer at Henry Schein One.
DPoP POC built to complement this — token binding + script injection blocking
are two layers of the same zero-trust UI security model.
