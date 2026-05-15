import type { UserRole } from "./auth";

export type ManagementRole = "admin" | "super_admin";
export type AdminDeviceRoleScope = "admin" | "super_admin";
export type RelayStatus = "pending" | "connected" | "expired" | "revoked";
export type AdminAccessRequestStatus = "pending" | "approved" | "rejected" | "expired";
export type ManagementActionStatus = "pending" | "approved" | "rejected" | "expired";
export type ManagementDecision = "allow" | "deny" | "pending";

export interface AdminDevice {
    device_id: string;
    role_scope: AdminDeviceRoleScope;
    owner_user_id: string;
    device_name: string;
    mac_hint?: string | null;
    device_public_key: string;
    fingerprint_hash: string;
    is_active: boolean;
    approved_by?: string | null;
    approved_at?: string | null;
    created_at: string;
    last_seen_at?: string | null;
    revoked_at?: string | null;
}

export interface EdgeRelaySession {
    relay_session_id: string;
    user_id: string;
    role: ManagementRole;
    device_id: string;
    status: RelayStatus;
    connected_at: string;
    last_heartbeat_at: string;
    expires_at: string;
    server_ack_status?: string | null;
}

export interface AdminAccessRequest {
    request_id: string;
    admin_user_id: string;
    device_id: string;
    device_name?: string | null;
    mac_hint?: string | null;
    device_public_key: string;
    fingerprint_hash: string;
    status: AdminAccessRequestStatus;
    requested_at: string;
    decided_by?: string | null;
    decided_at?: string | null;
    decision_note?: string | null;
}

export interface ManagementActionRequest {
    action_request_id: string;
    user_id: string;
    role: ManagementRole;
    device_id: string;
    action_type: string;
    payload_hash: string;
    status: ManagementActionStatus;
    ack_token_hash?: string | null;
    expires_at: string;
    created_at: string;
    decided_at?: string | null;
}

export interface ManagementAuditLog {
    audit_id: string;
    actor_user_id: string;
    actor_role: string;
    device_id?: string | null;
    action_type: string;
    target_type?: string | null;
    target_id?: string | null;
    decision: string;
    detail_json: Record<string, unknown>;
    created_at: string;
}

export interface ManagementUserSummary {
    user_id: string;
    username: string;
    display_name?: string | null;
    role: UserRole;
    is_active: boolean;
    created_at: string;
    last_login_at?: string | null;
}

export interface RelayStatusResponse {
    current?: EdgeRelaySession | null;
    super_admin_online: boolean;
    server_time: string;
}

export interface ManagementListEnvelope {
    users: ManagementUserSummary[];
    devices: AdminDevice[];
    access_requests: AdminAccessRequest[];
    audit_logs: ManagementAuditLog[];
}

export interface DeviceEnrollRequest {
    device_id: string;
    role_scope: AdminDeviceRoleScope;
    device_name: string;
    mac_hint?: string | null;
    device_public_key: string;
    fingerprint_hash: string;
}

export interface AdminDeviceEnvelope {
    device: AdminDevice;
}

export interface AdminAccessRequestCreate {
    device_id: string;
    device_name?: string | null;
    mac_hint?: string | null;
    device_public_key: string;
    fingerprint_hash: string;
}

export interface AdminAccessDecisionRequest {
    decision_note?: string | null;
}

export interface AdminAccessRequestEnvelope {
    request: AdminAccessRequest;
}

export interface SshTerminalStatus {
    enabled: boolean;
    status: string;
}
