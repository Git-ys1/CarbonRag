from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.ai_runtime.providers.base import BaseChatProvider, ChatCompletionResult, ProviderDescriptor
from app.main import app
from app.rag.kb.models import KnowledgeBaseCreate, RagChunk, RagDocumentCreate
from app.rag.kb.storage import RagKnowledgeStore
from app.rag.retrieval import dense as dense_module
from app.rag.retrieval.sparse import sparse_search_with_trace
from app.rag.spine import RagSpineService
from app.rag.vector_backend import milvus_store
from app.rag.vector_backend.milvus_store import MilvusVectorStoreAdapter
from tests.test_helpers import patch_test_auth_service, register_and_login

client = TestClient(app)


class FakeChatProvider(BaseChatProvider):
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def describe(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            name="fake-chat",
            provider_type="test",
            mode="chat",
            default_model="fake-grounded-model",
        )

    def generate_response(self, *, system_prompt: str, user_input: str) -> ChatCompletionResult:
        self.calls.append({"system_prompt": system_prompt, "user_input": user_input})
        return ChatCompletionResult(content="双碳目标包括碳达峰和碳中和。", metadata={"fake": True})


class FakeSettingsService:
    def __init__(self, chat_provider: BaseChatProvider) -> None:
        self.chat_provider = chat_provider

    def build_chat_provider(self, **kwargs):  # noqa: ANN003
        return SimpleNamespace(provider_ref="test:fake-provider"), self.chat_provider


def build_rag_service(tmp_path):
    return RagSpineService(
        store=RagKnowledgeStore(sqlite_db_path=tmp_path / "carbonrag.sqlite3"),
        chat_provider=FakeChatProvider(),
    )


def test_create_document_recreates_missing_shadow_owner(tmp_path) -> None:
    store = RagKnowledgeStore(sqlite_db_path=tmp_path / "carbonrag.sqlite3")
    owner_user_id = "system-policy-crawler"
    kb = store.create_kb(
        owner_user_id=owner_user_id,
        payload=KnowledgeBaseCreate(name="自动爬虫知识库", visibility="shared"),
    )
    store._execute("DELETE FROM users WHERE user_id = {p}", [owner_user_id])

    doc = store.create_document(
        owner_user_id=owner_user_id,
        kb_id=kb.kb_id,
        payload={"title": "政策文档", "text": "服务业扩能提质与节能环保服务。"},
    )

    assert doc.owner_user_id == owner_user_id
    assert store._select("SELECT user_id FROM users WHERE user_id = {p}", [owner_user_id])


def test_kb_document_status_and_test_qa(monkeypatch, tmp_path) -> None:
    service = build_rag_service(tmp_path)
    monkeypatch.setattr("app.rag.spine.get_settings", lambda: SimpleNamespace(rag_vector_backend="memory"))
    monkeypatch.setattr("app.api.v1.endpoints.kb.get_rag_spine_service", lambda: service)
    monkeypatch.setattr("app.api.v1.endpoints.rag.get_rag_spine_service", lambda: service)
    monkeypatch.setattr("app.api.v1.endpoints.rag.get_settings_service", lambda: FakeSettingsService(service.chat_provider))
    patch_test_auth_service(monkeypatch, db_path=tmp_path / "carbonrag.sqlite3")

    register_and_login(client, prefix="rag-spine")
    kb_response = client.post("/api/v1/kb", json={"name": "RAG-Pro 测试库"})
    assert kb_response.status_code == 200, kb_response.text
    kb_id = kb_response.json()["kb_id"]

    doc_response = client.post(
        f"/api/v1/kb/{kb_id}/documents",
        json={
            "title": "双碳目标测试文档",
            "text": "双碳目标包括碳达峰和碳中和。企业需要建立能源数据台账，并追踪用电量、燃气量和排放因子。",
        },
    )
    assert doc_response.status_code == 200, doc_response.text
    doc_id = doc_response.json()["doc_id"]

    assert client.post(f"/api/v1/kb/{kb_id}/documents/{doc_id}/parse").json()["status"] == "parsed"
    assert client.post(f"/api/v1/kb/{kb_id}/documents/{doc_id}/chunk").json()["status"] == "chunked"
    indexed = client.post(f"/api/v1/kb/{kb_id}/documents/{doc_id}/index").json()
    assert indexed["status"] == "indexed"
    assert indexed["indexed_chunk_count"] >= 1

    search = client.post(
        "/api/v1/rag/search",
        json={"kb_id": kb_id, "query": "企业如何追踪双碳目标？", "mode": "hybrid", "top_k": 3},
    )
    assert search.status_code == 200, search.text
    payload = search.json()
    assert payload["hits"]
    assert payload["trace"]["sparse_count"] >= 1
    assert payload["trace"]["merged_count"] >= 1
    assert payload["trace"]["vector_backend"] == "memory"

    qa = client.post(
        "/api/v1/rag/test-qa",
        json={"kb_id": kb_id, "query": "双碳目标包括什么？", "mode": "hybrid", "top_k": 3},
    )
    assert qa.status_code == 200, qa.text
    qa_payload = qa.json()
    assert qa_payload["run_id"]
    assert qa_payload["answer_mode"] == "llm_grounded"
    assert qa_payload["provider_name"] == "fake-chat"
    assert qa_payload["selected_chunks"]
    assert "双碳" in qa_payload["answer"]


