import { DatabaseOutlined, EyeOutlined, ReloadOutlined, SyncOutlined } from "@ant-design/icons";
import {
    Alert,
    Button,
    Card,
    Descriptions,
    Empty,
    List,
    Modal,
    Space,
    Spin,
    Statistic,
    Switch,
    Table,
    Tag,
    Tooltip,
    Typography,
    message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useMemo, useState } from "react";
import {
    getAdminFeedbackOverview,
    getAdminSystemStatus,
    getPolicyShowcaseRetrievalPreview,
    getPolicyShowcaseStatus,
    listAdminUsers,
    listPolicyShowcaseChunks,
    listPolicyShowcaseSources,
    resetAdminUserPassword,
    runPolicyShowcaseSource,
    updateAdminUser,
} from "../../services/admin";
import {
    listAdminKnowledgeItems,
    listAdminKnowledgeTasks,
    retryKnowledgeTask,
    triggerKnowledgeRebuild,
    triggerKnowledgeScan,
    updateAdminKnowledgeItem,
} from "../../services/knowledge";
import type {
    AdminFeedbackOverview,
    AdminSystemStatus,
    AdminUserSummary,
    PolicyShowcaseSourceSummary,
    PolicyShowcaseStatus,
} from "../../types/admin";
import type { KnowledgeItem, KnowledgeTask } from "../../types/knowledge";

type KnowledgeTaskRefreshAction = "scan" | "rebuild" | null;

