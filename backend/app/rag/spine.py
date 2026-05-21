from __future__ import annotations

import json
from time import perf_counter
from functools import lru_cache
from pathlib import Path

from app.ai_runtime.providers.base import BaseChatProvider
from app.ai_runtime.providers.factory import get_chat_provider
from app.core.config import get_settings
from app.rag.kb.models import (
    KnowledgeBase,
    KnowledgeBaseCreate,
    KnowledgeBaseOverview,
    KnowledgeBaseUpdate,
    RagAnswerResult,
    RagDocument,
    RagDocumentCreate,
    RagEvalCase,
    RagEvalRun,
    RagHealth,
    RagHit,
    RagPipelineBatchResult,
    RagPipelineMode,
    RagPipelineResult,
    RagSearchRequest,
    RagSearchResult,
    RagStats,
    RagTimingTrace,
    RagTrace,
)
from app.rag.kb.storage import RagKnowledgeStore
from app.rag.qa.test_qa import build_test_qa_answer
from app.rag.retrieval.dense import dense_search
from app.rag.retrieval.hybrid_rrf import merge_with_rrf
from app.rag.retrieval.rerank import BgeReranker
from app.rag.retrieval.sparse import sparse_search_with_trace
from app.rag.vector_backend.base import VectorSearchResult
from app.rag.vector_backend.runtime import resolve_vector_runtime


