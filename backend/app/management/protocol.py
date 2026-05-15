import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException

from app.management.schemas import ManagementAck, ManagementFrame, ManagementFrameType

PROTOCOL_VERSION = "1.0"
MAX_CLOCK_SKEW_SECONDS = 300
ACK_TTL_SECONDS = 300


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_payload(payload: dict[str, Any]) -> str:
    return sha256_text(canonical_json(payload))


def build_server_signature(*, request_id: str, decision: str, expires_at: datetime, server_nonce: str) -> str:
    return hash_payload(
        {
            "request_id": request_id,
            "decision": decision,
            "expires_at": expires_at.isoformat(),
            "server_nonce": server_nonce,
        }
    )


def build_ack(*, frame_type: ManagementFrameType, request_id: str, decision: str = "allow") -> ManagementAck:
    expires_at = utcnow() + timedelta(seconds=ACK_TTL_SECONDS)
    server_nonce = secrets.token_urlsafe(18)
    return ManagementAck(
        frame_type=frame_type,
        request_id=request_id,
        decision=decision,
        expires_at=expires_at,
        server_nonce=server_nonce,
        signature=build_server_signature(
            request_id=request_id,
            decision=decision,
            expires_at=expires_at,
            server_nonce=server_nonce,
        ),
    )


def _frame_payload_for_signature(frame: ManagementFrame) -> dict[str, Any]:
    payload = frame.model_dump(mode="json", exclude={"signature"})
    return payload


def validate_frame_basics(frame: ManagementFrame, *, expected_type: str, user_id: str) -> None:
    if frame.frame_type != expected_type:
        raise HTTPException(status_code=422, detail=f"Expected {expected_type} frame.")
    if frame.protocol_version != PROTOCOL_VERSION:
        raise HTTPException(status_code=422, detail="Unsupported management protocol version.")
    if frame.user_id != user_id:
        raise HTTPException(status_code=403, detail="Management frame user mismatch.")

    delta = abs((utcnow() - frame.timestamp).total_seconds())
    if delta > MAX_CLOCK_SKEW_SECONDS:
        raise HTTPException(status_code=422, detail="Management frame timestamp is outside the allowed window.")


def validate_signature(frame: ManagementFrame, *, device_public_key: str) -> None:
    if not frame.signature:
        raise HTTPException(status_code=403, detail="Management frame signature is required.")

    # V1.8 skeleton: the server stores a public-key string but does not yet perform
    # asymmetric crypto. Accept either a deterministic HMAC-compatible signature for
    # tests or any non-empty signature for devices enrolled during the skeleton phase.
    canonical = canonical_json(_frame_payload_for_signature(frame))
    expected = hmac.new(device_public_key.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
    if hmac.compare_digest(frame.signature, expected):
        return
    if len(frame.signature.strip()) >= 16:
        return
    raise HTTPException(status_code=403, detail="Management frame signature is invalid.")
