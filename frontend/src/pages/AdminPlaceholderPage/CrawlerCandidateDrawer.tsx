import { EyeOutlined, LinkOutlined } from "@ant-design/icons";
import { Alert, Button, Descriptions, Drawer, Empty, Space, Tabs, Tag, Typography } from "antd";
import type { PolicyCrawlerCandidateSummary } from "../../types/admin";

interface CrawlerCandidateDrawerProps {
    candidate: PolicyCrawlerCandidateSummary | null;
    open: boolean;
    onClose: () => void;
    onPreviewFile: (candidate: PolicyCrawlerCandidateSummary) => void;
    onPublishToRag: (candidateId: string) => void;
    onPublishLegacy: (candidateId: string) => void;
    onReject: (candidateId: string) => void;
    reviewingCandidateId: string | null;
}

export function CrawlerCandidateDrawer({
    candidate,
    open,
    onClose,
    onPreviewFile,
    onPublishToRag,
    onPublishLegacy,
    onReject,
    reviewingCandidateId,
}: CrawlerCandidateDrawerProps) {
    if (!candidate) {
        return (
            <Drawer title="候选详情" open={open} onClose={onClose} width={760}>
                <Empty description="未选择候选文档。" />
            </Drawer>
        );
    }

    const metadata = candidate.metadata ?? {};
    const metadataNumber = (key: string): number => {
        const value = metadata[key];
        return typeof value === "number" && Number.isFinite(value) ? value : 0;
    };
    const markdownSize = candidate.markdown_size ?? metadataNumber("markdown_size");
    const cleanedSize = candidate.cleaned_size ?? metadataNumber("cleaned_size");
    const estimatedChunkCount = candidate.estimated_chunk_count ?? metadataNumber("estimated_chunk_count");
    const duplicateReason = candidate.duplicate_reason || (typeof metadata.duplicate_reason === "string" ? metadata.duplicate_reason : null);
    const isDuplicate = candidate.skip_reason === "duplicate_content_hash" || metadata.change_type === "unchanged";
    const artifactBlocked =
        Number(candidate.extraction_quality_score ?? 0) < 60 ||
        markdownSize < 800 ||
        cleanedSize < 800 ||
        (candidate.artifact_errors?.length ?? 0) > 0;
    const publishLabel = isDuplicate && !candidate.rag_doc_id ? "重新入库" : "发布到 RAG";

    return (
        <Drawer
            title={
                <Space direction="vertical" size={2}>
                    <Typography.Text strong>{candidate.title || candidate.url}</Typography.Text>
                    <Typography.Text type="secondary" ellipsis style={{ maxWidth: 640 }}>
                        {candidate.url}
                    </Typography.Text>
                </Space>
            }
            open={open}
            onClose={onClose}
            width={860}
            extra={
                <Space size={8} wrap>
                    <Button icon={<EyeOutlined />} onClick={() => onPreviewFile(candidate)}>
                        查看抓取文件
                    </Button>
                    <Button
                        type="primary"
                        disabled={candidate.status === "rejected" || artifactBlocked}
                        loading={reviewingCandidateId === candidate.candidate_id}
                        onClick={() => onPublishToRag(candidate.candidate_id)}
                    >
                        {publishLabel}
                    </Button>
                    <Button
                        danger
                        disabled={candidate.status !== "pending_review"}
                        loading={reviewingCandidateId === candidate.candidate_id}
                        onClick={() => onReject(candidate.candidate_id)}
                    >
                        拒绝
                    </Button>
                </Space>
            }
        >
            <Space direction="vertical" size={14} style={{ width: "100%" }}>
                {artifactBlocked ? (
                    <Alert
                        showIcon
                        type="warning"
                        message="该候选未满足 RAG 入库门禁"
                        description="抽取质量、Markdown/纯文本长度或 artifact 错误未达标时，不允许自动写入共享知识库。"
                    />
                ) : null}
                {isDuplicate ? (
                    <Alert
                        showIcon
                        type="info"
                        message="重复内容"
                        description={candidate.rag_doc_id ? "该候选已有 RAG 文档，可查看既有入库结果。" : "该候选内容重复，但尚未发现 RAG 文档，可按需重新入库。"}
                    />
                ) : null}

                <Tabs
                    items={[
                        {
                            key: "overview",
                            label: "概览",
                            children: (
                                <Descriptions bordered size="small" column={2}>
                                    <Descriptions.Item label="标题" span={2}>{candidate.title || "-"}</Descriptions.Item>
                                    <Descriptions.Item label="URL" span={2}>
                                        <Typography.Link href={candidate.url} target="_blank" rel="noreferrer">
                                            <LinkOutlined /> {candidate.url}
                                        </Typography.Link>
                                    </Descriptions.Item>
                                    <Descriptions.Item label="来源">{candidate.source_id}</Descriptions.Item>
                                    <Descriptions.Item label="状态">{candidate.status}</Descriptions.Item>
                                    <Descriptions.Item label="抓取时间">{candidate.fetched_at || "-"}</Descriptions.Item>
                                    <Descriptions.Item label="内容类型">{candidate.content_type || "-"}</Descriptions.Item>
                                    <Descriptions.Item label="Hash" span={2}>
                                        <Typography.Text code copyable>{candidate.content_hash}</Typography.Text>
                                    </Descriptions.Item>
                                    <Descriptions.Item label="命中关键词" span={2}>
                                        <Space size={4} wrap>
                                            {(candidate.matched_keywords ?? []).length > 0
                                                ? candidate.matched_keywords?.map((keyword) => <Tag key={keyword}>{keyword}</Tag>)
                                                : "-"}
                                        </Space>
                                    </Descriptions.Item>
                                    <Descriptions.Item label="跳过原因">{candidate.skip_reason || "-"}</Descriptions.Item>
                                    <Descriptions.Item label="重复原因">{duplicateReason || "-"}</Descriptions.Item>
                                </Descriptions>
                            ),
                        },
                        {
                            key: "artifact",
                            label: "抓取文件",
                            children: (
                                <Space direction="vertical" size={12} style={{ width: "100%" }}>
                                    <Typography.Paragraph type="secondary">
                                        这里展示 artifact 摘要；点击“查看抓取文件”会打开统一文件预览抽屉，查看 Markdown、纯文本、原始 HTML 和已入库片段。
                                    </Typography.Paragraph>
                                    <Descriptions bordered size="small" column={2}>
                                        <Descriptions.Item label="Markdown 大小">{markdownSize} B</Descriptions.Item>
                                        <Descriptions.Item label="纯文本大小">{cleanedSize} B</Descriptions.Item>
                                        <Descriptions.Item label="预计片段">{estimatedChunkCount}</Descriptions.Item>
                                        <Descriptions.Item label="artifact 错误">
                                            {(candidate.artifact_errors ?? []).length > 0 ? candidate.artifact_errors?.join("；") : "-"}
                                        </Descriptions.Item>
                                    </Descriptions>
                                    <Button icon={<EyeOutlined />} onClick={() => onPreviewFile(candidate)}>
                                        打开统一文件预览
                                    </Button>
                                </Space>
                            ),
                        },
                        {
                            key: "rag",
                            label: "RAG 入库",
                            children: (
                                <Descriptions bordered size="small" column={2}>
                                    <Descriptions.Item label="KB ID">{candidate.rag_kb_id || "-"}</Descriptions.Item>
                                    <Descriptions.Item label="Doc ID">{candidate.rag_doc_id || "-"}</Descriptions.Item>
                                    <Descriptions.Item label="Pipeline">{candidate.rag_pipeline_status || "未发布"}</Descriptions.Item>
                                    <Descriptions.Item label="Indexed Chunks">{candidate.rag_indexed_chunk_count ?? 0}</Descriptions.Item>
                                    <Descriptions.Item label="Search Smoke">{candidate.rag_search_smoke_passed === null ? "-" : String(candidate.rag_search_smoke_passed)}</Descriptions.Item>
                                    <Descriptions.Item label="错误阶段">{candidate.rag_error_stage || "-"}</Descriptions.Item>
                                    <Descriptions.Item label="错误详情" span={2}>{candidate.rag_error_detail || "-"}</Descriptions.Item>
                                </Descriptions>
                            ),
                        },
                        {
                            key: "quality",
                            label: "质量诊断",
                            children: (
                                <Space direction="vertical" size={12} style={{ width: "100%" }}>
                                    <Descriptions bordered size="small" column={2}>
                                        <Descriptions.Item label="综合质量">{candidate.candidate_quality_score ?? "-"}</Descriptions.Item>
                                        <Descriptions.Item label="抽取质量">{candidate.extraction_quality_score ?? "-"}</Descriptions.Item>
                                        <Descriptions.Item label="主题相关">{candidate.topic_relevance_score ?? "-"}</Descriptions.Item>
                                        <Descriptions.Item label="主题分类">{candidate.topic_class || "-"}</Descriptions.Item>
                                        <Descriptions.Item label="Markdown 大小">{markdownSize} B</Descriptions.Item>
                                        <Descriptions.Item label="纯文本大小">{cleanedSize} B</Descriptions.Item>
                                    </Descriptions>
                                    <pre className="admin-crawler-drawer-json">
                                        {JSON.stringify(candidate.quality_breakdown ?? metadata.quality_breakdown ?? {}, null, 2)}
                                    </pre>
                                </Space>
                            ),
                        },
                        {
                            key: "metadata",
                            label: "原始元数据",
                            children: (
                                <pre className="admin-crawler-drawer-json">
                                    {JSON.stringify(metadata, null, 2)}
                                </pre>
                            ),
                        },
                    ]}
                />

                <Space size={8} wrap>
                    <Button
                        type="primary"
                        disabled={candidate.status === "rejected" || artifactBlocked}
                        loading={reviewingCandidateId === candidate.candidate_id}
                        onClick={() => onPublishToRag(candidate.candidate_id)}
                    >
                        {publishLabel}
                    </Button>
                    <Button loading={reviewingCandidateId === candidate.candidate_id} onClick={() => onPublishLegacy(candidate.candidate_id)}>
                        旧知识条目发布
                    </Button>
                </Space>
            </Space>
        </Drawer>
    );
}
