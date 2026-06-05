# Sentinel FIPS — 2-Minute Demo Script

The video shows one thing: **the cryptographic operation is gated by a relationship chain in a graph.** Revoke an edge → no signature.

## Before you hit record

- Stack already deployed (see [SETUP.md](SETUP.md)) and graph already seeded.
- **For the headline demo: deploy in `DryRun=false` (live mode)** — the whole point is showing real signatures and real alerts. Dry-run is for the skeptic-audience variant below.
- SNS subscription confirmed.
- CloudShell open in `us-east-1`, font bumped (Cmd-+ a few times).
- Two windows visible: **CloudShell** (left) + **email inbox** (right) for the alert moment.
- Run `bash demo.sh` once to warm Lambda — first invoke is the cold-start tax.

## Script (target: 2:15)

### 0:00 — Hook (15s)
> *"This is Sentinel FIPS. A signing request only succeeds if every relationship in the ReBAC chain is intact. Watch what happens when I break one link."*

Show [README.md](README.md) ReBAC diagram briefly:
```
sentinel-agent --delegate_of--> tony --member_of--> platform-team --can_sign--> idp-config-bundle
```

### 0:15 — ALLOWED path (40s)
In CloudShell:
```bash
bash demo.sh
# choose 3
```

Point at the output as it scrolls:
- `check_authorization` → **decision: ALLOW**, full chain returned
- `sign_bundle` → base64 **signature** issued by KMS (FIPS endpoint)
- Final line: **`REBAC_ALLOWED — ...`**

> *"Claude called the authorizer, got a permit from Cedar, and KMS signed inside the FIPS-validated boundary."*

### 0:55 — Break the chain (15s)
Back to the menu, choose **4**:
```
✓ tony#member_of removed — chain BROKEN
```

> *"I just revoked Tony's membership in the platform team. The graph is broken."*

### 1:10 — DENIED path (40s)
Choose **3** again.

Point at:
- `check_authorization` → **decision: DENY**, `reason: chain_broken`
- `emit_alert` fired — **no `sign_bundle` call**
- Final line: **`REBAC_DENIED — ...`**

Switch to the email window:
> *"Same request, no signature. EventBridge fired a CRITICAL alert to SNS."*

Show the alert email subject in the inbox.

### 1:50 — Restore + close (25s)
Back to CloudShell, choose **5** to restore, then **3** one more time:
```
✓ tony#member_of restored — chain INTACT
REBAC_ALLOWED — ...
```

> *"Edge restored, chain intact, signature flows again. The whole gate is the graph."*

End on the README architecture diagram and the **🔒 FIPS-3-GAP** legend.

---

## If you have 30 extra seconds

After the deny, run:
```bash
aws dynamodb scan --table-name sentinel-rebac \
  --query 'Items[].{key:subject_relation.S, objects:objects.SS}' --output table
```
Show the missing `tony#member_of` row. Pure visual proof the chain is broken in the data store.

## Cuts to make if you're over time

1. Drop the architecture diagram at the end (10s).
2. Skip showing the inbox; just call out *"alert fired"* (10s).
3. Skip the restore step (25s) — the deny is the punchline.

## What NOT to show on camera

- The Anthropic API key, the deploy prompts, any IAM ARNs that include the account ID — blur or skip.
- `sam deploy` output — too slow, unrelated to the point.
- CloudTrail events — interesting but kills the pace.

---

## Skeptic-audience variant (AI-doubters)

If recording for a senior manager / skeptical reviewer / "why is there an LLM in your security pipeline?" audience, swap the closing 25s for a **dry-run flex** that proves the AI is bounded:

### 1:50 — Restore, then dry-run flex (25s, replaces the standard close)

Choose **5** to restore the chain. Then run a dry-run request:

```bash
DRY_RUN=true python3 client.py
```

Point at:
- Verdict prefix: **`[DRY-RUN] REBAC_ALLOWED — would have signed ...`**
- The `sign_bundle` audit entry contains `"dry_run": true` and `"would_sign_digest": "<sha256>"` — **no actual KMS call**

Then prove it didn't actually sign:
```bash
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=Sign \
  --start-time $(date -u -d '2 minutes ago' +%Y-%m-%dT%H:%M:%SZ)
# Empty result → AI thought it signed; KMS was never invoked
```

> *"The AI thinks it signed. KMS confirms it didn't. That's bounded autonomy — the LLM has zero authority to perform the cryptographic operation. Run dry-run for two weeks before going live."*

End on [AI-GOVERNANCE.md](AI-GOVERNANCE.md) — the four-pillar frame: rock solid, safe, secure, haste.

### Talking points for live AI questions

If asked mid-demo, here are the canned answers from [AI-GOVERNANCE.md § The Skeptic's Q&A](AI-GOVERNANCE.md#the-skeptics-qa):

| Question | Three-second answer |
|---|---|
| *"What if the AI hallucinates?"* | "Cedar makes the security decision; the AI receives it as a tool result. Three layers catch hallucination — see AI-GOVERNANCE." |
| *"Can it be tricked by prompt injection?"* | "It can be tricked at the prose layer. It can't grant itself a Cedar permit. Sign Lambda re-checks independently." |
| *"What if Anthropic is down?"* | "Fail-closed. No signature is issued under degraded conditions. Step Functions is the documented exit ramp." |
| *"Why an LLM?"* | "Extensibility — adding a new response action is system prompt + handler, not state-graph rewrite. Audit value is identical." |

If they push, point at [AI-GOVERNANCE.md](AI-GOVERNANCE.md) and offer to share it after the call.
