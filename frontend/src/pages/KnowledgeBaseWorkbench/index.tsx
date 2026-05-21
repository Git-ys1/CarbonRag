import {
    ApiOutlined,
    CloudUploadOutlined,
    DatabaseOutlined,
    FileSearchOutlined,
    PartitionOutlined,
    PlayCircleOutlined,
    PlusOutlined,
    SearchOutlined,
} from "@ant-design/icons";
import { Alert, Button, Card, Empty, Input, List, Progress, Select, Space, Spin, Tabs, Tag, Typography, Upload } from "antd";
import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { useSettings } from "../../app/SettingsContext";
import { FilePreviewDrawer } from "../../components/FilePreviewDrawer";
import {
    chunkKbDocument,
    createKbDocument,
    createKnowledgeBase,
    deleteKbDocument,
    indexKbDocument,
    listKbDocumentChunks,
    listKbDocuments,
    listKnowledgeBases,
    parseKbDocument,
    rebuildKbDocumentIndex,
    runKbDocumentPipeline,
    runKbDocumentPipelineBatch,
    uploadKbDocument,
} from "../../services/kb";
import { listAttachableKnowledgeItems } from "../../services/knowledge";
import { runRagEval, runRagTestQA, searchRagSpine } from "../../services/rag";
import type { KnowledgeItem } from "../../types/knowledge";
import type { FilePreviewTarget } from "../../types/filePreview";
import type { KnowledgeBase, RagChunk, RagDocument, RagDocumentStatus, RagEvalRun, RagHit, RagPipelineBatchResult, RagPipelineMode, RagPipelineResult, RagSearchResult, RagTestQAResult, RagTimingTrace } from "../../types/kb";

type StageName = "parse" | "chunk" | "index";

const stageMeta: Record<StageName, { label: string; shortLabel: string; hint: string; icon: ReactNode }> = {
    parse: {
        label: "解析文档",
        shortLabel: "解析",
        hint: "读取原始文件或知识条目的正文，形成可处理文本。",
        icon: <FileSearchOutlined />,
    },
    chunk: {
        label: "生成片段",
        shortLabel: "分块",
        hint: "把长文档切成可检索的小段，并保留页码、表格、章节等定位信息。",
        icon: <PartitionOutlined />,
    },
    index: {
        label: "写入向量库",
        shortLabel: "入库",
        hint: "用 BGE-M3 生成向量并写入 Milvus，之后才能被 RAG 问答命中。",
        icon: <CloudUploadOutlined />,
    },
};

const statusLabelMap: Record<string, string> = {
    uploaded: "已导入，待解析",
    pending: "待处理",
    queued: "排队中",
    running: "处理中",
    parsing: "解析中",
    parsed: "已解析",
    chunked: "已分块",
    indexed: "已入库，可检索",
    failed: "失败",
    parse_failed: "解析失败",
    chunk_failed: "分块失败",
    index_failed: "入库失败",
};

const sourceTypeLabelMap: Record<string, string> = {
    manual: "手动文本",
    private_upload: "个人上传",
    private_sample: "知识条目",
    public_policy: "公共政策",
};

