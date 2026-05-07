from __future__ import annotations

import functools
import threading
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from app.knowledge.policy_ingestion import (
    CrawledDocument,
    FakeCrawlerProvider,
    OfdrwConverterAdapter,
    PolicyCrawlRequest,
    PolicyDocumentParser,
    ScrapyCrawlerProvider,
    build_policy_chunks,
    build_policy_web_knowledge_item,
    is_allowed_policy_url,
    normalize_policy_governance_metadata,
    stage_crawled_document,
    validate_policy_crawl_request,
)
from app.knowledge.schemas import KnowledgeTask
from app.knowledge.runner import KnowledgeTaskRunner
from app.knowledge.service import KnowledgeService
from app.knowledge.store import KnowledgeStore
from app.rag.contracts import ParsedDocument
from app.rag.workflow import build_policy_ingest_workflow
from app.retrieval.public_retriever import get_public_policy_retriever


def test_policy_crawler_allowlist_accepts_official_domains() -> None:
    assert is_allowed_policy_url("https://www.gov.cn/zhengce/content/example.htm")
    assert is_allowed_policy_url("https://fgw.beijing.gov.cn/zwxx/tzgg/example.html")
    assert not is_allowed_policy_url("https://example.com/policy.html")


def test_policy_crawl_request_rejects_non_official_domain() -> None:
    request = PolicyCrawlRequest(start_urls=["https://example.com/policy.html"])

    try:
        validate_policy_crawl_request(request)
    except ValueError as exc:
        assert "outside the official allowlist" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("non-official policy URL should be rejected")


def test_fake_crawler_returns_offline_documents() -> None:
    document = CrawledDocument(
        url="https://www.gov.cn/zhengce/content/sample.htm",
        title="政策样例",
        content="<html><body><p>碳达峰行动方案</p></body></html>",
    )
    provider = FakeCrawlerProvider(documents=[document])
    request = PolicyCrawlRequest(start_urls=[document.url])

    result = provider.crawl(request)

    assert result.status == "succeeded"
    assert result.documents == [document]
    assert result.metadata["offline"] is True


def test_scrapy_provider_is_disabled_or_unavailable_without_required_runtime(monkeypatch) -> None:
    request = PolicyCrawlRequest(start_urls=["https://www.gov.cn/zhengce/content/sample.htm"])
    disabled = ScrapyCrawlerProvider(enabled=False)

    assert disabled.crawl(request).status == "disabled"

    monkeypatch.setattr("app.knowledge.policy_ingestion.importlib.util.find_spec", lambda name: None)
    unavailable = ScrapyCrawlerProvider(enabled=True)

    result = unavailable.crawl(request)
    assert result.status == "unavailable"
    assert "Scrapy is not installed." in result.errors


def test_scrapy_provider_can_crawl_local_allowed_pages(tmp_path) -> None:
    pytest.importorskip("scrapy")
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    (site_dir / "index.html").write_text(
        "<html><head><title>政策目录</title></head><body><a href='/detail.html'>详情</a><p>政策目录</p></body></html>",
        encoding="utf-8",
    )
    (site_dir / "detail.html").write_text(
        "<html><head><title>政策详情</title></head><body><p>第一条 推动碳达峰行动。</p></body></html>",
        encoding="utf-8",
    )
    with _local_http_server(site_dir) as base_url:
        request = PolicyCrawlRequest(
            start_urls=[f"{base_url}/index.html"],
            allowed_domains=["127.0.0.1"],
            max_depth=1,
            max_pages=3,
            obey_robots=False,
            download_delay_seconds=0,
            timeout_seconds=30,
        )
        provider = ScrapyCrawlerProvider(enabled=True)

        result = provider.crawl(request)

    assert result.status == "succeeded"
    urls = {document.url for document in result.documents}
    assert any(url.endswith("/index.html") for url in urls)
    assert any(url.endswith("/detail.html") for url in urls)
    assert any("推动碳达峰行动" in document.content for document in result.documents)


def test_html_policy_parser_extracts_readable_text(tmp_path) -> None:
    source = tmp_path / "policy.html"
    source.write_text(
        """
        <html>
          <head><title>2030年前碳达峰行动方案</title><script>ignored()</script></head>
          <body><h1>2030年前碳达峰行动方案</h1><p>第一条 推动能源绿色低碳转型。</p></body>
        </html>
        """,
        encoding="utf-8",
    )
    parser = PolicyDocumentParser(parser_registry=_FakeParserRegistry())

    parsed = parser.parse_staged_document(
        path=source,
        content_type="text/html",
        source_url="https://www.gov.cn/zhengce/content/sample.htm",
    )

    assert parsed.parser_name == "carbonrag-html"
    assert parsed.source_type == "public_policy_web"
    assert "2030年前碳达峰行动方案" in parsed.text
    assert "ignored" not in parsed.text
    assert parsed.blocks
    assert parsed.metadata["parse_success"] is True


