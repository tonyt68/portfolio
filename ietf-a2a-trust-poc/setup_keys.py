#!/usr/bin/env python3
"""Generate signing keys and certificates for the PoC"""

import os
import json
from pathlib import Path
from datetime import datetime, timedelta
import secrets

def setup_signing_keys():
    """Generate owner and PA signing keys"""
    keys_dir = Path("./certs")
    keys_dir.mkdir(exist_ok=True)

    # Generate owner signing key (random 32-byte secret)
    owner_key = secrets.token_bytes(32)
    owner_key_path = keys_dir / "owner.key"
    with open(owner_key_path, "wb") as f:
        f.write(owner_key)
    os.chmod(owner_key_path, 0o600)
    print(f"✓ Owner signing key: {owner_key_path}")

    # Generate PA signing key (random 32-byte secret)
    pa_key = secrets.token_bytes(32)
    pa_key_path = keys_dir / "pa.key"
    with open(pa_key_path, "wb") as f:
        f.write(pa_key)
    os.chmod(pa_key_path, 0o600)
    print(f"✓ PA signing key: {pa_key_path}")

    return owner_key_path, pa_key_path


def setup_agent_certs():
    """Create demo agent certificates"""
    certs_dir = Path("./certs")
    certs_dir.mkdir(exist_ok=True)

    agents = [
        {
            "agent_id": "agent-a",
            "scopes": ["read:events"],
            "can_spawn": [],
            "ttl_days": 365
        },
        {
            "agent_id": "agent-b",
            "scopes": ["write:events"],
            "can_spawn": [],
            "ttl_days": 365
        }
    ]

    for agent in agents:
        cert_file = certs_dir / f"{agent['agent_id']}.json"
        cert_data = {
            "agent_id": agent["agent_id"],
            "state": "ACTIVE",
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(days=agent["ttl_days"])).isoformat(),
            "scopes": agent["scopes"],
            "can_spawn": agent["can_spawn"],
            "ttl_days": agent["ttl_days"]
        }

        with open(cert_file, "w") as f:
            json.dump(cert_data, f, indent=2)

        print(f"✓ Agent certificate: {cert_file}")


def setup_revocation_list():
    """Initialize empty Certificate Revocation List"""
    crl_file = Path("./certs/revocation_list.json")
    crl_data = {
        "revoked": [],
        "disabled": []
    }

    with open(crl_file, "w") as f:
        json.dump(crl_data, f, indent=2)

    print(f"✓ Certificate Revocation List: {crl_file}")


if __name__ == "__main__":
    print("Setting up A2A Trust PoC keys and certificates...\n")
    setup_signing_keys()
    print()
    setup_agent_certs()
    print()
    setup_revocation_list()
    print("\n✓ All keys and certificates ready!")
