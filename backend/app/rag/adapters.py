from __future__ import annotations

from typing import Any

from app.rag.contracts import ChunkRecord, CitationRef, RetrievalTrace
from app.rag.schemas import RagEvidenceChunk, RagEvidenceReference, RagRetrievalMetadata, RagRetrievalResult
from app.retrieval.schemas import RetrievedChunk


def chunk_record_from_retrieved_chunk(chunk: RetrievedChunk) -> ChunkRecord:
    return ChunkRecord.from_retrieved_chunk(chunk)


def chunk_record_from_evidence_chunk(chunk: RagEvidenceChunk) -> ChunkRecord:
    return ChunkRecord(
        chunk_id=chunk.chunk_id,
        document_id=chunk.doc_id,
        text=chunk.snippet,
        source_type=chunk.source_type,
        title=chunk.title,
        page=None,
        section=chunk.region or chunk.doc_type,
        block_ids=[],
        knowledge_item_id=chunk.knowledge_item_id,
        source=chunk.source,
        source_uri=chunk.source_url,
        source_url=chunk.source_url,
        metadata={
            "reference_id": chunk.reference_id,
            "score": chunk.score,
            "issued_at": chunk.issued_at,
            "region": chunk.region,
            "doc_type": chunk.doc_type,
            "sample_type": chunk.sample_type,
            "business_topic": chunk.business_topic,
            "library_scope": chunk.library_scope,
            "retrieval_layer": chunk.retrieval_layer,
        },
    )


def citation_ref_from_reference(
    reference: RagEvidenceReference,
    *,
    chunk: RagEvidenceChunk | ChunkRecord | None = None,
) -> CitationRef:
    if isinstance(chunk, RagEvidenceChunk):
        return CitationRef.from_chunk_record(
            reference_id=reference.reference_id,
            chunk=chunk_record_from_evidence_chunk(chunk),
        )
    if isinstance(chunk, ChunkRecord):
        return CitationRef.from_chunk_record(reference_id=reference.reference_id, chunk=chunk)

    return CitationRef(
        citation_id=reference.reference_id,
        document_id=reference.doc_id,
        chunk_id=reference.chunk_id,
        title=reference.title,
        source_uri=reference.source_url,
        metadata={"source_type": reference.source_type, "source": reference.source},
        source_type=reference.source_type,
        source=reference.source,
    )


def citation_refs_from_references(
    references: list[RagEvidenceReference],
    *,
    chunks: list[RagEvidenceChunk],
) -> list[CitationRef]:
    chunks_by_id = {chunk.chunk_id: chunk for chunk in chunks}
    return [
        citation_ref_from_reference(reference, chunk=chunks_by_id.get(reference.chunk_id))
        for reference in references
    ]


def retrieval_trace_from_components(
    *,
    query: str,
    metadata: RagRetrievalMetadata,
    chunks: list[RagEvidenceChunk],
    references: list[RagEvidenceReference],
) -> RetrievalTrace:
    citation_refs = citation_refs_from_references(references, chunks=chunks)
    prior_trace = metadata.trace
    provider_metadata = metadata.provider_metadata or {}
    trace_metadata: dict[str, Any] = dict(prior_trace.metadata if prior_trace else {})
    trace_metadata.update(
        {
            "knowledge_scope": metadata.knowledge_scope,
            "mode": metadata.mode,
            "provider_metadata_keys": sorted(provider_metadata.keys()),
            "public_chunk_count": metadata.public_chunk_count,
            "public_policy_demo_chunk_count": metadata.public_policy_demo_chunk_count,
            "private_chunk_count": metadata.private_chunk_count,
        }
    )

    trace_payload: dict[str, Any] = {
        "query": query,
        "retriever_mode": metadata.retriever_mode or metadata.mode,
        "requested_top_k": metadata.requested_top_k or metadata.top_k,
        "returned_count": metadata.returned_count if metadata.returned_count is not None else len(chunks),
        "fallback_used": bool(metadata.fallback_used),
        "fallback_reason": metadata.fallback_reason,
        "chunk_ids": [chunk.chunk_id for chunk in chunks],
        "citations": citation_refs,
        "strategy": metadata.strategy,
        "retrieval_path": metadata.retrieval_path,
        "latency_ms": metadata.latency_ms if metadata.latency_ms is not None else prior_trace.latency_ms,
        "total_hits": len(chunks),
        "workflow_id": prior_trace.workflow_id if prior_trace else provider_metadata.get("workflow_id"),
        "parser_name": prior_trace.parser_name if prior_trace else provider_metadata.get("parser_name"),
        "vector_backend": prior_trace.vector_backend if prior_trace else metadata.vector_backend,
        "error_code": prior_trace.error_code if prior_trace else provider_metadata.get("error_code"),
        "metadata": trace_metadata,
    }
    if prior_trace:
        trace_payload["trace_id"] = prior_trace.trace_id
        trace_payload["created_at"] = prior_trace.created_at
    return RetrievalTrace(**trace_payload)


def retrieval_trace_from_result(result: RagRetrievalResult) -> RetrievalTrace:
    return retrieval_trace_from_components(
        query=result.query,
        metadata=result.metadata,
        chunks=result.chunks,
        references=result.references,
    )
