from functools import lru_cache
from typing import Any

import jieba

from app.knowledge.schemas import KnowledgeChunk
from app.retrieval.bm25_compat import BM25Okapi
from app.retrieval.public_chunker import chunk_public_policy_document
from app.retrieval.public_corpus_loader import load_public_policy_documents
from app.retrieval.schemas import RetrievedChunk, RetrievalResult


def _tokenize(text: str) -> list[str]:
    return [
        token.strip()
        for token in jieba.lcut_for_search(text)
        if token.strip() and any(character.isalnum() or "\u4e00" <= character <= "\u9fff" for character in token)
    ]


class PublicPolicyRetriever:
    def __init__(self) -> None:
        self.documents = load_public_policy_documents()
        self.chunks: list[RetrievedChunk] = []
        for document in self.documents:
            self.chunks.extend(chunk_public_policy_document(document))
        self.chunks.extend(_load_runtime_policy_web_chunks())
        self._corpus_tokens = [_tokenize(chunk.snippet) for chunk in self.chunks]
        self._bm25 = BM25Okapi(self._corpus_tokens)

    def search(
        self,
        *,
        question: str,
        top_k: int = 5,
        knowledge_scope: str = "public",
        region: str | None = None,
        doc_type: str | None = None,
    ) -> RetrievalResult:
        if knowledge_scope != "public":
            raise ValueError("PublicPolicyRetriever only supports public knowledge scope.")

        query_tokens = _tokenize(question)
        if not query_tokens:
            return RetrievalResult(query=question, top_k=top_k, total_hits=0, hits=[])

        scores = self._bm25.get_scores(query_tokens)
        ranked_hits: list[RetrievedChunk] = []

        for chunk, score in zip(self.chunks, scores, strict=True):
            if region and chunk.region != region:
                continue
            if doc_type and chunk.doc_type != doc_type:
                continue

            title_boost = 0.0
            if any(token in chunk.title for token in query_tokens):
                title_boost = 0.5
            final_score = float(score) + title_boost
            if final_score <= 0:
                continue

            ranked_hits.append(chunk.model_copy(update={"score": round(final_score, 6)}))

        ranked_hits.sort(key=lambda item: item.score, reverse=True)
        selected_hits = ranked_hits[:top_k]
        return RetrievalResult(
            query=question,
            top_k=top_k,
            total_hits=len(selected_hits),
            hits=selected_hits,
        )


@lru_cache(maxsize=1)
def get_public_policy_retriever() -> PublicPolicyRetriever:
    return PublicPolicyRetriever()


def _load_runtime_policy_web_chunks() -> list[RetrievedChunk]:
    try:
        from app.knowledge import get_knowledge_service

        service = get_knowledge_service()
        items = service.list_admin_items(
            source_type="public_policy_web",
            index_status="indexed",
            is_enabled=True,
        )
        chunks: list[RetrievedChunk] = []
        for item in items:
            for chunk in service.list_chunks(knowledge_item_id=item.knowledge_item_id):
                chunks.append(_runtime_policy_chunk_to_retrieved_chunk(chunk))
        return chunks
    except Exception:  # noqa: BLE001
        return []


def _runtime_policy_chunk_to_retrieved_chunk(chunk: KnowledgeChunk) -> RetrievedChunk:
    return RetrievedChunk(
        doc_id=chunk.knowledge_item_id,
        knowledge_item_id=chunk.knowledge_item_id,
        title=chunk.title,
        source_type=_runtime_chunk_source_type(chunk),
        source=chunk.source,
        source_url=chunk.source_url,
        issued_at=chunk.issued_at,
        region=_optional_str(chunk.region),
        doc_type=_optional_str(chunk.doc_type),
        sample_type=_optional_str(chunk.sample_type),
        business_topic=_optional_str(chunk.business_topic),
        library_scope=chunk.library_scope if chunk.library_scope in {"personal", "shared"} else None,  # type: ignore[arg-type]
        chunk_id=chunk.chunk_id,
        snippet=chunk.snippet,
        score=0.0,
    )


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _runtime_chunk_source_type(chunk: KnowledgeChunk):
    if chunk.source_type == "public_policy_demo" or chunk.visibility == "demo":
        return "public_policy_demo"
    return "public_policy"
