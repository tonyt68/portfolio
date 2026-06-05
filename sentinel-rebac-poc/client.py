import asyncio
import json
import os
import sys
from pathlib import Path

import anthropic
from anthropic.lib.tools.mcp import async_mcp_tool
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

MCP_SERVER = Path(__file__).parent / "mcp_server.py"

# Stable system prompt — cached after first request (ephemeral TTL 5 min).
SYSTEM_PROMPT = """You are Sentinel AI, an autonomous security governance analyst for an identity platform.

Your authorization is governed by a ReBAC (Relationship-Based Access Control) graph.
Before acting on any threat, you MUST verify your authorization chain.

When analyzing a security finding:
1. Call check_rebac_permission with subject="sentinel-agent", action="can_remediate", resource=<threat_type>
2. If REBAC_DENIED: you are NOT authorized to act — this is a CRITICAL incident.
   Call send_audit_email and send_alert_webhook with state="REBAC_DENIED" and halt immediately.
3. If REBAC_ALLOWED: proceed with remediation.
   Call send_audit_email and send_alert_webhook with state="QUARANTINE".
4. Return a concise verdict showing the authorization decision and execution state.

The authorization chain must be intact for every action. A broken chain means revoked access — escalate, never bypass."""


async def analyze_finding(finding_json: str) -> str:
    finding = json.loads(finding_json)
    threat = finding["detail"]["type"]

    print(f"\n🤖 [SENTINEL AI] Investigating {threat} event...")

    aclient = anthropic.AsyncAnthropic()

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(MCP_SERVER)],
        env={**os.environ},
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as mcp_session:
            await mcp_session.initialize()

            tools_result = await mcp_session.list_tools()
            tools = [async_mcp_tool(t, mcp_session) for t in tools_result.tools]

            runner = aclient.beta.messages.tool_runner(
                model="claude-opus-4-7",
                max_tokens=4096,
                thinking={"type": "adaptive", "display": "summarized"},
                system=[{
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }],
                tools=tools,
                messages=[{
                    "role": "user",
                    "content": f"Security finding detected:\n{finding_json}",
                }],
            )

            verdict = ""
            async for message in runner:
                for block in message.content:
                    if block.type == "thinking" and getattr(block, "thinking", ""):
                        preview = block.thinking[:300].replace("\n", " ")
                        print(f"💭 [THINKING]: {preview}...")
                    elif block.type == "tool_use":
                        if block.name == "check_rebac_permission":
                            print(f"🔐 [REBAC]: Checking authorization chain...")
                        elif block.name == "send_audit_email":
                            state = block.input.get("state", "UNKNOWN")
                            icon = "🔴" if state == "REBAC_DENIED" else "🟢"
                            print(f"\n{'='*50}")
                            print(f"{icon} [DECISION]")
                            print(f"   Threat : {block.input.get('threat', '?')}")
                            print(f"   State  : {state}")
                            print(f"   Action : {block.input.get('action_details', '?')}")
                            print(f"{'='*50}\n")
                        else:
                            print(f"📡 [WEBHOOK]: Firing live alert...")
                    elif block.type == "text" and block.text:
                        verdict = block.text

    print(f"🧠 [AI VERDICT]: {verdict}\n")
    return verdict


def main():
    finding = '{"detail": {"type": "CryptoMining"}}'
    asyncio.run(analyze_finding(finding))


if __name__ == "__main__":
    main()
