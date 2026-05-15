from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.auth.schemas import UserRole
from app.knowledge.schemas import KnowledgeItemSummary, KnowledgeTaskSummary

KnowledgeRefreshScope = Literal["public_policy", "private_sample", "all"]
KnowledgeRefreshStatus = Literal["queued", "running", "succeeded", "failed"]
PolicyCrawlerCandidateStatus = Literal["pending_review", "published", "rejected"]


class AdminUserSummary(BaseModel):
    user_id: str
    username: str
    display_name: str
    role: UserRole
    is_active: bool
    password_must_change: bool
    created_at: datetime
    last_login_at: datetime | None = None
    session_count: int = 0
    report_count: int = 0
    feedback_count: int = 0


class UpdateAdminUserRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "admin"]
    is_active: bool


class DeleteAdminUsersRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_ids: list[str] = Field(min_length=1)
    current_password: str = Field(min_length=6, max_length=128)


class DeleteAdminUsersResponse(BaseModel):
    status: Literal["ok"] = "ok"
    deleted_user_ids: list[str]


class AdminFeedbackRecentEntry(BaseModel):
    feedback_id: str
    target_type: str
    rating: str
    session_id: str | None = None
    owner_user_id: str | None = None
    created_at: datetime


class AdminFeedbackOverview(BaseModel):
    total_count: int = 0
    ask_up_count: int = 0
    ask_down_count: int = 0
    calc_up_count: int = 0
    calc_down_count: int = 0
    recent_entries: list[AdminFeedbackRecentEntry] = Field(default_factory=list)


class AdminPrivateSampleItem(BaseModel):
    doc_id: str
    title: str
    source_type: str
    sample_type: str
    business_topic: str
    session_attachable: bool
    is_enabled: bool


class PolicyShowcaseSourceSummary(BaseModel):
    source_id: str
    title: str
    source_url: str
    source_label: str
    description: str
    default_query: str
    content_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyShowcaseWorkflowNodeSummary(BaseModel):
    node_id: str
    node_type: str
    status: str
    input_ref: str | None = None
    output_ref: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None
    retry_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyShowcaseWorkflowSummary(BaseModel):
    workflow_id: str
    workflow_type: str
    status: str
    current_node: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    nodes: list[PolicyShowcaseWorkflowNodeSummary] = Field(default_factory=list)


class PolicyShowcaseChunkSummary(BaseModel):
    chunk_id: str
    knowledge_item_id: str
    title: str
    source_type: str
    source: str
    source_url: str | None = None
    issued_at: str | None = None
    region: str | None = None
    doc_type: str | None = None
    snippet: str
    order_index: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyShowcaseRetrievalHit(BaseModel):
    chunk_id: str
    knowledge_item_id: str | None = None
    title: str
    source_type: str
    source: str
    source_url: str | None = None
    issued_at: str | None = None
    region: str | None = None
    doc_type: str | None = None
    snippet: str
    score: float
    matched_source: bool = False


class PolicyShowcaseRetrievalPreview(BaseModel):
    source_id: str
    query: str
    top_k: int
    total_hits: int
    hits: list[PolicyShowcaseRetrievalHit] = Field(default_factory=list)


class PolicyShowcaseStatus(BaseModel):
    source: PolicyShowcaseSourceSummary
    item: KnowledgeItemSummary | None = None
    latest_task: KnowledgeTaskSummary | None = None
    workflow: PolicyShowcaseWorkflowSummary | None = None
    chunks: list[PolicyShowcaseChunkSummary] = Field(default_factory=list)
    retrieval_preview: PolicyShowcaseRetrievalPreview | None = None
    indexed: bool = False


