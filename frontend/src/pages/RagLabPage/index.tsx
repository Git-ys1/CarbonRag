import {
    ApiOutlined,
    ClusterOutlined,
    DatabaseOutlined,
    ReloadOutlined,
    SearchOutlined,
} from "@ant-design/icons";
import {
    Alert,
    Button,
    Card,
    Descriptions,
    Empty,
    Input,
    List,
    Segmented,
    Select,
    Slider,
    Space,
    Spin,
    Statistic,
    Switch,
    Tag,
    Typography,
} from "antd";
import axios from "axios";
import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import env from "../../app/env";
import { listAttachableKnowledgeItems } from "../../services/knowledge";
import { retrieveRagEvidence } from "../../services/rag";
import type { KnowledgeItem } from "../../types/knowledge";
import type {
    RagEvidenceChunk,
    RagExperimentalRetrievalStrategy,
    RagGraphCandidate,
    RagGraphEntity,
    RagGraphMode,
    RagGraphRelation,
    RagGraphStatus,
    RagKnowledgeScope,
    RagQueryMode,
    RagRetrievalResult,
    RagRerankStatus,
    RagSourceType,
    RagVectorStatus,
} from "../../types/rag";

interface RagLabFormState {
    question: string;
    mode: RagQueryMode;
    retrieval_strategy: RagExperimentalRetrievalStrategy;
    graph_mode: RagGraphMode;
    knowledge_scope: RagKnowledgeScope;
    top_k: number;
    chunk_top_k: number;
    enable_rerank: boolean;
    include_references: boolean;
    allowed_knowledge_item_ids: string[];
    region?: string;
    doc_type?: string;
}

interface RagLabError {
    status?: number | null;
    message: string;
    detail?: string | null;
}

const initialFormState: RagLabFormState = {
    question: "2030年前碳达峰行动方案有哪些重点？",
    mode: "mix",
    retrieval_strategy: "bm25_only",
    graph_mode: "off",
    knowledge_scope: "mixed",
    top_k: 5,
    chunk_top_k: 8,
    enable_rerank: true,
    include_references: true,
    allowed_knowledge_item_ids: [],
};

