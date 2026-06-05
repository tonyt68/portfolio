import boto3
import json
import logging
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path

log = logging.getLogger(__name__)


class CertManager:
    """Manages certificate metadata in DynamoDB Template Registry + CRL checks"""

    def __init__(self, table_name: str, region: str, certs_dir: str = "./certs"):
        self.table_name = table_name
        self.dynamodb = boto3.resource('dynamodb', region_name=region)
        self.table = self.dynamodb.Table(table_name)
        self.certs_dir = Path(certs_dir)
        self.certs_dir.mkdir(parents=True, exist_ok=True)
        self.crl_file = self.certs_dir / "revocation_list.json"
        self.crl = self._load_crl()

    def register_template(self, agent_id: str, scopes: list, can_spawn: list, ttl_seconds: int) -> bool:
        """
        Register agent template in Template Registry.
        State: ACTIVE (ready to use)
        """
        try:
            item = {
                'template_id': agent_id,
                'state': 'ACTIVE',
                'allowed_scopes': scopes,
                'can_spawn': can_spawn,
                'ttl': ttl_seconds,
                'created_at': datetime.utcnow().isoformat(),
                'owner': 'tonyai-org'
            }

            self.table.put_item(Item=item)
            log.info("Template registered", extra={"template": agent_id, "scopes": scopes})
            return True

        except Exception as e:
            log.error("Template registration failed",
                     extra={"template": agent_id, "error": str(e)})
            return False

    def get_template(self, agent_id: str) -> Optional[dict]:
        """Get template from Registry"""
        try:
            response = self.table.get_item(Key={'template_id': agent_id})
            if 'Item' in response:
                log.info("Template retrieved", extra={"template": agent_id})
                return response['Item']
            else:
                log.warning("Template not found", extra={"template": agent_id})
                return None

        except Exception as e:
            log.error("Template retrieval failed",
                     extra={"template": agent_id, "error": str(e)})
            return None

    def update_state(self, agent_id: str, new_state: str) -> bool:
        """
        Update template state: ACTIVE → DISABLED → DELETED
        Fail-closed: state change fails = no update
        """
        valid_states = ['ACTIVE', 'DISABLED', 'DELETED']

        if new_state not in valid_states:
            log.warning("Invalid state", extra={"state": new_state})
            return False

        try:
            self.table.update_item(
                Key={'template_id': agent_id},
                UpdateExpression='SET #state = :state',
                ExpressionAttributeNames={'#state': 'state'},
                ExpressionAttributeValues={':state': new_state}
            )

            log.info("Template state updated",
                    extra={"template": agent_id, "new_state": new_state})
            return True

        except Exception as e:
            log.error("State update failed",
                     extra={"template": agent_id, "error": str(e)})
            return False

    def list_templates(self) -> list:
        """List all templates in Registry"""
        try:
            response = self.table.scan()
            templates = response.get('Items', [])
            log.info("Templates listed", extra={"count": len(templates)})
            return templates

        except Exception as e:
            log.error("Template listing failed", extra={"error": str(e)})
            return []

    # ===== Certificate Revocation List (CRL) =====

    def _load_crl(self) -> dict:
        """Load Certificate Revocation List from disk"""
        if self.crl_file.exists():
            try:
                with open(self.crl_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                log.error("Failed to load CRL", extra={"error": str(e)})
        return {"revoked": [], "disabled": []}

    def _save_crl(self):
        """Persist CRL to disk"""
        try:
            with open(self.crl_file, 'w') as f:
                json.dump(self.crl, f, indent=2)
            log.info("CRL saved",
                    extra={"revoked_count": len(self.crl.get("revoked", [])),
                          "disabled_count": len(self.crl.get("disabled", []))})
        except Exception as e:
            log.error("Failed to save CRL", extra={"error": str(e)})

    def disable_agent(self, agent_id: str) -> bool:
        """Disable agent (suspend): no new auth allowed"""
        try:
            if agent_id not in self.crl.get("disabled", []):
                self.crl["disabled"].append(agent_id)
                self._save_crl()
                log.info("Agent disabled", extra={"agent": agent_id})
            return True
        except Exception as e:
            log.error("Failed to disable agent", extra={"agent": agent_id, "error": str(e)})
            return False

    def revoke_agent(self, agent_id: str) -> bool:
        """Revoke agent (instant deny): no requests allowed"""
        try:
            if agent_id in self.crl.get("disabled", []):
                self.crl["disabled"].remove(agent_id)
            if agent_id not in self.crl.get("revoked", []):
                self.crl["revoked"].append(agent_id)
                self._save_crl()
                log.warning("Agent revoked", extra={"agent": agent_id})
            return True
        except Exception as e:
            log.error("Failed to revoke agent", extra={"agent": agent_id, "error": str(e)})
            return False

    def check_crl(self, agent_id: str) -> bool:
        """Check if agent is revoked or disabled. Returns True if allowed, False if denied"""
        if agent_id in self.crl.get("revoked", []):
            log.warning("CRL check failed: agent revoked", extra={"agent": agent_id})
            return False
        if agent_id in self.crl.get("disabled", []):
            log.warning("CRL check failed: agent disabled", extra={"agent": agent_id})
            return False
        return True
