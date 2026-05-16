from __future__ import annotations

from pathlib import Path
from typing import Any

from app.knowledge.policy_live_crawler import PolicyCrawlerCandidate, get_policy_crawler_scheduler
from app.rag.kb.models import KnowledgeBase, KnowledgeBaseCreate, RagDocumentCreate, RagPipelineResult
from app.rag.spine import RagSpineService, get_rag_spine_service

AUTO_CRAWLER_RAG_KB_NAME = "自动爬虫知识库"
OFFICIAL_POLICY_RAG_KB_NAME = "官方政策自动更新库"
SYSTEM_POLICY_CRAWLER_USER_ID = "system-policy-crawler"


def publish_crawled_candidate_to_rag_kb(
    candidate_id: str,
    reviewed_by_user_id: str | None,
    *,
    rag_service: RagSpineService | None = None,
) -> RagPipelineResult:
    """Publish a reviewed policy crawler candidate into the RAG-Pro KB spine."""

    scheduler = get_policy_crawler_scheduler()
    candidate = scheduler.store.get_candidate(candidate_id)
    if candidate is None:
        raise KeyError(candidate_id)
    if candidate.status == "rejected":
        raise ValueError("rejected candidates cannot be published to RAG")
    quality_score = candidate.metadata.get("candidate_quality_score")
    if quality_score is not None and int(quality_score) < 60:
        raise ValueError(f"candidate quality score {quality_score} is below 60; review manually before RAG publish")
    _validate_candidate_artifacts(candidate)
    service = rag_service or get_rag_spine_service()
    owner_user_id = SYSTEM_POLICY_CRAWLER_USER_ID
    kb = _ensure_official_policy_kb(service=service, owner_user_id=owner_user_id)
    doc = service.create_document(
        owner_user_id=owner_user_id,
        kb_id=kb.kb_id,
        payload=_candidate_document_payload(candidate),
    )
    try:
        result = service.run_document_pipeline(
            owner_user_id=owner_user_id,
            kb_id=kb.kb_id,
            doc_id=doc.doc_id,
            pipeline_mode="quick",
        )
        failed_stage = _pipeline_failed_stage(result)
        if failed_stage:
            scheduler.store.update_candidate_review(
                candidate_id=candidate.candidate_id,
                status="pending_review",
                reviewed_by_user_id=reviewed_by_user_id,
                review_note=_review_note_for_result(result),
                knowledge_item_id=candidate.knowledge_item_id,
                metadata=_rag_metadata(
                    candidate=candidate,
                    kb=kb,
                    result=result,
                    failed_stage=failed_stage,
                    error_detail=result.error_message or failed_stage,
                ),
            )
            raise ValueError(f"candidate RAG publish failed at {failed_stage}")
        scheduler.store.update_candidate_review(
            candidate_id=candidate.candidate_id,
            status="published",
            reviewed_by_user_id=reviewed_by_user_id,
            review_note=_review_note_for_result(result),
            knowledge_item_id=candidate.knowledge_item_id,
            metadata=_rag_metadata(candidate=candidate, kb=kb, result=result, failed_stage=None, error_detail=None),
        )
        return result
    except Exception as exc:  # noqa: BLE001
        if isinstance(exc, ValueError) and str(exc).startswith("candidate RAG publish failed at "):
            raise
        scheduler.store.update_candidate_review(
            candidate_id=candidate.candidate_id,
            status="pending_review",
            reviewed_by_user_id=reviewed_by_user_id,
            review_note=f"Published to RAG KB, but quick pipeline failed: {exc}",
            knowledge_item_id=candidate.knowledge_item_id,
            metadata=_rag_metadata(
                candidate=candidate,
                kb=kb,
                result=None,
                doc_id=doc.doc_id,
                failed_stage="rag_quick_pipeline",
                error_detail=str(exc),
            ),
        )
        raise


def _ensure_official_policy_kb(*, service: RagSpineService, owner_user_id: str) -> KnowledgeBase:
    for kb in service.list_kbs(owner_user_id=owner_user_id):
        if kb.name in {AUTO_CRAWLER_RAG_KB_NAME, OFFICIAL_POLICY_RAG_KB_NAME}:
            return kb
    return service.create_kb(
        owner_user_id=owner_user_id,
        payload=KnowledgeBaseCreate(
            name=AUTO_CRAWLER_RAG_KB_NAME,
            description="由官方政策 crawler 审核发布后自动写入的共享 RAG-Pro 知识库，系统自动维护，管理员只读。",
            visibility="shared",
            retrieval_mode="hybrid_rerank",
        ),
    )


