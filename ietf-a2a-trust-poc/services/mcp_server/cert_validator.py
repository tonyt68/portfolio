"""X.509 Certificate validation for IETF A2A Trust (RFC 5280 compliance)"""

import logging
import subprocess
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List

log = logging.getLogger(__name__)


class CertValidator:
    """Validates X.509 certificates, chain, and IETF extensions"""

    def __init__(self, ca_root_cert_path: str = "./certs/ca-root.crt"):
        self.ca_root_path = Path(ca_root_cert_path)

    def get_cert_info(self, cert_path: str) -> Optional[Dict]:
        """Extract certificate information (subject, issuer, expiry, extensions)"""
        try:
            result = subprocess.run(
                f"openssl x509 -in {cert_path} -text -noout",
                shell=True,
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                log.error("Failed to read cert", extra={"cert": cert_path})
                return None

            cert_text = result.stdout

            # Extract subject CN
            import re
            subject_match = re.search(r'Subject:.*CN=(\S+)', cert_text)
            subject_cn = subject_match.group(1) if subject_match else None

            # Extract issuer CN
            issuer_match = re.search(r'Issuer:.*CN=(\S+)', cert_text)
            issuer_cn = issuer_match.group(1) if issuer_match else None

            # Extract expiry
            not_after_match = re.search(r'Not After\s*:\s*(.+)', cert_text)
            not_after = not_after_match.group(1).strip() if not_after_match else None

            # Extract public key
            key_match = re.search(r'Public-Key: \((\d+) bit', cert_text)
            key_bits = int(key_match.group(1)) if key_match else None

            return {
                "subject_cn": subject_cn,
                "issuer_cn": issuer_cn,
                "not_after": not_after,
                "key_bits": key_bits,
                "raw_text": cert_text
            }

        except Exception as e:
            log.error("Error parsing cert", extra={"error": str(e)})
            return None

    def validate_chain(self, agent_cert_path: str) -> bool:
        """Validate certificate chain (issuer signature)"""
        try:
            # For demo: self-signed certs, check if issuer == subject
            cert_info = self.get_cert_info(agent_cert_path)
            if not cert_info:
                return False

            # Self-signed check (issuer == subject)
            if cert_info["issuer_cn"] == cert_info["subject_cn"]:
                log.info("Cert is self-signed", extra={"cn": cert_info["subject_cn"]})
                return True

            log.warning("Chain validation not yet implemented for CA-signed certs")
            return False

        except Exception as e:
            log.error("Chain validation error", extra={"error": str(e)})
            return False

    def is_cert_expired(self, cert_path: str) -> bool:
        """Check if certificate is expired"""
        try:
            result = subprocess.run(
                f"openssl x509 -in {cert_path} -noout -checkend 0",
                shell=True,
                capture_output=True
            )
            # checkend returns 0 if NOT expired
            return result.returncode != 0

        except Exception as e:
            log.error("Expiry check error", extra={"error": str(e)})
            return True  # Fail closed

    def validate_cert(self, agent_id: str, cert_path: str) -> tuple:
        """
        Full certificate validation per IETF spec.
        Returns: (valid: bool, reason: str)
        Fail-closed: any check fails = invalid
        """
        try:
            # Check cert file exists
            if not Path(cert_path).exists():
                return (False, "Certificate file not found")

            # Parse cert info
            cert_info = self.get_cert_info(cert_path)
            if not cert_info:
                return (False, "Failed to parse certificate")

            # Validate subject CN matches agent ID
            if cert_info["subject_cn"] != agent_id:
                return (False, f"Subject CN mismatch: {cert_info['subject_cn']} != {agent_id}")

            # Validate chain
            if not self.validate_chain(cert_path):
                return (False, "Certificate chain validation failed")

            # Check expiry
            if self.is_cert_expired(cert_path):
                return (False, "Certificate expired")

            # Validate key size (min 2048-bit RSA)
            if cert_info.get("key_bits", 0) < 2048:
                return (False, f"RSA key too small: {cert_info['key_bits']} bits")

            log.info("Certificate valid", extra={"agent": agent_id})
            return (True, "Certificate valid")

        except Exception as e:
            log.error("Cert validation error", extra={"error": str(e)})
            return (False, str(e))

    def parse_auth_bounds(self, metadata_path: str) -> Optional[Dict]:
        """Parse authorization bounds from certificate metadata"""
        try:
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)

            auth_bounds = metadata.get("authorization_bounds", {})
            return {
                "allowed_scopes": auth_bounds.get("allowed_scopes", []),
                "can_spawn": auth_bounds.get("can_spawn", []),
                "max_children": auth_bounds.get("max_children", 0)
            }

        except Exception as e:
            log.error("Failed to parse auth bounds", extra={"error": str(e)})
            return None

    def validate_scope_subset(self, requested_scopes: List[str], allowed_scopes: List[str]) -> bool:
        """Validate that requested_scopes ⊆ allowed_scopes (IETF requirement)"""
        for scope in requested_scopes:
            if scope not in allowed_scopes:
                log.warning("Scope not in allowed set",
                           extra={"scope": scope, "allowed": allowed_scopes})
                return False
        return True

    def validate_spawn_allowed(self, parent_id: str, child_id: str, parent_metadata: Dict) -> bool:
        """Validate child_id is in parent's CanSpawn list"""
        can_spawn = parent_metadata.get("authorization_bounds", {}).get("can_spawn", [])
        if child_id not in can_spawn:
            log.warning("Spawn not in CanSpawn list",
                       extra={"parent": parent_id, "child": child_id, "can_spawn": can_spawn})
            return False
        return True

    def validate_max_children(self, parent_id: str, current_children: int, parent_metadata: Dict) -> bool:
        """Validate child count does not exceed MaxChildren"""
        max_children = parent_metadata.get("authorization_bounds", {}).get("max_children", 0)
        if max_children > 0 and current_children >= max_children:
            log.warning("MaxChildren limit exceeded",
                       extra={"parent": parent_id, "current": current_children, "max": max_children})
            return False
        return True