export function RagLabPage() {
    const [formState, setFormState] = useState<RagLabFormState>(initialFormState);
    const [knowledgeItems, setKnowledgeItems] = useState<KnowledgeItem[]>([]);
    const [loadingKnowledgeItems, setLoadingKnowledgeItems] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [result, setResult] = useState<RagRetrievalResult | null>(null);
    const [ragError, setRagError] = useState<RagLabError | null>(null);

    const selectableKnowledgeItems = useMemo(
        () => knowledgeItems.filter((item) => item.is_enabled && item.session_attachable),
        [knowledgeItems],
    );

    useEffect(() => {
        void loadKnowledgeItems();
    }, []);

    useEffect(() => {
        if (formState.knowledge_scope === "public" && formState.allowed_knowledge_item_ids.length > 0) {
            setFormState((current) => ({ ...current, allowed_knowledge_item_ids: [] }));
        }
    }, [formState.knowledge_scope, formState.allowed_knowledge_item_ids.length]);

    async function loadKnowledgeItems() {
        setLoadingKnowledgeItems(true);
        setRagError(null);
        try {
            const items = await listAttachableKnowledgeItems();
            setKnowledgeItems(items);
        } catch (error) {
            setRagError(extractRagLabError(error, "当前无法加载可选知识条目。"));
        } finally {
            setLoadingKnowledgeItems(false);
        }
    }

    async function handleRetrieve() {
        const question = formState.question.trim();
        if (!question) {
            setRagError({ message: "问题不能为空。", detail: "query 为空，未发送 retrieval-only 请求。" });
            return;
        }

        setSubmitting(true);
        setRagError(null);
        try {
            const response = await retrieveRagEvidence({
                question,
                mode: formState.mode,
                retrieval_strategy: formState.retrieval_strategy,
                graph_mode: formState.graph_mode,
                knowledge_scope: formState.knowledge_scope,
                top_k: formState.top_k,
                chunk_top_k: formState.chunk_top_k,
                max_total_tokens: 30000,
                enable_rerank: formState.enable_rerank,
                include_references: formState.include_references,
                allowed_knowledge_item_ids:
                    formState.knowledge_scope === "public" ? [] : formState.allowed_knowledge_item_ids,
                region: formState.region ?? null,
                doc_type: formState.doc_type ?? null,
            });
            setResult(response);
        } catch (error) {
            setResult(null);
            setRagError(extractRagLabError(error, "当前 RAG 检索接口不可用。"));
        } finally {
            setSubmitting(false);
        }
    }

    function patchForm(next: Partial<RagLabFormState>) {
        setFormState((current) => ({ ...current, ...next }));
    }

    const metadata = result?.metadata;
    const backendBaseUrl = resolveBackendBaseUrl(env.apiBaseUrl);
    const retrievalEndpoint = `${env.apiBaseUrl.replace(/\/+$/, "")}/v1/rag/retrieve`;
    const requestPreview = buildRequestPreview(formState);
    const retrievalPath = metadata?.retrieval_path ?? metadata?.trace?.retrieval_path ?? [];
    const vectorStatus = metadata?.vector_status ?? "unavailable";
    const graphStatus = metadata?.graph_status ?? "unavailable";
    const rerankStatus = metadata?.rerank_status ?? "disabled";
    const effectiveRetrieverMode = resolveRetrieverMode(metadata, formState.mode);
    const fallbackUsed = metadata?.fallback_used ?? (metadata?.retriever_mode === "bm25_fallback");
    const providerMetadata = metadata?.provider_metadata ?? {};
    const latencyMs = metadata?.latency_ms ?? metadata?.trace?.latency_ms;

    return (
        <div className="rag-lab">
            <div className="rag-lab__controls">
                <Card
                    title="RAG 检索实验台"
                    extra={<Tag color="blue">V1.3</Tag>}
                >
                    <Space direction="vertical" size={16} style={{ width: "100%" }}>
                        <div className="rag-lab__endpoint">
                            <Typography.Text type="secondary">backendBaseUrl</Typography.Text>
                            <Typography.Text code copyable>{backendBaseUrl}</Typography.Text>
                            <Typography.Text type="secondary">API</Typography.Text>
                            <Typography.Text code copyable>{retrievalEndpoint}</Typography.Text>
                        </div>

                        <div className="rag-lab__field">
                            <Typography.Text strong>当前请求参数</Typography.Text>
                            <Descriptions bordered size="small" column={1}>
                                <Descriptions.Item label="query">
                                    <Typography.Text copyable>{requestPreview.query || "empty"}</Typography.Text>
                                </Descriptions.Item>
                                <Descriptions.Item label="top_k">{requestPreview.top_k}</Descriptions.Item>
                                <Descriptions.Item label="mode">{requestPreview.mode}</Descriptions.Item>
                                <Descriptions.Item label="retrieval_strategy">
                                    {requestPreview.retrieval_strategy}
                                </Descriptions.Item>
                                <Descriptions.Item label="graph_mode">
                                    {requestPreview.graph_mode}
                                </Descriptions.Item>
                                <Descriptions.Item label="use_public">
                                    <BooleanTag value={requestPreview.use_public} />
                                </Descriptions.Item>
                                <Descriptions.Item label="use_private">
                                    <BooleanTag value={requestPreview.use_private} />
                                </Descriptions.Item>
                            </Descriptions>
                        </div>

                        <div className="rag-lab__field">
                            <Typography.Text strong>检索问题</Typography.Text>
                            <Input.TextArea
                                value={formState.question}
                                onChange={(event) => patchForm({ question: event.target.value })}
                                autoSize={{ minRows: 4, maxRows: 8 }}
                                maxLength={2000}
                            />
                        </div>

                        <div className="rag-lab__field">
                            <Typography.Text strong>检索模式</Typography.Text>
                            <Segmented
                                block
                                value={formState.mode}
                                options={[
                                    { label: "Mix", value: "mix" },
                                    { label: "Naive", value: "naive" },
                                ]}
                                onChange={(value) => patchForm({ mode: value as RagQueryMode })}
                            />
                        </div>

                        <div className="rag-lab__field">
                            <Typography.Text strong>实验检索策略</Typography.Text>
                            <Segmented
                                block
                                value={formState.retrieval_strategy}
                                options={[
                                    { label: "BM25", value: "bm25_only" },
                                    { label: "Vector", value: "vector_only" },
                                    { label: "Hybrid", value: "bm25_vector_hybrid" },
                                ]}
                                onChange={(value) =>
                                    patchForm({ retrieval_strategy: value as RagExperimentalRetrievalStrategy })
                                }
                            />
                        </div>

                        <Alert
                            type="info"
                            showIcon
                            message="图谱检索为实验能力，不影响默认 /ask。"
                        />

                        <div className="rag-lab__field">
                            <Typography.Text strong>实验图谱模式</Typography.Text>
                            <Segmented
                                block
                                value={formState.graph_mode}
                                options={[
                                    { label: "Off", value: "off" },
                                    { label: "Local", value: "graph_local" },
                                    { label: "Global", value: "graph_global" },
                                    { label: "Hybrid", value: "graph_hybrid" },
                                ]}
                                onChange={(value) => patchForm({ graph_mode: value as RagGraphMode })}
                            />
                        </div>

                        <div className="rag-lab__field">
                            <Typography.Text strong>知识范围</Typography.Text>
                            <Segmented
                                block
                                value={formState.knowledge_scope}
                                options={[
                                    { label: "混合", value: "mixed" },
                                    { label: "公共", value: "public" },
                                    { label: "知识条目", value: "private_sample" },
                                ]}
                                onChange={(value) => patchForm({ knowledge_scope: value as RagKnowledgeScope })}
                            />
                        </div>

                        <div className="rag-lab__field">
                            <Typography.Text strong>候选知识条目</Typography.Text>
                            <Select
                                mode="multiple"
                                allowClear
                                loading={loadingKnowledgeItems}
                                disabled={formState.knowledge_scope === "public"}
                                value={formState.allowed_knowledge_item_ids}
                                onChange={(value) => patchForm({ allowed_knowledge_item_ids: value })}
                                options={selectableKnowledgeItems.map((item) => ({
                                    value: item.knowledge_item_id,
                                    label: `${item.title} · ${item.library_scope === "shared" ? "共享" : "个人"}`,
                                }))}
                                maxTagCount="responsive"
                            />
                        </div>

                        <div className="rag-lab__field">
                            <Typography.Text strong>返回条数：{formState.top_k}</Typography.Text>
                            <Slider
                                min={1}
                                max={10}
                                value={formState.top_k}
                                onChange={(value) => patchForm({ top_k: value })}
                            />
                        </div>

                        <div className="rag-lab__field">
                            <Typography.Text strong>候选片段：{formState.chunk_top_k}</Typography.Text>
                            <Slider
                                min={1}
                                max={20}
                                value={formState.chunk_top_k}
                                onChange={(value) => patchForm({ chunk_top_k: value })}
                            />
                        </div>

                        <div className="rag-lab__field">
                            <Typography.Text strong>公共政策过滤</Typography.Text>
                            <Space direction="vertical" size={8} style={{ width: "100%" }}>
                                <Select
                                    allowClear
                                    value={formState.region}
                                    onChange={(value) => patchForm({ region: value })}
                                    placeholder="地区"
                                    options={[
                                        { value: "national", label: "全国" },
                                        { value: "beijing", label: "北京" },
                                    ]}
                                />
                                <Select
                                    allowClear
                                    value={formState.doc_type}
                                    onChange={(value) => patchForm({ doc_type: value })}
                                    placeholder="文档类型"
                                    options={[
                                        { value: "policy", label: "政策" },
                                        { value: "standard", label: "标准" },
                                        { value: "guideline", label: "指南" },
                                    ]}
                                />
                            </Space>
                        </div>

                        <Space size={12} wrap>
                            <Switch
                                checked={formState.enable_rerank}
                                onChange={(checked) => patchForm({ enable_rerank: checked })}
                            />
                            <Typography.Text>启用 rerank</Typography.Text>
                            <Switch
                                checked={formState.include_references}
                                onChange={(checked) => patchForm({ include_references: checked })}
                            />
                            <Typography.Text>返回 references</Typography.Text>
                        </Space>

                        <Space size={12} wrap>
                            <Button
                                type="primary"
                                icon={<SearchOutlined />}
                                loading={submitting}
                                onClick={() => void handleRetrieve()}
                            >
                                运行检索
                            </Button>
                            <Button
                                icon={<ReloadOutlined />}
                                loading={loadingKnowledgeItems}
                                onClick={() => void loadKnowledgeItems()}
                            >
                                刷新条目
                            </Button>
                        </Space>
                    </Space>
                </Card>
            </div>

            <div className="rag-lab__results">
                {ragError ? (
                    <Alert
                        type="warning"
                        showIcon
                        className="chat-workbench__alert"
                        message={ragError.status ? `RAG Lab 提示 · HTTP ${ragError.status}` : "RAG Lab 提示"}
                        description={<ErrorDetail error={ragError} />}
                    />
                ) : null}

                {result && result.total_hits === 0 ? (
                    <Alert
                        type="info"
                        showIcon
                        className="chat-workbench__alert"
                        message="未检索到相关片段"
                        description={buildZeroHitMessage(metadata)}
                    />
                ) : null}

                <Card
                    title="检索状态"
                    extra={metadata ? <Tag color={metadata.retrieval_only === false ? "gold" : "green"}>retrieval-only</Tag> : null}
                >
                    {submitting ? (
                        <div className="chat-workbench__loading"><Spin /></div>
                    ) : metadata ? (
                        <div className="rag-lab__status-grid">
                            <Statistic title="命中片段" value={result?.total_hits ?? 0} prefix={<DatabaseOutlined />} />
                            <StatusStatistic
                                title="Vector"
                                value={vectorStatusLabelMap[vectorStatus]}
                                icon={<ApiOutlined />}
                                color={vectorStatusColorMap[vectorStatus]}
                            />
                            <StatusStatistic
                                title="Graph"
                                value={graphStatusLabelMap[graphStatus]}
                                icon={<ClusterOutlined />}
                                color={graphStatusColorMap[graphStatus]}
                            />
                            <StatusStatistic
                                title="Rerank"
                                value={rerankStatusLabelMap[rerankStatus]}
                                icon={<SearchOutlined />}
                                color={rerankStatusColorMap[rerankStatus]}
                            />
                        </div>
                    ) : (
                        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="尚未运行检索。" />
                    )}

                    {metadata ? (
                        <Descriptions
                            className="rag-lab__metadata"
                            bordered
                            size="small"
                            column={{ xs: 1, md: 2, xl: 3 }}
                        >
                            <Descriptions.Item label="retriever_mode">
                                <RetrievalModeTag mode={effectiveRetrieverMode} />
                            </Descriptions.Item>
                            <Descriptions.Item label="mode">{metadata.mode ?? "unknown"}</Descriptions.Item>
                            <Descriptions.Item label="scope">{metadata.knowledge_scope ?? "unknown"}</Descriptions.Item>
                            <Descriptions.Item label="strategy">{metadata.strategy ?? "unknown"}</Descriptions.Item>
                            <Descriptions.Item label="retrieval_strategy">
                                <Tag>{metadata.retrieval_strategy ?? formState.retrieval_strategy}</Tag>
                            </Descriptions.Item>
                            <Descriptions.Item label="graph_mode">
                                <Tag>{metadata.graph_mode ?? formState.graph_mode}</Tag>
                            </Descriptions.Item>
                            <Descriptions.Item label="graph_used">
                                <BooleanTag value={Boolean(metadata.graph_used)} />
                            </Descriptions.Item>
                            <Descriptions.Item label="graph_fallback_reason">
                                {metadata.graph_fallback_reason ? (
                                    <Tag color="gold">{metadata.graph_fallback_reason}</Tag>
                                ) : (
                                    <Tag color="green">none</Tag>
                                )}
                            </Descriptions.Item>
                            <Descriptions.Item label="vector_backend">
                                <Tag>{metadata.vector_backend ?? "none"}</Tag>
                            </Descriptions.Item>
                            <Descriptions.Item label="vector_adapter_name">
                                <Typography.Text code>{metadata.vector_adapter_name ?? "unknown"}</Typography.Text>
                            </Descriptions.Item>
                            <Descriptions.Item label="vector_backend_health">
                                <VectorHealthTag value={metadata.vector_backend_health ?? "unknown"} />
                            </Descriptions.Item>
                            <Descriptions.Item label="vector_hit_count">
                                {metadata.vector_hit_count ?? "unknown"}
                            </Descriptions.Item>
                            <Descriptions.Item label="path">
                                <Space size={4} wrap>
                                    {retrievalPath.map((item) => (
                                        <Tag key={item}>{item}</Tag>
                                    ))}
                                    {retrievalPath.length === 0 ? <Tag>empty</Tag> : null}
                                </Space>
                            </Descriptions.Item>
                            <Descriptions.Item label="requested_top_k">
                                {metadata.requested_top_k ?? metadata.top_k ?? requestPreview.top_k}
                            </Descriptions.Item>
                            <Descriptions.Item label="returned_count">
                                {metadata.returned_count ?? result?.chunks.length ?? 0}
                            </Descriptions.Item>
                            <Descriptions.Item label="chunk_top_k">{metadata.chunk_top_k ?? "unknown"}</Descriptions.Item>
                            <Descriptions.Item label="latency">
                                {typeof latencyMs === "number" ? `${latencyMs.toFixed(3)} ms` : "unknown"}
                            </Descriptions.Item>
                            <Descriptions.Item label="trace">
                                <Typography.Text code copyable>{metadata.trace?.trace_id ?? "unknown"}</Typography.Text>
                            </Descriptions.Item>
                            <Descriptions.Item label="fallback_used">
                                <BooleanTag value={Boolean(fallbackUsed)} />
                            </Descriptions.Item>
                            <Descriptions.Item label="fallback_reason">
                                {metadata.fallback_reason ? (
                                    <Tag color="gold">{metadata.fallback_reason}</Tag>
                                ) : (
                                    <Tag color="green">none</Tag>
                                )}
                            </Descriptions.Item>
                            <Descriptions.Item label="public_chunk_count">
                                {metadata.public_chunk_count ?? "unknown"}
                            </Descriptions.Item>
                            <Descriptions.Item label="private_chunk_count">
                                {metadata.private_chunk_count ?? "unknown"}
                            </Descriptions.Item>
                            <Descriptions.Item label="provider metadata">
                                <Typography.Text code>
                                    {Object.keys(providerMetadata).join(", ") || "empty"}
                                </Typography.Text>
                            </Descriptions.Item>
                        </Descriptions>
                    ) : null}
                </Card>

                <Card title={`证据片段${result ? `（${result.chunks.length}）` : ""}`}>
                    {result?.chunks.length ? (
                        <List
                            className="rag-evidence-list"
                            dataSource={result.chunks}
                            renderItem={(chunk) => (
                                <List.Item key={chunk.chunk_id}>
                                    <EvidenceChunkCard chunk={chunk} />
                                </List.Item>
                            )}
                        />
                    ) : (
                        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前没有证据片段。" />
                    )}
                </Card>

                <Card title={`References${result ? `（${result.references.length}）` : ""}`}>
                    {result?.references.length ? (
                        <List
                            dataSource={result.references}
                            renderItem={(reference) => (
                                <List.Item key={reference.reference_id}>
                                    <Space direction="vertical" size={6} style={{ width: "100%" }}>
                                        <Space size={8} wrap>
                                            <Tag color="blue">{reference.reference_id}</Tag>
                                            <Typography.Text strong>{reference.title}</Typography.Text>
                                            <Tag>{sourceTypeLabelMap[reference.source_type]}</Tag>
                                            <Typography.Text type="secondary">{reference.chunk_id}</Typography.Text>
                                        </Space>
                                        {reference.source_url ? (
                                            <Typography.Link href={reference.source_url} target="_blank" rel="noreferrer">
                                                {reference.source}
                                            </Typography.Link>
                                        ) : (
                                            <Typography.Text type="secondary">{reference.source}</Typography.Text>
                                        )}
                                    </Space>
                                </List.Item>
                            )}
                        />
                    ) : (
                        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前没有 references。" />
                    )}
                </Card>

                <Card title="Graph candidates">
                    <GraphMetadataPanel
                        entities={metadata?.graph_entities ?? []}
                        relations={metadata?.graph_relations ?? []}
                        candidates={metadata?.graph_candidates ?? []}
                    />
                </Card>
            </div>
        </div>
    );
}