def test_kb_defaults_upload_status_answer_and_eval(monkeypatch, tmp_path) -> None:
    service = build_rag_service(tmp_path)
    monkeypatch.setattr("app.rag.spine.get_settings", lambda: SimpleNamespace(rag_vector_backend="memory"))
    monkeypatch.setattr("app.api.v1.endpoints.kb.get_rag_spine_service", lambda: service)
    monkeypatch.setattr("app.api.v1.endpoints.rag.get_rag_spine_service", lambda: service)
    monkeypatch.setattr("app.api.v1.endpoints.rag.get_settings_service", lambda: FakeSettingsService(service.chat_provider))
    patch_test_auth_service(monkeypatch, db_path=tmp_path / "carbonrag.sqlite3")

    register_and_login(client, prefix="rag-parity")
    kb_response = client.post("/api/v1/kb", json={"name": "青木验收库"})
    assert kb_response.status_code == 200, kb_response.text
    kb_payload = kb_response.json()
    assert kb_payload["embedding_model"] == "BAAI/bge-m3"
    assert kb_payload["chunk_size"] == 512
    assert kb_payload["chunk_overlap"] == 64
    assert kb_payload["rerank_top_n"] == 5
    assert kb_payload["retrieval_top_k"] == 20
    kb_id = kb_payload["kb_id"]

    upload_response = client.post(
        f"/api/v1/kb/{kb_id}/documents/upload",
        files={
            "file": (
                "qingmu.md",
                "# 青木制造\n\n青木制造合计外购电力为 217,650 kWh。绿色电力凭证编号为 GEC-QM-2025-02-0007。".encode("utf-8"),
                "text/markdown",
            )
        },
    )
    assert upload_response.status_code == 200, upload_response.text
    doc_payload = upload_response.json()
    assert doc_payload["filename"] == "qingmu.md"
    assert doc_payload["file_type"] == "md"
    assert doc_payload["file_size"] > 0
    assert doc_payload["file_path"]
    assert doc_payload["parse_progress"] == 0
    doc_id = doc_payload["doc_id"]

    status = client.get(f"/api/v1/kb/{kb_id}/documents/{doc_id}/status")
    assert status.status_code == 200, status.text
    assert status.json()["doc_id"] == doc_id

    assert client.post(f"/api/v1/kb/{kb_id}/documents/{doc_id}/parse").json()["parse_progress"] == 100
    assert client.post(f"/api/v1/kb/{kb_id}/documents/{doc_id}/chunk").json()["chunk_progress"] == 100
    indexed = client.post(f"/api/v1/kb/{kb_id}/documents/{doc_id}/index").json()
    assert indexed["index_status"] == "indexed"

    answer = client.post(
        "/api/v1/rag/answer",
        json={"kb_id": kb_id, "query": "青木制造合计外购电力是多少？", "mode": "hybrid", "top_k": 3},
    )
    assert answer.status_code == 200, answer.text
    answer_payload = answer.json()
    assert answer_payload["answer_mode"] == "llm_grounded"
    assert answer_payload["provider_name"] == "fake-chat"
    assert answer_payload["selected_chunks"]
    assert answer_payload["citations"]
    assert answer_payload["retrieval_trace"]["kb_id"] == kb_id

    eval_response = client.post(
        "/api/v1/rag/eval/run",
        json={
            "kb_id": kb_id,
            "mode": "hybrid",
            "top_k": 3,
            "cases": [
                {
                    "case_id": "qingmu-electricity-total",
                    "question": "青木制造合计外购电力是多少？",
                    "expected_chunk_keywords": ["217,650", "外购电力"],
                }
            ],
        },
    )
    assert eval_response.status_code == 200, eval_response.text
    eval_payload = eval_response.json()
    assert eval_payload["metrics"]["case_count"] == 1
    assert "hit_at_3" in eval_payload["metrics"]
    assert "answer_mode_rate" in eval_payload["metrics"]
    assert eval_payload["cases"][0]["case_id"] == "qingmu-electricity-total"