def test_html_policy_parser_filters_boilerplate_and_extracts_metadata(tmp_path) -> None:
    source = tmp_path / "policy.html"
    source.write_text(
        """
        <html>
          <head><title>北京市绿色低碳政策</title><style>.hidden{}</style></head>
          <body>
            <nav>首页 政策公开 站点地图</nav>
            <div class="breadcrumb">当前位置：首页 > 政策</div>
            <aside class="sidebar">相关链接 不应进入正文</aside>
            <main>
              <h1>北京市绿色低碳政策</h1>
              <p>来源：北京市发展和改革委员会 发布时间：2026年5月2日</p>
              <p>第一条 推动重点行业开展碳核算和节能改造。</p>
              <p>第二条 建立绿色低碳项目清单。</p>
            </main>
            <div class="share">分享到微信</div>
            <footer>版权所有</footer>
          </body>
        </html>
        """,
        encoding="utf-8",
    )
    parser = PolicyDocumentParser(parser_registry=_FakeParserRegistry())

    parsed = parser.parse_staged_document(
        path=source,
        content_type="text/html",
        source_url="https://fgw.beijing.gov.cn/zwxx/tzgg/policy.html",
    )

    assert "推动重点行业开展碳核算" in parsed.text
    assert "首页 政策公开" not in parsed.text
    assert "当前位置" not in parsed.text
    assert "相关链接" not in parsed.text
    assert "分享到微信" not in parsed.text
    assert "版权所有" not in parsed.text
    assert parsed.metadata["publication_date"] == "2026-05-02"
    assert parsed.metadata["source_label"] == "北京市发展和改革委员会"
    assert parsed.metadata["issuing_authority"] == "北京市发展和改革委员会"
    assert parsed.metadata["parser_chain"] == ["carbonrag-html:success"]


def test_pdf_policy_parser_routes_to_registry(tmp_path) -> None:
    source = tmp_path / "policy.pdf"
    source.write_text("mock pdf", encoding="utf-8")
    registry = _FakeParserRegistry()
    parser = PolicyDocumentParser(parser_registry=registry)

    parsed = parser.parse_staged_document(
        path=source,
        content_type="application/pdf",
        source_url="https://www.gov.cn/zhengce/content/policy.pdf",
        title="PDF政策",
    )

    assert registry.calls == [(source, "application/pdf")]
    assert parsed.text == "PDF policy text"
    assert parsed.source_type == "public_policy_web"
    assert parsed.source_uri == "https://www.gov.cn/zhengce/content/policy.pdf"
    assert parsed.title == "PDF政策"
    assert parsed.visibility == "public"
    assert parsed.metadata["source_url"] == "https://www.gov.cn/zhengce/content/policy.pdf"
    assert parsed.metadata["original_source_uri"] == str(source)
    assert parsed.metadata["policy_content_type"] == "application/pdf"
    assert parsed.metadata["parser_chain"] == ["fake-registry:success"]


def test_ofd_policy_parser_fails_safely_when_converter_missing(monkeypatch, tmp_path) -> None:
    source = tmp_path / "policy.ofd"
    source.write_text("mock ofd", encoding="utf-8")
    monkeypatch.setattr("app.knowledge.policy_ingestion.importlib.util.find_spec", lambda name: None)
    parser = PolicyDocumentParser(parser_registry=_FakeParserRegistry(), ofd_converter=OfdrwConverterAdapter())

    parsed = parser.parse_staged_document(path=source, content_type="application/ofd")

    assert parsed.text == ""
    assert parsed.metadata["parse_success"] is False
    assert parsed.metadata["converter_name"] == "ofdrw"
    assert parsed.metadata["converter_available"] is False


