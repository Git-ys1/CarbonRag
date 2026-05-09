from __future__ import annotations

import importlib
from importlib import metadata as importlib_metadata
from pathlib import Path
import re
from typing import Any, Protocol

from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.knowledge.parsers import KnowledgeParseError, parse_document
from app.rag.contracts import DocumentBlock, ParsedDocument, hash_content


class ParserProviderDescriptor(BaseModel):
    name: str
    mode: str = "lightweight"
    supported_suffixes: list[str] = Field(default_factory=list)


class ParserProvider(Protocol):
    def describe(self) -> ParserProviderDescriptor:
        ...

    def supports(
        self,
        file_path: str | Path | None = None,
        content_type: str | None = None,
        *,
        mime_type: str | None = None,
        name: str | None = None,
    ) -> bool:
        ...

    def parse(
        self,
        file_path: str | Path | None = None,
        *,
        path: Path | str | None = None,
        mime_type: str | None = None,
        content_type: str | None = None,
    ) -> ParsedDocument:
        ...

    def score(self, document: ParsedDocument) -> float:
        ...


class DefaultParserProvider:
    parser_name = "carbonrag-default"
    parser_version = "1.0"
    supported_suffixes = {".txt", ".md", ".csv", ".xlsx", ".xls", ".docx", ".pdf", ".html", ".htm", ".pptx"}
    supported_content_types = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/csv",
        "text/html",
        "text/markdown",
        "text/plain",
    }

    def describe(self) -> ParserProviderDescriptor:
        return ParserProviderDescriptor(
            name=self.parser_name,
            mode="local",
            supported_suffixes=sorted(self.supported_suffixes),
        )

    def supports(
        self,
        file_path: str | Path | None = None,
        content_type: str | None = None,
        *,
        mime_type: str | None = None,
        name: str | None = None,
    ) -> bool:
        candidate_name = name or str(file_path or "")
        suffix = Path(candidate_name).suffix.lower()
        if suffix:
            return suffix in self.supported_suffixes
        resolved_content_type = content_type or mime_type
        return bool(resolved_content_type and resolved_content_type in self.supported_content_types)

    def parse(
        self,
        file_path: str | Path | None = None,
        *,
        path: Path | str | None = None,
        mime_type: str | None = None,
        content_type: str | None = None,
    ) -> ParsedDocument:
        resolved_path = Path(path or file_path or "")
        resolved_mime_type = content_type or mime_type or _guess_mime_type(resolved_path)
        if not self.supports(resolved_path, resolved_mime_type):
            return self._failed_document(
                path=resolved_path,
                mime_type=resolved_mime_type,
                error=f"Default parser does not support {resolved_path.suffix or resolved_path.name or 'unknown'}.",
            )
        try:
            parsed = parse_document(path=resolved_path, mime_type=resolved_mime_type)
        except KnowledgeParseError as exc:
            return self._failed_document(path=resolved_path, mime_type=resolved_mime_type, error=str(exc))
        except Exception as exc:  # noqa: BLE001
            return self._failed_document(path=resolved_path, mime_type=resolved_mime_type, error=str(exc))

        document_id = f"parsed-{hash_content(str(resolved_path))[:12]}"
        blocks = _structured_blocks_from_text(parsed.text, document_id=document_id)
        document = ParsedDocument(
            document_id=document_id,
            source_uri=str(resolved_path),
            source_type="local_file",
            title=resolved_path.name,
            text=parsed.text,
            mime_type=parsed.mime_type,
            source_path=str(resolved_path),
            parser_name=self.parser_name,
            blocks=blocks,
            metadata=self._metadata(
                source_file=str(resolved_path),
                parse_success=True,
                parse_error=None,
                text=parsed.text,
                blocks=blocks,
            ),
        )
        return document.model_copy(update={"quality_score": self.score(document)})

    def score(self, document: ParsedDocument) -> float:
        if not document.text.strip() or document.metadata.get("parse_success") is False:
            return 0.0
        score = 0.55
        if any(block.block_type == "title" for block in document.blocks) or document.title:
            score += 0.2
        if document.blocks:
            score += 0.15
        if any(block.page is not None for block in document.blocks):
            score += 0.1
        return min(score, 1.0)

    def _failed_document(self, *, path: Path, mime_type: str, error: str) -> ParsedDocument:
        document_id = f"parsed-{hash_content(str(path))[:12]}" if str(path) else "parsed-error"
        document = ParsedDocument(
            document_id=document_id,
            source_uri=str(path) if str(path) else None,
            source_type="local_file",
            title=path.name if str(path) else None,
            text="",
            mime_type=mime_type,
            source_path=str(path) if str(path) else None,
            parser_name=self.parser_name,
            quality_score=0.0,
            blocks=[],
            metadata=self._metadata(source_file=str(path), parse_success=False, parse_error=error),
        )
        return document

    def _metadata(
        self,
        *,
        source_file: str,
        parse_success: bool,
        parse_error: str | None,
        text: str = "",
        blocks: list[DocumentBlock] | None = None,
    ) -> dict:
        resolved_blocks = blocks or []
        page_numbers = sorted({block.page for block in resolved_blocks if block.page is not None})
        table_count = sum(1 for block in resolved_blocks if block.block_type == "table")
        metadata: dict[str, Any] = {
            "parser_name": self.parser_name,
            "parser_version": self.parser_version,
            "source": "app.knowledge.parsers",
            "source_file": source_file,
            "parse_success": parse_success,
            "parse_error": parse_error,
            "block_count": len(resolved_blocks),
            "page_count": len(page_numbers) or None,
            "table_count": table_count,
        }
        if text:
            metadata["text_length"] = len(text)
        return metadata


