from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.config import get_settings
from app.files.parser import get_file_parser_registry
from app.knowledge.parsers import KnowledgeParseError
from app.knowledge import get_knowledge_service
from app.knowledge.schemas import KnowledgeItemListFilters
from app.rag.documents.chunking import recursive_chunk_text
from app.rag.documents.status import resolve_document_status
from app.rag.embeddings import RagEmbeddingUnavailable, embed_documents
from app.rag.kb.models import KnowledgeBase, KnowledgeBaseCreate, KnowledgeBaseOverview, KnowledgeBaseUpdate, RagChunk, RagDocument, RagEvalRun
from app.rag.retrieval.dense import get_vector_store
from app.rag.vector_backend.base import VectorIndexResult
from app.rag.vector_backend.runtime import is_milvus_backend, resolve_vector_runtime
from app.retrieval.public_chunker import chunk_public_policy_document
from app.retrieval.public_corpus_loader import load_public_policy_documents
from app.runtime_db.bootstrap import bootstrap_runtime_database, get_runtime_backend_kind
from app.runtime_db.compat import connect_postgres
from app.session.store import DEFAULT_SESSION_DB_PATH


class RagKnowledgeStore:
    """RAG-Pro style KB store over CarbonRag runtime DB."""

    def __init__(self, *, database_url: str | None = None, sqlite_db_path: Path | str | None = None) -> None:
        settings = get_settings()
        self.database_url = database_url or settings.database_url
        self.sqlite_db_path = Path(sqlite_db_path or DEFAULT_SESSION_DB_PATH)
        self.backend_kind = get_runtime_backend_kind(self.database_url)
        self.sqlite_db_path.parent.mkdir(parents=True, exist_ok=True)
        bootstrap_runtime_database(database_url=self.database_url, sqlite_db_path=self.sqlite_db_path)

    @staticmethod
    def utcnow() -> datetime:
        return datetime.now(timezone.utc)

    def _connect(self):
        if self.backend_kind == "postgresql":
            return connect_postgres(self.database_url)
        connection = sqlite3.connect(self.sqlite_db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def create_kb(self, *, owner_user_id: str, payload: KnowledgeBaseCreate, is_default: bool = False) -> KnowledgeBase:
        now = self.utcnow().isoformat()
        kb_id = f"kb-{uuid4().hex[:12]}"
        self._ensure_user_reference(owner_user_id=owner_user_id)
        self._execute(
            """
            INSERT INTO rag_knowledge_bases (
                kb_id, owner_user_id, name, description, visibility, retrieval_mode,
                embedding_model, chunk_size, chunk_overlap, parent_chunk_size,
                rerank_top_n, retrieval_top_k, is_default, created_at, updated_at, metadata_json
            )
            VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})
            """,
            [
                kb_id,
                owner_user_id,
                payload.name,
                payload.description,
                payload.visibility,
                payload.retrieval_mode,
                payload.embedding_model,
                payload.chunk_size,
                payload.chunk_overlap,
                payload.parent_chunk_size,
                payload.rerank_top_n,
                payload.retrieval_top_k,
                is_default,
                now,
                now,
                "{}",
            ],
        )
        kb = self.get_kb(owner_user_id=owner_user_id, kb_id=kb_id)
        if kb is None:
            raise RuntimeError("rag knowledge base create failed")
        return kb

    def ensure_default_kb(self, *, owner_user_id: str) -> KnowledgeBase:
        rows = self._select(
            """
            SELECT * FROM rag_knowledge_bases
            WHERE owner_user_id = {p} AND is_default = {p}
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            [owner_user_id, True],
        )
        if rows:
            return self._row_to_kb(rows[0])
        return self.create_kb(
            owner_user_id=owner_user_id,
            payload=KnowledgeBaseCreate(name="默认知识库", description="CarbonRag 自动创建的个人 RAG-Pro 知识库。"),
            is_default=True,
        )

    def list_kbs(self, *, owner_user_id: str) -> list[KnowledgeBase]:
        rows = self._select(
            """
            SELECT * FROM rag_knowledge_bases
            WHERE owner_user_id = {p} OR visibility IN ('shared', 'public')
            ORDER BY is_default DESC, updated_at DESC
            """,
            [owner_user_id],
        )
        return [self._enrich_kb_summary(self._row_to_kb(row)) for row in rows]

    def get_kb(self, *, owner_user_id: str, kb_id: str) -> KnowledgeBase | None:
        rows = self._select(
            """
            SELECT * FROM rag_knowledge_bases
            WHERE kb_id = {p} AND (owner_user_id = {p} OR visibility IN ('shared', 'public'))
            """,
            [kb_id, owner_user_id],
        )
        return self._enrich_kb_summary(self._row_to_kb(rows[0])) if rows else None

    def update_kb(self, *, owner_user_id: str, kb_id: str, payload: KnowledgeBaseUpdate) -> KnowledgeBase:
        kb = self.get_kb(owner_user_id=owner_user_id, kb_id=kb_id)
        if kb is None or kb.owner_user_id != owner_user_id:
            raise KeyError(kb_id)
        now = self.utcnow().isoformat()
        self._execute(
            """
            UPDATE rag_knowledge_bases
            SET name = {p}, description = {p}, visibility = {p}, retrieval_mode = {p},
                embedding_model = {p}, chunk_size = {p}, chunk_overlap = {p}, parent_chunk_size = {p},
                rerank_top_n = {p}, retrieval_top_k = {p}, updated_at = {p}
            WHERE kb_id = {p} AND owner_user_id = {p}
            """,
            [
                payload.name or kb.name,
                payload.description if payload.description is not None else kb.description,
                payload.visibility or kb.visibility,
                payload.retrieval_mode or kb.retrieval_mode,
                payload.embedding_model or kb.embedding_model,
                payload.chunk_size if payload.chunk_size is not None else kb.chunk_size,
                payload.chunk_overlap if payload.chunk_overlap is not None else kb.chunk_overlap,
                payload.parent_chunk_size if payload.parent_chunk_size is not None else kb.parent_chunk_size,
                payload.rerank_top_n if payload.rerank_top_n is not None else kb.rerank_top_n,
                payload.retrieval_top_k if payload.retrieval_top_k is not None else kb.retrieval_top_k,
                now,
                kb_id,
                owner_user_id,
            ],
        )
        updated = self.get_kb(owner_user_id=owner_user_id, kb_id=kb_id)
        if updated is None:
            raise RuntimeError("rag knowledge base update failed")
        return updated

    def delete_kb(self, *, owner_user_id: str, kb_id: str) -> None:
        self._execute("DELETE FROM rag_knowledge_bases WHERE kb_id = {p} AND owner_user_id = {p}", [kb_id, owner_user_id])

    def create_document(self, *, owner_user_id: str, kb_id: str, payload: dict[str, Any]) -> RagDocument:
        self._ensure_user_reference(owner_user_id=owner_user_id)
        kb = self.get_kb(owner_user_id=owner_user_id, kb_id=kb_id)
        if kb is None:
            raise KeyError(kb_id)
        if kb.owner_user_id is None and self._is_system_kb(kb):
            self._execute(
                "UPDATE rag_knowledge_bases SET owner_user_id = {p}, updated_at = {p} WHERE kb_id = {p}",
                [owner_user_id, self.utcnow().isoformat(), kb.kb_id],
            )
            kb = self.get_kb(owner_user_id=owner_user_id, kb_id=kb_id)
            if kb is None:
                raise KeyError(kb_id)
        self._ensure_kb_writable(kb=kb, owner_user_id=owner_user_id)
        now = self.utcnow().isoformat()
        doc_id = f"rag-doc-{uuid4().hex[:12]}"
        knowledge_item_id = _optional_str(payload.get("knowledge_item_id"))
        file_id = _optional_str(payload.get("file_id"))
        title = _optional_str(payload.get("title"))
        source_type = _optional_str(payload.get("source_type")) or "manual"
        filename = _optional_str(payload.get("filename"))
        file_type = _optional_str(payload.get("file_type"))
        file_size = _optional_int(payload.get("file_size"))
        file_path = _optional_str(payload.get("file_path"))
        chunk_method = _optional_str(payload.get("chunk_method")) or "recursive"
        metadata: dict[str, Any] = {}

        if knowledge_item_id:
            item = get_knowledge_service().store.get_visible_item(owner_user_id=owner_user_id, knowledge_item_id=knowledge_item_id)
            if item is None:
                raise KeyError(knowledge_item_id)
            title = title or item.title
            file_id = file_id or item.file_id
            source_type = item.source_type
            metadata.update(
                {
                    "knowledge_item_id": item.knowledge_item_id,
                    "file_id": item.file_id,
                    "library_scope": item.library_scope,
                    "source_url": item.source_url,
                    "source": item.source,
                }
            )
            filename = filename or item.title
            file_type = file_type or Path(item.storage_path).suffix.lower().lstrip(".")
            file_path = file_path or item.storage_path
        elif payload.get("text"):
            metadata["text"] = str(payload["text"])
            for key in ("source", "source_url", "library_scope", "region", "doc_type"):
                if payload.get(key) is not None:
                    metadata[key] = payload[key]
        elif file_path:
            metadata["file_path"] = file_path
            metadata["filename"] = filename
            metadata["file_type"] = file_type

        if not title:
            title = filename or "未命名文档"
        self._execute(
            """
            INSERT INTO rag_documents (
                doc_id, kb_id, owner_user_id, knowledge_item_id, file_id,
                filename, file_type, file_size, file_path, title, source_type, chunk_method,
                status, parse_status, chunk_status, index_status, chunk_count, indexed_chunk_count,
                error_message, parse_progress, chunk_progress, error_stage, created_at, updated_at, metadata_json
            )
            VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})
            """,
            [
                doc_id,
                kb_id,
                owner_user_id,
                knowledge_item_id,
                file_id,
                filename,
                file_type,
                file_size,
                file_path,
                title,
                source_type,
                chunk_method,
                "uploaded",
                "uploaded",
                "pending",
                "pending",
                0,
                0,
                None,
                0,
                0,
                None,
                now,
                now,
                json.dumps(metadata, ensure_ascii=False),
            ],
        )
        return self.get_document(owner_user_id=owner_user_id, kb_id=kb_id, doc_id=doc_id)  # type: ignore[return-value]

    def list_documents(self, *, owner_user_id: str, kb_id: str) -> list[RagDocument]:
        self.require_kb(owner_user_id=owner_user_id, kb_id=kb_id)
        rows = self._select(
            "SELECT * FROM rag_documents WHERE kb_id = {p} ORDER BY updated_at DESC",
            [kb_id],
        )
        return [self._row_to_document(row) for row in rows]

    def get_kb_overview(self, *, owner_user_id: str, kb_id: str) -> KnowledgeBaseOverview:
        kb = self.require_kb(owner_user_id=owner_user_id, kb_id=kb_id)
        documents = self.list_documents(owner_user_id=owner_user_id, kb_id=kb_id)
        failed_count = sum(1 for doc in documents if doc.status == "failed" or bool(doc.error_stage))
        pending_count = sum(1 for doc in documents if doc.index_status != "indexed")
        return KnowledgeBaseOverview(
            kb=kb,
            documents=documents,
            document_count=len(documents),
            chunk_count=sum(doc.chunk_count for doc in documents),
            indexed_chunk_count=sum(doc.indexed_chunk_count for doc in documents),
            failed_document_count=failed_count,
            pending_document_count=pending_count,
            last_ingested_at=kb.last_ingested_at,
            health_status=kb.health_status,
            system_managed=kb.system_managed,
            read_only=kb.owner_user_id != owner_user_id or kb.system_managed,
        )

    def get_document(self, *, owner_user_id: str, kb_id: str, doc_id: str) -> RagDocument | None:
        self.require_kb(owner_user_id=owner_user_id, kb_id=kb_id)
        rows = self._select("SELECT * FROM rag_documents WHERE kb_id = {p} AND doc_id = {p}", [kb_id, doc_id])
        return self._row_to_document(rows[0]) if rows else None

    def delete_document(self, *, owner_user_id: str, kb_id: str, doc_id: str, vector_backend: str = "memory") -> None:
        doc = self._require_document(owner_user_id=owner_user_id, kb_id=kb_id, doc_id=doc_id)
        self._ensure_document_writable(doc=doc, owner_user_id=owner_user_id)
        try:
            get_vector_store(vector_backend).delete_document(kb_id=kb_id, doc_id=doc_id)
        except Exception:
            pass
        self._execute("DELETE FROM rag_chunks WHERE kb_id = {p} AND doc_id = {p}", [kb_id, doc_id])
        self._execute("DELETE FROM rag_documents WHERE kb_id = {p} AND doc_id = {p}", [kb_id, doc_id])

    def parse_document(self, *, owner_user_id: str, kb_id: str, doc_id: str) -> RagDocument:
        doc = self._require_document(owner_user_id=owner_user_id, kb_id=kb_id, doc_id=doc_id)
        self._ensure_document_writable(doc=doc, owner_user_id=owner_user_id)
        parse_status = "parsed"
        error = None
        metadata = dict(doc.metadata)
        parse_progress = 100
        error_stage = None
        if doc.knowledge_item_id:
            item = get_knowledge_service().store.get_visible_item(owner_user_id=owner_user_id, knowledge_item_id=doc.knowledge_item_id)
            if item is None:
                parse_status = "failed"
                error = "linked knowledge item is not visible"
                parse_progress = 0
                error_stage = "parse"
            elif item.parse_status not in {"parsed"} and item.index_status != "indexed":
                parse_status = "failed"
                error = f"linked knowledge item parse_status={item.parse_status}"
                parse_progress = 0
                error_stage = "parse"
        elif not doc.metadata.get("text"):
            file_path = doc.file_path or _optional_str(doc.metadata.get("file_path"))
            if file_path:
                try:
                    parsed = get_file_parser_registry().parse(path=Path(file_path), mime_type=_mime_from_doc(doc))
                    metadata.update(
                        {
                            "text": parsed.text,
                            "parsed_markdown": parsed.markdown,
                            "summary": parsed.summary,
                            "parser_name": parsed.parser_name,
                            "parser_version": parsed.parser_version,
                            "ocr_used": parsed.ocr_used,
                            "page_count": parsed.page_count,
                            "sheet_count": parsed.sheet_count,
                            "slide_count": parsed.slide_count,
                            "chunk_metadata": [item.model_dump() for item in parsed.chunk_metadata],
                            "parser_metadata": parsed.metadata,
                        }
                    )
                    self._update_document_metadata(doc_id=doc.doc_id, metadata=metadata)
                except KnowledgeParseError as exc:
                    parse_status = "failed"
                    error = str(exc)
                    parse_progress = 0
                    error_stage = "parse"
                except Exception as exc:  # noqa: BLE001
                    parse_status = "failed"
                    error = f"{type(exc).__name__}: {exc}"
                    parse_progress = 0
                    error_stage = "parse"
            else:
                parse_status = "failed"
                error = "document has no linked knowledge item, text payload, or file path"
                parse_progress = 0
                error_stage = "parse"
        return self._mark_document(
            doc=doc,
            parse_status=parse_status,
            chunk_status=doc.chunk_status,
            index_status=doc.index_status,
            error_message=error,
            parse_progress=parse_progress,
            error_stage=error_stage,
        )

    def chunk_document(self, *, owner_user_id: str, kb_id: str, doc_id: str) -> RagDocument:
        doc = self._require_document(owner_user_id=owner_user_id, kb_id=kb_id, doc_id=doc_id)
        self._ensure_document_writable(doc=doc, owner_user_id=owner_user_id)
        kb = self.require_kb(owner_user_id=owner_user_id, kb_id=kb_id)
        texts: list[tuple[str, dict[str, Any], str | None]] = []
        if doc.knowledge_item_id:
            chunks = get_knowledge_service().store.list_chunks(doc.knowledge_item_id)
            for chunk in chunks:
                texts.append(
                    (
                        chunk.snippet,
                        {
                            **chunk.metadata,
                            "title": chunk.title,
                            "source_type": chunk.source_type,
                            "library_scope": chunk.library_scope,
                            "source": chunk.source,
                            "source_url": chunk.source_url,
                            "knowledge_item_id": chunk.knowledge_item_id,
                            "file_id": doc.file_id,
                        },
                        chunk.chunk_id,
                    )
                )
        elif doc.metadata.get("text"):
            chunk_metadata = doc.metadata.get("chunk_metadata")
            meta_by_index = chunk_metadata if isinstance(chunk_metadata, list) else []
            for chunk in recursive_chunk_text(str(doc.metadata["text"]), chunk_size=kb.chunk_size, overlap=kb.chunk_overlap):
                parsed_meta = meta_by_index[chunk.chunk_index] if chunk.chunk_index < len(meta_by_index) and isinstance(meta_by_index[chunk.chunk_index], dict) else {}
                texts.append(
                    (
                        chunk.text,
                        {
                            "title": doc.title,
                            "source_type": doc.source_type,
                            "library_scope": doc.metadata.get("library_scope"),
                            "source": doc.metadata.get("source"),
                            "source_url": doc.metadata.get("source_url"),
                            "region": doc.metadata.get("region"),
                            "doc_type": doc.metadata.get("doc_type"),
                            "page_number": parsed_meta.get("page_number"),
                            "sheet_name": parsed_meta.get("sheet_name"),
                            "slide_number": parsed_meta.get("slide_number"),
                            "section_title": parsed_meta.get("section_title"),
                        },
                        None,
                    )
                )

        if not texts:
            return self._mark_document(
                doc=doc,
                parse_status=doc.parse_status,
                chunk_status="failed",
                index_status=doc.index_status,
                error_message="no chunks available",
                chunk_progress=0,
                error_stage="chunk",
            )

        self._execute("DELETE FROM rag_chunks WHERE doc_id = {p}", [doc_id])
        now = self.utcnow().isoformat()
        for index, (text, metadata, knowledge_chunk_id) in enumerate(texts):
            payload = _chunk_metadata(metadata)
            keywords = _extract_keywords(text)
            questions = _generate_questions(text)
            token_count = max(1, len(text) // 2)
            self._execute(
                """
                INSERT INTO rag_chunks (
                    rag_chunk_id, kb_id, doc_id, owner_user_id, knowledge_chunk_id, parent_chunk_id,
                    chunk_index, text, token_estimate, token_count, keywords_json, questions_json, milvus_id,
                    page_number, sheet_name, slide_number, section_title,
                    status, vector_status, dense_vector_json, sparse_vector_json, created_at, updated_at, metadata_json
                )
                VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})
                """,
                [
                    f"rag-chunk-{uuid4().hex[:12]}",
                    kb_id,
                    doc_id,
                    owner_user_id,
                    knowledge_chunk_id,
                    None,
                    index,
                    text,
                    token_count,
                    token_count,
                    json.dumps(keywords, ensure_ascii=False),
                    json.dumps(questions, ensure_ascii=False),
                    None,
                    payload.get("page_number"),
                    payload.get("sheet_name"),
                    payload.get("slide_number"),
                    payload.get("section_title"),
                    "chunked",
                    "pending",
                    None,
                    None,
                    now,
                    now,
                    json.dumps(payload, ensure_ascii=False),
                ],
            )
        return self._mark_document(
            doc=doc,
            parse_status="parsed",
            chunk_status="chunked",
            index_status="pending",
            chunk_count=len(texts),
            indexed_chunk_count=0,
            error_message=None,
            chunk_progress=100,
            error_stage=None,
        )

    def index_document(self, *, owner_user_id: str, kb_id: str, doc_id: str, vector_backend: str = "memory") -> RagDocument:
        doc = self._require_document(owner_user_id=owner_user_id, kb_id=kb_id, doc_id=doc_id)
        self._ensure_document_writable(doc=doc, owner_user_id=owner_user_id)
        chunks = self.list_chunks(owner_user_id=owner_user_id, kb_id=kb_id, doc_id=doc_id)
        if not chunks:
            doc = self.chunk_document(owner_user_id=owner_user_id, kb_id=kb_id, doc_id=doc_id)
            chunks = self.list_chunks(owner_user_id=owner_user_id, kb_id=kb_id, doc_id=doc_id)
        if not chunks:
            return self._mark_document(
                doc=doc,
                parse_status=doc.parse_status,
                chunk_status="failed",
                index_status="failed",
                error_message="no chunks to index",
            )
        now = self.utcnow().isoformat()
        runtime = resolve_vector_runtime(backend=vector_backend)
        try:
            embeddings = embed_documents([chunk.text for chunk in chunks]) if is_milvus_backend(vector_backend) else None
            vector_result = get_vector_store(vector_backend).index_chunks(chunks=chunks, embeddings=embeddings)
        except RagEmbeddingUnavailable as exc:
            vector_result = VectorIndexResult(
                indexed_count=0,
                backend=runtime.vector_runtime,
                available=False,
                degraded=True,
                warning=str(exc),
            )
        except Exception as exc:  # noqa: BLE001
            vector_result = VectorIndexResult(
                indexed_count=0,
                backend=runtime.vector_runtime,
                available=False,
                degraded=True,
                warning=str(exc),
            )

        if not vector_result.available or vector_result.indexed_count <= 0:
            self._update_document_metadata(
                doc_id=doc_id,
                metadata={
                    **doc.metadata,
                    "last_index_result": {
                        "vector_backend": vector_result.backend,
                        "degraded": True,
                        "warnings": [vector_result.warning or f"{vector_backend} index unavailable"],
                    },
                },
            )
            self._execute(
                "UPDATE rag_chunks SET vector_status = {p}, updated_at = {p} WHERE doc_id = {p}",
                [f"failed:{vector_backend}", now, doc_id],
            )
            return self._mark_document(
                doc=doc,
                parse_status=doc.parse_status,
                chunk_status="chunked",
                index_status="failed",
                indexed_chunk_count=0,
                error_message=vector_result.warning or f"{vector_backend} index unavailable",
            )

        if embeddings is not None:
            for index, chunk in enumerate(chunks):
                dense_vector = embeddings.dense[index] if index < len(embeddings.dense) else None
                sparse_vector = embeddings.sparse[index] if index < len(embeddings.sparse) else None
                self._execute(
                    """
                    UPDATE rag_chunks
                    SET vector_status = {p}, dense_vector_json = {p}, sparse_vector_json = {p}, updated_at = {p}
                    , milvus_id = {p}
                    WHERE rag_chunk_id = {p}
                    """,
                    [
                        f"indexed:{vector_result.backend}",
                        json.dumps(dense_vector, ensure_ascii=False) if dense_vector is not None else None,
                        json.dumps(sparse_vector, ensure_ascii=False) if sparse_vector is not None else None,
                        now,
                        chunk.rag_chunk_id if vector_result.backend.startswith("milvus") else None,
                        chunk.rag_chunk_id,
                    ],
                )
        else:
            self._execute("UPDATE rag_chunks SET vector_status = {p}, updated_at = {p} WHERE doc_id = {p}", [f"indexed:{vector_result.backend}", now, doc_id])
        self._update_document_metadata(
            doc_id=doc_id,
            metadata={
                **doc.metadata,
                "last_index_result": {
                    "vector_backend": vector_result.backend,
                    "degraded": bool(vector_result.degraded),
                    "warnings": [vector_result.warning] if vector_result.warning else [],
                },
            },
        )
        return self._mark_document(
            doc=doc,
            parse_status="parsed",
            chunk_status="chunked",
            index_status="indexed",
            indexed_chunk_count=vector_result.indexed_count,
            error_message=None,
            parse_progress=100,
            chunk_progress=100,
            error_stage=None,
        )

    def list_chunks(self, *, owner_user_id: str, kb_id: str, doc_id: str | None = None) -> list[RagChunk]:
        self.require_kb(owner_user_id=owner_user_id, kb_id=kb_id)
        params: list[object] = [kb_id]
        where = "kb_id = {p}"
        if doc_id:
            where += " AND doc_id = {p}"
            params.append(doc_id)
        rows = self._select(f"SELECT * FROM rag_chunks WHERE {where} ORDER BY doc_id ASC, chunk_index ASC", params)
        return [self._row_to_chunk(row) for row in rows]

    def list_searchable_chunks(
        self,
        *,
        owner_user_id: str,
        kb_id: str | None,
        knowledge_scope: str,
        allowed_knowledge_item_ids: list[str] | None = None,
    ) -> list[RagChunk]:
        params: list[object] = []
        clauses = ["c.status = 'chunked'"]
        if kb_id:
            kb = self.get_kb(owner_user_id=owner_user_id, kb_id=kb_id)
            if kb is None:
                raise KeyError(kb_id)
            clauses.append("c.kb_id = {p}")
            params.append(kb_id)
        else:
            clauses.append("(k.owner_user_id = {p} OR k.visibility IN ('shared', 'public'))")
            params.append(owner_user_id)

        if knowledge_scope == "public":
            clauses.append("d.source_type IN ('public_policy_web', 'public_policy')")
        elif knowledge_scope == "private_sample":
            if allowed_knowledge_item_ids:
                placeholders = ", ".join(self._placeholder() for _ in allowed_knowledge_item_ids)
                clauses.append(f"d.knowledge_item_id IN ({placeholders})")
                params.extend(allowed_knowledge_item_ids)
            else:
                clauses.append("d.owner_user_id = {p}")
                params.append(owner_user_id)
        elif allowed_knowledge_item_ids:
            placeholders = ", ".join(self._placeholder() for _ in allowed_knowledge_item_ids)
            clauses.append(f"(d.source_type IN ('public_policy_web', 'public_policy') OR d.knowledge_item_id IN ({placeholders}))")
            params.extend(allowed_knowledge_item_ids)
        else:
            clauses.append("(d.owner_user_id = {p} OR d.source_type IN ('public_policy_web', 'public_policy'))")
            params.append(owner_user_id)

        rows = self._select(
            f"""
            SELECT c.*
            FROM rag_chunks c
            JOIN rag_documents d ON d.doc_id = c.doc_id
            JOIN rag_knowledge_bases k ON k.kb_id = c.kb_id
            WHERE {" AND ".join(clauses)}
            ORDER BY c.updated_at DESC, c.chunk_index ASC
            """,
            params,
        )
        return [self._row_to_chunk(row) for row in rows]

    def sync_visible_knowledge(
        self,
        *,
        owner_user_id: str,
        knowledge_scope: str,
        allowed_knowledge_item_ids: list[str] | None = None,
        vector_backend: str = "memory",
    ) -> KnowledgeBase:
        kb = self.ensure_default_kb(owner_user_id=owner_user_id)
        if knowledge_scope in {"public", "mixed"}:
            self._sync_public_policy_corpus(owner_user_id=owner_user_id, kb=kb, vector_backend=vector_backend)
        filters = KnowledgeItemListFilters(
            knowledge_item_ids=allowed_knowledge_item_ids or [],
            is_enabled=True,
            session_attachable=True,
        )
        items = get_knowledge_service().list_visible_items(owner_user_id=owner_user_id, filters=filters)
        for item in items:
            if knowledge_scope == "public" and item.source_type != "public_policy_web":
                continue
            existing = self._select(
                "SELECT * FROM rag_documents WHERE kb_id = {p} AND knowledge_item_id = {p}",
                [kb.kb_id, item.knowledge_item_id],
            )
            if existing:
                continue
            doc = self.create_document(
                owner_user_id=owner_user_id,
                kb_id=kb.kb_id,
                payload={"knowledge_item_id": item.knowledge_item_id},
            )
            self.parse_document(owner_user_id=owner_user_id, kb_id=kb.kb_id, doc_id=doc.doc_id)
            self.chunk_document(owner_user_id=owner_user_id, kb_id=kb.kb_id, doc_id=doc.doc_id)
            self.index_document(owner_user_id=owner_user_id, kb_id=kb.kb_id, doc_id=doc.doc_id, vector_backend=vector_backend)
        return kb

    def _sync_public_policy_corpus(
        self,
        *,
        owner_user_id: str,
        kb: KnowledgeBase,
        vector_backend: str,
    ) -> None:
        try:
            documents = load_public_policy_documents()
        except Exception:
            return
        for public_doc in documents:
            metadata = public_doc.metadata
            existing = self._select(
                """
                SELECT * FROM rag_documents
                WHERE kb_id = {p} AND source_type = {p} AND title = {p}
                """,
                [kb.kb_id, "public_policy_web", metadata.title],
            )
            if existing:
                continue
            doc = self.create_document(
                owner_user_id=owner_user_id,
                kb_id=kb.kb_id,
                payload={
                    "title": metadata.title,
                    "text": public_doc.body,
                    "source_type": "public_policy_web",
                    "source": metadata.source,
                    "source_url": metadata.source_url,
                    "library_scope": "shared",
                    "region": metadata.region,
                    "doc_type": metadata.doc_type,
                },
            )
            self.parse_document(owner_user_id=owner_user_id, kb_id=kb.kb_id, doc_id=doc.doc_id)
            self._insert_public_policy_chunks(
                owner_user_id=owner_user_id,
                kb_id=kb.kb_id,
                doc_id=doc.doc_id,
                chunks=chunk_public_policy_document(public_doc),
            )
            self.index_document(owner_user_id=owner_user_id, kb_id=kb.kb_id, doc_id=doc.doc_id, vector_backend=vector_backend)

    def _insert_public_policy_chunks(
        self,
        *,
        owner_user_id: str,
        kb_id: str,
        doc_id: str,
        chunks,
    ) -> None:
        self._execute("DELETE FROM rag_chunks WHERE doc_id = {p}", [doc_id])
        now = self.utcnow().isoformat()
        for index, chunk in enumerate(chunks):
            payload = _chunk_metadata(
                {
                    "title": chunk.title,
                    "source_type": "public_policy_web",
                    "library_scope": "shared",
                    "source": chunk.source,
                    "source_url": chunk.source_url,
                    "region": chunk.region,
                    "doc_type": chunk.doc_type,
                    "section_title": chunk.section_title,
                }
            )
            keywords = _extract_keywords(chunk.snippet)
            questions = _generate_questions(chunk.snippet)
            token_count = max(1, len(chunk.snippet) // 2)
            self._execute(
                """
                INSERT INTO rag_chunks (
                    rag_chunk_id, kb_id, doc_id, owner_user_id, knowledge_chunk_id, parent_chunk_id,
                    chunk_index, text, token_estimate, token_count, keywords_json, questions_json, milvus_id,
                    page_number, sheet_name, slide_number, section_title,
                    status, vector_status, dense_vector_json, sparse_vector_json, created_at, updated_at, metadata_json
                )
                VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})
                """,
                [
                    f"rag-chunk-{uuid4().hex[:12]}",
                    kb_id,
                    doc_id,
                    owner_user_id,
                    chunk.chunk_id,
                    None,
                    index,
                    chunk.snippet,
                    token_count,
                    token_count,
                    json.dumps(keywords, ensure_ascii=False),
                    json.dumps(questions, ensure_ascii=False),
                    None,
                    chunk.page_number,
                    chunk.sheet_name,
                    chunk.slide_number,
                    chunk.section_title,
                    "chunked",
                    "pending",
                    None,
                    None,
                    now,
                    now,
                    json.dumps(payload, ensure_ascii=False),
                ],
            )
        doc = self._row_to_document(self._select("SELECT * FROM rag_documents WHERE doc_id = {p}", [doc_id])[0])
        self._mark_document(
            doc=doc,
            parse_status="parsed",
            chunk_status="chunked",
            index_status="pending",
            chunk_count=len(chunks),
            indexed_chunk_count=0,
            error_message=None,
        )

    def record_test_qa(
        self,
        *,
        owner_user_id: str,
        kb_id: str,
        query: str,
        answer: str,
        trace: dict[str, Any],
        citations: list[dict[str, Any]],
    ) -> str:
        self.require_kb(owner_user_id=owner_user_id, kb_id=kb_id)
        run_id = f"rag-qa-{uuid4().hex[:12]}"
        self._execute(
            """
            INSERT INTO rag_test_qa_runs (run_id, kb_id, owner_user_id, query, answer, trace_json, citations_json, created_at)
            VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})
            """,
            [
                run_id,
                kb_id,
                owner_user_id,
                query,
                answer,
                json.dumps(trace, ensure_ascii=False),
                json.dumps(citations, ensure_ascii=False),
                self.utcnow().isoformat(),
            ],
        )
        return run_id

    def record_eval_run(
        self,
        *,
        owner_user_id: str,
        kb_id: str | None,
        metrics: dict[str, Any],
        cases: list[dict[str, Any]],
        passed: bool,
    ) -> RagEvalRun:
        if kb_id is not None:
            self.require_kb(owner_user_id=owner_user_id, kb_id=kb_id)
        now = self.utcnow().isoformat()
        run_id = f"rag-eval-{uuid4().hex[:12]}"
        self._execute(
            """
            INSERT INTO rag_eval_runs (run_id, kb_id, owner_user_id, metrics_json, passed, created_at)
            VALUES ({p}, {p}, {p}, {p}, {p}, {p})
            """,
            [run_id, kb_id, owner_user_id, json.dumps(metrics, ensure_ascii=False), passed, now],
        )
        for case in cases:
            self._execute(
                """
                INSERT INTO rag_eval_cases (
                    case_id, run_id, kb_id, question, expected_json, result_json, hit, reciprocal_rank, created_at
                )
                VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})
                """,
                [
                    str(case.get("case_id") or f"case-{uuid4().hex[:8]}"),
                    run_id,
                    kb_id,
                    str(case.get("question") or ""),
                    json.dumps(case.get("expected") or {}, ensure_ascii=False),
                    json.dumps(case.get("result") or {}, ensure_ascii=False),
                    bool(case.get("hit")),
                    float(case.get("reciprocal_rank") or 0.0),
                    now,
                ],
            )
        return RagEvalRun(run_id=run_id, kb_id=kb_id, owner_user_id=owner_user_id, metrics=metrics, cases=cases, passed=passed, created_at=datetime.fromisoformat(now))

    def list_eval_runs(self, *, owner_user_id: str) -> list[RagEvalRun]:
        rows = self._select(
            """
            SELECT * FROM rag_eval_runs
            WHERE owner_user_id = {p}
            ORDER BY created_at DESC
            LIMIT 50
            """,
            [owner_user_id],
        )
        return [self._row_to_eval_run(row, cases=[]) for row in rows]

    def get_eval_run(self, *, owner_user_id: str, run_id: str) -> RagEvalRun | None:
        rows = self._select("SELECT * FROM rag_eval_runs WHERE owner_user_id = {p} AND run_id = {p}", [owner_user_id, run_id])
        if not rows:
            return None
        case_rows = self._select("SELECT * FROM rag_eval_cases WHERE run_id = {p} ORDER BY case_seq ASC", [run_id])
        cases = [
            {
                "case_id": row["case_id"],
                "question": row["question"],
                "expected": _parse_json_object(row.get("expected_json")),
                "result": _parse_json_object(row.get("result_json")),
                "hit": bool(row.get("hit")),
                "reciprocal_rank": float(row.get("reciprocal_rank") or 0.0),
            }
            for row in case_rows
        ]
        return self._row_to_eval_run(rows[0], cases=cases)

    def stats(self, *, owner_user_id: str | None = None) -> dict[str, int]:
        owner_clause = ""
        params: list[object] = []
        if owner_user_id is not None:
            owner_clause = " WHERE owner_user_id = {p}"
            params.append(owner_user_id)
        kb_count = self._count(f"SELECT COUNT(*) AS count FROM rag_knowledge_bases{owner_clause}", params)
        document_count = self._count(f"SELECT COUNT(*) AS count FROM rag_documents{owner_clause}", params)
        chunk_count = self._count(f"SELECT COUNT(*) AS count FROM rag_chunks{owner_clause}", params)
        indexed_count = self._count(
            f"SELECT COUNT(*) AS count FROM rag_chunks{owner_clause}{' AND' if owner_clause else ' WHERE'} vector_status LIKE 'indexed:%'",
            params,
        )
        return {
            "kb_count": kb_count,
            "document_count": document_count,
            "chunk_count": chunk_count,
            "indexed_chunk_count": indexed_count,
        }

    def require_kb(self, *, owner_user_id: str, kb_id: str) -> KnowledgeBase:
        kb = self.get_kb(owner_user_id=owner_user_id, kb_id=kb_id)
        if kb is None:
            raise KeyError(kb_id)
        return kb

    def _require_document(self, *, owner_user_id: str, kb_id: str, doc_id: str) -> RagDocument:
        doc = self.get_document(owner_user_id=owner_user_id, kb_id=kb_id, doc_id=doc_id)
        if doc is None:
            raise KeyError(doc_id)
        return doc

    @staticmethod
    def _is_system_kb(kb: KnowledgeBase) -> bool:
        return bool(kb.metadata.get("system_managed")) or kb.name in {"自动爬虫知识库", "官方政策自动更新库"}

    def _ensure_kb_writable(self, *, kb: KnowledgeBase, owner_user_id: str) -> None:
        if kb.owner_user_id != owner_user_id:
            raise PermissionError("knowledge base is read-only for this user")
        if self._is_system_kb(kb) and kb.owner_user_id != owner_user_id:
            raise PermissionError("system-managed knowledge base is read-only")

    def _ensure_document_writable(self, *, doc: RagDocument, owner_user_id: str) -> None:
        kb = self.require_kb(owner_user_id=owner_user_id, kb_id=doc.kb_id)
        self._ensure_kb_writable(kb=kb, owner_user_id=owner_user_id)
        if doc.owner_user_id and doc.owner_user_id != owner_user_id:
            raise PermissionError("document is read-only for this user")

    def _enrich_kb_summary(self, kb: KnowledgeBase) -> KnowledgeBase:
        rows = self._select(
            """
            SELECT
                COUNT(*) AS document_count,
                COALESCE(SUM(chunk_count), 0) AS chunk_count,
                COALESCE(SUM(indexed_chunk_count), 0) AS indexed_chunk_count,
                MAX(updated_at) AS last_ingested_at,
                SUM(CASE WHEN status = 'failed' OR error_stage IS NOT NULL THEN 1 ELSE 0 END) AS failed_count,
                SUM(CASE WHEN index_status != 'indexed' THEN 1 ELSE 0 END) AS pending_count
            FROM rag_documents
            WHERE kb_id = {p}
            """,
            [kb.kb_id],
        )
        summary = rows[0] if rows else {}
        document_count = int(summary.get("document_count") or 0)
        chunk_count = int(summary.get("chunk_count") or 0)
        indexed_chunk_count = int(summary.get("indexed_chunk_count") or 0)
        failed_count = int(summary.get("failed_count") or 0)
        pending_count = int(summary.get("pending_count") or 0)
        if failed_count:
            health_status = "failed"
        elif document_count == 0:
            health_status = "empty"
        elif pending_count:
            health_status = "needs_index"
        elif indexed_chunk_count > 0:
            health_status = "healthy"
        else:
            health_status = "unknown"
        system_managed = self._is_system_kb(kb)
        managed_by = kb.metadata.get("managed_by") or ("policy_crawler" if system_managed else None)
        kb_scope = kb.metadata.get("kb_scope") or ("system" if system_managed else ("shared" if kb.visibility in {"shared", "public"} else "personal"))
        last_ingested_at = summary.get("last_ingested_at")
        return kb.model_copy(
            update={
                "system_managed": system_managed,
                "managed_by": managed_by,
                "kb_scope": kb_scope,
                "document_count": document_count,
                "chunk_count": chunk_count,
                "indexed_chunk_count": indexed_chunk_count,
                "last_ingested_at": last_ingested_at,
                "health_status": health_status,
            }
        )

    def _mark_document(
        self,
        *,
        doc: RagDocument,
        parse_status: str,
        chunk_status: str,
        index_status: str,
        chunk_count: int | None = None,
        indexed_chunk_count: int | None = None,
        error_message: str | None = None,
        parse_progress: int | None = None,
        chunk_progress: int | None = None,
        error_stage: str | None = None,
    ) -> RagDocument:
        now = self.utcnow().isoformat()
        status = resolve_document_status(parse_status=parse_status, chunk_status=chunk_status, index_status=index_status)
        self._execute(
            """
            UPDATE rag_documents
            SET status = {p}, parse_status = {p}, chunk_status = {p}, index_status = {p},
                chunk_count = {p}, indexed_chunk_count = {p}, error_message = {p},
                parse_progress = {p}, chunk_progress = {p}, error_stage = {p}, updated_at = {p}
            WHERE doc_id = {p}
            """,
            [
                status,
                parse_status,
                chunk_status,
                index_status,
                doc.chunk_count if chunk_count is None else chunk_count,
                doc.indexed_chunk_count if indexed_chunk_count is None else indexed_chunk_count,
                error_message,
                doc.parse_progress if parse_progress is None else parse_progress,
                doc.chunk_progress if chunk_progress is None else chunk_progress,
                error_stage,
                now,
                doc.doc_id,
            ],
        )
        return self.get_document(owner_user_id=doc.owner_user_id or "", kb_id=doc.kb_id, doc_id=doc.doc_id) or doc

    def _count(self, query: str, params: list[object]) -> int:
        rows = self._select(query, params)
        return int(rows[0]["count"]) if rows else 0

    def _select(self, query: str, params: list[object]) -> list[dict[str, Any]]:
        sql = self._format_query(query)
        with self._connect() as connection:
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(sql, params)
                    return [dict(row) for row in cursor.fetchall()]
            rows = connection.execute(sql, params).fetchall()
            return [dict(row) for row in rows]

    def _execute(self, query: str, params: list[object]) -> None:
        sql = self._format_query(query)
        with self._connect() as connection:
            if self.backend_kind == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(sql, params)
                connection.commit()
                return
            connection.execute(sql, params)
            connection.commit()

    def _ensure_user_reference(self, *, owner_user_id: str) -> None:
        if not owner_user_id:
            raise ValueError("owner_user_id is required for RAG knowledge base persistence")
        rows = self._select("SELECT user_id FROM users WHERE user_id = {p}", [owner_user_id])
        if rows:
            return
        now = self.utcnow().isoformat()
        self._execute(
            """
            INSERT INTO users (user_id, username, password_hash, role, is_active, password_must_change, created_at, updated_at)
            VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})
            """,
            [
                owner_user_id,
                owner_user_id,
                "rag-kb-shadow-user",
                "user",
                True,
                False,
                now,
                now,
            ],
        )

    def _update_document_metadata(self, *, doc_id: str, metadata: dict[str, Any]) -> None:
        self._execute(
            "UPDATE rag_documents SET metadata_json = {p} WHERE doc_id = {p}",
            [json.dumps(metadata, ensure_ascii=False), doc_id],
        )

    def _format_query(self, query: str) -> str:
        return query.replace("{p}", self._placeholder())

    def _placeholder(self) -> str:
        return "%s" if self.backend_kind == "postgresql" else "?"

    @staticmethod
    def _row_to_kb(row: dict[str, Any]) -> KnowledgeBase:
        payload = dict(row)
        payload["metadata"] = _parse_json_object(payload.pop("metadata_json", None))
        payload["is_default"] = bool(payload.get("is_default"))
        return KnowledgeBase.model_validate(payload)

    @staticmethod
    def _row_to_document(row: dict[str, Any]) -> RagDocument:
        payload = dict(row)
        metadata = _parse_json_object(payload.pop("metadata_json", None))
        payload["metadata"] = metadata
        last_index = metadata.get("last_index_result") if isinstance(metadata, dict) else None
        if isinstance(last_index, dict):
            payload["vector_backend"] = last_index.get("vector_backend")
            payload["degraded"] = bool(last_index.get("degraded"))
            warnings = last_index.get("warnings")
            payload["index_warnings"] = warnings if isinstance(warnings, list) else []
        return RagDocument.model_validate(payload)

    @staticmethod
    def _row_to_chunk(row: dict[str, Any]) -> RagChunk:
        payload = dict(row)
        payload["metadata"] = _parse_json_object(payload.pop("metadata_json", None))
        payload["dense_vector"] = _parse_json_list(payload.pop("dense_vector_json", None))
        payload["sparse_vector"] = _parse_json_object(payload.pop("sparse_vector_json", None)) or None
        payload["keywords"] = _parse_json_str_list(payload.pop("keywords_json", None))
        payload["questions"] = _parse_json_str_list(payload.pop("questions_json", None))
        if not payload.get("token_count"):
            payload["token_count"] = payload.get("token_estimate") or 0
        return RagChunk.model_validate(payload)

    @staticmethod
    def _row_to_eval_run(row: dict[str, Any], *, cases: list[dict[str, Any]]) -> RagEvalRun:
        payload = dict(row)
        payload["metrics"] = _parse_json_object(payload.pop("metrics_json", None))
        payload["passed"] = bool(payload.get("passed"))
        payload["cases"] = cases
        return RagEvalRun.model_validate(payload)


def _chunk_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    payload = dict(metadata)
    for key in ("page_number", "slide_number"):
        if payload.get(key) in ("", None):
            payload[key] = None
        elif payload.get(key) is not None:
            try:
                payload[key] = int(payload[key])
            except (TypeError, ValueError):
                payload[key] = None
    for key in ("sheet_name", "section_title"):
        payload[key] = _optional_str(payload.get(key))
    return payload


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_json_object(value: Any) -> dict[str, Any]:
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _parse_json_list(value: Any) -> list[float] | None:
    if not value:
        return None
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, list) else None


def _parse_json_str_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def _mime_from_doc(doc: RagDocument) -> str:
    file_type = (doc.file_type or Path(doc.file_path or "").suffix.lower().lstrip(".")).lower()
    return {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "csv": "text/csv",
        "md": "text/markdown",
        "html": "text/html",
        "txt": "text/plain",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
    }.get(file_type, "application/octet-stream")


def _extract_keywords(text: str, top_k: int = 5) -> list[str]:
    words = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z]{3,}", text[:5000])
    freq: dict[str, int] = {}
    for word in words:
        token = word.lower()
        freq[token] = freq.get(token, 0) + 1
    return [word for word, _ in sorted(freq.items(), key=lambda item: item[1], reverse=True)[:top_k]]


def _generate_questions(text: str, count: int = 3) -> list[str]:
    sentences = [part.strip() for part in re.split(r"[。！？!?\.]+", text[:2000]) if len(part.strip()) > 10]
    questions: list[str] = []
    for sentence in sentences[:count]:
        preview = sentence[:30]
        if "如何" in sentence or "怎么" in sentence:
            questions.append(f"{preview} 的具体做法是什么？")
        elif "是" in sentence or "为" in sentence:
            questions.append(f"{preview} 具体指的是什么？")
        else:
            questions.append(f"这段内容中提到的“{preview}”是什么意思？")
    while len(questions) < count:
        questions.append("这段内容的核心观点是什么？")
    return questions[:count]