interface StatusStatisticProps {
    title: string;
    value: string;
    icon: ReactNode;
    color: string;
}

function StatusStatistic({ title, value, icon, color }: StatusStatisticProps) {
    return (
        <Statistic
            title={title}
            value={value}
            prefix={<span style={{ color }}>{icon}</span>}
            valueStyle={{ color }}
        />
    );
}

function BooleanTag({ value }: { value: boolean }) {
    return <Tag color={value ? "green" : "default"}>{value ? "true" : "false"}</Tag>;
}

function VectorHealthTag({ value }: { value: string }) {
    const color = value === "ok" ? "green" : value === "degraded" ? "gold" : value === "disabled" ? "default" : "red";
    return <Tag color={color}>{value}</Tag>;
}

function ErrorDetail({ error }: { error: RagLabError }) {
    return (
        <Space direction="vertical" size={4} style={{ width: "100%" }}>
            <Typography.Text>{error.message}</Typography.Text>
            {error.detail ? (
                <Typography.Paragraph className="rag-lab__error-detail" copyable>
                    {error.detail}
                </Typography.Paragraph>
            ) : null}
        </Space>
    );
}

function RetrievalModeTag({ mode }: { mode: string }) {
    const normalizedMode = mode.trim() || "unknown";
    const color = normalizedMode.includes("bm25")
        ? "gold"
        : normalizedMode === "mix"
          ? "blue"
          : normalizedMode === "naive"
            ? "cyan"
            : normalizedMode === "vector"
              ? "green"
              : "default";
    return <Tag color={color}>{normalizedMode}</Tag>;
}