class LightweightParserProvider(DefaultParserProvider):
    parser_name = "carbonrag-lightweight"


class DoclingParserProvider:
    parser_name = "docling"
    supported_suffixes = {".pdf", ".docx", ".pptx", ".html", ".md", ".txt"}
    supported_content_types = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/html",
        "text/markdown",
        "text/plain",
    }

    def __init__(self, *, converter: Any | None = None) -> None:
        self._converter = converter
        self.parser_version = _optional_package_version("docling")

    def describe(self) -> ParserProviderDescriptor:
        return ParserProviderDescriptor(
            name=self.parser_name,
            mode="optional",
            supported_suffixes=sorted(self.supported_suffixes),
        )

    @property
    def parser_available(self) -> bool:
        return self._converter is not None or importlib.util.find_spec("docling") is not None

    def supports(
        self,
        file_path: str | Path | None = None,
        content_type: str | None = None,
        *,
        mime_type: str | None = None,
        name: str | None = None,
    ) -> bool:
        if not self.parser_available:
            return False
        candidate_name = name or str(file_path or "")
        suffix = Path(candidate_name).suffix.lower()
        if suffix:
            return suffix in self.supported_suffixes
        resolved_content_type = content_type or mime_type
        return bool(resolved_content_type and resolved_content_type in self.supported_content_types)

    def parse(
        self,
        file_path: str | Path | None = None,
        *,
        path: Path | str | None = None,
        mime_type: str | None = None,
        content_type: str | None = None,
    ) -> ParsedDocument:
        resolved_path = Path(path or file_path or "")
        resolved_mime_type = content_type or mime_type or _guess_mime_type(resolved_path)
        if not self.supports(resolved_path, resolved_mime_type):
            return self._failed_document(
                path=resolved_path,
                mime_type=resolved_mime_type,
                error="Docling parser is unavailable or does not support this file.",
            )
        try:
            converter = self._converter or _build_docling_converter()
            converted = converter.convert(str(resolved_path))
            text = _extract_docling_text(converted)
            if not text.strip():
                return self._failed_document(
                    path=resolved_path,
                    mime_type=resolved_mime_type,
                    error="Docling parser returned empty text.",
                )
        except Exception as exc:  # noqa: BLE001
            return self._failed_document(path=resolved_path, mime_type=resolved_mime_type, error=str(exc))

        document_id = f"docling-{hash_content(str(resolved_path))[:12]}"
        document = ParsedDocument(
            document_id=document_id,
            source_uri=str(resolved_path),
            source_type="local_file",
            title=resolved_path.name,
            text=text,
            mime_type=resolved_mime_type,
            source_path=str(resolved_path),
            parser_name=self.parser_name,
            blocks=_blocks_from_text(text, document_id=document_id),
            metadata=self._metadata(
                source_file=str(resolved_path),
                parse_success=True,
                parse_error=None,
            ),
        )
        return document.model_copy(update={"quality_score": self.score(document)})

    def score(self, document: ParsedDocument) -> float:
        if not document.text.strip() or document.metadata.get("parse_success") is False:
            return 0.0
        score = 0.6
        if any(block.block_type == "title" for block in document.blocks) or document.title:
            score += 0.15
        if document.blocks:
            score += 0.15
        if any(block.page is not None for block in document.blocks):
            score += 0.1
        return min(score, 1.0)

    def _failed_document(self, *, path: Path, mime_type: str, error: str) -> ParsedDocument:
        document_id = f"docling-{hash_content(str(path))[:12]}" if str(path) else "docling-error"
        return ParsedDocument(
            document_id=document_id,
            source_uri=str(path) if str(path) else None,
            source_type="local_file",
            title=path.name if str(path) else None,
            text="",
            mime_type=mime_type,
            source_path=str(path) if str(path) else None,
            parser_name=self.parser_name,
            quality_score=0.0,
            blocks=[],
            metadata=self._metadata(source_file=str(path), parse_success=False, parse_error=error),
        )

    def _metadata(self, *, source_file: str, parse_success: bool, parse_error: str | None) -> dict:
        return {
            "parser_name": self.parser_name,
            "parser_available": self.parser_available,
            "parser_version": self.parser_version,
            "source_file": source_file,
            "parse_success": parse_success,
            "parse_error": parse_error,
        }


