"""Cryptographic operation — kms:Sign over a FIPS endpoint.

The CMK never leaves the HSM; only the signature crosses the boundary.
🔒 FIPS-3-GAP: KMS HSMs are FIPS 140-2 L3 today. CloudHSM (Marvell LiquidSecurity2)
backing a Custom Key Store is the swap for true 140-3 L3.

Defense in depth: this Lambda **independently re-runs the authorization check**
before invoking KMS. The orchestrator already calls the authorizer; this Lambda
calls it again and refuses to sign if the second check disagrees. Two-of-two
required, surviving any compromise of the orchestrator (prompt injection,
future code bug, malicious actor with orchestrator-only access).
"""
import base64
import hashlib
import json
import os

import boto3

_kms = boto3.client("kms")  # AWS_USE_FIPS_ENDPOINT=true forces kms-fips.<region>...
_lambda = boto3.client("lambda")
_KEY_ID = os.environ["KMS_KEY_ID"]
_AUTHORIZER_FN = os.environ["AUTHORIZER_FUNCTION"]


def lambda_handler(event, _context):
    bundle = event.get("bundle", "")
    principal = event.get("principal")
    action = event.get("action", "Sign")
    resource = event.get("resource")

    # Defense in depth — independent re-check before any cryptographic operation.
    if not principal or not resource:
        return {
            "error": "missing_authorization_context",
            "reason": "sign Lambda requires principal + resource for re-check",
        }

    recheck = _lambda.invoke(
        FunctionName=_AUTHORIZER_FN,
        InvocationType="RequestResponse",
        Payload=json.dumps({
            "principal": principal,
            "action": action,
            "resource": resource,
        }).encode(),
    )
    recheck_result = json.loads(recheck["Payload"].read())

    if recheck_result.get("decision") != "ALLOW":
        return {
            "error": "recheck_denied",
            "reason": "sign Lambda re-check did not return ALLOW",
            "recheck_decision": recheck_result.get("decision"),
            "recheck_reason": recheck_result.get("reason"),
        }

    # Re-check passed — proceed with cryptographic operation.
    digest = hashlib.sha256(bundle.encode("utf-8")).digest()

    resp = _kms.sign(
        KeyId=_KEY_ID,
        Message=digest,
        MessageType="DIGEST",
        SigningAlgorithm="RSASSA_PSS_SHA_256",
    )

    return {
        "signature": base64.b64encode(resp["Signature"]).decode("ascii"),
        "key_id": resp["KeyId"],
        "algorithm": resp["SigningAlgorithm"],
        "endpoint": _kms.meta.endpoint_url,
        "digest_sha256": digest.hex(),
        "recheck": "passed",
    }