function EvidenceChunkCard({ chunk }: { chunk: RagEvidenceChunk }) {
    return (
        <div className="rag-evidence-card">
            <Space direction="vertical" size={8} style={{ width: "100%" }}>
                <Space size={8} wrap>
                    <Typography.Text strong>{chunk.title}</Typography.Text>
                    <Tag color={sourceTypeColorMap[chunk.source_type]}>{sourceTypeLabelMap[chunk.source_type]}</Tag>
                    <Tag color={layerColorMap[chunk.retrieval_layer]}>{layerLabelMap[chunk.retrieval_layer]}</Tag>
                    <Tag>score {formatScore(chunk.score)}</Tag>
                    {chunk.source_retrievers?.length ? (
                        <Tag color="geekblue">{chunk.source_retrievers.join(" + ")}</Tag>
                    ) : null}
                    <Typography.Text type="secondary">{chunk.chunk_id}</Typography.Text>
                </Space>
                {hasRetrieverSourceMetadata(chunk) ? (
                    <Space size={8} wrap>
                        <Tag color={chunk.from_bm25 ? "gold" : "default"}>from_bm25 {String(Boolean(chunk.from_bm25))}</Tag>
                        <Tag color={chunk.from_vector ? "green" : "default"}>from_vector {String(Boolean(chunk.from_vector))}</Tag>
                        {typeof chunk.bm25_score === "number" ? <Tag>bm25 {formatScore(chunk.bm25_score)}</Tag> : null}
                        {typeof chunk.vector_score === "number" ? <Tag>vector {formatScore(chunk.vector_score)}</Tag> : null}
                        {typeof chunk.merged_score === "number" ? <Tag>merged {formatScore(chunk.merged_score)}</Tag> : null}
                    </Space>
                ) : null}
                <Typography.Paragraph
                    className="rag-evidence-card__snippet"
                    ellipsis={{ rows: 4, expandable: "collapsible", symbol: "展开" }}
                >
                    {chunk.snippet}
                </Typography.Paragraph>
                <Space size={8} wrap>
                    <Tag>{chunk.reference_id}</Tag>
                    {chunk.region ? <Tag>{chunk.region}</Tag> : null}
                    {chunk.doc_type ? <Tag>{chunk.doc_type}</Tag> : null}
                    {chunk.knowledge_item_id ? <Tag>{chunk.knowledge_item_id}</Tag> : null}
                    {chunk.source_url ? (
                        <Typography.Link href={chunk.source_url} target="_blank" rel="noreferrer">
                            {chunk.source}
                        </Typography.Link>
                    ) : (
                        <Typography.Text type="secondary">{chunk.source}</Typography.Text>
                    )}
                </Space>
            </Space>
        </div>
    );
}