class MinerUParserProvider:
    parser_name = "mineru"
    supported_suffixes = {".pdf"}
    supported_content_types = {"application/pdf"}

    def __init__(
        self,
        *,
        enabled: bool = False,
        converter: Any | None = None,
        output_format: str = "markdown",
    ) -> None:
        self.enabled = enabled
        self._converter = converter
        self.output_format = output_format
        self.parser_version = _optional_package_version("magic-pdf") or _optional_package_version("mineru")

    def describe(self) -> ParserProviderDescriptor:
        return ParserProviderDescriptor(
            name=self.parser_name,
            mode="optional-fallback",
            supported_suffixes=sorted(self.supported_suffixes),
        )

    @property
    def parser_available(self) -> bool:
        return self._converter is not None or _optional_module_available("magic_pdf", "mineru")

    def supports(
        self,
        file_path: str | Path | None = None,
        content_type: str | None = None,
        *,
        mime_type: str | None = None,
        name: str | None = None,
    ) -> bool:
        if not self.enabled or not self.parser_available:
            return False
        candidate_name = name or str(file_path or "")
        suffix = Path(candidate_name).suffix.lower()
        if suffix:
            return suffix in self.supported_suffixes
        resolved_content_type = content_type or mime_type
        return bool(resolved_content_type and resolved_content_type in self.supported_content_types)

    def parse(
        self,
        file_path: str | Path | None = None,
        *,
        path: Path | str | None = None,
        mime_type: str | None = None,
        content_type: str | None = None,
    ) -> ParsedDocument:
        resolved_path = Path(path or file_path or "")
        resolved_mime_type = content_type or mime_type or _guess_mime_type(resolved_path)
        if not self.enabled:
            return self._failed_document(
                path=resolved_path,
                mime_type=resolved_mime_type,
                error="MinerU parser is disabled.",
                fallback_reason="mineru_disabled",
            )
        if not self.supports(resolved_path, resolved_mime_type):
            return self._failed_document(
                path=resolved_path,
                mime_type=resolved_mime_type,
                error="MinerU parser is unavailable or does not support this file.",
                fallback_reason="mineru_unavailable_or_unsupported",
            )
        try:
            converter = self._converter or _build_mineru_converter()
            converted = _run_parser_converter(converter, resolved_path)
            text = _extract_parser_text(converted)
            if not text.strip():
                return self._failed_document(
                    path=resolved_path,
                    mime_type=resolved_mime_type,
                    error="MinerU parser returned empty text.",
                    fallback_reason="mineru_empty_text",
                )
        except Exception as exc:  # noqa: BLE001
            return self._failed_document(
                path=resolved_path,
                mime_type=resolved_mime_type,
                error=str(exc),
                fallback_reason="mineru_parse_failed",
            )

        document_id = f"mineru-{hash_content(str(resolved_path))[:12]}"
        document = ParsedDocument(
            document_id=document_id,
            source_uri=str(resolved_path),
            source_type="local_file",
            title=resolved_path.name,
            text=text,
            mime_type=resolved_mime_type,
            source_path=str(resolved_path),
            parser_name=self.parser_name,
            blocks=_blocks_from_text(text, document_id=document_id),
            metadata=self._metadata(
                source_file=str(resolved_path),
                parse_success=True,
                parse_error=None,
                fallback_reason=None,
            ),
        )
        return document.model_copy(update={"quality_score": self.score(document)})

    def score(self, document: ParsedDocument) -> float:
        if not document.text.strip() or document.metadata.get("parse_success") is False:
            return 0.0
        score = 0.62
        if any(block.block_type == "title" for block in document.blocks) or document.title:
            score += 0.14
        if document.blocks:
            score += 0.14
        if any(block.page is not None for block in document.blocks):
            score += 0.1
        return min(score, 1.0)

    def _failed_document(
        self,
        *,
        path: Path,
        mime_type: str,
        error: str,
        fallback_reason: str,
    ) -> ParsedDocument:
        document_id = f"mineru-{hash_content(str(path))[:12]}" if str(path) else "mineru-error"
        return ParsedDocument(
            document_id=document_id,
            source_uri=str(path) if str(path) else None,
            source_type="local_file",
            title=path.name if str(path) else None,
            text="",
            mime_type=mime_type,
            source_path=str(path) if str(path) else None,
            parser_name=self.parser_name,
            quality_score=0.0,
            blocks=[],
            metadata=self._metadata(
                source_file=str(path),
                parse_success=False,
                parse_error=error,
                fallback_reason=fallback_reason,
            ),
        )

    def _metadata(
        self,
        *,
        source_file: str,
        parse_success: bool,
        parse_error: str | None,
        fallback_reason: str | None,
    ) -> dict:
        return {
            "parser_name": self.parser_name,
            "parser_enabled": self.enabled,
            "parser_available": self.parser_available,
            "parser_version": self.parser_version,
            "source_file": source_file,
            "parse_success": parse_success,
            "parse_error": parse_error,
            "fallback_reason": fallback_reason,
            "output_format": self.output_format,
        }


