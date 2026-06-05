# AWS MCP Toolkit — AI-Powered Dev Operations
## From Manual CLI to Conversational Engineering

---

## What It Is

MCP (Model Context Protocol) is Anthropic's open standard for connecting AI models to external tools and data sources. AWS Labs publishes official MCP servers that expose AWS service APIs to Claude — turning natural language into AWS operations.

**The shift:**

```
Before MCP:  Engineer → terminal → CLI commands → parse JSON → repeat
After MCP:   Engineer → Claude → answer
```

Claude becomes the intelligent layer on top of your AWS environment. The engineer describes what they need. Claude figures out which services to query, correlates the results, and returns a plain-English answer.

---

## Architecture

```
Engineer (Claude Desktop / Claude Code)
    │
    ▼
MCP Client (built into Claude)
    │  MCP protocol (stdio)
    ▼
MCP Server (runs locally on your machine)
    │  AWS SDK calls (boto3)
    ▼
AWS Services (CloudWatch, Lambda, DynamoDB, CloudTrail, KMS, etc.)
    │
    ▼
Results → Claude → plain-English answer
```

**Key point:** The MCP server runs with your AWS credentials. Claude never has direct AWS access — it requests tool calls from the MCP server, which makes the actual API calls. The security boundary is the tools you expose and the IAM role you assign.

---

## Mac Setup — Claude Desktop + AWS MCP Server

Do this once — never manually login to AWS Console to check logs again.

### Step 1 — Install Claude Desktop

Download from `claude.ai/download` and install.

### Step 2 — Install uv (Python package runner)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

AWS Labs MCP servers run via `uvx` — no pip install needed.

### Step 3 — Configure AWS CLI

```bash
# Verify credentials are working
aws sts get-caller-identity

# If not configured
aws configure
# Access Key ID, Secret Access Key, region: us-east-1, output: json
```

### Step 4 — Configure Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "awslabs.core-mcp-server": {
      "command": "uvx",
      "args": ["awslabs.core-mcp-server@latest"],
      "env": {
        "AWS_REGION": "us-east-1",
        "AWS_PROFILE": "default",
        "FASTMCP_LOG_LEVEL": "ERROR"
      }
    },
    "awslabs.cloudwatch-logs-mcp-server": {
      "command": "uvx",
      "args": ["awslabs.cloudwatch-logs-mcp-server@latest"],
      "env": {
        "AWS_REGION": "us-east-1",
        "AWS_PROFILE": "default"
      }
    }
  }
}
```

Restart Claude Desktop. MCP tools appear automatically in the conversation.

### Step 5 — Test It

Open Claude Desktop and ask:
```
"Check the status of my sentinel-fips CloudFormation stack"
"Show me the last Lambda errors for sentinel-fips-orchestrator"
"Pull all CloudTrail KMS signing events from today"
```

No AWS Console. No CLI. Just ask.

---

## IAM Role for MCP — Sentinel FIPS

The MCP server needs its own scoped read-only role — not PowerUserAccess, not the operator role. Least privilege, same as everything else in this system.

The `sentinel-fips-mcp` role is defined in `template.yaml` and can be assumed by the demo user:

```
sentinel-demo (IAM user)
    → assumes sentinel-fips-mcp (read-only, scoped to Sentinel resources)
        → MCP server makes read-only calls
```

**Permissions scoped to:**
- `dynamodb:GetItem`, `dynamodb:Scan` → sentinel-rebac table only
- `logs:FilterLogEvents`, `logs:GetLogEvents` → orchestrator log group only
- `cloudtrail:LookupEvents` → read-only, account-wide
- `kms:Verify` → signing key only
- `cloudwatch:GetMetricData`, `cloudwatch:DescribeAlarms`
- `cloudformation:DescribeStacks`, `cloudformation:DescribeStackEvents`
- `lambda:GetFunctionConfiguration`

To assume the role for MCP:

```bash
# Add to ~/.aws/config
[profile sentinel-mcp]
role_arn = arn:aws:iam::537543783079:role/sentinel-fips-mcp
source_profile = default

# Then use in claude_desktop_config.json
"AWS_PROFILE": "sentinel-mcp"
```

---

## Use Cases

### Debug a Lambda Failure

```
Engineer: "My sentinel-fips-orchestrator Lambda is returning 502 errors"

Claude:
  → GetFunctionConfiguration → checks timeout, memory, env vars
  → FilterLogEvents → pulls last 50 error entries
  → GetTraceSummaries → checks X-Ray for slow segments
  → Returns: "Cold start at 28.4s exceeding 30s timeout.
              Increase timeout or reduce cold start — largest contributor
              is Secrets Manager GetSecretValue (11s)."