export function KnowledgeBaseWorkbench() {
    const navigate = useNavigate();
    const { getActiveProviderOverride } = useSettings();
    const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
    const [activeKbId, setActiveKbId] = useState<string | undefined>();
    const [activeDocId, setActiveDocId] = useState<string | undefined>();
    const [documents, setDocuments] = useState<RagDocument[]>([]);
    const [chunks, setChunks] = useState<RagChunk[]>([]);
    const [knowledgeItems, setKnowledgeItems] = useState<KnowledgeItem[]>([]);
    const [newKbName, setNewKbName] = useState("企业知识库");
    const [selectedKnowledgeItemId, setSelectedKnowledgeItemId] = useState<string | undefined>();
    const [query, setQuery] = useState("双碳目标有哪些关键要求？");
    const [searchResult, setSearchResult] = useState<RagSearchResult | null>(null);
    const [qaResult, setQaResult] = useState<RagTestQAResult | null>(null);
    const [evalResult, setEvalResult] = useState<RagEvalRun | null>(null);
    const [pipelineResult, setPipelineResult] = useState<RagPipelineResult | null>(null);
    const [pipelineBatchResult, setPipelineBatchResult] = useState<RagPipelineBatchResult | null>(null);
    const [loading, setLoading] = useState(false);
    const [runningStage, setRunningStage] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [filePreviewTarget, setFilePreviewTarget] = useState<FilePreviewTarget | null>(null);

    const activeKb = useMemo(() => kbs.find((item) => item.kb_id === activeKbId), [activeKbId, kbs]);
    const activeDoc = useMemo(() => documents.find((item) => item.doc_id === activeDocId), [activeDocId, documents]);

    useEffect(() => {
        void bootstrap();
    }, []);

    useEffect(() => {
        if (activeKbId) {
            void loadDocuments(activeKbId);
        }
    }, [activeKbId]);

    async function bootstrap() {
        setLoading(true);
        setError(null);
        try {
            const [nextKbs, items] = await Promise.all([listKnowledgeBases(), listAttachableKnowledgeItems()]);
            setKbs(nextKbs);
            setActiveKbId(nextKbs[0]?.kb_id);
            setKnowledgeItems(items);
        } catch {
            setError("当前无法加载知识库工作台。请确认后端已启动，并且你已经登录。");
        } finally {
            setLoading(false);
        }
    }

    async function loadDocuments(kbId: string, preferredDocId?: string) {
        setLoading(true);
        setError(null);
        try {
            const docs = await listKbDocuments(kbId);
            setDocuments(docs);
            const nextActiveDocId =
                preferredDocId && docs.some((doc) => doc.doc_id === preferredDocId)
                    ? preferredDocId
                    : docs[0]?.doc_id;
            setActiveDocId(nextActiveDocId);
            if (nextActiveDocId) {
                setChunks(await listKbDocumentChunks(kbId, nextActiveDocId));
            } else {
                setChunks([]);
            }
        } catch {
            setError("当前无法加载知识库文档。请确认该知识库仍存在，且你有访问权限。");
        } finally {
            setLoading(false);
        }
    }

    async function handleCreateKb() {
        if (!newKbName.trim()) {
            return;
        }
        const kb = await createKnowledgeBase({ name: newKbName.trim() });
        setKbs((current) => [kb, ...current]);
        setActiveKbId(kb.kb_id);
    }

    async function handleImportKnowledgeItem() {
        if (!activeKbId || !selectedKnowledgeItemId) {
            return;
        }
        const doc = await createKbDocument(activeKbId, { knowledge_item_id: selectedKnowledgeItemId });
        setDocuments((current) => [doc, ...current]);
        setActiveDocId(doc.doc_id);
        setChunks([]);
    }

    async function handleUploadToKb(file: File) {
        if (!activeKbId) {
            setError("请先选择或创建知识库。");
            return false;
        }
        setRunningStage(`upload:${file.name}`);
        setError(null);
        try {
            const doc = await uploadKbDocument(activeKbId, file);
            setDocuments((current) => [doc, ...current]);
            setActiveDocId(doc.doc_id);
            setChunks([]);
        } catch {
            setError("上传到知识库失败。请确认文件格式受支持，且后端文件解析服务正常。");
        } finally {
            setRunningStage(null);
        }
        return false;
    }

    async function handleLoadChunks(doc: RagDocument) {
        if (!activeKbId) {
            return;
        }
        setActiveDocId(doc.doc_id);
        setChunks(await listKbDocumentChunks(activeKbId, doc.doc_id));
    }

    async function handleDeleteDocument(doc: RagDocument) {
        if (!activeKbId) {
            return;
        }
        const confirmed = window.confirm(`确认删除文档“${doc.title}”？这会同步删除该文档片段和向量，不影响同知识库其他文档。`);
        if (!confirmed) {
            return;
        }
        setRunningStage(`${doc.doc_id}:delete`);
        setError(null);
        try {
            await deleteKbDocument(activeKbId, doc.doc_id);
            const nextDocs = documents.filter((item) => item.doc_id !== doc.doc_id);
            setDocuments(nextDocs);
            const nextDocId = nextDocs[0]?.doc_id;
            setActiveDocId(nextDocId);
            setChunks(nextDocId ? await listKbDocumentChunks(activeKbId, nextDocId) : []);
            setKbs(await listKnowledgeBases());
        } catch {
            setError("删除文档失败。系统自动维护知识库或共享知识库可能是只读的。");
        } finally {
            setRunningStage(null);
        }
    }

    async function handleRebuildDocumentIndex(doc: RagDocument) {
        if (!activeKbId) {
            return;
        }
        setRunningStage(`${doc.doc_id}:rebuild-index`);
        setError(null);
        try {
            const next = await rebuildKbDocumentIndex(activeKbId, doc.doc_id);
            setDocuments((current) => current.map((item) => item.doc_id === next.doc_id ? next : item));
            setActiveDocId(next.doc_id);
            setChunks(await listKbDocumentChunks(activeKbId, next.doc_id));
            setKbs(await listKnowledgeBases());
        } catch {
            setError("重建索引失败。请确认文档已分块，且 Milvus / BGE 模型可用。");
        } finally {
            setRunningStage(null);
        }
    }

    async function runDocStage(doc: RagDocument, stage: StageName) {
        if (!activeKbId) {
            return;
        }
        setRunningStage(`${doc.doc_id}:${stage}`);
        setError(null);
        try {
            const next =
                stage === "parse"
                    ? await parseKbDocument(activeKbId, doc.doc_id)
                    : stage === "chunk"
                        ? await chunkKbDocument(activeKbId, doc.doc_id)
                        : await indexKbDocument(activeKbId, doc.doc_id);
            setDocuments((current) => current.map((item) => item.doc_id === next.doc_id ? next : item));
            setActiveDocId(next.doc_id);
            setChunks(await listKbDocumentChunks(activeKbId, next.doc_id));
        } catch {
            setError(`${stageMeta[stage].label}失败。请检查文档状态、后端日志、Milvus/Docker 是否正常运行。`);
        } finally {
            setRunningStage(null);
        }
    }

    async function runDocPipeline(doc: RagDocument, pipelineMode: RagPipelineMode = "quick") {
        if (!activeKbId) {
            return;
        }
        setRunningStage(`${doc.doc_id}:${pipelineMode === "acceptance" ? "pipeline-acceptance" : "pipeline"}`);
        setError(null);
        setPipelineBatchResult(null);
        try {
            const result = await runKbDocumentPipeline(activeKbId, doc.doc_id, pipelineMode);
            setPipelineResult(result);
            setDocuments((current) => mergePipelineResultsIntoDocuments(current, [result]));
            await loadDocuments(activeKbId, doc.doc_id);
            setActiveDocId(doc.doc_id);
            setChunks(await listKbDocumentChunks(activeKbId, doc.doc_id));
            window.setTimeout(() => {
                void loadDocuments(activeKbId, doc.doc_id);
            }, 800);
            if (pipelineMode === "acceptance" && result.eval_passed !== null && result.eval_passed !== undefined) {
                await handleEval();
            }
        } catch {
            setError(`${pipelineMode === "acceptance" ? "完整验收 RAG" : "快速建立 RAG"}失败。请查看失败阶段、后端日志、Milvus/Docker 与 BGE 模型状态。`);
        } finally {
            setRunningStage(null);
        }
    }

    async function runPipelineBatch() {
        if (!activeKbId) {
            return;
        }
        setRunningStage(`${activeKbId}:pipeline-batch`);
        setError(null);
        setPipelineResult(null);
        try {
            const result = await runKbDocumentPipelineBatch(activeKbId, undefined, "quick");
            setPipelineBatchResult(result);
            setDocuments((current) => mergePipelineResultsIntoDocuments(current, result.results));
            await loadDocuments(activeKbId, activeDocId ?? result.results[0]?.doc_id);
            window.setTimeout(() => {
                void loadDocuments(activeKbId, activeDocId ?? result.results[0]?.doc_id);
            }, 800);
        } catch {
            setError("批量快速建立 RAG 失败。请确认当前知识库有待处理文档，且后端服务可用。");
        } finally {
            setRunningStage(null);
        }
    }

    async function handleSearch() {
        if (!query.trim()) {
            return;
        }
        setLoading(true);
        setError(null);
        try {
            const result = await searchRagSpine({ query, kb_id: activeKbId, mode: "hybrid_rerank" });
            setSearchResult(result);
            setQaResult(null);
        } catch {
            setError("检索测试失败。请确认文档已写入向量库，并且 Docker Milvus / BGE 模型可用。");
        } finally {
            setLoading(false);
        }
    }

    async function handleTestQA() {
        if (!query.trim()) {
            return;
        }
        setLoading(true);
        setError(null);
        try {
            const result = await runRagTestQA({
                query,
                kb_id: activeKbId,
                mode: "hybrid_rerank",
                provider_override: getActiveProviderOverride(),
            });
            setQaResult(result);
            setSearchResult(null);
        } catch {
            setError("检索问答测试失败。请先确认检索测试能命中片段。");
        } finally {
            setLoading(false);
        }
    }

    async function handleEval() {
        if (!activeKbId) {
            return;
        }
        setLoading(true);
        setError(null);
        try {
            setEvalResult(await runRagEval({ kb_id: activeKbId, mode: "hybrid_rerank", top_k: 5 }));
        } catch {
            setError("RAG 验收评分失败。请确认青木验收文档已入库并完成向量化。");
        } finally {
            setLoading(false);
        }
    }

    function openAskPageWithCurrentKb() {
        const params = new URLSearchParams();
        if (activeKbId) {
            params.set("kb_id", activeKbId);
        }
        params.set("rag_mode", "hybrid_rerank");
        if (query.trim()) {
            params.set("question", query.trim());
        }
        navigate(`/?${params.toString()}`);
    }

    const indexedDocCount = documents.filter((doc) => doc.index_status === "indexed").length;
    const failedDocCount = documents.filter((doc) => doc.status === "failed" || doc.error_stage).length;
    const totalChunkCount = documents.reduce((sum, doc) => sum + (doc.chunk_count ?? 0), 0);
    const totalIndexedChunkCount = documents.reduce((sum, doc) => sum + (doc.indexed_chunk_count ?? 0), 0);

    return (
        <div className="kb-console">
            <Card className="admin-console__hero kb-console__hero">
                <div className="admin-console__hero-layout">
                    <div className="admin-console__hero-copy">
                        <Typography.Text className="admin-console__eyebrow">知识库 · 入库与评测</Typography.Text>
                        <Typography.Title level={2}>把文档上传、检索和问答验收收进一条主线</Typography.Title>
                        <Typography.Paragraph>
                            左侧管理知识库和文档，右侧处理当前文档、测试检索、查看片段和验收评分。默认使用“快速建立 RAG”，完整验收需要显式运行，避免小文件也卡在评测和大模型调用上。
                        </Typography.Paragraph>
                    </div>
                    <Space className="admin-console__actions kb-console__hero-actions" size={10} wrap>
                        <Input value={newKbName} onChange={(event) => setNewKbName(event.target.value)} placeholder="新知识库名称" style={{ width: 180 }} />
                        <Button icon={<PlusOutlined />} type="primary" onClick={handleCreateKb}>创建知识库</Button>
                        <Select
                            value={activeKbId}
                            onChange={setActiveKbId}
                            style={{ minWidth: 260 }}
                            options={kbs.map((kb) => ({ value: kb.kb_id, label: `${kb.name}${kb.is_default ? " · 默认" : ""}` }))}
                            placeholder="选择知识库"
                        />
                    </Space>
                </div>
                {error ? <Alert type="error" showIcon message={error} className="admin-console__alert" /> : null}
            </Card>

            <div className="admin-console__summary kb-console__summary">
                <Card className="admin-summary-card">
                    <div className="admin-summary-card__icon"><DatabaseOutlined /></div>
                    <div>
                        <Typography.Text type="secondary">当前知识库</Typography.Text>
                        <Typography.Title level={4}>{activeKb?.name ?? "未选择"}</Typography.Title>
                    </div>
                    <Typography.Text type="secondary">{activeKb ? `${activeKb.embedding_model} · topK ${activeKb.retrieval_top_k}` : "先创建或选择一个知识库"}</Typography.Text>
                </Card>
                <Card className="admin-summary-card">
                    <div className="admin-summary-card__icon"><FileSearchOutlined /></div>
                    <div>
                        <Typography.Text type="secondary">文档</Typography.Text>
                        <Typography.Title level={4}>{documents.length}</Typography.Title>
                    </div>
                    <Typography.Text type="secondary">{indexedDocCount} 个已入库，{failedDocCount} 个失败</Typography.Text>
                </Card>
                <Card className="admin-summary-card">
                    <div className="admin-summary-card__icon"><PartitionOutlined /></div>
                    <div>
                        <Typography.Text type="secondary">片段</Typography.Text>
                        <Typography.Title level={4}>{totalChunkCount}</Typography.Title>
                    </div>
                    <Typography.Text type="secondary">已写入向量库 {totalIndexedChunkCount} 个</Typography.Text>
                </Card>
                <Card className="admin-summary-card">
                    <div className="admin-summary-card__icon"><ApiOutlined /></div>
                    <div>
                        <Typography.Text type="secondary">验收入口</Typography.Text>
                        <Typography.Title level={4}>{evalResult ? (evalResult.passed ? "通过" : "未通过") : "待运行"}</Typography.Title>
                    </div>
                    <Typography.Text type="secondary">Test QA、AskPage 和评分共用当前 KB</Typography.Text>
                </Card>
            </div>

            <Card className="admin-panel-card kb-console__folder-card" title="知识库文件夹">
                <List
                    grid={{ gutter: 12, xs: 1, sm: 2, lg: 3, xl: 4 }}
                    dataSource={kbs}
                    locale={{ emptyText: <Empty description="暂无知识库文件夹。" /> }}
                    renderItem={(kb) => (
                        <List.Item>
                            <Card
                                size="small"
                                hoverable
                                className={kb.kb_id === activeKbId ? "kb-folder-card kb-folder-card--active" : "kb-folder-card"}
                                onClick={() => setActiveKbId(kb.kb_id)}
                            >
                                <Space direction="vertical" size={8} style={{ width: "100%" }}>
                                    <Space wrap>
                                        <DatabaseOutlined />
                                        <Typography.Text strong ellipsis style={{ maxWidth: 180 }}>{kb.name}</Typography.Text>
                                        {kb.system_managed ? <Tag color="green">系统自动维护</Tag> : null}
                                        {kb.visibility === "shared" ? <Tag color="blue">共享</Tag> : <Tag>个人</Tag>}
                                    </Space>
                                    <Typography.Text type="secondary">
                                        {kb.document_count ?? 0} 文档 · {kb.indexed_chunk_count ?? 0}/{kb.chunk_count ?? 0} 片段已入库
                                    </Typography.Text>
                                    <Space wrap>
                                        <Tag color={kb.health_status === "healthy" ? "green" : kb.health_status === "failed" ? "red" : "default"}>
                                            {kb.health_status ?? "unknown"}
                                        </Tag>
                                        <Tag>{kb.kb_scope ?? (kb.system_managed ? "system" : "personal")}</Tag>
                                        {kb.managed_by ? <Tag>{kb.managed_by}</Tag> : null}
                                    </Space>
                                </Space>
                            </Card>
                        </List.Item>
                    )}
                />
            </Card>

            <div className="kb-console__workspace-grid">
                <Card
                    className="admin-panel-card kb-console__documents-card"
                    title="知识库与文档"
                    extra={loading ? <Spin size="small" /> : null}
                >
                    <Space direction="vertical" size={12} style={{ width: "100%" }}>
                        <Upload
                            showUploadList={false}
                            beforeUpload={(file) => {
                                void handleUploadToKb(file);
                                return false;
                            }}
                        >
                            <Button block type="primary" icon={<CloudUploadOutlined />} loading={Boolean(runningStage?.startsWith("upload:"))}>
                                直接上传到当前知识库
                            </Button>
                        </Upload>
                        <Space.Compact style={{ width: "100%" }}>
                            <Select
                                showSearch
                                value={selectedKnowledgeItemId}
                                onChange={setSelectedKnowledgeItemId}
                                style={{ width: "100%" }}
                                optionFilterProp="label"
                                placeholder="从已有上传文件或知识条目导入"
                                options={knowledgeItems.map((item) => ({ value: item.knowledge_item_id, label: item.title }))}
                            />
                            <Button onClick={handleImportKnowledgeItem} disabled={!activeKbId || !selectedKnowledgeItemId}>导入</Button>
                        </Space.Compact>
                        <Button
                            block
                            icon={<PlayCircleOutlined />}
                            onClick={runPipelineBatch}
                            disabled={!activeKbId || documents.length === 0}
                            loading={Boolean(runningStage?.endsWith(":pipeline-batch"))}
                        >
                            批量快速建立 RAG
                        </Button>
                        {pipelineBatchResult ? <PipelineBatchResultAlert result={pipelineBatchResult} /> : null}
                        {documents.length ? (
                            <List
                                className="kb-console__document-list"
                                dataSource={documents}
                                renderItem={(doc) => (
                                    <List.Item
                                        className={doc.doc_id === activeDocId ? "kb-document-item kb-document-item--active" : "kb-document-item"}
                                        onClick={() => void handleLoadChunks(doc)}
                                    >
                                        <List.Item.Meta
                                            avatar={<FileSearchOutlined />}
                                            title={<Space wrap>{doc.title}<StatusTag status={doc.status} /></Space>}
                                            description={
                                                <Space direction="vertical" size={4} style={{ width: "100%" }}>
                                                    <Typography.Text type="secondary">
                                                        解析 {statusLabel(doc.parse_status)} · 分块 {statusLabel(doc.chunk_status)} · 入库 {statusLabel(doc.index_status)}
                                                    </Typography.Text>
                                                    <Space wrap>
                                                        <Tag>{doc.chunk_count ?? 0} 片段</Tag>
                                                        <Tag color={(doc.indexed_chunk_count ?? 0) > 0 ? "green" : "default"}>{doc.indexed_chunk_count ?? 0} 已入库</Tag>
                                                        {doc.error_stage ? <Tag color="red">{pipelineStageLabel(doc.error_stage)}</Tag> : null}
                                                        <Button
                                                            size="small"
                                                            type="link"
                                                            onClick={(event) => {
                                                                event.stopPropagation();
                                                                setFilePreviewTarget({ sourceType: "rag_document", sourceId: doc.doc_id, kbId: doc.kb_id });
                                                            }}
                                                        >
                                                            查看文件
                                                        </Button>
                                                        <Button
                                                            size="small"
                                                            type="link"
                                                            loading={runningStage === `${doc.doc_id}:rebuild-index`}
                                                            onClick={(event) => {
                                                                event.stopPropagation();
                                                                void handleRebuildDocumentIndex(doc);
                                                            }}
                                                        >
                                                            重建索引
                                                        </Button>
                                                        <Button
                                                            size="small"
                                                            type="link"
                                                            danger
                                                            loading={runningStage === `${doc.doc_id}:delete`}
                                                            disabled={Boolean(activeKb?.system_managed)}
                                                            onClick={(event) => {
                                                                event.stopPropagation();
                                                                void handleDeleteDocument(doc);
                                                            }}
                                                        >
                                                            删除
                                                        </Button>
                                                    </Space>
                                                </Space>
                                            }
                                        />
                                    </List.Item>
                                )}
                            />
                        ) : <Empty description="暂无文档。上传文件或导入已有知识条目后，会出现在这里。" />}
                    </Space>
                </Card>

                <Card className="admin-panel-card kb-console__detail-card">
                    <Tabs
                        className="kb-console__tabs"
                        items={[
                            {
                                key: "pipeline",
                                label: "入库验收",
                                children: (
                                    activeDoc ? (
                                        <Space direction="vertical" size={14} style={{ width: "100%" }}>
                                            <div className="kb-console__section-head">
                                                <div>
                                                    <Typography.Title level={4}>{activeDoc.title}</Typography.Title>
                                                    <Typography.Paragraph type="secondary">
                                                        推荐先跑“快速建立 RAG”。如果需要正式验收，再运行“完整验收 RAG”或右侧评分面板。
                                                    </Typography.Paragraph>
                                                </div>
                                                <Button
                                                    type="primary"
                                                    icon={<PlayCircleOutlined />}
                                                    loading={runningStage === `${activeDoc.doc_id}:pipeline`}
                                                    onClick={() => runDocPipeline(activeDoc, "quick")}
                                                >
                                                    {activeDoc.error_stage ? "重试失败阶段" : "快速建立 RAG"}
                                                </Button>
                                                <Button
                                                    icon={<PlayCircleOutlined />}
                                                    loading={runningStage === `${activeDoc.doc_id}:pipeline-acceptance`}
                                                    onClick={() => runDocPipeline(activeDoc, "acceptance")}
                                                >
                                                    完整验收 RAG
                                                </Button>
                                            </div>
                                            <DocumentStatusSummary doc={activeDoc} />
                                            <Space wrap>
                                                <Button
                                                    icon={stageMeta.parse.icon}
                                                    loading={runningStage === `${activeDoc.doc_id}:parse`}
                                                    onClick={() => runDocStage(activeDoc, "parse")}
                                                >
                                                    {stageMeta.parse.label}
                                                </Button>
                                                <Button
                                                    icon={stageMeta.chunk.icon}
                                                    loading={runningStage === `${activeDoc.doc_id}:chunk`}
                                                    disabled={!canRunChunk(activeDoc)}
                                                    onClick={() => runDocStage(activeDoc, "chunk")}
                                                >
                                                    {stageMeta.chunk.label}
                                                </Button>
                                                <Button
                                                    type="primary"
                                                    icon={stageMeta.index.icon}
                                                    loading={runningStage === `${activeDoc.doc_id}:index`}
                                                    disabled={!canRunIndex(activeDoc)}
                                                    onClick={() => runDocStage(activeDoc, "index")}
                                                >
                                                    {stageMeta.index.label}
                                                </Button>
                                                <Button onClick={() => handleLoadChunks(activeDoc)}>查看片段</Button>
                                                <Button onClick={() => setFilePreviewTarget({ sourceType: "rag_document", sourceId: activeDoc.doc_id, kbId: activeDoc.kb_id })}>查看文件</Button>
                                                <Button loading={runningStage === `${activeDoc.doc_id}:rebuild-index`} onClick={() => void handleRebuildDocumentIndex(activeDoc)}>重建索引</Button>
                                                <Button danger loading={runningStage === `${activeDoc.doc_id}:delete`} onClick={() => void handleDeleteDocument(activeDoc)}>删除文档</Button>
                                            </Space>
                                            {pipelineResult ? <PipelineResultAlert result={pipelineResult} /> : null}
                                        </Space>
                                    ) : <Empty description="先在左侧选择一个文档。" />
                                ),
                            },
                            {
                                key: "qa",
                                label: "检索问答",
                                children: (
                                    <Space direction="vertical" size={14} style={{ width: "100%" }}>
                                        <Alert
                                            type="warning"
                                            showIcon
                                            message="Test QA 是 RAG 链路验收，不是普通聊天页"
                                            description="先检索当前知识库，再基于命中片段生成可追溯回答。正式聊天请点击“去 AskPage 用大模型问”。"
                                        />
                                        <Space.Compact style={{ width: "100%" }}>
                                            <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="输入一个能在文档中找到依据的问题" />
                                            <Button icon={<SearchOutlined />} onClick={handleSearch} loading={loading}>只测检索</Button>
                                            <Button icon={<PlayCircleOutlined />} type="primary" onClick={handleTestQA} loading={loading}>生成测试回答</Button>
                                            <Button onClick={openAskPageWithCurrentKb}>去 AskPage</Button>
                                        </Space.Compact>
                                        {searchResult ? <TracePanel mode="search" hits={searchResult.hits} trace={searchResult.trace} /> : null}
                                        {qaResult ? (
                                            <Card size="small" title="测试回答">
                                                <Space wrap style={{ marginBottom: 10 }}>
                                                    <Tag color={qaModeColor(qaResult.answer_mode)}>{qaModeLabel(qaResult.answer_mode)}</Tag>
                                                    <Tag color={qaResult.provider_name ? "green" : "default"}>
                                                        {qaResult.provider_name ? `大模型：${qaResult.provider_name}` : "未调用大模型"}
                                                    </Tag>
                                                    {qaResult.model_name ? <Tag>{qaResult.model_name}</Tag> : null}
                                                    <Tag color={evidenceQualityColor(qaResult.evidence_quality)}>
                                                        证据质量：{evidenceQualityLabel(qaResult.evidence_quality)}
                                                    </Tag>
                                                    {typeof qaResult.confidence === "number" ? <Tag>可信度 {Math.round(qaResult.confidence * 100)}%</Tag> : null}
                                                    {qaResult.selected_chunks?.length ? <Tag color="blue">已选引用片段 {qaResult.selected_chunks.length}</Tag> : null}
                                                    {activeDoc ? (
                                                        <Button size="small" onClick={() => setFilePreviewTarget({ sourceType: "rag_document", sourceId: activeDoc.doc_id, kbId: activeDoc.kb_id })}>
                                                            查看文件
                                                        </Button>
                                                    ) : null}
                                                </Space>
                                                <Typography.Paragraph>{qaResult.answer}</Typography.Paragraph>
                                                <TracePanel mode="qa" hits={qaResult.hits} trace={qaResult.retrieval_trace} />
                                            </Card>
                                        ) : null}
                                    </Space>
                                ),
                            },
                            {
                                key: "chunks",
                                label: "片段预览",
                                children: (
                                    <Space direction="vertical" size={12} style={{ width: "100%" }}>
                                        <Typography.Paragraph type="secondary">
                                            片段是 RAG 真正检索的最小单位。Test QA 命中的不是整份文件，而是这些片段。
                                        </Typography.Paragraph>
                                        {activeDoc ? <Tag color="blue">当前文档：{activeDoc.title}</Tag> : null}
                                        {chunks.length ? (
                                            <List
                                                dataSource={chunks.slice(0, 8)}
                                                renderItem={(chunk) => (
                                                    <List.Item>
                                                        <Typography.Paragraph ellipsis={{ rows: 3, expandable: "collapsible", symbol: "展开" }}>
                                                            <Typography.Text type="secondary">片段 #{chunk.chunk_index} · {statusLabel(chunk.vector_status)}</Typography.Text>
                                                            <br />
                                                            {chunk.text}
                                                        </Typography.Paragraph>
                                                    </List.Item>
                                                )}
                                            />
                                        ) : <Empty description="选择文档并完成“生成片段”后，这里会显示可检索片段。" />}
                                    </Space>
                                ),
                            },
                            {
                                key: "eval",
                                label: "验收评分",
                                children: (
                                    <Space direction="vertical" size={12} style={{ width: "100%" }}>
                                        <Button onClick={handleEval} loading={loading} disabled={!activeKbId}>运行验收评分</Button>
                                        {evalResult ? <EvalPanel evalResult={evalResult} /> : (
                                            <Empty description="运行评分后，这里会显示 Hit@3、MRR、引用覆盖和跨库泄漏等门禁结果。" />
                                        )}
                                    </Space>
                                ),
                            },
                        ]}
                    />
                </Card>
            </div>
            <FilePreviewDrawer
                open={Boolean(filePreviewTarget)}
                target={filePreviewTarget}
                onClose={() => setFilePreviewTarget(null)}
            />
        </div>
    );
}

