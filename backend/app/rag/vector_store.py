from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from app.rag.contracts import ChunkRecord, EmbeddingRecord
from app.runtime_db.compat import connect_postgres
from app.retrieval.mixed_retriever import MixedScopeRetriever, get_mixed_scope_retriever
from app.retrieval.private_retriever import PrivateSampleRetriever, get_private_sample_retriever
from app.retrieval.public_retriever import PublicPolicyRetriever, get_public_policy_retriever
from app.retrieval.schemas import RetrievedChunk

VectorStoreHealthStatus = Literal["ok", "degraded", "disabled", "error"]
VectorStoreFilters = dict[str, Any]


class VectorStoreHealth(BaseModel):
    backend: str
    status: VectorStoreHealthStatus
    available: bool
    reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class VectorStoreUpsertResult(BaseModel):
    backend: str
    upserted_count: int = 0
    skipped_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class VectorStoreSearchResult(BaseModel):
    chunks: list[RetrievedChunk] = Field(default_factory=list)
    total_hits: int = 0
    backend: str | None = None
    adapter_name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class VectorStoreAdapter(Protocol):
    def healthcheck(self) -> VectorStoreHealth:
        ...

    def upsert_chunks(
        self,
        *,
        chunks: list[ChunkRecord],
        embeddings: list[EmbeddingRecord] | None = None,
    ) -> VectorStoreUpsertResult:
        ...

    def search(
        self,
        *,
        question: str | None = None,
        query: str | None = None,
        filters: VectorStoreFilters | None = None,
        query_embedding: list[float] | None = None,
        top_k: int = 5,
        allowed_knowledge_item_ids: set[str] | None = None,
    ) -> VectorStoreSearchResult:
        ...

    def delete_by_document(self, *, document_id: str) -> VectorStoreUpsertResult:
        ...


class DisabledVectorStoreAdapter:
    backend = "disabled"

    def __init__(self, *, reason: str = "vector_store_disabled") -> None:
        self.reason = reason

    def healthcheck(self) -> VectorStoreHealth:
        return VectorStoreHealth(
            backend=self.backend,
            status="disabled",
            available=False,
            reason=self.reason,
        )

    def upsert_chunks(
        self,
        *,
        chunks: list[ChunkRecord],
        embeddings: list[EmbeddingRecord] | None = None,
    ) -> VectorStoreUpsertResult:
        return VectorStoreUpsertResult(
            backend=self.backend,
            upserted_count=0,
            skipped_count=len(chunks),
            metadata={"reason": self.reason, "embedding_count": len(embeddings or [])},
        )

    def search(
        self,
        *,
        question: str | None = None,
        query: str | None = None,
        filters: VectorStoreFilters | None = None,
        query_embedding: list[float] | None = None,
        top_k: int = 5,
        allowed_knowledge_item_ids: set[str] | None = None,
    ) -> VectorStoreSearchResult:
        resolved_query = _resolve_query(question=question, query=query)
        return VectorStoreSearchResult(
            chunks=[],
            total_hits=0,
            backend=self.backend,
            adapter_name=type(self).__name__,
            metadata={
                "status": "disabled",
                "reason": self.reason,
                "query_length": len(resolved_query),
                "embedding_seen": query_embedding is not None,
                "top_k": top_k,
                "filters": filters or {},
                "allowed_knowledge_item_count": len(allowed_knowledge_item_ids or set()),
            },
        )

    def delete_by_document(self, *, document_id: str) -> VectorStoreUpsertResult:
        return VectorStoreUpsertResult(
            backend=self.backend,
            upserted_count=0,
            skipped_count=0,
            metadata={"reason": self.reason, "document_id": document_id},
        )


