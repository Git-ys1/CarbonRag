from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Literal, Protocol
from urllib.parse import urlparse
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import Settings, get_settings
from app.knowledge.chunker import chunk_knowledge_text
from app.knowledge.schemas import KnowledgeChunk, KnowledgeItem
from app.rag.contracts import DocumentBlock, ParsedDocument, hash_content
from app.rag.parser import ParserRegistry


DEFAULT_POLICY_CRAWLER_ALLOWED_DOMAINS: tuple[str, ...] = (
    "www.gov.cn",
    "www.ndrc.gov.cn",
    "ndrc.gov.cn",
    "www.mee.gov.cn",
    "mee.gov.cn",
    "www.miit.gov.cn",
    "miit.gov.cn",
    "www.beijing.gov.cn",
    "beijing.gov.cn",
    "fgw.beijing.gov.cn",
    "sthjj.beijing.gov.cn",
    "jxj.beijing.gov.cn",
)

PolicyCrawlerStatus = Literal["disabled", "unavailable", "succeeded", "failed", "rejected"]
PolicyExpiryStatus = Literal["active", "expired", "unknown"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PolicyCrawlerValidationError(ValueError):
    pass


class CrawlerProviderDescriptor(BaseModel):
    name: str
    mode: str = "optional"
    enabled: bool = False
    available: bool = False


class PolicyCrawlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_urls: list[str] = Field(min_length=1)
    allowed_domains: list[str] = Field(default_factory=lambda: list(DEFAULT_POLICY_CRAWLER_ALLOWED_DOMAINS))
    max_depth: int = Field(default=1, ge=0, le=5)
    max_pages: int = Field(default=50, ge=1, le=200)
    obey_robots: bool = True
    download_delay_seconds: float = Field(default=1.0, ge=0.0)
    concurrent_requests_per_domain: int = Field(default=2, ge=1, le=4)
    timeout_seconds: float = Field(default=60.0, ge=1.0, le=300.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("start_urls")
    @classmethod
    def validate_urls(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for raw_url in value:
            url = raw_url.strip()
            if not url:
                raise ValueError("policy crawl URL cannot be blank")
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError(f"policy crawl URL must be http(s): {raw_url}")
            normalized.append(url)
        return list(dict.fromkeys(normalized))

    @field_validator("allowed_domains")
    @classmethod
    def validate_allowed_domains(cls, value: list[str]) -> list[str]:
        normalized = [_normalize_domain(domain) for domain in value if domain.strip()]
        if not normalized:
            raise ValueError("policy crawler requires at least one allowed domain")
        return list(dict.fromkeys(normalized))


class CrawledDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    title: str | None = None
    content: str = ""
    content_type: str = "text/html"
    status_code: int | None = Field(default=200, ge=100, le=599)
    source_name: str | None = None
    fetched_at: datetime = Field(default_factory=_utcnow)
    raw_storage_path: str | None = None
    content_hash: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        if not self.content_hash:
            self.content_hash = hash_content(self.content)


class CrawlResult(BaseModel):
    provider_name: str
    status: PolicyCrawlerStatus
    documents: list[CrawledDocument] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class StagedPolicyDocument(BaseModel):
    crawled: CrawledDocument
    storage_path: str
    mime_type: str
    staged_at: datetime = Field(default_factory=_utcnow)


class CrawlerProvider(Protocol):
    def describe(self) -> CrawlerProviderDescriptor:
        ...

    def crawl(self, request: PolicyCrawlRequest) -> CrawlResult:
        ...


class FakeCrawlerProvider:
    provider_name = "fake-policy-crawler"

    def __init__(self, *, documents: list[CrawledDocument] | None = None, enabled: bool = True) -> None:
        self.documents = documents or []
        self.enabled = enabled

    def describe(self) -> CrawlerProviderDescriptor:
        return CrawlerProviderDescriptor(
            name=self.provider_name,
            mode="fake",
            enabled=self.enabled,
            available=True,
        )

    def crawl(self, request: PolicyCrawlRequest) -> CrawlResult:
        if not self.enabled:
            return CrawlResult(provider_name=self.provider_name, status="disabled", errors=["Policy crawler is disabled."])
        try:
            validate_policy_crawl_request(request)
        except PolicyCrawlerValidationError as exc:
            return CrawlResult(provider_name=self.provider_name, status="rejected", errors=[str(exc)])
        return CrawlResult(
            provider_name=self.provider_name,
            status="succeeded",
            documents=self.documents,
            metadata={"offline": True, "requested_urls": request.start_urls},
        )


class ScrapyCrawlerProvider:
    provider_name = "scrapy-policy-crawler"

    def __init__(
        self,
        *,
        enabled: bool | None = None,
        runner: Callable[[PolicyCrawlRequest], list[CrawledDocument]] | None = None,
        settings: Settings | None = None,
    ) -> None:
        resolved_settings = settings or get_settings()
        self.enabled = resolved_settings.rag_enable_policy_crawler if enabled is None else enabled
        self.runner = runner

    @property
    def crawler_available(self) -> bool:
        return importlib.util.find_spec("scrapy") is not None

    def describe(self) -> CrawlerProviderDescriptor:
        return CrawlerProviderDescriptor(
            name=self.provider_name,
            mode="scrapy",
            enabled=self.enabled,
            available=self.crawler_available,
        )

    def crawl(self, request: PolicyCrawlRequest) -> CrawlResult:
        if not self.enabled:
            return CrawlResult(provider_name=self.provider_name, status="disabled", errors=["Policy crawler is disabled."])
        try:
            validate_policy_crawl_request(request)
        except PolicyCrawlerValidationError as exc:
            return CrawlResult(provider_name=self.provider_name, status="rejected", errors=[str(exc)])
        if not self.crawler_available:
            return CrawlResult(provider_name=self.provider_name, status="unavailable", errors=["Scrapy is not installed."])
        try:
            documents = self.runner(request) if self.runner is not None else _run_scrapy_crawler_subprocess(request)
        except Exception as exc:  # noqa: BLE001
            return CrawlResult(provider_name=self.provider_name, status="failed", errors=[str(exc)])
        return CrawlResult(
            provider_name=self.provider_name,
            status="succeeded",
            documents=documents,
            metadata=_scrapy_settings_metadata(request),
        )


class ConvertedPolicyDocument(BaseModel):
    success: bool
    path: str | None = None
    content_type: str | None = None
    converter_name: str = "ofdrw"
    converter_available: bool = False
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class OfdrwConverterAdapter:
    converter_name = "ofdrw"

    def __init__(self, *, converter: Any | None = None, output_format: str = "pdf") -> None:
        self.converter = converter
        self.output_format = output_format

    @property
    def converter_available(self) -> bool:
        return self.converter is not None or importlib.util.find_spec("ofdrw") is not None

    def convert(self, path: str | Path) -> ConvertedPolicyDocument:
        resolved_path = Path(path)
        if not self.converter_available:
            return ConvertedPolicyDocument(
                success=False,
                converter_available=False,
                error="OFDRW converter is unavailable.",
                metadata={"source_file": str(resolved_path), "output_format": self.output_format},
            )
        if self.converter is None:
            return ConvertedPolicyDocument(
                success=False,
                converter_available=True,
                error="OFDRW converter adapter requires an injected converter runner.",
                metadata={"source_file": str(resolved_path), "output_format": self.output_format},
            )
        try:
            converted = self.converter.convert(str(resolved_path))
        except Exception as exc:  # noqa: BLE001
            return ConvertedPolicyDocument(
                success=False,
                converter_available=True,
                error=str(exc),
                metadata={"source_file": str(resolved_path), "output_format": self.output_format},
            )
        converted_path = getattr(converted, "path", converted)
        target_path = Path(str(converted_path))
        content_type = "application/pdf" if target_path.suffix.lower() == ".pdf" else "text/html"
        return ConvertedPolicyDocument(
            success=True,
            path=str(target_path),
            content_type=content_type,
            converter_available=True,
            metadata={"source_file": str(resolved_path), "output_format": self.output_format},
        )


class PolicyDocumentParser:
    def __init__(
        self,
        *,
        parser_registry: ParserRegistry | None = None,
        ofd_converter: OfdrwConverterAdapter | None = None,
        settings: Settings | None = None,
    ) -> None:
        resolved_settings = settings or get_settings()
        self.parser_registry = parser_registry or ParserRegistry(
            preferred_provider="docling",
            enable_mineru=resolved_settings.rag_enable_mineru,
            fallback_chain=resolved_settings.rag_parser_fallback_chain,
        )
        self.ofd_converter = ofd_converter or OfdrwConverterAdapter()

    def parse_staged_document(
        self,
        *,
        path: str | Path,
        content_type: str,
        source_url: str | None = None,
        title: str | None = None,
    ) -> ParsedDocument:
        resolved_path = Path(path)
        normalized_content_type = _normalize_content_type(content_type, resolved_path)
        if normalized_content_type == "text/html":
            return self._parse_html(path=resolved_path, source_url=source_url, title=title)
        if normalized_content_type == "application/ofd":
            converted = self.ofd_converter.convert(resolved_path)
            if not converted.success or converted.path is None or converted.content_type is None:
                return self._failed_document(
                    path=resolved_path,
                    content_type=normalized_content_type,
                    source_url=source_url,
                    title=title,
                    error=converted.error or "OFD conversion failed.",
                    metadata={
                        "parser_name": "ofdrw",
                        "converter_name": converted.converter_name,
                        "converter_available": converted.converter_available,
                        **converted.metadata,
                    },
                )
            parsed = self.parse_staged_document(
                path=converted.path,
                content_type=converted.content_type,
                source_url=source_url,
                title=title,
            )
            return parsed.model_copy(
                update={
                    "metadata": {
                        **parsed.metadata,
                        "converted_from": "ofd",
                        "converter_name": converted.converter_name,
                        "converter_available": converted.converter_available,
                    }
                }
            )
        parsed = self.parser_registry.parse(resolved_path, content_type=normalized_content_type)
        return self._with_policy_context(
            parsed,
            source_url=source_url,
            title=title,
            content_type=normalized_content_type,
        )

    def _parse_html(self, *, path: Path, source_url: str | None, title: str | None) -> ParsedDocument:
        raw_html = _read_text(path)
        extracted = _extract_html_text(raw_html)
        document_title = title or extracted.title or path.name
        document_id = f"policy-html-{hash_content(source_url or str(path))[:12]}"
        blocks = _blocks_from_text(extracted.text, document_id=document_id)
        metadata = {
            "parser_name": "carbonrag-html",
            "parser_version": "1.0",
            "source_file": str(path),
            "source_url": source_url,
            "parse_success": bool(extracted.text.strip()),
            "parse_error": None if extracted.text.strip() else "HTML document returned empty text.",
            "parser_chain": ["carbonrag-html:success"] if extracted.text.strip() else ["carbonrag-html:failed"],
            **extracted.metadata,
        }
        return ParsedDocument(
            document_id=document_id,
            source_uri=source_url or str(path),
            source_type="public_policy_web",
            title=document_title,
            text=extracted.text,
            mime_type="text/html",
            source_path=str(path),
            parser_name="carbonrag-html",
            quality_score=0.8 if extracted.text.strip() else 0.0,
            blocks=blocks,
            metadata=metadata,
            visibility="public",
        )

    @staticmethod
    def _with_policy_context(
        parsed: ParsedDocument,
        *,
        source_url: str | None,
        title: str | None,
        content_type: str,
    ) -> ParsedDocument:
        metadata = {
            **parsed.metadata,
            "source_url": source_url,
            "policy_content_type": content_type,
            "original_source_uri": parsed.source_uri,
            "parse_success": parsed.metadata.get("parse_success", bool(parsed.text.strip())),
        }
        if "parser_chain" not in metadata:
            status = "success" if metadata.get("parse_success") is True else "failed"
            metadata["parser_chain"] = [f"{parsed.parser_name}:{status}"]
        return parsed.model_copy(
            update={
                "source_uri": source_url or parsed.source_uri,
                "source_type": "public_policy_web",
                "title": title or parsed.title,
                "mime_type": parsed.mime_type or content_type,
                "visibility": "public",
                "metadata": metadata,
            }
        )

    @staticmethod
    def _failed_document(
        *,
        path: Path,
        content_type: str,
        source_url: str | None,
        title: str | None,
        error: str,
        metadata: dict[str, Any] | None = None,
    ) -> ParsedDocument:
        payload = {
            "source_file": str(path),
            "source_url": source_url,
            "parse_success": False,
            "parse_error": error,
            **(metadata or {}),
        }
        return ParsedDocument(
            document_id=f"policy-error-{hash_content(source_url or str(path))[:12]}",
            source_uri=source_url or str(path),
            source_type="public_policy_web",
            title=title or path.name,
            text="",
            mime_type=content_type,
            source_path=str(path),
            parser_name=str(payload.get("parser_name") or "policy-parser"),
            quality_score=0.0,
            blocks=[],
            metadata=payload,
            visibility="public",
        )


class PolicyClauseAnchor(BaseModel):
    anchor_id: str
    label: str
    text: str
    order_index: int = Field(ge=1)
    page: int | None = Field(default=None, ge=1)
    source_url: str | None = None


class PolicyGovernanceMetadata(BaseModel):
    issuing_authority: str | None = None
    document_number: str | None = None
    publication_date: str | None = None
    effective_date: str | None = None
    expiry_status: PolicyExpiryStatus = "unknown"
    region: str | None = None
    industry: str | None = None
    topic_tags: list[str] = Field(default_factory=list)
    clause_anchors: list[PolicyClauseAnchor] = Field(default_factory=list)
    source_url: str | None = None
    source_title: str | None = None
    crawl_fetched_at: str | None = None
    content_hash: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class HtmlExtractionResult(BaseModel):
    title: str | None = None
    text: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


def validate_policy_crawl_request(request: PolicyCrawlRequest) -> None:
    for url in request.start_urls:
        if not is_allowed_policy_url(url, allowed_domains=request.allowed_domains):
            raise PolicyCrawlerValidationError(f"Policy crawl URL is outside the official allowlist: {url}")


def is_allowed_policy_url(url: str, *, allowed_domains: list[str] | tuple[str, ...] | None = None) -> bool:
    host = _url_host(url)
    if not host:
        return False
    allowed = allowed_domains or DEFAULT_POLICY_CRAWLER_ALLOWED_DOMAINS
    return any(host == domain or host.endswith(f".{domain}") for domain in (_normalize_domain(item) for item in allowed))


def stage_crawled_document(document: CrawledDocument, *, staging_dir: Path | str) -> StagedPolicyDocument:
    target_dir = Path(staging_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    suffix = _suffix_for_content_type(document.content_type)
    target_path = target_dir / f"policy-{hash_content(document.url)[:12]}{suffix}"
    target_path.write_text(document.content, encoding="utf-8")
    document.raw_storage_path = str(target_path)
    return StagedPolicyDocument(crawled=document, storage_path=str(target_path), mime_type=_normalize_content_type(document.content_type, target_path))


def build_policy_web_knowledge_item(
    *,
    staged: StagedPolicyDocument,
    knowledge_item_id: str | None = None,
    created_at: datetime | None = None,
) -> KnowledgeItem:
    now = created_at or _utcnow()
    crawled = staged.crawled
    visibility = "demo" if _is_demo_showcase_document(crawled) else "public"
    return KnowledgeItem(
        knowledge_item_id=knowledge_item_id or f"policy-web-{hash_content(crawled.url)[:12]}",
        tenant_id=None,
        owner_user_id=None,
        visibility=visibility,
        created_by=None,
        library_scope="shared",
        source_type="public_policy_web",
        source_ref=crawled.url,
        file_id=None,
        source=crawled.source_name or _infer_authority_from_url(crawled.url),
        source_url=crawled.url,
        sample_type=None,
        business_topic="policy",
        title=crawled.title or crawled.url,
        mime_type=staged.mime_type,
        storage_path=staged.storage_path,
        parse_status="pending",
        ingest_status="pending",
        index_status="pending",
        is_enabled=True,
        session_attachable=True,
        source_hash=crawled.content_hash,
        source_mtime=staged.staged_at.isoformat(),
        last_error=None,
        created_at=now,
        updated_at=now,
        last_indexed_at=None,
    )


def normalize_policy_governance_metadata(
    *,
    parsed: ParsedDocument,
    crawled: CrawledDocument | None = None,
    source_url: str | None = None,
) -> PolicyGovernanceMetadata:
    text = parsed.text or ""
    resolved_source_url = source_url or (crawled.url if crawled else parsed.source_uri)
    merged_metadata: dict[str, Any] = {}
    if crawled is not None:
        merged_metadata.update(crawled.metadata)
    merged_metadata.update(parsed.metadata)

    publication_date = _first_metadata_value(merged_metadata, "publication_date", "issued_at") or _extract_first_date(text)
    return PolicyGovernanceMetadata(
        issuing_authority=_first_metadata_value(merged_metadata, "issuing_authority") or _infer_authority_from_url(resolved_source_url),
        document_number=_first_metadata_value(merged_metadata, "document_number") or _extract_document_number(text),
        publication_date=publication_date,
        effective_date=_first_metadata_value(merged_metadata, "effective_date") or _extract_effective_date(text) or publication_date,
        expiry_status=_normalize_expiry_status(merged_metadata.get("expiry_status")),
        region=_first_metadata_value(merged_metadata, "region") or _infer_region(text=text, url=resolved_source_url),
        industry=_first_metadata_value(merged_metadata, "industry") or _infer_industry(text),
        topic_tags=_infer_topic_tags(text),
        clause_anchors=_extract_clause_anchors(text, source_url=resolved_source_url),
        source_url=resolved_source_url,
        source_title=parsed.title or (crawled.title if crawled else None),
        crawl_fetched_at=crawled.fetched_at.isoformat() if crawled else None,
        content_hash=crawled.content_hash if crawled else hash_content(text),
        metadata=merged_metadata,
    )


def build_policy_chunks(
    *,
    item: KnowledgeItem,
    parsed: ParsedDocument,
    policy_metadata: PolicyGovernanceMetadata,
    created_at: datetime,
) -> list[KnowledgeChunk]:
    chunks = chunk_knowledge_text(item=item, text=parsed.text, created_at=created_at)
    metadata_payload = policy_metadata.model_dump(mode="json")
    is_demo_showcase = item.visibility == "demo" or str(metadata_payload.get("source_kind") or "").startswith("demo")
    for chunk in chunks:
        chunk.source_url = policy_metadata.source_url or item.source_url
        chunk.issued_at = policy_metadata.publication_date
        chunk.region = policy_metadata.region
        chunk.doc_type = "policy"
        chunk.metadata = {
            **metadata_payload,
            "original_source_type": item.source_type,
            "retrieval_source_type": chunk.source_type,
            "chunk_content_hash": hash_content(chunk.snippet),
            "parser_name": parsed.parser_name,
        }
        if is_demo_showcase:
            chunk.metadata.update(
                {
                    "showcase_source": metadata_payload.get("showcase_source") or "demo_synthetic",
                    "source_kind": metadata_payload.get("source_kind") or "demo_showcase",
                    "is_synthetic": True,
                    "citation_source_type": "public_policy_demo",
                    "citation_disclaimer": metadata_payload.get("citation_disclaimer")
                    or "内置演示样例，不代表真实官方政策，不可作为官方政策依据引用。",
                }
            )
    return chunks


def _is_demo_showcase_document(crawled: CrawledDocument) -> bool:
    source_kind = str(crawled.metadata.get("source_kind") or "").strip().lower()
    showcase_source = str(crawled.metadata.get("showcase_source") or "").strip().lower()
    citation_source_type = str(crawled.metadata.get("citation_source_type") or "").strip().lower()
    return (
        source_kind in {"demo_showcase", "showcase_demo"}
        or showcase_source in {"demo_synthetic", "built_in_showcase"}
        or citation_source_type == "public_policy_demo"
    )


def _scrapy_settings_metadata(request: PolicyCrawlRequest) -> dict[str, Any]:
    return {
        "robots_obey": request.obey_robots,
        "download_delay_seconds": request.download_delay_seconds,
        "concurrent_requests_per_domain": request.concurrent_requests_per_domain,
        "max_depth": request.max_depth,
        "max_pages": request.max_pages,
        "timeout_seconds": request.timeout_seconds,
    }


def _run_scrapy_crawler_subprocess(request: PolicyCrawlRequest) -> list[CrawledDocument]:
    backend_dir = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="carbonrag-scrapy-") as tmp_dir:
        request_path = Path(tmp_dir) / "request.json"
        output_path = Path(tmp_dir) / "documents.json"
        request_path.write_text(request.model_dump_json(), encoding="utf-8")
        command = [
            sys.executable,
            "-m",
            "app.knowledge.policy_scrapy_runner",
            "--request",
            str(request_path),
            "--output",
            str(output_path),
        ]
        completed = subprocess.run(
            command,
            cwd=backend_dir,
            capture_output=True,
            text=True,
            timeout=request.timeout_seconds,
            check=False,
        )
        if completed.returncode != 0:
            stderr = completed.stderr.strip() or completed.stdout.strip() or "Scrapy runner failed."
            raise RuntimeError(stderr)
        if not output_path.exists():
            raise RuntimeError("Scrapy runner did not produce an output document file.")
        payload = json.loads(output_path.read_text(encoding="utf-8") or "[]")
        if not isinstance(payload, list):
            raise RuntimeError("Scrapy runner returned an invalid document payload.")
        return [CrawledDocument.model_validate(item) for item in payload]


def _extract_html_text(raw_html: str) -> HtmlExtractionResult:
    parser = _ReadableHtmlParser()
    parser.feed(raw_html)
    text = parser.text
    return HtmlExtractionResult(title=parser.title, text=text, metadata=_extract_html_policy_metadata(text))


class _ReadableHtmlParser(HTMLParser):
    block_tags = {"p", "div", "section", "article", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}
    skip_tags = {"script", "style", "noscript", "nav", "footer"}
    skip_attr_tokens = {
        "breadcrumb",
        "copyright",
        "footer",
        "menu",
        "nav",
        "pagination",
        "qrcode",
        "related",
        "share",
        "sidebar",
        "toolbar",
    }

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._title_parts: list[str] = []
        self._in_title = False
        self._skip_stack: list[str] = []

    @property
    def title(self) -> str | None:
        title = " ".join(part.strip() for part in self._title_parts if part.strip()).strip()
        return title or None

    @property
    def text(self) -> str:
        normalized = "\n".join(part.strip() for part in self._parts if part.strip())
        normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()
        return _dedupe_adjacent_lines(normalized)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.skip_tags or self._attrs_indicate_boilerplate(attrs):
            self._skip_stack.append(tag)
        if tag == "title":
            self._in_title = True
        if not self._skip_stack and (tag in self.block_tags or tag == "br"):
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._skip_stack:
            while self._skip_stack:
                skipped_tag = self._skip_stack.pop()
                if skipped_tag == tag:
                    break
        if tag == "title":
            self._in_title = False
        if not self._skip_stack and tag in self.block_tags:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        normalized = re.sub(r"\s+", " ", data).strip()
        if not normalized:
            return
        if self._in_title:
            self._title_parts.append(normalized)
        if self._skip_stack:
            return
        self._parts.append(normalized)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "br" and not self._skip_stack and not self._attrs_indicate_boilerplate(attrs):
            self._parts.append("\n")

    @classmethod
    def _attrs_indicate_boilerplate(cls, attrs: list[tuple[str, str | None]]) -> bool:
        values: list[str] = []
        for key, value in attrs:
            if key.lower() in {"class", "id", "role", "aria-label"} and value:
                values.append(value.lower())
        joined = " ".join(values).replace("_", "-")
        return any(token in joined for token in cls.skip_attr_tokens)


def _extract_html_policy_metadata(text: str) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    publication_date = _extract_first_date(text)
    if publication_date:
        metadata["publication_date"] = publication_date
    source_label = _extract_source_label(text)
    if source_label:
        metadata["source_label"] = source_label
        metadata["issuing_authority"] = source_label
    return metadata


def _extract_source_label(text: str) -> str | None:
    match = re.search(r"(?:来源|信息来源|发文机关|发布机构)[:：]\s*([^\n\r]{2,60})", text)
    if not match:
        return None
    value = re.split(r"(?:\s|　)*(?:时间|日期|发布时间|发布日期)[:：]?", match.group(1).strip(), maxsplit=1)[0]
    return value.strip(" ：:，,。") or None


def _dedupe_adjacent_lines(text: str) -> str:
    lines: list[str] = []
    previous = ""
    for line in (part.strip() for part in text.splitlines()):
        if not line:
            if lines and lines[-1]:
                lines.append("")
            continue
        if line == previous:
            continue
        lines.append(line)
        previous = line
    return "\n".join(lines).strip()


def _blocks_from_text(text: str, *, document_id: str) -> list[DocumentBlock]:
    blocks: list[DocumentBlock] = []
    for index, segment in enumerate((part.strip() for part in text.split("\n") if part.strip()), start=1):
        block_type = "title" if index == 1 and len(segment) <= 80 else "paragraph"
        blocks.append(
            DocumentBlock(
                block_id=f"policy-block-{index:04d}",
                document_id=document_id,
                block_type=block_type,  # type: ignore[arg-type]
                text=segment,
                order_index=index,
            )
        )
    return blocks


def _extract_clause_anchors(text: str, *, source_url: str | None) -> list[PolicyClauseAnchor]:
    anchors: list[PolicyClauseAnchor] = []
    for line in (part.strip() for part in text.splitlines()):
        if not line:
            continue
        for match in re.finditer(r"(第[一二三四五六七八九十百千万\d]+条)\s*([^第]{0,500})", line):
            label = match.group(1)
            clause_text = f"{label} {match.group(2).strip()}".strip()
            anchors.append(
                PolicyClauseAnchor(
                    anchor_id=f"clause-{len(anchors) + 1:04d}",
                    label=label,
                    text=clause_text[:500],
                    order_index=len(anchors) + 1,
                    source_url=source_url,
                )
            )
    return anchors


def _extract_document_number(text: str) -> str | None:
    match = re.search(r"[\u4e00-\u9fa5A-Za-z]{1,12}[〔\[]\d{4}[〕\]]\s*\d+\s*号", text)
    return match.group(0) if match else None


def _extract_first_date(text: str) -> str | None:
    match = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text)
    if not match:
        return None
    year, month, day = match.groups()
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def _extract_effective_date(text: str) -> str | None:
    match = re.search(r"(?:自|于)(\d{4})年(\d{1,2})月(\d{1,2})日(?:起)?(?:施行|实施)", text)
    if not match:
        return None
    year, month, day = match.groups()
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def _infer_topic_tags(text: str) -> list[str]:
    candidates = {
        "碳达峰": "碳达峰",
        "碳中和": "碳中和",
        "碳核算": "碳核算",
        "排放": "碳排放",
        "节能": "节能",
        "绿色": "绿色低碳",
    }
    return [tag for keyword, tag in candidates.items() if keyword in text]


def _infer_industry(text: str) -> str | None:
    if "工业" in text or "制造" in text:
        return "industrial"
    if "建筑" in text:
        return "building"
    if "交通" in text or "运输" in text:
        return "transport"
    if "能源" in text or "电力" in text:
        return "energy"
    return None


def _infer_region(*, text: str, url: str | None) -> str:
    if (url and "beijing" in url.lower()) or "北京" in text:
        return "beijing"
    return "national"


def _infer_authority_from_url(url: str | None) -> str | None:
    if not url:
        return None
    host = _url_host(url) or ""
    if "ndrc.gov.cn" in host:
        return "国家发展和改革委员会"
    if "mee.gov.cn" in host:
        return "生态环境部"
    if "miit.gov.cn" in host:
        return "工业和信息化部"
    if "beijing.gov.cn" in host:
        return "北京市人民政府"
    if "gov.cn" in host:
        return "中国政府网"
    return None


def _normalize_expiry_status(value: Any) -> PolicyExpiryStatus:
    normalized = str(value or "").strip().lower()
    if normalized in {"active", "expired", "unknown"}:
        return normalized  # type: ignore[return-value]
    if normalized in {"有效", "现行有效"}:
        return "active"
    if normalized in {"失效", "废止"}:
        return "expired"
    return "unknown"


def _first_metadata_value(metadata: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _normalize_content_type(content_type: str | None, path: Path) -> str:
    value = (content_type or "").split(";", 1)[0].strip().lower()
    if value:
        if value in {"application/ofd", "application/vnd.ofd"}:
            return "application/ofd"
        return value
    suffix = path.suffix.lower()
    if suffix in {".html", ".htm"}:
        return "text/html"
    if suffix == ".pdf":
        return "application/pdf"
    if suffix == ".ofd":
        return "application/ofd"
    return "application/octet-stream"


def _suffix_for_content_type(content_type: str) -> str:
    normalized = content_type.split(";", 1)[0].strip().lower()
    if normalized == "text/html":
        return ".html"
    if normalized == "application/pdf":
        return ".pdf"
    if normalized in {"application/ofd", "application/vnd.ofd"}:
        return ".ofd"
    return ".txt"


def _read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def _normalize_domain(domain: str) -> str:
    parsed = urlparse(domain if "://" in domain else f"https://{domain}")
    return (parsed.hostname or domain).lower().strip(".")


def _url_host(url: str | None) -> str | None:
    if not url:
        return None
    return (urlparse(url).hostname or "").lower().strip(".") or None


def new_policy_task_id() -> str:
    return f"ktask-policy-{uuid4().hex[:12]}"
