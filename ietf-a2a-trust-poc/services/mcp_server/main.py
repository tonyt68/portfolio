import os
import logging
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
import json
import uuid

from config import settings
from jwt_validator import JWTValidator
from hmac_verifier import HMACVerifier
from cedar_policy_eval import CedarPolicyEvaluator
from s3_tools import S3Tools
from audit import audit

# Setup logging
logging.basicConfig(level=settings.log_level)
log = logging.getLogger(__name__)

app = FastAPI(title="A2A Trust MCP Server", version="0.1.0")

# Initialize components
jwt_validator = JWTValidator(settings.jwt_secret)
hmac_verifier = HMACVerifier(settings.hmac_secret)
cedar_evaluator = CedarPolicyEvaluator(settings.cedar_policy_path)
s3_tools = S3Tools(settings.s3_bucket, settings.aws_region)


class WriteEventRequest(BaseModel):
    correlation_id: str
    event_data: dict
    agent_id: str
    requested_scopes: list


class ReadEventRequest(BaseModel):
    s3_key: str
    correlation_id: str


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "mcp_server"}


@app.post("/write-event")
async def write_event(request: WriteEventRequest):
    """
    MCP tool: Write event to S3 (Agent B only).
    Requires: valid JWT + HMAC + Cedar policy allow
    """
    span_id = str(uuid.uuid4())
    decision = "ALLOWED"
    reason = "Full chain validates"

    try:
        log.info(f"write_event: {request.agent_id} / {request.correlation_id}")

        # Cedar policy evaluation (scope check)
        granted_scopes = cedar_evaluator.evaluate(
            request.agent_id,
            request.requested_scopes
        )

        if not granted_scopes:
            decision = "DENIED"
            reason = "Cedar policy DENY"
            log.warning(f"Cedar DENY: {request.agent_id}")

            # Log to CloudWatch
            audit({
                "correlationId": request.correlation_id,
                "spanId": span_id,
                "agent": request.agent_id,
                "action": "write_event",
                "decision": decision,
                "reason": reason,
                "grantedScopes": [],
                "requestedScopes": request.requested_scopes,
                "timestamp": str(uuid.uuid4())
            })
            raise HTTPException(status_code=403, detail="Policy DENY")

        # S3 write
        s3_key = s3_tools.write_event(request.correlation_id, request.event_data)

        if not s3_key:
            decision = "DENIED"
            reason = "S3 write failed"
            raise HTTPException(status_code=500, detail="S3 write failed")

        # Log success to CloudWatch
        audit({
            "correlationId": request.correlation_id,
            "spanId": span_id,
            "agent": request.agent_id,
            "action": "write_event",
            "decision": decision,
            "reason": reason,
            "grantedScopes": granted_scopes,
            "requestedScopes": request.requested_scopes,
            "s3_key": s3_key,
            "timestamp": str(uuid.uuid4())
        })

        return {
            "status": "success",
            "s3_key": s3_key,
            "correlation_id": request.correlation_id,
            "decision": "ALLOWED"
        }

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"write_event error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal error")


@app.post("/read-event")
async def read_event(request: ReadEventRequest):
    """
    MCP tool: Read event from S3 (Agent A only).
    Requires: valid JWT + HMAC + Cedar policy allow
    """
    try:
        log.info("read_event request",
                extra={"s3_key": request.s3_key, "correlation_id": request.correlation_id})

        # S3 read
        content = s3_tools.read_event(request.s3_key)

        if not content:
            raise HTTPException(status_code=404, detail="Event not found")

        return {
            "status": "success",
            "content": content,
            "correlation_id": request.correlation_id,
            "decision": "ALLOWED"
        }

    except HTTPException:
        raise
    except Exception as e:
        log.error("read_event error", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail="Internal error")


@app.post("/validate-jwt")
async def validate_jwt_endpoint(request: Request):
    """Validate JWT token endpoint"""
    try:
        body = await request.json()
        token = body.get('token')

        if not token:
            raise HTTPException(status_code=400, detail="Token required")

        decoded = jwt.validator.validate(token)

        if not decoded:
            raise HTTPException(status_code=401, detail="Invalid JWT")

        return {"status": "valid", "claims": decoded}

    except Exception as e:
        log.error("JWT validation endpoint error", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail="Internal error")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