class RagSpineService:
    """RAG-Pro style primary RAG spine for CarbonRag V1.6.x."""

    def __init__(
        self,
        *,
        store: RagKnowledgeStore | None = None,
        chat_provider: BaseChatProvider | None = None,
        provider_ref: str | None = None,
    ) -> None:
        self.store = store or RagKnowledgeStore()
        self.chat_provider = chat_provider or get_chat_provider()
        self.provider_ref = provider_ref
        self.reranker = BgeReranker()

    def list_kbs(self, *, owner_user_id: str) -> list[KnowledgeBase]:
        return self.store.list_kbs(owner_user_id=owner_user_id)

    def create_kb(self, *, owner_user_id: str, payload: KnowledgeBaseCreate) -> KnowledgeBase:
        return self.store.create_kb(owner_user_id=owner_user_id, payload=payload)

    def get_kb(self, *, owner_user_id: str, kb_id: str) -> KnowledgeBase:
        return self.store.require_kb(owner_user_id=owner_user_id, kb_id=kb_id)

    def update_kb(self, *, owner_user_id: str, kb_id: str, payload: KnowledgeBaseUpdate) -> KnowledgeBase:
        return self.store.update_kb(owner_user_id=owner_user_id, kb_id=kb_id, payload=payload)

    def delete_kb(self, *, owner_user_id: str, kb_id: str) -> None:
        self.store.delete_kb(owner_user_id=owner_user_id, kb_id=kb_id)

    def create_document(self, *, owner_user_id: str, kb_id: str, payload: RagDocumentCreate) -> RagDocument:
        return self.store.create_document(owner_user_id=owner_user_id, kb_id=kb_id, payload=payload.model_dump())

    def list_documents(self, *, owner_user_id: str, kb_id: str) -> list[RagDocument]:
        return self.store.list_documents(owner_user_id=owner_user_id, kb_id=kb_id)

    def get_kb_overview(self, *, owner_user_id: str, kb_id: str) -> KnowledgeBaseOverview:
        return self.store.get_kb_overview(owner_user_id=owner_user_id, kb_id=kb_id)

    def get_document(self, *, owner_user_id: str, kb_id: str, doc_id: str) -> RagDocument:
        doc = self.store.get_document(owner_user_id=owner_user_id, kb_id=kb_id, doc_id=doc_id)
        if doc is None:
            raise KeyError(doc_id)
        return doc

    def parse_document(self, *, owner_user_id: str, kb_id: str, doc_id: str) -> RagDocument:
        return self.store.parse_document(owner_user_id=owner_user_id, kb_id=kb_id, doc_id=doc_id)

    def chunk_document(self, *, owner_user_id: str, kb_id: str, doc_id: str) -> RagDocument:
        return self.store.chunk_document(owner_user_id=owner_user_id, kb_id=kb_id, doc_id=doc_id)

    def index_document(self, *, owner_user_id: str, kb_id: str, doc_id: str) -> RagDocument:
        return self.store.index_document(
            owner_user_id=owner_user_id,
            kb_id=kb_id,
            doc_id=doc_id,
            vector_backend=self._effective_vector_backend(),
        )

    def delete_document(self, *, owner_user_id: str, kb_id: str, doc_id: str) -> None:
        return self.store.delete_document(
            owner_user_id=owner_user_id,
            kb_id=kb_id,
            doc_id=doc_id,
            vector_backend=self._effective_vector_backend(),
        )

    def rebuild_document_index(self, *, owner_user_id: str, kb_id: str, doc_id: str) -> RagDocument:
        doc = self.get_document(owner_user_id=owner_user_id, kb_id=kb_id, doc_id=doc_id)
        if doc.chunk_status != "chunked" or doc.chunk_count <= 0:
            doc = self.chunk_document(owner_user_id=owner_user_id, kb_id=kb_id, doc_id=doc_id)
        return self.index_document(owner_user_id=owner_user_id, kb_id=kb_id, doc_id=doc_id)

    def list_chunks(self, *, owner_user_id: str, kb_id: str, doc_id: str | None = None):
        return self.store.list_chunks(owner_user_id=owner_user_id, kb_id=kb_id, doc_id=doc_id)

    def run_document_pipeline(self, *, owner_user_id: str, kb_id: str, doc_id: str, pipeline_mode: RagPipelineMode = "quick") -> RagPipelineResult:
        """Run the RAG-Pro acceptance path for one document.

        This intentionally stays synchronous for V1.6.24 so the workbench can
        explain the exact stage that failed before we introduce background jobs.
        """

        started_total = perf_counter()
        timings: dict[str, float] = {}
        warnings: list[str] = []
        vector_backend = self._effective_vector_backend()
        runtime = self._runtime_profile(backend=vector_backend)
        doc = self.get_document(owner_user_id=owner_user_id, kb_id=kb_id, doc_id=doc_id)

        if doc.parse_status != "parsed":
            started = perf_counter()
            doc = self.parse_document(owner_user_id=owner_user_id, kb_id=kb_id, doc_id=doc_id)
            timings["parse_ms"] = _elapsed_ms(started)
        if doc.parse_status != "parsed":
            return self._pipeline_result(
                doc=doc,
                pipeline_mode=pipeline_mode,
                vector_runtime=runtime.vector_runtime,
                failed_stage="parse",
                warnings=warnings,
                timing_trace=_pipeline_timing(timings, started_total, doc=doc),
            )

        if doc.chunk_status != "chunked" or doc.chunk_count <= 0:
            started = perf_counter()
            doc = self.chunk_document(owner_user_id=owner_user_id, kb_id=kb_id, doc_id=doc_id)
            timings["chunk_ms"] = _elapsed_ms(started)
        if doc.chunk_status != "chunked" or doc.chunk_count <= 0:
            return self._pipeline_result(
                doc=doc,
                pipeline_mode=pipeline_mode,
                vector_runtime=runtime.vector_runtime,
                failed_stage="chunk",
                warnings=warnings,
                timing_trace=_pipeline_timing(timings, started_total, doc=doc),
            )

        if doc.index_status != "indexed" or doc.indexed_chunk_count < doc.chunk_count:
            started = perf_counter()
            doc = self.index_document(owner_user_id=owner_user_id, kb_id=kb_id, doc_id=doc_id)
            timings["milvus_insert_ms"] = _elapsed_ms(started)
        if doc.index_status != "indexed" or doc.indexed_chunk_count <= 0:
            return self._pipeline_result(
                doc=doc,
                pipeline_mode=pipeline_mode,
                vector_runtime=runtime.vector_runtime,
                failed_stage="index",
                warnings=warnings,
                timing_trace=_pipeline_timing(timings, started_total, doc=doc),
            )

        chunks = self.list_chunks(owner_user_id=owner_user_id, kb_id=kb_id, doc_id=doc_id)
        smoke_query = _build_pipeline_smoke_query(doc=doc, chunks=chunks)
        search_smoke_passed = False
        degraded = bool(doc.degraded)
        try:
            started = perf_counter()
            search = self.search(
                owner_user_id=owner_user_id,
                request=RagSearchRequest(query=smoke_query, kb_id=kb_id, mode="hybrid", top_k=5),
            )
            timings["total_ms"] = _elapsed_ms(started)
            timings["embedding_ms"] = search.trace.timing_trace.embedding_ms or 0.0
            timings["milvus_client_ms"] = search.trace.timing_trace.milvus_client_ms or 0.0
            timings["milvus_search_ms"] = search.trace.timing_trace.milvus_search_ms or 0.0
            timings["sparse_ms"] = search.trace.timing_trace.sparse_ms or 0.0
            timings["rrf_ms"] = search.trace.timing_trace.rrf_ms or 0.0
            warnings.extend(search.trace.warnings)
            degraded = degraded or search.trace.degraded
            search_smoke_passed = any(hit.doc_id == doc_id for hit in search.hits)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"search_smoke_failed:{type(exc).__name__}: {exc}")

        eval_passed: bool | None = None
        eval_failed = False
        if pipeline_mode == "acceptance":
            cases = _load_pipeline_default_eval_cases(kb_id=kb_id)
            if cases:
                try:
                    started = perf_counter()
                    eval_run = self.run_eval(owner_user_id=owner_user_id, kb_id=kb_id, cases=cases, mode="hybrid", top_k=5)
                    timings["llm_ms"] = _elapsed_ms(started)
                    eval_passed = eval_run.passed
                    eval_failed = not eval_run.passed
                except Exception as exc:  # noqa: BLE001
                    eval_passed = False
                    eval_failed = True
                    warnings.append(f"eval_smoke_failed:{type(exc).__name__}: {exc}")
            else:
                warnings.append("eval_not_configured")

        failed_stage = None
        if not search_smoke_passed:
            failed_stage = "search_smoke"
        elif eval_failed:
            failed_stage = "eval_smoke"
        return self._pipeline_result(
            doc=doc,
            pipeline_mode=pipeline_mode,
            vector_runtime=runtime.vector_runtime,
            search_smoke_passed=search_smoke_passed,
            eval_passed=eval_passed,
            failed_stage=failed_stage,
            degraded=degraded,
            warnings=warnings,
            timing_trace=_pipeline_timing(timings, started_total, doc=doc),
        )

    def run_document_pipeline_batch(
        self,
        *,
        owner_user_id: str,
        kb_id: str,
        doc_ids: list[str] | None = None,
        pipeline_mode: RagPipelineMode = "quick",
    ) -> RagPipelineBatchResult:
        documents = self.list_documents(owner_user_id=owner_user_id, kb_id=kb_id)
        requested = set(doc_ids or [])
        targets = [
            doc
            for doc in documents
            if (not requested and (doc.index_status != "indexed" or doc.status == "failed" or doc.error_stage))
            or (requested and doc.doc_id in requested)
        ]
        results = [
            self.run_document_pipeline(owner_user_id=owner_user_id, kb_id=kb_id, doc_id=doc.doc_id, pipeline_mode=pipeline_mode)
            for doc in targets
        ]
        succeeded_count = sum(1 for item in results if item.failed_stage is None)
        failed_count = len(results) - succeeded_count
        return RagPipelineBatchResult(
            kb_id=kb_id,
            total_count=len(results),
            succeeded_count=succeeded_count,
            failed_count=failed_count,
            results=results,
        )

    def search(self, *, owner_user_id: str, request: RagSearchRequest) -> RagSearchResult:
        started_total = perf_counter()
        kb_id = request.kb_id
        vector_backend = self._effective_vector_backend()
        if kb_id is None:
            kb = self.store.sync_visible_knowledge(
                owner_user_id=owner_user_id,
                knowledge_scope=request.knowledge_scope,
                allowed_knowledge_item_ids=request.allowed_knowledge_item_ids,
                vector_backend=vector_backend,
            )
            kb_id = kb.kb_id
        db_started = perf_counter()
        chunks = self.store.list_searchable_chunks(
            owner_user_id=owner_user_id,
            kb_id=kb_id,
            knowledge_scope=request.knowledge_scope,
            allowed_knowledge_item_ids=request.allowed_knowledge_item_ids,
        )
        db_load_chunks_ms = _elapsed_ms(db_started)
        dense_result = (
            VectorSearchResult(hits=[], backend=vector_backend, available=True)
            if request.mode == "sparse"
            else dense_search(query=request.query, chunks=chunks, top_k=max(request.top_k * 4, request.top_k), backend=vector_backend)
        )
        sparse_result = None if request.mode == "dense" else sparse_search_with_trace(query=request.query, chunks=chunks, top_k=max(request.top_k * 4, request.top_k))
        sparse_hits = [] if sparse_result is None else sparse_result.hits
        rrf_started = perf_counter()
        merged = merge_with_rrf(sparse_hits=sparse_hits, dense_hits=dense_result.hits)
        rrf_ms = _elapsed_ms(rrf_started)

        rerank_applied = False
        warning = None
        hits: list[RagHit]
        rerank_started = perf_counter()
        if request.mode == "hybrid_rerank":
            hits, rerank_applied, warning = self.reranker.rerank(query=request.query, hits=merged, top_k=request.top_k)
        else:
            hits = merged[: request.top_k]
        rerank_ms = _elapsed_ms(rerank_started) if request.mode == "hybrid_rerank" else 0.0

        warnings: list[str] = []
        runtime = self._runtime_profile(backend=vector_backend)
        warnings.extend(runtime.warnings)
        degraded = bool(runtime.degraded)
        if dense_result.warning:
            warnings.append(f"向量后端不可用：{dense_result.warning}")
            degraded = True
        if warning:
            warnings.append(f"重排序未应用：{warning}")
            if request.mode == "hybrid_rerank":
                degraded = True

        trace = RagTrace(
            dense_count=len(dense_result.hits),
            sparse_count=len(sparse_hits),
            merged_count=len(merged),
            rerank_applied=rerank_applied,
            vector_backend=runtime.vector_backend,
            vector_runtime=runtime.vector_runtime,
            degraded=degraded,
            warnings=warnings,
            retrieval_mode=request.mode,
            kb_id=kb_id,
            knowledge_scope=request.knowledge_scope,
            timing_trace=RagTimingTrace(
                embedding_ms=dense_result.embedding_ms,
                milvus_client_ms=dense_result.client_ms,
                milvus_search_ms=dense_result.search_ms,
                db_load_chunks_ms=db_load_chunks_ms,
                sparse_ms=sparse_result.elapsed_ms if sparse_result else 0.0,
                rrf_ms=rrf_ms,
                rerank_ms=rerank_ms,
                total_ms=_elapsed_ms(started_total),
                loaded_chunk_count=len(chunks),
                dense_candidate_count=len(dense_result.hits),
                sparse_candidate_count=len(sparse_hits),
                rrf_candidate_count=len(merged),
                rerank_candidate_count=len(hits),
                milvus_client_init_count=dense_result.client_init_count,
                sparse_cache_hit=sparse_result.cache_hit if sparse_result else None,
                sparse_loaded_chunk_count=sparse_result.loaded_chunk_count if sparse_result else 0,
            ),
        )
        return RagSearchResult(query=request.query, kb_id=kb_id, hits=hits, trace=trace)

    def answer(self, *, owner_user_id: str, request: RagSearchRequest) -> RagAnswerResult:
        result = self.search(owner_user_id=owner_user_id, request=request)
        answer = build_test_qa_answer(
            query=request.query,
            search_result=result,
            chat_provider=self.chat_provider,
            provider_ref=self.provider_ref,
        )
        return RagAnswerResult(
            answer=answer["answer"],
            answer_mode=answer["answer_mode"],
            provider_name=answer["provider_name"],
            model_name=answer["model_name"],
            selected_chunks=answer["selected_chunks"],
            evidence_quality=answer["evidence_quality"],
            confidence=answer["confidence"],
            citations=answer["citations"],
            hits=answer["hits"],
            retrieval_trace=answer["retrieval_trace"],
        )

    def test_qa(self, *, owner_user_id: str, request: RagSearchRequest) -> dict:
        search_result = self.search(owner_user_id=owner_user_id, request=request)
        result = build_test_qa_answer(
            query=request.query,
            search_result=search_result,
            chat_provider=self.chat_provider,
            provider_ref=self.provider_ref,
        )
        kb_id = request.kb_id or result["retrieval_trace"].kb_id
        run_id = None
        if kb_id:
            run_id = self.store.record_test_qa(
                owner_user_id=owner_user_id,
                kb_id=kb_id,
                query=request.query,
                answer=result["answer"],
                trace=result["retrieval_trace"].model_dump(),
                citations=result["citations"],
            )
        payload = dict(result)
        payload["retrieval_trace"] = payload["retrieval_trace"].model_dump()
        payload["hits"] = [hit.model_dump() for hit in payload["hits"]]
        return {"run_id": run_id, **payload}

    def run_eval(
        self,
        *,
        owner_user_id: str,
        kb_id: str | None,
        cases: list[RagEvalCase],
        mode: str = "hybrid_rerank",
        top_k: int = 5,
    ) -> RagEvalRun:
        evaluated_cases: list[dict] = []
        hit_at_1 = 0
        hit_at_3 = 0
        recall_at_5_total = 0.0
        precision_at_5_total = 0.0
        mrr_total = 0.0
        citation_covered = 0
        no_hit_count = 0
        vector_failure_count = 0
        cross_kb_leak_count = 0
        answer_mode_counts: dict[str, int] = {}

        for case in cases:
            result = self.answer(
                owner_user_id=owner_user_id,
                request=RagSearchRequest(query=case.question, kb_id=kb_id or case.expected_kb_id, mode=mode, top_k=top_k),  # type: ignore[arg-type]
            )
            hits = result.hits
            keywords = case.expected_chunk_keywords or case.expected_answer_keywords
            matched_rank = _first_matching_rank(hits=hits, keywords=keywords)
            hit = matched_rank is not None
            hit_at_1 += int(matched_rank == 1)
            hit_at_3 += int(matched_rank is not None and matched_rank <= 3)
            recall_at_5_total += 1.0 if hit else 0.0
            precision_at_5_total += _precision_at_k(hits=hits, keywords=keywords, k=5)
            mrr_total += (1.0 / matched_rank) if matched_rank else 0.0
            citation_covered += int(bool(result.citations))
            no_hit_count += int(not hits)
            vector_failure_count += int(result.retrieval_trace.degraded or result.retrieval_trace.dense_count == 0)
            cross_kb_leak_count += sum(1 for item in hits if kb_id and item.kb_id != kb_id)
            answer_mode_counts[result.answer_mode] = answer_mode_counts.get(result.answer_mode, 0) + 1
            evaluated_cases.append(
                {
                    "case_id": case.case_id,
                    "question": case.question,
                    "expected": case.model_dump(),
                    "result": {
                        "answer_mode": result.answer_mode,
                        "answer": result.answer,
                        "matched_rank": matched_rank,
                        "citation_count": len(result.citations),
                        "trace": result.retrieval_trace.model_dump(),
                        "hits": [hit.model_dump() for hit in hits],
                    },
                    "hit": hit,
                    "reciprocal_rank": (1.0 / matched_rank) if matched_rank else 0.0,
                }
            )

        total = max(1, len(cases))
        metrics = {
            "case_count": len(cases),
            "hit_at_1": hit_at_1 / total,
            "hit_at_3": hit_at_3 / total,
            "recall_at_5": recall_at_5_total / total,
            "precision_at_5": precision_at_5_total / total,
            "mrr": mrr_total / total,
            "citation_coverage": citation_covered / total,
            "answer_mode_rate": {key: value / total for key, value in answer_mode_counts.items()},
            "no_hit_count": no_hit_count,
            "vector_failure_count": vector_failure_count,
            "cross_kb_leak_count": cross_kb_leak_count,
        }
        passed = bool(
            metrics["hit_at_3"] >= 0.85
            and metrics["mrr"] >= 0.75
            and metrics["citation_coverage"] == 1.0
            and cross_kb_leak_count == 0
            and vector_failure_count == 0
        )
        return self.store.record_eval_run(
            owner_user_id=owner_user_id,
            kb_id=kb_id,
            metrics=metrics,
            cases=evaluated_cases,
            passed=passed,
        )

    def list_eval_runs(self, *, owner_user_id: str) -> list[RagEvalRun]:
        return self.store.list_eval_runs(owner_user_id=owner_user_id)

    def get_eval_run(self, *, owner_user_id: str, run_id: str) -> RagEvalRun:
        run = self.store.get_eval_run(owner_user_id=owner_user_id, run_id=run_id)
        if run is None:
            raise KeyError(run_id)
        return run

    def health(self, *, owner_user_id: str | None = None) -> RagHealth:
        stats = self.store.stats(owner_user_id=owner_user_id)
        backend = self._effective_vector_backend()
        runtime = self._runtime_profile(backend=backend)
        warnings = list(runtime.warnings)
        degraded = bool(runtime.degraded)
        if runtime.vector_runtime == "memory_dev":
            warnings.append("当前使用 memory lexical fallback；比赛验收应使用 Docker Milvus Standalone + BGE-M3。")
        elif runtime.vector_runtime == "chroma_dev":
            warnings.append("Chroma 仅保留兼容；V1.6.8 Windows 默认验收路径为 Docker Milvus Standalone。")
        return RagHealth(
            vector_backend=backend,
            vector_runtime=runtime.vector_runtime,
            milvus_uri=runtime.milvus_uri,
            require_real_vector=runtime.require_real_vector,
            degraded=degraded,
            document_count=stats["document_count"],
            chunk_count=stats["chunk_count"],
            warnings=warnings,
        )

    def stats(self, *, owner_user_id: str | None = None) -> RagStats:
        raw = self.store.stats(owner_user_id=owner_user_id)
        backend = self._effective_vector_backend()
        runtime = self._runtime_profile(backend=backend)
        return RagStats(
            **raw,
            vector_backend=backend,
            vector_runtime=runtime.vector_runtime,
            milvus_uri=runtime.milvus_uri,
            require_real_vector=runtime.require_real_vector,
        )

    @staticmethod
    def _effective_vector_backend() -> str:
        return RagSpineService._runtime_profile().vector_backend

    @staticmethod
    def _runtime_profile(*, backend: str | None = None):
        settings = get_settings()
        selected_backend = backend if backend is not None else getattr(settings, "rag_vector_backend", "memory")
        selected_uri = getattr(settings, "rag_milvus_uri", None)
        return resolve_vector_runtime(backend=selected_backend, milvus_uri=selected_uri)

    @staticmethod
    def _pipeline_result(
        *,
        doc: RagDocument,
        vector_runtime: str,
        search_smoke_passed: bool = False,
        eval_passed: bool | None = None,
        failed_stage: str | None = None,
        degraded: bool | None = None,
        warnings: list[str] | None = None,
        pipeline_mode: RagPipelineMode = "quick",
        timing_trace: RagTimingTrace | None = None,
    ) -> RagPipelineResult:
        return RagPipelineResult(
            doc_id=doc.doc_id,
            pipeline_mode=pipeline_mode,
            parse_status=doc.parse_status,
            chunk_status=doc.chunk_status,
            index_status=doc.index_status,
            chunk_count=doc.chunk_count,
            indexed_chunk_count=doc.indexed_chunk_count,
            vector_runtime=vector_runtime,
            degraded=bool(doc.degraded if degraded is None else degraded),
            search_smoke_passed=search_smoke_passed,
            eval_passed=eval_passed,
            failed_stage=failed_stage,
            error_message=doc.error_message,
            warnings=warnings or list(doc.index_warnings),
            timing_trace=timing_trace or RagTimingTrace(),
        )


