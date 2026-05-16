import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { PropsWithChildren } from "react";
import axios from "axios";
import { changePassword, deleteOwnAccount, getCurrentUser, loginAccount, logoutAccount, registerAccount, updateProfile } from "../services/auth";
import {
    createAdminAccessRequest,
    enrollManagementDevice,
    getOrCreateManagementDeviceIdentity,
    getRelayStatus,
    sendRelayHeartbeat,
    startAdminRelay,
    startSuperAdminRelay,
} from "../services/managementApi";
import type { AuthUser, ChangePasswordRequest, CurrentPasswordRequest, LoginRequest, RegisterRequest, UpdateProfileRequest } from "../types/auth";

interface AuthContextValue {
    user: AuthUser | null;
    loading: boolean;
    login: (payload: LoginRequest) => Promise<AuthUser>;
    register: (payload: RegisterRequest) => Promise<AuthUser>;
    logout: () => Promise<void>;
    deleteAccount: (payload: CurrentPasswordRequest) => Promise<void>;
    refresh: () => Promise<AuthUser | null>;
    changePassword: (payload: ChangePasswordRequest) => Promise<AuthUser>;
    updateProfile: (payload: UpdateProfileRequest) => Promise<AuthUser>;
}

const AuthContext = createContext<AuthContextValue | null>(null);
const MANAGEMENT_RELAY_READY_EVENT = "carbonrag-management-relay-ready";

export function AuthProvider({ children }: PropsWithChildren) {
    const [user, setUser] = useState<AuthUser | null>(null);
    const [loading, setLoading] = useState(true);

    async function refresh() {
        try {
            const response = await getCurrentUser();
            setUser(response.user);
            return response.user;
        } catch (error) {
            if (axios.isAxiosError(error) && error.response?.status === 401) {
                setUser(null);
                return null;
            }
            throw error;
        } finally {
            setLoading(false);
        }
    }

    useEffect(() => {
        void refresh();
    }, []);

    useEffect(() => {
        if (!user || user.password_must_change || !isManagementRole(user.role)) {
            return;
        }

        let cancelled = false;
        let heartbeatTimer: number | undefined;

        const startHeartbeat = (relaySessionId: string) => {
            window.clearInterval(heartbeatTimer);
            heartbeatTimer = window.setInterval(() => {
                void sendRelayHeartbeat(relaySessionId).catch(() => undefined);
            }, 25_000);
        };

        const dispatchReady = () => {
            window.dispatchEvent(new CustomEvent(MANAGEMENT_RELAY_READY_EVENT, { detail: { role: user.role } }));
        };

        const bootstrapRelay = async () => {
            try {
                const existing = await getRelayStatus().catch(() => null);
                if (
                    existing?.current?.status === "connected" &&
                    existing.current.role === user.role &&
                    !cancelled
                ) {
                    startHeartbeat(existing.current.relay_session_id);
                    dispatchReady();
                    return;
                }

                const identity = await getOrCreateManagementDeviceIdentity();
                if (user.role === "super_admin") {
                    let started = await startSuperAdminRelay(user.user_id).catch(async () => {
                        await enrollManagementDevice({
                            device_id: identity.deviceId,
                            role_scope: "super_admin",
                            device_name: getBrowserDeviceName(),
                            mac_hint: null,
                            device_public_key: identity.publicKeyJson,
                            fingerprint_hash: identity.fingerprintHash,
                        });
                        return startSuperAdminRelay(user.user_id);
                    });
                    if (!cancelled) {
                        startHeartbeat(started.ack.request_id);
                        dispatchReady();
                    }
                    return;
                }

                const started = await startAdminRelay(user.user_id).catch(async () => {
                    await ensureAdminAccessRequest(user);
                    return null;
                });
                if (started && !cancelled) {
                    startHeartbeat(started.ack.request_id);
                    dispatchReady();
                }
            } catch {
                // Silent by design: admin pages will show explicit guidance if relay cannot be established.
            }
        };

        void bootstrapRelay();
        return () => {
            cancelled = true;
            window.clearInterval(heartbeatTimer);
        };
    }, [user?.user_id, user?.role, user?.password_must_change]);

    async function login(payload: LoginRequest) {
        const response = await loginAccount(payload);
        setUser(response.user);
        return response.user;
    }

    async function register(payload: RegisterRequest) {
        const response = await registerAccount(payload);
        return response.user;
    }

    async function logout() {
        try {
            await logoutAccount();
        } finally {
            setUser(null);
        }
    }

    async function deleteAccount(payload: CurrentPasswordRequest) {
        await deleteOwnAccount(payload);
        setUser(null);
    }

    async function handleChangePassword(payload: ChangePasswordRequest) {
        const response = await changePassword(payload);
        setUser(response.user);
        return response.user;
    }

    async function handleUpdateProfile(payload: UpdateProfileRequest) {
        const response = await updateProfile(payload);
        setUser(response.user);
        return response.user;
    }

    const value = useMemo<AuthContextValue>(
        () => ({
            user,
            loading,
            login,
            register,
            logout,
            deleteAccount,
            refresh,
            changePassword: handleChangePassword,
            updateProfile: handleUpdateProfile,
        }),
        [loading, user],
    );

    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

async function ensureAdminAccessRequest(user: AuthUser) {
    const identity = await getOrCreateManagementDeviceIdentity();
    const requestKey = `carbonrag-admin-access-requested:${user.user_id}:${identity.deviceId}`;
    await enrollManagementDevice({
        device_id: identity.deviceId,
        role_scope: "admin",
        device_name: getBrowserDeviceName(),
        mac_hint: null,
        device_public_key: identity.publicKeyJson,
        fingerprint_hash: identity.fingerprintHash,
    }).catch(() => undefined);
    if (window.localStorage.getItem(requestKey)) {
        return;
    }
    await createAdminAccessRequest({
        device_id: identity.deviceId,
        device_name: getBrowserDeviceName(),
        mac_hint: null,
        device_public_key: identity.publicKeyJson,
        fingerprint_hash: identity.fingerprintHash,
    });
    window.localStorage.setItem(requestKey, new Date().toISOString());
}

function getBrowserDeviceName() {
    const ua = window.navigator.userAgent || "当前浏览器";
    return ua.length > 120 ? `${ua.slice(0, 117)}...` : ua;
}

function isManagementRole(role: AuthUser["role"]): role is "admin" | "super_admin" {
    return role === "admin" || role === "super_admin";
}

export function useAuth() {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error("useAuth must be used within AuthProvider.");
    }
    return context;
}
