import { httpClient } from "./http";
import type {
    AdminAccessDecisionRequest,
    AdminAccessRequestCreate,
    AdminAccessRequestEnvelope,
    AdminDeviceEnvelope,
    DeviceEnrollRequest,
    ManagementListEnvelope,
    RelayStatusResponse,
    SshTerminalStatus,
} from "../types/management";

export async function getManagementOverview() {
    const response = await httpClient.get<ManagementListEnvelope>("/v1/management/overview");
    return response.data;
}

export async function getRelayStatus() {
    const response = await httpClient.get<RelayStatusResponse>("/v1/management/relay/status");
    return response.data;
}

export async function enrollManagementDevice(payload: DeviceEnrollRequest) {
    const response = await httpClient.post<AdminDeviceEnvelope>("/v1/management/device/enroll", payload);
    return response.data;
}

export async function createAdminAccessRequest(payload: AdminAccessRequestCreate) {
    const response = await httpClient.post<AdminAccessRequestEnvelope>("/v1/management/admin-access/request", payload);
    return response.data;
}

export async function approveAdminAccessRequest(requestId: string, payload: AdminAccessDecisionRequest = {}) {
    const response = await httpClient.post<AdminAccessRequestEnvelope>(
        `/v1/management/admin-access/${requestId}/approve`,
        payload,
    );
    return response.data;
}

export async function rejectAdminAccessRequest(requestId: string, payload: AdminAccessDecisionRequest = {}) {
    const response = await httpClient.post<AdminAccessRequestEnvelope>(
        `/v1/management/admin-access/${requestId}/reject`,
        payload,
    );
    return response.data;
}

export async function getManagementAuditLogs() {
    const response = await httpClient.get<ManagementListEnvelope>("/v1/management/audit-logs");
    return response.data;
}

export async function getSshTerminalStatus() {
    const response = await httpClient.get<SshTerminalStatus>("/v1/management/ssh-terminal/status");
    return response.data;
}
