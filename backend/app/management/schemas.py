from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ManagementRole = Literal["admin", "super_admin"]
AdminDeviceRoleScope = Literal["admin", "super_admin"]
RelayStatus = Literal["pending", "connected", "expired", "revoked"]
AdminAccessRequestStatus = Literal["pending", "approved", "rejected", "expired"]
ManagementActionStatus = Literal["pending", "approved", "rejected", "expired"]
ManagementDecision = Literal["allow", "deny", "pending"]
ManagementFrameType = Literal[
    "SA_HELLO",
    "SA_ACK",
    "AD_HELLO",
    "AD_ACK",
    "ACTION_REQUEST",
    "ACTION_ACK",
    "HEARTBEAT",
    "ADMIN_ACCESS_REQUEST",
    "ADMIN_ACCESS_APPROVED",
    "ADMIN_ACCESS_REJECTED",
]


class AdminDevice(BaseModel):
    device_id: str
    role_scope: AdminDeviceRoleScope
    owner_user_id: str
    device_name: str
    mac_hint: str | None = None
    device_public_key: str
    fingerprint_hash: str
    is_active: bool
    approved_by: str | None = None
    approved_at: datetime | None = None
    created_at: datetime
    last_seen_at: datetime | None = None
    revoked_at: datetime | None = None


class EdgeRelaySession(BaseModel):
    relay_session_id: str
    user_id: str
    role: ManagementRole
    device_id: str
    status: RelayStatus
    connected_at: datetime
    last_heartbeat_at: datetime
    expires_at: datetime
    server_ack_status: str | None = None


class AdminAccessRequest(BaseModel):
    request_id: str
    admin_user_id: str
    device_id: str
    device_name: str | None = None
    mac_hint: str | None = None
    device_public_key: str
    fingerprint_hash: str
    status: AdminAccessRequestStatus
    requested_at: datetime
    decided_by: str | None = None
    decided_at: datetime | None = None
    decision_note: str | None = None


class ManagementActionRequest(BaseModel):
    action_request_id: str
    user_id: str
    role: ManagementRole
    device_id: str
    action_type: str
    payload_hash: str
    status: ManagementActionStatus
    ack_token_hash: str | None = None
    expires_at: datetime
    created_at: datetime
    decided_at: datetime | None = None


class ManagementAuditLog(BaseModel):
    audit_id: str
    actor_user_id: str
    actor_role: str
    device_id: str | None = None
    action_type: str
    target_type: str | None = None
    target_id: str | None = None
    decision: str
    detail_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ManagementUserSummary(BaseModel):
    user_id: str
    username: str
    display_name: str | None = None
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None


class ManagementFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    frame_type: ManagementFrameType
    protocol_version: str = "1.0"
    user_id: str
    device_id: str
    timestamp: datetime
    nonce: str = Field(min_length=8, max_length=128)
    payload_hash: str
    signature: str | None = None
    mac_hint_head: str | None = None
    mac_hint_tail: str | None = None
    session_id: str | None = None
    requested_action: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ManagementAck(BaseModel):
    frame_type: ManagementFrameType
    request_id: str
    decision: ManagementDecision
    expires_at: datetime
    server_nonce: str
    signature: str
    status: str = "ok"


class DeviceEnrollRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str = Field(min_length=6, max_length=160)
    role_scope: AdminDeviceRoleScope
    device_name: str = Field(min_length=1, max_length=160)
    mac_hint: str | None = Field(default=None, max_length=64)
    device_public_key: str = Field(min_length=8, max_length=4096)
    fingerprint_hash: str = Field(min_length=12, max_length=128)


class AdminAccessRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str = Field(min_length=6, max_length=160)
    device_name: str | None = Field(default=None, max_length=160)
    mac_hint: str | None = Field(default=None, max_length=64)
    device_public_key: str = Field(min_length=8, max_length=4096)
    fingerprint_hash: str = Field(min_length=12, max_length=128)


class AdminAccessDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_note: str | None = Field(default=None, max_length=500)


class ActionRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str = Field(min_length=6, max_length=160)
    action_type: str = Field(min_length=2, max_length=120)
    payload_hash: str = Field(min_length=16, max_length=128)


class RelayHeartbeatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relay_session_id: str = Field(min_length=6, max_length=160)


class RelayStatusResponse(BaseModel):
    current: EdgeRelaySession | None = None
    super_admin_online: bool
    server_time: datetime


class ManagementOverview(BaseModel):
    users: list[ManagementUserSummary] = Field(default_factory=list)
    devices: list[AdminDevice] = Field(default_factory=list)
    relay: RelayStatusResponse
    access_requests: list[AdminAccessRequest] = Field(default_factory=list)
    audit_logs: list[ManagementAuditLog] = Field(default_factory=list)


class AdminAccessRequestEnvelope(BaseModel):
    request: AdminAccessRequest


class AdminDeviceEnvelope(BaseModel):
    device: AdminDevice


class ActionAckEnvelope(BaseModel):
    action: ManagementActionRequest
    ack: ManagementAck


class ManagementListEnvelope(BaseModel):
    users: list[ManagementUserSummary] = Field(default_factory=list)
    devices: list[AdminDevice] = Field(default_factory=list)
    access_requests: list[AdminAccessRequest] = Field(default_factory=list)
    audit_logs: list[ManagementAuditLog] = Field(default_factory=list)
