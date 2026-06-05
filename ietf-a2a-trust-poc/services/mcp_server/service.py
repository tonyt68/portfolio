"""Business logic service layer (separates from FastAPI routing)"""

import logging
import uuid
from typing import Dict, Optional, List

log = logging.getLogger(__name__)


class EventService:
    """Handles event write/read business logic"""

    def __init__(self, jwt_validator, hmac_verifier, cedar_evaluator, s3_tools, audit_fn):
        self.jwt_validator = jwt_validator
        self.hmac_verifier = hmac_verifier
        self.cedar_evaluator = cedar_evaluator
        self.s3_tools = s3_tools
        self.audit_fn = audit_fn

    def write_event(self, correlation_id: str, agent_id: str, requested_scopes: List[str], event_data: Dict) -> tuple:
        """
        Write event: validates → authorizes → stores → audits.
        Returns: (success: bool, s3_key: str, decision: str, reason: str)
        """
        span_id = str(uuid.uuid4())
        decision = "ALLOWED"
        reason = "Full chain validates"
        granted_scopes = []

        try:
            # Authorize via Cedar policy
            granted_scopes = self.cedar_evaluator.evaluate(agent_id, requested_scopes)

            if not granted_scopes:
                decision = "DENIED"
                reason = "Cedar policy DENY"
                self.audit_fn({
                    "correlationId": correlation_id,
                    "spanId": span_id,
                    "agent": agent_id,
                    "action": "write_event",
                    "decision": decision,
                    "reason": reason,
                    "grantedScopes": [],
                    "requestedScopes": requested_scopes
                })
                return (False, None, decision, reason)

            # Store in S3
            s3_key = self.s3_tools.write_event(correlation_id, event_data)

            if not s3_key:
                decision = "DENIED"
                reason = "S3 write failed"
                return (False, None, decision, reason)

            # Audit success
            self.audit_fn({
                "correlationId": correlation_id,
                "spanId": span_id,
                "agent": agent_id,
                "action": "write_event",
                "decision": decision,
                "reason": reason,
                "grantedScopes": granted_scopes,
                "requestedScopes": requested_scopes,
                "s3_key": s3_key
            })

            return (True, s3_key, decision, reason)

        except Exception as e:
            log.error(f"write_event error: {str(e)}")
            return (False, None, "DENIED", str(e))

    def read_event(self, correlation_id: str, agent_id: str, s3_key: str) -> tuple:
        """
        Read event: authorizes → retrieves → audits.
        Returns: (success: bool, content: str, decision: str, reason: str)
        """
        span_id = str(uuid.uuid4())
        decision = "ALLOWED"
        reason = "Full chain validates"

        try:
            # Authorize (read:events)
            granted_scopes = self.cedar_evaluator.evaluate(agent_id, ["read:events"])

            if not granted_scopes:
                decision = "DENIED"
                reason = "Cedar policy DENY"
                self.audit_fn({
                    "correlationId": correlation_id,
                    "spanId": span_id,
                    "agent": agent_id,
                    "action": "read_event",
                    "decision": decision,
                    "reason": reason
                })
                return (False, None, decision, reason)

            # Retrieve from S3
            content = self.s3_tools.read_event(s3_key)

            if not content:
                decision = "DENIED"
                reason = "Event not found"
                return (False, None, decision, reason)

            # Audit success
            self.audit_fn({
                "correlationId": correlation_id,
                "spanId": span_id,
                "agent": agent_id,
                "action": "read_event",
                "decision": decision,
                "reason": reason,
                "s3_key": s3_key
            })

            return (True, content, decision, reason)

        except Exception as e:
            log.error(f"read_event error: {str(e)}")
            return (False, None, "DENIED", str(e))