class PolicyCrawlerSourceSummary(BaseModel):
    source_id: str
    title: str
    source_url: str
    source_label: str
    allowed_domain: str
    is_enabled: bool
    schedule_interval_seconds: int | None = None
    last_run_id: str | None = None
    last_run_status: str | None = None
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    last_error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    source_category: str | None = None
    region: str | None = None
    priority: int | None = None
    topic_tags: list[str] = Field(default_factory=list)
    parser_profile: str | None = None
    review_required: bool | None = None
    target_rag_kb_id: str | None = None
    recommendation_reason: str | None = None
    risk_level: str | None = None

    @model_validator(mode="before")
    @classmethod
    def derive_registry_fields(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        metadata = value.get("metadata") if isinstance(value.get("metadata"), dict) else {}
        value.setdefault("source_category", metadata.get("source_category") or metadata.get("scope"))
        value.setdefault("region", metadata.get("region"))
        value.setdefault("priority", metadata.get("priority"))
        raw_tags = metadata.get("topic_tags")
        value.setdefault("topic_tags", raw_tags if isinstance(raw_tags, list) else [])
        value.setdefault("parser_profile", metadata.get("parser_profile") or metadata.get("discovery_mode"))
        value.setdefault("review_required", metadata.get("review_required"))
        value.setdefault("target_rag_kb_id", metadata.get("target_rag_kb_id"))
        value.setdefault("recommendation_reason", metadata.get("recommendation_reason"))
        value.setdefault("risk_level", metadata.get("risk_level"))
        return value


class PolicyCrawlerSourceUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=3, max_length=96)
    title: str = Field(min_length=2, max_length=240)
    source_url: str = Field(min_length=8, max_length=1000)
    source_label: str = Field(min_length=2, max_length=120)
    allowed_domain: str | None = Field(default=None, max_length=160)
    is_enabled: bool = False
    schedule_interval_seconds: int | None = Field(default=None, ge=60, le=2_592_000)
    source_category: str | None = Field(default=None, max_length=80)
    region: str | None = Field(default=None, max_length=80)
    priority: int = Field(default=50, ge=0, le=100)
    topic_tags: list[str] = Field(default_factory=list)
    start_urls: list[str] = Field(default_factory=list)
    extra_start_urls: list[str] = Field(default_factory=list)
    include_patterns: list[str] = Field(default_factory=list)
    exclude_patterns: list[str] = Field(default_factory=list)
    required_keywords: list[str] = Field(default_factory=list)
    optional_keywords: list[str] = Field(default_factory=list)
    crawl_mode: str = "listing"
    parser_profile: str = "generic_html"
    max_depth: int = Field(default=1, ge=0, le=5)
    max_pages: int = Field(default=20, ge=1, le=100)
    download_delay_seconds: float = Field(default=1.0, ge=0.0, le=30.0)
    schedule_enabled: bool = False
    review_required: bool = True
    target_rag_kb_id: str | None = Field(default=None, max_length=160)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyCrawlerDryRunCandidateSummary(BaseModel):
    url: str
    title: str | None = None
    content_type: str
    http_status: int | None = None
    matched_keywords: list[str] = Field(default_factory=list)
    skip_reason: str | None = None
    candidate_quality_score: int = 0
    quality_breakdown: dict[str, int] = Field(default_factory=dict)
    cleaned_markdown_preview: str = ""
    estimated_chunk_count: int = 0
    target_rag_kb_id: str | None = None
    canonical_url: str | None = None


class PolicyCrawlerDryRunSummary(BaseModel):
    source_id: str
    status: str
    provider_name: str | None = None
    start_urls: list[str] = Field(default_factory=list)
    robots_obey: bool = True
    candidate_count: int = 0
    skipped_count: int = 0
    target_rag_kb_id: str | None = None
    candidates: list[PolicyCrawlerDryRunCandidateSummary] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyCrawlerRecommendedImportSummary(BaseModel):
    imported_count: int
    enabled_count: int
    sources: list[PolicyCrawlerSourceSummary] = Field(default_factory=list)