function GraphMetadataPanel({
    entities,
    relations,
    candidates,
}: {
    entities: RagGraphEntity[];
    relations: RagGraphRelation[];
    candidates: RagGraphCandidate[];
}) {
    if (entities.length === 0 && relations.length === 0 && candidates.length === 0) {
        return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前没有 graph candidates。" />;
    }
    return (
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
            {candidates.length ? (
                <List
                    dataSource={candidates}
                    renderItem={(candidate) => (
                        <List.Item key={candidate.candidate_id}>
                            <Space direction="vertical" size={6} style={{ width: "100%" }}>
                                <Space size={8} wrap>
                                    <Typography.Text strong>{candidate.title}</Typography.Text>
                                    <Tag>score {formatScore(candidate.score)}</Tag>
                                    {candidate.entity_name ? <Tag color="blue">{candidate.entity_name}</Tag> : null}
                                    {candidate.relation_type ? <Tag color="purple">{candidate.relation_type}</Tag> : null}
                                    {candidate.reason ? <Tag color="gold">{candidate.reason}</Tag> : null}
                                    {candidate.source_chunk_ids.map((chunkId) => (
                                        <Tag key={chunkId}>{chunkId}</Tag>
                                    ))}
                                </Space>
                                <Typography.Text>{candidate.snippet}</Typography.Text>
                                <Space size={8} wrap>
                                    {(candidate.entity_ids ?? []).slice(0, 6).map((entityId) => (
                                        <Tag key={entityId} color="cyan">{entityId}</Tag>
                                    ))}
                                </Space>
                            </Space>
                        </List.Item>
                    )}
                />
            ) : null}

            <Descriptions bordered size="small" column={{ xs: 1, md: 3 }}>
                <Descriptions.Item label="graph_entities">{entities.length}</Descriptions.Item>
                <Descriptions.Item label="graph_relations">{relations.length}</Descriptions.Item>
                <Descriptions.Item label="graph_candidates">{candidates.length}</Descriptions.Item>
            </Descriptions>

            {entities.length ? (
                <Space size={8} wrap>
                    {entities.slice(0, 12).map((entity) => (
                        <Tag key={entity.entity_id} color="blue">
                            {entity.name} · {entity.entity_type} · {formatScore(entity.confidence)}
                        </Tag>
                    ))}
                </Space>
            ) : null}

            {relations.length ? (
                <Space direction="vertical" size={6} style={{ width: "100%" }}>
                    {relations.slice(0, 8).map((relation) => (
                        <Typography.Text key={relation.relation_id} type="secondary">
                            {relation.relation_type}: {relation.source_entity_id} → {relation.target_entity_id}
                        </Typography.Text>
                    ))}
                </Space>
            ) : null}
        </Space>
    );
}