function DocumentStatusSummary({ doc }: { doc: RagDocument }) {
    const generatedCount = doc.chunk_count ?? 0;
    const indexedCount = doc.indexed_chunk_count ?? 0;
    return (
        <Space direction="vertical" size={6} className="kb-document-status">
            <Typography.Text type="secondary">
                {documentReadableSummary(doc)}
            </Typography.Text>
            <Space wrap>
                <Tag color={statusColor(doc.parse_status)}>解析：{statusLabel(doc.parse_status)}</Tag>
                <Tag color={statusColor(doc.chunk_status)}>分块：{statusLabel(doc.chunk_status)}</Tag>
                <Tag color={statusColor(doc.index_status)}>向量入库：{statusLabel(doc.index_status)}</Tag>
                <Tag>{vectorBackendLabel(doc.vector_backend)}</Tag>
                <Tag>片段 {generatedCount} 个，已入库 {indexedCount} 个</Tag>
                {doc.source_type ? <Tag>{sourceTypeLabelMap[doc.source_type] ?? doc.source_type}</Tag> : null}
            </Space>
            {doc.index_warnings?.length ? (
                <Alert type="warning" showIcon message={doc.index_warnings.map(humanizeWarning).join("；")} />
            ) : null}
            <Space wrap>
                <Progress size="small" percent={doc.parse_progress ?? parseProgressFromStatus(doc.parse_status)} style={{ width: 160 }} />
                <Typography.Text type="secondary">解析进度</Typography.Text>
                <Progress size="small" percent={doc.chunk_progress ?? chunkProgressFromStatus(doc.chunk_status)} style={{ width: 160 }} />
                <Typography.Text type="secondary">分块进度</Typography.Text>
            </Space>
        </Space>
    );
}

