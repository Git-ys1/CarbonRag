import { ReloadOutlined } from "@ant-design/icons";
import {
    Button,
    Card,
    Empty,
    List,
    Space,
    Spin,
    Statistic,
    Tabs,
    Tag,
    Typography,
} from "antd";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useFeedback } from "../../hooks/useFeedback";
import { loadMyKnowledgeWorkspace } from "../../services/knowledge";
import type { KnowledgeItem, MyKnowledgeFeedback, MyKnowledgeReport, MyKnowledgeWorkspace } from "../../types/knowledge";
import { useNavigate } from "react-router-dom";

const emptyWorkspace: MyKnowledgeWorkspace = {
    uploads: [],
    knowledgeItems: [],
    reports: [],
    feedback: [],
    taskSummary: [],
};

export function MyKnowledgePage() {
    const navigate = useNavigate();
    const feedback = useFeedback();
    const [workspace, setWorkspace] = useState<MyKnowledgeWorkspace>(emptyWorkspace);
    const [loading, setLoading] = useState(true);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);

    useEffect(() => {
        void refreshWorkspace();
    }, []);

    useEffect(() => {
        if (!errorMessage) {
            return;
        }
        feedback.error({
            title: "我的知识库提示",
            description: errorMessage,
            source: "MyKnowledgePage",
            key: `knowledge:${errorMessage}`,
        });
    }, [errorMessage, feedback]);

    async function refreshWorkspace() {
        setLoading(true);
        setErrorMessage(null);
        try {
            const nextWorkspace = await loadMyKnowledgeWorkspace();
            setWorkspace(nextWorkspace);
        } catch (error) {
            setErrorMessage(extractDetailMessage(error) ?? "当前无法加载我的知识库，请确认后端已启动。");
        } finally {
            setLoading(false);
        }
    }

    return (
        <div className="knowledge-workbench">
            <div className="knowledge-workbench__sidebar">
                <Card
                    title="我的知识概览"
                    extra={<Button icon={<ReloadOutlined />} onClick={() => void refreshWorkspace()} loading={loading}>刷新</Button>}
                >
                    <Typography.Paragraph type="secondary">
                        这里汇总你上传过的资料、已经入库的知识条目、生成过的报告和反馈记录。默认先展示“我有什么、现在可做什么”，而不是后台任务指标。
                    </Typography.Paragraph>
                    <div className="admin-stats">
                        <Statistic title="上传" value={workspace.uploads.length} />
                        <Statistic title="知识条目" value={workspace.knowledgeItems.length} />
                        <Statistic title="报告" value={workspace.reports.length} />
                    </div>
                    <div style={{ height: 12 }} />
                    <Statistic title="反馈" value={workspace.feedback.length} />
                </Card>

                <Card title="最近任务">
                    <List
                        size="small"
                        dataSource={workspace.taskSummary.slice(0, 5)}
                        locale={{ emptyText: "暂无任务记录。" }}
                        renderItem={(item) => (
                            <List.Item>
                                <Space direction="vertical" size={4} style={{ width: "100%" }}>
                                    <Space size={8} wrap>
                                        <Tag color={taskStatusColorMap[item.status]}>{taskStatusLabelMap[item.status]}</Tag>
                                        <Tag>{item.scope}</Tag>
                                    </Space>
                                    <Typography.Text>{item.summary ?? "系统正在处理这条知识任务。"}</Typography.Text>
                                    <Typography.Text type="secondary">{formatTimestamp(item.created_at)}</Typography.Text>
                                </Space>
                            </List.Item>
                        )}
                    />
                </Card>
            </div>

            <div className="knowledge-workbench__main">
                <Card
                    title="知识库 · 个人知识条目"
                    extra={<Tag color="blue">当前登录用户可见</Tag>}
                    className="knowledge-workbench__content-card"
                >
                    {loading ? (
                        <div className="chat-workbench__loading">
                            <Spin size="large" />
                        </div>
                    ) : (
                        <Tabs
                            defaultActiveKey="uploads"
                            items={[
                                {
                                    key: "uploads",
                                    label: "我的上传",
                                    children: (
                                        <List
                                            dataSource={workspace.uploads}
                                            locale={{ emptyText: <Empty description="暂无上传文件。" /> }}
                                            renderItem={(item) => (
                                                <List.Item key={item.knowledge_item_id}>
                                                    <KnowledgeCard
                                                        title={item.title}
                                                        subtitle={`所属会话：${item.session_title ?? item.session_id ?? "未关联会话"}`}
                                                        tags={[
                                                            { label: knowledgeStatusLabelMap[item.index_status] ?? item.index_status, color: statusColorMap[item.index_status] },
                                                            { label: item.mime_type ?? "未知类型" },
                                                            { label: `上传于 ${formatTimestamp(item.uploaded_at ?? item.updated_at ?? "")}` },
                                                        ]}
                                                    />
                                                </List.Item>
                                            )}
                                        />
                                    ),
                                },
                                {
                                    key: "items",
                                    label: "我的知识条目",
                                    children: (
                                        <List
                                            dataSource={workspace.knowledgeItems}
                                            locale={{ emptyText: <Empty description="当前没有可展示的知识条目。" /> }}
                                            renderItem={(item) => (
                                                <List.Item key={item.knowledge_item_id}>
                                                    <KnowledgeCard
                                                        title={item.title}
                                                        subtitle={item.source_label}
                                                        description={item.last_error ?? "知识条目已可用于检索或等待系统继续处理。"}
                                                        tags={[
                                                            { label: item.library_scope === "shared" ? "共享知识" : "个人知识", color: item.library_scope === "shared" ? "blue" : "green" },
                                                            { label: knowledgeSourceLabelMap[item.source_type] },
                                                            { label: `解析 ${knowledgeStatusLabelMap[item.parse_status]}`, color: statusColorMap[item.parse_status] },
                                                            { label: `入库 ${knowledgeStatusLabelMap[item.ingest_status]}`, color: statusColorMap[item.ingest_status] },
                                                            { label: `索引 ${knowledgeStatusLabelMap[item.index_status]}`, color: statusColorMap[item.index_status] },
                                                            { label: item.session_attachable ? "允许挂接" : "暂不可挂接" },
                                                        ]}
                                                    />
                                                </List.Item>
                                            )}
                                        />
                                    ),
                                },
                                {
                                    key: "reports",
                                    label: "我的报告",
                                    children: (
                                        <List
                                            dataSource={workspace.reports}
                                            locale={{ emptyText: <Empty description="暂无报告。" /> }}
                                            renderItem={(record) => (
                                                <List.Item key={record.report_id}>
                                                    <KnowledgeCard
                                                        title={record.title}
                                                        subtitle={`所属会话：${record.session_title}`}
                                                        tags={[
                                                            { label: reportTypeLabelMap[record.report_type] },
                                                            { label: `更新于 ${formatTimestamp(record.updated_at)}` },
                                                            { label: `${record.source_count} 个来源` },
                                                        ]}
                                                        action={(
                                                            <Button size="small" onClick={() => navigate("/report")}>
                                                                打开报告页
                                                            </Button>
                                                        )}
                                                    />
                                                </List.Item>
                                            )}
                                        />
                                    ),
                                },
                                {
                                    key: "feedback",
                                    label: "我的反馈",
                                    children: (
                                        <List
                                            dataSource={workspace.feedback}
                                            locale={{
                                                emptyText: (
                                                    <Empty description="当前还没有可展示的个人反馈。" />
                                                ),
                                            }}
                                            renderItem={(record) => (
                                                <List.Item key={record.feedback_id}>
                                                    <KnowledgeCard
                                                        title={feedbackTargetLabelMap[record.target_type] ?? record.target_type}
                                                        subtitle={record.comment ?? "未填写补充说明"}
                                                        tags={[
                                                            { label: record.rating === "up" ? "正向" : "负向", color: record.rating === "up" ? "green" : "red" },
                                                            { label: record.session_id ?? "未关联会话" },
                                                            { label: formatTimestamp(record.created_at) },
                                                        ]}
                                                    />
                                                </List.Item>
                                            )}
                                        />
                                    ),
                                },
                            ]}
                        />
                    )}
                </Card>
            </div>
        </div>
    );
}

