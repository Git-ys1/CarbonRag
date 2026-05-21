from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.rag.embeddings import RagEmbeddingUnavailable, embed_documents, embed_query
from app.rag.kb.models import RagChunk
from app.rag.vector_backend.base import BaseVectorStore, VectorIndexResult, VectorSearchHit, VectorSearchResult
from app.rag.vector_backend.runtime import resolve_vector_runtime


class MilvusVectorStoreAdapter(BaseVectorStore):
    """Milvus Lite/Milvus adapter migrated from the RAG-Pro vector-store spine."""

    backend_name = "milvus"
    dense_dim = 1024

    def delete_document(self, *, kb_id: str, doc_id: str) -> bool:
        runtime = resolve_vector_runtime()
        if not kb_id or not doc_id:
            return False
        if runtime.degraded:
            return False
        client, _, _ = _milvus_client()
        collection_name = _collection_name(kb_id)
        if not _has_collection(client, collection_name):
            return False
        client.delete(collection_name=collection_name, filter=f'doc_id == "{_escape_filter_value(doc_id)}"')
        try:
            client.flush(collection_name=collection_name)
        except Exception:
            pass
        return True

    def index_chunks(self, *, chunks: list[RagChunk], embeddings=None) -> VectorIndexResult:
        start_total = time.perf_counter()
        embedding_ms = 0.0
        runtime = resolve_vector_runtime()
        if not chunks:
            return VectorIndexResult(indexed_count=0, backend=runtime.vector_runtime, available=True, degraded=runtime.degraded, warning=_runtime_warning(runtime))
        try:
            client, client_init_count, client_ms = _milvus_client()
            if embeddings is None:
                embedding_started = time.perf_counter()
                embeddings = embed_documents([chunk.text for chunk in chunks])
                embedding_ms = _elapsed_ms(embedding_started)
            if not embeddings.dense:
                return VectorIndexResult(
                    indexed_count=0,
                    backend=runtime.vector_runtime,
                    available=False,
                    degraded=True,
                    warning="BGE-M3 returned no dense vectors.",
                    client_ms=client_ms,
                    embedding_ms=embedding_ms,
                    client_init_count=client_init_count,
                )
            chunk_index = {chunk.rag_chunk_id: index for index, chunk in enumerate(chunks)}
            indexed_count = 0
            insert_started = time.perf_counter()
            for kb_id, kb_chunks in _group_by_kb(chunks).items():
                collection_name = _collection_name(kb_id)
                _ensure_collection(client, collection_name, len(embeddings.dense[0]))
                rows: list[dict[str, Any]] = []
                for chunk in kb_chunks:
                    index = chunk_index[chunk.rag_chunk_id]
                    rows.append(
                        {
                            "id": chunk.rag_chunk_id,
                            "chunk_id": chunk.rag_chunk_id,
                            "doc_id": chunk.doc_id,
                            "kb_id": chunk.kb_id,
                            "owner_user_id": chunk.owner_user_id or "",
                            "source_type": str(chunk.metadata.get("source_type") or "private_upload")[:64],
                            "title": str(chunk.metadata.get("title") or chunk.metadata.get("source") or "RAG 文档")[:512],
                            "content": chunk.text[:8000],
                            "dense_vector": embeddings.dense[index],
                            "page_number": int(chunk.page_number or 0),
                            "sheet_name": str(chunk.sheet_name or "")[:256],
                            "slide_number": int(chunk.slide_number or 0),
                        }
                    )
                try:
                    client.delete(collection_name=collection_name, filter=f'doc_id == "{_escape_filter_value(kb_chunks[0].doc_id)}"')
                except Exception:
                    pass
                client.insert(collection_name=collection_name, data=rows)
                try:
                    client.flush(collection_name=collection_name)
                except Exception:
                    # Older/embedded Milvus clients may not expose flush. Search can
                    # still work eventually, but standalone should flush for E2E smoke.
                    pass
                indexed_count += len(rows)
            return VectorIndexResult(
                indexed_count=indexed_count,
                backend=runtime.vector_runtime,
                available=True,
                degraded=runtime.degraded,
                warning=_runtime_warning(runtime),
                client_ms=client_ms,
                insert_ms=_elapsed_ms(insert_started),
                embedding_ms=embedding_ms,
                client_init_count=client_init_count,
            )
        except RagEmbeddingUnavailable as exc:
            return VectorIndexResult(indexed_count=0, backend=runtime.vector_runtime, available=False, degraded=True, warning=str(exc), embedding_ms=embedding_ms)
        except Exception as exc:  # noqa: BLE001
            return VectorIndexResult(
                indexed_count=0,
                backend=runtime.vector_runtime,
                available=False,
                degraded=True,
                warning=f"Milvus runtime unavailable ({runtime.vector_runtime}): {exc}",
                insert_ms=_elapsed_ms(start_total),
                embedding_ms=embedding_ms,
            )

    def search(self, *, query: str, chunks: list[RagChunk], top_k: int) -> VectorSearchResult:
        embedding_ms = 0.0
        runtime = resolve_vector_runtime()
        if not chunks:
            return VectorSearchResult(hits=[], backend=runtime.vector_runtime, available=True, degraded=runtime.degraded, warning=_runtime_warning(runtime))
        try:
            client, client_init_count, client_ms = _milvus_client()
            embedding_started = time.perf_counter()
            dense_query, _ = embed_query(query)
            embedding_ms = _elapsed_ms(embedding_started)
            chunk_map = {chunk.rag_chunk_id: chunk for chunk in chunks}
            hits: list[VectorSearchHit] = []
            search_started = time.perf_counter()
            for kb_id in sorted({chunk.kb_id for chunk in chunks}):
                collection_name = _collection_name(kb_id)
                if not _has_collection(client, collection_name):
                    continue
                results = client.search(
                    collection_name=collection_name,
                    data=[dense_query],
                    anns_field="dense_vector",
                    limit=max(top_k, 1),
                    output_fields=["chunk_id"],
                )
                for row in results[0] if results else []:
                    entity = row.get("entity") or {}
                    chunk_id = str(entity.get("chunk_id") or row.get("id") or "")
                    chunk = chunk_map.get(chunk_id)
                    if chunk is None:
                        continue
                    score = float(row.get("distance") or row.get("score") or 0.0)
                    hits.append(VectorSearchHit(chunk=chunk, score=score))
            hits.sort(key=lambda item: item.score, reverse=True)
            return VectorSearchResult(
                hits=hits[:top_k],
                backend=runtime.vector_runtime,
                available=True,
                degraded=runtime.degraded,
                warning=_runtime_warning(runtime),
                client_ms=client_ms,
                search_ms=_elapsed_ms(search_started),
                embedding_ms=embedding_ms,
                client_init_count=client_init_count,
            )
        except RagEmbeddingUnavailable as exc:
            return VectorSearchResult(hits=[], backend=runtime.vector_runtime, available=False, degraded=True, warning=str(exc), embedding_ms=embedding_ms)
        except Exception as exc:  # noqa: BLE001
            return VectorSearchResult(
                hits=[],
                backend=runtime.vector_runtime,
                available=False,
                degraded=True,
                warning=f"Milvus runtime unavailable ({runtime.vector_runtime}): {exc}",
                embedding_ms=embedding_ms,
            )


