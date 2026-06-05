import logging
from typing import Optional

log = logging.getLogger(__name__)


class PolicyAuthority:
    """Validates dual-signature (Owner + Policy Authority) on policy changes"""

    def validate_dual_sig(self, policy_doc: dict, owner_sig: str, pa_sig: str) -> bool:
        """
        Validate that policy change has both Owner and Policy Authority signatures.
        Fail-closed: missing any signature = DENY
        """
        try:
            if not owner_sig:
                log.warning("Owner signature missing")
                return False

            if not pa_sig:
                log.warning("Policy Authority signature missing")
                return False

            # TODO: Implement actual signature verification
            # For PoC, just check that both are present and non-empty

            log.info("Dual-sig validation passed",
                    extra={"policy": policy_doc.get('name')})
            return True

        except Exception as e:
            log.error("Dual-sig validation error", extra={"error": str(e)})
            return False
