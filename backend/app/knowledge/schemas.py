from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

KnowledgeItemScope = Literal["personal", "shared"]
KnowledgeItemSourceType = Literal["uploaded_file", "private_sample_repo", "public_policy_web"]
KnowledgeVisibility = Literal["public", "tenant", "private", "demo"]
KnowledgeParseStatus = Literal["pending", "running", "parsed", "parse_failed"]
KnowledgeIngestStatus = Literal["pending", "running", "ingested", "ingest_failed"]
KnowledgeIndexStatus = Literal["pending", "running", "indexed", "index_failed", "stale"]
KnowledgeItemStatus = Literal[
    "pending",
    "running",
    "parsed",
    "parse_failed",
    "ingested",
    "ingest_failed",
    "indexed",
    "index_failed",
    "stale",
]
KnowledgeTaskType = Literal["upload_ingest", "rebuild", "rescan", "retry", "crawl_ingest", "crawl_refresh"]
KnowledgeTaskStatus = Literal["queued", "running", "succeeded", "failed"]


class KnowledgeItem(BaseModel):
    knowledge_item_id: str
    tenant_id: str | None = None
    owner_user_id: str | None = None
    visibility: KnowledgeVisibility = "private"
    created_by: str | None = None
    library_scope: KnowledgeItemScope
    source_type: KnowledgeItemSourceType
    source_ref: str
    file_id: str | None = None
    source: str | None = None
    source_url: str | None = None
    sample_type: str | None = None
    business_topic: str | None = None
    title: str
    mime_type: str
    storage_path: str
    parse_status: KnowledgeParseStatus
    ingest_status: KnowledgeIngestStatus
    index_status: KnowledgeIndexStatus
    is_enabled: bool = True
    session_attachable: bool = True
    source_hash: str | None = None
    source_mtime: str | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime
    last_indexed_at: datetime | None = None
    chunk_count: int = 0
    task_count: int = 0
    latest_task_status: KnowledgeTaskStatus | None = None


class KnowledgeItemSummary(BaseModel):
    knowledge_item_id: str
    doc_id: str | None = None
    tenant_id: str | None = None
    owner_user_id: str | None = None
    visibility: KnowledgeVisibility | None = None
    created_by: str | None = None
    library_scope: KnowledgeItemScope
    source_type: KnowledgeItemSourceType
    source_ref: str
    source_label: str | None = None
    file_id: str | None = None
    title: str
    mime_type: str | None = None
    parse_status: str
    ingest_status: str
    index_status: str
    is_enabled: bool = True
    session_attachable: bool = True
    last_error: str | None = None
    updated_at: datetime | None = None
    sample_type: str | None = None
    business_topic: str | None = None
    source: str | None = None
    source_url: str | None = None
    session_id: str | None = None
    session_title: str | None = None
    uploaded_at: datetime | None = None
    size: int | None = None

    @model_validator(mode="before")
    @classmethod
    def populate_derived_fields(cls, values):
        if not isinstance(values, dict):
            return values

        payload = dict(values)
        if not payload.get("doc_id") and payload.get("source_type") == "private_sample_repo":
            payload["doc_id"] = payload.get("knowledge_item_id")
        if not payload.get("source_label"):
            source_type = payload.get("source_type")
            if source_type == "private_sample_repo":
                payload["source_label"] = "共享知识条目"
            elif source_type == "uploaded_file":
                payload["source_label"] = "上传文件"
            elif source_type == "public_policy_web":
                if payload.get("visibility") == "demo":
                    payload["source_label"] = "演示样例"
                else:
                    payload["source_label"] = "官方政策网页"
        return payload


class KnowledgeItemDetail(KnowledgeItemSummary):
    metadata: dict[str, str] = Field(default_factory=dict)
    chunk_count: int = 0
    task_count: int = 0


class KnowledgeItemListFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner_user_id: str | None = None
    library_scope: KnowledgeItemScope | None = None
    source_type: KnowledgeItemSourceType | None = None
    parse_status: KnowledgeParseStatus | None = None
    ingest_status: KnowledgeIngestStatus | None = None
    index_status: KnowledgeIndexStatus | None = None
    session_attachable: bool | None = None
    is_enabled: bool | None = None
    source_ref: str | None = None
    file_id: str | None = None
    knowledge_item_ids: list[str] = Field(default_factory=list)


