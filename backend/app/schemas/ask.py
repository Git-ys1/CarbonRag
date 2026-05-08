from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.settings.schemas import LocalProviderOverride


KnowledgeScope = Literal["public", "private_sample", "mixed"]
AskStatus = Literal["ok", "provider_error", "invalid_input"]
MessageStatus = Literal["pending", "thinking", "streaming", "done", "error", "ok", "provider_error", "invalid_input"]
CitationSourceType = Literal["public_policy", "public_policy_demo", "private_sample", "private_upload"]


class AskCitation(BaseModel):
    doc_id: str
    knowledge_item_id: str | None = None
    title: str
    source_type: CitationSourceType = "public_policy"
    source: str
    source_url: str | None = None
    snippet: str
    chunk_id: str
    library_scope: Literal["personal", "shared"] | None = None


class AskSourceSummary(BaseModel):
    knowledge_scope: KnowledgeScope
    public_policy_count: int = 0
    public_policy_demo_count: int = 0
    private_sample_count: int = 0
    private_upload_count: int = 0
    total_citation_count: int = 0


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str
    knowledge_scope: KnowledgeScope = "public"
    top_k: int = Field(default=5, ge=1)
    attached_file_ids: list[str] = Field(default_factory=list)
    attached_knowledge_item_ids: list[str] = Field(default_factory=list)
    request_group_id: str | None = None
    resume_cursor: int | None = Field(default=None, ge=0)
    provider_override: LocalProviderOverride | None = None

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        return value.strip()

    @field_validator("request_group_id")
    @classmethod
    def normalize_request_group_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class AskResponse(BaseModel):
    answer: str
    mode: Literal["ask"]
    status: AskStatus
    citations: list[AskCitation] = Field(default_factory=list)
    source_summary: AskSourceSummary
    trace_id: str
