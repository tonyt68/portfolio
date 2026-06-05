import logging
import json
import hashlib
from typing import Optional
from pathlib import Path

log = logging.getLogger(__name__)


class PolicyAuthority:
    """Validates dual-signature (Owner + Policy Authority) on policy changes using X.509 certs"""

    def __init__(self, owner_cert_path: str, owner_key_path: str, pa_cert_path: str, pa_key_path: str):
        """
        Initialize with X.509 certificates and private keys.
        Uses RSA signatures for IETF compliance.
        """
        self.owner_cert_path = Path(owner_cert_path)
        self.owner_key_path = Path(owner_key_path)
        self.pa_cert_path = Path(pa_cert_path)
        self.pa_key_path = Path(pa_key_path)

    def _sign_data(self, data: str, key_path: Path) -> Optional[str]:
        """Sign data with RSA private key using OpenSSL"""
        try:
            import subprocess
            import tempfile

            # Write data to temp file
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
                f.write(data)
                data_file = f.name

            try:
                # Sign with openssl
                result = subprocess.run(
                    f"openssl dgst -sha256 -sign {key_path} {data_file} | openssl enc -base64 -A",
                    shell=True,
                    capture_output=True,
                    text=True
                )

                if result.returncode != 0:
                    log.error("OpenSSL signing error", extra={"error": result.stderr})
                    return None

                return result.stdout.strip()

            finally:
                import os
                os.unlink(data_file)

        except Exception as e:
            log.error("Failed to sign data", extra={"error": str(e)})
            return None

    def _verify_sig(self, data: str, sig: str, cert_path: Path) -> bool:
        """Verify RSA signature using X.509 certificate"""
        try:
            import subprocess
            import tempfile

            # Write data to temp file
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
                f.write(data)
                data_file = f.name

            # Write signature to temp file
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.sig') as f:
                f.write(sig)
                sig_file = f.name

            try:
                # Verify with openssl
                result = subprocess.run(
                    f"openssl enc -d -base64 -A -in {sig_file} | "
                    f"openssl dgst -sha256 -verify <(openssl x509 -in {cert_path} -pubkey -noout) "
                    f"-signature /dev/stdin {data_file}",
                    shell=True,
                    executable="/bin/bash",
                    capture_output=True,
                    text=True
                )

                return "Verified OK" in result.stdout

            finally:
                import os
                os.unlink(data_file)
                os.unlink(sig_file)

        except Exception as e:
            log.error("Signature verification error", extra={"error": str(e)})
            return False

    def validate_dual_sig(self, policy_doc: dict, owner_sig: str, pa_sig: str) -> bool:
        """
        Validate that policy change has both Owner and Policy Authority RSA signatures.
        Fail-closed: missing or invalid signature = DENY
        """
        try:
            # Check signatures present
            if not owner_sig:
                log.warning("Owner signature missing")
                return False

            if not pa_sig:
                log.warning("Policy Authority signature missing")
                return False

            # Check certs exist
            if not self.owner_cert_path.exists() or not self.pa_cert_path.exists():
                log.error("Certificates not found")
                return False

            # Normalize policy document for signing
            policy_json = json.dumps(policy_doc, sort_keys=True)

            # Verify owner signature
            if not self._verify_sig(policy_json, owner_sig, self.owner_cert_path):
                log.warning("Owner signature invalid", extra={"policy": policy_doc.get('name')})
                return False

            # Verify PA signature
            if not self._verify_sig(policy_json, pa_sig, self.pa_cert_path):
                log.warning("PA signature invalid", extra={"policy": policy_doc.get('name')})
                return False

            log.info("Dual-sig validation passed (RSA X.509)",
                    extra={"policy": policy_doc.get('name')})
            return True

        except Exception as e:
            log.error("Dual-sig validation error", extra={"error": str(e)})
            return False

    def create_dual_sig(self, policy_doc: dict) -> tuple:
        """Create RSA dual signatures for a policy document"""
        try:
            if not self.owner_key_path.exists() or not self.pa_key_path.exists():
                log.error("Signing keys not found")
                return (None, None)

            # Normalize policy document for signing
            policy_json = json.dumps(policy_doc, sort_keys=True)

            # Sign with owner key
            owner_sig = self._sign_data(policy_json, self.owner_key_path)
            if not owner_sig:
                log.error("Failed to create owner signature")
                return (None, None)

            # Sign with PA key
            pa_sig = self._sign_data(policy_json, self.pa_key_path)
            if not pa_sig:
                log.error("Failed to create PA signature")
                return (None, None)

            log.info("Dual signatures created (RSA X.509)", extra={"policy": policy_doc.get('name')})
            return (owner_sig, pa_sig)

        except Exception as e:
            log.error("Failed to create signatures", extra={"error": str(e)})
            return (None, None)
