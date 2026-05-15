import {
    ApiOutlined,
    CheckOutlined,
    CloseOutlined,
    DesktopOutlined,
    KeyOutlined,
    ReloadOutlined,
    SafetyCertificateOutlined,
} from "@ant-design/icons";
import { Button, Card, Descriptions, Empty, Space, Table, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../../app/AuthContext";
import { useFeedback } from "../../hooks/useFeedback";
import {
    approveAdminAccessRequest,
    enrollManagementDevice,
    getManagementOverview,
    getRelayStatus,
    getSshTerminalStatus,
    rejectAdminAccessRequest,
} from "../../services/managementApi";
import type {
    AdminAccessRequest,
    AdminDevice,
    ManagementAuditLog,
    ManagementListEnvelope,
    ManagementUserSummary,
    RelayStatusResponse,
    SshTerminalStatus,
} from "../../types/management";

const DEVICE_KEY = "carbonrag-management-device-id";

export function SuperAdminPage() {
    const { user } = useAuth();
    const feedback = useFeedback();
    const [loading, setLoading] = useState(true);
    const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);
    const [overview, setOverview] = useState<ManagementListEnvelope>({
        users: [],
        devices: [],
        access_requests: [],
        audit_logs: [],
    });
    const [relay, setRelay] = useState<RelayStatusResponse | null>(null);
    const [terminal, setTerminal] = useState<SshTerminalStatus | null>(null);

    const currentDevice = useMemo(() => {
        if (typeof window === "undefined") {
            return "browser-device";
        }
        const existing = window.localStorage.getItem(DEVICE_KEY);
        if (existing) {
            return existing;
        }
        const next = `device-${crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36)}`;
        window.localStorage.setItem(DEVICE_KEY, next);
        return next;
    }, []);

    useEffect(() => {
        void refreshAll();
    }, []);

    async function refreshAll() {
        setLoading(true);
        try {
            const [overviewResult, relayResult, terminalResult] = await Promise.all([
                getManagementOverview(),
                getRelayStatus(),
                getSshTerminalStatus(),
            ]);
            setOverview(overviewResult);
            setRelay(relayResult);
            setTerminal(terminalResult);
        } catch (error) {
            feedback.error({
                title: "无法读取超级管理员控制台",
                description: extractErrorMessage(error),
                source: "SuperAdminPage",
            });
        } finally {
            setLoading(false);
        }
    }

    async function handleEnrollCurrentDevice() {
        if (!user) {
            return;
        }
        setActionLoadingId("enroll-device");
        try {
            await enrollManagementDevice({
                device_id: currentDevice,
                role_scope: "super_admin",
                device_name: navigator.userAgent.slice(0, 120) || "当前浏览器",
                device_public_key: `local-browser-public-key-placeholder:${currentDevice}`,
                fingerprint_hash: `fp-${currentDevice}`.slice(0, 120),
                mac_hint: null,
            });
            feedback.success({ title: "当前设备已登记", history: true, source: "SuperAdminPage" });
            await refreshAll();
        } catch (error) {
            feedback.error({
                title: "设备登记失败",
                description: extractErrorMessage(error),
                source: "SuperAdminPage",
            });
        } finally {
            setActionLoadingId(null);
        }
    }

    async function handleApproveRequest(request: AdminAccessRequest) {
        setActionLoadingId(request.request_id);
        try {
            await approveAdminAccessRequest(request.request_id, { decision_note: "super_admin approved" });
            feedback.success({ title: "管理员恢复申请已批准", history: true, source: "SuperAdminPage" });
            await refreshAll();
        } catch (error) {
            feedback.error({
                title: "批准申请失败",
                description: extractErrorMessage(error),
                source: "SuperAdminPage",
            });
        } finally {
            setActionLoadingId(null);
        }
    }

    async function handleRejectRequest(request: AdminAccessRequest) {
        setActionLoadingId(request.request_id);
        try {
            await rejectAdminAccessRequest(request.request_id, { decision_note: "super_admin rejected" });
            feedback.warning({ title: "管理员恢复申请已拒绝", history: true, source: "SuperAdminPage" });
            await refreshAll();
        } catch (error) {
            feedback.error({
                title: "拒绝申请失败",
                description: extractErrorMessage(error),
                source: "SuperAdminPage",
            });
        } finally {
            setActionLoadingId(null);
        }
    }

    const userColumns: ColumnsType<ManagementUserSummary> = [
        {
            title: "账号",
            dataIndex: "username",
            render: (_, record) => (
                <Space direction="vertical" size={0}>
                    <Typography.Text strong>{record.username}</Typography.Text>
                    <Typography.Text type="secondary">{record.display_name || record.user_id}</Typography.Text>
                </Space>
            ),
        },
        {
            title: "角色",
            dataIndex: "role",
            render: (role: string) => <Tag color={role === "super_admin" ? "gold" : role === "admin" ? "purple" : "default"}>{roleLabel(role)}</Tag>,
        },
        {
            title: "状态",
            dataIndex: "is_active",
            render: (active: boolean) => <Tag color={active ? "green" : "red"}>{active ? "启用" : "禁用"}</Tag>,
        },
        {
            title: "最近登录",
            dataIndex: "last_login_at",
            render: formatTime,
        },
    ];

    const deviceColumns: ColumnsType<AdminDevice> = [
        { title: "设备", dataIndex: "device_name" },
        { title: "范围", dataIndex: "role_scope", render: (value: string) => roleLabel(value) },
        { title: "状态", dataIndex: "is_active", render: (active: boolean) => <Tag color={active ? "green" : "red"}>{active ? "有效" : "失效"}</Tag> },
        { title: "最后在线", dataIndex: "last_seen_at", render: formatTime },
        { title: "设备编号", dataIndex: "device_id", render: (value: string) => <Typography.Text code>{shortId(value)}</Typography.Text> },
    ];

    const requestColumns: ColumnsType<AdminAccessRequest> = [
        { title: "管理员", dataIndex: "admin_user_id", render: (value: string) => <Typography.Text code>{shortId(value)}</Typography.Text> },
        { title: "设备", dataIndex: "device_name", render: (value, record) => value || shortId(record.device_id) },
        { title: "状态", dataIndex: "status", render: (value: string) => <Tag color={value === "pending" ? "orange" : value === "approved" ? "green" : "red"}>{requestStatusLabel(value)}</Tag> },
        { title: "申请时间", dataIndex: "requested_at", render: formatTime },
        {
            title: "操作",
            key: "actions",
            render: (_, record) =>
                record.status === "pending" ? (
                    <Space size={8}>
                        <Button
                            size="small"
                            icon={<CheckOutlined />}
                            loading={actionLoadingId === record.request_id}
                            onClick={() => void handleApproveRequest(record)}
                        >
                            同意
                        </Button>
                        <Button
                            size="small"
                            danger
                            icon={<CloseOutlined />}
                            loading={actionLoadingId === record.request_id}
                            onClick={() => void handleRejectRequest(record)}
                        >
                            拒绝
                        </Button>
                    </Space>
                ) : null,
        },
    ];

    const auditColumns: ColumnsType<ManagementAuditLog> = [
        { title: "时间", dataIndex: "created_at", render: formatTime },
        { title: "动作", dataIndex: "action_type" },
        { title: "操作者", dataIndex: "actor_user_id", render: (value: string) => <Typography.Text code>{shortId(value)}</Typography.Text> },
        { title: "决策", dataIndex: "decision", render: (value: string) => <Tag>{value}</Tag> },
    ];

    return (
        <div className="super-admin-page">
            <div className="super-admin-page__hero">
                <Space direction="vertical" size={6}>
                    <Typography.Title level={2}>超级管理员控制台</Typography.Title>
                    <Typography.Text type="secondary">
                        管理设备绑定、管理员恢复申请、Relay 状态和审计记录。Web SSH 当前保持关闭。
                    </Typography.Text>
                </Space>
                <Button icon={<ReloadOutlined />} onClick={() => void refreshAll()} loading={loading}>
                    刷新
                </Button>
            </div>

            <div className="super-admin-page__grid">
                <Card>
                    <Descriptions column={1} size="small" title={<Space><SafetyCertificateOutlined />权限状态</Space>}>
                        <Descriptions.Item label="当前账号">{user?.display_name || user?.username}</Descriptions.Item>
                        <Descriptions.Item label="角色">
                            <Tag color="gold">超级管理员</Tag>
                        </Descriptions.Item>
                        <Descriptions.Item label="当前设备">
                            <Typography.Text code>{shortId(currentDevice)}</Typography.Text>
                        </Descriptions.Item>
                    </Descriptions>
                    <Button
                        type="primary"
                        icon={<KeyOutlined />}
                        loading={actionLoadingId === "enroll-device"}
                        onClick={() => void handleEnrollCurrentDevice()}
                    >
                        登记当前设备
                    </Button>
                </Card>
                <Card>
                    <Descriptions column={1} size="small" title={<Space><ApiOutlined />Edge Relay</Space>}>
                        <Descriptions.Item label="超级管理员在线">
                            <Tag color={relay?.super_admin_online ? "green" : "default"}>
                                {relay?.super_admin_online ? "在线" : "未连接"}
                            </Tag>
                        </Descriptions.Item>
                        <Descriptions.Item label="当前 Relay">
                            {relay?.current ? relay.current.status : "暂无"}
                        </Descriptions.Item>
                        <Descriptions.Item label="服务器时间">{formatTime(relay?.server_time)}</Descriptions.Item>
                    </Descriptions>
                </Card>
                <Card>
                    <Descriptions column={1} size="small" title={<Space><DesktopOutlined />Web SSH</Space>}>
                        <Descriptions.Item label="状态">
                            <Tag color={terminal?.enabled ? "red" : "default"}>{terminal?.enabled ? "已启用" : "默认关闭"}</Tag>
                        </Descriptions.Item>
                        <Descriptions.Item label="说明">
                            {terminal?.status || "需要单独安全评审后才能启用。"}
                        </Descriptions.Item>
                    </Descriptions>
                </Card>
            </div>

            <Card title="待审批管理员恢复申请">
                <Table
                    rowKey="request_id"
                    loading={loading}
                    columns={requestColumns}
                    dataSource={overview.access_requests}
                    pagination={{ pageSize: 6 }}
                    locale={{ emptyText: <Empty description="暂无恢复申请" /> }}
                />
            </Card>
            <Card title="管理员与用户">
                <Table
                    rowKey="user_id"
                    loading={loading}
                    columns={userColumns}
                    dataSource={overview.users}
                    pagination={{ pageSize: 8 }}
                />
            </Card>
            <Card title="管理员设备">
                <Table
                    rowKey="device_id"
                    loading={loading}
                    columns={deviceColumns}
                    dataSource={overview.devices}
                    pagination={{ pageSize: 8 }}
                />
            </Card>
            <Card title="管理审计日志">
                <Table
                    rowKey="audit_id"
                    loading={loading}
                    columns={auditColumns}
                    dataSource={overview.audit_logs}
                    pagination={{ pageSize: 8 }}
                />
            </Card>
        </div>
    );
}

function roleLabel(role: string) {
    if (role === "super_admin") {
        return "超级管理员";
    }
    if (role === "admin") {
        return "管理员";
    }
    return "用户";
}

function requestStatusLabel(status: string) {
    if (status === "pending") {
        return "待审批";
    }
    if (status === "approved") {
        return "已通过";
    }
    if (status === "rejected") {
        return "已拒绝";
    }
    return "已过期";
}

function formatTime(value?: string | null) {
    if (!value) {
        return "暂无";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return value;
    }
    return date.toLocaleString("zh-CN", { hour12: false });
}

function shortId(value?: string | null) {
    if (!value) {
        return "暂无";
    }
    return value.length > 16 ? `${value.slice(0, 8)}...${value.slice(-6)}` : value;
}

function extractErrorMessage(error: unknown) {
    if (error && typeof error === "object") {
        const response = (error as { response?: { data?: { detail?: unknown; message?: unknown } } }).response;
        const detail = response?.data?.detail ?? response?.data?.message;
        if (typeof detail === "string" && detail.trim()) {
            return detail;
        }
    }
    return error instanceof Error ? error.message : "请稍后重试。";
}
