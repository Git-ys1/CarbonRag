from __future__ import annotations

from datetime import datetime, timezone

from app.knowledge.runner import KnowledgeTaskRunner
from app.knowledge.service import KnowledgeService
from app.knowledge.store import KnowledgeStore
from app.session.adapters.sqlite_store import SQLiteSessionStore
from tests.test_helpers import create_test_user_id


class _NoBootstrapKnowledgeService(KnowledgeService):
    def bootstrap_shared_library(self):  # type: ignore[override]
        return []


class _FakeSessionService:
    knowledge_service = None


def _create_session_and_upload(tmp_path, *, filename: str, content: str, prefix: str):
    db_path = tmp_path / "carbonrag.sqlite3"
    owner_user_id = create_test_user_id(db_path, prefix=prefix[:12])
    session_store = SQLiteSessionStore(db_path)
    session = session_store.create_session(
        session_id=f"session-{prefix}",
        owner_user_id=owner_user_id,
        title="知识库测试会话",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    source_path = tmp_path / filename
    source_path.write_text(content, encoding="utf-8")
    uploaded_file = session_store.create_uploaded_file(
        file_id=f"file-{prefix}",
        session_id=session.session_id,
        filename=filename,
        size=source_path.stat().st_size,
        mime_type="text/plain" if filename.endswith(".txt") else "application/msword",
        stored_at=datetime.now(timezone.utc).isoformat(),
        storage_path=str(source_path),
    )
    return db_path, owner_user_id, session, source_path, uploaded_file


def test_knowledge_service_ingests_uploaded_text_file(tmp_path, monkeypatch) -> None:
    db_path, owner_user_id, _, _, uploaded_file = _create_session_and_upload(
        tmp_path,
        filename="energy.txt",
        content="企业节能改造\n照明与空调优化",
        prefix="knowledgeok",
    )
    store = KnowledgeStore(sqlite_db_path=db_path)
    runner = KnowledgeTaskRunner()
    service = _NoBootstrapKnowledgeService(store=store, session_service=_FakeSessionService())

    monkeypatch.setattr("app.knowledge.runner.get_knowledge_task_runner", lambda: runner)
    monkeypatch.setattr("app.knowledge.service.get_knowledge_service", lambda: service)

    tasks = service.sync_uploaded_files(owner_user_id=owner_user_id)
    assert tasks
    assert tasks[0].knowledge_item_id == uploaded_file.file_id

    processed = runner.run_once()
    assert tasks[0].task_id in processed

    item = store.get_item(uploaded_file.file_id)
    assert item is not None
    assert item.parse_status == "parsed"
    assert item.ingest_status == "ingested"
    assert item.index_status == "indexed"
    assert store.list_chunks(uploaded_file.file_id)
    assert store.list_my_uploads(owner_user_id=owner_user_id)[0].knowledge_item_id == uploaded_file.file_id


def test_knowledge_service_marks_unsupported_doc_as_parse_failed(tmp_path, monkeypatch) -> None:
    db_path, owner_user_id, _, _, uploaded_file = _create_session_and_upload(
        tmp_path,
        filename="legacy.doc",
        content="旧版 DOC 不能直接解析",
        prefix="knowledgefail",
    )
    store = KnowledgeStore(sqlite_db_path=db_path)
    runner = KnowledgeTaskRunner()
    service = _NoBootstrapKnowledgeService(store=store, session_service=_FakeSessionService())

    monkeypatch.setattr("app.knowledge.runner.get_knowledge_task_runner", lambda: runner)
    monkeypatch.setattr("app.knowledge.service.get_knowledge_service", lambda: service)

    tasks = service.sync_uploaded_files(owner_user_id=owner_user_id)
    assert tasks

    processed = runner.run_once()
    assert tasks[0].task_id in processed

    item = store.get_item(uploaded_file.file_id)
    assert item is not None
    assert item.parse_status == "parse_failed"
    assert item.ingest_status == "ingest_failed"
    assert item.index_status == "index_failed"
    task = store.get_task(tasks[0].task_id)
    assert task is not None
    assert task.status == "failed"
    assert task.error_detail


def test_clear_private_retrieval_caches_also_clears_rag_engine(monkeypatch) -> None:
    cleared: list[str] = []

    class FakeRagEngineFactory:
        def __call__(self):
            raise AssertionError("cache clear should not instantiate the RAG engine")

        def cache_clear(self) -> None:
            cleared.append("rag")

    monkeypatch.setattr(
        "app.retrieval.private_retriever.get_private_sample_retriever.cache_clear",
        lambda: cleared.append("private"),
    )
    monkeypatch.setattr(
        "app.retrieval.mixed_retriever.get_mixed_scope_retriever.cache_clear",
        lambda: cleared.append("mixed"),
    )
    monkeypatch.setattr("app.rag.service.get_rag_engine_service", FakeRagEngineFactory())

    KnowledgeService._clear_private_retrieval_caches()

    assert cleared == ["private", "mixed", "rag"]