@lru_cache(maxsize=1)
def get_rag_spine_service() -> RagSpineService:
    return RagSpineService()


def _first_matching_rank(*, hits: list[RagHit], keywords: list[str]) -> int | None:
    if not hits:
        return None
    if not keywords:
        return 1
    normalized_keywords = [item.lower() for item in keywords if item.strip()]
    for index, hit in enumerate(hits, start=1):
        haystack = f"{hit.title}\n{hit.snippet}".lower()
        if any(keyword in haystack for keyword in normalized_keywords):
            return index
    return None


def _precision_at_k(*, hits: list[RagHit], keywords: list[str], k: int) -> float:
    if not hits:
        return 0.0
    if not keywords:
        return min(len(hits), k) / max(1, k)
    normalized_keywords = [item.lower() for item in keywords if item.strip()]
    candidates = hits[:k]
    matched = 0
    for hit in candidates:
        haystack = f"{hit.title}\n{hit.snippet}".lower()
        matched += int(any(keyword in haystack for keyword in normalized_keywords))
    return matched / max(1, k)


def _pipeline_timing(timings: dict[str, float], started_total: float, *, doc: RagDocument) -> RagTimingTrace:
    return RagTimingTrace(
        parse_ms=timings.get("parse_ms"),
        chunk_ms=timings.get("chunk_ms"),
        embedding_ms=timings.get("embedding_ms"),
        milvus_client_ms=timings.get("milvus_client_ms"),
        milvus_insert_ms=timings.get("milvus_insert_ms"),
        milvus_search_ms=timings.get("milvus_search_ms"),
        sparse_ms=timings.get("sparse_ms"),
        rrf_ms=timings.get("rrf_ms"),
        llm_ms=timings.get("llm_ms"),
        total_ms=_elapsed_ms(started_total),
        loaded_chunk_count=doc.chunk_count,
        dense_candidate_count=doc.indexed_chunk_count,
    )


def _elapsed_ms(started: float) -> float:
    return round((perf_counter() - started) * 1000, 3)


def _build_pipeline_smoke_query(*, doc: RagDocument, chunks: list) -> str:
    for chunk in chunks:
        text = getattr(chunk, "text", "").strip()
        if text:
            return text[:80]
    return doc.title


def _load_pipeline_default_eval_cases(*, kb_id: str | None) -> list[RagEvalCase]:
    path = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "rag" / "gold_questions.json"
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    records = raw.get("cases", raw) if isinstance(raw, dict) else raw
    if not isinstance(records, list):
        return []
    cases: list[RagEvalCase] = []
    for record in records:
        if isinstance(record, dict):
            payload = dict(record)
            if kb_id and not payload.get("expected_kb_id"):
                payload["expected_kb_id"] = kb_id
            cases.append(RagEvalCase.model_validate(payload))
    return cases

