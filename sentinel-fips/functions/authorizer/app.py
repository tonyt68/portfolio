"""ReBAC chain checker — BFS over DynamoDB tuples, then Cedar via Verified Permissions.

Returns:
  {
    "decision": "ALLOW" | "DENY",
    "chain":    [{subject, relation, object}, ...],
    "reason":   present when chain is broken,
  }
"""
import os

import boto3

_dynamodb = boto3.resource("dynamodb")
_table = _dynamodb.Table(os.environ["REBAC_TABLE"])
_avp = boto3.client("verifiedpermissions")
_POLICY_STORE_ID = os.environ["POLICY_STORE_ID"]

RELATIONS = ("delegate_of", "member_of", "can_sign")

TYPE_MAP = {
    "sentinel-agent": "SentinelFips::Service",
    "tony": "SentinelFips::User",
    "platform-team": "SentinelFips::Team",
    "idp-config-bundle": "SentinelFips::Bundle",
}


def lambda_handler(event, _context):
    principal = event["principal"]
    action = event.get("action", "Sign")
    resource = event["resource"]

    chain = _resolve_chain(principal, resource)

    if not chain["intact"]:
        return {
            "decision": "DENY",
            "reason": "chain_broken",
            "missing_link_for": chain["dead_end"],
            "chain": chain["edges"],
        }

    entities = _build_entities(chain["edges"])
    avp_resp = _avp.is_authorized(
        policyStoreId=_POLICY_STORE_ID,
        principal={
            "entityType": TYPE_MAP.get(principal, "SentinelFips::Service"),
            "entityId": principal,
        },
        action={
            "actionType": "SentinelFips::Action",
            "actionId": action,
        },
        resource={
            "entityType": TYPE_MAP.get(resource, "SentinelFips::Bundle"),
            "entityId": resource,
        },
        entities={"entityList": entities},
    )

    return {
        "decision": avp_resp["decision"],
        "chain": chain["edges"],
        "determining_policies": [
            p.get("policyId") for p in avp_resp.get("determiningPolicies", [])
        ],
    }


def _resolve_chain(principal: str, resource: str) -> dict:
    """BFS from principal through ReBAC edges until we hit resource.

    Fetches all relation keys for each node in one BatchGetItem instead of
    N serial GetItem calls — cuts round trips from N*len(RELATIONS) to N.
    """
    visited: set[str] = set()
    queue: list[str] = [principal]
    edges: list[dict] = []
    found = False

    while queue:
        node = queue.pop(0)
        if node in visited:
            continue
        visited.add(node)

        response = _dynamodb.batch_get_item(
            RequestItems={
                _table.name: {
                    "Keys": [
                        {"subject_relation": f"{node}#{rel}"} for rel in RELATIONS
                    ]
                }
            }
        )
        items = response.get("Responses", {}).get(_table.name, [])

        for item in items:
            relation = item["subject_relation"].split("#", 1)[1]
            for obj in item.get("objects", []):
                edges.append({"subject": node, "relation": relation, "object": obj})
                if obj == resource:
                    found = True
                else:
                    queue.append(obj)

        if found:
            return {"intact": True, "edges": edges, "dead_end": None}

    return {"intact": False, "edges": edges, "dead_end": principal}


def _build_entities(edges: list[dict]) -> list[dict]:
    """Translate `delegate_of` / `member_of` edges into AVP parent relationships
    so Cedar's `principal in Team::"..."` check resolves transitively."""
    parents: dict[str, list[str]] = {}
    for e in edges:
        if e["relation"] in ("delegate_of", "member_of"):
            parents.setdefault(e["subject"], []).append(e["object"])

    entities = []
    for subject, parent_ids in parents.items():
        entities.append({
            "identifier": {
                "entityType": TYPE_MAP.get(subject, "SentinelFips::User"),
                "entityId": subject,
            },
            "parents": [
                {
                    "entityType": TYPE_MAP.get(p, "SentinelFips::Team"),
                    "entityId": p,
                }
                for p in parent_ids
            ],
        })
    return entities