class ParserRegistry:
    def __init__(
        self,
        *,
        preferred_provider: str = "default",
        default_provider: DefaultParserProvider | None = None,
        docling_provider: DoclingParserProvider | None = None,
        mineru_provider: MinerUParserProvider | None = None,
        enable_mineru: bool = False,
        fallback_chain: str | list[str] | tuple[str, ...] | None = None,
        min_optional_score: float = 0.01,
    ) -> None:
        self.preferred_provider = preferred_provider
        self.default_provider = default_provider or DefaultParserProvider()
        self.docling_provider = docling_provider or DoclingParserProvider()
        self.mineru_provider = mineru_provider or MinerUParserProvider(enabled=enable_mineru)
        self.enable_mineru = enable_mineru
        self.fallback_chain = _normalize_fallback_chain(fallback_chain)
        self.min_optional_score = min_optional_score

    def select_provider(
        self,
        file_path: str | Path | None = None,
        content_type: str | None = None,
        *,
        mime_type: str | None = None,
        name: str | None = None,
    ) -> ParserProvider:
        if self.preferred_provider == "docling" and self.docling_provider.supports(
            file_path,
            content_type,
            mime_type=mime_type,
            name=name,
        ):
            return self.docling_provider
        if self.preferred_provider == "mineru" and self.mineru_provider.supports(
            file_path,
            content_type,
            mime_type=mime_type,
            name=name,
        ):
            return self.mineru_provider
        return self.default_provider

    def parse(
        self,
        file_path: str | Path | None = None,
        *,
        path: Path | str | None = None,
        mime_type: str | None = None,
        content_type: str | None = None,
    ) -> ParsedDocument:
        resolved_path = path or file_path
        resolved_content_type = content_type or mime_type
        if self.preferred_provider not in {"docling", "mineru"}:
            return self.default_provider.parse(resolved_path, content_type=resolved_content_type)

        chain = self._chain_for_preferred_provider()
        parser_chain: list[str] = []
        fallback_reason: str | None = None
        fallback_from: str | None = None
        optional_attempts: list[str] = []

        for provider_name in chain:
            if provider_name == "default":
                fallback = self.default_provider.parse(resolved_path, content_type=resolved_content_type)
                status = "success" if fallback.metadata.get("parse_success") is True else "failed"
                parser_chain.append(f"default:{status}")
                return self._with_chain_metadata(
                    fallback,
                    parser_chain=parser_chain,
                    fallback_from=fallback_from,
                    fallback_chain_from=optional_attempts,
                    fallback_reason=fallback_reason,
                )

            optional_attempts.append(provider_name)
            if provider_name == "docling":
                parsed, status, reason = self._try_optional_provider(
                    provider=self.docling_provider,
                    provider_name="docling",
                    resolved_path=resolved_path,
                    resolved_content_type=resolved_content_type,
                    unavailable_reason="docling_unavailable_or_unsupported",
                )
            elif provider_name == "mineru":
                parsed, status, reason = self._try_mineru_provider(
                    resolved_path=resolved_path,
                    resolved_content_type=resolved_content_type,
                )
            else:
                parser_chain.append(f"{provider_name}:unknown")
                continue

            parser_chain.append(f"{provider_name}:{status}")
            if status == "success" and parsed is not None:
                return self._with_chain_metadata(
                    parsed,
                    parser_chain=parser_chain,
                    fallback_from=fallback_from,
                    fallback_chain_from=optional_attempts,
                    fallback_reason=fallback_reason,
                )
            fallback_reason = fallback_reason or reason
            fallback_from = fallback_from or provider_name

        fallback = self.default_provider.parse(resolved_path, content_type=resolved_content_type)
        status = "success" if fallback.metadata.get("parse_success") is True else "failed"
        parser_chain.append(f"default:{status}")
        return fallback.model_copy(
            update={
                "metadata": {
                    **fallback.metadata,
                    "fallback_from": fallback_from,
                    "fallback_chain_from": optional_attempts,
                    "fallback_reason": fallback_reason,
                    "parser_chain": parser_chain,
                }
            }
        )

    def _chain_for_preferred_provider(self) -> list[str]:
        if self.preferred_provider == "mineru":
            ordered = ["mineru", *[name for name in self.fallback_chain if name != "mineru"]]
        else:
            ordered = self.fallback_chain
        if "default" not in ordered:
            ordered = [*ordered, "default"]
        return ordered

    def _try_optional_provider(
        self,
        *,
        provider: ParserProvider,
        provider_name: str,
        resolved_path: str | Path | None,
        resolved_content_type: str | None,
        unavailable_reason: str,
    ) -> tuple[ParsedDocument | None, str, str | None]:
        if not provider.supports(resolved_path, resolved_content_type):
            return None, "unavailable", unavailable_reason
        parsed = provider.parse(resolved_path, content_type=resolved_content_type)
        if parsed.metadata.get("parse_success") is not True:
            reason = str(parsed.metadata.get("parse_error") or f"{provider_name}_parse_failed")
            return parsed, "failed", reason
        if provider.score(parsed) < self.min_optional_score:
            return parsed, "low_score", f"{provider_name}_low_score"
        return parsed, "success", None

    def _try_mineru_provider(
        self,
        *,
        resolved_path: str | Path | None,
        resolved_content_type: str | None,
    ) -> tuple[ParsedDocument | None, str, str | None]:
        if not self.enable_mineru:
            return None, "disabled", "mineru_disabled"
        return self._try_optional_provider(
            provider=self.mineru_provider,
            provider_name="mineru",
            resolved_path=resolved_path,
            resolved_content_type=resolved_content_type,
            unavailable_reason="mineru_unavailable_or_unsupported",
        )

    @staticmethod
    def _with_chain_metadata(
        document: ParsedDocument,
        *,
        parser_chain: list[str],
        fallback_from: str | None,
        fallback_chain_from: list[str],
        fallback_reason: str | None,
    ) -> ParsedDocument:
        metadata = {
            **document.metadata,
            "parser_chain": parser_chain,
        }
        if fallback_from:
            metadata["fallback_from"] = fallback_from
            metadata["fallback_chain_from"] = fallback_chain_from
            metadata["fallback_reason"] = fallback_reason
        return document.model_copy(update={"metadata": metadata})


