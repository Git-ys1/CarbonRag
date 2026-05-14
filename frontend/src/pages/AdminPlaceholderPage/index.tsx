import {
    CloudServerOutlined,
    DatabaseOutlined,
    EyeOutlined,
    MessageOutlined,
    ReloadOutlined,
    SyncOutlined,
    TeamOutlined,
} from "@ant-design/icons";
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
    Tabs,
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
    getPolicyCrawlerStatus,
    getPolicyShowcaseRetrievalPreview,
    getPolicyShowcaseStatus,
    listAdminUsers,
    listPolicyCrawlerCandidates,
    listPolicyCrawlerRuns,
    listPolicyCrawlerSources,
    listPolicyShowcaseChunks,
    listPolicyShowcaseSources,
    publishPolicyCrawlerCandidate,
    rejectPolicyCrawlerCandidate,
    resetAdminUserPassword,
    runPolicyCrawlerSource,
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
    PolicyCrawlerCandidateSummary,
    PolicyCrawlerRunSummary,
    PolicyCrawlerSourceSummary,
    PolicyCrawlerStatusSummary,
    PolicyShowcaseSourceSummary,
    PolicyShowcaseStatus,
} from "../../types/admin";
import type { KnowledgeItem, KnowledgeTask } from "../../types/knowledge";

type KnowledgeTaskRefreshAction = "scan" | "rebuild" | null;

const approvedPolicyCrawlerSources: PolicyCrawlerSourceSummary[] = [
    {
        source_id: "gov-cn-policy-library",
        title: "中国政府网：2030年前碳达峰行动方案",
        source_url: "https://www.gov.cn/zhengce/content/2021-10/26/content_5644984.htm",
        source_label: "中国政府网",
        allowed_domain: "gov.cn",
        is_enabled: true,
        schedule_interval_seconds: null,
        last_run_id: null,
        last_run_status: null,
        last_run_at: null,
        next_run_at: null,
        last_error: null,
        metadata: { scope: "national_policy", topic: "carbon_peak" },
    },
    {
        source_id: "ndrc-policy-releases",
        title: "国家发展改革委政策发布",
        source_url: "https://www.ndrc.gov.cn/xxgk/zcfb/",
        source_label: "国家发展改革委",
        allowed_domain: "ndrc.gov.cn",
        is_enabled: true,
        schedule_interval_seconds: null,
        last_run_id: null,
        last_run_status: null,
        last_run_at: null,
        next_run_at: null,
        last_error: null,
        metadata: { scope: "national_policy" },
    },
    {
        source_id: "mee-policy-releases",
        title: "生态环境部政策公开",
        source_url: "https://www.mee.gov.cn/xxgklssj/",
        source_label: "生态环境部",
        allowed_domain: "mee.gov.cn",
        is_enabled: true,
        schedule_interval_seconds: null,
        last_run_id: null,
        last_run_status: null,
        last_run_at: null,
        next_run_at: null,
        last_error: null,
        metadata: { scope: "environment_policy" },
    },
    {
        source_id: "miit-policy-releases",
        title: "工业和信息化部政策文件",
        source_url: "https://www.miit.gov.cn/zwgk/zcwj/",
        source_label: "工业和信息化部",
        allowed_domain: "miit.gov.cn",
        is_enabled: true,
        schedule_interval_seconds: null,
        last_run_id: null,
        last_run_status: null,
        last_run_at: null,
        next_run_at: null,
        last_error: null,
        metadata: { scope: "industry_policy" },
    },
    {
        source_id: "beijing-policy-library",
        title: "北京市政策文件",
        source_url: "https://www.beijing.gov.cn/zhengce/",
        source_label: "北京市人民政府",
        allowed_domain: "beijing.gov.cn",
        is_enabled: true,
        schedule_interval_seconds: null,
        last_run_id: null,
        last_run_status: null,
        last_run_at: null,
        next_run_at: null,
        last_error: null,
        metadata: { scope: "local_policy", region: "北京" },
    },
    {
        source_id: "beijing-fgw-policy",
        title: "北京市发展改革委政策文件",
        source_url: "https://fgw.beijing.gov.cn/fgwzwgk/2024zcwj/",
        source_label: "北京市发展和改革委员会",
        allowed_domain: "fgw.beijing.gov.cn",
        is_enabled: true,
        schedule_interval_seconds: null,
        last_run_id: null,
        last_run_status: null,
        last_run_at: null,
        next_run_at: null,
        last_error: null,
        metadata: { scope: "local_policy", region: "北京" },
    },
];