const knowledgeStatusLabelMap: Record<"pending" | "running" | "succeeded" | "failed" | "ready", string> = {
    pending: "待处理",
    running: "处理中",
    succeeded: "已完成",
    failed: "失败",
    ready: "已就绪",
};

const statusColorMap: Record<"pending" | "running" | "succeeded" | "failed" | "ready", string> = {
    pending: "default",
    running: "processing",
    succeeded: "green",
    failed: "red",
    ready: "blue",
};

const knowledgeSourceLabelMap: Record<string, string> = {
    uploaded_file: "上传文件",
    private_sample_repo: "共享知识条目",
    knowledge_item: "知识条目",
};

const reportTypeLabelMap: Record<string, string> = {
    policy_summary: "政策解读摘要",
    mixed_analysis: "政策 + 样例分析",
    carbon_summary: "碳核算结果说明",
};

const feedbackTargetLabelMap: Record<string, string> = {
    ask: "问答反馈",
    calc_carbon: "核算反馈",
    report: "报告反馈",
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
    failed: "red",
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

function extractDetailMessage(value: unknown): string | null {
    if (!value || typeof value !== "object") {
        return null;
    }
    const candidate = value as { detail?: unknown };
    return typeof candidate.detail === "string" ? candidate.detail : null;
}

interface KnowledgeCardProps {
    title: string;
    subtitle: string;
    description?: string;
    tags: Array<{ label: string; color?: string }>;
    action?: ReactNode;
}

function KnowledgeCard({ title, subtitle, description, tags, action }: KnowledgeCardProps) {
    return (
        <div className="knowledge-card">
            <div className="knowledge-card__body">
                <Space direction="vertical" size={6} style={{ width: "100%" }}>
                    <Typography.Text strong>{title}</Typography.Text>
                    <Typography.Text type="secondary">{subtitle}</Typography.Text>
                    {description ? (
                        <Typography.Paragraph type="secondary" className="knowledge-card__description">
                            {description}
                        </Typography.Paragraph>
                    ) : null}
                    <Space size={8} wrap>
                        {tags.map((tag) => (
                            <Tag key={`${title}-${tag.label}`} color={tag.color}>
                                {tag.label}
                            </Tag>
                        ))}
                    </Space>
                </Space>
            </div>
            {action ? <div className="knowledge-card__action">{action}</div> : null}
        </div>
    );
}
