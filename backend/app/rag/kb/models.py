from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.settings.schemas import LocalProviderOverride


KnowledgeBaseVisibility = Literal["private", "shared", "public"]
RagDocumentStatus = Literal["uploaded", "parsed", "chunked", "indexed", "failed"]
RagRetrievalMode = Literal["dense", "sparse", "hybrid", "hybrid_rerank"]
RagPipelineMode = Literal["quick", "acceptance"]


class KnowledgeBase(BaseModel):
    kb_id: str
    owner_user_id: str | None = None
    name: str
    description: str | None = None
    visibility: KnowledgeBaseVisibility = "private"
    retrieval_mode: RagRetrievalMode = "hybrid"
    embedding_model: str = "BAAI/bge-m3"
    chunk_size: int = 512
    chunk_overlap: int = 64
    parent_chunk_size: int | None = None
    rerank_top_n: int = 5
    retrieval_top_k: int = 20
    is_default: bool = False
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
    system_managed: bool = False
    managed_by: str | None = None
    kb_scope: str | None = None
    document_count: int = 0
    chunk_count: int = 0
    indexed_chunk_count: int = 0
    last_ingested_at: datetime | None = None
    health_status: str = "unknown"


class RagDocument(BaseModel):
    doc_id: str
    kb_id: str
    owner_user_id: str | None = None
    knowledge_item_id: str | None = None
    file_id: str | None = None
    filename: str | None = None
    file_type: str | None = None
    file_size: int | None = None
    file_path: str | None = None
    title: str
    source_type: str
    chunk_method: str = "recursive"
    parse_progress: int = 0
    chunk_progress: int = 0
    error_stage: str | None = None
    status: RagDocumentStatus = "uploaded"
    parse_status: str = "uploaded"
    chunk_status: str = "pending"
    index_status: str = "pending"
    chunk_count: int = 0
    indexed_chunk_count: int = 0
    error_message: str | None = None
    vector_backend: str | None = None
    degraded: bool = False
    index_warnings: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeBaseOverview(BaseModel):
    kb: KnowledgeBase
    documents: list[RagDocument] = Field(default_factory=list)
    document_count: int = 0
    chunk_count: int = 0
    indexed_chunk_count: int = 0
    failed_document_count: int = 0
    pending_document_count: int = 0
    last_ingested_at: datetime | None = None
    health_status: str = "unknown"
    system_managed: bool = False
    read_only: bool = False


class RagChunk(BaseModel):
    rag_chunk_id: str
    kb_id: str
    doc_id: str
    owner_user_id: str | None = None
    knowledge_chunk_id: str | None = None
    parent_chunk_id: str | None = None
    chunk_index: int
    text: str
    token_estimate: int = 0
    token_count: int = 0
    keywords: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    milvus_id: str | None = None
    page_number: int | None = None
    sheet_name: str | None = None
    slide_number: int | None = None
    section_title: str | None = None
    status: str = "chunked"
    vector_status: str = "pending"
    dense_vector: list[float] | None = None
    sparse_vector: dict[str, float] | None = None
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeBaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str | None = None
    visibility: KnowledgeBaseVisibility = "private"
    retrieval_mode: RagRetrievalMode = "hybrid"
    embedding_model: str = "BAAI/bge-m3"
    chunk_size: int = Field(default=512, ge=64, le=8192)
    chunk_overlap: int = Field(default=64, ge=0, le=2048)
    parent_chunk_size: int | None = Field(default=None, ge=128, le=16384)
    rerank_top_n: int = Field(default=5, ge=1, le=50)
    retrieval_top_k: int = Field(default=20, ge=1, le=100)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name cannot be blank")
        return normalized


class KnowledgeBaseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    description: str | None = None
    visibility: KnowledgeBaseVisibility | None = None
    retrieval_mode: RagRetrievalMode | None = None
    embedding_model: str | None = None
    chunk_size: int | None = Field(default=None, ge=64, le=8192)
    chunk_overlap: int | None = Field(default=None, ge=0, le=2048)
    parent_chunk_size: int | None = Field(default=None, ge=128, le=16384)
    rerank_top_n: int | None = Field(default=None, ge=1, le=50)
    retrieval_top_k: int | None = Field(default=None, ge=1, le=100)


class RagDocumentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    knowledge_item_id: str | None = None
    file_id: str | None = None
    title: str | None = None
    text: str | None = None
    source_type: str = "manual"
    filename: str | None = None
    file_type: str | None = None
    file_size: int | None = None
    file_path: str | None = None
    chunk_method: str = "recursive"


class RagSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    kb_id: str | None = None
    knowledge_scope: Literal["public", "private_sample", "mixed"] = "mixed"
    mode: RagRetrievalMode = "hybrid_rerank"
    top_k: int = Field(default=5, ge=1, le=50)
    allowed_knowledge_item_ids: list[str] = Field(default_factory=list)
    provider_override: LocalProviderOverride | None = None

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("query cannot be blank")
        return normalized


