#!/usr/bin/env bash
# Sentinel FIPS demo menu — mirrors the Sentinel POC menu.
set -euo pipefail

STACK="${STACK:-sentinel-fips}"
REGION="${AWS_REGION:-us-east-1}"

assume_operator_role() {
  local role_arn="arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/sentinel-fips-operator"
  echo "Assuming sentinel-fips-operator role..."
  eval $(aws sts assume-role --role-arn "$role_arn" --role-session-name demo \
    --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' --output text \
    | awk '{print "export AWS_ACCESS_KEY_ID="$1"\nexport AWS_SECRET_ACCESS_KEY="$2"\nexport AWS_SESSION_TOKEN="$3}')
  echo "✓ Now running as sentinel-fips-operator"
}

# Auto-assume operator role if running as sentinel-demo user
if aws sts get-caller-identity --query 'Arn' --output text 2>/dev/null | grep -q 'user/sentinel-demo'; then
  assume_operator_role
fi

resolve_outputs() {
  local outputs
  outputs="$(aws cloudformation describe-stacks --stack-name "$STACK" --region "$REGION" \
    --query 'Stacks[0].Outputs' --output json 2>/dev/null || echo '[]')"
  export SENTINEL_ENDPOINT="$(jq -r '.[]? | select(.OutputKey=="ApiEndpoint")       | .OutputValue' <<<"$outputs")"
  export TABLE="$(jq             -r '.[]? | select(.OutputKey=="RebacTableName")     | .OutputValue' <<<"$outputs")"
  export ALERT_TOPIC="$(jq       -r '.[]? | select(.OutputKey=="AlertTopicArn")      | .OutputValue' <<<"$outputs")"
  export OPERATOR_ROLE_ARN="$(jq -r '.[]? | select(.OutputKey=="OperatorRoleArn")   | .OutputValue' <<<"$outputs")"
}

setup_demo_user() {
  local user="sentinel-demo"
  local account_id
  account_id="$(aws sts get-caller-identity --query Account --output text)"

  if [[ -z "${OPERATOR_ROLE_ARN:-}" ]]; then
    echo "Stack not deployed yet — deploy first (option 1) to create the operator role."
    return
  fi

  # Create user if missing
  if aws iam get-user --user-name "$user" &>/dev/null; then
    echo "IAM user '$user' already exists — skipping creation."
  else
    aws iam create-user --user-name "$user"
    echo "✓ IAM user '$user' created."
  fi

  # Attach (or overwrite) inline policy scoped to role assumption only
  aws iam put-user-policy \
    --user-name "$user" \
    --policy-name sentinel-fips-assume-operator \
    --policy-document "{
      \"Version\": \"2012-10-17\",
      \"Statement\": [{
        \"Effect\": \"Allow\",
        \"Action\": \"sts:AssumeRole\",
        \"Resource\": \"${OPERATOR_ROLE_ARN}\"
      }]
    }"
  echo "✓ Inline policy attached — user can only assume sentinel-fips-operator."

  # Attach full CloudShell access so sentinel-demo can open a terminal and upload files
  aws iam put-user-policy \
    --user-name "$user" \
    --policy-name sentinel-fips-cloudshell \
    --policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"cloudshell:*","Resource":"*"}]}'
  echo "✓ CloudShell policy attached — user can open a CloudShell terminal and upload files."

  # Set / reset console password
  local tmp_pwd
  tmp_pwd="Sentinel-$(openssl rand -hex 4)!"
  if aws iam get-login-profile --user-name "$user" &>/dev/null; then
    aws iam update-login-profile --user-name "$user" --password "$tmp_pwd" --no-password-reset-required
    echo "✓ Console password reset."
  else
    aws iam create-login-profile --user-name "$user" --password "$tmp_pwd" --no-password-reset-required
    echo "✓ Console login profile created."
  fi

  echo ""
  echo "================================================="
  echo "  Demo user ready"
  echo "  User:     $user"
  echo "  Temp pwd: $tmp_pwd   (save to password manager)"
  echo "  Login:    https://${account_id}.signin.aws.amazon.com/console"
  echo "  Then:     Switch role → sentinel-fips-operator"
  echo "================================================="
}

resolve_outputs