function StatusTag({ status }: { status: string }) {
    return <Tag color={statusColor(status)}>{statusLabel(status)}</Tag>;
}

function TracePanel({ hits, trace, mode }: { hits: RagHit[]; trace: RagSearchResult["trace"]; mode: "search" | "qa" }) {
    const noHits = hits.length === 0;
    return (
        <Space direction="vertical" size={10} style={{ width: "100%", marginTop: 12 }}>
            <Space wrap>
                <Tag color={trace.degraded ? "orange" : "green"}>向量库：{vectorBackendLabel(trace.vector_runtime ?? trace.vector_backend)}</Tag>
                <Tag color={trace.dense_count > 0 ? "geekblue" : "default"}>向量命中 {trace.dense_count}</Tag>
                <Tag color={trace.sparse_count > 0 ? "blue" : "default"}>关键词命中 {trace.sparse_count}</Tag>
                <Tag color={trace.merged_count > 0 ? "cyan" : "default"}>融合候选 {trace.merged_count}</Tag>
                <Tag color={trace.rerank_applied ? "green" : "default"}>重排序：{trace.rerank_applied ? "已执行" : "未执行"}</Tag>
            </Space>
            {trace.timing_trace ? <TimingTags timing={trace.timing_trace} /> : null}
            {trace.warnings?.length ? <Alert type="warning" showIcon message={trace.warnings.map(humanizeWarning).join("；")} /> : null}
            {noHits ? (
                <Empty
                    description={
                        mode === "search"
                            ? "没有检索到片段。请先确认文档已完成“写入向量库”，或换一个更贴近文档原文的问题。"
                            : "没有可引用片段，因此不会生成没有依据的 RAG 回答。"
                    }
                />
            ) : (
                <List
                    size="small"
                    dataSource={hits}
                    renderItem={(hit) => (
                        <List.Item>
                            <List.Item.Meta
                                title={<Space wrap>{hit.title}<Tag>{sourceTypeLabelMap[hit.source_type] ?? hit.source_type}</Tag>{hit.page_number ? <Tag>第 {hit.page_number} 页</Tag> : null}</Space>}
                                description={
                                    <Typography.Paragraph ellipsis={{ rows: 2, expandable: "collapsible", symbol: "展开" }}>
                                        {hit.snippet}
                                    </Typography.Paragraph>
                                }
                            />
                            <Typography.Text type="secondary" className="kb-hit-score">
                                向量 {formatScore(hit.dense_score)} · 关键词 {formatScore(hit.sparse_score)} · 融合 {formatScore(hit.rrf_score)} · 重排 {formatScore(hit.rerank_score)}
                            </Typography.Text>
                        </List.Item>
                    )}
                />
            )}
        </Space>
    );
}

