import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

from app.management.protocol import canonical_json, sha256_text
from app.management.schemas import ManagementFrame


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


@dataclass
class ManagementTestDevice:
    device_id: str
    public_jwk: str
    fingerprint_hash: str
    private_key: ec.EllipticCurvePrivateKey


def create_management_test_device(prefix: str = "device") -> ManagementTestDevice:
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_numbers = private_key.public_key().public_numbers()
    public_jwk_payload = {
        "kty": "EC",
        "crv": "P-256",
        "x": _b64url(public_numbers.x.to_bytes(32, "big")),
        "y": _b64url(public_numbers.y.to_bytes(32, "big")),
        "ext": True,
        "key_ops": ["verify"],
    }
    public_jwk = canonical_json(public_jwk_payload)
    return ManagementTestDevice(
        device_id=f"{prefix}-{uuid4().hex[:12]}",
        public_jwk=public_jwk,
        fingerprint_hash=sha256_text(public_jwk),
        private_key=private_key,
    )


def build_signed_management_frame(
    *,
    frame_type: str,
    user_id: str,
    device: ManagementTestDevice,
    nonce: str | None = None,
    payload_hash: str | None = None,
) -> dict:
    frame = {
        "frame_type": frame_type,
        "protocol_version": "1.0",
        "user_id": user_id,
        "device_id": device.device_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "nonce": nonce or f"nonce-{uuid4().hex[:16]}",
        "payload_hash": payload_hash or ("f" * 64),
    }
    model_frame = ManagementFrame(**frame)
    signature_payload = canonical_json(model_frame.model_dump(mode="json", exclude={"signature"}))
    signature = device.private_key.sign(signature_payload.encode("utf-8"), ec.ECDSA(hashes.SHA256()))
    return {**frame, "signature": _b64url(signature)}


def enroll_management_device(
    client,
    *,
    device: ManagementTestDevice,
    role_scope: str,
    device_name: str = "测试管理设备",
) -> dict:
    response = client.post(
        "/api/v1/management/device/enroll",
        json={
            "device_id": device.device_id,
            "role_scope": role_scope,
            "device_name": device_name,
            "mac_hint": "aa:bb",
            "device_public_key": device.public_jwk,
            "fingerprint_hash": device.fingerprint_hash,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["device"]


def start_management_relay(client, *, user_id: str, role: str, device: ManagementTestDevice) -> dict:
    frame_type = "SA_HELLO" if role == "super_admin" else "AD_HELLO"
    endpoint = "/api/v1/management/super-admin/hello" if role == "super_admin" else "/api/v1/management/admin/hello"
    response = client.post(
        endpoint,
        json=build_signed_management_frame(frame_type=frame_type, user_id=user_id, device=device),
    )
    assert response.status_code == 200, response.text
    return response.json()


def build_action_ack_headers(
    client,
    *,
    device: ManagementTestDevice,
    action_type: str,
    target_type: str,
    target_id: str,
    payload: dict | None = None,
) -> dict[str, str]:
    payload_hash = sha256_text(canonical_json(payload or {}))
    response = client.post(
        "/api/v1/management/action/request",
        json={
            "device_id": device.device_id,
            "action_type": action_type,
            "target_type": target_type,
            "target_id": target_id,
            "payload_hash": payload_hash,
        },
    )
    assert response.status_code == 200, response.text
    action = response.json()["action"]
    return {
        "X-Management-Action-Request-Id": action["action_request_id"],
        "X-Management-Payload-Hash": payload_hash,
    }
