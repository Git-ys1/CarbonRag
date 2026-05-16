import { httpClient } from "./http";
import env from "../app/env";
import type {
    ActionAckEnvelope,
    AdminAccessDecisionRequest,
    AdminAccessRequestCreate,
    AdminAccessRequestEnvelope,
    AdminDeviceEnvelope,
    DeviceEnrollRequest,
    ManagementAck,
    ManagementListEnvelope,
    RelayStatusResponse,
    ServerOpsCommandSummary,
    ServerOpsRunResponse,
    SshTerminalStatus,
} from "../types/management";

const LEGACY_DEVICE_ID_KEY = "carbonrag-management-device-id";
const DEVICE_ID_KEY_PREFIX = "carbonrag-management-device-id";
const DEVICE_CONTEXT_KEY = "carbonrag-management-current-device-context";
const DEVICE_DB_NAME = "carbonrag-management-device-keys";
const DEVICE_DB_STORE = "keys";
const LEGACY_DEVICE_KEY_RECORD = "p256-signing-keypair";

export type ManagementRoleScope = "admin" | "super_admin";

export interface ManagementDeviceContext {
    userId: string;
    roleScope: ManagementRoleScope;
}

export interface ManagementDeviceIdentity {
    deviceId: string;
    publicKeyJwk: JsonWebKey;
    publicKeyJson: string;
    fingerprintHash: string;
}

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
    const headers = await buildActionAckHeaders("ADMIN_ACCESS_APPROVE", "admin_access_request", requestId, payload);
    const response = await httpClient.post<AdminAccessRequestEnvelope>(
        `/v1/management/admin-access/${requestId}/approve`,
        payload,
        { headers },
    );
    return response.data;
}