function TimingTags({ timing }: { timing: RagTimingTrace }) {
    return (
        <Space wrap>
            <Tag>总耗时 {formatMs(timing.total_ms)}</Tag>
            <Tag>DB {formatMs(timing.db_load_chunks_ms)}</Tag>
            <Tag>BGE {formatMs(timing.embedding_ms)}</Tag>
            <Tag>Milvus 连接 {formatMs(timing.milvus_client_ms)} / 新建 {timing.milvus_client_init_count ?? 0}</Tag>
            <Tag>Milvus 检索 {formatMs(timing.milvus_search_ms)}</Tag>
            <Tag color={timing.sparse_cache_hit ? "green" : "default"}>关键词 {formatMs(timing.sparse_ms)} / 缓存 {timing.sparse_cache_hit ? "命中" : "未命中"}</Tag>
            <Tag>RRF {formatMs(timing.rrf_ms)}</Tag>
            <Tag>重排 {formatMs(timing.rerank_ms)}</Tag>
            <Tag>候选 {timing.loaded_chunk_count ?? 0}/{timing.dense_candidate_count ?? 0}/{timing.sparse_candidate_count ?? 0}/{timing.rrf_candidate_count ?? 0}</Tag>
        </Space>
    );
}

function mergePipelineResultsIntoDocuments(documents: RagDocument[], results: RagPipelineResult[]): RagDocument[] {
    const byDocId = new Map(results.map((result) => [result.doc_id, result]));
    return documents.map((doc) => {
        const result = byDocId.get(doc.doc_id);
        if (!result) {
            return doc;
        }
        const nextStatus = pipelineDocumentStatus(result);
        return {
            ...doc,
            status: nextStatus,
            parse_status: result.parse_status,
            chunk_status: result.chunk_status,
            index_status: result.index_status,
            chunk_count: result.chunk_count,
            indexed_chunk_count: result.indexed_chunk_count,
            parse_progress: result.parse_status === "parsed" ? 100 : doc.parse_progress,
            chunk_progress: result.chunk_status === "chunked" ? 100 : doc.chunk_progress,
            vector_backend: result.vector_runtime,
            degraded: result.degraded,
            error_stage: result.failed_stage,
            error_message: result.error_message,
            index_warnings: result.warnings,
        };
    });
}

