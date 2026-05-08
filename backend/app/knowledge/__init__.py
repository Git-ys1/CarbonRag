from __future__ import annotations

from importlib import import_module

from app.knowledge.chunker import (
    chunk_knowledge_text,
    chunk_text_to_knowledge_chunks,
    hash_chunk_content,
    token_count,
)
from app.knowledge.extractor import extract_text_from_source
from app.knowledge.schemas import (
    KnowledgeChunk,
    KnowledgeChunkInput,
    KnowledgeIndexStatus,
    KnowledgeIngestStatus,
    KnowledgeItem,
    KnowledgeItemListFilters,
    KnowledgeItemScope,
    KnowledgeItemSourceType,
    KnowledgeItemStatus,
    KnowledgeParseStatus,
    KnowledgeTask,
    KnowledgeTaskListFilters,
    KnowledgeTaskStatus,
    KnowledgeTaskType,
    ParsedDocument,
)
from app.knowledge.store import BaseKnowledgeStore, KnowledgeStore, build_knowledge_store

__all__ = [
    "BaseKnowledgeStore",
    "KnowledgeChunk",
    "KnowledgeChunkInput",
    "KnowledgeIndexStatus",
    "KnowledgeIngestStatus",
    "KnowledgeItem",
    "KnowledgeItemListFilters",
    "KnowledgeItemScope",
    "KnowledgeItemSourceType",
    "KnowledgeItemStatus",
    "KnowledgeParseStatus",
    "KnowledgeStore",
    "KnowledgeTask",
    "KnowledgeTaskListFilters",
    "KnowledgeTaskRunner",
    "KnowledgeTaskStatus",
    "KnowledgeTaskType",
    "KnowledgeService",
    "ParsedDocument",
    "build_knowledge_store",
    "chunk_knowledge_text",
    "chunk_text_to_knowledge_chunks",
    "extract_text_from_source",
    "get_knowledge_service",
    "get_knowledge_task_runner",
    "get_policy_crawler_scheduler",
    "hash_chunk_content",
    "token_count",
]


def __getattr__(name: str):
    if name == "KnowledgeService" or name == "get_knowledge_service":
        module = import_module("app.knowledge.service")
        return getattr(module, name)
    if name == "KnowledgeTaskRunner" or name == "get_knowledge_task_runner":
        module = import_module("app.knowledge.runner")
        return getattr(module, name)
    if name == "get_policy_crawler_scheduler":
        module = import_module("app.knowledge.policy_live_crawler")
        return getattr(module, name)
    raise AttributeError(name)
