from functools import lru_cache
from time import perf_counter
from typing import Any

from app.ai_runtime.providers.base import BaseEmbeddingProvider, BaseRerankProvider, RerankItem
from app.ai_runtime.providers.factory import get_embedding_provider, get_rerank_provider
from app.core.config import Settings, get_settings
from app.rag.adapters import chunk_record_from_evidence_chunk, citation_refs_from_references
from app.rag.contracts import RetrievalTrace
from app.rag.graph import GraphIndexBuilder, RuleBasedGraphIndexBuilder
from app.rag.graph import select_graph_candidates
from app.rag.schemas import (
    RagEvidenceChunk,
    RagEvidenceReference,
    RagKnowledgeScope,
    RagQueryParams,
    RagRetrievalMetadata,
    RagRetrievalResult,
)
from app.rag.retriever_strategy import BM25Retriever, HybridRetriever, RetrieverStrategyResult, VectorRetriever
from app.rag.strategy import build_retrieval_path, plan_retrieval_strategy
from app.rag.vector import BaseVectorRetriever, DisabledVectorRetriever
from app.rag.vector_store import (
    CurrentVectorStoreAdapter,
    VectorStoreAdapter,
    VectorStoreHealth,
    build_vector_store_adapter,
)
from app.retrieval.mixed_retriever import MixedScopeRetriever, get_mixed_scope_retriever
from app.retrieval.private_retriever import PrivateSampleRetriever, get_private_sample_retriever
from app.retrieval.public_retriever import PublicPolicyRetriever, get_public_policy_retriever
from app.retrieval.schemas import RetrievedChunk, RetrievalResult