export function AdminPlaceholderPage() {
    const [loading, setLoading] = useState(true);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const [systemStatus, setSystemStatus] = useState<AdminSystemStatus | null>(null);
    const [users, setUsers] = useState<AdminUserSummary[]>([]);
    const [feedbackOverview, setFeedbackOverview] = useState<AdminFeedbackOverview | null>(null);
    const [knowledgeItems, setKnowledgeItems] = useState<KnowledgeItem[]>([]);
    const [knowledgeTasks, setKnowledgeTasks] = useState<KnowledgeTask[]>([]);
    const [policySources, setPolicySources] = useState<PolicyShowcaseSourceSummary[]>([]);
    const [policyShowcaseStatus, setPolicyShowcaseStatus] = useState<PolicyShowcaseStatus | null>(null);
    const [userSavingId, setUserSavingId] = useState<string | null>(null);
    const [knowledgeItemSavingId, setKnowledgeItemSavingId] = useState<string | null>(null);
    const [refreshingKnowledge, setRefreshingKnowledge] = useState<KnowledgeTaskRefreshAction>(null);
    const [runningPolicySourceId, setRunningPolicySourceId] = useState<string | null>(null);
    const [loadingPolicySourceId, setLoadingPolicySourceId] = useState<string | null>(null);
    const [selectedTask, setSelectedTask] = useState<KnowledgeTask | null>(null);

    const userColumns = useMemo<ColumnsType<AdminUserSummary>>(
        () => [
            {
                title: "用户",
                dataIndex: "username",
                key: "username",
                render: (_, record) => (
                    <Space direction="vertical" size={0}>
                        <Typography.Text strong>{record.username}</Typography.Text>
                        <Typography.Text type="secondary">{record.user_id}</Typography.Text>
                    </Space>
                ),
            },
            {
                title: "角色",
                key: "role",
                render: (_, record) => (
                    <Space direction="vertical" size={4}>
                        <Typography.Text>{roleLabelMap[record.role] ?? record.role}</Typography.Text>
                        <Button
                            size="small"
                            disabled={userSavingId === record.user_id}
                            onClick={() => void handleUpdateUser(record, record.role === "admin" ? "user" : "admin", record.is_active)}
                        >
                            切换角色
                        </Button>
                    </Space>
                ),
            },
            {
                title: "状态",
                key: "is_active",
                render: (_, record) => (
                    <Switch
                        size="small"
                        checked={record.is_active}
                        loading={userSavingId === record.user_id}
                        onChange={(checked) => void handleUpdateUser(record, record.role, checked)}
                    />
                ),
            },
            {
                title: "使用情况",
                key: "counts",
                render: (_, record) => (
                    <Space size={8} wrap>
                        <Tag>{record.session_count} 个会话</Tag>
                        <Tag>{record.report_count} 份报告</Tag>
                        <Tag>{record.feedback_count} 条反馈</Tag>
                    </Space>
                ),
            },
            {
                title: "操作",
                key: "actions",
                render: (_, record) => (
                    <Space size={8} wrap>
                        {record.password_must_change ? <Tag color="orange">下次登录需改密</Tag> : null}
                        <Button
                            size="small"
                            disabled={userSavingId === record.user_id}
                            onClick={() => void handleResetPassword(record.user_id)}
                        >
                            重置密码
                        </Button>
                    </Space>
                ),
            },
        ],
        [userSavingId],
    );

    const knowledgeColumns = useMemo<ColumnsType<KnowledgeItem>>(
        () => [
            {
                title: "知识条目",
                key: "title",
                render: (_, record) => (
                    <Space direction="vertical" size={2}>
                        <Typography.Text strong>{record.title}</Typography.Text>
                        <Typography.Text type="secondary">{record.source_label}</Typography.Text>
                        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                            {record.source_ref}
                        </Typography.Text>
                    </Space>
                ),
            },
            {
                title: "层级",
                key: "library_scope",
                render: (_, record) => (
                    <Tag color={record.library_scope === "shared" ? "blue" : "green"}>
                        {libraryScopeLabelMap[record.library_scope]}
                    </Tag>
                ),
            },
            {
                title: "来源类型",
                key: "source_type",
                render: (_, record) => <Tag>{sourceTypeLabelMap[record.source_type] ?? record.source_type}</Tag>,
            },
            {
                title: "解析 / 入库 / 索引",
                key: "pipeline",
                render: (_, record) => (
                    <Space size={6} wrap>
                        <Tag color={statusColorMap[record.parse_status]}>{statusLabelMap[record.parse_status]}</Tag>
                        <Tag color={statusColorMap[record.ingest_status]}>{statusLabelMap[record.ingest_status]}</Tag>
                        <Tag color={statusColorMap[record.index_status]}>{statusLabelMap[record.index_status]}</Tag>
                    </Space>
                ),
            },
            {
                title: "启用 / 可挂接",
                key: "switches",
                render: (_, record) => {
                    const editable = record.library_scope === "shared";
                    if (!editable) {
                        return <Tag color="default">个人知识只读</Tag>;
                    }
                    return (
                        <Space size={12} wrap>
                            <Space size={6}>
                                <Typography.Text type="secondary">启用</Typography.Text>
                                <Switch
                                    size="small"
                                    checked={record.is_enabled}
                                    loading={knowledgeItemSavingId === record.knowledge_item_id}
                                    onChange={(checked) =>
                                        void handleUpdateKnowledgeItem(record, {
                                            is_enabled: checked,
                                            session_attachable: record.session_attachable,
                                        })
                                    }
                                />
                            </Space>
                            <Space size={6}>
                                <Typography.Text type="secondary">可挂接</Typography.Text>
                                <Switch
                                    size="small"
                                    checked={record.session_attachable}
                                    loading={knowledgeItemSavingId === record.knowledge_item_id}
                                    onChange={(checked) =>
                                        void handleUpdateKnowledgeItem(record, {
                                            is_enabled: record.is_enabled,
                                            session_attachable: checked,
                                        })
                                    }
                                />
                            </Space>
                        </Space>
                    );
                },
            },
            {
                title: "更新时间",
                key: "updated_at",
                render: (_, record) => formatTimestamp(record.updated_at ?? ""),
            },
        ],
        [knowledgeItemSavingId],
    );

    const taskColumns = useMemo<ColumnsType<KnowledgeTask>>(
        () => [
            {
                title: "任务编号",
                dataIndex: "task_id",
                key: "task_id",
                width: 180,
                render: (value: string) => <Typography.Text code>{value}</Typography.Text>,
            },
            {
                title: "动作",
                key: "task_type",
                width: 100,
                render: (_, record) => <Tag>{taskTypeLabelMap[record.task_type] ?? record.task_type}</Tag>,
            },
            {
                title: "范围",
                key: "scope",
                width: 100,
                render: (_, record) => <Tag>{taskScopeLabelMap[record.scope] ?? record.scope}</Tag>,
            },
            {
                title: "状态",
                key: "status",
                width: 90,
                render: (_, record) => <Tag color={taskStatusColorMap[record.status]}>{taskStatusLabelMap[record.status]}</Tag>,
            },
            {
                title: "摘要",
                key: "summary",
                width: 260,
                render: (_, record) => (
                    <div className="admin-table-cell admin-table-cell--multiline">
                        <Typography.Paragraph
                            type="secondary"
                            ellipsis={{ rows: 2, expandable: false, tooltip: record.summary ?? "暂无摘要。" }}
                        >
                            {record.summary ?? "暂无摘要。"}
                        </Typography.Paragraph>
                    </div>
                ),
            },
            {
                title: "对象",
                key: "target_label",
                width: 180,
                render: (_, record) => (
                    <div className="admin-table-cell">
                        <Tooltip title={record.target_label ?? "全部"}>
                            <Typography.Text ellipsis>{record.target_label ?? "全部"}</Typography.Text>
                        </Tooltip>
                    </div>
                ),
            },
            {
                title: "时间",
                key: "created_at",
                width: 150,
                render: (_, record) => formatTimestamp(record.created_at),
            },
            {
                title: "操作",
                key: "actions",
                width: 140,
                render: (_, record) => (
                    <Space size={8} wrap>
                        <Button size="small" icon={<EyeOutlined />} onClick={() => setSelectedTask(record)}>
                            详情
                        </Button>
                        <Button size="small" disabled={record.status === "running"} onClick={() => void handleRetryTask(record.task_id)}>
                            重试
                        </Button>
                    </Space>
                ),
            },
        ],
        [],
    );

    const selectedPolicySource = policySources[0] ?? policyShowcaseStatus?.source ?? null;
    const policyChunks = policyShowcaseStatus?.chunks ?? [];
    const policyRetrievalHits = policyShowcaseStatus?.retrieval_preview?.hits ?? [];

    useEffect(() => {
        void loadAdminWorkspace();
    }, []);

    async function fetchPolicyShowcase(sourceId: string): Promise<PolicyShowcaseStatus> {
        const status = await getPolicyShowcaseStatus(sourceId);
        const [chunks, retrievalPreview] = await Promise.all([
            listPolicyShowcaseChunks(sourceId),
            getPolicyShowcaseRetrievalPreview(sourceId, status.source.default_query, 5),
        ]);
        return {
            ...status,
            chunks,
            retrieval_preview: retrievalPreview,
        };
    }

    async function loadAdminWorkspace() {
        setLoading(true);
        setErrorMessage(null);
        try {
            const [nextUsers, nextFeedback, nextKnowledgeItems, nextTasks, nextStatus, nextPolicySources] = await Promise.all([
                listAdminUsers(),
                getAdminFeedbackOverview(),
                listAdminKnowledgeItems(),
                listAdminKnowledgeTasks(),
                getAdminSystemStatus(),
                listPolicyShowcaseSources(),
            ]);
            setUsers(nextUsers);
            setFeedbackOverview(nextFeedback);
            setKnowledgeItems(nextKnowledgeItems);
            setKnowledgeTasks(nextTasks);
            setSystemStatus(nextStatus);
            setPolicySources(nextPolicySources);
            if (nextPolicySources[0]) {
                setPolicyShowcaseStatus(await fetchPolicyShowcase(nextPolicySources[0].source_id));
            } else {
                setPolicyShowcaseStatus(null);
            }
        } catch (error) {
            setErrorMessage(extractDetailMessage(error) ?? "加载管理员工作台失败。");
        } finally {
            setLoading(false);
        }
    }

    async function handleUpdateUser(record: AdminUserSummary, role: "user" | "admin", isActive: boolean) {
        setUserSavingId(record.user_id);
        setErrorMessage(null);
        try {
            const updated = await updateAdminUser(record.user_id, {
                role,
                is_active: isActive,
            });
            setUsers((current) => current.map((item) => (item.user_id === updated.user_id ? updated : item)));
            message.success(`已更新用户「${updated.username}」。`);
            void refreshSystemStatus();
        } catch (error) {
            setErrorMessage(extractDetailMessage(error) ?? "更新用户失败。");
        } finally {
            setUserSavingId(null);
        }
    }

    async function handleResetPassword(userId: string) {
        setUserSavingId(userId);
        setErrorMessage(null);
        try {
            const result = await resetAdminUserPassword(userId);
            Modal.info({
                title: "临时密码",
                content: (
                    <Space direction="vertical" size={8}>
                        <Typography.Paragraph>密码已重置。该用户下次登录时必须修改密码。</Typography.Paragraph>
                        <Typography.Text code>{result.temporary_password}</Typography.Text>
                    </Space>
                ),
            });
            await refreshUsers();
        } catch (error) {
            setErrorMessage(extractDetailMessage(error) ?? "重置密码失败。");
        } finally {
            setUserSavingId(null);
        }
    }

    async function handleUpdateKnowledgeItem(
        record: KnowledgeItem,
        patch: Pick<KnowledgeItem, "is_enabled" | "session_attachable">,
    ) {
        setKnowledgeItemSavingId(record.knowledge_item_id);
        setErrorMessage(null);
        try {
            const updated = await updateAdminKnowledgeItem(record.knowledge_item_id, patch);
            setKnowledgeItems((current) =>
                current.map((item) =>
                    item.knowledge_item_id === record.knowledge_item_id
                        ? {
                              ...item,
                              is_enabled: updated.is_enabled,
                              session_attachable: updated.session_attachable,
                          }
                        : item,
                ),
            );
            message.success(`已更新知识条目「${record.title}」。`);
            void refreshSystemStatus();
        } catch (error) {
            setErrorMessage(extractDetailMessage(error) ?? "更新知识条目失败。");
        } finally {
            setKnowledgeItemSavingId(null);
        }
    }

    async function handleRetryTask(taskId: string) {
        setErrorMessage(null);
        try {
            const updated = await retryKnowledgeTask(taskId);
            setKnowledgeTasks((current) => [updated, ...current.filter((item) => item.task_id !== updated.task_id)]);
            message.success("任务重试已提交。");
            void refreshSystemStatus();
        } catch (error) {
            setErrorMessage(extractDetailMessage(error) ?? "重试任务失败。");
        }
    }

    async function handleTriggerKnowledgeRefresh(action: KnowledgeTaskRefreshAction) {
        setRefreshingKnowledge(action);
        setErrorMessage(null);
        try {
            const task = action === "rebuild" ? await triggerKnowledgeRebuild() : await triggerKnowledgeScan();
            setKnowledgeTasks((current) => [task, ...current.filter((item) => item.task_id !== task.task_id)]);
            message.success(`知识任务已提交：${taskTypeLabelMap[task.task_type] ?? task.task_type}。`);
            await loadAdminWorkspace();
        } catch (error) {
            setErrorMessage(extractDetailMessage(error) ?? "知识任务触发失败。");
        } finally {
            setRefreshingKnowledge(null);
        }
    }

    async function handleRefreshPolicyShowcase(sourceId: string) {
        setLoadingPolicySourceId(sourceId);
        setErrorMessage(null);
        try {
            setPolicyShowcaseStatus(await fetchPolicyShowcase(sourceId));
        } catch (error) {
            setErrorMessage(extractDetailMessage(error) ?? "刷新政策摄取状态失败。");
        } finally {
            setLoadingPolicySourceId(null);
        }
    }

    async function handleRunPolicyShowcase(sourceId: string) {
        setRunningPolicySourceId(sourceId);
        setErrorMessage(null);
        try {
            const status = await runPolicyShowcaseSource(sourceId);
            setPolicyShowcaseStatus(status);
            message.success("政策知识摄取已完成，公共政策检索索引已刷新。");
            await loadAdminWorkspace();
        } catch (error) {
            setErrorMessage(extractDetailMessage(error) ?? "运行政策知识摄取失败。");
        } finally {
            setRunningPolicySourceId(null);
        }
    }

    async function refreshUsers() {
        const nextUsers = await listAdminUsers();
        setUsers(nextUsers);
        await refreshSystemStatus();
    }

    async function refreshSystemStatus() {
        const nextStatus = await getAdminSystemStatus();
        setSystemStatus(nextStatus);
    }

    return (
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
            <Card>
                <Typography.Title level={2}>管理员控制台</Typography.Title>
                <Typography.Paragraph>
                    这里汇总用户、知识条目、更新任务、反馈和系统状态。管理员可以在这里查看知识库条目、触发扫描与重建，并管理用户与反馈概览。
                </Typography.Paragraph>
                <Space size={12} wrap>
                    <Button icon={<ReloadOutlined />} onClick={() => void loadAdminWorkspace()} disabled={loading}>
                        刷新
                    </Button>
                    <Button
                        icon={<SyncOutlined />}
                        loading={refreshingKnowledge === "scan"}
                        onClick={() => void handleTriggerKnowledgeRefresh("scan")}
                    >
                        扫描知识变动
                    </Button>
                    <Button
                        type="primary"
                        icon={<SyncOutlined />}
                        loading={refreshingKnowledge === "rebuild"}
                        onClick={() => void handleTriggerKnowledgeRefresh("rebuild")}
                    >
                        重建知识索引
                    </Button>
                </Space>
                {errorMessage ? (
                    <Alert
                        showIcon
                        type="warning"
                        message="管理员工作台提示"
                        description={errorMessage}
                        className="auth-card__alert"
                    />
                ) : null}
            </Card>

            {loading ? (
                <Card>
                    <div className="chat-workbench__loading">
                        <Spin size="large" />
                    </div>
                </Card>
            ) : (
                <div className="admin-grid">
                    <Card title="系统连接状态">
                        {systemStatus ? (
                            <Descriptions column={1} size="small" bordered>
                                <Descriptions.Item label="应用名称">{systemStatus.app_name}</Descriptions.Item>
                                <Descriptions.Item label="版本">{systemStatus.version}</Descriptions.Item>
                                <Descriptions.Item label="环境">{environmentLabelMap[systemStatus.env] ?? systemStatus.env}</Descriptions.Item>
                                <Descriptions.Item label="数据库">
                                    {databaseBackendLabelMap[systemStatus.database_backend] ?? systemStatus.database_backend}
                                </Descriptions.Item>
                                <Descriptions.Item label="模型">{systemStatus.model_name}</Descriptions.Item>
                                <Descriptions.Item label="模型服务模式">
                                    {providerModeLabelMap[systemStatus.model_provider_mode] ?? systemStatus.model_provider_mode}
                                </Descriptions.Item>
                                <Descriptions.Item label="用户数">{systemStatus.total_users}</Descriptions.Item>
                                <Descriptions.Item label="会话数">{systemStatus.total_sessions}</Descriptions.Item>
                                <Descriptions.Item label="报告数">{systemStatus.total_reports}</Descriptions.Item>
                                <Descriptions.Item label="反馈数">{systemStatus.total_feedback_entries}</Descriptions.Item>
                                <Descriptions.Item label="知识条目">
                                    {systemStatus.enabled_private_samples} / {systemStatus.total_private_samples}
                                </Descriptions.Item>
                                <Descriptions.Item label="最近刷新">
                                    {systemStatus.latest_refresh_status
                                        ? taskStatusLabelMap[systemStatus.latest_refresh_status]
                                        : "暂无"}
                                </Descriptions.Item>
                            </Descriptions>
                        ) : (
                            <Typography.Text type="secondary">暂无系统状态。</Typography.Text>
                        )}
                    </Card>

                    <Card title="反馈概览">
                        {feedbackOverview ? (
                            <Space direction="vertical" size={16} style={{ width: "100%" }}>
                                <div className="admin-stats">
                                    <Statistic title="总数" value={feedbackOverview.total_count} />
                                    <Statistic title="问答赞成" value={feedbackOverview.ask_up_count} />
                                    <Statistic title="问答反对" value={feedbackOverview.ask_down_count} />
                                    <Statistic title="核算赞成" value={feedbackOverview.calc_up_count} />
                                    <Statistic title="核算反对" value={feedbackOverview.calc_down_count} />
                                </div>
                                <List
                                    size="small"
                                    dataSource={feedbackOverview.recent_entries}
                                    locale={{ emptyText: "暂无反馈。" }}
                                    renderItem={(item) => (
                                        <List.Item>
                                            <Space direction="vertical" size={2} style={{ width: "100%" }}>
                                                <Space size={8} wrap>
                                                    <Tag>{feedbackTargetLabelMap[item.target_type] ?? item.target_type}</Tag>
                                                    <Tag color={item.rating === "up" ? "green" : "red"}>
                                                        {item.rating === "up" ? "正向" : "负向"}
                                                    </Tag>
                                                    <Typography.Text type="secondary">{item.owner_user_id ?? "匿名"}</Typography.Text>
                                                </Space>
                                                <Typography.Text type="secondary">{formatTimestamp(item.created_at)}</Typography.Text>
                                            </Space>
                                        </List.Item>
                                    )}
                                />
                            </Space>
                        ) : (
                            <Typography.Text type="secondary">暂无反馈汇总。</Typography.Text>
                        )}
                    </Card>

                    <Card
                        className="admin-grid__table-card admin-grid__wide-card"
                        title="政策知识三段式摄取"
                        extra={
                            <Tag color={policyShowcaseStatus?.indexed ? "green" : "orange"}>
                                {policyShowcaseStatus?.indexed ? "已入库可检索" : "待运行"}
                            </Tag>
                        }
                    >
                        <Space direction="vertical" size={12} style={{ width: "100%" }}>
                            <Alert
                                showIcon
                                type="info"
                                message="内置政策摄取展示链路"
                                description="该入口运行项目内置离线合成样例，走真实 crawl_ingest、policy_ingest、分块和 BM25 检索；样例会标记为演示来源，不作为官方政策依据引用，也不启用线上爬虫调度。"
                            />
                            {selectedPolicySource ? (
                                <>
                                    <Descriptions column={2} size="small" bordered>
                                        <Descriptions.Item label="展示源">
                                            {selectedPolicySource.title}
                                        </Descriptions.Item>
                                        <Descriptions.Item label="来源">
                                            {selectedPolicySource.source_label}
                                        </Descriptions.Item>
                                        <Descriptions.Item label="文号">
                                            {formatMetadataValue(selectedPolicySource.metadata.document_number)}
                                        </Descriptions.Item>
                                        <Descriptions.Item label="发布日期">
                                            {formatMetadataValue(selectedPolicySource.metadata.publication_date)}
                                        </Descriptions.Item>
                                        <Descriptions.Item label="原文链接" span={2}>
                                            {selectedPolicySource.source_url.startsWith("http") ? (
                                                <Typography.Link href={selectedPolicySource.source_url} target="_blank" rel="noreferrer">
                                                    {selectedPolicySource.source_url}
                                                </Typography.Link>
                                            ) : (
                                                <Typography.Text code>{selectedPolicySource.source_url}</Typography.Text>
                                            )}
                                        </Descriptions.Item>
                                        <Descriptions.Item label="默认检索问题" span={2}>
                                            {selectedPolicySource.default_query}
                                        </Descriptions.Item>
                                        <Descriptions.Item label="知识条目">
                                            {policyShowcaseStatus?.item?.knowledge_item_id ?? "尚未创建"}
                                        </Descriptions.Item>
                                        <Descriptions.Item label="最新任务">
                                            {policyShowcaseStatus?.latest_task
                                                ? taskStatusLabelMap[policyShowcaseStatus.latest_task.status] ??
                                                  policyShowcaseStatus.latest_task.status
                                                : "暂无任务"}
                                        </Descriptions.Item>
                                        <Descriptions.Item label="工作流">
                                            {policyShowcaseStatus?.workflow
                                                ? `${policyShowcaseStatus.workflow.workflow_type} / ${policyShowcaseStatus.workflow.status}`
                                                : "暂无工作流"}
                                        </Descriptions.Item>
                                        <Descriptions.Item label="分块数量">{policyChunks.length}</Descriptions.Item>
                                    </Descriptions>
                                    <Space size={8} wrap>
                                        <Button
                                            type="primary"
                                            icon={<DatabaseOutlined />}
                                            loading={runningPolicySourceId === selectedPolicySource.source_id}
                                            onClick={() => void handleRunPolicyShowcase(selectedPolicySource.source_id)}
                                        >
                                            运行/刷新摄取展示
                                        </Button>
                                        <Button
                                            icon={<ReloadOutlined />}
                                            loading={loadingPolicySourceId === selectedPolicySource.source_id}
                                            onClick={() => void handleRefreshPolicyShowcase(selectedPolicySource.source_id)}
                                        >
                                            刷新状态
                                        </Button>
                                        <Button href="/rag-lab">打开 RAG Lab 验证</Button>
                                    </Space>
                                    <List
                                        size="small"
                                        header={<Typography.Text strong>工作流节点</Typography.Text>}
                                        dataSource={policyShowcaseStatus?.workflow?.nodes ?? []}
                                        locale={{ emptyText: "尚未运行摄取工作流。" }}
                                        renderItem={(node) => (
                                            <List.Item>
                                                <Space size={8} wrap>
                                                    <Typography.Text code>{node.node_id}</Typography.Text>
                                                    <Tag color={taskStatusColorMap[node.status] ?? "default"}>{node.status}</Tag>
                                                    {node.error_message ? <Tag color="red">{node.error_message}</Tag> : null}
                                                </Space>
                                            </List.Item>
                                        )}
                                    />
                                    <List
                                        size="small"
                                        header={<Typography.Text strong>摄取分块</Typography.Text>}
                                        dataSource={policyChunks.slice(0, 3)}
                                        locale={{ emptyText: "暂无分块，点击运行摄取后生成。" }}
                                        renderItem={(chunk) => (
                                            <List.Item>
                                                <Space direction="vertical" size={4} style={{ width: "100%" }}>
                                                    <Space size={8} wrap>
                                                        <Typography.Text code>{chunk.chunk_id}</Typography.Text>
                                                        <Tag>{sourceTypeLabelMap[chunk.source_type] ?? chunk.source_type}</Tag>
                                                        {chunk.issued_at ? <Tag>{chunk.issued_at}</Tag> : null}
                                                    </Space>
                                                    <Typography.Paragraph ellipsis={{ rows: 2 }}>
                                                        {chunk.snippet}
                                                    </Typography.Paragraph>
                                                </Space>
                                            </List.Item>
                                        )}
                                    />
                                    <List
                                        size="small"
                                        header={
                                            <Typography.Text strong>
                                                检索预览：{policyShowcaseStatus?.retrieval_preview?.query ?? selectedPolicySource.default_query}
                                            </Typography.Text>
                                        }
                                        dataSource={policyRetrievalHits.slice(0, 5)}
                                        locale={{ emptyText: "暂无命中，运行摄取后可看到演示样例证据。" }}
                                        renderItem={(hit) => (
                                            <List.Item>
                                                <Space direction="vertical" size={4} style={{ width: "100%" }}>
                                                    <Space size={8} wrap>
                                                        <Tag color={hit.matched_source ? "green" : "default"}>
                                                            {hit.matched_source ? "本次展示源" : "公共政策"}
                                                        </Tag>
                                                        <Tag>{sourceTypeLabelMap[hit.source_type] ?? hit.source_type}</Tag>
                                                        <Typography.Text type="secondary">score {hit.score.toFixed(3)}</Typography.Text>
                                                    </Space>
                                                    <Typography.Text strong>{hit.title}</Typography.Text>
                                                    <Typography.Paragraph ellipsis={{ rows: 2 }}>
                                                        {hit.snippet}
                                                    </Typography.Paragraph>
                                                </Space>
                                            </List.Item>
                                        )}
                                    />
                                </>
                            ) : (
                                <Empty description="暂无可用政策源。" />
                            )}
                        </Space>
                    </Card>

                    <Card
                        className="admin-grid__table-card"
                        title="知识条目 / 文档列表"
                        extra={
                            <Tag color="blue">
                                {knowledgeItems.length} 个条目
                            </Tag>
                        }
                    >
                        <Table
                            rowKey="knowledge_item_id"
                            columns={knowledgeColumns}
                            dataSource={knowledgeItems}
                            pagination={{ pageSize: 6 }}
                            scroll={{ y: 420, x: 980 }}
                            tableLayout="fixed"
                            size="small"
                            locale={{ emptyText: <Empty description="暂无知识条目。" /> }}
                        />
                    </Card>

                    <Card
                        className="admin-grid__table-card"
                        title="更新任务列表"
                        extra={<Tag color="purple">{knowledgeTasks.length} 条任务</Tag>}
                    >
                        <Typography.Paragraph type="secondary" className="admin-grid__table-hint">
                            任务列表固定高度显示，长摘要会折叠。点击“详情”可在弹窗中查看完整任务信息。
                        </Typography.Paragraph>
                        <Table
                            rowKey="task_id"
                            columns={taskColumns}
                            dataSource={knowledgeTasks}
                            pagination={{ pageSize: 6, showSizeChanger: false }}
                            scroll={{ y: 420, x: 1180 }}
                            tableLayout="fixed"
                            size="small"
                            locale={{ emptyText: <Empty description="暂无知识任务。" /> }}
                        />
                    </Card>

                    <Card className="admin-grid__table-card" title="用户列表">
                        <Table
                            rowKey="user_id"
                            columns={userColumns}
                            dataSource={users}
                            pagination={{ pageSize: 8, showSizeChanger: false }}
                            scroll={{ y: 420, x: 980 }}
                            tableLayout="fixed"
                            size="small"
                        />
                    </Card>
                </div>
            )}

            <Modal
                title="知识任务详情"
                open={selectedTask !== null}
                onCancel={() => setSelectedTask(null)}
                footer={[
                    <Button key="close" onClick={() => setSelectedTask(null)}>
                        关闭
                    </Button>,
                ]}
                width={760}
            >
                {selectedTask ? (
                    <div className="admin-task-detail">
                        <Descriptions column={2} size="small" bordered>
                            <Descriptions.Item label="任务编号" span={2}>
                                <Typography.Text code>{selectedTask.task_id}</Typography.Text>
                            </Descriptions.Item>
                            <Descriptions.Item label="动作">
                                {taskTypeLabelMap[selectedTask.task_type] ?? selectedTask.task_type}
                            </Descriptions.Item>
                            <Descriptions.Item label="状态">
                                <Tag color={taskStatusColorMap[selectedTask.status]}>
                                    {taskStatusLabelMap[selectedTask.status]}
                                </Tag>
                            </Descriptions.Item>
                            <Descriptions.Item label="范围">
                                {taskScopeLabelMap[selectedTask.scope] ?? selectedTask.scope}
                            </Descriptions.Item>
                            <Descriptions.Item label="创建时间">
                                {formatTimestamp(selectedTask.created_at)}
                            </Descriptions.Item>
                            <Descriptions.Item label="开始时间">
                                {selectedTask.started_at ? formatTimestamp(selectedTask.started_at) : "暂无"}
                            </Descriptions.Item>
                            <Descriptions.Item label="完成时间">
                                {selectedTask.finished_at ? formatTimestamp(selectedTask.finished_at) : "暂无"}
                            </Descriptions.Item>
                            <Descriptions.Item label="目标对象" span={2}>
                                {selectedTask.target_label ?? "全部"}
                            </Descriptions.Item>
                        </Descriptions>
                        <div className="admin-task-detail__section">
                            <Typography.Text strong>任务摘要</Typography.Text>
                            <div className="admin-task-detail__content">
                                <Typography.Paragraph>
                                    {selectedTask.summary ?? "暂无摘要。"}
                                </Typography.Paragraph>
                            </div>
                        </div>
                        <div className="admin-task-detail__section">
                            <Typography.Text strong>最近错误</Typography.Text>
                            <div className="admin-task-detail__content">
                                <Typography.Paragraph type="secondary">
                                    {selectedTask.last_error ?? "暂无错误信息。"}
                                </Typography.Paragraph>
                            </div>
                        </div>
                    </div>
                ) : null}
            </Modal>
        </Space>
    );
}