def _blocks_from_text(text: str, *, document_id: str) -> list[DocumentBlock]:
    blocks: list[DocumentBlock] = []
    for index, segment in enumerate((part.strip() for part in text.split("\n\n")), start=1):
        if not segment:
            continue
        first_line = segment.splitlines()[0].strip()
        if first_line.startswith("#"):
            block_type = "title"
        elif "；" in segment and ("=" in segment or segment.startswith("表格")):
            block_type = "table"
        elif first_line.startswith(("-", "*", "1.")):
            block_type = "list"
        else:
            block_type = "paragraph"
        blocks.append(
            DocumentBlock(
                block_id=f"block-{index:04d}",
                document_id=document_id,
                block_type=block_type,  # type: ignore[arg-type]
                text=segment,
                order_index=index,
            )
        )
    return blocks


def _structured_blocks_from_text(text: str, *, document_id: str) -> list[DocumentBlock]:
    blocks: list[DocumentBlock] = []
    current_page: int | None = None
    current_section: str | None = None
    order_index = 0
    for raw_segment in (part.strip() for part in text.split("\n\n")):
        if not raw_segment:
            continue
        segment, current_page, current_section, marker_metadata = _strip_block_marker(
            raw_segment,
            current_page=current_page,
            current_section=current_section,
        )
        if not segment:
            continue
        order_index += 1
        first_line = segment.splitlines()[0].strip()
        if first_line.startswith("#"):
            block_type = "title"
        elif marker_metadata.get("marker_type") in {"table", "sheet"} or " | " in first_line:
            block_type = "table"
        elif first_line.startswith(("-", "*", "1.")):
            block_type = "list"
        else:
            block_type = "paragraph"
        blocks.append(
            DocumentBlock(
                block_id=f"block-{order_index:04d}",
                document_id=document_id,
                block_type=block_type,  # type: ignore[arg-type]
                text=segment,
                page=current_page,
                section=current_section,
                order_index=order_index,
                metadata=marker_metadata,
            )
        )
    return blocks


