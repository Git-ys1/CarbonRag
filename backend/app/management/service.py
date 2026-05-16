import secrets
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from uuid import uuid4

from fastapi import HTTPException

from app.auth.schemas import AuthenticatedUser
from app.management.protocol import build_ack, sha256_text, validate_frame_basics, validate_signature
from app.management.schemas import (
    ActionAckEnvelope,
    ActionRequestCreate,
    AdminAccessDecisionRequest,
    AdminAccessRequest,
    AdminAccessRequestCreate,
    AdminAccessRequestEnvelope,
    AdminDevice,
    AdminDeviceEnvelope,
    DeviceEnrollRequest,
    EdgeRelaySession,
    ManagementAck,
    ManagementAuditLog,
    ManagementFrame,
    ManagementListEnvelope,
    ManagementUserSummary,
    RelayHeartbeatRequest,
    RelayStatusResponse,
)
from app.management.storage import ManagementStore

MAX_ADMINS_PER_DEVICE = 5
ACK_TTL_SECONDS = 300
RELAY_TTL_SECONDS = 900


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat()


class ManagementService:
    def __init__(self, store: ManagementStore | None = None) -> None:
        self.store = store or ManagementStore()

    def _audit(
        self,
        *,
        actor_user_id: str,
        actor_role: str,
        action_type: str,
        decision: str,
        device_id: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        detail_json: dict | None = None,
    ) -> None:
        self.store.insert_audit_log(
            {
                "audit_id": f"audit-{uuid4().hex[:16]}",
                "actor_user_id": actor_user_id,
                "actor_role": actor_role,
                "device_id": device_id,
                "action_type": action_type,
                "target_type": target_type,
                "target_id": target_id,
                "decision": decision,
                "detail_json": detail_json or {},
                "created_at": _iso(_utcnow()),
            }
        )

    def _ensure_nonce(self, frame: ManagementFrame) -> None:
        now = _utcnow()
        self.store.cleanup_expired_nonces(_iso(now))
        self.store.insert_nonce(
            {
                "nonce_id": f"nonce-{uuid4().hex[:16]}",
                "user_id": frame.user_id,
                "device_id": frame.device_id,
                "nonce": frame.nonce,
                "frame_type": frame.frame_type,
                "payload_hash": frame.payload_hash,
                "seen_at": _iso(now),
                "expires_at": _iso(now + timedelta(seconds=900)),
            }
        )

    def record_audit(
        self,
        *,
        actor_user_id: str,
        actor_role: str,
        action_type: str,
        decision: str,
        device_id: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        detail_json: dict | None = None,
    ) -> None:
        self._audit(
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            device_id=device_id,
            action_type=action_type,
            target_type=target_type,
            target_id=target_id,
            decision=decision,
            detail_json=detail_json,
        )

    def enforce_single_super_admin(self) -> None:
        super_admins = self.store.list_active_super_admins()
        if len(super_admins) > 1:
            raise RuntimeError("Multiple active super_admin users exist. Run auth seed repair before enabling management.")

    def has_admin_console_access(self, user: AuthenticatedUser) -> bool:
        if user.role == "super_admin":
            return True
        if user.role != "admin":
            return False
        devices = self.store.list_devices()
        return any(
            device.get("owner_user_id") == user.user_id
            and device.get("role_scope") == "admin"
            and bool(device.get("is_active"))
            and device.get("approved_at")
            for device in devices
        )

    def has_valid_action_ack(self, *, user_id: str, role: str) -> bool:
        return self.store.has_active_relay(user_id=user_id, role=role)

    def has_active_relay(self, *, user_id: str, role: str) -> bool:
        return self.store.has_active_relay(user_id=user_id, role=role)

    def consume_action_ack(
        self,
        *,
        user_id: str,
        role: str,
        action_request_id: str,
        action_type: str,
        target_type: str | None,
        target_id: str | None,
        payload_hash: str,
    ) -> bool:
        action = self.store.consume_action_ack(
            action_request_id=action_request_id,
            user_id=user_id,
            role=role,
            action_type=action_type,
            target_type=target_type,
            target_id=target_id,
            payload_hash=payload_hash,
        )
        if action:
            self._audit(
                actor_user_id=user_id,
                actor_role=role,
                device_id=str(action.get("device_id") or ""),
                action_type=f"{action_type}:CONSUME_ACK",
                target_type=target_type,
                target_id=target_id,
                decision="allow",
                detail_json={"action_request_id": action_request_id, "payload_hash": payload_hash},
            )
        return action is not None

    def enroll_device(self, user: AuthenticatedUser, payload: DeviceEnrollRequest) -> AdminDeviceEnvelope:
        if user.role == "user":
            raise HTTPException(status_code=403, detail="Management devices are only available for admin roles.")
        if payload.role_scope == "super_admin" and user.role != "super_admin":
            raise HTTPException(status_code=403, detail="Only super_admin can enroll a super_admin device.")
        if payload.role_scope == "admin" and user.role not in {"admin", "super_admin"}:
            raise HTTPException(status_code=403, detail="Only admin roles can enroll an admin device.")

        existing = self.store.get_device(payload.device_id)
        if existing and existing.get("owner_user_id") != user.user_id:
            raise HTTPException(status_code=409, detail="Device id is already registered by another user.")
        if payload.role_scope == "super_admin":
            active_super_devices = self.store.count_active_super_admin_devices()
            if active_super_devices > 0 and not (existing and bool(existing.get("is_active"))):
                raise HTTPException(status_code=409, detail="Only one active super_admin device is allowed.")
        if payload.role_scope == "admin" and self.store.count_active_admin_devices_for_fingerprint(payload.fingerprint_hash) >= MAX_ADMINS_PER_DEVICE:
            raise HTTPException(status_code=409, detail="This device already has the maximum number of admin bindings.")

        now = _utcnow()
        auto_approved = user.role == "super_admin" and payload.role_scope == "super_admin"
        device = self.store.upsert_device(
            {
                "device_id": payload.device_id,
                "role_scope": payload.role_scope,
                "owner_user_id": user.user_id,
                "device_name": payload.device_name,
                "mac_hint": payload.mac_hint,
                "device_public_key": payload.device_public_key,
                "fingerprint_hash": payload.fingerprint_hash,
                "is_active": 1,
                "approved_by": user.user_id if auto_approved else None,
                "approved_at": _iso(now) if auto_approved else None,
                "created_at": existing.get("created_at") if existing else _iso(now),
                "last_seen_at": _iso(now),
                "revoked_at": None,
            }
        )
        self._audit(
            actor_user_id=user.user_id,
            actor_role=user.role,
            device_id=payload.device_id,
            action_type="DEVICE_ENROLL",
            target_type="admin_device",
            target_id=payload.device_id,
            decision="allow" if auto_approved else "pending",
        )
        return AdminDeviceEnvelope(device=AdminDevice.model_validate(device))

    def _require_active_device(self, *, user: AuthenticatedUser, frame: ManagementFrame, role_scope: str) -> dict:
        device = self.store.get_device(frame.device_id)
        if not device:
            raise HTTPException(status_code=403, detail="Management device is not enrolled.")
        if device.get("owner_user_id") != user.user_id:
            raise HTTPException(status_code=403, detail="Management device is owned by another user.")
        if device.get("role_scope") != role_scope:
            raise HTTPException(status_code=403, detail="Management device scope mismatch.")
        if not bool(device.get("is_active")) or not device.get("approved_at"):
            raise HTTPException(status_code=403, detail="Management device is not approved.")
        validate_signature(frame, device_public_key=str(device["device_public_key"]))
        return device

    def super_admin_hello(self, user: AuthenticatedUser, frame: ManagementFrame) -> ManagementAck:
        if user.role != "super_admin":
            raise HTTPException(status_code=403, detail="super_admin access required.")
        validate_frame_basics(frame, expected_type="SA_HELLO", user_id=user.user_id)
        self._ensure_nonce(frame)
        self._require_active_device(user=user, frame=frame, role_scope="super_admin")
        ack = build_ack(frame_type="SA_ACK", request_id=f"sa-{uuid4().hex[:16]}")
        now = _utcnow()
        self.store.insert_relay_session(
            {
                "relay_session_id": ack.request_id,
                "user_id": user.user_id,
                "role": "super_admin",
                "device_id": frame.device_id,
                "status": "connected",
                "connected_at": _iso(now),
                "last_heartbeat_at": _iso(now),
                "expires_at": _iso(now + timedelta(seconds=RELAY_TTL_SECONDS)),
                "server_ack_status": "allow",
            }
        )
        self.store.expire_connected_relay_sessions(user_id=user.user_id, role="super_admin", except_session_id=ack.request_id)
        self._audit(
            actor_user_id=user.user_id,
            actor_role=user.role,
            device_id=frame.device_id,
            action_type="SA_HELLO",
            decision="allow",
        )
        return ack

    def admin_hello(self, user: AuthenticatedUser, frame: ManagementFrame) -> ManagementAck:
        if user.role != "admin":
            raise HTTPException(status_code=403, detail="admin access required.")
        validate_frame_basics(frame, expected_type="AD_HELLO", user_id=user.user_id)
        self._ensure_nonce(frame)
        self._require_active_device(user=user, frame=frame, role_scope="admin")
        ack = build_ack(frame_type="AD_ACK", request_id=f"ad-{uuid4().hex[:16]}")
        now = _utcnow()
        self.store.insert_relay_session(
            {
                "relay_session_id": ack.request_id,
                "user_id": user.user_id,
                "role": "admin",
                "device_id": frame.device_id,
                "status": "connected",
                "connected_at": _iso(now),
                "last_heartbeat_at": _iso(now),
                "expires_at": _iso(now + timedelta(seconds=RELAY_TTL_SECONDS)),
                "server_ack_status": "allow",
            }
        )
        self.store.expire_connected_relay_sessions(user_id=user.user_id, role="admin", except_session_id=ack.request_id)
        self._audit(
            actor_user_id=user.user_id,
            actor_role=user.role,
            device_id=frame.device_id,
            action_type="AD_HELLO",
            decision="allow",
        )
        return ack

    def request_action_ack(self, user: AuthenticatedUser, payload: ActionRequestCreate) -> ActionAckEnvelope:
        if user.role not in {"admin", "super_admin"}:
            raise HTTPException(status_code=403, detail="Management action requires admin role.")
        role_scope = "super_admin" if user.role == "super_admin" else "admin"
        device = self.store.get_device(payload.device_id)
        if not device or device.get("owner_user_id") != user.user_id or device.get("role_scope") != role_scope:
            raise HTTPException(status_code=403, detail="Approved management device required.")
        if not bool(device.get("is_active")) or not device.get("approved_at"):
            raise HTTPException(status_code=403, detail="Management device is not approved.")
        if not self.store.has_active_relay(user_id=user.user_id, role=user.role):
            raise HTTPException(status_code=403, detail="Active management relay required before requesting ACTION_ACK.")
        now = _utcnow()
        ack_token = secrets.token_urlsafe(24)
        action = self.store.insert_action_request(
            {
                "action_request_id": f"act-{uuid4().hex[:16]}",
                "user_id": user.user_id,
                "role": user.role,
                "device_id": payload.device_id,
                "action_type": payload.action_type,
                "target_type": payload.target_type,
                "target_id": payload.target_id,
                "payload_hash": payload.payload_hash,
                "status": "approved",
                "ack_token_hash": sha256_text(ack_token),
                "expires_at": _iso(now + timedelta(seconds=ACK_TTL_SECONDS)),
                "created_at": _iso(now),
                "decided_at": _iso(now),
                "consumed_at": None,
                "relay_session_id": (self.store.get_current_relay_session(user_id=user.user_id, role=user.role) or {}).get("relay_session_id"),
            }
        )
        ack = build_ack(frame_type="ACTION_ACK", request_id=action["action_request_id"])
        self._audit(
            actor_user_id=user.user_id,
            actor_role=user.role,
            device_id=payload.device_id,
            action_type=payload.action_type,
            target_type=payload.target_type,
            target_id=payload.target_id,
            decision="allow",
            detail_json={"payload_hash": payload.payload_hash, "action_request_id": action["action_request_id"]},
        )
        return ActionAckEnvelope(action=action, ack=ack)

    def create_access_request(self, user: AuthenticatedUser, payload: AdminAccessRequestCreate) -> AdminAccessRequestEnvelope:
        if user.role != "admin":
            raise HTTPException(status_code=403, detail="Only admin can request management access restoration.")
        now = _utcnow()
        request = self.store.insert_access_request(
            {
                "request_id": f"req-{uuid4().hex[:16]}",
                "admin_user_id": user.user_id,
                "device_id": payload.device_id,
                "device_name": payload.device_name,
                "mac_hint": payload.mac_hint,
                "device_public_key": payload.device_public_key,
                "fingerprint_hash": payload.fingerprint_hash,
                "status": "pending",
                "requested_at": _iso(now),
            }
        )
        self._audit(
            actor_user_id=user.user_id,
            actor_role=user.role,
            device_id=payload.device_id,
            action_type="ADMIN_ACCESS_REQUEST",
            target_type="admin_access_request",
            target_id=request["request_id"],
            decision="pending",
        )
        return AdminAccessRequestEnvelope(request=AdminAccessRequest.model_validate(request))

    def approve_access_request(
        self,
        current_user: AuthenticatedUser,
        request_id: str,
        payload: AdminAccessDecisionRequest,
    ) -> AdminAccessRequestEnvelope:
        if current_user.role != "super_admin":
            raise HTTPException(status_code=403, detail="super_admin access required.")
        request = self.store.get_access_request(request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Access request not found.")
        if request.get("status") != "pending":
            raise HTTPException(status_code=409, detail="Access request is not pending.")
        if self.store.count_active_admin_devices_for_fingerprint(str(request["fingerprint_hash"])) >= MAX_ADMINS_PER_DEVICE:
            raise HTTPException(status_code=409, detail="This device already has the maximum number of admin bindings.")
        now = _utcnow()
        self.store.upsert_device(
            {
                "device_id": request["device_id"],
                "role_scope": "admin",
                "owner_user_id": request["admin_user_id"],
                "device_name": request.get("device_name") or "Admin device",
                "mac_hint": request.get("mac_hint"),
                "device_public_key": request["device_public_key"],
                "fingerprint_hash": request["fingerprint_hash"],
                "is_active": 1,
                "approved_by": current_user.user_id,
                "approved_at": _iso(now),
                "created_at": _iso(now),
                "last_seen_at": _iso(now),
                "revoked_at": None,
            }
        )
        updated = self.store.update_access_request(
            request_id,
            status="approved",
            decided_by=current_user.user_id,
            decided_at=_iso(now),
            decision_note=payload.decision_note,
        )
        self._audit(
            actor_user_id=current_user.user_id,
            actor_role=current_user.role,
            device_id=request["device_id"],
            action_type="ADMIN_ACCESS_APPROVE",
            target_type="admin_access_request",
            target_id=request_id,
            decision="allow",
        )
        return AdminAccessRequestEnvelope(request=AdminAccessRequest.model_validate(updated))

    def reject_access_request(
        self,
        current_user: AuthenticatedUser,
        request_id: str,
        payload: AdminAccessDecisionRequest,
    ) -> AdminAccessRequestEnvelope:
        if current_user.role != "super_admin":
            raise HTTPException(status_code=403, detail="super_admin access required.")
        request = self.store.get_access_request(request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Access request not found.")
        now = _utcnow()
        updated = self.store.update_access_request(
            request_id,
            status="rejected",
            decided_by=current_user.user_id,
            decided_at=_iso(now),
            decision_note=payload.decision_note,
        )
        self._audit(
            actor_user_id=current_user.user_id,
            actor_role=current_user.role,
            device_id=request.get("device_id"),
            action_type="ADMIN_ACCESS_REJECT",
            target_type="admin_access_request",
            target_id=request_id,
            decision="deny",
        )
        return AdminAccessRequestEnvelope(request=AdminAccessRequest.model_validate(updated))

    def relay_status(self, user: AuthenticatedUser) -> RelayStatusResponse:
        current = self.store.get_current_relay_session(user_id=user.user_id)
        super_current = self.store.get_current_relay_session(role="super_admin")
        return RelayStatusResponse(
            current=EdgeRelaySession.model_validate(current) if current else None,
            super_admin_online=super_current is not None,
            server_time=_utcnow(),
        )

    def heartbeat(self, user: AuthenticatedUser, payload: RelayHeartbeatRequest) -> RelayStatusResponse:
        session = self.store.get_relay_session(payload.relay_session_id)
        if not session or session.get("user_id") != user.user_id:
            raise HTTPException(status_code=404, detail="Relay session not found.")
        self.store.update_relay_heartbeat(payload.relay_session_id, _iso(_utcnow()))
        return self.relay_status(user)

    def list_management(self, user: AuthenticatedUser) -> ManagementListEnvelope:
        if user.role not in {"admin", "super_admin"}:
            raise HTTPException(status_code=403, detail="Management access required.")
        if user.role != "super_admin":
            return ManagementListEnvelope(
                users=[],
                devices=[
                    AdminDevice.model_validate(device)
                    for device in self.store.list_devices()
                    if device.get("owner_user_id") == user.user_id
                ],
                access_requests=[
                    AdminAccessRequest.model_validate(request)
                    for request in self.store.list_access_requests()
                    if request.get("admin_user_id") == user.user_id
                ],
                audit_logs=[],
            )
        return ManagementListEnvelope(
            users=[ManagementUserSummary.model_validate(item) for item in self.store.list_management_users()],
            devices=[AdminDevice.model_validate(item) for item in self.store.list_devices()],
            access_requests=[AdminAccessRequest.model_validate(item) for item in self.store.list_access_requests()],
            audit_logs=[ManagementAuditLog.model_validate(item) for item in self.store.list_audit_logs()],
        )

    def list_audit_logs(self, user: AuthenticatedUser) -> list[ManagementAuditLog]:
        if user.role != "super_admin":
            raise HTTPException(status_code=403, detail="super_admin access required.")
        return [ManagementAuditLog.model_validate(item) for item in self.store.list_audit_logs()]


@lru_cache(maxsize=1)
def get_management_service() -> ManagementService:
    return ManagementService()