class PolicyCrawlerRunSummary(BaseModel):
    run_id: str
    source_id: str
    trigger_type: str
    triggered_by_user_id: str | None = None
    status: str
    provider_name: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
    document_count: int = 0
    candidate_count: int = 0
    error_detail: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyCrawlerCandidateSummary(BaseModel):
    candidate_id: str
    run_id: str
    source_id: str
    url: str
    title: str | None = None
    content_type: str
    content_hash: str
    source_name: str | None = None
    fetched_at: datetime | None = None
    status: PolicyCrawlerCandidateStatus
    reviewed_by_user_id: str | None = None
    reviewed_at: datetime | None = None
    review_note: str | None = None
    knowledge_item_id: str | None = None
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
    rag_kb_id: str | None = None
    rag_doc_id: str | None = None
    rag_pipeline_status: str | None = None
    rag_indexed_chunk_count: int | None = None
    rag_search_smoke_passed: bool | None = None
    rag_error_stage: str | None = None
    rag_error_detail: str | None = None
    candidate_quality_score: int | None = None
    extraction_quality_score: int | None = None
    topic_relevance_score: int | None = None
    topic_class: str | None = None
    artifact_errors: list[str] = Field(default_factory=list)
    cleaned_size: int | None = None
    markdown_size: int | None = None
    estimated_chunk_count: int | None = None
    quality_breakdown: dict[str, Any] = Field(default_factory=dict)
    matched_keywords: list[str] = Field(default_factory=list)
    skip_reason: str | None = None

    @model_validator(mode="before")
    @classmethod
    def derive_rag_fields(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        metadata = value.get("metadata") if isinstance(value.get("metadata"), dict) else {}
        value.setdefault("rag_kb_id", metadata.get("rag_kb_id"))
        value.setdefault("rag_doc_id", metadata.get("rag_doc_id"))
        value.setdefault("rag_pipeline_status", metadata.get("rag_pipeline_status"))
        value.setdefault("rag_indexed_chunk_count", metadata.get("rag_indexed_chunk_count") or metadata.get("indexed_chunk_count"))
        value.setdefault("rag_search_smoke_passed", metadata.get("rag_search_smoke_passed"))
        value.setdefault("rag_error_stage", metadata.get("rag_error_stage") or metadata.get("error_stage"))
        value.setdefault("rag_error_detail", metadata.get("rag_error_detail") or metadata.get("error_detail"))
        value.setdefault("candidate_quality_score", metadata.get("candidate_quality_score"))
        value.setdefault("extraction_quality_score", metadata.get("extraction_quality_score"))
        value.setdefault("topic_relevance_score", metadata.get("topic_relevance_score"))
        value.setdefault("topic_class", metadata.get("topic_class"))
        value.setdefault("artifact_errors", metadata.get("artifact_errors") if isinstance(metadata.get("artifact_errors"), list) else [])
        value.setdefault("cleaned_size", metadata.get("cleaned_size"))
        value.setdefault("markdown_size", metadata.get("markdown_size"))
        value.setdefault("estimated_chunk_count", metadata.get("estimated_chunk_count"))
        value.setdefault("quality_breakdown", metadata.get("quality_breakdown") or {})
        raw_keywords = metadata.get("matched_keywords") or metadata.get("matched_policy_keywords")
        value.setdefault("matched_keywords", raw_keywords if isinstance(raw_keywords, list) else [])
        value.setdefault("skip_reason", metadata.get("skip_reason"))
        return value


class PolicyCrawlerCandidateArtifactsSummary(BaseModel):
    candidate_id: str
    raw_exists: bool
    cleaned_exists: bool
    markdown_exists: bool
    raw_size: int = 0
    cleaned_size: int = 0
    markdown_size: int = 0
    markdown_preview: str = ""
    cleaned_text_preview: str = ""
    raw_excerpt: str = ""
    estimated_chunk_count: int = 0
    artifact_errors: list[str] = Field(default_factory=list)
    extraction_quality_score: int | None = None
    topic_relevance_score: int | None = None
    topic_class: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyCrawlerStatusSummary(BaseModel):
    scheduler_started: bool
    scheduled_enabled: bool
    manual_enabled: bool
    auto_publish_enabled: bool = False
    running: bool
    crawler_backend: str
    provider_name: str
    provider_mode: str
    provider_enabled: bool
    provider_available: bool
    local_scrapy_available: bool | None = None
    scrapyd_available: bool | None = None
    scrapyd_endpoint_label: str | None = None
    provider_error: str | None = None
    external_job_id: str | None = None
    interval_seconds: int
    initial_delay_seconds: float
    source_count: int = 0
    pending_candidate_count: int = 0
    recent_run_status: str | None = None
    safe_limits: dict[str, Any] = Field(default_factory=dict)


class UpdateAdminPrivateSampleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_enabled: bool
    session_attachable: bool


class KnowledgeRefreshTask(BaseModel):
    task_id: str
    scope: KnowledgeRefreshScope
    status: KnowledgeRefreshStatus
    requested_by_user_id: str | None = None
    summary: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class TriggerKnowledgeRefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: KnowledgeRefreshScope = "all"


class AdminSystemStatus(BaseModel):
    app_name: str
    version: str
    env: str
    database_backend: str
    model_provider_mode: str
    model_name: str
    total_users: int
    total_sessions: int
    total_reports: int
    total_feedback_entries: int
    total_private_samples: int
    enabled_private_samples: int
    latest_refresh_status: KnowledgeRefreshStatus | None = None
    total_knowledge_items: int = 0
    total_knowledge_tasks: int = 0