class RagEngineService:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        vector_retriever: BaseVectorRetriever | None = None,
        embedding_provider: BaseEmbeddingProvider | None = None,
        rerank_provider: BaseRerankProvider | None = None,
        public_retriever: PublicPolicyRetriever | None = None,
        private_retriever: PrivateSampleRetriever | None = None,
        mixed_retriever: MixedScopeRetriever | None = None,
        vector_store_adapter: VectorStoreAdapter | None = None,
        graph_index_builder: GraphIndexBuilder | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.vector_retriever = vector_retriever or DisabledVectorRetriever()
        self.embedding_provider = embedding_provider or get_embedding_provider()
        self.rerank_provider = rerank_provider or get_rerank_provider()
        self.public_retriever = public_retriever or get_public_policy_retriever()
        self.private_retriever = private_retriever or get_private_sample_retriever()
        self.mixed_retriever = mixed_retriever or get_mixed_scope_retriever()
        self.graph_index_builder = graph_index_builder or RuleBasedGraphIndexBuilder()
        self.current_vector_store_adapter = CurrentVectorStoreAdapter(
            public_retriever=self.public_retriever,
            private_retriever=self.private_retriever,
            mixed_retriever=self.mixed_retriever,
        )
        if vector_store_adapter is None:
            self.vector_store_adapter = build_vector_store_adapter(
                settings=self.settings,
                current_adapter=self.current_vector_store_adapter,
            )
            self.fallback_vector_store_adapter = self.current_vector_store_adapter
        else:
            self.vector_store_adapter = vector_store_adapter
            self.fallback_vector_store_adapter = vector_store_adapter

    def retrieve(self, params: RagQueryParams) -> RagRetrievalResult:
        started_at = perf_counter()
        chunk_top_k = params.chunk_top_k or params.top_k
        strategy_plan = plan_retrieval_strategy(mode=params.mode, knowledge_scope=params.knowledge_scope)
        provider_metadata: dict = {}
        vector_status = "disabled"
        fallback_reason = self._initial_fallback_reason()
        vector_hits: list[RetrievedChunk] = []
        vector_hit_count = 0
        vector_store_health = self._vector_store_health()
        provider_metadata["vector_store"] = vector_store_health.model_dump()
        chunk_source_metadata: dict[str, dict[str, Any]] = {}
        private_allowed_ids = self._private_allowed_ids(params)

        if params.retrieval_strategy is not None:
            strategy_result = self._retrieve_with_experimental_strategy(
                params=params,
                chunk_top_k=chunk_top_k,
                vector_store_health=vector_store_health,
            )
            selected_hits = strategy_result.chunks
            strategy_metadata = strategy_result.metadata
            chunk_source_metadata = strategy_metadata.get("chunk_sources", {})
            retrieval_layer = str(strategy_metadata.get("retrieval_layer") or "bm25_fallback")
            vector_status = str(strategy_metadata.get("vector_status") or "disabled")
            vector_hit_count = int(strategy_metadata.get("vector_hit_count") or 0)
            fallback_reason = _optional_metadata_str(strategy_metadata.get("fallback_reason"))
            provider_metadata["retriever_strategy"] = strategy_metadata
        else:
            if self.settings.rag_engine_enabled and self.settings.rag_vector_enabled:
                if self._uses_pgvector_backend():
                    if vector_store_health.available:
                        try:
                            query_embedding = self._resolve_query_embedding(params.question)
                            vector_store_result = self.vector_store_adapter.search(
                                question=params.question,
                                query_embedding=query_embedding,
                                top_k=chunk_top_k,
                                filters={
                                    "knowledge_scope": params.knowledge_scope,
                                    "source_type": self._source_type_filter(params.knowledge_scope),
                                    "allowed_knowledge_item_ids": sorted(private_allowed_ids)
                                    if private_allowed_ids is not None
                                    else [],
                                    "region": params.region,
                                    "doc_type": params.doc_type,
                                },
                                allowed_knowledge_item_ids=private_allowed_ids,
                            )
                            vector_hits = vector_store_result.chunks
                            vector_hit_count = vector_store_result.total_hits
                            provider_metadata["vector_store_search"] = vector_store_result.metadata
                            vector_status = "queried" if vector_store_result.metadata.get("status") != "error" else "error"
                            if vector_hits:
                                fallback_reason = None
                            else:
                                fallback_reason = str(
                                    vector_store_result.metadata.get("reason")
                                    or "pgvector_returned_no_hits"
                                )
                        except Exception as exc:  # noqa: BLE001
                            vector_status = "error"
                            fallback_reason = "pgvector_retrieval_error"
                            provider_metadata["vector_store_error"] = {"type": type(exc).__name__, "message": str(exc)}
                    else:
                        vector_status = "unavailable"
                        fallback_reason = vector_store_health.reason or "pgvector_unavailable"
                elif self.vector_retriever.is_available():
                    try:
                        query_embedding = self._resolve_query_embedding(params.question)
                        vector_result = self.vector_retriever.search(
                            question=params.question,
                            query_embedding=query_embedding,
                            top_k=chunk_top_k,
                            allowed_knowledge_item_ids=private_allowed_ids,
                        )
                        vector_hits = vector_result.chunks
                        vector_hit_count = len(vector_hits)
                        provider_metadata["vector"] = vector_result.metadata
                        vector_status = "queried"
                        fallback_reason = None if vector_hits else "vector_returned_no_hits"
                    except Exception as exc:  # noqa: BLE001
                        vector_status = "error"
                        fallback_reason = "vector_retrieval_error"
                        provider_metadata["vector_error"] = {"type": type(exc).__name__, "message": str(exc)}
                else:
                    vector_status = "unavailable"
                    fallback_reason = "vector_retriever_unavailable"

            if vector_hits:
                selected_hits = vector_hits[:chunk_top_k]
                retrieval_layer = "vector"
            else:
                fallback_result = self._fallback_search(params)
                selected_hits = fallback_result.hits
                retrieval_layer = "bm25_fallback"
                provider_metadata["fallback"] = {
                    "total_hits": fallback_result.total_hits,
                    "scope": params.knowledge_scope,
                }

        selected_hits, rerank_status = self._maybe_rerank(
            params=params,
            hits=selected_hits,
            provider_metadata=provider_metadata,
        )
        selected_hits = self._apply_metadata_filters(params=params, hits=selected_hits)

        chunks = [
            self._build_evidence_chunk(
                hit=hit,
                index=index,
                retrieval_layer=retrieval_layer,
                source_metadata=chunk_source_metadata.get(hit.chunk_id),
            )
            for index, hit in enumerate(selected_hits[: params.top_k], start=1)
        ]
        references = [
            RagEvidenceReference(
                reference_id=chunk.reference_id,
                chunk_id=chunk.chunk_id,
                doc_id=chunk.doc_id,
                title=chunk.title,
                source_type=chunk.source_type,
                source=chunk.source,
                source_url=chunk.source_url,
            )
            for chunk in chunks
        ]
        graph_status = "unavailable" if params.mode == "mix" else "skipped"
        retrieval_path = build_retrieval_path(
            retrieval_layer=retrieval_layer,
            vector_status=vector_status,
            graph_status=graph_status,
            rerank_status=rerank_status,
        )
        latency_ms = round((perf_counter() - started_at) * 1000, 3)
        fallback_used = retrieval_layer == "bm25_fallback"
        citation_refs = citation_refs_from_references(references, chunks=chunks)
        trace = RetrievalTrace(
            query=params.question,
            retriever_mode=retrieval_layer,
            requested_top_k=params.top_k,
            returned_count=len(chunks),
            fallback_used=fallback_used,
            fallback_reason=fallback_reason,
            chunk_ids=[chunk.chunk_id for chunk in chunks],
            citations=citation_refs,
            strategy=strategy_plan.name,
            retrieval_path=retrieval_path,
            latency_ms=latency_ms,
            total_hits=len(chunks),
            workflow_id=None,
            parser_name=None,
            vector_backend=vector_store_health.backend,
            error_code=fallback_reason if fallback_used and fallback_reason else None,
            metadata={
                "planned_layers": strategy_plan.planned_layers,
                "provider_metadata_keys": sorted(provider_metadata.keys()),
                "vector_backend": vector_store_health.backend,
                "vector_backend_health": vector_store_health.status,
                "vector_adapter_name": self._vector_adapter_name(vector_store_health),
                "vector_hit_count": vector_hit_count,
                "retrieval_strategy": params.retrieval_strategy,
            },
        )
        public_chunk_count, public_policy_demo_chunk_count, private_chunk_count = self._count_chunk_scopes(chunks)
        graph_metadata = (
            self._build_graph_metadata(chunks=chunks, question=params.question, graph_mode=params.graph_mode)
            if params.graph_mode != "off"
            else self._empty_graph_metadata(status="skipped", graph_mode=params.graph_mode)
        )
        provider_metadata["graph"] = graph_metadata["metadata"]

        metadata = RagRetrievalMetadata(
            mode=params.mode,
            knowledge_scope=params.knowledge_scope,
            top_k=params.top_k,
            chunk_top_k=chunk_top_k,
            retrieval_only=params.retrieval_only,
            retriever_mode=retrieval_layer,
            requested_top_k=params.top_k,
            returned_count=len(chunks),
            fallback_used=fallback_used,
            strategy=strategy_plan.name,
            retrieval_strategy=params.retrieval_strategy,
            retrieval_path=retrieval_path,
            vector_status=vector_status,
            vector_backend=vector_store_health.backend,
            vector_backend_health=vector_store_health.status,
            vector_adapter_name=self._vector_adapter_name(vector_store_health),
            vector_hit_count=vector_hit_count,
            graph_status=graph_status,
            graph_mode=params.graph_mode,
            graph_entity_count=graph_metadata["metadata"].get("entity_count"),
            graph_relation_count=graph_metadata["metadata"].get("relation_count"),
            graph_candidate_count=graph_metadata["metadata"].get("candidate_count"),
            graph_used=graph_metadata["metadata"].get("graph_used"),
            graph_fallback_reason=graph_metadata["metadata"].get("graph_fallback_reason"),
            rerank_status=rerank_status,
            fallback_reason=fallback_reason,
            latency_ms=trace.latency_ms,
            public_chunk_count=public_chunk_count,
            public_policy_demo_chunk_count=public_policy_demo_chunk_count,
            private_chunk_count=private_chunk_count,
            graph_entities=graph_metadata["entities"],
            graph_relations=graph_metadata["relations"],
            graph_candidates=graph_metadata["candidates"],
            trace=trace,
            provider_metadata=provider_metadata,
        )
        return RagRetrievalResult(
            query=params.question,
            total_hits=len(chunks),
            chunks=chunks,
            references=references if params.include_references else [],
            metadata=metadata,
        )

    def _initial_fallback_reason(self) -> str | None:
        if not self.settings.rag_engine_enabled:
            return "rag_engine_disabled"
        if not self.settings.rag_vector_enabled:
            return "rag_vector_disabled"
        return None

    @staticmethod
    def _private_allowed_ids(params: RagQueryParams) -> set[str] | None:
        if params.knowledge_scope == "public":
            return None
        return set(params.allowed_knowledge_item_ids)

    def _resolve_query_embedding(self, question: str) -> list[float] | None:
        if not self.vector_retriever.requires_embedding() and not self._uses_pgvector_backend():
            return None
        embedding_result = self.embedding_provider.embed_stub([question])
        if not embedding_result.vectors:
            return None
        return embedding_result.vectors[0]

    def _retrieve_with_experimental_strategy(
        self,
        *,
        params: RagQueryParams,
        chunk_top_k: int,
        vector_store_health: VectorStoreHealth,
    ) -> RetrieverStrategyResult:
        allowed_ids = self._private_allowed_ids(params)
        filters = {
            "knowledge_scope": params.knowledge_scope,
            "source_type": self._source_type_filter(params.knowledge_scope),
            "region": params.region,
            "doc_type": params.doc_type,
        }
        if allowed_ids is not None:
            filters["allowed_knowledge_item_ids"] = sorted(allowed_ids)
        query_embedding = None
        embedding_metadata: dict[str, Any] = {}
        if params.retrieval_strategy in {"vector_only", "bm25_vector_hybrid"}:
            try:
                query_embedding = self._resolve_query_embedding(params.question)
                embedding_metadata["query_embedding_seen"] = query_embedding is not None
            except Exception as exc:  # noqa: BLE001
                embedding_metadata = {
                    "query_embedding_seen": False,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }

        bm25_retriever = BM25Retriever(adapter=self.current_vector_store_adapter)
        vector_retriever = VectorRetriever(adapter=self.vector_store_adapter, health=vector_store_health)
        if params.retrieval_strategy == "bm25_only":
            result = bm25_retriever.retrieve(
                query=params.question,
                top_k=chunk_top_k,
                filters=filters,
                allowed_knowledge_item_ids=allowed_ids,
            )
        elif params.retrieval_strategy == "vector_only":
            result = vector_retriever.retrieve(
                query=params.question,
                top_k=chunk_top_k,
                filters=filters,
                query_embedding=query_embedding,
                allowed_knowledge_item_ids=allowed_ids,
            )
            if not result.chunks:
                fallback = bm25_retriever.retrieve(
                    query=params.question,
                    top_k=chunk_top_k,
                    filters=filters,
                    allowed_knowledge_item_ids=allowed_ids,
                )
                result = RetrieverStrategyResult(
                    strategy=result.strategy,
                    chunks=fallback.chunks,
                    total_hits=fallback.total_hits,
                    metadata={
                        **result.metadata,
                        "fallback_used": True,
                        "fallback_reason": result.metadata.get("fallback_reason") or "vector_returned_no_hits",
                        "fallback_metadata": fallback.metadata,
                        "chunk_sources": fallback.metadata.get("chunk_sources", {}),
                        "retrieval_layer": "bm25_fallback",
                    },
                )
        else:
            result = HybridRetriever(
                bm25_retriever=bm25_retriever,
                vector_retriever=vector_retriever,
            ).retrieve(
                query=params.question,
                top_k=chunk_top_k,
                filters=filters,
                query_embedding=query_embedding,
                allowed_knowledge_item_ids=allowed_ids,
            )

        result.metadata.update(
            {
                "strategy": params.retrieval_strategy,
                "filters": filters,
                "embedding": embedding_metadata,
            }
        )
        return result

    def _fallback_search(self, params: RagQueryParams) -> RetrievalResult:
        allowed_ids = self._private_allowed_ids(params)
        adapter_result = self.fallback_vector_store_adapter.search(
            question=params.question,
            top_k=params.top_k,
            filters={
                "knowledge_scope": params.knowledge_scope,
                "region": params.region,
                "doc_type": params.doc_type,
                "allowed_knowledge_item_ids": sorted(allowed_ids) if allowed_ids is not None else [],
            },
            allowed_knowledge_item_ids=allowed_ids,
        )
        return RetrievalResult(
            query=params.question,
            top_k=params.top_k,
            total_hits=adapter_result.total_hits,
            hits=adapter_result.chunks,
        )

    def _uses_pgvector_backend(self) -> bool:
        return str(getattr(self.settings, "rag_vector_backend", "current") or "current").strip().lower() == "pgvector"

    @staticmethod
    def _source_type_filter(knowledge_scope: RagKnowledgeScope) -> str | None:
        if knowledge_scope == "public":
            return "public_policy"
        if knowledge_scope == "private_sample":
            return "private_sample"
        return None

    def _maybe_rerank(
        self,
        *,
        params: RagQueryParams,
        hits: list[RetrievedChunk],
        provider_metadata: dict,
    ) -> tuple[list[RetrievedChunk], str]:
        if not params.enable_rerank:
            return hits, "disabled"
        if not self.settings.rag_rerank_enabled:
            return hits, "disabled"
        try:
            rerank_items = [
                RerankItem(
                    item_id=hit.chunk_id,
                    text=hit.snippet,
                    metadata={"doc_id": hit.doc_id, "source_type": hit.source_type},
                )
                for hit in hits
            ]
            rerank_result = self.rerank_provider.rerank_stub(
                query=params.question,
                items=rerank_items,
                top_k=params.top_k,
            )
            provider_metadata["rerank"] = rerank_result.metadata
            if rerank_result.metadata.get("status") == "skipped":
                return hits, "skipped"
            order = {chunk_id: index for index, chunk_id in enumerate(rerank_result.ranked_ids)}
            reranked = sorted(
                hits,
                key=lambda hit: order.get(hit.chunk_id, len(order)),
            )
            return reranked[: params.top_k], "applied"
        except Exception as exc:  # noqa: BLE001
            provider_metadata["rerank_error"] = {"type": type(exc).__name__, "message": str(exc)}
            return hits, "error"

    @staticmethod
    def _apply_metadata_filters(
        *,
        params: RagQueryParams,
        hits: list[RetrievedChunk],
    ) -> list[RetrievedChunk]:
        filtered = hits
        if params.region:
            filtered = [hit for hit in filtered if hit.region == params.region]
        if params.doc_type:
            filtered = [hit for hit in filtered if hit.doc_type == params.doc_type]
        return filtered

    @staticmethod
    def _build_evidence_chunk(
        *,
        hit: RetrievedChunk,
        index: int,
        retrieval_layer: str,
        source_metadata: dict[str, Any] | None = None,
    ) -> RagEvidenceChunk:
        source_metadata = source_metadata or {}
        resolved_layer = _optional_metadata_str(source_metadata.get("retrieval_layer")) or retrieval_layer
        return RagEvidenceChunk(
            reference_id=f"ref-{index}",
            doc_id=hit.doc_id,
            knowledge_item_id=hit.knowledge_item_id,
            title=hit.title,
            source_type=hit.source_type,
            source=hit.source,
            source_url=hit.source_url,
            issued_at=hit.issued_at,
            region=hit.region,
            doc_type=hit.doc_type,
            sample_type=hit.sample_type,
            business_topic=hit.business_topic,
            library_scope=hit.library_scope,
            chunk_id=hit.chunk_id,
            snippet=hit.snippet,
            score=hit.score,
            retrieval_layer=resolved_layer,  # type: ignore[arg-type]
            bm25_score=_optional_metadata_float(source_metadata.get("bm25_score")),
            vector_score=_optional_metadata_float(source_metadata.get("vector_score")),
            merged_score=_optional_metadata_float(source_metadata.get("merged_score")),
            from_bm25=_optional_metadata_bool(source_metadata.get("from_bm25")),
            from_vector=_optional_metadata_bool(source_metadata.get("from_vector")),
            source_retrievers=_metadata_str_list(source_metadata.get("source_retrievers")),
        )

    @staticmethod
    def _count_chunk_scopes(chunks: list[RagEvidenceChunk]) -> tuple[int, int, int]:
        public_count = sum(1 for chunk in chunks if chunk.source_type == "public_policy")
        public_demo_count = sum(1 for chunk in chunks if chunk.source_type == "public_policy_demo")
        private_count = sum(1 for chunk in chunks if chunk.source_type in {"private_sample", "private_upload"})
        return public_count, public_demo_count, private_count

    def _vector_store_health(self) -> VectorStoreHealth:
        try:
            return self.vector_store_adapter.healthcheck()
        except Exception as exc:  # noqa: BLE001
            backend = str(getattr(self.vector_store_adapter, "backend", "current") or "current")
            return VectorStoreHealth(
                backend=backend,
                status="degraded",
                available=False,
                reason=str(exc),
                metadata={"adapter_name": type(self.vector_store_adapter).__name__, "error_type": type(exc).__name__},
            )

    def _build_graph_metadata(
        self,
        *,
        chunks: list[RagEvidenceChunk],
        question: str,
        graph_mode: str,
    ) -> dict[str, Any]:
        if not chunks:
            return self._empty_graph_metadata(
                status="ok",
                graph_mode=graph_mode,
                graph_fallback_reason="graph_no_retrieved_chunks",
            )
        try:
            if not self.graph_index_builder.is_available():
                return self._empty_graph_metadata(
                    status="disabled",
                    graph_mode=graph_mode,
                    graph_fallback_reason="graph_index_unavailable",
                )
            chunk_records = [chunk_record_from_evidence_chunk(chunk) for chunk in chunks]
            build_result = self.graph_index_builder.build(chunks=chunk_records)
            selected_candidates, graph_fallback_reason = select_graph_candidates(
                mode=graph_mode,
                question=question,
                build_result=build_result,
                top_k=len(chunks) or 5,
            )
            return {
                "entities": build_result.entities,
                "relations": build_result.relations,
                "candidates": selected_candidates,
                "metadata": {
                    **build_result.metadata,
                    "status": build_result.status,
                    "graph_mode": graph_mode,
                    "entity_count": build_result.entity_count,
                    "relation_count": build_result.relation_count,
                    "community_count": build_result.community_count,
                    "candidate_count": len(selected_candidates),
                    "raw_candidate_count": build_result.candidate_count,
                    "graph_used": bool(selected_candidates),
                    "graph_fallback_reason": graph_fallback_reason,
                },
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "entities": [],
                "relations": [],
                "candidates": [],
                "metadata": {
                    "status": "error",
                    "graph_mode": graph_mode,
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                    "graph_used": False,
                    "graph_fallback_reason": "graph_query_error",
                },
            }

    @staticmethod
    def _empty_graph_metadata(
        *,
        status: str,
        graph_mode: str = "off",
        graph_fallback_reason: str | None = None,
    ) -> dict[str, Any]:
        return {
            "entities": [],
            "relations": [],
            "candidates": [],
            "metadata": {
                "status": status,
                "graph_mode": graph_mode,
                "entity_count": 0,
                "relation_count": 0,
                "candidate_count": 0,
                "graph_used": False,
                "graph_fallback_reason": graph_fallback_reason,
            },
        }

    @staticmethod
    def _vector_adapter_name(health: VectorStoreHealth) -> str:
        adapter_name = health.metadata.get("adapter_name")
        return adapter_name if isinstance(adapter_name, str) and adapter_name else health.backend


def _optional_metadata_str(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _optional_metadata_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _optional_metadata_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _metadata_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def build_rag_query_params(
    *,
    question: str,
    knowledge_scope: RagKnowledgeScope,
    top_k: int = 5,
    mode: str | None = None,
    allowed_knowledge_item_ids: list[str] | set[str] | None = None,
    enable_rerank: bool = True,
    region: str | None = None,
    doc_type: str | None = None,
) -> RagQueryParams:
    settings = get_settings()
    requested_mode = mode or settings.rag_default_mode
    if requested_mode not in {"naive", "mix"}:
        requested_mode = "mix"
    return RagQueryParams(
        question=question,
        mode=requested_mode,  # type: ignore[arg-type]
        knowledge_scope=knowledge_scope,
        top_k=top_k,
        allowed_knowledge_item_ids=list(allowed_knowledge_item_ids or []),
        enable_rerank=enable_rerank,
        region=region,
        doc_type=doc_type,
        graph_mode="off",
    )


@lru_cache(maxsize=1)
def get_rag_engine_service() -> RagEngineService:
    return RagEngineService()