def _candidate_document_payload(candidate: PolicyCrawlerCandidate) -> RagDocumentCreate:
    metadata = candidate.metadata
    markdown_path = _existing_path(metadata.get("markdown_storage_path"))
    cleaned_path = _existing_path(metadata.get("cleaned_storage_path"))
    raw_path = _existing_path(metadata.get("raw_storage_path") or candidate.storage_path)
    file_path = markdown_path or cleaned_path or raw_path
    text = None if file_path else _candidate_text_from_storage(candidate)
    return RagDocumentCreate(
        title=candidate.title or candidate.url,
        text=text,
        source_type="public_policy",
        filename=_filename_for_candidate(candidate=candidate, path=file_path),
        file_type=(Path(file_path).suffix.lower().lstrip(".") if file_path else "md"),
        file_size=(Path(file_path).stat().st_size if file_path and Path(file_path).exists() else None),
        file_path=file_path,
        chunk_method="recursive",
    )


def _validate_candidate_artifacts(candidate: PolicyCrawlerCandidate) -> None:
    metadata = candidate.metadata
    markdown_path = _existing_path(metadata.get("markdown_storage_path"))
    cleaned_path = _existing_path(metadata.get("cleaned_storage_path"))
    if not markdown_path or not cleaned_path:
        raise ValueError("empty_extraction: markdown or cleaned artifact is missing")
    markdown_size = int(metadata.get("markdown_size") or Path(markdown_path).stat().st_size)
    cleaned_size = int(metadata.get("cleaned_size") or Path(cleaned_path).stat().st_size)
    estimated_chunk_count = int(metadata.get("estimated_chunk_count") or 0)
    extraction_quality_score = int(metadata.get("extraction_quality_score") or metadata.get("candidate_quality_score") or 0)
    if markdown_size < 800 or cleaned_size < 800:
        raise ValueError("empty_extraction: markdown and cleaned text must both be at least 800 bytes")
    if estimated_chunk_count <= 0:
        raise ValueError("zero_chunks: candidate has no estimated chunks")
    if extraction_quality_score < 60:
        raise ValueError(f"empty_extraction: extraction quality score {extraction_quality_score} is below 60")


def _pipeline_failed_stage(result: RagPipelineResult) -> str | None:
    if result.failed_stage:
        return result.failed_stage
    if result.chunk_count <= 0:
        return "zero_chunks"
    if result.indexed_chunk_count <= 0:
        return "index_failed"
    if result.search_smoke_passed is False:
        return "search_smoke_failed"
    return None


def _existing_path(value: object) -> str | None:
    if not value:
        return None
    path = Path(str(value))
    return str(path) if path.exists() else None


def _candidate_text_from_storage(candidate: PolicyCrawlerCandidate) -> str:
    path = Path(candidate.storage_path)
    if not path.exists():
        raise FileNotFoundError(candidate.storage_path)
    return path.read_text(encoding="utf-8", errors="ignore")


def _filename_for_candidate(*, candidate: PolicyCrawlerCandidate, path: str | None) -> str:
    if path:
        return Path(path).name
    safe_title = (candidate.title or candidate.candidate_id).strip() or candidate.candidate_id
    return f"{safe_title}.md"


def _review_note_for_result(result: RagPipelineResult) -> str:
    if result.failed_stage:
        return f"Published to RAG KB, quick pipeline failed at {result.failed_stage}: {result.error_message or 'unknown error'}"
    return (
        "Published to RAG KB and quick pipeline completed. "
        f"Indexed chunks: {result.indexed_chunk_count}/{result.chunk_count}."
    )


def _rag_metadata(
    *,
    candidate: PolicyCrawlerCandidate,
    kb: KnowledgeBase,
    result: RagPipelineResult | None,
    doc_id: str | None = None,
    failed_stage: str | None,
    error_detail: str | None,
) -> dict[str, Any]:
    resolved_doc_id = doc_id or (result.doc_id if result else None)
    metadata: dict[str, Any] = {
        "publish_target": "rag_pro_kb",
        "publish_mode": "manual_rag",
        "rag_kb_id": kb.kb_id,
        "rag_kb_name": AUTO_CRAWLER_RAG_KB_NAME,
        "rag_kb_storage_name": kb.name,
        "rag_doc_id": resolved_doc_id,
        "rag_pipeline_mode": "quick",
        "rag_pipeline_status": "failed" if failed_stage or (result and result.failed_stage) else "indexed",
        "rag_error_stage": failed_stage or (result.failed_stage if result else None),
        "rag_error_detail": error_detail or (result.error_message if result else None),
    }
    if result is not None:
        metadata.update(
            {
                "indexed_chunk_count": result.indexed_chunk_count,
                "rag_indexed_chunk_count": result.indexed_chunk_count,
                "rag_chunk_count": result.chunk_count,
                "rag_search_smoke_passed": result.search_smoke_passed,
                "rag_vector_runtime": result.vector_runtime,
                "rag_degraded": result.degraded,
                "rag_warnings": result.warnings,
            }
        )
    return {**candidate.metadata, **metadata}
