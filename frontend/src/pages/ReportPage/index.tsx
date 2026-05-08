import {
    CopyOutlined,
    FileTextOutlined,
    ReloadOutlined,
    SaveOutlined,
} from "@ant-design/icons";
import {
    Alert,
    Button,
    Card,
    Checkbox,
    Collapse,
    Empty,
    Input,
    List,
    Segmented,
    Select,
    Space,
    Spin,
    Tag,
    Typography,
    message,
} from "antd";
import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import { useNavigate } from "react-router-dom";
import { useSettings } from "../../app/SettingsContext";
import { useWorkbenchShellContext } from "../../layouts/WorkbenchShellContext";
import { getSession } from "../../services/sessions";
import {
    createReport,
    getReport,
    listSessionCarbonResults,
    listSessionReports,
    updateReport,
} from "../../services/reports";
import type { SessionDetail, SessionMessage } from "../../types/session";
import type {
    ReportCitation,
    ReportDetail,
    ReportSourceSummary,
    ReportSummary,
    ReportType,
    SessionCarbonCalculationSummary,
} from "../../types/report";

type PreviewMode = "preview" | "edit";

const reportTypeOptions: { label: string; value: ReportType }[] = [
    { label: "政策解读摘要", value: "policy_summary" },
    { label: "政策 + 样例分析", value: "mixed_analysis" },
    { label: "碳核算结果说明", value: "carbon_summary" },
];

const reportTypeLabelMap: Record<ReportType, string> = {
    policy_summary: "政策解读摘要",
    mixed_analysis: "政策 + 样例分析",
    carbon_summary: "碳核算结果说明",
};

const sourceTypeLabelMap = {
    public_policy: "公共政策",
    public_policy_demo: "演示样例",
    private_sample: "知识条目",
    carbon_factor: "排放因子",
} as const;

const sourceTypeColorMap = {
    public_policy: "blue",
    public_policy_demo: "orange",
    private_sample: "magenta",
    carbon_factor: "gold",
} as const;

const emptyReportSourceSummary: ReportSourceSummary = {
    public_policy_count: 0,
    public_policy_demo_count: 0,
    private_sample_count: 0,
    carbon_factor_count: 0,
    total_citation_count: 0,
};

