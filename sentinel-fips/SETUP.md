# Sentinel FIPS — AWS Setup

Everything runs in **AWS CloudShell** (region `us-east-1`). Local Docker / SAM CLI is not required.

## Files this references

| Step uses | File |
|---|---|
| Deploys all AWS resources | [template.yaml](template.yaml) |
| Three Lambda functions | [functions/orchestrator/](functions/orchestrator/), [functions/authorizer/](functions/authorizer/), [functions/sign/](functions/sign/) |
| Menu wrapper + seeds ReBAC graph | [demo.sh](demo.sh) |
| HTTP client invoked from the menu | [client.py](client.py) |

---

## 1. Open CloudShell

AWS Console → top right → CloudShell icon. Make sure the region selector is `us-east-1`.

## 2. Get the code into CloudShell

Zip the project folder locally, then in CloudShell use *Actions → Upload file* to upload the zip, then:

```bash
unzip sentinel-fips.zip
cd sentinel-fips
```

## 3. Deploy

```bash
sam build
```

> **Note:** If `sam build` fails on Python version mismatch, use `sam build --use-container` — requires Docker and ECR access from CloudShell. Alternatively confirm `template.yaml` runtime matches CloudShell's native Python version (`python3.13` as of 2026).

**First time only — guided deploy:**
```bash
sam deploy --guided --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM
```
Follow the prompt table below. SAM saves your answers to `samconfig.toml` — subsequent deploys skip all prompts.

> **Why `CAPABILITY_NAMED_IAM`:** The `sentinel-fips-operator` IAM role is a named role. CloudFormation requires explicit acknowledgment when creating named IAM roles — `CAPABILITY_IAM` alone is not enough.

**Every time after — fast deploy:**
```bash
sam deploy --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM --parameter-overrides AnthropicApiKey=YOUR_KEY_HERE
```
No prompts. Consistent. Durable.

> **Why `AnthropicApiKey` is not saved:** SAM does not save `NoEcho` parameters to `samconfig.toml` — it's a security feature. You must pass it explicitly every deploy.

> **`AnthropicBaseUrl`** defaults to `https://api.anthropic.com` and is saved by SAM — no need to pass it unless overriding (e.g., proxy or Bedrock swap).

You will be prompted for the following — answer each exactly as shown:

| Prompt | Your Answer | Notes |
|---|---|---|
| `Stack Name` | `sentinel-fips` | Hit Enter if shown as default |
| `AWS Region` | `us-east-1` | Hit Enter if shown as default |
| `AnthropicApiKey` | paste your key | From `console.anthropic.com` — stored NoEcho into Secrets Manager. Double-check before hitting Enter. |
| `AlertEmail` | your email address | **Type carefully** — SNS confirmation goes here. Typo = no alert emails. |
| `DryRun` | `true` | Hit Enter — default is `true`, recommended for first deploy |
| `Confirm changes before deploy` | `N` | Hit Enter |
| `Allow SAM CLI IAM role creation` | `Y` | Required — SAM creates Lambda execution roles |
| `OrchestratorFunction has no authentication` | `y` | POC — API is intentionally open |
| `Disable rollback` | `N` | Hit Enter — keep rollback enabled |
| `Save arguments to configuration file` | `Y` | Saves `samconfig.toml` so next deploy skips these prompts |
| `SAM configuration file` | Hit Enter | Accepts default `samconfig.toml` |
| `SAM configuration environment` | Hit Enter | Accepts default `default` |

> **Tip:** Go slowly on `AlertEmail` — it's the most common fat-finger. If you mistype, fix it after deploy with: `sam deploy --parameter-overrides AlertEmail=your@email.com`

Deploy takes ~3-4 minutes. The CloudFormation stack ends with `CREATE_COMPLETE`.

### Dry-Run vs Live Mode

The `DryRun` parameter controls whether `sign_bundle` and `emit_alert` actually have side effects:

| Mode | `sign_bundle` | `emit_alert` | `check_authorization` | Use when |
|---|---|---|---|---|
| **`DryRun=true`** (recommended for first deploy) | Returns *"would have signed"* stub, no KMS call | Returns *"would have alerted"* stub, no SNS email | Runs normally (read-only) | Building trust; demonstrating to skeptics; verifying behavior before going live |
| **`DryRun=false`** (live mode — for the headline demo video) | Real `kms:Sign`, real signature returned | Real EventBridge → SNS email | Same | Production-like behavior; the demo where you need to show real signatures |