const statusLabelMap: Record<string, string> = {
    pending: "待处理",
    running: "处理中",
    succeeded: "已完成",
    failed: "失败",
    ready: "已就绪",
};

const statusColorMap: Record<string, string> = {
    pending: "default",
    running: "processing",
    succeeded: "green",
    failed: "red",
    ready: "blue",
};

const roleLabelMap = {
    user: "普通用户",
    admin: "管理员",
} as const;

const libraryScopeLabelMap = {
    personal: "个人知识",
    shared: "共享知识",
} as const;

const sourceTypeLabelMap: Record<string, string> = {
    uploaded_file: "上传文件",
    private_sample_repo: "共享知识条目",
    knowledge_item: "知识条目",
    public_policy_web: "官方政策网页",
    public_policy: "公共政策",
    public_policy_demo: "演示样例",
    private_sample: "私有知识",
    private_upload: "个人上传",
};

const taskTypeLabelMap: Record<string, string> = {
    upload_ingest: "上传入库",
    rebuild: "重建索引",
    rescan: "扫描变动",
    retry: "重试任务",
    crawl_ingest: "政策采集入库",
    crawl_refresh: "政策采集刷新",
};

const taskStatusLabelMap: Record<string, string> = {
    queued: "排队中",
    running: "运行中",
    succeeded: "已完成",
    failed: "失败",
};

