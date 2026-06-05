"""Sentinel FIPS orchestrator — Claude Opus 4.7 driving an AWS-side tool-use loop.

Tools:
  check_authorization  → invokes the authorizer Lambda (ReBAC chain + Cedar)
  sign_bundle          → invokes the sign Lambda (KMS over FIPS endpoint)
  emit_alert           → puts a Sentinel.AuthChainBroken event on EventBridge

Modes:
  DRY_RUN=true   → sign_bundle and emit_alert return "would have ..." stubs
                   without invoking KMS or EventBridge. check_authorization
                   runs normally (read-only). Verdict prefixed with [DRY-RUN].

Self-policing:
  After the tool-use loop, structural assertions validate the audit trail.
  Any violation emits a Sentinel.AgentMisbehavior event and forces a deny verdict.
"""
import base64
import hashlib
import json
import os

import boto3
from anthropic import Anthropic

_secrets = boto3.client("secretsmanager")
_lambda = boto3.client("lambda")
_events = boto3.client("events")

_CLIENT: Anthropic | None = None

MODEL = "claude-opus-4-7"
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"

SYSTEM_PROMPT = """You are Sentinel, a security agent that gates a FIPS-validated cryptographic operation behind a ReBAC authorization chain on AWS.

For every signing request you MUST follow this protocol exactly:

1. Call check_authorization with the principal, action, and resource from the request.
2. Inspect the response:
   - If decision == "ALLOW" and the chain is intact, call sign_bundle with the request bundle, principal, action, and resource. (The sign Lambda re-verifies authorization independently — defense in depth — so all four fields are required.)
   - If decision == "DENY" or the chain is broken, call emit_alert with a clear reason and DO NOT sign.
3. Never call sign_bundle without a successful check_authorization in the same turn.
4. After you finish (signed or alerted), reply with a single line of the form:
     REBAC_ALLOWED — <one sentence>   (when signed)
     REBAC_DENIED — <one sentence>    (when chain broken or forbid)

Be terse. The audit trail captures the tool calls; your final line is the human-readable verdict."""

TOOLS = [
    {
        "name": "check_authorization",
        "description": "Traverse the ReBAC graph from principal toward resource and ask Cedar (Verified Permissions) for a permit/forbid decision. Returns {decision, chain, ...}.",
        "input_schema": {
            "type": "object",
            "properties": {
                "principal": {"type": "string"},
                "action": {"type": "string"},
                "resource": {"type": "string"},
            },
            "required": ["principal", "action", "resource"],
        },
    },
    {
        "name": "sign_bundle",
        "description": "Sign the SHA-256 digest of the bundle inside the FIPS-validated KMS boundary. Only call after check_authorization returned ALLOW.",
        "input_schema": {
            "type": "object",
            "properties": {
                "bundle": {"type": "string", "description": "Bundle contents to sign"},
                "principal": {"type": "string"},
                "action": {"type": "string"},
                "resource": {"type": "string"},
            },
            "required": ["bundle", "principal", "action", "resource"],
        },
    },
    {
        "name": "emit_alert",
        "description": "Emit a Sentinel.AuthChainBroken event so EventBridge pages the on-call via SNS. Call when authorization is denied or the chain is broken.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string"},
                "principal": {"type": "string"},
                "resource": {"type": "string"},
            },
            "required": ["reason", "principal", "resource"],
        },
    },
]


def _client() -> Anthropic:
    global _CLIENT
    if _CLIENT is None:
        secret = _secrets.get_secret_value(SecretId=os.environ["ANTHROPIC_SECRET_ID"])
        base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
        _CLIENT = Anthropic(api_key=secret["SecretString"], base_url=base_url)
    return _CLIENT


def _dispatch(name: str, args: dict) -> dict:
    if name == "check_authorization":
        # Read-only — runs identically in dry-run and live mode.
        resp = _lambda.invoke(
            FunctionName=os.environ["AUTHORIZER_FUNCTION"],
            InvocationType="RequestResponse",
            Payload=json.dumps(args).encode(),
        )
        return json.loads(resp["Payload"].read())

    if name == "sign_bundle":
        if DRY_RUN:
            digest = hashlib.sha256(args.get("bundle", "").encode("utf-8")).digest()
            return {
                "dry_run": True,
                "would_sign_digest": digest.hex(),
                "would_use_key": os.environ.get("KMS_KEY_ID_HINT", "alias/sentinel-fips"),
                "would_use_alg": "RSASSA_PSS_SHA_256",
                "note": "DRY_RUN=true — KMS was not invoked. Verify with `aws cloudtrail lookup-events ... EventName=Sign`.",
            }
        resp = _lambda.invoke(
            FunctionName=os.environ["SIGN_FUNCTION"],
            InvocationType="RequestResponse",
            Payload=json.dumps(args).encode(),
        )
        return json.loads(resp["Payload"].read())

    if name == "emit_alert":
        if DRY_RUN:
            return {
                "dry_run": True,
                "would_alert": args,
                "note": "DRY_RUN=true — EventBridge/SNS were not invoked.",
            }
        _events.put_events(Entries=[{
            "Source": "sentinel.fips",
            "DetailType": "Sentinel.AuthChainBroken",
            "Detail": json.dumps(args),
        }])
        return {"alerted": True, **args}

    return {"error": f"unknown tool {name}"}