function pipelineDocumentStatus(result: RagPipelineResult): RagDocumentStatus {
    if (result.failed_stage) {
        return "failed";
    }
    if (result.index_status === "indexed") {
        return "indexed";
    }
    if (result.chunk_status === "chunked") {
        return "chunked";
    }
    if (result.parse_status === "parsed") {
        return "parsed";
    }
    return "uploaded";
}

function EvalPanel({ evalResult }: { evalResult: RagEvalRun }) {
    const metrics = evalResult.metrics;
    const failedCases = evalResult.cases.filter((item) => item.hit === false);
    return (
        <Card size="small" title="验收评分" style={{ marginTop: 12 }}>
            <Space wrap>
                <Tag color={evalResult.passed ? "green" : "red"}>{evalResult.passed ? "通过" : "未通过"}</Tag>
                <Tag>Hit@3 {formatPercent(metrics.hit_at_3)}</Tag>
                <Tag>MRR {formatPercent(metrics.mrr)}</Tag>
                <Tag>引用覆盖 {formatPercent(metrics.citation_coverage)}</Tag>
                <Tag>跨库泄漏 {String(metrics.cross_kb_leak_count ?? 0)}</Tag>
                <Tag>向量失败 {String(metrics.vector_failure_count ?? 0)}</Tag>
            </Space>
            <Typography.Paragraph type="secondary" style={{ marginTop: 8 }}>
                通过线：Milvus Standalone、无降级、Hit@3 ≥ 85%、MRR ≥ 75%、引用覆盖 100%、跨库泄漏 0。
            </Typography.Paragraph>
            {failedCases.length ? (
                <Space direction="vertical" style={{ width: "100%" }}>
                    <Alert
                        type="error"
                        showIcon
                        message={`未通过问题 ${failedCases.length} 个`}
                        description="请按 expected keywords、actual topK snippets、跨库泄漏、向量失败或 rerank 失败逐项定位。"
                    />
                    <List
                        size="small"
                        dataSource={failedCases}
                        renderItem={(item) => (
                            <List.Item>
                                <Space direction="vertical" size={2}>
                                    <Typography.Text strong>
                                        {String(item.case_id ?? "eval-case")}：{String(item.question ?? "未命名问题")}
                                    </Typography.Text>
                                    <Typography.Text type="secondary">
                                        期望关键词：{formatCaseValue(item.expected_keywords ?? item.expected_chunk_keywords)}
                                    </Typography.Text>
                                    <Typography.Text type="secondary">
                                        实际 TopK：{formatCaseValue(item.actual_topk_snippets ?? item.topk_snippets ?? item.hits)}
                                    </Typography.Text>
                                    <Typography.Text type={item.cross_kb_leak ? "danger" : "secondary"}>
                                        跨库泄漏：{String(item.cross_kb_leak ?? false)}；向量失败：{String(item.vector_failure ?? false)}；重排序失败：{String(item.rerank_failed ?? false)}
                                    </Typography.Text>
                                </Space>
                            </List.Item>
                        )}
                    />
                </Space>
            ) : null}
        </Card>
    );
}