class CurrentVectorStoreAdapter:
    backend = "current"

    def __init__(
        self,
        *,
        public_retriever: PublicPolicyRetriever | None = None,
        private_retriever: PrivateSampleRetriever | None = None,
        mixed_retriever: MixedScopeRetriever | None = None,
    ) -> None:
        self.public_retriever = public_retriever or get_public_policy_retriever()
        self.private_retriever = private_retriever or get_private_sample_retriever()
        self.mixed_retriever = mixed_retriever or get_mixed_scope_retriever()

    def healthcheck(self) -> VectorStoreHealth:
        try:
            public_chunk_count = _count_retriever_chunks(self.public_retriever)
            private_chunk_count = _count_retriever_chunks(self.private_retriever)
            return VectorStoreHealth(
                backend=self.backend,
                status="ok",
                available=True,
                metadata={
                    "adapter_name": type(self).__name__,
                    "storage": "in_memory_bm25",
                    "public_chunk_count": public_chunk_count,
                    "private_chunk_count": private_chunk_count,
                },
            )
        except Exception as exc:  # noqa: BLE001
            return VectorStoreHealth(
                backend=self.backend,
                status="degraded",
                available=False,
                reason=str(exc),
                metadata={"adapter_name": type(self).__name__, "error_type": type(exc).__name__},
            )

    def upsert_chunks(
        self,
        *,
        chunks: list[ChunkRecord],
        embeddings: list[EmbeddingRecord] | None = None,
    ) -> VectorStoreUpsertResult:
        return VectorStoreUpsertResult(
            backend=self.backend,
            upserted_count=0,
            skipped_count=len(chunks),
            metadata={
                "adapter_name": type(self).__name__,
                "reason": "current_adapter_is_read_through",
                "embedding_count": len(embeddings or []),
            },
        )

    def search(
        self,
        *,
        question: str | None = None,
        query: str | None = None,
        filters: VectorStoreFilters | None = None,
        query_embedding: list[float] | None = None,
        top_k: int = 5,
        allowed_knowledge_item_ids: set[str] | None = None,
    ) -> VectorStoreSearchResult:
        resolved_query = _resolve_query(question=question, query=query)
        resolved_filters = filters or {}
        knowledge_scope = str(resolved_filters.get("knowledge_scope") or "mixed")
        allowed_ids = _resolve_allowed_ids(
            allowed_knowledge_item_ids=allowed_knowledge_item_ids,
            filters=resolved_filters,
        )

        if knowledge_scope == "public":
            result = self.public_retriever.search(
                question=resolved_query,
                top_k=top_k,
                knowledge_scope="public",
                region=_optional_str(resolved_filters.get("region")),
                doc_type=_optional_str(resolved_filters.get("doc_type")),
            )
        elif knowledge_scope == "private_sample":
            result = self.private_retriever.search(
                question=resolved_query,
                top_k=top_k,
                knowledge_scope="private_sample",
                allowed_knowledge_item_ids=allowed_ids,
                business_topic=_optional_str(resolved_filters.get("business_topic")),
            )
        else:
            result = self.mixed_retriever.search(
                question=resolved_query,
                top_k=top_k,
                allowed_knowledge_item_ids=allowed_ids,
            )

        return VectorStoreSearchResult(
            chunks=result.hits,
            total_hits=result.total_hits,
            backend=self.backend,
            adapter_name=type(self).__name__,
            metadata={
                "status": "ok",
                "adapter_name": type(self).__name__,
                "storage": "in_memory_bm25",
                "knowledge_scope": knowledge_scope,
                "top_k": top_k,
                "query_embedding_seen": query_embedding is not None,
                "allowed_knowledge_item_count": len(allowed_ids or set()),
            },
        )

    def delete_by_document(self, *, document_id: str) -> VectorStoreUpsertResult:
        return VectorStoreUpsertResult(
            backend=self.backend,
            upserted_count=0,
            skipped_count=0,
            metadata={
                "adapter_name": type(self).__name__,
                "reason": "current_adapter_is_read_through",
                "document_id": document_id,
            },
        )


