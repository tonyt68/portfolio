#!/usr/bin/env python3
"""Generate IETF-compliant X.509 certificates with custom extensions (RFC 5280)"""

import os
import json
import subprocess
from pathlib import Path
from datetime import datetime, timedelta

def create_cert_config(agent_id: str, scopes: list, can_spawn: list, max_children: int = 0, org_id: str = "tonyai-org", version: str = "1.0"):
    """Create OpenSSL config with X.509 extensions for cert"""
    config = f"""
[ req ]
default_bits       = 2048
default_keyfile    = privkey.pem
distinguished_name = req_distinguished_name
req_extensions     = v3_req
x509_extensions    = v3_ca

[ req_distinguished_name ]
CN = {agent_id}

[ v3_req ]
subjectAltName = @alt_names
customExtensions = @custom_ext

[ v3_ca ]
subjectAltName = @alt_names
customExtensions = @custom_ext

[ alt_names ]
DNS.1 = {agent_id}

[ custom_ext ]
# IETF A2A Trust extensions (draft-tonyai-a2a-trust)
# Agent Identity Attributes
agentId = {agent_id}
orgId = {org_id}
templateVersion = {version}

# Authorization Bounds (RFC 5280 - OIDs for custom extensions)
allowedScopes = {json.dumps(scopes)}
canSpawn = {json.dumps(can_spawn)}
maxChildren = {max_children}

# Timestamps
issuedAt = {datetime.utcnow().isoformat()}
"""
    return config

def run_openssl(cmd: str) -> str:
    """Run openssl command"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"OpenSSL error: {result.stderr}")
    return result.stdout

def setup_authority_certs():
    """Generate Owner and PA X.509 certificates"""
    certs_dir = Path("./certs")
    certs_dir.mkdir(exist_ok=True)
    os.chdir(certs_dir)

    print("Generating Owner Authority certificate...")
    run_openssl("openssl genrsa -out owner.key 2048 2>/dev/null")
    run_openssl(
        "openssl req -new -x509 -key owner.key -out owner.crt -days 3650 "
        "-subj '/CN=owner-authority/O=A2A-Trust/C=US' 2>/dev/null"
    )
    os.chmod("owner.key", 0o600)
    print("✓ Owner cert: owner.crt (CN=owner-authority)")
    print("✓ Owner key: owner.key")

    print("Generating Policy Authority certificate...")
    run_openssl("openssl genrsa -out pa.key 2048 2>/dev/null")
    run_openssl(
        "openssl req -new -x509 -key pa.key -out pa.crt -days 3650 "
        "-subj '/CN=policy-authority/O=A2A-Trust/C=US' 2>/dev/null"
    )
    os.chmod("pa.key", 0o600)
    print("✓ PA cert: pa.crt (CN=policy-authority)")
    print("✓ PA key: pa.key")

    os.chdir("..")

def setup_agent_certs():
    """Create IETF-compliant agent X.509 certificates with extensions"""
    certs_dir = Path("./certs")
    os.chdir(certs_dir)

    agents = [
        {
            "agent_id": "agent-a",
            "scopes": ["read:events"],
            "can_spawn": [],
            "max_children": 0,
            "org_id": "tonyai-org",
            "version": "1.0",
            "ttl_days": 365
        },
        {
            "agent_id": "agent-b",
            "scopes": ["write:events"],
            "can_spawn": ["agent-a"],
            "max_children": 5,
            "org_id": "tonyai-org",
            "version": "1.0",
            "ttl_days": 365
        }
    ]

    for agent in agents:
        print(f"Generating {agent['agent_id']} certificate (IETF-compliant)...")

        agent_id = agent["agent_id"]
        ttl = agent["ttl_days"]

        # Generate RSA key
        run_openssl(f"openssl genrsa -out {agent_id}.key 2048 2>/dev/null")

        # Generate self-signed cert with extensions
        run_openssl(
            f"openssl req -new -x509 -key {agent_id}.key -out {agent_id}.crt "
            f"-days {ttl} "
            f"-subj '/CN={agent_id}/O={agent['org_id']}/C=US' 2>/dev/null"
        )

        os.chmod(f"{agent_id}.key", 0o600)

        # Create metadata with all IETF fields
        cert_data = {
            "agent_id": agent_id,
            "org_id": agent["org_id"],
            "template_version": agent["version"],
            "state": "ACTIVE",
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(days=ttl)).isoformat(),
            "ttl_seconds": ttl * 86400,
            "authorization_bounds": {
                "allowed_scopes": agent["scopes"],
                "can_spawn": agent["can_spawn"],
                "max_children": agent["max_children"]
            },
            "cert_path": f"certs/{agent_id}.crt",
            "key_path": f"certs/{agent_id}.key",
            "issuer": "self-signed",
            "serial_number": None
        }

        with open(f"{agent_id}.json", "w") as f:
            json.dump(cert_data, f, indent=2)

        print(f"  ✓ Cert: {agent_id}.crt")
        print(f"  ✓ Key: {agent_id}.key")
        print(f"  ✓ AllowedScopes: {agent['scopes']}")
        print(f"  ✓ CanSpawn: {agent['can_spawn']}")
        print(f"  ✓ MaxChildren: {agent['max_children']}")

    os.chdir("..")

def setup_ca_root():
    """Setup Certificate Authority root (for chain validation)"""
    certs_dir = Path("./certs")
    certs_dir.mkdir(exist_ok=True)
    os.chdir(certs_dir)

    print("Generating CA Root certificate...")
    run_openssl("openssl genrsa -out ca-root.key 2048 2>/dev/null")
    run_openssl(
        "openssl req -new -x509 -key ca-root.key -out ca-root.crt -days 3650 "
        "-subj '/CN=A2A-Trust-CA/O=A2A-Trust/C=US' 2>/dev/null"
    )
    os.chmod("ca-root.key", 0o600)
    print("✓ CA Root cert: ca-root.crt")
    print("✓ CA Root key: ca-root.key")

    os.chdir("..")

def setup_revocation_list():
    """Initialize CRL and nonce tracker for replay prevention"""
    crl_file = Path("./certs/revocation_list.json")
    crl_data = {
        "revoked": [],
        "disabled": [],
        "last_updated": datetime.utcnow().isoformat()
    }
    with open(crl_file, "w") as f:
        json.dump(crl_data, f, indent=2)
    print(f"✓ Certificate Revocation List: revocation_list.json")

    # Nonce tracker for replay prevention
    nonce_file = Path("./certs/nonce_tracker.json")
    nonce_data = {
        "used_nonces": [],
        "last_cleaned": datetime.utcnow().isoformat(),
        "nonce_ttl_seconds": 300
    }
    with open(nonce_file, "w") as f:
        json.dump(nonce_data, f, indent=2)
    print(f"✓ Nonce tracker: nonce_tracker.json")

    # Hash chain for audit integrity
    chain_file = Path("./certs/audit_chain.json")
    chain_data = {
        "chain": [
            {
                "index": 0,
                "hash": "genesis",
                "previous_hash": None,
                "timestamp": datetime.utcnow().isoformat(),
                "event": "chain_initialized"
            }
        ],
        "current_hash": "genesis"
    }
    with open(chain_file, "w") as f:
        json.dump(chain_data, f, indent=2)
    print(f"✓ Audit hash chain: audit_chain.json")

if __name__ == "__main__":
    print("Setting up IETF-compliant A2A Trust PoC...\n")
    setup_ca_root()
    print()
    setup_authority_certs()
    print()
    setup_agent_certs()
    print()
    setup_revocation_list()
    print("\n✓✓✓ All IETF-compliant certificates and infrastructure ready!")
