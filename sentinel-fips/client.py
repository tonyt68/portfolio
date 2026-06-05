#!/usr/bin/env python3
"""Sentinel FIPS demo client.

Posts a signing request to the orchestrator API and prints the verdict + tool trace.

Endpoint is read from the SENTINEL_ENDPOINT env var (set by demo.sh from the
CloudFormation outputs) or passed via --endpoint.
"""
import argparse
import json
import os
import sys
import urllib.request


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--endpoint", default=os.environ.get("SENTINEL_ENDPOINT"))
    p.add_argument("--principal", default="sentinel-agent")
    p.add_argument("--action", default="Sign")
    p.add_argument("--resource", default="idp-config-bundle")
    p.add_argument("--bundle", default="idp-config-v1.yaml: <privileged config payload>")
    args = p.parse_args()

    if not args.endpoint:
        print("error: set SENTINEL_ENDPOINT or pass --endpoint", file=sys.stderr)
        return 2

    body = json.dumps({
        "principal": args.principal,
        "action": args.action,
        "resource": args.resource,
        "bundle": args.bundle,
    }).encode()

    req = urllib.request.Request(
        args.endpoint,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    print(f"\n→ POST {args.endpoint}")
    print(f"  principal={args.principal} action={args.action} resource={args.resource}\n")

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode(errors='replace')}", file=sys.stderr)
        return 1

    body = json.loads(payload["body"]) if "body" in payload and isinstance(payload.get("body"), str) else payload

    print("=== Sentinel FIPS verdict ===")
    print(body.get("verdict") or "(no verdict)")
    print()
    print("Tool trace:")
    for step in body.get("audit", []):
        tool = step.get("tool")
        inp = json.dumps(step.get("input"), separators=(",", ":"))
        result = json.dumps(step.get("result"), separators=(",", ":"))
        if len(result) > 220:
            result = result[:217] + "..."
        print(f"  → {tool}({inp})")
        print(f"     ↳ {result}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