export async function rejectAdminAccessRequest(requestId: string, payload: AdminAccessDecisionRequest = {}) {
    const headers = await buildActionAckHeaders("ADMIN_ACCESS_REJECT", "admin_access_request", requestId, payload);
    const response = await httpClient.post<AdminAccessRequestEnvelope>(
        `/v1/management/admin-access/${requestId}/reject`,
        payload,
        { headers },
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

export function openSshTerminalSocket() {
    return new WebSocket(buildWebSocketUrl("/v1/management/ssh-terminal/ws"));
}

export async function listServerOpsCommands() {
    const response = await httpClient.get<{ commands: ServerOpsCommandSummary[] }>("/v1/management/server-ops/commands");
    return response.data.commands;
}

export async function runServerOpsCommand(commandId: string, reason?: string) {
    const payload = { confirm: true, reason: reason || null };
    const headers = await buildActionAckHeaders("SERVER_OPS_RUN", "server_ops_command", commandId, payload);
    const response = await httpClient.post<ServerOpsRunResponse>(
        `/v1/management/server-ops/commands/${commandId}/run`,
        payload,
        { headers },
    );
    return response.data;
}

export async function startSuperAdminRelay(userId: string) {
    const context = { userId, roleScope: "super_admin" as const };
    const identity = await getOrCreateManagementDeviceIdentity(context);
    const frame = await buildSignedManagementFrame({
        frameType: "SA_HELLO",
        userId,
        deviceId: identity.deviceId,
        requestedAction: "ENTER_SUPER_ADMIN_CONSOLE",
    });
    const response = await httpClient.post<ManagementAck>("/v1/management/super-admin/hello", frame);
    setActiveManagementDeviceContext(context);
    return { ack: response.data, identity };
}

export async function startAdminRelay(userId: string) {
    const context = { userId, roleScope: "admin" as const };
    const identity = await getOrCreateManagementDeviceIdentity(context);
    const frame = await buildSignedManagementFrame({
        frameType: "AD_HELLO",
        userId,
        deviceId: identity.deviceId,
        requestedAction: "ENTER_ADMIN_CONSOLE",
    });
    const response = await httpClient.post<ManagementAck>("/v1/management/admin/hello", frame);
    setActiveManagementDeviceContext(context);
    return { ack: response.data, identity };
}

export async function sendRelayHeartbeat(relaySessionId: string) {
    const response = await httpClient.post<RelayStatusResponse>("/v1/management/relay/heartbeat", {
        relay_session_id: relaySessionId,
    });
    return response.data;
}

export async function getOrCreateManagementDeviceIdentity(context?: ManagementDeviceContext): Promise<ManagementDeviceIdentity> {
    const resolvedContext = resolveManagementDeviceContext(context);
    if (resolvedContext) {
        setActiveManagementDeviceContext(resolvedContext);
    }
    const namespace = resolvedContext ? managementDeviceNamespace(resolvedContext) : null;
    const deviceId = getOrCreateDeviceId(namespace);
    const keyPair = await getOrCreateDeviceKeyPair(namespace);
    const publicKeyJwk = await crypto.subtle.exportKey("jwk", keyPair.publicKey);
    const publicKeyJson = JSON.stringify(normalizePublicJwk(publicKeyJwk));
    const fingerprintHash = await sha256Hex(publicKeyJson);
    return { deviceId, publicKeyJwk, publicKeyJson, fingerprintHash };
}

export async function resetManagementDeviceIdentity(context: ManagementDeviceContext): Promise<ManagementDeviceIdentity> {
    const namespace = managementDeviceNamespace(context);
    window.localStorage.removeItem(deviceIdStorageKey(namespace));
    await deleteDeviceKeyPair(namespace).catch(() => undefined);
    setActiveManagementDeviceContext(context);
    return getOrCreateManagementDeviceIdentity(context);
}

export function isManagementDeviceOwnershipConflict(error: unknown) {
    const message = extractApiDetail(error).toLowerCase();
    return message.includes("already registered by another user") || message.includes("owned by another user");
}

export async function buildActionAckHeaders(
    actionType: string,
    targetType: string,
    targetId: string,
    payload: unknown,
) {
    const identity = await getOrCreateManagementDeviceIdentity();
    const payloadHash = await sha256Hex(stableStringify(payload ?? {}));
    const response = await httpClient.post<ActionAckEnvelope>("/v1/management/action/request", {
        device_id: identity.deviceId,
        action_type: actionType,
        target_type: targetType,
        target_id: targetId,
        payload_hash: payloadHash,
    });
    return {
        "X-Management-Action-Request-Id": response.data.action.action_request_id,
        "X-Management-Payload-Hash": payloadHash,
    };
}

async function buildSignedManagementFrame({
    frameType,
    userId,
    deviceId,
    requestedAction,
}: {
    frameType: "SA_HELLO" | "AD_HELLO";
    userId: string;
    deviceId: string;
    requestedAction: string;
}) {
    const payloadHash = await sha256Hex(stableStringify({ user_id: userId, device_id: deviceId, requested_action: requestedAction }));
    const frame = {
        frame_type: frameType,
        protocol_version: "1.0",
        user_id: userId,
        device_id: deviceId,
        timestamp: managementFrameTimestamp(),
        nonce: randomNonce(),
        requested_action: requestedAction,
        payload_hash: payloadHash,
        mac_hint_head: null,
        mac_hint_tail: null,
        session_id: null,
        metadata: {},
    };
    const signature = await signCanonicalPayload(frame);
    return { ...frame, signature };
}

async function signCanonicalPayload(payload: Record<string, unknown>) {
    const context = resolveManagementDeviceContext();
    const keyPair = await getOrCreateDeviceKeyPair(context ? managementDeviceNamespace(context) : null);
    const encoded = new TextEncoder().encode(stableStringify(payload));
    const signature = await crypto.subtle.sign({ name: "ECDSA", hash: "SHA-256" }, keyPair.privateKey, encoded);
    return base64Url(signature);
}

async function getOrCreateDeviceKeyPair(namespace: string | null): Promise<CryptoKeyPair> {
    const db = await openDeviceDb();
    const recordKey = deviceKeyRecord(namespace);
    const existing = await readKeyPair(db, recordKey);
    if (existing) {
        return existing;
    }
    const keyPair = await crypto.subtle.generateKey(
        { name: "ECDSA", namedCurve: "P-256" },
        false,
        ["sign", "verify"],
    );
    await writeKeyPair(db, recordKey, keyPair);
    return keyPair;
}

function getOrCreateDeviceId(namespace: string | null) {
    const storageKey = deviceIdStorageKey(namespace);
    const existing = window.localStorage.getItem(storageKey);
    if (existing) {
        return existing;
    }
    const next = `device-${crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36)}`;
    window.localStorage.setItem(storageKey, next);
    return next;
}

function openDeviceDb(): Promise<IDBDatabase> {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open(DEVICE_DB_NAME, 1);
        request.onupgradeneeded = () => {
            request.result.createObjectStore(DEVICE_DB_STORE);
        };
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
}

function readKeyPair(db: IDBDatabase, recordKey: string): Promise<CryptoKeyPair | null> {
    return new Promise((resolve, reject) => {
        const transaction = db.transaction(DEVICE_DB_STORE, "readonly");
        const request = transaction.objectStore(DEVICE_DB_STORE).get(recordKey);
        request.onsuccess = () => resolve((request.result as CryptoKeyPair | undefined) ?? null);
        request.onerror = () => reject(request.error);
    });
}

function writeKeyPair(db: IDBDatabase, recordKey: string, keyPair: CryptoKeyPair): Promise<void> {
    return new Promise((resolve, reject) => {
        const transaction = db.transaction(DEVICE_DB_STORE, "readwrite");
        transaction.objectStore(DEVICE_DB_STORE).put(keyPair, recordKey);
        transaction.oncomplete = () => resolve();
        transaction.onerror = () => reject(transaction.error);
    });
}

function deleteDeviceKeyPair(namespace: string): Promise<void> {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open(DEVICE_DB_NAME, 1);
        request.onupgradeneeded = () => {
            request.result.createObjectStore(DEVICE_DB_STORE);
        };
        request.onsuccess = () => {
            const db = request.result;
            const transaction = db.transaction(DEVICE_DB_STORE, "readwrite");
            transaction.objectStore(DEVICE_DB_STORE).delete(deviceKeyRecord(namespace));
            transaction.oncomplete = () => {
                db.close();
                resolve();
            };
            transaction.onerror = () => {
                db.close();
                reject(transaction.error);
            };
        };
        request.onerror = () => reject(request.error);
    });
}