def test_ofd_policy_parser_routes_converted_document_to_registry(tmp_path) -> None:
    source = tmp_path / "policy.ofd"
    converted = tmp_path / "policy.pdf"
    source.write_text("mock ofd", encoding="utf-8")
    converted.write_text("mock pdf", encoding="utf-8")
    registry = _FakeParserRegistry()
    parser = PolicyDocumentParser(
        parser_registry=registry,
        ofd_converter=OfdrwConverterAdapter(converter=_FakeOfdConverter(converted)),
    )

    parsed = parser.parse_staged_document(
        path=source,
        content_type="application/ofd",
        source_url="https://www.gov.cn/zhengce/content/policy.ofd",
    )

    assert registry.calls == [(converted, "application/pdf")]
    assert parsed.source_type == "public_policy_web"
    assert parsed.source_uri == "https://www.gov.cn/zhengce/content/policy.ofd"
    assert parsed.metadata["source_url"] == "https://www.gov.cn/zhengce/content/policy.ofd"
    assert parsed.metadata["original_source_uri"] == str(converted)
    assert parsed.metadata["policy_content_type"] == "application/pdf"
    assert parsed.metadata["parser_chain"] == ["fake-registry:success"]
    assert parsed.metadata["converted_from"] == "ofd"
    assert parsed.metadata["converter_name"] == "ofdrw"


def test_policy_metadata_and_chunks_are_serializable_and_public_compatible(tmp_path) -> None:
    crawled = CrawledDocument(
        url="https://www.gov.cn/zhengce/content/sample.htm",
        title="2030年前碳达峰行动方案",
        content="<html><body>发改气候〔2021〕123号\n2021年10月24日\n第一条 推动碳达峰和碳核算。</body></html>",
    )
    staged = stage_crawled_document(crawled, staging_dir=tmp_path / "staging")
    item = build_policy_web_knowledge_item(staged=staged, created_at=datetime.now(timezone.utc))
    parser = PolicyDocumentParser(parser_registry=_FakeParserRegistry())
    parsed = parser.parse_staged_document(path=staged.storage_path, content_type=staged.mime_type, source_url=crawled.url)
    metadata = normalize_policy_governance_metadata(parsed=parsed, crawled=crawled)
    chunks = build_policy_chunks(item=item, parsed=parsed, policy_metadata=metadata, created_at=datetime.now(timezone.utc))

    assert item.source_type == "public_policy_web"
    assert chunks
    assert all(chunk.source_type == "public_policy" for chunk in chunks)
    assert chunks[0].metadata["original_source_type"] == "public_policy_web"
    assert chunks[0].metadata["source_url"] == crawled.url
    assert chunks[0].metadata["clause_anchors"]
    assert "碳达峰" in chunks[0].metadata["topic_tags"]


def test_policy_chunk_metadata_persists_in_knowledge_store(tmp_path) -> None:
    db_path = tmp_path / "carbonrag.sqlite3"
    store = KnowledgeStore(sqlite_db_path=db_path)
    crawled = CrawledDocument(
        url="https://www.gov.cn/zhengce/content/sample.htm",
        title="政策入库样例",
        content="<html><body><p>第一条 推动绿色低碳发展。</p></body></html>",
    )
    staged = stage_crawled_document(crawled, staging_dir=tmp_path / "staging")
    item = build_policy_web_knowledge_item(staged=staged, created_at=datetime.now(timezone.utc))
    parsed = PolicyDocumentParser(parser_registry=_FakeParserRegistry()).parse_staged_document(
        path=staged.storage_path,
        content_type=staged.mime_type,
        source_url=crawled.url,
    )
    metadata = normalize_policy_governance_metadata(parsed=parsed, crawled=crawled)
    chunks = build_policy_chunks(item=item, parsed=parsed, policy_metadata=metadata, created_at=datetime.now(timezone.utc))

    store.upsert_item(item)
    store.replace_chunks(knowledge_item_id=item.knowledge_item_id, chunks=chunks, indexed_at=datetime.now(timezone.utc))
    reloaded = store.list_chunks(item.knowledge_item_id)

    assert reloaded
    assert reloaded[0].metadata["original_source_type"] == "public_policy_web"
    assert reloaded[0].source_type == "public_policy"


def test_policy_workflow_and_task_types_are_available() -> None:
    workflow = build_policy_ingest_workflow(knowledge_item_id="policy-web-001")
    task = KnowledgeTask(
        task_id="task-policy-001",
        knowledge_item_id="policy-web-001",
        task_type="crawl_ingest",
        status="queued",
        created_at=datetime.now(timezone.utc),
    )

    assert workflow.workflow_type == "policy_ingest"
    assert [node.node_id for node in workflow.nodes] == [
        "crawl_source",
        "stage_crawled_document",
        "parse_document",
        "normalize_policy_metadata",
        "build_chunks",
        "upsert_vector_index",
        "index_completed",
    ]
    assert task.task_type == "crawl_ingest"