export function ReportPage() {
    const navigate = useNavigate();
    const { getActiveProviderOverride } = useSettings();
    const { activeSessionId, refreshSessions } = useWorkbenchShellContext();
    const [activeSession, setActiveSession] = useState<SessionDetail | null>(null);
    const [reports, setReports] = useState<ReportSummary[]>([]);
    const [carbonResults, setCarbonResults] = useState<SessionCarbonCalculationSummary[]>([]);
    const [selectedReportId, setSelectedReportId] = useState<string | null>(null);
    const [activeReport, setActiveReport] = useState<ReportDetail | null>(null);
    const [reportType, setReportType] = useState<ReportType>("policy_summary");
    const [title, setTitle] = useState("");
    const [selectedMessageIds, setSelectedMessageIds] = useState<string[]>([]);
    const [selectedCarbonResultId, setSelectedCarbonResultId] = useState<string | undefined>(undefined);
    const [previewMode, setPreviewMode] = useState<PreviewMode>("preview");
    const [editorContent, setEditorContent] = useState("");
    const [loadingSessionDetail, setLoadingSessionDetail] = useState(false);
    const [loadingReport, setLoadingReport] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [saving, setSaving] = useState(false);
    const [transportError, setTransportError] = useState<string | null>(null);

    const selectableMessages = useMemo(
        () => (activeSession?.messages ?? []).filter((item) => item.role === "assistant" && item.citations.length > 0),
        [activeSession],
    );

    const groupedCitations = useMemo(
        () => groupReportCitations(activeReport?.citations ?? []),
        [activeReport],
    );
    const currentSummary = activeReport?.source_summary ?? emptyReportSourceSummary;
    const reportReadiness = useMemo(
        () => buildReportReadiness(reportType, selectableMessages, carbonResults, selectedMessageIds, selectedCarbonResultId),
        [reportType, selectableMessages, carbonResults, selectedMessageIds, selectedCarbonResultId],
    );

    useEffect(() => {
        if (!activeSessionId) {
            setActiveSession(null);
            setReports([]);
            setCarbonResults([]);
            setSelectedReportId(null);
            setActiveReport(null);
            return;
        }
        void loadSessionWorkspace(activeSessionId);
    }, [activeSessionId]);

    useEffect(() => {
        if (!selectedReportId) {
            return;
        }
        void loadReport(selectedReportId);
    }, [selectedReportId]);

    useEffect(() => {
        if (selectedReportId) {
            return;
        }
        applyDefaults(reportType, activeSession, carbonResults, setSelectedMessageIds, setSelectedCarbonResultId);
    }, [reportType, activeSession, carbonResults, selectedReportId]);

    async function loadSessionWorkspace(sessionId: string) {
        setLoadingSessionDetail(true);
        setTransportError(null);
        setSelectedReportId(null);
        setActiveReport(null);
        try {
            const [detail, reportList, carbonList] = await Promise.all([
                getSession(sessionId),
                listSessionReports(sessionId),
                listSessionCarbonResults(sessionId),
            ]);
            setActiveSession(detail);
            setReports(reportList);
            setCarbonResults(carbonList);
            setTitle("");
            setEditorContent("");
            setPreviewMode("preview");
            applyDefaults(reportType, detail, carbonList, setSelectedMessageIds, setSelectedCarbonResultId);
        } catch {
            setActiveSession(null);
            setReports([]);
            setCarbonResults([]);
            setTransportError("当前无法读取所选会话的报告上下文，请稍后重试。");
        } finally {
            setLoadingSessionDetail(false);
        }
    }

    async function loadReport(reportId: string) {
        setLoadingReport(true);
        setTransportError(null);
        try {
            const detail = await getReport(reportId);
            setActiveReport(detail);
            setReportType(detail.report_type);
            setTitle(detail.title);
            setEditorContent(detail.content);
            setPreviewMode("preview");
            setSelectedMessageIds(
                detail.sources.filter((item) => item.source_type === "message").map((item) => item.source_ref),
            );
            setSelectedCarbonResultId(
                detail.sources.find((item) => item.source_type === "carbon_result")?.source_ref,
            );
        } catch {
            setTransportError("当前无法读取所选报告，请稍后重试。");
        } finally {
            setLoadingReport(false);
        }
    }

    async function handleGenerate() {
        if (!activeSessionId) {
            setTransportError("当前没有可用会话。");
            return;
        }

        setSubmitting(true);
        setTransportError(null);
        try {
            const created = await createReport({
                session_id: activeSessionId,
                report_type: reportType,
                title: title.trim() || undefined,
                source_message_ids: selectedMessageIds,
                carbon_result_id: selectedCarbonResultId,
                output_format: "markdown",
                provider_override: getActiveProviderOverride(),
            });
            await loadSessionWorkspace(activeSessionId);
            setSelectedReportId(created.report_id);
            message.success("报告已生成。");
        } catch (error) {
            setTransportError(extractDetailMessage(error) ?? "当前无法生成报告，请稍后重试。");
        } finally {
            setSubmitting(false);
        }
    }

    async function handleSave() {
        if (!activeReport) {
            return;
        }
        setSaving(true);
        setTransportError(null);
        try {
            const updated = await updateReport(activeReport.report_id, {
                title: title.trim() || undefined,
                content: editorContent,
            });
            setActiveReport(updated);
            setTitle(updated.title);
            setEditorContent(updated.content);
            if (activeSessionId) {
                const sessionReports = await listSessionReports(activeSessionId);
                setReports(sessionReports);
            }
            message.success("报告修改已保存。");
        } catch (error) {
            setTransportError(extractDetailMessage(error) ?? "当前无法保存报告，请稍后重试。");
        } finally {
            setSaving(false);
        }
    }

    async function handleCopyMarkdown() {
        if (!activeReport) {
            return;
        }
        try {
            await navigator.clipboard.writeText(activeReport.content);
            message.success("正文已复制。");
        } catch {
            message.error("复制失败，请检查浏览器权限。");
        }
    }

    return (
        <div className="chat-workbench chat-workbench--single-column">
            <div className="chat-workbench__main">
                {transportError ? (
                    <Alert
                        type="warning"
                        showIcon
                        className="chat-workbench__alert"
                        message="报告工作台提示"
                        description={transportError}
                    />
                ) : null}

                <Card title="当前会话报告列表">
                    {loadingSessionDetail ? (
                        <div className="chat-workbench__loading"><Spin /></div>
                    ) : reports.length ? (
                        <List
                            className="chat-session-list"
                            dataSource={reports}
                            renderItem={(report) => (
                                <List.Item
                                    className={selectedReportId === report.report_id
                                        ? "chat-session-list__item chat-session-list__item--active"
                                        : "chat-session-list__item"}
                                    onClick={() => setSelectedReportId(report.report_id)}
                                >
                                    <div className="chat-session-list__content">
                                        <Typography.Text strong>{report.title}</Typography.Text>
                                        <Typography.Text type="secondary">
                                            {reportTypeLabelMap[report.report_type]} · {formatTimestamp(report.updated_at)}
                                        </Typography.Text>
                                    </div>
                                </List.Item>
                            )}
                        />
                    ) : (
                        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前会话还没有生成报告。" />
                    )}
                </Card>

                <Card
                    className="report-workbench__config-card"
                    title="报告配置区"
                    extra={activeSession ? <Tag color="blue">{activeSession.title}</Tag> : null}
                >
                    <Typography.Paragraph type="secondary">
                        这里会默认尝试使用当前会话里最近可用的回答或核算结果。重新生成会产生一份新报告；保存编辑会覆盖当前报告正文。
                    </Typography.Paragraph>

                    {!reportReadiness.ready ? (
                        <Alert
                            type="info"
                            showIcon
                            message={reportReadiness.title}
                            description={reportReadiness.description}
                            action={reportReadiness.actionLabel ? (
                                <Button size="small" onClick={() => navigate(reportReadiness.actionTarget ?? "/")}>
                                    {reportReadiness.actionLabel}
                                </Button>
                            ) : null}
                        />
                    ) : null}

                    <div className="report-workbench__config-stack">
                        <Segmented
                            block
                            value={reportType}
                            onChange={(value) => {
                                setSelectedReportId(null);
                                setActiveReport(null);
                                setReportType(value as ReportType);
                            }}
                            options={reportTypeOptions}
                        />

                        <div className="report-workbench__field">
                            <Typography.Text strong>报告标题</Typography.Text>
                            <Input
                                value={title}
                                onChange={(event) => setTitle(event.target.value)}
                                placeholder="可选；为空时使用模板名 + 会话标题"
                            />
                        </div>

                        <div className="report-workbench__field">
                            <Typography.Text strong>引用来源选择</Typography.Text>
                            <Checkbox.Group
                                className="report-workbench__checkbox-group"
                                value={selectedMessageIds}
                                onChange={(value) => setSelectedMessageIds(value as string[])}
                            >
                                <Space direction="vertical" style={{ width: "100%" }}>
                                    {selectableMessages.length ? selectableMessages.map((messageItem) => (
                                        <Checkbox key={messageItem.message_id} value={messageItem.message_id}>
                                            <Space direction="vertical" size={4}>
                                                <Typography.Text strong>
                                                    {messageItem.content.slice(0, 42)}
                                                </Typography.Text>
                                                <Space size={8} wrap>
                                                    <Tag>{messageItem.citations.length} 条引用</Tag>
                                                    <Tag color="blue">{buildMessageSourceHint(messageItem)}</Tag>
                                                </Space>
                                            </Space>
                                        </Checkbox>
                                    )) : (
                                        <Typography.Text type="secondary">
                                            当前会话还没有可作为报告来源的助手消息。你也可以直接点击“生成报告”，后端会尝试自动回退到最近合法来源。
                                        </Typography.Text>
                                    )}
                                </Space>
                            </Checkbox.Group>
                        </div>

                        <div className="report-workbench__field">
                            <Typography.Text strong>可选碳核算结果</Typography.Text>
                            <Select
                                allowClear
                                value={selectedCarbonResultId}
                                onChange={(value) => setSelectedCarbonResultId(value)}
                                placeholder="仅碳核算结果说明必填"
                                options={carbonResults.map((item) => ({
                                    value: item.trace_id,
                                    label: `${item.period_label ?? "未命名周期"} | ${item.total_emission_kgco2e.toFixed(3)} kgCO2e`,
                                }))}
                            />
                        </div>

                        <Space size={12} wrap>
                            <Button
                                type="primary"
                                icon={<FileTextOutlined />}
                                loading={submitting}
                                onClick={() => void handleGenerate()}
                            >
                                生成报告
                            </Button>
                            <Button
                                icon={<ReloadOutlined />}
                                loading={submitting}
                                onClick={() => void handleGenerate()}
                            >
                                重新生成
                            </Button>
                            <Button
                                icon={<CopyOutlined />}
                                disabled={!activeReport}
                                onClick={() => void handleCopyMarkdown()}
                            >
                                复制正文
                            </Button>
                            <Button
                                icon={<SaveOutlined />}
                                disabled={!activeReport}
                                loading={saving}
                                onClick={() => void handleSave()}
                            >
                                保存编辑
                            </Button>
                        </Space>
                    </div>
                </Card>

                <Card
                    className="report-workbench__preview-card"
                    title="报告预览区"
                    extra={activeReport ? <Tag color="green">{activeReport.trace_id}</Tag> : null}
                >
                    {loadingReport || loadingSessionDetail ? (
                        <div className="chat-workbench__loading"><Spin /></div>
                    ) : activeReport ? (
                        <div className="report-workbench__preview-stack">
                            <Space size={8} wrap>
                                <Tag color="gold">{reportTypeLabelMap[activeReport.report_type]}</Tag>
                                <Tag>{currentSummary.total_citation_count} 条依据</Tag>
                                <Tag>{formatTimestamp(activeReport.created_at)}</Tag>
                                <Tag color="blue">更新于 {formatTimestamp(activeReport.updated_at)}</Tag>
                            </Space>

                            <Segmented<PreviewMode>
                                value={previewMode}
                                onChange={(value) => setPreviewMode(value)}
                                options={[
                                    { label: "预览", value: "preview" },
                                    { label: "编辑正文", value: "edit" },
                                ]}
                            />

                            {previewMode === "preview" ? (
                                <div className="report-workbench__markdown">
                                    <ReactMarkdown>{activeReport.content}</ReactMarkdown>
                                </div>
                            ) : (
                                <Input.TextArea
                                    value={editorContent}
                                    onChange={(event) => setEditorContent(event.target.value)}
                                    autoSize={{ minRows: 18, maxRows: 28 }}
                                />
                            )}

                            <Collapse
                                ghost
                                defaultActiveKey={[]}
                                items={[
                                    {
                                        key: "citations",
                                        label: `查看依据（${currentSummary.total_citation_count}）`,
                                        children: groupedCitations.public_policy.length || groupedCitations.public_policy_demo.length || groupedCitations.private_sample.length || groupedCitations.carbon_factor.length ? (
                                            <div className="chat-citation-groups">
                                                {groupedCitations.public_policy.length ? (
                                                    <ReportCitationGroup
                                                        title="政策依据"
                                                        citations={groupedCitations.public_policy}
                                                    />
                                                ) : null}
                                                {groupedCitations.public_policy_demo.length ? (
                                                    <ReportCitationGroup
                                                        title="演示样例依据"
                                                        citations={groupedCitations.public_policy_demo}
                                                    />
                                                ) : null}
                                                {groupedCitations.private_sample.length ? (
                                                    <ReportCitationGroup
                                                        title="知识条目依据"
                                                        citations={groupedCitations.private_sample}
                                                    />
                                                ) : null}
                                                {groupedCitations.carbon_factor.length ? (
                                                    <ReportCitationGroup
                                                        title="排放因子依据"
                                                        citations={groupedCitations.carbon_factor}
                                                    />
                                                ) : null}
                                            </div>
                                        ) : (
                                            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前报告暂无依据。" />
                                        ),
                                    },
                                ]}
                            />
                        </div>
                    ) : (
                        <Empty
                            image={Empty.PRESENTED_IMAGE_SIMPLE}
                            description="选择当前会话后即可生成报告；若当前会话缺少可用来源，这里会提示你先去问答页或碳核算页补充上下文。"
                        />
                    )}
                </Card>
            </div>
        </div>
    );
}

