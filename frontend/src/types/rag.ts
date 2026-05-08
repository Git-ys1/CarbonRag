export type RagQueryMode = "naive" | "mix";
export type RagKnowledgeScope = "public" | "private_sample" | "mixed";
export type RagRetrievalLayer = "vector" | "bm25_fallback" | "graph";
export type RagSourceType = "public_policy" | "public_policy_demo" | "private_sample" | "private_upload";
export type RagVectorStatus = "disabled" | "unavailable" | "queried" | "error";
export type RagGraphStatus = "unavailable" | "skipped";
export type RagRerankStatus = "disabled" | "skipped" | "applied" | "error";
export type RagRetrievalStrategy = "dense_only" | "bm25_dense_hybrid" | "citation_first" | "graph_augmented";
export type RagExperimentalRetrievalStrategy = "bm25_only" | "vector_only" | "bm25_vector_hybrid";
export type RagGraphMode = "off" | "graph_local" | "graph_global" | "graph_hybrid";

export interface RagRetrieveRequest {
    question: string;
    mode: RagQueryMode;
    knowledge_scope: RagKnowledgeScope;
    top_k: number;
    chunk_top_k?: number | null;
    max_total_tokens?: number;
    enable_rerank: boolean;
    include_references: boolean;
    allowed_knowledge_item_ids: string[];
    region?: string | null;
    doc_type?: string | null;
    retrieval_strategy?: RagExperimentalRetrievalStrategy | null;
    graph_mode?: RagGraphMode;
}

export interface RagEvidenceChunk {
    reference_id: string;
    doc_id: string;
    knowledge_item_id: string | null;
    title: string;
    source_type: RagSourceType;
    source: string;
    source_url: string | null;
    issued_at: string | null;
    region: string | null;
    doc_type: string | null;
    sample_type: string | null;
    business_topic: string | null;
    library_scope: "personal" | "shared" | null;
    chunk_id: string;
    snippet: string;
    score: number;
    retrieval_layer: RagRetrievalLayer;
    bm25_score?: number | null;
    vector_score?: number | null;
    merged_score?: number | null;
    from_bm25?: boolean | null;
    from_vector?: boolean | null;
    source_retrievers?: string[];
}

export interface RagEvidenceReference {
    reference_id: string;
    chunk_id: string;
    doc_id: string;
    title: string;
    source_type: RagSourceType;
    source: string;
    source_url: string | null;
}

export interface RagGraphEntity {
    entity_id: string;
    name: string;
    entity_type: string;
    source_chunk_ids: string[];
    confidence: number;
    metadata?: Record<string, unknown>;
}

export interface RagGraphRelation {
    relation_id: string;
    source_entity_id: string;
    target_entity_id: string;
    relation_type: string;
    description?: string | null;
    source_chunk_ids: string[];
    confidence: number;
    metadata?: Record<string, unknown>;
}

export interface RagGraphCandidate {
    candidate_id: string;
    title: string;
    snippet: string;
    source_chunk_ids: string[];
    entity_ids?: string[];
    relation_ids?: string[];
    entity_name?: string | null;
    relation_type?: string | null;
    reason?: string | null;
    score: number;
    metadata?: Record<string, unknown>;
}

export interface RagRetrievalMetadata {
    mode?: RagQueryMode | null;
    knowledge_scope?: RagKnowledgeScope | null;
    top_k?: number | null;
    chunk_top_k?: number | null;
    retrieval_only?: boolean | null;
    retriever_mode?: RagRetrievalLayer | null;
    requested_top_k?: number | null;
    returned_count?: number | null;
    fallback_used?: boolean | null;
    strategy?: RagRetrievalStrategy | null;
    retrieval_strategy?: RagExperimentalRetrievalStrategy | null;
    retrieval_path?: string[] | null;
    vector_status?: RagVectorStatus | null;
    vector_backend?: string | null;
    vector_backend_health?: string | null;
    vector_adapter_name?: string | null;
    vector_hit_count?: number | null;
    graph_status?: RagGraphStatus | null;
    graph_mode?: RagGraphMode | null;
    graph_entity_count?: number | null;
    graph_relation_count?: number | null;
    graph_candidate_count?: number | null;
    graph_used?: boolean | null;
    graph_fallback_reason?: string | null;
    rerank_status?: RagRerankStatus | null;
    fallback_reason?: string | null;
    latency_ms?: number | null;
    public_chunk_count?: number | null;
    public_policy_demo_chunk_count?: number | null;
    private_chunk_count?: number | null;
    graph_entities?: RagGraphEntity[] | null;
    graph_relations?: RagGraphRelation[] | null;
    graph_candidates?: RagGraphCandidate[] | null;
    trace?: {
        trace_id: string;
        query?: string | null;
        retriever_mode?: string | null;
        requested_top_k?: number | null;
        returned_count?: number | null;
        fallback_used?: boolean | null;
        chunk_ids?: string[];
        citations?: unknown[];
        strategy: RagRetrievalStrategy;
        retrieval_path: string[];
        latency_ms: number;
        total_hits: number;
        fallback_reason: string | null;
        created_at: string;
        metadata: Record<string, unknown>;
    } | null;
    provider_metadata?: Record<string, unknown> | null;
}

export interface RagRetrievalResult {
    query: string;
    total_hits: number;
    chunks: RagEvidenceChunk[];
    references: RagEvidenceReference[];
    metadata: RagRetrievalMetadata;
}
