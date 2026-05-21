export type RagDocumentStatus = "uploaded" | "parsed" | "chunked" | "indexed" | "failed";
export type RagRetrievalMode = "dense" | "sparse" | "hybrid" | "hybrid_rerank";
export type RagPipelineMode = "quick" | "acceptance";

export interface KnowledgeBase {
    kb_id: string;
    owner_user_id?: string | null;
    name: string;
    description?: string | null;
    visibility: "private" | "shared" | "public";
    retrieval_mode: RagRetrievalMode;
    embedding_model: string;
    chunk_size: number;
    chunk_overlap: number;
    parent_chunk_size?: number | null;
    rerank_top_n: number;
    retrieval_top_k: number;
    is_default: boolean;
    created_at: string;
    updated_at: string;
    metadata?: Record<string, unknown>;
    system_managed?: boolean;
    managed_by?: string | null;
    kb_scope?: string | null;
    document_count?: number;
    chunk_count?: number;
    indexed_chunk_count?: number;
    last_ingested_at?: string | null;
    health_status?: string;
}

export interface RagDocument {
    doc_id: string;
    kb_id: string;
    owner_user_id?: string | null;
    knowledge_item_id?: string | null;
    file_id?: string | null;
    filename?: string | null;
    file_type?: string | null;
    file_size?: number | null;
    file_path?: string | null;
    title: string;
    source_type: string;
    chunk_method?: string;
    parse_progress?: number;
    chunk_progress?: number;
    error_stage?: string | null;
    status: RagDocumentStatus;
    parse_status: string;
    chunk_status: string;
    index_status: string;
    chunk_count: number;
    indexed_chunk_count: number;
    error_message?: string | null;
    vector_backend?: string | null;
    degraded?: boolean;
    index_warnings?: string[];
    created_at: string;
    updated_at: string;
    metadata?: Record<string, unknown>;
}

export interface RagChunk {
    rag_chunk_id: string;
    kb_id: string;
    doc_id: string;
    knowledge_chunk_id?: string | null;
    chunk_index: number;
    text: string;
    token_estimate: number;
    token_count?: number;
    keywords?: string[];
    questions?: string[];
    milvus_id?: string | null;
    page_number?: number | null;
    sheet_name?: string | null;
    slide_number?: number | null;
    section_title?: string | null;
    vector_status: string;
}

export interface RagTrace {
    dense_count: number;
    sparse_count: number;
    merged_count: number;
    rerank_applied: boolean;
    vector_backend: string;
    vector_runtime?: string | null;
    degraded: boolean;
    warnings: string[];
    retrieval_mode: RagRetrievalMode;
    kb_id?: string | null;
    timing_trace?: RagTimingTrace;
}

export interface KnowledgeBaseOverview {
    kb: KnowledgeBase;
    documents: RagDocument[];
    document_count: number;
    chunk_count: number;
    indexed_chunk_count: number;
    failed_document_count: number;
    pending_document_count: number;
    last_ingested_at?: string | null;
    health_status: string;
    system_managed: boolean;
    read_only: boolean;
}

export interface RagHit {
    chunk_id: string;
    doc_id: string;
    kb_id?: string | null;
    title: string;
    snippet: string;
    source_type: string;
    dense_score?: number | null;
    sparse_score?: number | null;
    rrf_score?: number | null;
    rerank_score?: number | null;
    page_number?: number | null;
    sheet_name?: string | null;
    slide_number?: number | null;
}

export interface RagSearchResult {
    query: string;
    kb_id?: string | null;
    hits: RagHit[];
    trace: RagTrace;
}

export interface RagTestQAResult {
    run_id?: string | null;
    answer: string;
    answer_mode?: "llm_grounded" | "retrieval_only" | "no_hits";
    provider_name?: string | null;
    model_name?: string | null;
    selected_chunks?: RagHit[];
    evidence_quality?: "none" | "weak" | "usable" | "strong" | string | null;
    confidence?: number | null;
    citations: Record<string, unknown>[];
    hits: RagHit[];
    retrieval_trace: RagTrace;
}

export interface RagEvalRun {
    run_id: string;
    kb_id?: string | null;
    owner_user_id?: string | null;
    metrics: Record<string, number | string | boolean | Record<string, number>>;
    cases: Record<string, unknown>[];
    passed: boolean;
    created_at: string;
}

export interface RagPipelineResult {
    doc_id: string;
    pipeline_mode?: RagPipelineMode;
    parse_status: string;
    chunk_status: string;
    index_status: string;
    chunk_count: number;
    indexed_chunk_count: number;
    vector_runtime: string;
    degraded: boolean;
    search_smoke_passed: boolean;
    eval_passed?: boolean | null;
    failed_stage?: string | null;
    error_message?: string | null;
    warnings: string[];
    timing_trace?: RagTimingTrace;
}

export interface RagPipelineBatchResult {
    kb_id: string;
    total_count: number;
    succeeded_count: number;
    failed_count: number;
    results: RagPipelineResult[];
}

export interface RagTimingTrace {
    parse_ms?: number | null;
    chunk_ms?: number | null;
    embedding_ms?: number | null;
    milvus_client_ms?: number | null;
    milvus_insert_ms?: number | null;
    milvus_search_ms?: number | null;
    db_load_chunks_ms?: number | null;
    sparse_ms?: number | null;
    rrf_ms?: number | null;
    rerank_ms?: number | null;
    llm_ms?: number | null;
    total_ms?: number | null;
    loaded_chunk_count?: number;
    dense_candidate_count?: number;
    sparse_candidate_count?: number;
    rrf_candidate_count?: number;
    rerank_candidate_count?: number;
    milvus_client_init_count?: number;
    sparse_cache_hit?: boolean | null;
    sparse_loaded_chunk_count?: number;
}