const taskStatusColorMap: Record<string, string> = {
    queued: "default",
    running: "processing",
    succeeded: "green",
    completed: "green",
    skipped: "default",
    failed: "red",
};

const taskScopeLabelMap: Record<string, string> = {
    public_policy: "公共政策",
    private_sample: "私有知识",
    all: "全部范围",
};

const feedbackTargetLabelMap: Record<string, string> = {
    ask: "问答反馈",
    calc_carbon: "核算反馈",
    report: "报告反馈",
};

const environmentLabelMap: Record<string, string> = {
    development: "本地开发环境",
    production: "生产环境",
    staging: "预发布环境",
};

const databaseBackendLabelMap: Record<string, string> = {
    sqlite: "本地数据库",
    postgresql: "生产数据库",
};

const providerModeLabelMap: Record<string, string> = {
    openai_compatible: "兼容模式",
    stub: "模拟模式",
};

function formatTimestamp(value: string) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return value || "暂无";
    }
    return date.toLocaleString("zh-CN", {
        hour12: false,
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
    });
}

function formatMetadataValue(value: unknown) {
    if (typeof value === "string" && value.trim()) {
        return value;
    }
    if (typeof value === "number" || typeof value === "boolean") {
        return String(value);
    }
    return "暂无";
}

function extractDetailMessage(value: unknown): string | null {
    if (!value || typeof value !== "object") {
        return null;
    }
    const candidate = value as { detail?: unknown };
    return typeof candidate.detail === "string" ? candidate.detail : null;
}