function formatCaseValue(value: unknown): string {
    if (Array.isArray(value)) {
        return value.map((item) => (typeof item === "object" ? JSON.stringify(item) : String(item))).join(" / ") || "-";
    }
    if (value && typeof value === "object") {
        return JSON.stringify(value);
    }
    return value === undefined || value === null || value === "" ? "-" : String(value);
}

function PipelineResultAlert({ result }: { result: RagPipelineResult }) {
    const passed = !result.failed_stage && !result.degraded && result.search_smoke_passed && result.eval_passed !== false;
    return (
        <Alert
            type={passed ? "success" : "warning"}
            showIcon
            className="kb-workbench__flow"
            message={passed ? `${pipelineModeLabel(result.pipeline_mode)}完成` : `${pipelineModeLabel(result.pipeline_mode)}需要处理：${pipelineStageLabel(result.failed_stage)}`}
            description={
                <Space direction="vertical" size={4}>
                    <Typography.Text>
                        解析：{statusLabel(result.parse_status)}；分块：{statusLabel(result.chunk_status)}；向量入库：{statusLabel(result.index_status)}；
                        片段 {result.chunk_count} 个，已入库 {result.indexed_chunk_count} 个；检索冒烟：{result.search_smoke_passed ? "通过" : "未通过"}；
                        验收评分：{result.eval_passed === null || result.eval_passed === undefined ? "未配置" : result.eval_passed ? "通过" : "未通过"}。
                    </Typography.Text>
                    {result.timing_trace ? <TimingTags timing={result.timing_trace} /> : null}
                    {result.error_message ? <Typography.Text type="danger">{result.error_message}</Typography.Text> : null}
                    {result.warnings?.length ? <Typography.Text type="secondary">{result.warnings.map(humanizeWarning).join("；")}</Typography.Text> : null}
                </Space>
            }
        />
    );
}