const normalizedApprovedPolicyCrawlerSources: PolicyCrawlerSourceSummary[] = approvedPolicyCrawlerSources.map((source) => {
    const normalized: Record<string, Partial<PolicyCrawlerSourceSummary>> = {
        "gov-cn-policy-library": {
            title: "中国政府网政策文件库",
            source_url: "https://www.gov.cn/zhengce/",
            source_label: "中国政府网",
            metadata: { scope: "national_policy", discovery_mode: "official_policy_search" },
        },
        "ndrc-policy-releases": {
            title: "国家发展改革委碳达峰碳中和",
            source_url: "https://www.ndrc.gov.cn/fggz/hjyzy/tdftzh/",
            source_label: "国家发展改革委",
            metadata: { scope: "national_policy", discovery_mode: "policy_listing" },
        },
        "mee-policy-releases": {
            title: "生态环境部应对气候变化",
            source_url: "https://www.mee.gov.cn/ywgz/ydqhbh/",
            source_label: "生态环境部",
            metadata: { scope: "environment_policy", discovery_mode: "policy_listing" },
        },
        "miit-policy-releases": {
            title: "工业和信息化部政策文件",
            source_url: "https://www.miit.gov.cn/search/wjfb.html?websiteid=110000000000000&pg=&p=&tpl=14&category=51&q=%E8%8A%82%E8%83%BD%E9%99%8D%E7%A2%B3",
            source_label: "工业和信息化部",
            metadata: { scope: "industry_policy", discovery_mode: "official_policy_search" },
        },
        "beijing-policy-library": {
            title: "北京市政策文件入口",
            source_url: "https://www.beijing.gov.cn/zhengce/",
            source_label: "北京市人民政府",
            metadata: { scope: "local_policy", region: "北京", discovery_mode: "policy_listing" },
        },
        "beijing-fgw-policy": {
            title: "北京市发展改革委政策文件入口",
            source_url: "https://fgw.beijing.gov.cn/fgwzwgk/2024zcwj/",
            source_label: "北京市发展和改革委员会",
            metadata: { scope: "local_policy", region: "北京", discovery_mode: "policy_listing" },
        },
    };
    return {
        ...source,
        ...(normalized[source.source_id] ?? {}),
        metadata: {
            ...source.metadata,
            ...(normalized[source.source_id]?.metadata ?? {}),
        },
    };
});

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
    const [policyCrawlerStatus, setPolicyCrawlerStatus] = useState<PolicyCrawlerStatusSummary | null>(null);
    const [policyCrawlerSources, setPolicyCrawlerSources] = useState<PolicyCrawlerSourceSummary[]>([]);
    const [policyCrawlerRuns, setPolicyCrawlerRuns] = useState<PolicyCrawlerRunSummary[]>([]);
    const [policyCrawlerCandidates, setPolicyCrawlerCandidates] = useState<PolicyCrawlerCandidateSummary[]>([]);
    const [userSavingId, setUserSavingId] = useState<string | null>(null);
    const [knowledgeItemSavingId, setKnowledgeItemSavingId] = useState<string | null>(null);
    const [refreshingKnowledge, setRefreshingKnowledge] = useState<KnowledgeTaskRefreshAction>(null);
    const [runningPolicySourceId, setRunningPolicySourceId] = useState<string | null>(null);
    const [loadingPolicySourceId, setLoadingPolicySourceId] = useState<string | null>(null);
    const [runningCrawlerSourceId, setRunningCrawlerSourceId] = useState<string | null>(null);
    const [reviewingCandidateId, setReviewingCandidateId] = useState<string | null>(null);
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
    const policyCrawlerBackendLabel = formatCrawlerBackend(policyCrawlerStatus?.crawler_backend);
    const policyCrawlerSourcesForDisplay = useMemo(() => {
        const sourceById = new Map(policyCrawlerSources.map((source) => [source.source_id, source]));
        return normalizedApprovedPolicyCrawlerSources.map((fallback) => {
            const current = sourceById.get(fallback.source_id);
            if (!current) {
                return fallback;
            }
            return {
                ...fallback,
                ...current,
                metadata: {
                    ...fallback.metadata,
                    ...current.metadata,
                },
            };
        });
    }, [policyCrawlerSources]);
    const approvedCrawlerDomains = useMemo(
        () =>
            Array.from(
                new Set(
                    [
                        ...(Array.isArray(policyCrawlerStatus?.safe_limits.allowed_domains)
                            ? policyCrawlerStatus.safe_limits.allowed_domains.map(String)
                            : []),
                        ...normalizedApprovedPolicyCrawlerSources.map((source) => source.allowed_domain),
                    ].filter(Boolean),
                ),
            ),
        [policyCrawlerStatus],
    );

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

    async function fetchPolicyCrawlerWorkspace() {
        const [status, sources, runs, candidates] = await Promise.all([
            getPolicyCrawlerStatus(),
            listPolicyCrawlerSources(),
            listPolicyCrawlerRuns(undefined, 10),
            listPolicyCrawlerCandidates(undefined, undefined, 20),
        ]);
        setPolicyCrawlerStatus(status);
        setPolicyCrawlerSources(sources);
        setPolicyCrawlerRuns(runs);
        setPolicyCrawlerCandidates(candidates);
    }

    async function loadAdminWorkspace() {
        setLoading(true);
        setErrorMessage(null);
        try {
            const [
                nextUsers,
                nextFeedback,
                nextKnowledgeItems,
                nextTasks,
                nextStatus,
                nextPolicySources,
                nextCrawlerStatus,
                nextCrawlerSources,
                nextCrawlerRuns,
                nextCrawlerCandidates,
            ] = await Promise.all([
                listAdminUsers(),
                getAdminFeedbackOverview(),
                listAdminKnowledgeItems(),
                listAdminKnowledgeTasks(),
                getAdminSystemStatus(),
                listPolicyShowcaseSources(),
                getPolicyCrawlerStatus(),
                listPolicyCrawlerSources(),
                listPolicyCrawlerRuns(undefined, 10),
                listPolicyCrawlerCandidates(undefined, undefined, 20),
            ]);
            setUsers(nextUsers);
            setFeedbackOverview(nextFeedback);
            setKnowledgeItems(nextKnowledgeItems);
            setKnowledgeTasks(nextTasks);
            setSystemStatus(nextStatus);
            setPolicySources(nextPolicySources);
            setPolicyCrawlerStatus(nextCrawlerStatus);
            setPolicyCrawlerSources(nextCrawlerSources);
            setPolicyCrawlerRuns(nextCrawlerRuns);
            setPolicyCrawlerCandidates(nextCrawlerCandidates);
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

    async function handleRunPolicyCrawler(sourceId: string) {
        setRunningCrawlerSourceId(sourceId);
        setErrorMessage(null);
        try {
            const run = await runPolicyCrawlerSource(sourceId);
            if (run.status === "succeeded") {
                if (run.candidate_count > 0) {
                    const indexedCount =
                        typeof run.metadata.auto_indexed_count === "number" ? run.metadata.auto_indexed_count : run.candidate_count;
                    message.success(`真实 Scrapy 抓取完成，新增/刷新 ${run.candidate_count} 条政策记录，已索引 ${indexedCount} 条。`);
                } else {
                    message.warning("真实 Scrapy 已运行，但本次没有匹配到双碳政策或技术标准。请查看运行记录和主题过滤数量。");
                }
            } else {
                setErrorMessage(run.error_detail ?? `实时政策爬虫运行结束，状态：${crawlerRunStatusLabelMap[run.status] ?? run.status}`);
            }
            await fetchPolicyCrawlerWorkspace();
        } catch (error) {
            setErrorMessage(extractDetailMessage(error) ?? "运行实时政策爬虫失败。");
        } finally {
            setRunningCrawlerSourceId(null);
        }
    }

    async function handlePublishPolicyCandidate(candidateId: string) {
        setReviewingCandidateId(candidateId);
        setErrorMessage(null);
        try {
            await publishPolicyCrawlerCandidate(candidateId);
            message.success("候选政策已发布，已进入 crawl_ingest 队列。");
            await Promise.all([fetchPolicyCrawlerWorkspace(), loadKnowledgeWorkspace()]);
        } catch (error) {
            setErrorMessage(extractDetailMessage(error) ?? "发布候选政策失败。");
        } finally {
            setReviewingCandidateId(null);
        }
    }

    async function handleRejectPolicyCandidate(candidateId: string) {
        setReviewingCandidateId(candidateId);
        setErrorMessage(null);
        try {
            await rejectPolicyCrawlerCandidate(candidateId);
            message.success("候选政策已拒绝，不会进入检索。");
            await fetchPolicyCrawlerWorkspace();
        } catch (error) {
            setErrorMessage(extractDetailMessage(error) ?? "拒绝候选政策失败。");
        } finally {
            setReviewingCandidateId(null);
        }
    }

    async function loadKnowledgeWorkspace() {
        const [nextKnowledgeItems, nextTasks] = await Promise.all([listAdminKnowledgeItems(), listAdminKnowledgeTasks()]);
        setKnowledgeItems(nextKnowledgeItems);
        setKnowledgeTasks(nextTasks);
        await refreshSystemStatus();
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
        <Space className="admin-console" direction="vertical" size={18}>
            <Card className="admin-console__hero">
                <div className="admin-console__hero-layout">
                    <div className="admin-console__hero-copy">
                        <Typography.Text className="admin-console__eyebrow">CarbonRag 管理后台</Typography.Text>
                        <Typography.Title level={2}>系统治理总览</Typography.Title>
                        <Typography.Paragraph>
                            集中查看用户、知识库任务、反馈和系统连接状态；高风险操作保留在对应卡片内处理。
                        </Typography.Paragraph>
                    </div>
                    <Space className="admin-console__actions" size={10} wrap>
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
                </div>
                {errorMessage ? (
                    <Alert
                        showIcon
                        type="warning"
                        message="管理员工作台提示"
                        description={errorMessage}
                        className="admin-console__alert"
                    />
                ) : null}
            </Card>

            {loading ? (
                <Card className="admin-console__loading-card">
                    <div className="chat-workbench__loading">
                        <Spin size="large" />
                    </div>
                </Card>
            ) : (
                <>
                <div className="admin-console__summary">
                    <Card className="admin-summary-card">
                        <div className="admin-summary-card__icon">
                            <TeamOutlined />
                        </div>
                        <Statistic title="用户" value={systemStatus?.total_users ?? users.length} />
                        <Typography.Text type="secondary">{users.filter((item) => item.is_active).length} 个启用账号</Typography.Text>
                    </Card>
                    <Card className="admin-summary-card">
                        <div className="admin-summary-card__icon">
                            <DatabaseOutlined />
                        </div>
                        <Statistic title="知识条目" value={knowledgeItems.length} />
                        <Typography.Text type="secondary">{knowledgeTasks.length} 条知识任务</Typography.Text>
                    </Card>
                    <Card className="admin-summary-card">
                        <div className="admin-summary-card__icon">
                            <MessageOutlined />
                        </div>
                        <Statistic title="反馈" value={feedbackOverview?.total_count ?? 0} />
                        <Typography.Text type="secondary">问答 / 核算反馈汇总</Typography.Text>
                    </Card>
                    <Card className="admin-summary-card">
                        <div className="admin-summary-card__icon">
                            <CloudServerOutlined />
                        </div>
                        <Statistic title="运行环境" value={environmentLabelMap[systemStatus?.env ?? ""] ?? "未知"} />
                        <Typography.Text type="secondary">
                            {databaseBackendLabelMap[systemStatus?.database_backend ?? ""] ?? "数据库状态待确认"}
                        </Typography.Text>
                    </Card>
                </div>

                <Tabs
                    className="admin-console__tabs"
                    defaultActiveKey="overview"
                    items={[
                        {
                            key: "overview",
                            label: "系统概览",
                            children: (
                                <div className="admin-grid admin-grid--tab">
                    <Card className="admin-panel-card" title="系统连接状态">
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

                    <Card className="admin-panel-card" title="反馈概览">
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

                                </div>
                            ),
                        },
                        {
                            key: "policy",
                            label: "政策摄取",
                            children: (
                                <div className="admin-grid admin-grid--tab">
                    <Card
                        className="admin-panel-card admin-grid__table-card admin-grid__wide-card"
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

                                </div>
                            ),
                        },
                        {
                            key: "crawler",
                            label: "实时爬虫",
                            children: (
                                <div className="admin-grid admin-grid--tab">
                    <Card
                        className="admin-panel-card admin-grid__table-card admin-grid__wide-card"
                        title="实时政策爬虫"
                        extra={
                            <Space size={8} wrap>
                                <Tag color={policyCrawlerStatus?.crawler_backend === "scrapyd" ? "purple" : "blue"}>
                                    {policyCrawlerBackendLabel}
                                </Tag>
                                <Tag color={policyCrawlerStatus?.provider_available ? "green" : "orange"}>
                                    {policyCrawlerStatus?.provider_available ? "Scrapy 真实可用" : "Scrapy 当前不可用"}
                                </Tag>
                                <Tag color={policyCrawlerStatus?.scheduled_enabled ? "blue" : "default"}>
                                    {policyCrawlerStatus?.scheduled_enabled ? "自动更新已启用" : "仅手动触发"}
                                </Tag>
                            </Space>
                        }
                    >
                        <Space direction="vertical" size={12} style={{ width: "100%" }}>
                            <Alert
                                showIcon
                                type="warning"
                                message="官方白名单自动更新知识库"
                                description="实时政策爬虫只访问 gov.cn、ndrc.gov.cn、mee.gov.cn、miit.gov.cn、fgw.beijing.gov.cn、beijing.gov.cn 六类官方白名单域名；抓取到的双碳政策和技术标准会自动创建或刷新 public_policy_web，并立即进入解析、入库和索引链路。"
                            />
                            <Alert
                                showIcon
                                type={policyCrawlerStatus?.provider_available ? "success" : "info"}
                                message={
                                    policyCrawlerStatus?.provider_available
                                        ? "当前后端已能导入 Scrapy，可以执行真实官方源抓取"
                                        : "当前后端 Python 环境还不能导入 Scrapy"
                                }
                                description={
                                    policyCrawlerStatus?.provider_available
                                        ? "点击下方任一官方源的“抓取并自动入库”会真实访问该白名单站点，页面会展示抓到的政策文件、匹配关键词、解析入库与索引结果。"
                                        : `请确认正在运行的后端使用 backend/.venv，并执行 ${String(
                                                  policyCrawlerStatus?.safe_limits.scrapy_install_command ??
                                                  "backend\\.venv\\Scripts\\python.exe -m pip install scrapy==2.15.2",
                                          )} 后重启后端服务。`
                                }
                            />
                            {policyCrawlerStatus ? (
                                <>
                                    <Descriptions column={2} size="small" bordered>
                                    <Descriptions.Item label="Provider">
                                        {policyCrawlerStatus.provider_name} / {policyCrawlerStatus.provider_mode}
                                    </Descriptions.Item>
                                    <Descriptions.Item label="Backend">
                                        <Space size={8} wrap>
                                            <Tag color={policyCrawlerStatus.crawler_backend === "scrapyd" ? "purple" : "blue"}>
                                                {formatCrawlerBackend(policyCrawlerStatus.crawler_backend)}
                                            </Tag>
                                            {policyCrawlerStatus.external_job_id ? (
                                                <Typography.Text code>{policyCrawlerStatus.external_job_id}</Typography.Text>
                                            ) : null}
                                        </Space>
                                    </Descriptions.Item>
                                    <Descriptions.Item label="Local Scrapy">
                                        <Tag color={availabilityColor(policyCrawlerStatus.local_scrapy_available)}>
                                            {availabilityLabel(policyCrawlerStatus.local_scrapy_available)}
                                        </Tag>
                                    </Descriptions.Item>
                                    <Descriptions.Item label="Scrapyd">
                                        <Space size={8} wrap>
                                            <Tag color={availabilityColor(policyCrawlerStatus.scrapyd_available)}>
                                                {availabilityLabel(policyCrawlerStatus.scrapyd_available)}
                                            </Tag>
                                            {policyCrawlerStatus.scrapyd_endpoint_label ? (
                                                <Typography.Text code>{policyCrawlerStatus.scrapyd_endpoint_label}</Typography.Text>
                                            ) : null}
                                        </Space>
                                    </Descriptions.Item>
                                    <Descriptions.Item label="Provider 状态">
                                        <Space size={8} wrap>
                                            <Tag color={policyCrawlerStatus.provider_enabled ? "green" : "default"}>
                                                {policyCrawlerStatus.provider_enabled ? "已启用" : "未启用"}
                                            </Tag>
                                            <Tag color={policyCrawlerStatus.provider_available ? "green" : "orange"}>
                                                {policyCrawlerStatus.provider_available ? "可用" : "不可用"}
                                            </Tag>
                                        </Space>
                                    </Descriptions.Item>
                                    <Descriptions.Item label="待处理记录">
                                        {policyCrawlerStatus.pending_candidate_count}
                                    </Descriptions.Item>
                                    <Descriptions.Item label="最近运行">
                                        {policyCrawlerStatus.recent_run_status
                                            ? crawlerRunStatusLabelMap[policyCrawlerStatus.recent_run_status] ??
                                              policyCrawlerStatus.recent_run_status
                                            : "暂无"}
                                    </Descriptions.Item>
                                    <Descriptions.Item label="安全限制" span={2}>
                                        robots={String(policyCrawlerStatus.safe_limits.obey_robots ?? true)}, depth=
                                        {formatMetadataValue(policyCrawlerStatus.safe_limits.max_depth)}, pages=
                                        {formatMetadataValue(policyCrawlerStatus.safe_limits.max_pages)}, delay=
                                        {formatMetadataValue(policyCrawlerStatus.safe_limits.download_delay_seconds)}s,
                                        concurrency=
                                        {formatMetadataValue(policyCrawlerStatus.safe_limits.concurrent_requests_per_domain)}
                                    </Descriptions.Item>
                                    <Descriptions.Item label="官方白名单" span={2}>
                                        <Space size={6} wrap>
                                            {approvedCrawlerDomains.map((domain) => (
                                                <Tag key={domain} color="blue">
                                                    {domain}
                                                </Tag>
                                            ))}
                                        </Space>
                                    </Descriptions.Item>
                                    </Descriptions>
                                    {!policyCrawlerStatus.provider_available ? (
                                        <Alert
                                            showIcon
                                            type="info"
                                            message="Scrapy 未安装或当前后端环境不可用"
                                            description="Admin 仍会展示官方源和手动抓取入口；安装 scrapy 后，手动抓取会真正访问官方白名单源。未安装时点击会记录 unavailable 运行结果，不会影响 /ask。"
                                        />
                                    ) : null}
                                    {policyCrawlerStatus.provider_error ? (
                                        <Alert
                                            showIcon
                                            type="warning"
                                            message={`${formatCrawlerBackend(policyCrawlerStatus.crawler_backend)} backend detail`}
                                            description={policyCrawlerStatus.provider_error}
                                        />
                                    ) : null}
                                </>
                            ) : (
                                <Typography.Text type="secondary">暂无爬虫状态。</Typography.Text>
                            )}

                            <div className="admin-crawler-source-grid">
                                {policyCrawlerSourcesForDisplay.map((source) => {
                                    const sourceRuns = policyCrawlerRuns.filter((run) => run.source_id === source.source_id);
                                    const sourceCandidates = policyCrawlerCandidates.filter(
                                        (candidate) => candidate.source_id === source.source_id,
                                    );
                                    const latestRun = sourceRuns[0];
                                    const disabledReason = !source.is_enabled
                                        ? "该源已停用"
                                        : policyCrawlerStatus?.manual_enabled === false
                                          ? "手动触发已关闭"
                                          : policyCrawlerStatus?.running
                                            ? "已有爬虫运行中"
                                            : null;
                                    return (
                                        <Card
                                            key={source.source_id}
                                            size="small"
                                            className="admin-crawler-source-card"
                                            title={
                                                <Space size={8} wrap>
                                                    <Typography.Text strong>{source.title}</Typography.Text>
                                                    <Tag color="blue">{source.allowed_domain}</Tag>
                                                </Space>
                                            }
                                            extra={
                                                <Tag color={source.is_enabled ? "green" : "default"}>
                                                    {source.is_enabled ? "启用" : "停用"}
                                                </Tag>
                                            }
                                        >
                                            <Space direction="vertical" size={8} style={{ width: "100%" }}>
                                                <Typography.Text type="secondary">{source.source_label}</Typography.Text>
                                                <Typography.Link href={source.source_url} target="_blank" rel="noreferrer">
                                                    {source.source_url}
                                                </Typography.Link>
                                                <Space size={8} wrap>
                                                    <Tag color={crawlerRunStatusColorMap[source.last_run_status ?? latestRun?.status ?? ""] ?? "default"}>
                                                        {source.last_run_status || latestRun?.status
                                                            ? crawlerRunStatusLabelMap[source.last_run_status ?? latestRun?.status ?? ""] ??
                                                              source.last_run_status ??
                                                              latestRun?.status
                                                            : "尚未抓取"}
                                                    </Tag>
                                                    <Tag>{sourceCandidates.length} 条入库记录</Tag>
                                                    {latestRun ? <Tag>{latestRun.document_count} 个文档</Tag> : null}
                                                </Space>
                                                {source.last_error || latestRun?.error_detail ? (
                                                    <Typography.Paragraph type="danger" ellipsis={{ rows: 2 }}>
                                                        {source.last_error ?? latestRun?.error_detail}
                                                    </Typography.Paragraph>
                                                ) : (
                                                    <Typography.Text type="secondary">
                                                        点击后会真实访问该官方白名单源，匹配双碳政策/技术标准后自动进入知识库。
                                                    </Typography.Text>
                                                )}
                                                <Space size={8} wrap>
                                                    <Tooltip title={disabledReason ?? "真实运行 Scrapy，并遵守 robots、限速、深度和页数限制；命中的政策文件会自动入库索引。"}>
                                                        <Button
                                                            type="primary"
                                                            icon={<ReloadOutlined />}
                                                            disabled={Boolean(disabledReason)}
                                                            loading={runningCrawlerSourceId === source.source_id}
                                                            onClick={() => void handleRunPolicyCrawler(source.source_id)}
                                                        >
                                                            抓取并自动入库
                                                        </Button>
                                                    </Tooltip>
                                                    <Button icon={<SyncOutlined />} onClick={() => void fetchPolicyCrawlerWorkspace()}>
                                                        刷新
                                                    </Button>
                                                </Space>
                                            </Space>
                                        </Card>
                                    );
                                })}
                            </div>

                            <List
                                className="admin-compact-list"
                                size="small"
                                header={<Typography.Text strong>自动入库记录</Typography.Text>}
                                dataSource={policyCrawlerCandidates.slice(0, 8)}
                                locale={{ emptyText: "暂无记录。抓取成功后会显示政策文件、来源、摘要、匹配关键词和索引结果。" }}
                                renderItem={(candidate) => {
                                    const matchedKeywords = metadataStringList(candidate.metadata.matched_policy_keywords);
                                    return (
                                    <List.Item>
                                        <Space direction="vertical" size={6} style={{ width: "100%" }}>
                                            <Space size={8} wrap>
                                                <Typography.Text strong>{candidateDisplayTitle(candidate)}</Typography.Text>
                                                {candidate.title && isGenericPolicyCrawlerTitle(candidate.title) ? (
                                                    <Tag color="orange">标题需复核</Tag>
                                                ) : null}
                                                <Tag color={candidateStatusColorMap[candidate.status]}>
                                                    {candidateStatusLabelMap[candidate.status] ?? candidate.status}
                                                </Tag>
                                                <Tag>{candidate.content_type}</Tag>
                                                {candidateQualityTags(candidate).map((tag) => (
                                                    <Tag key={`${candidate.candidate_id}-${tag.label}`} color={tag.color}>
                                                        {tag.label}
                                                    </Tag>
                                                ))}
                                            </Space>
                                            <Typography.Link href={candidate.url} target="_blank" rel="noreferrer" ellipsis>
                                                {candidate.url}
                                            </Typography.Link>
                                            <Typography.Paragraph type="secondary" ellipsis={{ rows: 2 }}>
                                                {formatCandidateSummary(candidate)}
                                            </Typography.Paragraph>
                                            <Descriptions size="small" column={{ xs: 1, sm: 2, md: 3 }}>
                                                <Descriptions.Item label="来源入口">
                                                    {formatMetadataText(candidate.metadata.seed_url) || candidate.source_id}
                                                </Descriptions.Item>
                                                <Descriptions.Item label="抓取深度">
                                                    {formatMetadataText(candidate.metadata.candidate_depth) || "0"}
                                                </Descriptions.Item>
                                                <Descriptions.Item label="内容大小">
                                                    {formatBytes(candidate.metadata.candidate_content_length)}
                                                </Descriptions.Item>
                                                <Descriptions.Item label="发现地址" span={2}>
                                                    <Typography.Text ellipsis>
                                                        {formatMetadataText(candidate.metadata.candidate_response_url) || candidate.url}
                                                    </Typography.Text>
                                                </Descriptions.Item>
                                                <Descriptions.Item label="匹配关键词">
                                                    {matchedKeywords.length > 0 ? (
                                                        <Space size={4} wrap>
                                                            {matchedKeywords.map((keyword) => (
                                                                <Tag key={`${candidate.candidate_id}-${keyword}`} color="green">
                                                                    {keyword}
                                                                </Tag>
                                                            ))}
                                                        </Space>
                                                    ) : (
                                                        <Typography.Text type="warning">未匹配双碳/技术标准关键词</Typography.Text>
                                                    )}
                                                </Descriptions.Item>
                                                <Descriptions.Item label="入库结果">
                                                    {candidate.review_note || (candidate.knowledge_item_id ? "已创建知识条目" : "等待自动处理")}
                                                </Descriptions.Item>
                                            </Descriptions>
                                            <Typography.Text type="secondary">
                                                hash {candidate.content_hash.slice(0, 12)} / {formatTimestamp(candidate.updated_at)}
                                            </Typography.Text>
                                        </Space>
                                    </List.Item>
                                    );
                                }}
                            />

                            <List
                                className="admin-compact-list"
                                size="small"
                                header={<Typography.Text strong>最近运行记录</Typography.Text>}
                                dataSource={policyCrawlerRuns.slice(0, 5)}
                                locale={{ emptyText: "暂无运行记录。" }}
                                renderItem={(run) => {
                                    const runCandidates = policyCrawlerCandidates.filter((candidate) => candidate.run_id === run.run_id);
                                    const indexedCount =
                                        typeof run.metadata.auto_indexed_count === "number" ? run.metadata.auto_indexed_count : 0;
                                    const failedIndexCount =
                                        typeof run.metadata.auto_index_failed_count === "number" ? run.metadata.auto_index_failed_count : 0;
                                    const skippedTopicCount =
                                        typeof run.metadata.skipped_topic_count === "number" ? run.metadata.skipped_topic_count : 0;
                                    return (
                                    <List.Item>
                                        <Space direction="vertical" size={8} style={{ width: "100%" }}>
                                            <Space size={8} wrap>
                                                <Typography.Text code>{run.run_id}</Typography.Text>
                                                <Tag color={crawlerRunStatusColorMap[run.status] ?? "default"}>
                                                    {crawlerRunStatusLabelMap[run.status] ?? run.status}
                                                </Tag>
                                                 <Tag>{run.trigger_type}</Tag>
                                                {typeof run.metadata.external_job_id === "string" ? (
                                                    <Tag>{run.metadata.external_job_id}</Tag>
                                                ) : null}
                                                <Tag>{run.document_count} 抓取文档</Tag>
                                                <Tag>{run.candidate_count} 入库记录</Tag>
                                                <Tag color={indexedCount > 0 ? "green" : "default"}>{indexedCount} 已索引</Tag>
                                                {failedIndexCount > 0 ? <Tag color="red">{failedIndexCount} 索引失败</Tag> : null}
                                                <Tag color={skippedTopicCount > 0 ? "gold" : "default"}>{skippedTopicCount} 主题过滤</Tag>
                                            </Space>
                                            <Typography.Text type={run.error_detail ? "danger" : "secondary"}>
                                                {run.error_detail ?? `${formatTimestamp(run.started_at)} / ${run.provider_name ?? "unknown"}`}
                                            </Typography.Text>
                                            <Descriptions size="small" column={{ xs: 1, sm: 2, md: 4 }}>
                                                <Descriptions.Item label="自动发布">
                                                    {formatMetadataValue(run.metadata.auto_published_count)}
                                                </Descriptions.Item>
                                                <Descriptions.Item label="索引成功率">
                                                    {run.candidate_count > 0
                                                        ? `${indexedCount}/${run.candidate_count}`
                                                        : "暂无入库记录"}
                                                </Descriptions.Item>
                                                <Descriptions.Item label="主题过滤">
                                                    {formatMetadataValue(run.metadata.skipped_topic_count)}
                                                </Descriptions.Item>
                                                <Descriptions.Item label="运行耗时">
                                                    {run.finished_at
                                                        ? `${Math.max(0, Math.round((new Date(run.finished_at).getTime() - new Date(run.started_at).getTime()) / 1000))}s`
                                                        : "运行中"}
                                                </Descriptions.Item>
                                            </Descriptions>
                                            {runCandidates.length > 0 ? (
                                                <Space direction="vertical" size={4} style={{ width: "100%" }}>
                                                    <Typography.Text type="secondary">本次命中文档</Typography.Text>
                                                    {runCandidates.slice(0, 4).map((candidate) => {
                                                        const keywords = metadataStringList(candidate.metadata.matched_policy_keywords);
                                                        return (
                                                            <div key={`${run.run_id}-${candidate.candidate_id}`} className="admin-crawler-hit-row">
                                                                <Space size={6} wrap>
                                                                    <Typography.Text strong>{candidateDisplayTitle(candidate)}</Typography.Text>
                                                                    <Tag color={candidate.metadata.index_status === "indexed" ? "green" : "default"}>
                                                                        {formatMetadataText(candidate.metadata.index_status) ?? candidate.status}
                                                                    </Tag>
                                                                    {keywords.slice(0, 5).map((keyword) => (
                                                                        <Tag key={`${candidate.candidate_id}-${keyword}`} color="blue">
                                                                            {keyword}
                                                                        </Tag>
                                                                    ))}
                                                                </Space>
                                                                <Typography.Link href={candidate.url} target="_blank" rel="noreferrer" ellipsis>
                                                                    {candidate.url}
                                                                </Typography.Link>
                                                            </div>
                                                        );
                                                    })}
                                                </Space>
                                            ) : null}
                                        </Space>
                                    </List.Item>
                                    );
                                }}
                            />
                        </Space>
                    </Card>

                                </div>
                            ),
                        },
                        {
                            key: "knowledge",
                            label: "知识与任务",
                            children: (
                                <div className="admin-grid admin-grid--tab">
                    <Card
                        className="admin-panel-card admin-grid__table-card"
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
                        className="admin-panel-card admin-grid__table-card"
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

                                </div>
                            ),
                        },
                        {
                            key: "users",
                            label: "用户管理",
                            children: (
                                <div className="admin-grid admin-grid--tab">
                    <Card className="admin-panel-card admin-grid__table-card admin-grid__wide-card" title="用户列表">
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
                            ),
                        },
                    ]}
                />
                </>
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

const crawlerRunStatusLabelMap: Record<string, string> = {
    running: "运行中",
    succeeded: "已完成",
    failed: "失败",
    disabled: "已禁用",
    unavailable: "不可用",
    rejected: "已拒绝",
    skipped: "已跳过",
};

const crawlerRunStatusColorMap: Record<string, string> = {
    running: "processing",
    succeeded: "green",
    failed: "red",
    disabled: "default",
    unavailable: "orange",
    rejected: "red",
    skipped: "default",
};

const candidateStatusLabelMap: Record<string, string> = {
    pending_review: "待自动处理",
    published: "已入库",
    rejected: "已拒绝",
};

const candidateStatusColorMap: Record<string, string> = {
    pending_review: "orange",
    published: "green",
    rejected: "red",
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

function formatCrawlerBackend(value?: string | null) {
    if (value === "scrapyd") {
        return "Scrapyd";
    }
    return "Local Scrapy";
}

function availabilityLabel(value?: boolean | null) {
    if (value === true) {
        return "available";
    }
    if (value === false) {
        return "unavailable";
    }
    return "not configured";
}

function availabilityColor(value?: boolean | null) {
    if (value === true) {
        return "green";
    }
    if (value === false) {
        return "orange";
    }
    return "default";
}

function formatMetadataValue(value: unknown) {
    if (Array.isArray(value)) {
        const items = value.map((item) => formatMetadataText(item)).filter((item): item is string => Boolean(item));
        return items.length ? items.join("、") : "暂无";
    }
    if (typeof value === "string" && value.trim()) {
        return value;
    }
    if (typeof value === "number" || typeof value === "boolean") {
        return String(value);
    }
    return "暂无";
}

function formatMetadataText(value: unknown): string | null {
    if (typeof value === "string" && value.trim()) {
        return value.trim();
    }
    if (typeof value === "number" || typeof value === "boolean") {
        return String(value);
    }
    return null;
}

function metadataStringList(value: unknown): string[] {
    if (Array.isArray(value)) {
        return value.map((item) => formatMetadataText(item)).filter((item): item is string => Boolean(item));
    }
    const single = formatMetadataText(value);
    if (!single) {
        return [];
    }
    return single
        .split(/[、,，]/)
        .map((item) => item.trim())
        .filter(Boolean);
}

function formatBytes(value: unknown): string {
    const bytes = Number(value);
    if (!Number.isFinite(bytes) || bytes < 0) {
        return "未知";
    }
    if (bytes < 1024) {
        return `${bytes} B`;
    }
    if (bytes < 1024 * 1024) {
        return `${(bytes / 1024).toFixed(1)} KB`;
    }
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function formatCandidateSummary(candidate: PolicyCrawlerCandidateSummary): string {
    const summary = formatMetadataText(candidate.metadata.candidate_summary);
    if (summary) {
        return summary;
    }
    if (candidate.content_type.includes("pdf") || candidate.content_type.includes("ofd")) {
        return `${candidate.content_type} 文件，待发布后进入解析链路。`;
    }
    return "暂无正文摘要。请查看 URL、内容类型和抓取元数据后再决定是否发布。";
}

function candidateDisplayTitle(candidate: PolicyCrawlerCandidateSummary): string {
    const title = candidate.title?.trim();
    if (title && !isGenericPolicyCrawlerTitle(title)) {
        return title;
    }
    const metadataTitle =
        formatMetadataText(candidate.metadata.source_title) ||
        formatMetadataText(candidate.metadata.source_label) ||
        formatMetadataText(candidate.metadata.candidate_response_url);
    return metadataTitle || title || candidate.url;
}

function isGenericPolicyCrawlerTitle(value: string): boolean {
    const title = value.trim();
    return [
        "国务院政策文件库",
        "政策文件库",
        "政策文件",
        "政策公开",
        "政策发布",
        "搜索",
        "检索",
    ].includes(title);
}

function candidateQualityTags(candidate: PolicyCrawlerCandidateSummary) {
    const keywords = metadataStringList(candidate.metadata.matched_policy_keywords);
    const depth = Number(candidate.metadata.candidate_depth ?? 0);
    const tags: Array<{ label: string; color: string }> = [];
    tags.push({ label: keywords.length > 0 ? `${keywords.length} 个关键词` : "无关键词", color: keywords.length > 0 ? "green" : "orange" });
    tags.push({ label: depth > 0 ? "具体页面" : "入口页", color: depth > 0 ? "blue" : "default" });
    if (candidate.metadata.index_status === "indexed") {
        tags.push({ label: "已索引", color: "green" });
    } else if (candidate.metadata.index_status === "failed") {
        tags.push({ label: "索引失败", color: "red" });
    }
    return tags;
}

function extractDetailMessage(value: unknown): string | null {
    if (!value || typeof value !== "object") {
        return null;
    }
    const candidate = value as { detail?: unknown; message?: unknown; response?: { data?: { detail?: unknown; message?: unknown } } };
    const responseDetail = candidate.response?.data?.detail ?? candidate.response?.data?.message;
    if (typeof responseDetail === "string" && responseDetail.trim()) {
        return responseDetail;
    }
    if (typeof candidate.detail === "string" && candidate.detail.trim()) {
        return candidate.detail;
    }
    return typeof candidate.message === "string" && candidate.message.trim() ? candidate.message : null;
}