function resolveManagementDeviceContext(context?: ManagementDeviceContext): ManagementDeviceContext | null {
    if (context?.userId && context.roleScope) {
        return context;
    }
    const stored = window.localStorage.getItem(DEVICE_CONTEXT_KEY);
    if (!stored) {
        return null;
    }
    try {
        const parsed = JSON.parse(stored) as Partial<ManagementDeviceContext>;
        if (parsed.userId && (parsed.roleScope === "admin" || parsed.roleScope === "super_admin")) {
            return { userId: parsed.userId, roleScope: parsed.roleScope };
        }
    } catch {
        window.localStorage.removeItem(DEVICE_CONTEXT_KEY);
    }
    return null;
}

function setActiveManagementDeviceContext(context: ManagementDeviceContext) {
    window.localStorage.setItem(DEVICE_CONTEXT_KEY, JSON.stringify(context));
}

function managementDeviceNamespace(context: ManagementDeviceContext) {
    return `${context.roleScope}:${context.userId}`;
}

function deviceIdStorageKey(namespace: string | null) {
    return namespace ? `${DEVICE_ID_KEY_PREFIX}:${namespace}` : LEGACY_DEVICE_ID_KEY;
}

function deviceKeyRecord(namespace: string | null) {
    return namespace ? `${LEGACY_DEVICE_KEY_RECORD}:${namespace}` : LEGACY_DEVICE_KEY_RECORD;
}

function normalizePublicJwk(jwk: JsonWebKey): JsonWebKey {
    return {
        kty: jwk.kty,
        crv: jwk.crv,
        x: jwk.x,
        y: jwk.y,
        ext: true,
    };
}

function randomNonce() {
    const bytes = new Uint8Array(24);
    crypto.getRandomValues(bytes);
    return base64Url(bytes.buffer);
}

function managementFrameTimestamp() {
    // Pydantic serializes UTC datetimes at second precision as "...Z"; avoid
    // signing browser millisecond text that the backend normalizes to microseconds.
    return new Date().toISOString().replace(/\.\d{3}Z$/u, "Z");
}

async function sha256Hex(value: string) {
    const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
    return Array.from(new Uint8Array(digest))
        .map((byte) => byte.toString(16).padStart(2, "0"))
        .join("");
}

function base64Url(buffer: ArrayBuffer) {
    const bytes = new Uint8Array(buffer);
    let binary = "";
    bytes.forEach((byte) => {
        binary += String.fromCharCode(byte);
    });
    return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/u, "");
}

function buildWebSocketUrl(path: string) {
    const base = String(httpClient.defaults.baseURL || env.apiBaseUrl || "/api").replace(/\/+$/u, "");
    const url = new URL(base, window.location.origin);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    url.pathname = `${url.pathname.replace(/\/+$/u, "")}${path}`;
    return url.toString();
}

function extractApiDetail(error: unknown) {
    if (error && typeof error === "object") {
        const response = (error as { response?: { data?: { detail?: unknown; message?: unknown } } }).response;
        const detail = response?.data?.detail ?? response?.data?.message;
        if (typeof detail === "string") {
            return detail;
        }
    }
    return error instanceof Error ? error.message : "";
}

function stableStringify(value: unknown): string {
    if (value === null || typeof value !== "object") {
        return JSON.stringify(value);
    }
    if (Array.isArray(value)) {
        return `[${value.map((item) => stableStringify(item)).join(",")}]`;
    }
    const object = value as Record<string, unknown>;
    return `{${Object.keys(object)
        .sort()
        .map((key) => `${JSON.stringify(key)}:${stableStringify(object[key])}`)
        .join(",")}}`;
}
