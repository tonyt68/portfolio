# Phase 7 Remaining Work

## Double Signature (Dual-Sig) Validation
**Location:** `services/admin_bootstrap/policy_authority.py`

**What it does:**
- Validates Cedar policy updates require TWO signatures:
  1. Owner signature (cert authority)
  2. Policy Authority signature (compliance/legal)
- Both must be valid before policy change is applied
- Fail-closed: any sig validation error = DENY

**Status:** ⏳ Needs implementation (currently stubbed)

**Test:** Demo Scenario 4-5 (dual-sig tampering attacks)

---

## Certificate Modification & Lifecycle
**Location:** `services/admin_bootstrap/cert_manager.py`

**What it does:**
- Manages cert state machine:
  - ACTIVE → active agent
  - DISABLED → suspended (no new auth)
  - DELETED → revoked (instant deny)
- TTL enforcement (expires after max lifetime)
- CRL (Certificate Revocation List) management

**Status:** ⏳ Needs full implementation (currently stubbed)

**Test:** Demo Scenarios 7-9 (revocation, TTL, CRL checks)

---

## Why These Matter
- **Dual-sig:** Ensures policy changes require dual approval (compliance requirement)
- **Cert lifecycle:** Enables instant agent suspension/revocation without cert rotation
- Together: Implement IETF draft-tonyai-a2a-trust-00 requirements

---

## TODO for Phase 7 Final
- [ ] Implement dual-signature validation in policy_authority.py
- [ ] Implement cert lifecycle in cert_manager.py
- [ ] Wire CRL checks into main.py authorization
- [ ] Test scenarios 4-9 with real enforcement
- [ ] Red team: test dual-sig bypass attempts
- [ ] Commit: "Phase 7c: Dual-sig + cert lifecycle implementation"

**Priority:** Phase 8 (Claude integration) can proceed in parallel.