while true; do
  # Check chain integrity
  GREEN='\033[0;32m'
  RED='\033[0;31m'
  BLINK='\033[5m'
  RESET='\033[0m'

  if [[ -n "${TABLE:-}" ]]; then
    TONY_LINK=$(aws dynamodb get-item --region "$REGION" --table-name "$TABLE" \
      --key '{"subject_relation":{"S":"tony#member_of"}}' \
      --query 'Item.subject_relation.S' --output text 2>/dev/null || echo "")
    if [[ "$TONY_LINK" == "tony#member_of" ]]; then
      CHAIN_STATUS="${GREEN}🟢 INTACT${RESET}"
      CHAIN_COLOR="$GREEN"
    else
      CHAIN_STATUS="${BLINK}${RED}🔴 BROKEN${RESET}"
      CHAIN_COLOR="$RED"
    fi
  else
    CHAIN_STATUS="⚪ unknown (not deployed)"
    CHAIN_COLOR=""
  fi

  echo ""
  echo "================================================="
  echo "   Sentinel FIPS — ReBAC + FIPS 140-3 Boundary"
  echo "================================================="
  echo "   Stack:    $STACK ($REGION)"
  echo "   Endpoint: ${SENTINEL_ENDPOINT:-<not deployed>}"
  echo "   Table:    ${TABLE:-<not deployed>}"
  echo ""
  echo "   FLOW — ALLOWED:  2 → 3"
  echo "   FLOW — DENIED:   2 → 3 → 4 → 3"
  echo "   FLOW — RECOVERY: 2 → 3 → 4 → 3 → 5 → 3"
  echo ""
  echo -e "   ReBAC chain: $CHAIN_STATUS"
  echo -e "   ${CHAIN_COLOR}sentinel-agent → delegate_of → tony${RESET}"
  echo -e "   ${CHAIN_COLOR}tony           → member_of   → platform-team${RESET}"
  echo -e "   ${CHAIN_COLOR}platform-team  → can_sign    → idp-config-bundle${RESET}"
  echo ""
  echo "-------------------------------------------------"
  cat <<EOF
   1) Deploy stack (sam build && sam deploy --guided)
   2) Seed ReBAC graph
   3) Run Sentinel signing request
   4) Revoke Tony's membership   (chain → BROKEN)
   5) Restore Tony's membership  (chain → INTACT)
   6) Verify ReBAC graph
   7) Tail recent audit events (CloudTrail)
   8) Tear down stack
   9) Setup demo user (sentinel-demo / least-privilege)
   q) Quit
EOF
  read -rp "Choose: " choice
  case "$choice" in
    1)
      sam build
      sam deploy --guided
      resolve_outputs
      ;;
    2)
      echo "Seeding ReBAC graph in $TABLE ($REGION)..."
      aws dynamodb put-item --region "$REGION" --table-name "$TABLE" --item '{"subject_relation":{"S":"sentinel-agent#delegate_of"},"objects":{"SS":["tony"]}}'
      aws dynamodb put-item --region "$REGION" --table-name "$TABLE" --item '{"subject_relation":{"S":"tony#member_of"},"objects":{"SS":["platform-team"]}}'
      aws dynamodb put-item --region "$REGION" --table-name "$TABLE" --item '{"subject_relation":{"S":"platform-team#can_sign"},"objects":{"SS":["idp-config-bundle"]}}'
      echo "Seeded:"
      echo "    sentinel-agent  --delegate_of-->  tony"
      echo "    tony            --member_of-->    platform-team"
      echo "    platform-team   --can_sign-->     idp-config-bundle"
      ;;
    3)
      if [[ -z "${SENTINEL_ENDPOINT:-}" ]]; then
        echo "Stack not deployed yet. Run option 1." ; continue
      fi
      python3 client.py
      ;;
    4)
      aws dynamodb delete-item --region "$REGION" --table-name "$TABLE" \
        --key '{"subject_relation":{"S":"tony#member_of"}}'
      echo "✓ tony#member_of removed — chain BROKEN"
      ;;
    5)
      aws dynamodb put-item --region "$REGION" --table-name "$TABLE" --item '{
        "subject_relation": {"S": "tony#member_of"},
        "objects":          {"SS": ["platform-team"]}
      }'
      echo "✓ tony#member_of restored — chain INTACT"
      ;;
    6)
      echo "ReBAC tuples in $TABLE:"
      aws dynamodb scan --region "$REGION" --table-name "$TABLE" \
        --query 'Items[].{key:subject_relation.S, objects:objects.SS}' --output table
      ;;
    7)
      echo "Last 5 management events touching kms / verifiedpermissions / lambda:"
      aws cloudtrail lookup-events --region "$REGION" \
        --max-results 5 \
        --query 'Events[].{Time:EventTime, User:Username, Event:EventName, Source:EventSource}' \
        --output table
      ;;
    8)
      sam delete --stack-name "$STACK" --region "$REGION"
      echo "Note: AuditBucket and AnthropicSecret are retained — delete manually if desired."
      ;;
    9)
      setup_demo_user
      ;;
    q|Q)
      exit 0
      ;;
    *)
      echo "Unknown choice."
      ;;
  esac
done
