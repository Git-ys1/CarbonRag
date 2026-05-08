from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.settings.schemas import LocalProviderOverride

ReportType = Literal["policy_summary", "mixed_analysis", "carbon_summary"]
ReportOutputFormat = Literal["markdown"]
ReportStatus = Literal["ok"]
ReportSourceType = Literal["message", "citation", "carbon_result"]
ReportCitationSourceType = Literal["public_policy", "public_policy_demo", "private_sample", "carbon_factor"]


class ReportCitation(BaseModel):
    source_type: ReportCitationSourceType
    title: str
    source: str
    source_url: str | None = None
    snippet: str
    chunk_id: str | None = None
    factor_id: str | None = None


class ReportSourceSummary(BaseModel):
    public_policy_count: int = 0
    public_policy_demo_count: int = 0
    private_sample_count: int = 0
    carbon_factor_count: int = 0
    total_citation_count: int = 0


class ReportSourceEntry(BaseModel):
    source_type: ReportSourceType
    source_ref: str
    label: str
    order_index: int


class CreateReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    report_type: ReportType
    title: str | None = None
    source_message_ids: list[str] = Field(default_factory=list)
    carbon_result_id: str | None = None
    output_format: ReportOutputFormat = "markdown"
    request_group_id: str | None = None
    resume_cursor: int | None = Field(default=None, ge=0)
    provider_override: LocalProviderOverride | None = None

    @field_validator("session_id", "title", "carbon_result_id", "request_group_id")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("source_message_ids")
    @classmethod
    def normalize_source_message_ids(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(item.strip() for item in value if item.strip()))

    @model_validator(mode="after")
    def require_session_id(self) -> "CreateReportRequest":
        if not self.session_id:
            raise ValueError("session_id is required.")
        return self


class UpdateReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    content: str

    @field_validator("title", "content")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def require_content(self) -> "UpdateReportRequest":
        if not self.content:
            raise ValueError("content cannot be empty.")
        return self


class ReportSummary(BaseModel):
    report_id: str
    report_type: ReportType
    title: str
    created_at: datetime
    updated_at: datetime
    source_count: int


class ReportDetail(BaseModel):
    report_id: str
    session_id: str
    report_type: ReportType
    title: str
    status: ReportStatus = "ok"
    content: str
    output_format: ReportOutputFormat = "markdown"
    citations: list[ReportCitation] = Field(default_factory=list)
    source_summary: ReportSourceSummary = Field(default_factory=ReportSourceSummary)
    sources: list[ReportSourceEntry] = Field(default_factory=list)
    trace_id: str
    created_at: datetime
    updated_at: datetime


class StoredReport(BaseModel):
    report_id: str
    session_id: str
    report_type: ReportType
    title: str
    content: str
    output_format: ReportOutputFormat
    citations: list[ReportCitation]
    source_summary: ReportSourceSummary
    sources: list[ReportSourceEntry]
    trace_id: str
    created_at: datetime
    updated_at: datetime


class ReportSection(BaseModel):
    heading: str
    body: str


class ReportGenerationPayload(BaseModel):
    title: str
    sections: list[ReportSection]
