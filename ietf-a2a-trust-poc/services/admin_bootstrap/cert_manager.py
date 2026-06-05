import boto3
import json
import logging
from datetime import datetime
from typing import Optional

log = logging.getLogger(__name__)


class CertManager:
    """Manages certificate metadata in DynamoDB Template Registry"""

    def __init__(self, table_name: str, region: str):
        self.table_name = table_name
        self.dynamodb = boto3.resource('dynamodb', region_name=region)
        self.table = self.dynamodb.Table(table_name)

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