class KnowledgeChunk(BaseModel):
    chunk_id: str
    knowledge_item_id: str
    tenant_id: str | None = None
    owner_user_id: str | None = None
    visibility: KnowledgeVisibility = "private"
    created_by: str | None = None
    title: str
    source_type: str
    library_scope: str
    source: str
    source_url: str | None = None
    issued_at: str | None = None
    region: str | None = None
    doc_type: str | None = None
    sample_type: str | None = None
    business_topic: str | None = None
    snippet: str
    order_index: int
    metadata: dict[str, object] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class KnowledgeChunkInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    tenant_id: str | None = None
    owner_user_id: str | None = None
    visibility: KnowledgeVisibility = "private"
    created_by: str | None = None
    title: str
    source_type: str
    library_scope: str
    source: str
    source_url: str | None = None
    issued_at: str | None = None
    region: str | None = None
    doc_type: str | None = None
    sample_type: str | None = None
    business_topic: str | None = None
    snippet: str
    order_index: int
    metadata: dict[str, object] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ParsedDocument(BaseModel):
    text: str
    mime_type: str
    source_path: str | None = None


class RepoPrivateSampleMetadata(BaseModel):
    doc_id: str
    title: str
    source_type: str
    sample_type: str
    business_topic: str
    filepath: str
    session_attachable: bool
    source: str | None = None
    source_url: str | None = None


class RepoPrivateSampleSource(BaseModel):
    metadata: RepoPrivateSampleMetadata
    storage_path: str
    mime_type: str
    source_hash: str
    source_mtime: str


class KnowledgeTaskEnqueueResult(BaseModel):
    task_id: str
    knowledge_item_id: str | None = None
    task_type: KnowledgeTaskType
    status: KnowledgeTaskStatus


class KnowledgeItemDetailResponse(BaseModel):
    item: KnowledgeItem
    chunks: list[KnowledgeChunk] = Field(default_factory=list)
    tasks: list[KnowledgeTask] = Field(default_factory=list)


class MyUploadEntry(BaseModel):
    file_id: str
    session_id: str
    filename: str
    size: int
    mime_type: str
    stored_at: datetime
    storage_path: str
    knowledge_item_id: str | None = None
    parse_status: KnowledgeParseStatus | None = None
    ingest_status: KnowledgeIngestStatus | None = None
    index_status: KnowledgeIndexStatus | None = None
    latest_task_status: KnowledgeTaskStatus | None = None


class KnowledgeTask(BaseModel):
    task_id: str
    knowledge_item_id: str | None = None
    owner_user_id: str | None = None
    requested_by_user_id: str | None = None
    task_type: KnowledgeTaskType
    status: KnowledgeTaskStatus
    summary: str | None = None
    error_detail: str | None = None
    attempt_count: int = 0
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class KnowledgeTaskSummary(BaseModel):
    task_id: str
    knowledge_item_id: str | None = None
    owner_user_id: str | None = None
    requested_by_user_id: str | None = None
    task_type: KnowledgeTaskType
    status: KnowledgeTaskStatus
    scope: str = "all"
    summary: str | None = None
    target_label: str | None = None
    last_error: str | None = Field(default=None, validation_alias="error_detail")
    error_detail: str | None = None
    attempt_count: int = 0
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class KnowledgeTaskListFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner_user_id: str | None = None
    requested_by_user_id: str | None = None
    knowledge_item_id: str | None = None
    task_type: KnowledgeTaskType | None = None
    status: KnowledgeTaskStatus | None = None


class KnowledgeTaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    knowledge_item_id: str | None = None
    owner_user_id: str | None = None
    requested_by_user_id: str | None = None
    task_type: KnowledgeTaskType
    status: KnowledgeTaskStatus
    summary: str | None = None
    error_detail: str | None = None
    attempt_count: int = 0
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