interface ReportCitationGroupProps {
    title: string;
    citations: ReportCitation[];
}

function ReportCitationGroup({ title, citations }: ReportCitationGroupProps) {
    return (
        <div className="chat-citation-group">
            <Space size={8} wrap className="chat-citation-group__header">
                <Typography.Text strong>{title}</Typography.Text>
                <Tag>{citations.length}</Tag>
            </Space>
            <List
                dataSource={citations}
                renderItem={(citation) => (
                    <List.Item key={`${citation.source_type}-${citation.chunk_id ?? citation.factor_id ?? citation.title}`}>
                        <div className="chat-citation-card">
                            <Space size={8} wrap>
                                <Typography.Text strong>{citation.title}</Typography.Text>
                                <Tag color={sourceTypeColorMap[citation.source_type]}>
                                    {sourceTypeLabelMap[citation.source_type]}
                                </Tag>
                                <Tag>{citation.source}</Tag>
                            </Space>
                            <Typography.Paragraph
                                className="chat-citation-card__snippet"
                                ellipsis={{ rows: 3, expandable: "collapsible", symbol: "展开" }}
                            >
                                {citation.snippet}
                            </Typography.Paragraph>
                            {citation.source_url?.startsWith("http") ? (
                                <Typography.Link href={citation.source_url} target="_blank" rel="noreferrer">
                                    查看来源
                                </Typography.Link>
                            ) : citation.source_type === "public_policy_demo" ? (
                                <Typography.Text type="secondary">内置演示样例，不代表真实官方政策。</Typography.Text>
                            ) : null}
                        </div>
                    </List.Item>
                )}
            />
        </div>
    );
}

