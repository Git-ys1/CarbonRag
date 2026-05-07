from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.auth.schemas import UserRole
from app.knowledge.schemas import KnowledgeItemSummary, KnowledgeTaskSummary

KnowledgeRefreshScope = Literal["public_policy", "private_sample", "all"]
KnowledgeRefreshStatus = Literal["queued", "running", "succeeded", "failed"]


class AdminUserSummary(BaseModel):
    user_id: str
    username: str
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

    role: UserRole
    is_active: bool


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
