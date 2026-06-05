#!/usr/bin/env python3
"""
TonyAI Security Portfolio — Launch Pad
Presents all security PoCs with a menu and launches the selected demo
in a new Terminal window.
"""

import subprocess
import sys

# ── ANSI colors ──────────────────────────────────────────────────
R   = "\033[0m"       # reset
B   = "\033[1m"       # bold
DIM = "\033[2m"       # dim
LG  = "\033[37m"      # light gray
CY  = "\033[96m"      # cyan
GR  = "\033[38;5;114m"  # light green
YL  = "\033[93m"      # yellow
PU  = "\033[95m"      # purple
BL  = "\033[94m"      # blue
RD  = "\033[91m"      # red
MRD = "\033[38;5;131m"  # muted red
WH  = "\033[97m"      # white

POCS = [
    {
        "name": "Last Mile Zero Trust",
        "desc": "Zero static credentials, no inbound firewall holes, cryptographic audit trail",
        "path": "/Users/tonyai/dev/last-mile-zero-trust",
        "cmd": "bash demo.sh",
        "stack": "Python, AWS SQS, HashiCorp Vault, PostgreSQL, Redis, ReBAC, JWT RS256, MCP",
        "compliance": "SOC2, PCI DSS v4, FIPS 140-3, NIST 800-207",
        "color": GR,
        "icon": "🛡️",
    },
    {
        "name": "Bedrock Agent + Last Mile — HIPAA AI Access",
        "desc": "AWS Bedrock Agent with secure, auditable access to on-prem patient records",
        "path": "/Users/tonyai/dev/last-mile-zero-trust/demos/hipaa-bedrock",
        "cmd": "bash demo_hipaa.sh",
        "stack": "Python, AWS Bedrock, SQS, Lambda, HashiCorp Vault, PostgreSQL, Redis, ReBAC",
        "compliance": "HIPAA, SOC2, FIPS 140-3, NIST 800-207",
        "color": BL,
        "icon": "🏥",
    },
    {
        "name": "Sentinel FIPS — AWS-Native FIPS 140-3 Security Boundary",
        "desc": "Dual auth before any AI action, KMS-signed decisions, tamper-proof audit trail",
        "path": "/Users/tonyai/dev/sentinel-fips",
        "cmd": "bash demo.sh",
        "stack": "Python, AWS Lambda, API Gateway, KMS, DynamoDB, Cedar/AVP, S3 Object Lock",
        "compliance": "FIPS 140-3, FedRAMP Moderate/High, SOC2, NIST 800-53",
        "color": YL,
        "icon": "🔒",
    },
    {
        "name": "Sentinel ReBAC — Agentic Authorization",
        "desc": "Relationship graph authorization — revoke one edge, enforcement stops everywhere",
        "path": "/Users/tonyai/dev/sentinel-rebac-poc",
        "cmd": "bash sentinel.sh",
        "stack": "Python, Redis, MCP, Claude Opus 4.7, Kubernetes, Docker",
        "compliance": "SOC2, OWASP A01/A04",
        "color": PU,
        "icon": "🕸️",
    },
    {
        "name": "Sentinel MCP — AWS Ops Toolkit",
        "desc": "Security investigation time cut from 45 minutes to 60 seconds",
        "path": "/Users/tonyai/dev/sentinel-mcp-poc",
        "cmd": "python sentinel_mcp_server.py",
        "stack": "Python, FastMCP, boto3, AWS DynamoDB, CloudTrail, CloudWatch, KMS, Lambda",
        "compliance": "SOC2, OWASP A05/A09",
        "color": CY,
        "icon": "⚡",
    },
    {
        "name": "RAG Knowledge Assistant — Enterprise AI Adoption",
        "desc": "Local knowledge base first — sensitive data never reaches an external API",
        "path": "/Users/tonyai/dev/rag-knowledge-assistant",
        "cmd": "npm start",
        "stack": "TypeScript, Node.js, Anthropic Claude SDK, JSON knowledge store",
        "compliance": "SOC2, OWASP A01/A09",
        "color": RD,
        "icon": "🧠",
    },
]

BANNER = f"""
{GR}╔══════════════════════════════════════════════════════════════════╗
║   🔐  TonyAI Security Portfolio — Launch Pad                     ║
║   Zero Trust · AI Governance · Identity · Compliance             ║
╚══════════════════════════════════════════════════════════════════╝{R}
"""

SEP = f"{DIM}  {'─' * 64}{R}"


def print_menu():
    print(BANNER)
    for i, poc in enumerate(POCS, 1):
        c = poc["color"]
        print(f"  {B}{PU}{i}. {poc['icon']}  {poc['name']}{R}")
        print(f"     {PU}{poc['desc']}{R}")
        print(f"     {LG}Stack:      {poc['stack']}{R}")
        print(f"     {LG}Compliance: {poc['compliance']}{R}")
        print(SEP)
    print(f"\n  {MRD}0. Exit{R}\n")


def launch(poc):
    script = f'cd {poc["path"]} && {poc["cmd"]}'
    subprocess.run([
        "osascript", "-e",
        f'tell application "Terminal" to do script "{script}"'
    ])
    print(f"\n  {GR}Launching:{R} {poc['name']}")
    print(f"  {DIM}Folder:   {poc['path']}")
    print(f"  Command:  {poc['cmd']}{R}\n")


def main():
    while True:
        print_menu()
        try:
            choice = input(f"  {GR}Select PoC to launch ({MRD}0 to exit{GR}):{R} ").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n  {DIM}Exiting.{R}")
            sys.exit(0)

        if choice == "0":
            print(f"\n  {DIM}Exiting.{R}\n")
            sys.exit(0)

        if not choice.isdigit() or not (1 <= int(choice) <= len(POCS)):
            print(f"\n  {RD}Invalid selection. Enter 1–{len(POCS)} or 0 to exit.{R}\n")
            continue

        launch(POCS[int(choice) - 1])
        input(f"  {DIM}Press Enter to return to menu...{R}")
        print()


if __name__ == "__main__":
    main()