function applyDefaults(
    nextReportType: ReportType,
    session: SessionDetail | null,
    nextCarbonResults: SessionCarbonCalculationSummary[],
    setSelectedMessageIds: (value: string[]) => void,
    setSelectedCarbonResultId: (value: string | undefined) => void,
) {
    if (!session) {
        setSelectedMessageIds([]);
        setSelectedCarbonResultId(undefined);
        return;
    }

    const defaultMessage = pickDefaultMessage(session.messages, nextReportType);
    setSelectedMessageIds(defaultMessage ? [defaultMessage.message_id] : []);
    setSelectedCarbonResultId(
        nextReportType === "carbon_summary" ? nextCarbonResults[0]?.trace_id : undefined,
    );
}

function pickDefaultMessage(messages: SessionMessage[], reportType: ReportType) {
    const candidates = [...messages]
        .filter((item) => item.role === "assistant" && item.citations.length > 0)
        .reverse();

    if (reportType === "mixed_analysis") {
        return candidates.find(
            (item) =>
                item.citations.some((citation) => citation.source_type === "public_policy") &&
                item.citations.some((citation) => citation.source_type === "private_sample"),
        ) ?? candidates[0];
    }

    if (reportType === "policy_summary") {
        return candidates.find((item) => item.citations.some((citation) => citation.source_type === "public_policy"))
            ?? candidates[0];
    }

    return candidates[0];
}

