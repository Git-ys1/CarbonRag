from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from app.auth.schemas import AuthenticatedUser
from app.core.config import REPO_ROOT, get_settings, resolve_repo_path
from app.file_preview.schemas import FilePreviewChunk, FilePreviewResponse, FilePreviewSourceType
from app.knowledge import get_knowledge_service, get_policy_crawler_scheduler
from app.rag.spine import get_rag_spine_service

MAX_PREVIEW_CHARS = 250_000
INLINE_MIME_PREFIXES = ("image/", "text/")
INLINE_MIME_TYPES = {"application/pdf"}


@dataclass(frozen=True)
class FilePreviewRaw:
    path: Path
    filename: str
    mime_type: str


class FilePreviewService:
    def preview(
        self,
        *,
        source_type: FilePreviewSourceType,
        source_id: str,
        current_user: AuthenticatedUser,
        kb_id: str | None = None,
    ) -> FilePreviewResponse:
        if source_type == "session_file":
            return self._session_file_preview(file_id=source_id, current_user=current_user)
        if source_type == "knowledge_item":
            return self._knowledge_item_preview(knowledge_item_id=source_id, current_user=current_user)
        if source_type == "rag_document":
            if not kb_id:
                raise KeyError("kb_id is required for rag_document preview")
            return self._rag_document_preview(kb_id=kb_id, doc_id=source_id, current_user=current_user)
        if source_type == "crawler_candidate":
            return self._crawler_candidate_preview(candidate_id=source_id, current_user=current_user)
        raise KeyError(source_type)

    def raw(
        self,
        *,
        source_type: FilePreviewSourceType,
        source_id: str,
        current_user: AuthenticatedUser,
        kb_id: str | None = None,
    ) -> FilePreviewRaw:
        if source_type == "session_file":
            preview = self._session_file_preview(file_id=source_id, current_user=current_user)
            return self._raw_from_metadata(preview.metadata, fallback_filename=preview.filename or preview.title)
        if source_type == "knowledge_item":
            preview = self._knowledge_item_preview(knowledge_item_id=source_id, current_user=current_user)
            return self._raw_from_metadata(preview.metadata, fallback_filename=preview.filename or preview.title)
        if source_type == "rag_document":
            if not kb_id:
                raise KeyError("kb_id is required for rag_document raw preview")
            preview = self._rag_document_preview(kb_id=kb_id, doc_id=source_id, current_user=current_user)
            return self._raw_from_metadata(preview.metadata, fallback_filename=preview.filename or preview.title)
        if source_type == "crawler_candidate":
            preview = self._crawler_candidate_preview(candidate_id=source_id, current_user=current_user)
            return self._raw_from_metadata(preview.metadata, fallback_filename=preview.filename or preview.title)
        raise KeyError(source_type)

    def _session_file_preview(self, *, file_id: str, current_user: AuthenticatedUser) -> FilePreviewResponse:
        store = get_knowledge_service().store
        payload = (
            store.get_uploaded_file_detail_any_owner(file_id=file_id)
            if current_user.role in {"admin", "super_admin"}
            else store.get_uploaded_file_detail(owner_user_id=current_user.user_id, file_id=file_id)
        )
        if payload is None:
            raise KeyError(file_id)
        if current_user.role not in {"admin", "super_admin"} and payload.get("owner_user_id") != current_user.user_id:
            raise PermissionError(file_id)

        parse_result = store.get_file_parse_result(file_id=file_id) or {}
        knowledge_item_id = payload.get("knowledge_item_id")
        chunks = self._knowledge_chunks(knowledge_item_id) if knowledge_item_id else []
        metadata = {
            **self._filter_none(payload),
            "parse_result": self._filter_none(parse_result),
            "storage_path": payload.get("storage_path"),
        }
        return self._response(
            source_type="session_file",
            source_id=file_id,
            title=str(payload.get("filename") or file_id),
            filename=payload.get("filename"),
            mime_type=payload.get("mime_type"),
            size=payload.get("size"),
            status=str(payload.get("parse_status") or payload.get("index_status") or "uploaded"),
            source_url=None,
            markdown=parse_result.get("extracted_markdown"),
            text=parse_result.get("extracted_text"),
            chunks=chunks,
            metadata=metadata,
            raw_path=payload.get("storage_path"),
        )

    def _knowledge_item_preview(self, *, knowledge_item_id: str, current_user: AuthenticatedUser) -> FilePreviewResponse:
        store = get_knowledge_service().store
        item = store.get_item(knowledge_item_id) if current_user.role in {"admin", "super_admin"} else store.get_visible_item(
            owner_user_id=current_user.user_id,
            knowledge_item_id=knowledge_item_id,
        )
        if item is None:
            raise KeyError(knowledge_item_id)

        parse_result = store.get_file_parse_result(file_id=item.file_id) if item.file_id else None
        chunks = self._knowledge_chunks(knowledge_item_id)
        metadata = {
            **self._filter_none(item.model_dump(mode="python")),
            "parse_result": self._filter_none(parse_result or {}),
            "storage_path": item.storage_path,
        }
        markdown = (parse_result or {}).get("extracted_markdown")
        text = (parse_result or {}).get("extracted_text") or "\n\n".join(chunk.text for chunk in chunks)
        return self._response(
            source_type="knowledge_item",
            source_id=knowledge_item_id,
            title=item.title,
            filename=Path(item.storage_path).name if item.storage_path else item.title,
            mime_type=item.mime_type,
            size=None,
            status=item.index_status,
            source_url=item.source_url,
            markdown=markdown,
            text=text,
            chunks=chunks,
            metadata=metadata,
            raw_path=item.storage_path,
        )

    def _rag_document_preview(self, *, kb_id: str, doc_id: str, current_user: AuthenticatedUser) -> FilePreviewResponse:
        service = get_rag_spine_service()
        doc = service.get_document(owner_user_id=current_user.user_id, kb_id=kb_id, doc_id=doc_id)
        chunks = [
            FilePreviewChunk(
                chunk_id=chunk.rag_chunk_id,
                doc_id=chunk.doc_id,
                kb_id=chunk.kb_id,
                order_index=chunk.chunk_index,
                text=chunk.text,
                title=doc.title,
                source_type=doc.source_type,
                source_url=doc.metadata.get("source_url"),
                page_number=chunk.page_number,
                sheet_name=chunk.sheet_name,
                slide_number=chunk.slide_number,
                section_title=chunk.section_title,
                vector_status=chunk.vector_status,
                metadata=chunk.metadata,
            )
            for chunk in service.list_chunks(owner_user_id=current_user.user_id, kb_id=kb_id, doc_id=doc_id)
        ]
        markdown = self._metadata_text(doc.metadata, "parsed_markdown", "markdown")
        text = self._metadata_text(doc.metadata, "text", "cleaned_text", "raw_text") or "\n\n".join(chunk.text for chunk in chunks)
        metadata = {
            **self._filter_none(doc.model_dump(mode="python")),
            "storage_path": doc.file_path,
        }
        return self._response(
            source_type="rag_document",
            source_id=doc_id,
            title=doc.title,
            filename=doc.filename,
            mime_type=self._guess_mime(doc.filename or doc.file_path or doc.file_type),
            size=doc.file_size,
            status=doc.index_status or doc.status,
            source_url=doc.metadata.get("source_url"),
            markdown=markdown,
            text=text,
            chunks=chunks,
            metadata=metadata,
            raw_path=doc.file_path,
            kb_id=kb_id,
        )

    def _crawler_candidate_preview(self, *, candidate_id: str, current_user: AuthenticatedUser) -> FilePreviewResponse:
        if current_user.role not in {"admin", "super_admin"}:
            raise PermissionError(candidate_id)
        candidate = get_policy_crawler_scheduler().store.get_candidate(candidate_id)
        if candidate is None:
            raise KeyError(candidate_id)
        metadata = dict(candidate.metadata)
        markdown = self._read_registered_text(metadata.get("markdown_storage_path"))
        text = self._read_registered_text(metadata.get("cleaned_storage_path")) or self._read_registered_text(candidate.storage_path)
        chunks: list[FilePreviewChunk] = []
        rag_kb_id = metadata.get("rag_kb_id")
        rag_doc_id = metadata.get("rag_doc_id")
        if isinstance(rag_kb_id, str) and isinstance(rag_doc_id, str):
            try:
                chunks = [
                    FilePreviewChunk(
                        chunk_id=chunk.rag_chunk_id,
                        doc_id=chunk.doc_id,
                        kb_id=chunk.kb_id,
                        order_index=chunk.chunk_index,
                        text=chunk.text,
                        title=candidate.title,
                        source_type="public_policy",
                        source_url=candidate.url,
                        page_number=chunk.page_number,
                        sheet_name=chunk.sheet_name,
                        slide_number=chunk.slide_number,
                        section_title=chunk.section_title,
                        vector_status=chunk.vector_status,
                        metadata=chunk.metadata,
                    )
                    for chunk in get_rag_spine_service().list_chunks(
                        owner_user_id=current_user.user_id,
                        kb_id=rag_kb_id,
                        doc_id=rag_doc_id,
                    )
                ]
            except KeyError:
                chunks = []
        return self._response(
            source_type="crawler_candidate",
            source_id=candidate_id,
            title=candidate.title or candidate.url,
            filename=Path(candidate.storage_path).name,
            mime_type=candidate.content_type,
            size=None,
            status=candidate.status,
            source_url=candidate.url,
            markdown=markdown,
            text=text,
            chunks=chunks,
            metadata={
                **self._filter_none(candidate.model_dump(mode="python")),
                "storage_path": candidate.storage_path,
            },
            raw_path=candidate.storage_path,
        )

    def _response(
        self,
        *,
        source_type: FilePreviewSourceType,
        source_id: str,
        title: str,
        filename: str | None,
        mime_type: str | None,
        size: int | None,
        status: str,
        source_url: str | None,
        markdown: str | None,
        text: str | None,
        chunks: list[FilePreviewChunk],
        metadata: dict[str, Any],
        raw_path: str | None,
        kb_id: str | None = None,
    ) -> FilePreviewResponse:
        markdown, markdown_truncated = self._truncate(markdown)
        text, text_truncated = self._truncate(text)
        raw = self._safe_path(raw_path)
        raw_available = raw is not None and raw.exists() and raw.is_file()
        raw_mime = mime_type or self._guess_mime(filename or str(raw_path or ""))
        query = f"?{urlencode({'kb_id': kb_id})}" if kb_id else ""
        raw_url = f"/api/v1/file-previews/{source_type}/{source_id}/raw{query}" if raw_available else None
        tabs = []
        if markdown:
            tabs.append("markdown")
        if text:
            tabs.append("text")
        if chunks:
            tabs.append("chunks")
        if raw_available:
            tabs.append("raw")
        tabs.append("metadata")
        return FilePreviewResponse(
            source_type=source_type,
            source_id=source_id,
            title=title,
            filename=filename,
            mime_type=raw_mime,
            size=size,
            status=status,
            source_url=source_url,
            markdown=markdown,
            text=text,
            chunks=chunks,
            metadata=metadata,
            raw_available=raw_available,
            raw_preview_url=raw_url,
            raw_download_url=raw_url,
            can_inline_raw=raw_available and self._can_inline(raw_mime),
            available_tabs=tabs,
            truncated=markdown_truncated or text_truncated,
        )

    def _knowledge_chunks(self, knowledge_item_id: str) -> list[FilePreviewChunk]:
        return [
            FilePreviewChunk(
                chunk_id=chunk.chunk_id,
                order_index=chunk.order_index,
                text=chunk.snippet,
                title=chunk.title,
                source_type=chunk.source_type,
                source_url=chunk.source_url,
                page_number=self._int_or_none(chunk.metadata.get("page_number")),
                sheet_name=self._str_or_none(chunk.metadata.get("sheet_name")),
                slide_number=self._int_or_none(chunk.metadata.get("slide_number")),
                section_title=self._str_or_none(chunk.metadata.get("section_title")),
                vector_status="indexed",
                metadata=chunk.metadata,
            )
            for chunk in get_knowledge_service().store.list_chunks(knowledge_item_id=knowledge_item_id)
        ]

    def _raw_from_metadata(self, metadata: dict[str, Any], *, fallback_filename: str) -> FilePreviewRaw:
        path_value = metadata.get("storage_path") or metadata.get("file_path")
        path = self._safe_path(path_value)
        if path is None or not path.exists() or not path.is_file():
            raise FileNotFoundError(path_value or fallback_filename)
        return FilePreviewRaw(
            path=path,
            filename=Path(str(path_value or fallback_filename)).name or fallback_filename,
            mime_type=self._guess_mime(str(path)),
        )

    def _read_registered_text(self, path_value: object) -> str | None:
        path = self._safe_path(path_value)
        if path is None or not path.exists() or not path.is_file():
            return None
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        return self._truncate(text)[0]

    def _safe_path(self, path_value: object) -> Path | None:
        if not isinstance(path_value, str) or not path_value.strip():
            return None
        candidate = Path(path_value)
        roots = {
            resolve_repo_path(get_settings().upload_dir).resolve(),
            resolve_repo_path(get_settings().public_data_dir).resolve(),
            (REPO_ROOT / "backend" / "data").resolve(),
            (REPO_ROOT / "data").resolve(),
        }
        candidates = [candidate] if candidate.is_absolute() else [REPO_ROOT / candidate, REPO_ROOT / "backend" / candidate, Path.cwd() / candidate]
        resolved_candidates = [item.resolve() for item in candidates]
        for resolved in resolved_candidates:
            if resolved.exists() and any(self._is_relative_to(resolved, root) for root in roots):
                return resolved
        for resolved in resolved_candidates:
            if any(self._is_relative_to(resolved, root) for root in roots):
                return resolved
        return None

    @staticmethod
    def _is_relative_to(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
        except ValueError:
            return False
        return True

    @staticmethod
    def _metadata_text(metadata: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return None

    @staticmethod
    def _filter_none(payload: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in payload.items() if value is not None}

    @staticmethod
    def _truncate(value: str | None) -> tuple[str | None, bool]:
        if value is None:
            return None, False
        if len(value) <= MAX_PREVIEW_CHARS:
            return value, False
        return value[:MAX_PREVIEW_CHARS], True

    @staticmethod
    def _guess_mime(value: str | None) -> str | None:
        if not value:
            return None
        guessed, _ = mimetypes.guess_type(value)
        return guessed

    @staticmethod
    def _can_inline(mime_type: str | None) -> bool:
        if not mime_type:
            return False
        return mime_type in INLINE_MIME_TYPES or any(mime_type.startswith(prefix) for prefix in INLINE_MIME_PREFIXES)

    @staticmethod
    def _int_or_none(value: object) -> int | None:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _str_or_none(value: object) -> str | None:
        return value if isinstance(value, str) and value else None


def get_file_preview_service() -> FilePreviewService:
    return FilePreviewService()
