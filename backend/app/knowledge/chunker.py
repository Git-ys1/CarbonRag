from __future__ import annotations

import hashlib

import jieba

from app.knowledge.schemas import KnowledgeChunk, KnowledgeItem

MIN_CHUNK_LENGTH = 80
MAX_CHUNK_LENGTH = 420


def chunk_knowledge_text(*, item: KnowledgeItem, text: str, created_at) -> list[KnowledgeChunk]:
    segments = _split_segments(text)
    merged = _merge_segments(segments)
    chunks: list[KnowledgeChunk] = []
    for index, snippet in enumerate(merged, start=1):
        chunks.append(
            KnowledgeChunk(
                knowledge_item_id=item.knowledge_item_id,
                chunk_id=f"{item.knowledge_item_id}_chunk_{index:02d}",
                tenant_id=item.tenant_id,
                owner_user_id=item.owner_user_id,
                visibility=item.visibility,
                created_by=item.created_by,
                title=item.title,
                source_type=_resolve_chunk_source_type(item),
                library_scope=item.library_scope,
                source=item.source or _resolve_default_source(item),
                source_url=item.source_url,
                sample_type=item.sample_type,
                business_topic=item.business_topic,
                snippet=snippet,
                order_index=index,
                created_at=created_at,
                updated_at=created_at,
            )
        )
    return chunks


def chunk_text_to_knowledge_chunks(
    *,
    knowledge_item_id: str,
    title: str,
    source_type: str,
    library_scope: str,
    source: str,
    snippet_text: str,
    source_url: str | None = None,
    issued_at: str | None = None,
    region: str | None = None,
    doc_type: str | None = None,
    sample_type: str | None = None,
    business_topic: str | None = None,
    created_at=None,
) -> list[KnowledgeChunk]:
    pseudo_item = KnowledgeItem(
        knowledge_item_id=knowledge_item_id,
        owner_user_id=None,
        library_scope=library_scope,  # type: ignore[arg-type]
        source_type=source_type,  # type: ignore[arg-type]
        source_ref=knowledge_item_id,
        file_id=None,
        source=source,
        source_url=source_url,
        sample_type=sample_type,
        business_topic=business_topic,
        title=title,
        mime_type="text/plain",
        storage_path="",
        parse_status="parsed",
        ingest_status="ingested",
        index_status="indexed",
        is_enabled=True,
        session_attachable=True,
        source_hash=None,
        source_mtime=None,
        last_error=None,
        created_at=created_at or chunk_utcnow(),
        updated_at=created_at or chunk_utcnow(),
        last_indexed_at=created_at or chunk_utcnow(),
    )
    chunks = chunk_knowledge_text(item=pseudo_item, text=snippet_text, created_at=created_at or chunk_utcnow())
    for chunk in chunks:
        chunk.source_url = source_url
        chunk.issued_at = issued_at
        chunk.region = region
        chunk.doc_type = doc_type
    return chunks


def _split_segments(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    parts = [segment.strip() for segment in normalized.split("\n\n")]
    flattened: list[str] = []
    for part in parts:
        if not part:
            continue
        lines = [line.strip() for line in part.splitlines() if line.strip()]
        flattened.append(" ".join(lines))
    return flattened


def _merge_segments(segments: list[str]) -> list[str]:
    if not segments:
        return []

    merged: list[str] = []
    buffer = ""
    for segment in segments:
        current = segment.strip()
        if not current:
            continue
        candidate = f"{buffer}\n\n{current}".strip() if buffer else current
        if len(candidate) <= MAX_CHUNK_LENGTH:
            buffer = candidate
            continue
        if buffer:
            merged.append(buffer)
            buffer = ""
        if len(current) <= MAX_CHUNK_LENGTH:
            buffer = current
            continue
        merged.extend(_slice_long_segment(current))

    if buffer:
        merged.append(buffer)

    normalized: list[str] = []
    carry = ""
    for chunk in merged:
        candidate = f"{carry}\n\n{chunk}".strip() if carry else chunk
        if len(candidate) < MIN_CHUNK_LENGTH:
            carry = candidate
            continue
        normalized.append(candidate)
        carry = ""
    if carry:
        if normalized:
            normalized[-1] = f"{normalized[-1]}\n\n{carry}".strip()
        else:
            normalized.append(carry)
    return normalized


def _slice_long_segment(segment: str) -> list[str]:
    words = segment.split()
    if len(words) <= 1:
        return [segment[index:index + MAX_CHUNK_LENGTH].strip() for index in range(0, len(segment), MAX_CHUNK_LENGTH)]

    pieces: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= MAX_CHUNK_LENGTH:
            current = candidate
            continue
        if current:
            pieces.append(current)
        current = word
    if current:
        pieces.append(current)
    return pieces


def _resolve_chunk_source_type(item: KnowledgeItem) -> str:
    if item.source_type == "public_policy_web":
        if item.visibility == "demo":
            return "public_policy_demo"
        return "public_policy"
    if item.source_type == "uploaded_file":
        return "private_upload"
    return "private_sample"


def _resolve_default_source(item: KnowledgeItem) -> str:
    if item.source_type == "public_policy_web":
        if item.visibility == "demo":
            return "CarbonRag 演示样例"
        return "官方政策采集"
    if item.library_scope == "shared":
        return "管理员共享知识库"
    return "用户上传知识"


def chunk_utcnow():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


def hash_chunk_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def token_count(content: str) -> int:
    return len([token for token in jieba.lcut_for_search(content) if token.strip()])
