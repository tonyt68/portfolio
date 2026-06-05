import os
import json
import redis
import smtplib
import urllib.request
from datetime import datetime, timezone
from email.mime.text import MIMEText
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("sentinel-governance")
r = redis.Redis(host="localhost", port=6379, decode_responses=True)


def _check_rebac(subject: str, action: str, resource: str, visited: set = None) -> list | None:
    """Recursively traverse the ReBAC relationship graph to find an authorization chain."""
    if visited is None:
        visited = set()
    if subject in visited:
        return None
    visited.add(subject)

    # Direct permission at this node
    if r.sismember(f"rebac:{subject}:{action}", resource):
        return [f"{subject} --{action}--> {resource}"]

    # Traverse delegate_of links (sentinel-agent acts on behalf of tony)
    for delegate in r.smembers(f"rebac:{subject}:delegate_of"):
        path = _check_rebac(delegate, action, resource, visited)
        if path:
            return [f"{subject} --delegate_of--> {delegate}"] + path

    # Traverse member_of links (tony is member of platform-team)
    for group in r.smembers(f"rebac:{subject}:member_of"):
        path = _check_rebac(group, action, resource, visited)
        if path:
            return [f"{subject} --member_of--> {group}"] + path

    return None


@mcp.tool()
def check_rebac_permission(subject: str, action: str, resource: str) -> str:
    """Check if a subject is authorized to perform an action on a resource via ReBAC graph traversal.

    Args:
        subject: The entity requesting access (e.g. sentinel-agent).
        action: The action to perform (e.g. can_remediate).
        resource: The target resource (e.g. CryptoMining).
    """
    chain = _check_rebac(subject, action, resource)
    if chain:
        chain_str = " → ".join(chain)
        return f"REBAC_ALLOWED: {subject} is authorized to {action} {resource}\nChain: {chain_str}"
    return (
        f"REBAC_DENIED: {subject} is NOT authorized to {action} {resource}\n"
        "No authorization chain found. Membership revoked or relationship graph broken."
    )


@mcp.tool()
def send_audit_email(threat: str, action_details: str, state: str) -> str:
    """Send an audit email to the security team documenting the authorization decision.

    Args:
        threat: The threat type that was detected.
        action_details: Full description of the analysis and action taken.
        state: Execution state (e.g. QUARANTINE, REBAC_DENIED).
    """
    msg = MIMEText(f"ReBAC Authorization Report\n\nThreat: {threat}\nDetails: {action_details}")

    if state == "REBAC_DENIED":
        msg["Subject"] = "🔴 CRITICAL: Sentinel Authorization Chain Broken — Access DENIED"
    else:
        msg["Subject"] = "🟢 Sentinel: Threat Authorized & Remediated"

    msg["From"] = "sentinel@idp.local"
    msg["To"] = "security-audit@idp.local"

    port = int(os.getenv("SENTINEL_SMTP_PORT", 1025))
    try:
        with smtplib.SMTP("127.0.0.1", port, timeout=5) as server:
            server.sendmail("sentinel@idp.local", ["security-audit@idp.local"], msg.as_string())
        return f"✅ Audit email sent (Port {port})"
    except Exception as e:
        return f"❌ Email failed: {e}"


@mcp.tool()
def send_alert_webhook(threat: str, state: str, action_details: str) -> str:
    """POST a live alert to the webhook endpoint for real-time monitoring.

    Args:
        threat: The threat type that was detected.
        state: Execution state (e.g. QUARANTINE, REBAC_DENIED).
        action_details: Full description of the analysis and action taken.
    """
    url = os.getenv("SENTINEL_WEBHOOK_URL", "")
    if not url:
        return "WEBHOOK_SKIPPED: SENTINEL_WEBHOOK_URL not set"

    payload = json.dumps({
        "source": "Sentinel AI",
        "threat": threat,
        "state": state,
        "action": action_details,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }).encode()

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return f"✅ Webhook fired — {resp.status} ({url})"
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return (
                "❌ Webhook 404 — URL expired. Get a new one:\n"
                "   1. Open https://webhook.site in your browser\n"
                "   2. Copy your unique URL from the top of the page\n"
                "   3. export SENTINEL_WEBHOOK_URL=\"https://webhook.site/your-new-id\"\n"
                "   4. Re-run the POC"
            )
        return f"❌ Webhook failed: {e}"
    except Exception as e:
        return f"❌ Webhook failed: {e}"


if __name__ == "__main__":
    mcp.run()
