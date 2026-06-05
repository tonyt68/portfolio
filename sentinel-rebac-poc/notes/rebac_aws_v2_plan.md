# Sentinel v2 — AWS ReBAC Architecture Plan
> Status: DRAFT — refine and implement after v1 (local Redis/Minikube) is stable

---

## Strategy

Separate **Relationships** (who is connected to what) from **Logic** (the rules).

| Layer | AWS Service | Role |
|-------|-------------|------|
| Relationship Store | Amazon Neptune (Graph DB) | Stores entity hierarchies and relationship edges |
| Policy Engine | Amazon Verified Permissions | Evaluates Cedar policies — permit or forbid |
| Integration | AWS Lambda Authorizer | Bridges Neptune graph data into AVP requests |
| IaC | CloudFormation (AWS-native) | Provisions all resources |

---

## 1. Cedar Schema (Validation Layer)

Defines the universe — valid entities, relationships, and actions.

```json
{
  "ReBAC": {
    "entityTypes": {
      "User": {
        "memberOfTypes": ["Team"]
      },
      "Service": {
        "shape": {
          "type": "Record",
          "attributes": {}
        }
      },
      "Team": {
        "memberOfTypes": ["Team"]
      },
      "Document": {
        "shape": {
          "type": "Record",
          "attributes": {
            "authorizedTeams": { "type": "Set", "element": { "type": "Entity", "name": "Team" } },
            "managedBy": { "type": "Entity", "name": "Service" }
          }
        }
      }
    },
    "actions": {
      "view":    { "appliesTo": { "principalTypes": ["User"],    "resourceTypes": ["Document"] } },
      "process": { "appliesTo": { "principalTypes": ["Service"], "resourceTypes": ["Document"] } }
    }
  }
}
```

---

## 2. Cedar Policies (Authorization Logic)

### Human User Policy (Inherited Access via Team Membership)
```cedar
permit (
    principal is User,
    action == Action::"view",
    resource is Document
)
when {
    // Permission flows through teams resolved from the Neptune graph
    principal in resource.authorizedTeams
};
```

### Service Policy (Direct Ownership)
```cedar
permit (
    principal is Service,
    action == Action::"process",
    resource is Document
)
when {
    // Service must be the assigned manager of the document
    resource.managedBy == principal
};
```

---

## 3. Infrastructure as Code

### CloudFormation (IaC of choice)
```yaml
Resources:
  ReBACPolicyStore:
    Type: AWS::VerifiedPermissions::PolicyStore
    Properties:
      ValidationSettings:
        Mode: STRICT

  UserPolicy:
    Type: AWS::VerifiedPermissions::Policy
    Properties:
      PolicyStoreId: !Ref ReBACPolicyStore
      Definition:
        Static:
          Statement: >
            permit(principal is User, action == Action::"view", resource is Document)
            when { principal in resource.authorizedTeams };
```

---

## 4. Integration Layer — Lambda Authorizer

Bridges Neptune graph relationships into Verified Permissions authorization requests.

```python
import boto3
import os

avp = boto3.client('verifiedpermissions')

def lambda_handler(event, context):
    uid = event['principalId']  # e.g., "User::Tony"
    did = event['resourceId']   # e.g., "Document::Doc1"

    # 1. Query Neptune for all teams the user belongs to (including parent teams)
    # Gremlin: g.V(uid).repeat(out('memberOf', 'partOf')).emit().id().toList()
    user_teams = ["Team::PlatformTeam", "Team::SecurityTeam"]  # resolved from Neptune

    # 2. Authorize via Cedar / Verified Permissions
    response = avp.is_authorized(
        policyStoreId=os.environ['POLICY_STORE_ID'],
        principal={'entityType': 'User', 'entityId': uid},
        action={'actionType': 'Action', 'actionId': 'view'},
        resource={'entityType': 'Document', 'entityId': did},
        entities={
            'entityList': [{
                'identifier': {'entityType': 'Document', 'entityId': did},
                'attributes': {
                    'authorizedTeams': {
                        'set': [{'entityId': t, 'entityType': 'Team'} for t in user_teams]
                    }
                }
            }]
        }
    )

    return {"isAuthorized": response['decision'] == 'ALLOW'}
```

---

## 5. Neptune Graph Schema

### Nodes
| Node Type | Description |
|-----------|-------------|
| User | Human or service principal |
| Team | Group or department |
| Document / Service | The resource being protected |

### Edges
| Edge | Direction | Meaning |
|------|-----------|---------|
| memberOf | User → Team | User belongs to team |
| partOf | Team → Team | Team hierarchy (sub → parent) |
| owns | Team → Document | Team has ownership rights |
| managedBy | Document → Service | Service is assigned manager |

---

## v1 → v2 Migration Map

| v1 (Local) | v2 (AWS) |
|------------|----------|
| Redis (SADD/SMEMBERS) | Amazon Neptune (Gremlin graph) |
| Python `_check_rebac()` traversal | Lambda Authorizer + Gremlin queries |
| MCP `check_rebac_permission` tool | Lambda → AVP `is_authorized` API call |
| Minikube | ECS/Fargate or EKS |
| Manual seed script | Terraform IaC |

---

## TODO (v2 Implementation)
- [ ] Get AWS Educate / Academy account
- [ ] Provision Neptune cluster (CloudFormation)
- [ ] Provision Verified Permissions policy store (CloudFormation)
- [ ] Port Cedar schema and policies
- [ ] Build Lambda authorizer with Neptune Gremlin queries
- [ ] Wire Sentinel MCP tool to call Lambda instead of Redis
- [ ] Neptune seeder Lambda called from CloudFormation Custom Resource
- [ ] Demo: same ALLOWED/DENIED flow, now on real AWS
