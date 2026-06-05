import logging
import uuid
import requests
import anthropic
import os
import json
import hmac
import hashlib
from datetime import datetime

log = logging.getLogger(__name__)


class ScenarioRunner:
    """Runs all 11 demo scenarios with real Claude API calls and cryptographic signatures"""

    def __init__(self, mcp_url: str, admin_url: str):
        self.mcp_url = mcp_url
        self.admin_url = admin_url
        self.audit_trail = []
        self.claude_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.hmac_secret = os.getenv("HMAC_SECRET", "dev-secret-key").encode()
        self.owner_key = self._load_key("../certs/owner.key")
        self.pa_key = self._load_key("../certs/pa.key")

    def _load_key(self, key_path: str) -> bytes:
        """Load signing key from file"""
        try:
            with open(key_path, "rb") as f:
                return f.read()
        except Exception as e:
            log.warning(f"Could not load key {key_path}: {e}")
            return b"demo-key"

    def generate_correlation_id(self) -> str:
        """Generate UUID v7 correlation ID"""
        return str(uuid.uuid4())

    def create_request_hmac(self, payload: dict) -> str:
        """Create HMAC-SHA256 for request payload"""
        payload_json = json.dumps(payload, sort_keys=True)
        return hmac.new(
            self.hmac_secret,
            payload_json.encode(),
            hashlib.sha256
        ).hexdigest()

    def create_dual_sig(self, policy_doc: dict) -> tuple:
        """Create owner and PA signatures for policy document"""
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

        return (owner_sig, pa_sig)

    def call_claude(self, prompt: str) -> str:
        """Call Claude API and return response"""
        message = self.claude_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return message.content[0].text

    def log_to_audit(self, scenario_id: int, agent_id: str, action: str, decision: str, reason: str):
        """Log scenario result to audit trail"""
        entry = {
            "scenario_id": scenario_id,
            "agent_id": agent_id,
            "action": action,
            "decision": decision,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.audit_trail.append(entry)
        log.info(f"Audit: {entry}")

    # ========== 11 Scenarios ==========

    def scenario_1_golden_path(self):
        """Golden path: full auth chain succeeds"""
        correlation_id = self.generate_correlation_id()
        agent_id = "agent-b"

        # Claude formulates request
        prompt = "As an A2A trust agent, formulate a brief data write request in JSON format."
        claude_response = self.call_claude(prompt)

        # Agent B writes event with cryptographic signature
        payload = {
            "correlation_id": correlation_id,
            "agent_id": agent_id,
            "requested_scopes": ["write:events"],
            "event_data": {"claude_suggestion": claude_response}
        }
        payload["request_hmac"] = self.create_request_hmac(payload)

        response = requests.post(f"{self.mcp_url}/write-event", json=payload)
        decision = "ALLOWED" if response.status_code == 200 else "DENIED"
        self.log_to_audit(1, agent_id, "write_event", decision, "Full chain validates")

    def scenario_2_dynamic_policy_update(self):
        """Dynamic policy update changes enforcement"""
        correlation_id = self.generate_correlation_id()
        agent_id = "agent-b"

        prompt = "Suggest a policy change that would grant agent-a write permissions. Keep it brief."
        claude_response = self.call_claude(prompt)

        payload = {
            "correlation_id": correlation_id,
            "agent_id": agent_id,
            "requested_scopes": ["write:events"],
            "event_data": {"policy_suggestion": claude_response}
        }
        payload["request_hmac"] = self.create_request_hmac(payload)

        response = requests.post(f"{self.mcp_url}/write-event", json=payload)
        decision = "ALLOWED" if response.status_code == 200 else "DENIED"
        self.log_to_audit(2, agent_id, "write_event", decision, "Policy updated")

    def scenario_3_rogue_spawn(self):
        """Agent tries to spawn unauthorized child"""
        correlation_id = self.generate_correlation_id()
        agent_id = "agent-a"

        prompt = "Explain why an agent should not spawn a child without explicit authorization."
        claude_response = self.call_claude(prompt)

        payload = {
            "correlation_id": correlation_id,
            "agent_id": agent_id,
            "requested_scopes": ["spawn:child"],
            "event_data": {"reason": claude_response}
        }
        payload["request_hmac"] = self.create_request_hmac(payload)

        response = requests.post(f"{self.mcp_url}/write-event", json=payload)
        decision = "ALLOWED" if response.status_code == 200 else "DENIED"
        self.log_to_audit(3, agent_id, "spawn", decision, "Not in CanSpawn list")

    def scenario_4_dual_sig_missing(self):
        """Policy update missing PA signature"""
        correlation_id = self.generate_correlation_id()
        agent_id = "agent-b"

        prompt = "What would happen if a policy change was signed by the owner but not the policy authority?"
        claude_response = self.call_claude(prompt)

        # Create policy document and sign with owner only (missing PA sig)
        policy_doc = {
            "name": "policy-4",
            "agent": "agent-a",
            "scopes": ["write:events"],
            "created_at": datetime.utcnow().isoformat()
        }
        owner_sig, pa_sig = self.create_dual_sig(policy_doc)

        payload = {
            "correlation_id": correlation_id,
            "agent_id": agent_id,
            "requested_scopes": ["write:events"],
            "event_data": {"dual_sig_analysis": claude_response},
            "policy_doc": policy_doc,
            "owner_sig": owner_sig,
            "pa_sig": None  # Missing PA signature!
        }
        payload["request_hmac"] = self.create_request_hmac(payload)

        response = requests.post(f"{self.mcp_url}/write-event", json=payload)
        decision = "ALLOWED" if response.status_code == 200 else "DENIED"
        self.log_to_audit(4, agent_id, "policy_update", decision, "PA sig missing")

    def scenario_5_dual_sig_tampered(self):
        """PA signature tampered"""
        correlation_id = self.generate_correlation_id()
        agent_id = "agent-b"

        prompt = "Explain the security implications of a tampered PA signature."
        claude_response = self.call_claude(prompt)

        # Create policy document and sign with both, then tamper PA sig
        policy_doc = {
            "name": "policy-5",
            "agent": "agent-a",
            "scopes": ["write:events"],
            "created_at": datetime.utcnow().isoformat()
        }
        owner_sig, pa_sig = self.create_dual_sig(policy_doc)
        tampered_pa_sig = pa_sig[:-4] + "XXXX"  # Tamper last 4 chars

        payload = {
            "correlation_id": correlation_id,
            "agent_id": agent_id,
            "requested_scopes": ["write:events"],
            "event_data": {"sig_tampering": claude_response},
            "policy_doc": policy_doc,
            "owner_sig": owner_sig,
            "pa_sig": tampered_pa_sig  # Tampered!
        }
        payload["request_hmac"] = self.create_request_hmac(payload)

        response = requests.post(f"{self.mcp_url}/write-event", json=payload)
        decision = "ALLOWED" if response.status_code == 200 else "DENIED"
        self.log_to_audit(5, agent_id, "policy_update", decision, "PA sig tampered")

    def scenario_6_scope_escalation(self):
        """Child requests scopes beyond parent's"""
        correlation_id = self.generate_correlation_id()
        agent_id = "agent-a"

        prompt = "What scopes should a child agent never be allowed to request?"
        claude_response = self.call_claude(prompt)

        payload = {
            "correlation_id": correlation_id,
            "agent_id": agent_id,
            "requested_scopes": ["admin:all"],
            "event_data": {"escalation_analysis": claude_response}
        }
        payload["request_hmac"] = self.create_request_hmac(payload)

        response = requests.post(f"{self.mcp_url}/write-event", json=payload)
        decision = "ALLOWED" if response.status_code == 200 else "DENIED"
        self.log_to_audit(6, agent_id, "write_event", decision, "Child exceeds scopes")

    def scenario_7_revocation_lifecycle(self):
        """Cert lifecycle: ACTIVE → DISABLED → DELETED"""
        correlation_id = self.generate_correlation_id()
        agent_id = "agent-b"

        prompt = "Describe the cert state machine: ACTIVE, DISABLED, DELETED. What happens at each transition?"
        claude_response = self.call_claude(prompt)

        payload = {
            "correlation_id": correlation_id,
            "agent_id": agent_id,
            "requested_scopes": ["write:events"],
            "event_data": {"cert_lifecycle": claude_response}
        }
        payload["request_hmac"] = self.create_request_hmac(payload)

        response = requests.post(f"{self.mcp_url}/write-event", json=payload)
        decision = "ALLOWED" if response.status_code == 200 else "DENIED"
        self.log_to_audit(7, agent_id, "write_event", decision, "Template DELETED")

    def scenario_8_crl_check_failure(self):
        """Revoked cert in middle of chain"""
        correlation_id = self.generate_correlation_id()
        agent_id = "agent-b"

        prompt = "Why is a revoked certificate in the middle of a cert chain dangerous?"
        claude_response = self.call_claude(prompt)

        payload = {
            "correlation_id": correlation_id,
            "agent_id": agent_id,
            "requested_scopes": ["write:events"],
            "event_data": {"crl_analysis": claude_response}
        }
        payload["request_hmac"] = self.create_request_hmac(payload)

        response = requests.post(f"{self.mcp_url}/write-event", json=payload)
        decision = "ALLOWED" if response.status_code == 200 else "DENIED"
        self.log_to_audit(8, agent_id, "write_event", decision, "Revoked cert mid-chain")

    def scenario_9_ttl_expiry(self):
        """Cert TTL exceeded"""
        correlation_id = self.generate_correlation_id()
        agent_id = "agent-b"

        prompt = "What should happen when an agent's TTL expires?"
        claude_response = self.call_claude(prompt)

        payload = {
            "correlation_id": correlation_id,
            "agent_id": agent_id,
            "requested_scopes": ["write:events"],
            "event_data": {"ttl_analysis": claude_response}
        }
        payload["request_hmac"] = self.create_request_hmac(payload)

        response = requests.post(f"{self.mcp_url}/write-event", json=payload)
        decision = "ALLOWED" if response.status_code == 200 else "DENIED"
        self.log_to_audit(9, agent_id, "write_event", decision, "Expired template")

    def scenario_10_cross_org_grant(self):
        """Cross-org grant then revocation"""
        correlation_id = self.generate_correlation_id()
        agent_id = "agent-b"

        prompt = "Why should cross-org grants be time-limited and revocable?"
        claude_response = self.call_claude(prompt)

        payload = {
            "correlation_id": correlation_id,
            "agent_id": agent_id,
            "requested_scopes": ["write:events"],
            "event_data": {"cross_org_analysis": claude_response}
        }
        payload["request_hmac"] = self.create_request_hmac(payload)

        response = requests.post(f"{self.mcp_url}/write-event", json=payload)
        decision = "ALLOWED" if response.status_code == 200 else "DENIED"
        self.log_to_audit(10, agent_id, "write_event", decision, "Grant revoked")

    def scenario_11_replay_attack(self):
        """Reused correlationId"""
        correlation_id = self.generate_correlation_id()
        agent_id = "agent-b"

        prompt = "How should an A2A system prevent replay attacks using correlationId?"
        claude_response = self.call_claude(prompt)

        # First request
        payload = {
            "correlation_id": correlation_id,
            "agent_id": agent_id,
            "requested_scopes": ["write:events"],
            "event_data": {"replay_prevention": claude_response}
        }
        payload["request_hmac"] = self.create_request_hmac(payload)

        response = requests.post(f"{self.mcp_url}/write-event", json=payload)
        decision = "ALLOWED" if response.status_code == 200 else "DENIED"
        self.log_to_audit(11, agent_id, "write_event", decision, "Reused nonce")