def test_kb_document_pipeline_runs_all_stages_and_reports_smoke(monkeypatch, tmp_path) -> None:
    service = build_rag_service(tmp_path)
    monkeypatch.setattr("app.rag.spine.get_settings", lambda: SimpleNamespace(rag_vector_backend="memory"))
    monkeypatch.setattr("app.rag.spine._load_pipeline_default_eval_cases", lambda *, kb_id: [])
    monkeypatch.setattr("app.api.v1.endpoints.kb.get_rag_spine_service", lambda: service)
    patch_test_auth_service(monkeypatch, db_path=tmp_path / "carbonrag.sqlite3")

    register_and_login(client, prefix="rag-pipeline")
    kb_id = client.post("/api/v1/kb", json={"name": "Pipeline 测试库"}).json()["kb_id"]
    doc_id = client.post(
        f"/api/v1/kb/{kb_id}/documents",
        json={"title": "Pipeline 文档", "text": "Pipeline 文档包含外购电力 217,650 kWh，可用于检索冒烟。"},
    ).json()["doc_id"]

    response = client.post(f"/api/v1/kb/{kb_id}/documents/{doc_id}/run-pipeline")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["parse_status"] == "parsed"
    assert payload["chunk_status"] == "chunked"
    assert payload["index_status"] == "indexed"
    assert payload["chunk_count"] >= 1
    assert payload["indexed_chunk_count"] >= 1
    assert payload["search_smoke_passed"] is True
    assert payload["eval_passed"] is None
    assert payload["failed_stage"] is None
    assert payload["pipeline_mode"] == "quick"
    assert "eval_not_configured" not in payload["warnings"]
    assert payload["timing_trace"]["total_ms"] is not None

    acceptance = client.post(
        f"/api/v1/kb/{kb_id}/documents/{doc_id}/run-pipeline",
        json={"pipeline_mode": "acceptance"},
    )
    assert acceptance.status_code == 200, acceptance.text
    acceptance_payload = acceptance.json()
    assert acceptance_payload["pipeline_mode"] == "acceptance"
    assert acceptance_payload["eval_passed"] is None
    assert "eval_not_configured" in acceptance_payload["warnings"]


def test_kb_document_pipeline_batch_summarizes_pending_documents(monkeypatch, tmp_path) -> None:
    service = build_rag_service(tmp_path)
    monkeypatch.setattr("app.rag.spine.get_settings", lambda: SimpleNamespace(rag_vector_backend="memory"))
    monkeypatch.setattr("app.rag.spine._load_pipeline_default_eval_cases", lambda *, kb_id: [])
    monkeypatch.setattr("app.api.v1.endpoints.kb.get_rag_spine_service", lambda: service)
    patch_test_auth_service(monkeypatch, db_path=tmp_path / "carbonrag.sqlite3")

    register_and_login(client, prefix="rag-pipeline-batch")
    kb_id = client.post("/api/v1/kb", json={"name": "Batch 测试库"}).json()["kb_id"]
    for index in range(2):
        client.post(
            f"/api/v1/kb/{kb_id}/documents",
            json={"title": f"Batch 文档 {index}", "text": f"Batch 文档 {index} 包含可检索内容。"},
        )

    response = client.post(f"/api/v1/kb/{kb_id}/documents/run-pipeline-batch", json={})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total_count"] == 2
    assert payload["succeeded_count"] == 2
    assert payload["failed_count"] == 0
    assert all(item["search_smoke_passed"] for item in payload["results"])
    assert all(item["pipeline_mode"] == "quick" for item in payload["results"])


