import hashlib
import json
import secrets
import base64
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, utils

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

    canonical = canonical_json(_frame_payload_for_signature(frame))
    public_key = _load_ec_public_key(device_public_key)
    signature = _decode_signature(frame.signature)
    try:
        public_key.verify(signature, canonical.encode("utf-8"), ec.ECDSA(hashes.SHA256()))
        return
    except InvalidSignature:
        # WebCrypto ECDSA returns IEEE-P1363 r||s bytes, while cryptography verifies DER.
        if len(signature) == 64:
            der_signature = utils.encode_dss_signature(
                int.from_bytes(signature[:32], "big"),
                int.from_bytes(signature[32:], "big"),
            )
            try:
                public_key.verify(der_signature, canonical.encode("utf-8"), ec.ECDSA(hashes.SHA256()))
                return
            except InvalidSignature:
                pass
    raise HTTPException(status_code=403, detail="Management frame signature is invalid.")


def _load_ec_public_key(device_public_key: str):
    try:
        payload = json.loads(device_public_key)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=403, detail="Management device public key must be a JWK.") from exc
    if payload.get("kty") != "EC" or payload.get("crv") != "P-256" or not payload.get("x") or not payload.get("y"):
        raise HTTPException(status_code=403, detail="Management device public key must be ECDSA P-256 JWK.")
    try:
        x = int.from_bytes(_b64url_decode(str(payload["x"])), "big")
        y = int.from_bytes(_b64url_decode(str(payload["y"])), "big")
        numbers = ec.EllipticCurvePublicNumbers(x=x, y=y, curve=ec.SECP256R1())
        return numbers.public_key()
    except Exception as exc:
        raise HTTPException(status_code=403, detail="Management device public key is invalid.") from exc


def _decode_signature(signature: str) -> bytes:
    value = signature.strip()
    if value.startswith("base64url:"):
        value = value.removeprefix("base64url:")
    try:
        return _b64url_decode(value)
    except Exception as exc:
        raise HTTPException(status_code=403, detail="Management frame signature is not valid base64url.") from exc


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))