const sourceTypeLabelMap: Record<RagSourceType, string> = {
    public_policy: "公共政策",
    public_policy_demo: "演示样例",
    private_sample: "知识条目",
    private_upload: "个人上传",
};

const sourceTypeColorMap: Record<RagSourceType, string> = {
    public_policy: "blue",
    public_policy_demo: "orange",
    private_sample: "magenta",
    private_upload: "green",
};

const layerLabelMap = {
    vector: "vector",
    bm25_fallback: "BM25 fallback",
    graph: "graph",
} as const;

const layerColorMap = {
    vector: "green",
    bm25_fallback: "gold",
    graph: "purple",
} as const;

const vectorStatusLabelMap: Record<RagVectorStatus, string> = {
    disabled: "disabled",
    unavailable: "unavailable",
    queried: "queried",
    error: "error",
};

const vectorStatusColorMap: Record<RagVectorStatus, string> = {
    disabled: "#8c8c8c",
    unavailable: "#d48806",
    queried: "#389e0d",
    error: "#cf1322",
};

const graphStatusLabelMap: Record<RagGraphStatus, string> = {
    unavailable: "unavailable",
    skipped: "skipped",
};

const graphStatusColorMap: Record<RagGraphStatus, string> = {
    unavailable: "#d48806",
    skipped: "#8c8c8c",
};