def test_crawled_policy_document_can_be_indexed_and_retrieved(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "carbonrag.sqlite3"
    store = KnowledgeStore(sqlite_db_path=db_path)
    runner = KnowledgeTaskRunner()
    service = _NoBootstrapKnowledgeService(store=store, session_service=_FakeSessionService())
    monkeypatch.setattr("app.knowledge.runner.get_knowledge_task_runner", lambda: runner)
    monkeypatch.setattr("app.knowledge.service.get_knowledge_service", lambda: service)
    monkeypatch.setattr("app.knowledge.get_knowledge_service", lambda: service)
    get_public_policy_retriever.cache_clear()

    crawled = CrawledDocument(
        url="https://www.gov.cn/zhengce/content/crawl-index.htm",
        title="低碳韧性校园建设行动方案",
        content="""
        <html><head><title>低碳韧性校园建设行动方案</title></head>
        <body>
          <h1>低碳韧性校园建设行动方案</h1>
          <p>国办发〔2026〕8号 2026年5月1日</p>
          <p>第一条 推动低碳韧性校园建设，完善碳核算、节能改造和绿色低碳教育。</p>
          <p>第二条 建立校园能源排放数据台账，鼓励公开透明的政策评估。</p>
        </body></html>
        """,
    )

    task = service.create_policy_item_from_crawled_document(
        crawled_document=crawled,
        staging_dir=tmp_path / "staging",
    )
    processed = runner.run_once()

    assert task.task_id in processed
    refreshed_task = store.get_task(task.task_id)
    assert refreshed_task is not None
    assert refreshed_task.status == "succeeded"
    item = store.get_item(task.knowledge_item_id or "")
    assert item is not None
    assert item.source_type == "public_policy_web"
    assert item.parse_status == "parsed"
    assert item.ingest_status == "ingested"
    assert item.index_status == "indexed"

    workflow = store.get_latest_workflow_run(knowledge_item_id=item.knowledge_item_id)
    assert workflow is not None
    assert workflow.workflow_type == "policy_ingest"
    assert workflow.status == "completed"
    assert workflow.current_node == "index_completed"

    chunks = store.list_chunks(item.knowledge_item_id)
    assert chunks
    assert chunks[0].source_type == "public_policy"
    assert chunks[0].metadata["original_source_type"] == "public_policy_web"
    assert chunks[0].metadata["source_url"] == crawled.url
    assert chunks[0].metadata["publication_date"] == "2026-05-01"
    assert chunks[0].metadata["clause_anchors"]
    assert chunks[0].metadata["parser_name"] == "carbonrag-html"
    assert chunks[0].metadata["metadata"]["parser_chain"] == ["carbonrag-html:success"]

    get_public_policy_retriever.cache_clear()
    result = get_public_policy_retriever().search(question="低碳韧性校园 碳核算", top_k=5)

    assert any(hit.knowledge_item_id == item.knowledge_item_id for hit in result.hits)


class _FakeParserRegistry:
    def __init__(self) -> None:
        self.calls: list[tuple[Path, str]] = []

    def parse(self, file_path, *, content_type=None):
        path = Path(file_path)
        self.calls.append((path, content_type))
        return ParsedDocument(
            document_id="fake-pdf-document",
            source_uri=str(path),
            source_type="public_policy_web",
            title=path.name,
            text="PDF policy text",
            mime_type=content_type,
            source_path=str(path),
            parser_name="fake-registry",
            quality_score=0.9,
            visibility="public",
            metadata={"parser_name": "fake-registry", "parse_success": True},
        )


class _FakeOfdConverter:
    def __init__(self, converted_path: Path) -> None:
        self.converted_path = converted_path

    def convert(self, file_path: str):
        assert file_path.endswith(".ofd")
        return self.converted_path


class _LocalHttpServer:
    def __init__(self, directory: Path) -> None:
        handler = functools.partial(SimpleHTTPRequestHandler, directory=str(directory))
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> str:
        self.thread.start()
        host, port = self.server.server_address
        return f"http://{host}:{port}"

    def __exit__(self, exc_type, exc, tb) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def _local_http_server(directory: Path) -> _LocalHttpServer:
    return _LocalHttpServer(directory)


class _NoBootstrapKnowledgeService(KnowledgeService):
    def bootstrap_shared_library(self):  # type: ignore[override]
        return []


class _FakeSessionService:
    knowledge_service = None