def _strip_block_marker(
    segment: str,
    *,
    current_page: int | None,
    current_section: str | None,
) -> tuple[str, int | None, str | None, dict[str, Any]]:
    metadata: dict[str, Any] = {}
    normalized = segment.strip()

    page_match = re.match(r"^\[(Page|Slide)\s+(\d+)\]\s*(.*)$", normalized, flags=re.IGNORECASE | re.DOTALL)
    if page_match:
        marker_type = page_match.group(1).lower()
        current_page = int(page_match.group(2))
        current_section = f"{marker_type} {current_page}"
        metadata.update({"marker_type": marker_type, "marker_value": current_page})
        return page_match.group(3).strip(), current_page, current_section, metadata

    table_match = re.match(r"^\[(Table)\s+([^\]]+)\]\s*(.*)$", normalized, flags=re.IGNORECASE | re.DOTALL)
    if table_match:
        marker_detail = table_match.group(2).strip()
        metadata.update({"marker_type": "table", "marker_value": marker_detail})
        return table_match.group(3).strip(), current_page, current_section, metadata

    sheet_match = re.match(r"^\[(Sheet)\s+([^\]]+)\]\s*(.*)$", normalized, flags=re.IGNORECASE | re.DOTALL)
    if sheet_match:
        marker_detail = sheet_match.group(2).strip()
        current_section = f"sheet {marker_detail}"
        metadata.update({"marker_type": "sheet", "marker_value": marker_detail})
        return sheet_match.group(3).strip(), current_page, current_section, metadata

    return normalized, current_page, current_section, metadata