const rerankStatusLabelMap: Record<RagRerankStatus, string> = {
    disabled: "disabled",
    skipped: "skipped",
    applied: "applied",
    error: "error",
};

const rerankStatusColorMap: Record<RagRerankStatus, string> = {
    disabled: "#8c8c8c",
    skipped: "#8c8c8c",
    applied: "#389e0d",
    error: "#cf1322",
};

function formatScore(value: number) {
    return Number.isFinite(value) ? value.toFixed(4) : "0.0000";
}

function hasRetrieverSourceMetadata(chunk: RagEvidenceChunk) {
    return Boolean(
        chunk.from_bm25 !== null && chunk.from_bm25 !== undefined
        || chunk.from_vector !== null && chunk.from_vector !== undefined
        || typeof chunk.bm25_score === "number"
        || typeof chunk.vector_score === "number"
        || typeof chunk.merged_score === "number"
        || chunk.source_retrievers?.length,
    );
}

function buildRequestPreview(formState: RagLabFormState) {
    return {
        query: formState.question.trim(),
        top_k: formState.top_k,
        mode: formState.mode,
        retrieval_strategy: formState.retrieval_strategy,
        graph_mode: formState.graph_mode,
        use_public: formState.knowledge_scope === "public" || formState.knowledge_scope === "mixed",
        use_private: formState.knowledge_scope === "private_sample" || formState.knowledge_scope === "mixed",
    };
}