class PgVectorStoreAdapter:
    backend = "pgvector"

    def __init__(
        self,
        *,
        database_url: str | None = None,
        connection_factory: Callable[[str], Any] | None = None,
        table_name: str = "rag_embeddings",
    ) -> None:
        self.database_url = database_url
        self.connection_factory = connection_factory or connect_postgres
        self.table_name = _safe_table_name(table_name)

    def healthcheck(self) -> VectorStoreHealth:
        if not self.database_url:
            return VectorStoreHealth(
                backend=self.backend,
                status="degraded",
                available=False,
                reason="pgvector_database_url_missing",
                metadata={"adapter_name": type(self).__name__, "table": self.table_name},
            )
        try:
            self._healthcheck()
            return VectorStoreHealth(
                backend=self.backend,
                status="ok",
                available=True,
                metadata={"adapter_name": type(self).__name__, "table": self.table_name},
            )
        except Exception as exc:  # noqa: BLE001
            return VectorStoreHealth(
                backend=self.backend,
                status="degraded",
                available=False,
                reason=str(exc),
                metadata={"adapter_name": type(self).__name__, "table": self.table_name, "error_type": type(exc).__name__},
            )

    def upsert_chunks(
        self,
        *,
        chunks: list[ChunkRecord],
        embeddings: list[EmbeddingRecord] | None = None,
    ) -> VectorStoreUpsertResult:
        embeddings_by_chunk_id = {embedding.chunk_id: embedding for embedding in embeddings or []}
        rows = [
            self._build_upsert_row(chunk=chunk, embedding=embeddings_by_chunk_id.get(chunk.chunk_id))
            for chunk in chunks
            if embeddings_by_chunk_id.get(chunk.chunk_id) is not None
            and embeddings_by_chunk_id[chunk.chunk_id].vector
        ]
        if not rows:
            return VectorStoreUpsertResult(
                backend=self.backend,
                upserted_count=0,
                skipped_count=len(chunks),
                metadata={
                    "adapter_name": type(self).__name__,
                    "reason": "no_embeddings_supplied",
                    "embedding_count": len(embeddings or []),
                },
            )
        try:
            self._upsert_rows(rows)
            return VectorStoreUpsertResult(
                backend=self.backend,
                upserted_count=len(rows),
                skipped_count=len(chunks) - len(rows),
                metadata={"adapter_name": type(self).__name__, "table": self.table_name},
            )
        except Exception as exc:  # noqa: BLE001
            return VectorStoreUpsertResult(
                backend=self.backend,
                upserted_count=0,
                skipped_count=len(chunks),
                metadata={
                    "adapter_name": type(self).__name__,
                    "reason": "pgvector_upsert_failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
            )

    def search(
        self,
        *,
        question: str | None = None,
        query: str | None = None,
        filters: VectorStoreFilters | None = None,
        query_embedding: list[float] | None = None,
        top_k: int = 5,
        allowed_knowledge_item_ids: set[str] | None = None,
    ) -> VectorStoreSearchResult:
        resolved_query = _resolve_query(question=question, query=query)
        resolved_filters = filters or {}
        if allowed_knowledge_item_ids is not None:
            resolved_filters = {**resolved_filters, "allowed_knowledge_item_ids": sorted(allowed_knowledge_item_ids)}
        if not query_embedding:
            return VectorStoreSearchResult(
                chunks=[],
                total_hits=0,
                backend=self.backend,
                adapter_name=type(self).__name__,
                metadata={
                    "status": "degraded",
                    "reason": "query_embedding_required",
                    "query_length": len(resolved_query),
                    "top_k": top_k,
                    "filters": resolved_filters,
                },
            )
        try:
            rows = self._search_rows(
                query_embedding=query_embedding,
                top_k=top_k,
                filters=resolved_filters,
            )
            chunks = [_retrieved_chunk_from_pgvector_row(row) for row in rows]
            return VectorStoreSearchResult(
                chunks=chunks,
                total_hits=len(chunks),
                backend=self.backend,
                adapter_name=type(self).__name__,
                metadata={
                    "status": "ok",
                    "adapter_name": type(self).__name__,
                    "query_length": len(resolved_query),
                    "query_embedding_seen": True,
                    "top_k": top_k,
                    "filters": resolved_filters,
                    "vector_hit_count": len(chunks),
                },
            )
        except Exception as exc:  # noqa: BLE001
            return VectorStoreSearchResult(
                chunks=[],
                total_hits=0,
                backend=self.backend,
                adapter_name=type(self).__name__,
                metadata={
                    "status": "error",
                    "reason": "pgvector_search_failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "query_length": len(resolved_query),
                    "top_k": top_k,
                    "filters": resolved_filters,
                },
            )

    def delete_by_document(self, *, document_id: str) -> VectorStoreUpsertResult:
        try:
            deleted_count = self._delete_rows_by_document(document_id=document_id)
            return VectorStoreUpsertResult(
                backend=self.backend,
                upserted_count=0,
                skipped_count=0,
                metadata={"adapter_name": type(self).__name__, "document_id": document_id, "deleted_count": deleted_count},
            )
        except Exception as exc:  # noqa: BLE001
            return VectorStoreUpsertResult(
                backend=self.backend,
                upserted_count=0,
                skipped_count=0,
                metadata={
                    "adapter_name": type(self).__name__,
                    "document_id": document_id,
                    "reason": "pgvector_delete_failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
            )

    def _connect(self) -> Any:
        if not self.database_url:
            raise RuntimeError("pgvector database_url is not configured.")
        return self.connection_factory(self.database_url)

    def _healthcheck(self) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(f"SELECT 1 FROM {self.table_name} LIMIT 1")

    def _upsert_rows(self, rows: list[dict[str, Any]]) -> None:
        query = f"""
            INSERT INTO {self.table_name} (
                embedding_id,
                chunk_id,
                document_id,
                source_type,
                title,
                source,
                source_url,
                visibility,
                text,
                metadata,
                embedding,
                model_name,
                created_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::vector, %s, %s
            )
            ON CONFLICT (chunk_id) DO UPDATE SET
                embedding_id = EXCLUDED.embedding_id,
                document_id = EXCLUDED.document_id,
                source_type = EXCLUDED.source_type,
                title = EXCLUDED.title,
                source = EXCLUDED.source,
                source_url = EXCLUDED.source_url,
                visibility = EXCLUDED.visibility,
                text = EXCLUDED.text,
                metadata = EXCLUDED.metadata,
                embedding = EXCLUDED.embedding,
                model_name = EXCLUDED.model_name,
                created_at = EXCLUDED.created_at
        """
        with self._connect() as connection:
            with connection.cursor() as cursor:
                for row in rows:
                    cursor.execute(
                        query,
                        (
                            row["embedding_id"],
                            row["chunk_id"],
                            row["document_id"],
                            row["source_type"],
                            row["title"],
                            row["source"],
                            row["source_url"],
                            row["visibility"],
                            row["text"],
                            json.dumps(row["metadata"], ensure_ascii=False),
                            row["embedding"],
                            row["model_name"],
                            row["created_at"],
                        ),
                    )

    def _search_rows(
        self,
        *,
        query_embedding: list[float],
        top_k: int,
        filters: VectorStoreFilters,
    ) -> list[dict[str, Any]]:
        where_sql, filter_params = _build_pgvector_filter_clause(filters)
        vector_literal = _vector_literal(query_embedding)
        query = f"""
            SELECT
                embedding_id,
                chunk_id,
                document_id,
                source_type,
                title,
                source,
                source_url,
                visibility,
                text,
                metadata,
                model_name,
                created_at,
                1 - (embedding <=> %s::vector) AS score
            FROM {self.table_name}
            {where_sql}
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (vector_literal, *filter_params, vector_literal, top_k))
                rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def _delete_rows_by_document(self, *, document_id: str) -> int:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(f"DELETE FROM {self.table_name} WHERE document_id = %s", (document_id,))
                return int(getattr(cursor, "rowcount", 0) or 0)

    @staticmethod
    def _build_upsert_row(*, chunk: ChunkRecord, embedding: EmbeddingRecord | None) -> dict[str, Any]:
        if embedding is None or not embedding.vector:
            raise ValueError("Embedding vector is required for pgvector upsert.")
        metadata = {
            **chunk.metadata,
            "knowledge_item_id": chunk.knowledge_item_id,
            "page": chunk.page,
            "section": chunk.section,
            "block_ids": chunk.block_ids,
            "content_hash": chunk.content_hash,
        }
        return {
            "embedding_id": embedding.embedding_id,
            "chunk_id": chunk.chunk_id,
            "document_id": chunk.document_id,
            "source_type": chunk.source_type,
            "title": chunk.title,
            "source": chunk.source,
            "source_url": chunk.source_uri or chunk.source_url,
            "visibility": _optional_str(chunk.visibility or chunk.metadata.get("visibility") or chunk.metadata.get("library_scope")),
            "text": chunk.text,
            "metadata": metadata,
            "embedding": _vector_literal(embedding.vector),
            "model_name": embedding.model_name,
            "created_at": embedding.created_at,
        }


class FakeVectorStoreAdapter:
    backend = "fake"

    def __init__(
        self,
        *,
        chunks: list[RetrievedChunk] | None = None,
        status: VectorStoreHealthStatus = "ok",
        available: bool = True,
    ) -> None:
        self.chunks = chunks or []
        self.status = status
        self.available = available

    def healthcheck(self) -> VectorStoreHealth:
        return VectorStoreHealth(
            backend=self.backend,
            status=self.status,
            available=self.available,
            reason=None if self.available else "fake_vector_store_unavailable",
            metadata={"adapter_name": type(self).__name__, "chunk_count": len(self.chunks)},
        )

    def upsert_chunks(
        self,
        *,
        chunks: list[ChunkRecord],
        embeddings: list[EmbeddingRecord] | None = None,
    ) -> VectorStoreUpsertResult:
        self.chunks.extend(_retrieved_chunk_from_chunk_record(chunk) for chunk in chunks)
        return VectorStoreUpsertResult(
            backend=self.backend,
            upserted_count=len(chunks),
            skipped_count=0,
            metadata={"adapter_name": type(self).__name__, "embedding_count": len(embeddings or [])},
        )

    def search(
        self,
        *,
        question: str | None = None,
        query: str | None = None,
        filters: VectorStoreFilters | None = None,
        query_embedding: list[float] | None = None,
        top_k: int = 5,
        allowed_knowledge_item_ids: set[str] | None = None,
    ) -> VectorStoreSearchResult:
        resolved_query = _resolve_query(question=question, query=query)
        allowed_ids = _resolve_allowed_ids(
            allowed_knowledge_item_ids=allowed_knowledge_item_ids,
            filters=filters or {},
        )
        knowledge_scope = str((filters or {}).get("knowledge_scope") or "mixed")
        candidates = self.chunks
        if knowledge_scope == "public":
            candidates = [chunk for chunk in candidates if chunk.source_type == "public_policy"]
        elif allowed_ids is not None and knowledge_scope == "mixed":
            candidates = [
                chunk
                for chunk in candidates
                if chunk.source_type == "public_policy" or chunk.knowledge_item_id in allowed_ids
            ]
        elif allowed_ids is not None:
            candidates = [chunk for chunk in candidates if chunk.knowledge_item_id in allowed_ids]
        selected = candidates[:top_k]
        return VectorStoreSearchResult(
            chunks=selected,
            total_hits=len(selected),
            backend=self.backend,
            adapter_name=type(self).__name__,
            metadata={
                "status": self.status,
                "adapter_name": type(self).__name__,
                "query": resolved_query,
                "query_embedding_seen": query_embedding is not None,
                "top_k": top_k,
                "allowed_knowledge_item_count": len(allowed_ids or set()),
            },
        )

    def delete_by_document(self, *, document_id: str) -> VectorStoreUpsertResult:
        before_count = len(self.chunks)
        self.chunks = [chunk for chunk in self.chunks if chunk.doc_id != document_id]
        deleted_count = before_count - len(self.chunks)
        return VectorStoreUpsertResult(
            backend=self.backend,
            upserted_count=0,
            skipped_count=0,
            metadata={"adapter_name": type(self).__name__, "deleted_count": deleted_count},
        )


def build_vector_store_adapter(
    *,
    settings: Any,
    current_adapter: CurrentVectorStoreAdapter | None = None,
) -> VectorStoreAdapter:
    backend = str(getattr(settings, "rag_vector_backend", "current") or "current").strip().lower()
    if backend == "pgvector":
        return PgVectorStoreAdapter(database_url=getattr(settings, "database_url", None))
    return current_adapter or CurrentVectorStoreAdapter()


def _resolve_query(*, question: str | None, query: str | None) -> str:
    resolved = (question if question is not None else query) or ""
    return resolved.strip()


def _resolve_allowed_ids(
    *,
    allowed_knowledge_item_ids: set[str] | None,
    filters: VectorStoreFilters,
) -> set[str] | None:
    if allowed_knowledge_item_ids is not None:
        return allowed_knowledge_item_ids
    raw_value = filters.get("allowed_knowledge_item_ids")
    if raw_value is None:
        return None
    if isinstance(raw_value, str):
        return {raw_value}
    if isinstance(raw_value, (list, set, tuple)):
        return {str(item) for item in raw_value if str(item).strip()}
    return None


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _count_retriever_chunks(retriever: object) -> int | None:
    chunks = getattr(retriever, "chunks", None)
    if chunks is None:
        return None
    return len(chunks)


def _retrieved_chunk_from_chunk_record(chunk: ChunkRecord) -> RetrievedChunk:
    library_scope = chunk.metadata.get("library_scope")
    return RetrievedChunk(
        doc_id=chunk.document_id,
        knowledge_item_id=chunk.knowledge_item_id,
        title=chunk.title,
        source_type=chunk.source_type,
        source=chunk.source or chunk.source_uri or "fake-vector-store",
        source_url=chunk.source_uri or chunk.source_url,
        region=_optional_str(chunk.metadata.get("region")),
        doc_type=_optional_str(chunk.metadata.get("doc_type")),
        sample_type=_optional_str(chunk.metadata.get("sample_type")),
        business_topic=_optional_str(chunk.metadata.get("business_topic")),
        library_scope=library_scope if library_scope in {"personal", "shared"} else None,  # type: ignore[arg-type]
        chunk_id=chunk.chunk_id,
        snippet=chunk.text,
        score=float(chunk.metadata.get("score") or 1.0),
    )


def _retrieved_chunk_from_pgvector_row(row: dict[str, Any]) -> RetrievedChunk:
    metadata = _metadata_from_row(row.get("metadata"))
    source_type = _normalize_source_type(row.get("source_type") or metadata.get("source_type"))
    library_scope = metadata.get("library_scope")
    return RetrievedChunk(
        doc_id=str(row.get("document_id") or metadata.get("document_id") or ""),
        knowledge_item_id=_optional_str(metadata.get("knowledge_item_id")),
        title=str(row.get("title") or metadata.get("title") or row.get("chunk_id") or "pgvector chunk"),
        source_type=source_type,  # type: ignore[arg-type]
        source=str(row.get("source") or metadata.get("source") or "pgvector"),
        source_url=_optional_str(row.get("source_url") or metadata.get("source_url")),
        issued_at=_optional_str(metadata.get("issued_at")),
        region=_optional_str(metadata.get("region")),
        doc_type=_optional_str(metadata.get("doc_type")),
        sample_type=_optional_str(metadata.get("sample_type")),
        business_topic=_optional_str(metadata.get("business_topic")),
        library_scope=library_scope if library_scope in {"personal", "shared"} else None,  # type: ignore[arg-type]
        chunk_id=str(row.get("chunk_id") or ""),
        snippet=str(row.get("text") or ""),
        score=float(row.get("score") or metadata.get("score") or 0.0),
    )


def _metadata_from_row(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _normalize_source_type(value: Any) -> str:
    normalized = str(value or "").strip()
    if normalized in {"public_policy", "public_policy_demo", "private_sample", "private_upload"}:
        return normalized
    return "private_sample"


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(str(float(item)) for item in vector) + "]"


def _build_pgvector_filter_clause(filters: VectorStoreFilters) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    knowledge_scope = _optional_str(filters.get("knowledge_scope"))
    allowed_ids = _resolve_allowed_ids(allowed_knowledge_item_ids=None, filters=filters)
    source_type_filter = filters.get("source_type")
    scope_handles_source_type = False

    if knowledge_scope == "public":
        clauses.append("source_type = %s")
        params.append("public_policy")
        scope_handles_source_type = True
    elif knowledge_scope == "private_sample":
        scope_handles_source_type = True
        if not allowed_ids:
            return "WHERE 1 = 0", []
        private_source_types = ("private_sample", "private_upload")
        placeholders = ", ".join(["%s"] * len(private_source_types))
        clauses.append(f"source_type IN ({placeholders})")
        params.extend(private_source_types)
        allowed_placeholders = ", ".join(["%s"] * len(allowed_ids))
        clauses.append(f"metadata->>'knowledge_item_id' IN ({allowed_placeholders})")
        params.extend(sorted(allowed_ids))
    elif knowledge_scope == "mixed":
        scope_handles_source_type = True
        if not allowed_ids:
            clauses.append("source_type = %s")
            params.append("public_policy")
        else:
            allowed_placeholders = ", ".join(["%s"] * len(allowed_ids))
            clauses.append(f"(source_type = %s OR metadata->>'knowledge_item_id' IN ({allowed_placeholders}))")
            params.append("public_policy")
            params.extend(sorted(allowed_ids))
    elif "allowed_knowledge_item_ids" in filters and not allowed_ids:
        if source_type_filter in {"private_sample", "private_upload"}:
            return "WHERE 1 = 0", []
        if source_type_filter is None:
            clauses.append("source_type = %s")
            params.append("public_policy")
            scope_handles_source_type = True

    for key in ("source_type", "document_id", "visibility"):
        if key == "source_type" and scope_handles_source_type:
            continue
        value = filters.get(key)
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            values = [str(item) for item in value if str(item).strip()]
            if not values:
                continue
            placeholders = ", ".join(["%s"] * len(values))
            clauses.append(f"{key} IN ({placeholders})")
            params.extend(values)
        else:
            clauses.append(f"{key} = %s")
            params.append(str(value))
    if allowed_ids and not scope_handles_source_type:
        placeholders = ", ".join(["%s"] * len(allowed_ids))
        clauses.append(f"metadata->>'knowledge_item_id' IN ({placeholders})")
        params.extend(sorted(allowed_ids))
    if not clauses:
        return "", []
    return "WHERE " + " AND ".join(clauses), params


def _safe_table_name(value: str) -> str:
    normalized = value.strip()
    if not normalized or not normalized.replace("_", "").isalnum():
        raise ValueError("Unsafe pgvector table name.")
    return normalized
