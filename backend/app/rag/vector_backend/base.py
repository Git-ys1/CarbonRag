from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.rag.kb.models import RagChunk


@dataclass(slots=True)
class VectorSearchHit:
    chunk: RagChunk
    score: float


@dataclass(slots=True)
class VectorSearchResult:
    hits: list[VectorSearchHit]
    backend: str
    available: bool
    degraded: bool = False
    warning: str | None = None
    client_ms: float = 0.0
    search_ms: float = 0.0
    embedding_ms: float = 0.0
    client_init_count: int = 0


@dataclass(slots=True)
class VectorIndexResult:
    indexed_count: int
    backend: str
    available: bool
    degraded: bool = False
    warning: str | None = None
    client_ms: float = 0.0
    insert_ms: float = 0.0
    embedding_ms: float = 0.0
    client_init_count: int = 0


class BaseVectorStore(ABC):
    backend_name: str

    def index_chunks(self, *, chunks: list[RagChunk], embeddings=None) -> VectorIndexResult:
        return VectorIndexResult(
            indexed_count=len(chunks),
            backend=self.backend_name,
            available=True,
        )

    def delete_document(self, *, kb_id: str, doc_id: str) -> bool:
        del kb_id, doc_id
        return False

    @abstractmethod
    def search(self, *, query: str, chunks: list[RagChunk], top_k: int) -> VectorSearchResult:
        raise NotImplementedError

