from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.rag.contracts import RetrievalStrategyName, RetrievalTrace
from app.rag.graph import GraphCandidate, GraphEntity, GraphRelation
from app.retrieval.schemas import SourceType


RagQueryMode = Literal["naive", "mix"]
RagKnowledgeScope = Literal["public", "private_sample", "mixed"]
RagRetrievalLayer = Literal["vector", "bm25_fallback", "graph"]
RagExperimentalRetrievalStrategy = Literal["bm25_only", "vector_only", "bm25_vector_hybrid"]
RagGraphMode = Literal["off", "graph_local", "graph_global", "graph_hybrid"]


class RagQueryParams(BaseModel):
    question: str
    mode: RagQueryMode = "mix"
    knowledge_scope: RagKnowledgeScope = "mixed"
    top_k: int = Field(default=5, ge=1, le=20)
    chunk_top_k: int | None = Field(default=None, ge=1, le=50)
    max_total_tokens: int = Field(default=30_000, ge=1)
    enable_rerank: bool = True
    include_references: bool = True
    retrieval_only: bool = True
    allowed_knowledge_item_ids: list[str] = Field(default_factory=list)
    region: str | None = None
    doc_type: str | None = None
    retrieval_strategy: RagExperimentalRetrievalStrategy | None = None
    graph_mode: RagGraphMode = "off"

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("question cannot be blank")
        return normalized

    @field_validator("allowed_knowledge_item_ids")
    @classmethod
    def normalize_allowed_ids(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(item.strip() for item in value if item.strip()))


class RagEvidenceChunk(BaseModel):
    reference_id: str
    doc_id: str
    knowledge_item_id: str | None = None
    title: str
    source_type: SourceType
    source: str
    source_url: str | None = None
    issued_at: str | None = None
    region: str | None = None
    doc_type: str | None = None
    sample_type: str | None = None
    business_topic: str | None = None
    library_scope: Literal["personal", "shared"] | None = None
    chunk_id: str
    snippet: str
    score: float
    retrieval_layer: RagRetrievalLayer
    bm25_score: float | None = None
    vector_score: float | None = None
    merged_score: float | None = None
    from_bm25: bool | None = None
    from_vector: bool | None = None
    source_retrievers: list[str] = Field(default_factory=list)

    def to_retrieved_hit(self) -> dict[str, Any]:
        payload = self.model_dump()
        payload.pop("reference_id", None)
        payload.pop("retrieval_layer", None)
        payload.pop("bm25_score", None)
        payload.pop("vector_score", None)
        payload.pop("merged_score", None)
        payload.pop("from_bm25", None)
        payload.pop("from_vector", None)
        payload.pop("source_retrievers", None)
        return payload


class RagEvidenceReference(BaseModel):
    reference_id: str
    chunk_id: str
    doc_id: str
    title: str
    source_type: SourceType
    source: str
    source_url: str | None = None


class RagRetrievalMetadata(BaseModel):
    mode: RagQueryMode
    knowledge_scope: RagKnowledgeScope
    top_k: int
    chunk_top_k: int
    retrieval_only: bool
    retriever_mode: RagRetrievalLayer | None = None
    requested_top_k: int | None = None
    returned_count: int | None = None
    fallback_used: bool | None = None
    strategy: RetrievalStrategyName = "bm25_dense_hybrid"
    retrieval_strategy: RagExperimentalRetrievalStrategy | None = None
    retrieval_path: list[str] = Field(default_factory=list)
    vector_status: Literal["disabled", "unavailable", "queried", "error"]
    vector_backend: str | None = None
    vector_backend_health: str | None = None
    vector_adapter_name: str | None = None
    vector_hit_count: int | None = Field(default=None, ge=0)
    graph_status: Literal["unavailable", "skipped"]
    graph_mode: RagGraphMode = "off"
    graph_entity_count: int | None = Field(default=None, ge=0)
    graph_relation_count: int | None = Field(default=None, ge=0)
    graph_candidate_count: int | None = Field(default=None, ge=0)
    graph_used: bool | None = None
    graph_fallback_reason: str | None = None
    rerank_status: Literal["disabled", "skipped", "applied", "error"]
    fallback_reason: str | None = None
    latency_ms: float | None = None
    public_chunk_count: int | None = None
    public_policy_demo_chunk_count: int | None = None
    private_chunk_count: int | None = None
    graph_entities: list[GraphEntity] = Field(default_factory=list)
    graph_relations: list[GraphRelation] = Field(default_factory=list)
    graph_candidates: list[GraphCandidate] = Field(default_factory=list)
    trace: RetrievalTrace = Field(default_factory=RetrievalTrace)
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


class RagRetrievalResult(BaseModel):
    query: str
    total_hits: int
    chunks: list[RagEvidenceChunk] = Field(default_factory=list)
    references: list[RagEvidenceReference] = Field(default_factory=list)
    metadata: RagRetrievalMetadata

    @property
    def hits(self) -> list[dict[str, Any]]:
        return [chunk.to_retrieved_hit() for chunk in self.chunks]