def _validate_audit(audit: list[dict], verdict: str | None) -> tuple[bool, str]:
    """Structural assertions on the AI's tool sequence.

    Returns (ok, reason). A failure means the AI went off-script — caller emits
    Sentinel.AgentMisbehavior and forces a deny.
    """
    if not audit:
        return False, "no_tool_calls"

    if audit[0]["tool"] != "check_authorization":
        return False, "first_tool_not_check_authorization"

    auth_result = audit[0].get("result", {})
    decision = auth_result.get("decision")
    signed = any(s["tool"] == "sign_bundle" for s in audit)
    alerted = any(s["tool"] == "emit_alert" for s in audit)

    if decision == "ALLOW":
        if not signed:
            return False, "permit_but_no_sign"
        if alerted:
            return False, "permit_but_alerted"
    elif decision == "DENY":
        if signed:
            return False, "deny_but_signed"
        if not alerted:
            return False, "deny_but_no_alert"
    else:
        return False, f"unexpected_decision_{decision}"

    if not verdict:
        return False, "missing_verdict"
    expected_prefixes = ("REBAC_ALLOWED", "REBAC_DENIED", "[DRY-RUN]")
    if not verdict.startswith(expected_prefixes):
        return False, "verdict_wrong_prefix"

    return True, "ok"


def _emit_misbehavior(reason: str, audit: list[dict], verdict: str | None) -> None:
    """Emit Sentinel.AgentMisbehavior event when the AI breaks protocol."""
    detail = {
        "reason": reason,
        "audit": audit,
        "verdict": verdict,
        "dry_run": DRY_RUN,
    }
    if DRY_RUN:
        # Even misbehavior alerts are stubbed in dry-run.
        return
    try:
        _events.put_events(Entries=[{
            "Source": "sentinel.fips",
            "DetailType": "Sentinel.AgentMisbehavior",
            "Detail": json.dumps(detail),
        }])
    except Exception:
        # Best effort — do not raise from the misbehavior path.
        pass


def lambda_handler(event, context):
    body = event.get("body") if isinstance(event, dict) else None
    if isinstance(body, str):
        body = json.loads(body)
    body = body or event or {}

    principal = body.get("principal", "sentinel-agent")
    action = body.get("action", "Sign")
    resource = body.get("resource", "idp-config-bundle")
    bundle = body.get("bundle", "<idp-config-v1.yaml>")

    user_msg = (
        f"Signing request received.\n"
        f"  principal: {principal}\n"
        f"  action:    {action}\n"
        f"  resource:  {resource}\n"
        f"  bundle:    {bundle}\n"
        f"  mode:      {'DRY_RUN' if DRY_RUN else 'LIVE'}\n"
        f"Verify authorization and proceed per protocol."
    )

    messages = [{"role": "user", "content": user_msg}]
    audit: list[dict] = []
    verdict: str | None = None

    client = _client()
    for _ in range(8):
        resp = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=[{
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }],
            tools=TOOLS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": resp.content})

        if resp.stop_reason == "end_turn":
            for block in resp.content:
                if block.type == "text":
                    verdict = block.text.strip()
            break

        tool_results = []
        for block in resp.content:
            if block.type == "tool_use":
                result = _dispatch(block.name, block.input)
                audit.append({
                    "tool": block.name,
                    "input": block.input,
                    "result": result,
                })
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                })

        if not tool_results:
            break
        messages.append({"role": "user", "content": tool_results})

    # Decorate verdict with DRY_RUN prefix if applicable.
    if DRY_RUN and verdict and not verdict.startswith("[DRY-RUN]"):
        verdict = f"[DRY-RUN] {verdict}"

    # Structural self-policing.
    ok, reason = _validate_audit(audit, verdict)
    if not ok:
        _emit_misbehavior(reason, audit, verdict)
        forced_verdict = "REBAC_DENIED — agent misbehavior detected, request denied"
        # Structured log line so the CloudWatch metric filter on REBAC_DENIED matches.
        print(json.dumps({
            "verdict": forced_verdict,
            "agent_misbehavior": reason,
            "tools_called": [s["tool"] for s in audit],
            "dry_run": DRY_RUN,
        }))
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "verdict": forced_verdict,
                "audit": audit,
                "agent_misbehavior": reason,
                "dry_run": DRY_RUN,
            }),
        }

    # Structured log line — first token is the verdict, so CloudWatch metric
    # filters on REBAC_ALLOWED / REBAC_DENIED match correctly.
    print(json.dumps({
        "verdict": verdict,
        "tools_called": [s["tool"] for s in audit],
        "dry_run": DRY_RUN,
    }))

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "verdict": verdict,
            "audit": audit,
            "dry_run": DRY_RUN,
        }),
    }
