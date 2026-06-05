"""Replay attack prevention for IETF A2A Trust (timestamp + nonce validation)"""

import logging
import json
import uuid
from pathlib import Path
from datetime import datetime, timedelta
from typing import Tuple

log = logging.getLogger(__name__)


class ReplayPrevention:
    """Tracks nonces and validates timestamps to prevent replay attacks"""

    def __init__(self, nonce_tracker_path: str = "./certs/nonce_tracker.json"):
        self.tracker_path = Path(nonce_tracker_path)
        self.nonce_ttl_seconds = 300  # 5 minutes
        self.tracker = self._load_tracker()

    def _load_tracker(self) -> dict:
        """Load nonce tracker from disk"""
        if self.tracker_path.exists():
            try:
                with open(self.tracker_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                log.error("Failed to load nonce tracker", extra={"error": str(e)})
        return {"used_nonces": [], "last_cleaned": datetime.utcnow().isoformat()}

    def _save_tracker(self):
        """Persist nonce tracker to disk"""
        try:
            with open(self.tracker_path, 'w') as f:
                json.dump(self.tracker, f, indent=2)
        except Exception as e:
            log.error("Failed to save nonce tracker", extra={"error": str(e)})

    def _cleanup_expired_nonces(self):
        """Remove expired nonces from tracker"""
        try:
            now = datetime.utcnow()
            cutoff = now - timedelta(seconds=self.nonce_ttl_seconds)

            original_count = len(self.tracker["used_nonces"])

            # Keep only recent nonces
            self.tracker["used_nonces"] = [
                nonce_entry for nonce_entry in self.tracker["used_nonces"]
                if datetime.fromisoformat(nonce_entry["timestamp"]) > cutoff
            ]

            removed = original_count - len(self.tracker["used_nonces"])
            if removed > 0:
                log.info("Expired nonces cleaned", extra={"removed": removed})
                self.tracker["last_cleaned"] = datetime.utcnow().isoformat()
                self._save_tracker()

        except Exception as e:
            log.error("Nonce cleanup error", extra={"error": str(e)})

    def generate_nonce(self) -> str:
        """Generate UUID v4 nonce for client to include in request"""
        return str(uuid.uuid4())

    def validate_request(self, request_nonce: str, request_timestamp: str) -> Tuple[bool, str]:
        """
        Validate request freshness and nonce uniqueness.
        Returns: (valid: bool, reason: str)
        """
        try:
            # Parse timestamp
            try:
                req_time = datetime.fromisoformat(request_timestamp)
            except Exception:
                return (False, "Invalid timestamp format")

            # Check timestamp freshness (must be within 5 minutes)
            now = datetime.utcnow()
            time_diff = abs((now - req_time).total_seconds())

            if time_diff > self.nonce_ttl_seconds:
                return (False, f"Timestamp too old: {time_diff}s > {self.nonce_ttl_seconds}s")

            # Cleanup old nonces
            self._cleanup_expired_nonces()

            # Check nonce uniqueness
            for nonce_entry in self.tracker["used_nonces"]:
                if nonce_entry["nonce"] == request_nonce:
                    return (False, "Nonce already used (replay attack detected)")

            # Record nonce as used
            self.tracker["used_nonces"].append({
                "nonce": request_nonce,
                "timestamp": request_timestamp,
                "agent_id": None  # Will be set by caller
            })
            self._save_tracker()

            log.info("Request validated", extra={"nonce": request_nonce[:8]})
            return (True, "Request valid")

        except Exception as e:
            log.error("Replay prevention error", extra={"error": str(e)})
            return (False, str(e))

    def mark_nonce_used(self, nonce: str, agent_id: str, timestamp: str):
        """Mark nonce as used for a specific agent"""
        try:
            for entry in self.tracker["used_nonces"]:
                if entry["nonce"] == nonce:
                    entry["agent_id"] = agent_id
                    self._save_tracker()
                    return
        except Exception as e:
            log.error("Failed to mark nonce used", extra={"error": str(e)})