def test_kb_document_pipeline_reports_index_failure(monkeypatch, tmp_path) -> None:
    service = build_rag_service(tmp_path)
    monkeypatch.setattr("app.rag.spine.get_settings", lambda: SimpleNamespace(rag_vector_backend="memory"))
    monkeypatch.setattr("app.rag.spine._load_pipeline_default_eval_cases", lambda *, kb_id: [])
    patch_test_auth_service(monkeypatch, db_path=tmp_path / "carbonrag.sqlite3")

    owner_user_id = register_and_login(client, prefix="rag-pipeline-fail")["user_id"]
    kb = service.create_kb(owner_user_id=owner_user_id, payload=KnowledgeBaseCreate(name="Fail 库"))
    doc = service.create_document(
        owner_user_id=owner_user_id,
        kb_id=kb.kb_id,
        payload=RagDocumentCreate(title="Fail 文档", text="需要触发 index 失败。"),
    )

    def fail_index(*, owner_user_id: str, kb_id: str, doc_id: str):  # noqa: ARG001
        current = service.get_document(owner_user_id=owner_user_id, kb_id=kb_id, doc_id=doc_id)
        return service.store._mark_document(
            doc=current,
            parse_status="parsed",
            chunk_status="chunked",
            index_status="failed",
            error_message="forced index failure",
            error_stage="index",
        )

    monkeypatch.setattr(service, "index_document", fail_index)
    result = service.run_document_pipeline(owner_user_id=owner_user_id, kb_id=kb.kb_id, doc_id=doc.doc_id)
    assert result.failed_stage == "index"
    assert result.index_status == "failed"
    assert result.error_message == "forced index failure"


def test_sparse_search_reuses_kb_corpus_cache() -> None:
    now = datetime.now(timezone.utc)
    chunks = [
        RagChunk(
            rag_chunk_id="chunk-1",
            kb_id="kb-cache",
            doc_id="doc-1",
            chunk_index=0,
            text="青木制造外购电力 217650 kWh",
            created_at=now,
            updated_at=now,
        )
    ]

    first = sparse_search_with_trace(query="外购电力", chunks=chunks, top_k=3)
    second = sparse_search_with_trace(query="外购电力", chunks=chunks, top_k=3)

    assert first.cache_hit is False
    assert second.cache_hit is True
    assert second.loaded_chunk_count == 1


def test_rag_vector_store_adapter_reused(monkeypatch) -> None:
    dense_module.reset_vector_store_cache()
    monkeypatch.setattr(
        dense_module,
        "get_settings",
        lambda: SimpleNamespace(
            rag_milvus_uri="http://127.0.0.1:19530",
            rag_chroma_persist_dir="./data/outputs/chroma",
        ),
    )

    first = dense_module.get_vector_store("milvus")
    second = dense_module.get_vector_store("milvus_standalone")
    third = dense_module.get_vector_store("milvus_lite")

    assert first is second
    assert first is third