function resolveBackendBaseUrl(apiBaseUrl: string) {
    const trimmed = apiBaseUrl.replace(/\/+$/, "");
    if (trimmed === "/api") {
        return window.location.origin;
    }
    if (trimmed.endsWith("/api")) {
        return trimmed.slice(0, -4) || "/";
    }
    return trimmed || window.location.origin;
}

function resolveRetrieverMode(
    metadata: RagRetrievalResult["metadata"] | undefined,
    requestedMode: RagQueryMode,
): string {
    const retrieverMode = metadata?.retriever_mode;
    if (retrieverMode === "bm25_fallback") {
        return "bm25 fallback";
    }
    return retrieverMode ?? metadata?.mode ?? requestedMode;
}

function buildZeroHitMessage(metadata?: RagRetrievalResult["metadata"]) {
    if (!metadata) {
        return "请求已经完成，但当前问题没有返回可展示证据。";
    }
    const retrievalPath = metadata.retrieval_path ?? metadata.trace?.retrieval_path ?? [];
    const parts = [
        `检索路径：${retrievalPath.join(" -> ") || "empty"}`,
        metadata.fallback_reason ? `fallback：${metadata.fallback_reason}` : "fallback：none",
        `vector：${metadata.vector_status ?? "unknown"}`,
        `graph：${metadata.graph_status ?? "unknown"}`,
    ];
    return parts.join("；");
}

function extractRagLabError(value: unknown, fallbackMessage: string): RagLabError {
    if (axios.isAxiosError(value)) {
        const detail = value.response?.data?.detail ?? value.response?.data;
        return {
            status: value.response?.status ?? null,
            message: extractBackendMessage(detail) ?? value.message ?? fallbackMessage,
            detail: formatBackendDetail(detail),
        };
    }

    if (!value || typeof value !== "object") {
        return { message: fallbackMessage };
    }

    const candidate = value as {
        detail?: unknown;
        message?: unknown;
    };
    const detail = candidate.detail;
    return {
        message: extractBackendMessage(detail) ?? (typeof candidate.message === "string" ? candidate.message : fallbackMessage),
        detail: formatBackendDetail(detail),
    };
}

function extractBackendMessage(detail: unknown): string | null {
    if (typeof detail === "string") {
        return detail;
    }
    if (Array.isArray(detail)) {
        for (const item of detail) {
            const message = extractBackendMessage(item);
            if (message) {
                return message;
            }
        }
        return null;
    }
    if (detail && typeof detail === "object") {
        const candidate = detail as Record<string, unknown>;
        for (const key of ["message", "msg", "error_code", "error"]) {
            const value = candidate[key];
            if (typeof value === "string" && value.trim()) {
                return value;
            }
        }
    }
    return null;
}

function formatBackendDetail(detail: unknown): string | null {
    if (typeof detail === "string") {
        return detail;
    }
    if (Array.isArray(detail)) {
        return detail
            .map((item) => {
                const formatted = formatBackendDetail(item);
                return formatted || null;
            })
            .filter((item): item is string => Boolean(item))
            .join("；") || null;
    }
    if (detail && typeof detail === "object") {
        const candidate = detail as Record<string, unknown>;
        const parts = ["error", "error_code", "message", "msg"]
            .map((key) => {
                const value = candidate[key];
                if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
                    return `${key}: ${value}`;
                }
                return null;
            })
            .filter((item): item is string => Boolean(item));
        if (parts.length > 0) {
            return parts.join("；");
        }
    }
    return null;
}
