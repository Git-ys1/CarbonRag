from __future__ import annotations

from pathlib import Path

from app.core.config import Settings
from app.knowledge.policy_ingestion import (
    CrawledDocument,
    FakeCrawlerProvider,
    PolicyCrawlRequest,
    ScrapydCrawlerProvider,
    ScrapyCrawlerProvider,
)
from app.knowledge.policy_live_crawler import PolicyCrawlerScheduler, PolicyCrawlerStore
from app.knowledge.runner import KnowledgeTaskRunner
from app.knowledge.service import KnowledgeService
from app.knowledge.store import KnowledgeStore
from app.retrieval.public_retriever import get_public_policy_retriever


def test_policy_live_crawler_startup_seeds_sources_without_scheduled_run(tmp_path) -> None:
    scheduler = _build_scheduler(tmp_path, provider=FakeCrawlerProvider(documents=[]))

    scheduler.start()

    status = scheduler.status()
    assert status.scheduler_started is True
    assert status.scheduled_enabled is False
    assert status.source_count >= 1
    assert scheduler.list_runs() == []

    scheduler.stop()


def test_policy_live_crawler_scrapy_unavailable_records_run_without_crashing(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("app.knowledge.policy_ingestion.importlib.util.find_spec", lambda name: None)
    scheduler = _build_scheduler(tmp_path)
    scheduler.start()

    status = scheduler.status()
    assert status.manual_enabled is True
    assert status.provider_enabled is True
    assert status.provider_available is False

    run = scheduler.run_source_now(source_id="gov-cn-policy-library", triggered_by_user_id=None)

    assert run.status == "unavailable"
    assert "Scrapy is not installed." in (run.error_detail or "")
    assert scheduler.list_candidates() == []


def test_policy_live_crawler_backend_defaults_to_local_scrapy(tmp_path) -> None:
    scheduler = _build_scheduler(tmp_path)
    scheduler.start()

    status = scheduler.status()

    assert status.crawler_backend == "local_scrapy"
    assert status.provider_mode == "scrapy"
    assert status.manual_enabled is True
    assert status.scheduled_enabled is False


def test_policy_live_crawler_scrapyd_unavailable_does_not_crash(tmp_path) -> None:
    def fake_get(url: str, timeout_seconds: float):
        del url, timeout_seconds
        raise RuntimeError("daemon refused connection")

    settings = _settings(
        tmp_path,
        {
            "rag_policy_crawler_backend": "scrapyd",
            "rag_policy_scrapyd_endpoint": "http://127.0.0.1:6800",
        },
    )
    provider = ScrapydCrawlerProvider(settings=settings, http_get=fake_get)
    scheduler = _build_scheduler(tmp_path, provider=provider, settings=settings)
    scheduler.start()

    status = scheduler.status()
    run = scheduler.run_source_now(source_id="gov-cn-policy-library", triggered_by_user_id=None)

    assert status.crawler_backend == "scrapyd"
    assert status.provider_available is False
    assert status.scrapyd_available is False
    assert status.scrapyd_endpoint_label == "http://127.0.0.1:6800"
    assert "daemon refused connection" in (status.provider_error or "")
    assert run.status == "unavailable"
    assert scheduler.list_candidates() == []


def test_policy_live_crawler_scrapyd_success_stages_pending_candidates(tmp_path) -> None:
    document = _official_document("https://www.gov.cn/zhengce/scrapyd-policy.html")

    def fake_get(url: str, timeout_seconds: float):
        del timeout_seconds
        if url.endswith("/daemonstatus.json"):
            return {"status": "ok"}
        return {"status": "ok", "finished": [{"id": "job-1"}], "running": [], "pending": []}

    def fake_post(url: str, payload: dict, timeout_seconds: float):
        del url, timeout_seconds
        assert payload["project"] == "carbonrag"
        assert payload["spider"] == "carbonrag_policy_spider"
        assert payload["obey_robots"] == "true"
        return {"status": "ok", "jobid": "job-1", "documents": [document.model_dump(mode="json")]}

    settings = _settings(tmp_path, {"rag_policy_crawler_backend": "scrapyd"})
    provider = ScrapydCrawlerProvider(settings=settings, http_get=fake_get, http_post=fake_post, sleeper=lambda seconds: None)
    scheduler = _build_scheduler(tmp_path, provider=provider, settings=settings)
    scheduler.start()

    run = scheduler.run_source_now(source_id="gov-cn-policy-library", triggered_by_user_id=None)
    candidates = scheduler.list_candidates()

    assert run.status == "succeeded"
    assert run.metadata["external_job_id"] == "job-1"
    assert candidates
    assert candidates[0].status == "pending_review"
    assert candidates[0].url == document.url


def test_scrapyd_provider_rejects_non_allowlisted_url_before_http_calls(tmp_path) -> None:
    calls = {"get": 0, "post": 0}

    def fake_get(url: str, timeout_seconds: float):
        del url, timeout_seconds
        calls["get"] += 1
        return {"status": "ok"}

    def fake_post(url: str, payload: dict, timeout_seconds: float):
        del url, payload, timeout_seconds
        calls["post"] += 1
        return {"status": "ok", "jobid": "job-1"}

    provider = ScrapydCrawlerProvider(
        settings=_settings(tmp_path, {"rag_policy_crawler_backend": "scrapyd"}),
        http_get=fake_get,
        http_post=fake_post,
    )

    result = provider.crawl(
        PolicyCrawlRequest(
            start_urls=["https://example.com/not-official.html"],
            allowed_domains=["www.gov.cn"],
        )
    )

    assert result.status == "rejected"
    assert calls == {"get": 0, "post": 0}


def test_policy_live_crawler_stages_pending_candidates_before_indexing(tmp_path) -> None:
    document = _official_document("https://www.gov.cn/zhengce/live-policy.html")
    scheduler = _build_scheduler(tmp_path, provider=FakeCrawlerProvider(documents=[document]))
    scheduler.start()

    run = scheduler.run_source_now(source_id="gov-cn-policy-library", triggered_by_user_id=None)
    candidates = scheduler.list_candidates()
    knowledge_store = KnowledgeStore(sqlite_db_path=tmp_path / "carbonrag.sqlite3")

    assert run.status == "succeeded"
    assert run.candidate_count == 1
    assert candidates[0].status == "pending_review"
    assert candidates[0].storage_path
    assert Path(candidates[0].storage_path).exists()
    assert knowledge_store.get_item_by_source(
        owner_user_id=None,
        library_scope="shared",
        source_type="public_policy_web",
        source_ref=document.url,
    ) is None


def test_policy_live_crawler_publish_candidate_enqueues_crawl_ingest(monkeypatch, tmp_path) -> None:
    document = _official_document("https://www.gov.cn/zhengce/publish-policy.html")
    scheduler = _build_scheduler(tmp_path, provider=FakeCrawlerProvider(documents=[document]))
    scheduler.start()
    scheduler.run_source_now(source_id="gov-cn-policy-library", triggered_by_user_id=None)
    candidate = scheduler.list_candidates()[0]
    runner = KnowledgeTaskRunner()
    service = _NoBootstrapKnowledgeService(
        store=KnowledgeStore(sqlite_db_path=tmp_path / "carbonrag.sqlite3"),
        session_service=_FakeSessionService(),
    )
    monkeypatch.setattr("app.knowledge.service.get_knowledge_service", lambda: service)
    monkeypatch.setattr("app.knowledge.runner.get_knowledge_task_runner", lambda: runner)

    published = scheduler.publish_candidate(candidate_id=candidate.candidate_id, reviewed_by_user_id=None)
    queued_tasks = service.list_tasks(knowledge_item_id=published.knowledge_item_id, include_shared=True)

    assert published.status == "published"
    assert published.knowledge_item_id
    assert queued_tasks
    assert queued_tasks[0].task_type == "crawl_ingest"
    assert queued_tasks[0].status == "queued"


def test_policy_live_crawler_reject_candidate_does_not_index(monkeypatch, tmp_path) -> None:
    document = _official_document("https://www.gov.cn/zhengce/reject-policy.html")
    scheduler = _build_scheduler(tmp_path, provider=FakeCrawlerProvider(documents=[document]))
    scheduler.start()
    scheduler.run_source_now(source_id="gov-cn-policy-library", triggered_by_user_id=None)
    candidate = scheduler.list_candidates()[0]
    service = _NoBootstrapKnowledgeService(
        store=KnowledgeStore(sqlite_db_path=tmp_path / "carbonrag.sqlite3"),
        session_service=_FakeSessionService(),
    )
    monkeypatch.setattr("app.knowledge.service.get_knowledge_service", lambda: service)

    rejected = scheduler.reject_candidate(candidate_id=candidate.candidate_id, reviewed_by_user_id=None)

    assert rejected.status == "rejected"
    assert service.store.get_item_by_source(
        owner_user_id=None,
        library_scope="shared",
        source_type="public_policy_web",
        source_ref=document.url,
    ) is None
    assert service.list_tasks(include_shared=True, task_type="crawl_ingest") == []


def test_policy_live_crawler_non_reentrant_guard(tmp_path) -> None:
    scheduler = _build_scheduler(tmp_path, provider=FakeCrawlerProvider(documents=[]))
    scheduler.start()

    assert scheduler._run_lock.acquire(blocking=False) is True
    try:
        try:
            scheduler.run_source_now(source_id="gov-cn-policy-library", triggered_by_user_id=None)
        except RuntimeError as exc:
            assert "already running" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("scheduler should reject re-entrant runs")
    finally:
        scheduler._run_lock.release()


def test_policy_live_crawler_published_candidate_can_be_processed(monkeypatch, tmp_path) -> None:
    document = _official_document("https://www.gov.cn/zhengce/index-policy.html")
    scheduler = _build_scheduler(tmp_path, provider=FakeCrawlerProvider(documents=[document]))
    scheduler.start()
    scheduler.run_source_now(source_id="gov-cn-policy-library", triggered_by_user_id=None)
    candidate = scheduler.list_candidates()[0]
    runner = KnowledgeTaskRunner()
    service = _NoBootstrapKnowledgeService(
        store=KnowledgeStore(sqlite_db_path=tmp_path / "carbonrag.sqlite3"),
        session_service=_FakeSessionService(),
    )
    monkeypatch.setattr("app.knowledge.service.get_knowledge_service", lambda: service)
    monkeypatch.setattr("app.knowledge.runner.get_knowledge_task_runner", lambda: runner)
    monkeypatch.setattr("app.knowledge.get_knowledge_service", lambda: service)
    get_public_policy_retriever.cache_clear()

    published = scheduler.publish_candidate(candidate_id=candidate.candidate_id, reviewed_by_user_id=None)
    processed = runner.run_once()

    assert processed
    item = service.store.get_item(published.knowledge_item_id or "")
    assert item is not None
    assert item.source_type == "public_policy_web"
    assert item.index_status == "indexed"
    chunks = service.list_chunks(knowledge_item_id=item.knowledge_item_id)
    assert chunks
    assert chunks[0].source_type == "public_policy"


def _build_scheduler(tmp_path, *, provider=None, settings: Settings | None = None, settings_overrides: dict | None = None) -> PolicyCrawlerScheduler:
    db_path = tmp_path / "carbonrag.sqlite3"
    public_dir = tmp_path / "public"
    resolved_settings = settings or _settings(tmp_path, settings_overrides)
    return PolicyCrawlerScheduler(
        store=PolicyCrawlerStore(sqlite_db_path=db_path),
        provider=provider,
        settings=resolved_settings,
        candidate_dir=public_dir / "policy_crawl_candidates",
    )


def _settings(tmp_path, overrides: dict | None = None) -> Settings:
    public_dir = tmp_path / "public"
    return Settings(
        public_data_dir=str(public_dir),
        rag_policy_live_crawler_scheduled_enabled=False,
        rag_policy_live_crawler_initial_delay_seconds=0.01,
        rag_policy_live_crawler_interval_seconds=60,
        rag_policy_live_crawler_failure_backoff_seconds=5,
        **(overrides or {}),
    )


def _official_document(url: str) -> CrawledDocument:
    return CrawledDocument(
        url=url,
        title="Official carbon policy sample",
        content="""
        <html>
          <head><title>Official carbon policy sample</title></head>
          <body>
            <h1>Official carbon policy sample</h1>
            <p>Issued at 2026-05-08 by an official policy source.</p>
            <p>Article 1 promotes carbon accounting, energy saving, and low-carbon transition.</p>
          </body>
        </html>
        """,
        content_type="text/html",
        source_name="Official policy source",
    )


class _NoBootstrapKnowledgeService(KnowledgeService):
    def bootstrap_shared_library(self):  # type: ignore[override]
        return []


class _FakeSessionService:
    knowledge_service = None