function buildMessageSourceHint(message: SessionMessage) {
    const hasPublic = message.citations.some((citation) => citation.source_type === "public_policy");
    const hasPrivate = message.citations.some((citation) => citation.source_type === "private_sample");
    if (hasPublic && hasPrivate) {
        return "政策 + 知识条目";
    }
    if (hasPublic) {
        return "政策依据";
    }
    if (hasPrivate) {
        return "知识条目依据";
    }
    return "一般来源";
}

function buildReportReadiness(
    reportType: ReportType,
    selectableMessages: SessionMessage[],
    carbonResults: SessionCarbonCalculationSummary[],
    selectedMessageIds: string[],
    selectedCarbonResultId: string | undefined,
) {
    const suggestedMessage = pickDefaultMessage(selectableMessages, reportType);

    if (reportType === "carbon_summary") {
        if (selectedCarbonResultId || carbonResults.length > 0) {
            return {
                ready: true,
                title: "",
                description: "",
                actionLabel: null,
                actionTarget: null,
            };
        }
        return {
            ready: false,
            title: "当前会话还没有可用的碳核算结果",
            description: "先去碳核算页完成一次核算，再回来生成“碳核算结果说明”报告。",
            actionLabel: "前往碳核算页",
            actionTarget: "/carbon-calc",
        };
    }

    if (selectedMessageIds.length > 0 || suggestedMessage) {
        return {
            ready: true,
            title: "",
            description: "",
            actionLabel: null,
            actionTarget: null,
        };
    }

    return {
        ready: false,
        title: "当前会话还没有可用的报告来源",
        description: "先在问答页完成至少一轮带依据的助手回答，再回来生成报告。",
        actionLabel: "前往问答页",
        actionTarget: "/",
    };
}

function groupReportCitations(citations: ReportCitation[]) {
    return {
        public_policy: citations.filter((item) => item.source_type === "public_policy"),
        public_policy_demo: citations.filter((item) => item.source_type === "public_policy_demo"),
        private_sample: citations.filter((item) => item.source_type === "private_sample"),
        carbon_factor: citations.filter((item) => item.source_type === "carbon_factor"),
    };
}

function formatTimestamp(value: string) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return value;
    }
    return date.toLocaleString("zh-CN", {
        hour12: false,
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
    });
}

function extractDetailMessage(value: unknown): string | null {
    if (!value || typeof value !== "object") {
        return null;
    }
    const candidate = value as { detail?: unknown };
    return typeof candidate.detail === "string" ? candidate.detail : null;
}