Switch modes post-deploy without redeploying:
```bash
aws lambda update-function-configuration \
  --function-name sentinel-fips-orchestrator \
  --environment 'Variables={DRY_RUN=true,ANTHROPIC_SECRET_ID=...,AUTHORIZER_FUNCTION=...,SIGN_FUNCTION=...}'
```
*(easier path: re-run `sam deploy --parameter-overrides DryRun=false`)*

Full rationale and verification recipes: [AI-GOVERNANCE.md § Dry-Run Mode](AI-GOVERNANCE.md#dry-run-mode).

## 4. Confirm the SNS subscription

Open the email titled *AWS Notification — Subscription Confirmation* and click the link. Without this, [demo.sh](demo.sh) option 4 won't page you.

## 5. Seed the ReBAC graph

```bash
bash demo.sh
# choose 2
```

Writes three tuples to DynamoDB:

```
sentinel-agent  --delegate_of-->  tony
tony            --member_of-->    platform-team
platform-team   --can_sign-->     idp-config-bundle
```

## 6. Smoke test

```bash
bash demo.sh
# choose 3 → expect REBAC_ALLOWED + a base64 signature
```

---

## Teardown

```bash
bash demo.sh   # then choose 8
# or directly:
sam delete --stack-name sentinel-fips --region us-east-1
```

**Retained on purpose** (delete manually from the console once you're sure you're done):

- **S3 audit bucket** `sentinel-fips-audit-<account>` — Object Lock COMPLIANCE prevents deletion until the 1-day retention elapses on every object. Wait 24h after the last write, then *Empty bucket → Delete bucket*.
- **Secrets Manager** `sentinel-fips/anthropic-api-key` — AWS schedules a 7-day deletion window by default. Force-delete via `aws secretsmanager delete-secret --secret-id sentinel-fips/anthropic-api-key --force-delete-without-recovery` if you want it gone immediately.

## Cost while idle

~$1/month — the KMS CMK. DynamoDB on-demand at zero traffic is $0; Lambda + API Gateway free-tier covers the demo. Verified Permissions charges per `IsAuthorized` (fractions of a cent per call).

## Region note

`us-east-1` is required as written — Verified Permissions and the FIPS KMS endpoint must both exist in the deploy region. Don't change the region without re-checking service availability.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `sam build` fails on Python version | Confirm `template.yaml` runtime is `python3.13` to match CloudShell's native Python version |
| Orchestrator returns 502 | First invocation cold-start can exceed default API GW timeout — retry once |
| `verifiedpermissions:IsAuthorized` AccessDenied | Confirm the stack reached `CREATE_COMPLETE`; the policy attaches after the function |
| `PolicyStore CREATE_FAILED — needs a subscription` | Amazon Verified Permissions must be activated first — go to AWS Console → search "Verified Permissions" → open it and click through to activate → then redeploy |
| `Failed to create changeset` after a rollback | Previous stack still exists in failed state — delete it first: `aws cloudformation delete-stack --stack-name sentinel-fips --region us-east-1` → wait 30 seconds → then redeploy |
| No alert email on revoke | SNS subscription not confirmed (step 4) |
| Alert email not firing in live mode | EventBridge publish permission missing from SNS topic policy — run: `aws sns set-topic-attributes --topic-arn <alerts-arn> --attribute-name Policy --attribute-value '{"Version":"2012-10-17","Statement":[{"Sid":"__default_statement_ID","Effect":"Allow","Principal":{"AWS":"*"},"Action":["SNS:GetTopicAttributes","SNS:SetTopicAttributes","SNS:AddPermission","SNS:RemovePermission","SNS:DeleteTopic","SNS:Subscribe","SNS:ListSubscriptionsByTopic","SNS:Publish"],"Resource":"<alerts-arn>","Condition":{"StringEquals":{"AWS:SourceOwner":"<account-id>"}}},{"Sid":"AllowEventBridgePublish","Effect":"Allow","Principal":{"Service":"events.amazonaws.com"},"Action":"sns:Publish","Resource":"<alerts-arn>"}]}'` |
| `UPDATE_ROLLBACK_FAILED` on SNS topics deleted outside CloudFormation | Run `aws cloudformation continue-update-rollback --stack-name sentinel-fips --resources-to-skip PatternAlertTopic AlertTopic` → then manually recreate topics → then redeploy |
| Stack delete stuck on bucket | Object Lock retention not elapsed — wait 24h, empty, retry |
| `sentinel-demo` CloudShell not authorized | Run demo.sh option 9 again — CloudShell policy is now included automatically |
