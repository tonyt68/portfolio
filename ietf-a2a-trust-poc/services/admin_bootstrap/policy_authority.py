import logging
import json
import hmac
import hashlib
from typing import Optional

log = logging.getLogger(__name__)


class PolicyAuthority:
    """Validates dual-signature (Owner + Policy Authority) on policy changes"""

    def __init__(self, owner_key_path: str, pa_key_path: str):
        """
        Initialize with signing keys.
        owner_key_path: Path to owner's HMAC secret
        pa_key_path: Path to PA's HMAC secret
        """
        self.owner_key = self._load_key(owner_key_path)
        self.pa_key = self._load_key(pa_key_path)

    def _load_key(self, key_path: str) -> Optional[bytes]:
        """Load key from file"""
        try:
            with open(key_path, 'rb') as f:
                key = f.read()
                if key:
                    return key
                else:
                    log.warning("Key file empty", extra={"path": key_path})
                    return None
        except FileNotFoundError:
            log.warning("Key file not found", extra={"path": key_path})
            return None
        except Exception as e:
            log.error("Failed to load key", extra={"path": key_path, "error": str(e)})
            return None

    def validate_dual_sig(self, policy_doc: dict, owner_sig: str, pa_sig: str) -> bool:
        """
        Validate that policy change has both Owner and Policy Authority signatures.
        Fail-closed: missing or invalid signature = DENY
        """
        try:
            if not owner_sig:
                log.warning("Owner signature missing")
                return False

            if not pa_sig:
                log.warning("Policy Authority signature missing")
                return False

            if not self.owner_key or not self.pa_key:
                log.error("Signing keys not loaded")
                return False

            policy_json = json.dumps(policy_doc, sort_keys=True)

            expected_owner_sig = hmac.new(
                self.owner_key,
                policy_json.encode(),
                hashlib.sha256
            ).hexdigest()

            if not hmac.compare_digest(owner_sig, expected_owner_sig):
                log.warning("Owner signature invalid", extra={"policy": policy_doc.get('name')})
                return False

            expected_pa_sig = hmac.new(
                self.pa_key,
                policy_json.encode(),
                hashlib.sha256
            ).hexdigest()

            if not hmac.compare_digest(pa_sig, expected_pa_sig):
                log.warning("PA signature invalid", extra={"policy": policy_doc.get('name')})
                return False

            log.info("Dual-sig validation passed",
                    extra={"policy": policy_doc.get('name')})
            return True

        except Exception as e:
            log.error("Dual-sig validation error", extra={"error": str(e)})
            return False

    def create_dual_sig(self, policy_doc: dict) -> tuple:
        """Create dual signatures for a policy document"""
        try:
            if not self.owner_key or not self.pa_key:
                log.error("Signing keys not loaded")
                return (None, None)

            policy_json = json.dumps(policy_doc, sort_keys=True)

            owner_sig = hmac.new(
                self.owner_key,
                policy_json.encode(),
                hashlib.sha256
            ).hexdigest()

            pa_sig = hmac.new(
                self.pa_key,
                policy_json.encode(),
                hashlib.sha256
            ).hexdigest()

            log.info("Dual signatures created", extra={"policy": policy_doc.get('name')})
            return (owner_sig, pa_sig)

        except Exception as e:
            log.error("Failed to create signatures", extra={"error": str(e)})
            return (None, None)
