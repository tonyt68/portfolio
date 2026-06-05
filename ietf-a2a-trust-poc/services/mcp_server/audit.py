"""Audit logging — CloudWatch Logs + fallback to console"""

import json
import logging
import time
import os
import boto3

log = logging.getLogger("audit")

AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
LOG_GROUP = os.getenv('CLOUDWATCH_LOG_GROUP', '/a2a-trust-poc/audit')
LOG_STREAM = os.getenv('SERVICE_NAME', 'mcp-server')

_cw_client = boto3.client('logs', region_name=AWS_REGION)
_stream_ready = False


def _ensure_stream():
    """Create log group/stream if needed"""
    global _stream_ready
    if _stream_ready:
        return

    try:
        _cw_client.create_log_group(logGroupName=LOG_GROUP)
    except _cw_client.exceptions.ResourceAlreadyExistsException:
        pass
    except Exception as e:
        log.warning(f'CloudWatch log group setup failed: {e}')

    try:
        _cw_client.create_log_stream(logGroupName=LOG_GROUP, logStreamName=LOG_STREAM)
    except _cw_client.exceptions.ResourceAlreadyExistsException:
        pass
    except Exception as e:
        log.warning(f'CloudWatch log stream setup failed: {e}')

    _stream_ready = True


def audit(entry: dict) -> None:
    """Write audit entry to CloudWatch"""
    _ensure_stream()

    try:
        message = json.dumps(entry, default=str)
        _cw_client.put_log_events(
            logGroupName=LOG_GROUP,
            logStreamName=LOG_STREAM,
            logEvents=[{
                'timestamp': int(time.time() * 1000),
                'message': message
            }]
        )
        log.info(f'Audit logged: {entry.get("decision")}')
    except Exception as e:
        log.error(f'CloudWatch write failed: {e}')