```

### Troubleshoot a Branch in Dev

```
Engineer: "Branch feature/rebac-v2 is deployed to dev — authorization
           is failing but works in local tests"

Claude:
  → DescribeStacks → finds sentinel-fips-dev stack
  → GetFunctionConfiguration → checks REBAC_TABLE env var
    (points to wrong table — dev stack using prod table name)
  → Scan → reads DynamoDB tuples in dev table (empty — not seeded)
  → Returns: "Dev stack REBAC_TABLE points to sentinel-rebac,
              which exists but has no tuples. Seed the dev table."
```

### Monitor After Deploy

```
Engineer: "Deploy just finished — is everything healthy?"

Claude:
  → DescribeStacks → confirms CREATE_COMPLETE
  → DescribeAlarms → checks all CloudWatch alarms
  → FilterLogEvents → scans for errors in last 5 minutes
  → Returns: "Stack healthy. One alarm in INSUFFICIENT_DATA
              (RebacDenyBurst — no traffic yet, expected).
              No Lambda errors. Ready."
```

### Deploy Without a Pipeline

```
Engineer: "Deploy sentinel-fips with DryRun=false and my API key"

Claude:
  → runs sam build
  → runs sam deploy with correct capabilities and parameter overrides
  → tails CloudFormation events in real time
  → reports success or explains what failed with the fix
```

---

## Sentinel FIPS MCP Server — v2 PoC

A purpose-built MCP server for Sentinel FIPS audit and operations. No AWS Console, no CLI, no manual log parsing.

### What It Replaces

| Today (manual) | With Sentinel MCP |
|---|---|
| Console → DynamoDB → scan table | *"Is the ReBAC chain intact?"* |
| CloudTrail → filter kms:Sign → parse JSON | *"Show me all signing events this week"* |
| CloudWatch → log group → filter DENIED | *"Why was the last request denied?"* |
| CloudTrail → filter DeleteItem → parse | *"Did anyone change the graph today?"* |

### Implementation — `sentinel_mcp_server.py`

```python
import json
from datetime import datetime, timedelta, timezone
import boto3
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("sentinel-fips")

TABLE_NAME = "sentinel-rebac"
LOG_GROUP = "/aws/lambda/sentinel-fips-orchestrator"
KMS_KEY_ID = "alias/sentinel-fips"

dynamodb = boto3.resource("dynamodb")
cloudtrail = boto3.client("cloudtrail")
logs = boto3.client("logs")
kms = boto3.client("kms")


@mcp.tool()
def check_chain_status() -> str:
    """Check if the ReBAC authorization chain is currently intact."""
    table = dynamodb.Table(TABLE_NAME)
    item = table.get_item(
        Key={"subject_relation": "tony#member_of"}
    ).get("Item")
    return "INTACT — tony#member_of present" if item else "BROKEN — tony#member_of missing"


@mcp.tool()
def get_full_chain() -> list[dict]:
    """Return all ReBAC tuples currently in the graph."""
    table = dynamodb.Table(TABLE_NAME)
    items = table.scan().get("Items", [])
    return [{"key": i["subject_relation"], "objects": list(i.get("objects", []))}
            for i in items]


@mcp.tool()
def get_signing_history(hours: int = 24) -> list[dict]:
    """Return all KMS signing events from CloudTrail for the last N hours."""
    start = datetime.now(timezone.utc) - timedelta(hours=hours)
    events = cloudtrail.lookup_events(
        LookupAttributes=[{"AttributeKey": "EventName", "AttributeValue": "Sign"}],
        StartTime=start,
        MaxResults=50
    )
    return [
        {"time": str(e["EventTime"]), "user": e.get("Username", "unknown")}
        for e in events.get("Events", [])
    ]