def test_milvus_client_reused_between_searches(monkeypatch) -> None:
    class FakeMilvusClient:
        init_count = 0

        def __init__(self, uri: str) -> None:
            self.uri = uri
            FakeMilvusClient.init_count += 1

        def has_collection(self, collection_name: str) -> bool:  # noqa: ARG002
            return True

        def search(self, **kwargs):  # noqa: ANN003
            return [[{"entity": {"chunk_id": "chunk-1"}, "distance": 0.9}]]

    monkeypatch.setitem(__import__("sys").modules, "pymilvus", SimpleNamespace(MilvusClient=FakeMilvusClient))
    monkeypatch.setattr(
        milvus_store,
        "get_settings",
        lambda: SimpleNamespace(
            rag_milvus_uri="http://127.0.0.1:19530",
            rag_milvus_collection_prefix="carbonrag",
        ),
    )
    monkeypatch.setattr(
        milvus_store,
        "resolve_vector_runtime",
        lambda: SimpleNamespace(vector_runtime="milvus_standalone", degraded=False, warnings=[]),
    )
    monkeypatch.setattr(milvus_store, "embed_query", lambda query: ([0.1] * 1024, {}))
    milvus_store._CLIENT_CACHE.clear()
    milvus_store._COLLECTION_EXISTS_CACHE.clear()
    now = datetime.now(timezone.utc)
    chunks = [
        RagChunk(
            rag_chunk_id="chunk-1",
            kb_id="kb-milvus",
            doc_id="doc-1",
            chunk_index=0,
            text="青木制造外购电力 217650 kWh",
            created_at=now,
            updated_at=now,
        )
    ]

    adapter = MilvusVectorStoreAdapter()
    first = adapter.search(query="外购电力", chunks=chunks, top_k=3)
    second = adapter.search(query="外购电力", chunks=chunks, top_k=3)

    assert first.client_init_count == 1
    assert second.client_init_count == 0
    assert FakeMilvusClient.init_count == 1


def test_warm_search_does_not_reinitialize_milvus_client(monkeypatch) -> None:
    class FakeMilvusClient:
        init_count = 0

        def __init__(self, uri: str) -> None:
            self.uri = uri
            FakeMilvusClient.init_count += 1

        def has_collection(self, collection_name: str) -> bool:  # noqa: ARG002
            return True

        def search(self, **kwargs):  # noqa: ANN003
            return [[{"entity": {"chunk_id": "chunk-1"}, "distance": 0.9}]]

    settings = SimpleNamespace(
        rag_milvus_uri="http://127.0.0.1:19530",
        rag_milvus_collection_prefix="carbonrag",
        rag_chroma_persist_dir="./data/outputs/chroma",
    )
    monkeypatch.setitem(__import__("sys").modules, "pymilvus", SimpleNamespace(MilvusClient=FakeMilvusClient))
    monkeypatch.setattr(dense_module, "get_settings", lambda: settings)
    monkeypatch.setattr(milvus_store, "get_settings", lambda: settings)
    monkeypatch.setattr(
        milvus_store,
        "resolve_vector_runtime",
        lambda: SimpleNamespace(vector_runtime="milvus_standalone", degraded=False, warnings=[]),
    )
    monkeypatch.setattr(milvus_store, "embed_query", lambda query: ([0.1] * 1024, {}))
    dense_module.reset_vector_store_cache()
    milvus_store._CLIENT_CACHE.clear()
    milvus_store._COLLECTION_EXISTS_CACHE.clear()
    now = datetime.now(timezone.utc)
    chunks = [
        RagChunk(
            rag_chunk_id="chunk-1",
            kb_id="kb-milvus",
            doc_id="doc-1",
            chunk_index=0,
            text="青木制造外购电力 217650 kWh",
            created_at=now,
            updated_at=now,
        )
    ]

    first = dense_module.dense_search(query="外购电力", chunks=chunks, top_k=3, backend="milvus")
    second = dense_module.dense_search(query="外购电力", chunks=chunks, top_k=3, backend="milvus")

    assert first.client_init_count == 1
    assert second.client_init_count == 0
    assert FakeMilvusClient.init_count == 1


def test_kb_user_isolation(monkeypatch, tmp_path) -> None:
    service = build_rag_service(tmp_path)
    monkeypatch.setattr("app.api.v1.endpoints.kb.get_rag_spine_service", lambda: service)
    patch_test_auth_service(monkeypatch, db_path=tmp_path / "carbonrag.sqlite3")

    register_and_login(client, prefix="rag-owner")
    kb_id = client.post("/api/v1/kb", json={"name": "私有库"}).json()["kb_id"]

    register_and_login(client, prefix="rag-other")
    response = client.get(f"/api/v1/kb/{kb_id}")
    assert response.status_code == 404