class RagHit(BaseModel):
    chunk_id: str
    rag_chunk_id: str | None = None
    doc_id: str
    kb_id: str | None = None
    title: str
    snippet: str
    source_type: str
    source: str | None = None
    source_url: str | None = None
    library_scope: Literal["personal", "shared"] | None = None
    file_id: str | None = None
    knowledge_item_id: str | None = None
    page_number: int | None = None
    sheet_name: str | None = None
    slide_number: int | None = None
    section_title: str | None = None
    dense_score: float | None = None
    sparse_score: float | None = None
    rrf_score: float | None = None
    rerank_score: float | None = None

    @property
    def score(self) -> float:
        return self.rerank_score or self.rrf_score or self.dense_score or self.sparse_score or 0.0

    def to_tool_hit(self) -> dict[str, Any]:
        payload = self.model_dump()
        payload["score"] = self.score
        payload["bm25_score"] = self.sparse_score
        payload["vector_score"] = self.dense_score
        return payload


class RagTimingTrace(BaseModel):
    parse_ms: float | None = None
    chunk_ms: float | None = None
    embedding_ms: float | None = None
    milvus_client_ms: float | None = None
    milvus_insert_ms: float | None = None
    milvus_search_ms: float | None = None
    db_load_chunks_ms: float | None = None
    sparse_ms: float | None = None
    rrf_ms: float | None = None
    rerank_ms: float | None = None
    llm_ms: float | None = None
    total_ms: float | None = None
    loaded_chunk_count: int = 0
    dense_candidate_count: int = 0
    sparse_candidate_count: int = 0
    rrf_candidate_count: int = 0
    rerank_candidate_count: int = 0
    milvus_client_init_count: int = 0
    sparse_cache_hit: bool | None = None
    sparse_loaded_chunk_count: int = 0


class RagTrace(BaseModel):
    dense_count: int = 0
    sparse_count: int = 0
    merged_count: int = 0
    rerank_applied: bool = False
    vector_backend: str = "memory"
    vector_runtime: str = "memory_dev"
    degraded: bool = False
    warnings: list[str] = Field(default_factory=list)
    retrieval_mode: RagRetrievalMode = "hybrid_rerank"
    kb_id: str | None = None
    knowledge_scope: str = "mixed"
    generation_provider: str | None = None
    generation_model: str | None = None
    provider_ref: str | None = None
    thinking_content: str | None = None
    timing_trace: RagTimingTrace = Field(default_factory=RagTimingTrace)


class RagSearchResult(BaseModel):
    query: str
    kb_id: str | None = None
    hits: list[RagHit] = Field(default_factory=list)
    trace: RagTrace = Field(default_factory=RagTrace)


class RagAnswerResult(BaseModel):
    answer: str
    answer_mode: Literal["llm_grounded", "retrieval_only", "no_hits"] = "retrieval_only"
    provider_name: str | None = None
    model_name: str | None = None
    selected_chunks: list[dict[str, Any]] = Field(default_factory=list)
    evidence_quality: str | None = None
    confidence: float | None = None
    citations: list[dict[str, Any]] = Field(default_factory=list)
    hits: list[RagHit] = Field(default_factory=list)
    retrieval_trace: RagTrace = Field(default_factory=RagTrace)


class RagEvalCase(BaseModel):
    case_id: str
    question: str
    expected_chunk_keywords: list[str] = Field(default_factory=list)
    expected_answer_keywords: list[str] = Field(default_factory=list)
    expected_kb_id: str | None = None


class RagEvalRun(BaseModel):
    run_id: str
    kb_id: str | None = None
    owner_user_id: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    cases: list[dict[str, Any]] = Field(default_factory=list)
    passed: bool = False
    created_at: datetime


class RagHealth(BaseModel):
    enabled: bool = True
    spine: str = "rag-pro"
    vector_backend: str = "memory"
    vector_runtime: str = "memory_dev"
    milvus_uri: str | None = None
    require_real_vector: bool = True
    degraded: bool = False
    document_count: int = 0
    chunk_count: int = 0
    warnings: list[str] = Field(default_factory=list)


class RagStats(BaseModel):
    kb_count: int = 0
    document_count: int = 0
    chunk_count: int = 0
    indexed_chunk_count: int = 0
    vector_backend: str = "memory"
    vector_runtime: str = "memory_dev"
    milvus_uri: str | None = None
    require_real_vector: bool = True


class RagPipelineResult(BaseModel):
    doc_id: str
    pipeline_mode: RagPipelineMode = "quick"
    parse_status: str
    chunk_status: str
    index_status: str
    chunk_count: int = 0
    indexed_chunk_count: int = 0
    vector_runtime: str = "memory_dev"
    degraded: bool = False
    search_smoke_passed: bool = False
    eval_passed: bool | None = None
    failed_stage: str | None = None
    error_message: str | None = None
    warnings: list[str] = Field(default_factory=list)
    timing_trace: RagTimingTrace = Field(default_factory=RagTimingTrace)


class RagPipelineBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_ids: list[str] | None = None
    pipeline_mode: RagPipelineMode = "quick"


class RagPipelineRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pipeline_mode: RagPipelineMode = "quick"


class RagPipelineBatchResult(BaseModel):
    kb_id: str
    total_count: int = 0
    succeeded_count: int = 0
    failed_count: int = 0
    results: list[RagPipelineResult] = Field(default_factory=list)