@mcp.tool()
def get_denial_history(hours: int = 24) -> list[str]:
    """Return all REBAC_DENIED events from CloudWatch for the last N hours."""
    start_ms = int((datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp() * 1000)
    response = logs.filter_log_events(
        logGroupName=LOG_GROUP,
        startTime=start_ms,
        filterPattern="REBAC_DENIED"
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
    """Return all ReBAC graph modifications from CloudTrail for the last N hours."""
    start = datetime.now(timezone.utc) - timedelta(hours=hours)
    events = cloudtrail.lookup_events(
        LookupAttributes=[{"AttributeKey": "ResourceName", "AttributeValue": TABLE_NAME}],
        StartTime=start,
        MaxResults=50
    )
    return [
        {"time": str(e["EventTime"]), "action": e["EventName"], "user": e.get("Username", "unknown")}
        for e in events.get("Events", [])
    ]


@mcp.tool()
def verify_signature(signature_hex: str, message: str) -> str:
    """Verify a KMS RSA-PSS signature against the original message."""
    try:
        result = kms.verify(
            KeyId=KMS_KEY_ID,
            Message=message.encode(),
            MessageType="RAW",
            Signature=bytes.fromhex(signature_hex),
            SigningAlgorithm="RSASSA_PSS_SHA_256"
        )
        return "VALID" if result["SignatureValid"] else "INVALID"
    except Exception as e:
        return f"ERROR: {e}"


if __name__ == "__main__":
    mcp.run()
```

### Install and Run

```bash
# Install dependencies
pip install mcp boto3

# Run the server (from the sentinel-fips project root)
python sentinel_mcp_server.py
```

### Wire into Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "sentinel-fips": {
      "command": "python",
      "args": ["/Users/tonyai/dev/sentinel-mcp-poc/sentinel_mcp_server.py"],
      "env": {
        "AWS_REGION": "us-east-1",
        "AWS_PROFILE": "sentinel-mcp"
      }
    }
  }
}
```

### How You Use It

```
You: "Is the chain intact?"
Claude → check_chain_status() → "INTACT — tony#member_of present"

You: "Show me everything signed yesterday"
Claude → get_signing_history(24) → timestamped table

You: "Why was the last request denied?"
Claude → get_denial_history(1) → verdict from CloudWatch

You: "Did anyone change the ReBAC graph today?"
Claude → get_chain_changes(24) → who changed what and when

You: "Verify this signature: abc123..."
Claude → verify_signature("abc123...", "bundle content") → "VALID"
```

---

## Company MCP Server — The Force Multiplier

An AWS MCP server gives Claude access to AWS. A company MCP server gives Claude access to internal systems — runbooks, ticketing, deployments, feature flags, service catalog. Combined, Claude becomes a company-aware engineering assistant.

```
Claude
  → AWS MCP server        (CloudWatch, Lambda, DynamoDB, X-Ray)
  → Company MCP server    (Jira, Confluence runbooks, pipelines,
                           feature flags, service catalog, on-call)
```

### What a Company MCP Server Exposes

| Tool | What it does |
|---|---|
| `get_runbook` | Pulls runbook from Confluence by service name |
| `get_deployment` | Returns what is deployed where and from which branch |
| `get_feature_flags` | Current flag state per environment |
| `create_ticket` | Opens an incident ticket from the diagnosis |
| `get_service_owner` | Who owns the service, who is on-call |
| `get_pipeline_status` | Last build result, test failures, deployment gate |

### The Velocity Story

```
Engineer: "Why is checkout failing in staging?"

Claude:
  → pulls CloudWatch logs            (AWS MCP)
  → finds the error
  → searches Confluence for runbook  (Company MCP)
  → checks Jira for open tickets     (Company MCP)
  → checks feature flag state        (Company MCP)
  → returns full diagnosis + runbook link + ticket + flag owner
```

That answer took a senior engineer 45 minutes. Claude returns it in 60 seconds.

---

## Security Model

| Concern | Answer |
|---|---|
| Is it like SSH? | No — scoped API proxy, not a shell. Claude calls predefined tools only. No arbitrary command execution. |
| Prompt injection risk? | Scope IAM to read-only in prod. A malicious log entry cannot cause write operations if the role does not allow them. |
| Are credentials exposed? | MCP server uses local AWS credentials or an assumed role. Claude never sees credentials directly. |
| Can it touch production? | Only if the IAM role allows it. Sentinel MCP role is read-only by design. |

---

## What to Know for the Interview

| Question | Answer |
|---|---|
| "What is MCP?" | Open protocol for connecting AI to external tools. AWS Labs publishes MCP servers for their services. Claude + MCP server = conversational AWS operations. |
| "How is it different from Bedrock Agents?" | MCP is for interactive dev/ops — human in the loop. Bedrock Agents is for autonomous production workloads. Different use cases, not competitors. |
| "Is it safe?" | Scoped API proxy, not a shell. Safety is the IAM role. Read-only in prod, scoped write in dev — same posture as any service account. |
| "When would you NOT use it?" | Unattended production automation — use a pipeline. MCP is for humans working interactively. |
| "How does it help teams?" | Removes the CLI expertise barrier. Any engineer investigates any service in plain language. Faster debugging, faster post-deploy verification, faster PoC iteration. |
| "What about a company MCP server?" | Expose internal tools — runbooks, Jira, feature flags — alongside AWS. Junior engineer gets a senior's diagnosis in 60 seconds. That is the AI enablement investment. |