_CLIENT_CACHE: dict[str, Any] = {}
_COLLECTION_EXISTS_CACHE: set[tuple[str, str]] = set()


def _milvus_client():
    try:
        from pymilvus import MilvusClient
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("pymilvus is not installed.") from exc
    settings = get_settings()
    uri = settings.rag_milvus_uri
    if uri and not uri.startswith(("http://", "https://", "tcp://")):
        Path(uri).parent.mkdir(parents=True, exist_ok=True)
    cache_key = str(uri or "")
    started = time.perf_counter()
    if cache_key in _CLIENT_CACHE:
        return _CLIENT_CACHE[cache_key], 0, _elapsed_ms(started)
    client = MilvusClient(uri=uri)
    _CLIENT_CACHE[cache_key] = client
    return client, 1, _elapsed_ms(started)


def _ensure_collection(client, collection_name: str, dim: int) -> None:
    client_key = _client_cache_key(client)
    if (client_key, collection_name) in _COLLECTION_EXISTS_CACHE:
        return
    if client.has_collection(collection_name):
        _COLLECTION_EXISTS_CACHE.add((client_key, collection_name))
        return
    try:
        from pymilvus import DataType

        schema = client.create_schema(auto_id=False, enable_dynamic_field=True)
        schema.add_field(field_name="id", datatype=DataType.VARCHAR, max_length=96, is_primary=True)
        schema.add_field(field_name="chunk_id", datatype=DataType.VARCHAR, max_length=96)
        schema.add_field(field_name="doc_id", datatype=DataType.VARCHAR, max_length=96)
        schema.add_field(field_name="kb_id", datatype=DataType.VARCHAR, max_length=96)
        schema.add_field(field_name="owner_user_id", datatype=DataType.VARCHAR, max_length=96)
        schema.add_field(field_name="source_type", datatype=DataType.VARCHAR, max_length=64)
        schema.add_field(field_name="title", datatype=DataType.VARCHAR, max_length=512)
        schema.add_field(field_name="content", datatype=DataType.VARCHAR, max_length=8192)
        schema.add_field(field_name="page_number", datatype=DataType.INT64)
        schema.add_field(field_name="sheet_name", datatype=DataType.VARCHAR, max_length=256)
        schema.add_field(field_name="slide_number", datatype=DataType.INT64)
        schema.add_field(field_name="dense_vector", datatype=DataType.FLOAT_VECTOR, dim=dim)
        index_params = client.prepare_index_params()
        index_params.add_index(field_name="dense_vector", index_type="FLAT", metric_type="COSINE")
        client.create_collection(collection_name=collection_name, schema=schema, index_params=index_params)
    except Exception:
        client.create_collection(collection_name=collection_name, dimension=dim, metric_type="COSINE", auto_id=False)
    _COLLECTION_EXISTS_CACHE.add((client_key, collection_name))


def _has_collection(client, collection_name: str) -> bool:
    client_key = _client_cache_key(client)
    if (client_key, collection_name) in _COLLECTION_EXISTS_CACHE:
        return True
    exists = bool(client.has_collection(collection_name))
    if exists:
        _COLLECTION_EXISTS_CACHE.add((client_key, collection_name))
    return exists


def _collection_name(kb_id: str) -> str:
    prefix = re.sub(r"[^A-Za-z0-9_]", "_", get_settings().rag_milvus_collection_prefix or "carbonrag")
    safe_kb = re.sub(r"[^A-Za-z0-9_]", "_", kb_id)
    candidate = f"{prefix}_{safe_kb}"
    if not candidate[0].isalpha() and candidate[0] != "_":
        candidate = f"c_{candidate}"
    return candidate[:255]


def _group_by_kb(chunks: list[RagChunk]) -> dict[str, list[RagChunk]]:
    grouped: dict[str, list[RagChunk]] = {}
    for chunk in chunks:
        grouped.setdefault(chunk.kb_id, []).append(chunk)
    return grouped


def _escape_filter_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _runtime_warning(runtime) -> str | None:
    return "; ".join(runtime.warnings) if runtime.warnings else None


def _client_cache_key(client) -> str:
    return str(id(client))


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 3)
