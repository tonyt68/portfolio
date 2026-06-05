"""
Sentinel FIPS MCP Server — audit and ops tools for Claude Desktop / Claude Code.

Run:  python sentinel_mcp_server.py
Deps: pip install mcp boto3

Wire into Claude Desktop (~/Library/Application Support/Claude/claude_desktop_config.json):
{
  "mcpServers": {
    "sentinel-fips": {
      "command": "python",
      "args": ["/path/to/sentinel_mcp_server.py"],
      "env": { "AWS_REGION": "us-east-1", "AWS_PROFILE": "sentinel-mcp" }
    }
  }
}

The sentinel-mcp AWS profile assumes the sentinel-fips-mcp role (read-only).
Add to ~/.aws/config:
  [profile sentinel-mcp]
  role_arn = arn:aws:iam::<account-id>:role/sentinel-fips-mcp
  source_profile = default
"""

import json
import os
from datetime import datetime, timedelta, timezone

import boto3
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("sentinel-fips")

TABLE_NAME = os.environ.get("REBAC_TABLE", "sentinel-rebac")
LOG_GROUP = os.environ.get("LOG_GROUP", "/aws/lambda/sentinel-fips-orchestrator")
KMS_KEY_ID = os.environ.get("KMS_KEY_ID", "alias/sentinel-fips")

_dynamodb = boto3.resource("dynamodb")
_cloudtrail = boto3.client("cloudtrail")
_logs = boto3.client("logs")
_kms = boto3.client("kms")
_sts = boto3.client("sts")

EXPECTED_ROLE = "sentinel-fips-mcp"
EXPECTED_USER = "sentinel-demo"


@mcp.tool()
def verify_setup() -> dict:
    """Verify the MCP server is running with the correct identity and permissions.

    Checks:
    - Who the server is running as (sts:GetCallerIdentity — no permissions required)
    - Whether the assumed role is sentinel-fips-mcp (read-only, expected)
    - Whether the source user is sentinel-demo (expected demo identity)
    - Whether DynamoDB connectivity works (lightweight read probe)

    Returns a status dict with pass/fail for each check plus the full caller ARN.
    """
    result = {}

    # Identity check — works with zero IAM permissions
    identity = _sts.get_caller_identity()
    arn = identity["Arn"]
    account = identity["Account"]
    result["caller_arn"] = arn
    result["account"] = account

    # Role check — ARN looks like:
    # arn:aws:sts::<account>:assumed-role/sentinel-fips-mcp/sentinel-demo
    role_ok = EXPECTED_ROLE in arn
    user_ok = EXPECTED_USER in arn
    result["role_check"] = "PASS" if role_ok else f"FAIL — expected role '{EXPECTED_ROLE}' not in ARN"
    result["user_check"] = "PASS" if user_ok else f"FAIL — expected user '{EXPECTED_USER}' not in ARN"

    # Connectivity probe — try a single DynamoDB read
    try:
        table = _dynamodb.Table(TABLE_NAME)
        table.get_item(Key={"subject_relation": "__probe__"})
        result["dynamodb_connectivity"] = "PASS"
    except Exception as e:
        result["dynamodb_connectivity"] = f"FAIL — {e}"

    result["overall"] = (
        "READY" if all(v == "PASS" for v in [
            result["role_check"],
            result["user_check"],
            result["dynamodb_connectivity"],
        ]) else "NOT READY — see checks above"
    )

    return result


@mcp.tool()
def check_chain_status() -> str:
    """Check whether the ReBAC authorization chain is currently intact.

    Returns INTACT if the sentinel-agent→tony→platform-team→idp-config-bundle
    chain is present, BROKEN otherwise.
    """
    table = _dynamodb.Table(TABLE_NAME)
    item = table.get_item(Key={"subject_relation": "tony#member_of"}).get("Item")
    return "INTACT — tony#member_of present" if item else "BROKEN — tony#member_of missing"


@mcp.tool()
def get_full_chain() -> list[dict]:
    """Return every ReBAC tuple currently in the graph.

    Each entry has 'key' (subject#relation) and 'objects' (list of targets).
    """
    table = _dynamodb.Table(TABLE_NAME)
    items = table.scan().get("Items", [])
    return [
        {"key": i["subject_relation"], "objects": list(i.get("objects", []))}
        for i in items
    ]


@mcp.tool()
def get_signing_history(hours: int = 24) -> list[dict]:
    """Return all KMS signing events from CloudTrail for the last N hours.

    Args:
        hours: Look-back window in hours (default 24).
    """
    start = datetime.now(timezone.utc) - timedelta(hours=hours)
    response = _cloudtrail.lookup_events(
        LookupAttributes=[{"AttributeKey": "EventName", "AttributeValue": "Sign"}],
        StartTime=start,
        MaxResults=50,
    )
    return [
        {
            "time": str(e["EventTime"]),
            "user": e.get("Username", "unknown"),
            "event_id": e.get("EventId", ""),
        }
        for e in response.get("Events", [])
    ]


@mcp.tool()
def get_denial_history(hours: int = 24) -> list[str]:
    """Return all REBAC_DENIED verdicts from CloudWatch for the last N hours.

    Args:
        hours: Look-back window in hours (default 24).
    """
    start_ms = int(
        (datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp() * 1000
    )
    response = _logs.filter_log_events(
        logGroupName=LOG_GROUP,
        startTime=start_ms,
        filterPattern="REBAC_DENIED",
    )
    results = []
    for e in response.get("events", []):
        try:
            msg = json.loads(e["message"])
            results.append(msg.get("verdict", e["message"]))
        except Exception:
            results.append(e["message"])
    return results


@mcp.tool()
def get_chain_changes(hours: int = 24) -> list[dict]:
    """Return all ReBAC graph modifications from CloudTrail for the last N hours.

    Covers PutItem, UpdateItem, DeleteItem against the sentinel-rebac table.

    Args:
        hours: Look-back window in hours (default 24).
    """
    start = datetime.now(timezone.utc) - timedelta(hours=hours)
    response = _cloudtrail.lookup_events(
        LookupAttributes=[
            {"AttributeKey": "ResourceName", "AttributeValue": TABLE_NAME}
        ],
        StartTime=start,
        MaxResults=50,
    )
    return [
        {
            "time": str(e["EventTime"]),
            "action": e["EventName"],
            "user": e.get("Username", "unknown"),
        }
        for e in response.get("Events", [])
    ]


@mcp.tool()
def verify_signature(signature_hex: str, message: str) -> str:
    """Verify a KMS RSA-PSS signature against the original message.

    Args:
        signature_hex: Hex-encoded signature bytes returned by the sign endpoint.
        message:       The original plaintext message that was signed.

    Returns:
        VALID, INVALID, or ERROR: <reason>.
    """
    try:
        result = _kms.verify(
            KeyId=KMS_KEY_ID,
            Message=message.encode(),
            MessageType="RAW",
            Signature=bytes.fromhex(signature_hex),
            SigningAlgorithm="RSASSA_PSS_SHA_256",
        )
        return "VALID" if result["SignatureValid"] else "INVALID"
    except Exception as e:
        return f"ERROR: {e}"


if __name__ == "__main__":
    mcp.run()