function PipelineBatchResultAlert({ result }: { result: RagPipelineBatchResult }) {
    return (
        <Alert
            type={result.failed_count === 0 ? "success" : "warning"}
            showIcon
            className="kb-workbench__flow"
            message={`批量快速建立 RAG：成功 ${result.succeeded_count} / ${result.total_count}`}
            description={result.failed_count ? `失败 ${result.failed_count} 个；请查看对应文档的失败阶段并点击“重试失败阶段”。` : "所有待处理文档已完成本轮 pipeline。"}
        />
    );
}

function pipelineStageLabel(value?: string | null) {
    if (!value) {
        return "无";
    }
    const labels: Record<string, string> = {
        parse: "解析文档",
        chunk: "生成片段",
        index: "写入向量库",
        search_smoke: "检索冒烟",
        eval_smoke: "验收评分",
    };
    return labels[value] ?? value;
}

function pipelineModeLabel(value?: string | null) {
    if (value === "acceptance") {
        return "完整验收 RAG";
    }
    return "快速建立 RAG";
}

function formatMs(value?: number | null) {
    if (typeof value !== "number") {
        return "-";
    }
    if (value >= 1000) {
        return `${(value / 1000).toFixed(2)}s`;
    }
    return `${Math.round(value)}ms`;
}

function canRunChunk(doc: RagDocument) {
    return ["parsed", "chunked", "indexed"].includes(doc.parse_status) || doc.chunk_count > 0;
}

function canRunIndex(doc: RagDocument) {
    return ["chunked", "indexed"].includes(doc.chunk_status) || doc.chunk_count > 0;
}

function parseProgressFromStatus(status?: string | null) {
    if (status === "parsed" || status === "indexed" || status === "chunked") return 100;
    if (status === "failed" || status === "parse_failed") return 0;
    return 0;
}

function chunkProgressFromStatus(status?: string | null) {
    if (status === "chunked" || status === "indexed") return 100;
    if (status === "failed" || status === "chunk_failed") return 0;
    return 0;
}

function documentReadableSummary(doc: RagDocument) {
    if (doc.status === "indexed" || doc.index_status === "indexed") {
        return "这份文档已写入向量库，可以被检索和 Test QA 命中。";
    }
    if (doc.chunk_status === "chunked" || doc.chunk_count > 0) {
        return "这份文档已经生成片段，下一步点击“写入向量库”。";
    }
    if (doc.parse_status === "parsed") {
        return "这份文档已经解析出正文，下一步点击“生成片段”。";
    }
    if (doc.status === "failed" || doc.parse_status.includes("failed") || doc.index_status.includes("failed")) {
        return doc.error_message ? `处理失败：${doc.error_message}` : "处理失败，请查看后端日志或重新导入。";
    }
    return "这份文档已导入，下一步点击“解析文档”。";
}

function statusLabel(status?: string | null) {
    if (!status) {
        return "未开始";
    }
    return statusLabelMap[status] ?? status;
}

function statusColor(status?: string | null) {
    if (!status) {
        return "default";
    }
    if (["indexed", "parsed", "chunked"].includes(status)) {
        return "green";
    }
    if (["failed", "parse_failed", "chunk_failed", "index_failed"].includes(status)) {
        return "red";
    }
    if (["running", "parsing", "queued"].includes(status)) {
        return "blue";
    }
    return "default";
}

function vectorBackendLabel(value?: string | null) {
    if (!value) {
        return "向量库：未写入";
    }
    const normalized = value.toLowerCase();
    if (normalized.includes("milvus_standalone") || normalized === "milvus") {
        return "Milvus Docker";
    }
    if (normalized.includes("milvus_lite")) {
        return "Milvus Lite";
    }
    if (normalized.includes("memory")) {
        return "内存开发模式";
    }
    if (normalized.includes("chroma")) {
        return "Chroma 兼容模式";
    }
    return value;
}

function qaModeLabel(value?: string | null) {
    if (value === "llm_grounded") {
        return "已调用大模型生成";
    }
    if (value === "retrieval_only") {
        return "仅检索，生成失败";
    }
    if (value === "no_hits") {
        return "无命中，未调用模型";
    }
    return "Test QA";
}

function qaModeColor(value?: string | null) {
    if (value === "llm_grounded") {
        return "green";
    }
    if (value === "retrieval_only") {
        return "orange";
    }
    if (value === "no_hits") {
        return "red";
    }
    return "default";
}

function evidenceQualityLabel(value?: string | null) {
    if (value === "strong") {
        return "强";
    }
    if (value === "usable") {
        return "可用";
    }
    if (value === "weak") {
        return "弱";
    }
    if (value === "none") {
        return "无";
    }
    return value || "未知";
}

function evidenceQualityColor(value?: string | null) {
    if (value === "strong") {
        return "green";
    }
    if (value === "usable") {
        return "blue";
    }
    if (value === "weak") {
        return "orange";
    }
    if (value === "none") {
        return "red";
    }
    return "default";
}

function humanizeWarning(value: string) {
    if (value.includes("BGE reranker local model is missing")) {
        const target = value.split("pre-download to ")[1];
        return target
            ? `BGE 重排序模型缺失；请先下载或解压到 ${target}`
            : "BGE 重排序模型缺失；请先下载或解压本地 reranker 模型。";
    }
    return value
        .replace(/no_hits/g, "没有命中片段")
        .replace(/rerank_disabled/g, "重排序已禁用")
        .replace(/bge_reranker_unavailable/g, "BGE 重排序不可用")
        .replace(/vector unavailable/g, "向量检索不可用")
        .replace(/fallback/g, "降级")
        .replace(/BGE/g, "BGE")
        .replace(/Milvus/g, "Milvus");
}

function formatScore(value?: number | null) {
    return typeof value === "number" ? value.toFixed(3) : "-";
}

function formatPercent(value: unknown) {
    return typeof value === "number" ? `${Math.round(value * 100)}%` : "-";
}