def _guess_mime_type(path: Path) -> str:
    mapping = {
        ".csv": "text/csv",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".html": "text/html",
        ".htm": "text/html",
        ".md": "text/markdown",
        ".pdf": "application/pdf",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".txt": "text/plain",
        ".xls": "application/vnd.ms-excel",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    return mapping.get(path.suffix.lower(), "application/octet-stream")


def _optional_package_version(package_name: str) -> str | None:
    try:
        return importlib_metadata.version(package_name)
    except importlib_metadata.PackageNotFoundError:
        return None


def _optional_module_available(*module_names: str) -> bool:
    return any(importlib.util.find_spec(module_name) is not None for module_name in module_names)


def _build_docling_converter() -> Any:
    try:
        module = importlib.import_module("docling.document_converter")
        converter_cls = getattr(module, "DocumentConverter")
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("Docling is not installed. Install optional dependency `docling` first.") from exc
    return converter_cls()


def _build_mineru_converter() -> Any:
    candidate_modules = ("magic_pdf", "mineru")
    for module_name in candidate_modules:
        try:
            module = importlib.import_module(module_name)
        except Exception:  # noqa: BLE001
            continue
        for attribute_name in ("DocumentConverter", "MinerUConverter", "Converter"):
            converter_cls = getattr(module, attribute_name, None)
            if converter_cls is not None:
                return converter_cls()
    raise RuntimeError(
        "MinerU is not installed or does not expose a supported converter API. "
        "Install the optional MinerU stack or inject a converter adapter."
    )


def _run_parser_converter(converter: Any, path: Path) -> Any:
    for method_name in ("convert", "parse"):
        method = getattr(converter, method_name, None)
        if callable(method):
            return method(str(path))
    if callable(converter):
        return converter(str(path))
    raise RuntimeError("Parser converter must provide convert(), parse(), or be callable.")


def _extract_docling_text(converted: Any) -> str:
    return _extract_parser_text(converted)


def _extract_parser_text(converted: Any) -> str:
    document = getattr(converted, "document", converted)
    for method_name in ("export_to_markdown", "export_to_text"):
        method = getattr(document, method_name, None)
        if callable(method):
            text = method()
            if text:
                return str(text).strip()
    text = getattr(document, "text", None)
    if text:
        return str(text).strip()
    return str(document).strip()


def _normalize_fallback_chain(value: str | list[str] | tuple[str, ...] | None) -> list[str]:
    if value is None:
        raw_values: list[str] = ["docling", "mineru", "default"]
    elif isinstance(value, str):
        raw_values = value.split(",")
    else:
        raw_values = list(value)
    normalized: list[str] = []
    for raw_value in raw_values:
        provider_name = raw_value.strip().lower()
        if provider_name and provider_name not in normalized:
            normalized.append(provider_name)
    if not normalized:
        normalized.append("default")
    if "default" not in normalized:
        normalized.append("default")
    return normalized


def get_default_parser_provider() -> DefaultParserProvider:
    return DefaultParserProvider()


def get_lightweight_parser_provider() -> LightweightParserProvider:
    return LightweightParserProvider()


def get_parser_registry(settings: Settings | None = None) -> ParserRegistry:
    resolved_settings = settings or get_settings()
    return ParserRegistry(
        preferred_provider=resolved_settings.rag_parser_provider,
        enable_mineru=resolved_settings.rag_enable_mineru,
        fallback_chain=resolved_settings.rag_parser_fallback_chain,
    )
