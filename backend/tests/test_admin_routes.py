from fastapi.testclient import TestClient

from app.admin.service import AdminService
from app.core.config import Settings
from app.knowledge import KnowledgeService
from app.knowledge.runner import KnowledgeTaskRunner
from app.knowledge.store import KnowledgeStore
from app.knowledge.policy_ingestion import CrawledDocument, FakeCrawlerProvider
from app.knowledge.policy_live_crawler import PolicyCrawlerScheduler, PolicyCrawlerStore
from app.main import app
from app.auth.schemas import RegisterRequest
from app.management.service import ManagementService
from app.management.storage import ManagementStore
from app.retrieval.public_retriever import get_public_policy_retriever
from tests.management_test_utils import (
    build_action_ack_headers,
    create_management_test_device,
    enroll_management_device,
    start_management_relay,
)
from tests.test_helpers import TEST_PASSWORD, patch_test_auth_service

client = TestClient(app)


def build_admin_service(*, auth_service, db_path):
    return AdminService(auth_service=auth_service, sqlite_db_path=db_path)


def build_knowledge_service(*, db_path):
    return KnowledgeService(store=KnowledgeStore(sqlite_db_path=db_path))


def build_management_service(*, db_path):
    return ManagementService(store=ManagementStore(sqlite_db_path=db_path))


def patch_management_service(monkeypatch, *, db_path):
    management_service = build_management_service(db_path=db_path)
    monkeypatch.setattr("app.management.router.get_management_service", lambda: management_service)
    monkeypatch.setattr("app.management.service.get_management_service", lambda: management_service)
    return management_service


def login_seed_admin_and_change_password() -> dict:
    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "123456"},
    )
    assert login_response.status_code == 200
    assert login_response.json()["must_change_password"] is True
    change_response = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "123456", "new_password": "newpass123"},
    )
    assert change_response.status_code == 200
    return change_response.json()["user"]


def start_seed_super_admin_management_session() -> tuple[dict, object]:
    user = client.get("/api/v1/auth/me").json()["user"]
    device = create_management_test_device("sa-device")
    enroll_management_device(client, device=device, role_scope="super_admin", device_name="测试超级管理员设备")
    start_management_relay(client, user_id=user["user_id"], role="super_admin", device=device)
    return user, device


def action_headers(device, *, action_type: str, target_type: str, target_id: str, payload: dict | None = None) -> dict:
    return build_action_ack_headers(
        client,
        device=device,
        action_type=action_type,
        target_type=target_type,
        target_id=target_id,
        payload=payload,
    )


def test_admin_routes_require_admin_role_and_password_change(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "carbonrag.sqlite3"
    auth_service = patch_test_auth_service(monkeypatch, db_path=db_path)
    auth_service.ensure_seed_admin_and_backfill()
    admin_service = build_admin_service(auth_service=auth_service, db_path=db_path)
    knowledge_service = build_knowledge_service(db_path=db_path)
    patch_management_service(monkeypatch, db_path=db_path)
    monkeypatch.setattr("app.api.v1.endpoints.admin.get_admin_service", lambda: admin_service)
    monkeypatch.setattr("app.private_samples.catalog.get_knowledge_service", lambda: knowledge_service)

    client.cookies.clear()
    client.post("/api/v1/auth/register", json={"username": "member_one", "password": TEST_PASSWORD})
    client.post("/api/v1/auth/login", json={"username": "member_one", "password": TEST_PASSWORD})
    user_response = client.get("/api/v1/admin/users")
    assert user_response.status_code == 403

    client.cookies.clear()
    login_response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "123456"})
    assert login_response.status_code == 200
    assert login_response.json()["must_change_password"] is True
    blocked_response = client.get("/api/v1/admin/users")
    assert blocked_response.status_code == 403


def test_admin_routes_manage_users_private_samples_and_refresh(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "carbonrag.sqlite3"
    auth_service = patch_test_auth_service(monkeypatch, db_path=db_path)
    auth_service.ensure_seed_admin_and_backfill()
    admin_service = build_admin_service(auth_service=auth_service, db_path=db_path)
    knowledge_service = build_knowledge_service(db_path=db_path)
    patch_management_service(monkeypatch, db_path=db_path)
    monkeypatch.setattr("app.api.v1.endpoints.admin.get_admin_service", lambda: admin_service)
    monkeypatch.setattr("app.private_samples.catalog.get_knowledge_service", lambda: knowledge_service)

    client.cookies.clear()
    login_seed_admin_and_change_password()
    _, management_device = start_seed_super_admin_management_session()

    register_response = client.post(
        "/api/v1/auth/register",
        json={"username": "member_two", "password": TEST_PASSWORD},
    )
    user_id = register_response.json()["user"]["user_id"]

    users_response = client.get("/api/v1/admin/users")
    assert users_response.status_code == 200
    assert any(item["user_id"] == user_id for item in users_response.json())

    create_user_payload = {
        "username": "created_user",
        "password": TEST_PASSWORD,
        "display_name": "created_user_display",
        "role": "user",
    }
    create_user_response = client.post(
        "/api/v1/admin/users",
        json=create_user_payload,
        headers=action_headers(
            management_device,
            action_type="ADMIN_USER_CREATE",
            target_type="user",
            target_id="new",
            payload=create_user_payload,
        ),
    )
    assert create_user_response.status_code == 200
    assert create_user_response.json()["username"] == "created_user"
    assert create_user_response.json()["role"] == "user"

    create_admin_payload = {
        "username": "created_admin",
        "password": TEST_PASSWORD,
        "display_name": "created_admin_display",
        "role": "admin",
    }
    create_admin_response = client.post(
        "/api/v1/admin/users",
        json=create_admin_payload,
        headers=action_headers(
            management_device,
            action_type="ADMIN_USER_CREATE",
            target_type="user",
            target_id="new",
            payload=create_admin_payload,
        ),
    )
    assert create_admin_response.status_code == 200
    assert create_admin_response.json()["role"] == "admin"

    update_response = client.patch(
        f"/api/v1/admin/users/{user_id}",
        json={"role": "admin", "is_active": True},
        headers=action_headers(
            management_device,
            action_type="ADMIN_USER_UPDATE",
            target_type="user",
            target_id=user_id,
            payload={"role": "admin", "is_active": True},
        ),
    )
    assert update_response.status_code == 200
    assert update_response.json()["role"] == "admin"

    reset_response = client.post(
        f"/api/v1/admin/users/{user_id}/reset-password",
        headers=action_headers(
            management_device,
            action_type="ADMIN_USER_RESET_PASSWORD",
            target_type="user",
            target_id=user_id,
            payload={},
        ),
    )
    assert reset_response.status_code == 200
    assert reset_response.json()["temporary_password"]

    private_samples_response = client.get("/api/v1/admin/private-samples")
    assert private_samples_response.status_code == 200
    doc_id = private_samples_response.json()[0]["doc_id"]

    knowledge_items_response = client.get("/api/v1/admin/knowledge-items")
    assert knowledge_items_response.status_code == 200
    assert any(item["knowledge_item_id"] == doc_id for item in knowledge_items_response.json())

    knowledge_tasks_response = client.get("/api/v1/admin/knowledge-tasks")
    assert knowledge_tasks_response.status_code == 200
    assert isinstance(knowledge_tasks_response.json(), list)

    update_private_sample_response = client.patch(
        f"/api/v1/admin/private-samples/{doc_id}",
        json={"is_enabled": True, "session_attachable": True},
        headers=action_headers(
            management_device,
            action_type="ADMIN_PRIVATE_SAMPLE_UPDATE",
            target_type="private_sample",
            target_id=doc_id,
            payload={"is_enabled": True, "session_attachable": True},
        ),
    )
    assert update_private_sample_response.status_code == 200
    assert update_private_sample_response.json()["doc_id"] == doc_id

    refresh_response = client.post(
        "/api/v1/admin/knowledge-refresh-tasks",
        json={"scope": "public_policy"},
        headers=action_headers(
            management_device,
            action_type="ADMIN_KNOWLEDGE_REFRESH_TRIGGER",
            target_type="knowledge_refresh",
            target_id="trigger",
            payload={"scope": "public_policy"},
        ),
    )
    assert refresh_response.status_code == 200
    assert refresh_response.json()["status"] == "succeeded"


def test_admin_batch_delete_users_requires_password_and_blocks_protected_targets(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "carbonrag.sqlite3"
    auth_service = patch_test_auth_service(monkeypatch, db_path=db_path)
    auth_service.ensure_seed_admin_and_backfill()
    admin_service = build_admin_service(auth_service=auth_service, db_path=db_path)
    patch_management_service(monkeypatch, db_path=db_path)
    monkeypatch.setattr("app.api.v1.endpoints.admin.get_admin_service", lambda: admin_service)

    client.cookies.clear()
    login_seed_admin_and_change_password()
    _, management_device = start_seed_super_admin_management_session()
    admin_user = client.get("/api/v1/auth/me").json()["user"]

    register_response = client.post(
        "/api/v1/auth/register",
        json={"username": "delete_member", "password": TEST_PASSWORD},
    )
    target_user_id = register_response.json()["user"]["user_id"]
    admin_target = auth_service.register(RegisterRequest(username="delete_admin", password=TEST_PASSWORD))
    admin_target = auth_service.update_user(user_id=admin_target.user_id, role="admin", is_active=True)

    wrong_password_response = client.request(
        "DELETE",
        "/api/v1/admin/users",
        json={"user_ids": [target_user_id], "current_password": "wrongpass123"},
        headers=action_headers(
            management_device,
            action_type="ADMIN_USER_DELETE",
            target_type="user_batch",
            target_id="batch",
            payload={"user_ids": [target_user_id], "current_password": "wrongpass123"},
        ),
    )
    assert wrong_password_response.status_code == 422
    assert any(item.user_id == target_user_id for item in admin_service.list_users())

    delete_self_response = client.request(
        "DELETE",
        "/api/v1/admin/users",
        json={"user_ids": [admin_user["user_id"]], "current_password": "newpass123"},
        headers=action_headers(
            management_device,
            action_type="ADMIN_USER_DELETE",
            target_type="user_batch",
            target_id="batch",
            payload={"user_ids": [admin_user["user_id"]], "current_password": "newpass123"},
        ),
    )
    assert delete_self_response.status_code == 400

    delete_super_admin_response = client.request(
        "DELETE",
        "/api/v1/admin/users",
        json={"user_ids": [admin_user["user_id"]], "current_password": "newpass123"},
        headers=action_headers(
            management_device,
            action_type="ADMIN_USER_DELETE",
            target_type="user_batch",
            target_id="batch",
            payload={"user_ids": [admin_user["user_id"]], "current_password": "newpass123"},
        ),
    )
    assert delete_super_admin_response.status_code == 400

    delete_admin_response = client.request(
        "DELETE",
        "/api/v1/admin/users",
        json={"user_ids": [admin_target.user_id], "current_password": "newpass123"},
        headers=action_headers(
            management_device,
            action_type="ADMIN_USER_DELETE",
            target_type="user_batch",
            target_id="batch",
            payload={"user_ids": [admin_target.user_id], "current_password": "newpass123"},
        ),
    )
    assert delete_admin_response.status_code == 200
    assert delete_admin_response.json()["deleted_user_ids"] == [admin_target.user_id]

    delete_response = client.request(
        "DELETE",
        "/api/v1/admin/users",
        json={"user_ids": [target_user_id], "current_password": "newpass123"},
        headers=action_headers(
            management_device,
            action_type="ADMIN_USER_DELETE",
            target_type="user_batch",
            target_id="batch",
            payload={"user_ids": [target_user_id], "current_password": "newpass123"},
        ),
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted_user_ids"] == [target_user_id]
    assert all(item.user_id != target_user_id for item in admin_service.list_users())

    client.cookies.clear()
    relogin_response = client.post(
        "/api/v1/auth/login",
        json={"username": "delete_member", "password": TEST_PASSWORD},
    )
    assert relogin_response.status_code == 401


def test_admin_policy_showcase_source_runs_to_retrievable_demo_policy(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "carbonrag.sqlite3"
    auth_service = patch_test_auth_service(monkeypatch, db_path=db_path)
    auth_service.ensure_seed_admin_and_backfill()
    admin_service = build_admin_service(auth_service=auth_service, db_path=db_path)
    knowledge_service = build_knowledge_service(db_path=db_path)
    runner = KnowledgeTaskRunner()
    patch_management_service(monkeypatch, db_path=db_path)
    monkeypatch.setattr("app.api.v1.endpoints.admin.get_admin_service", lambda: admin_service)
    monkeypatch.setattr("app.private_samples.catalog.get_knowledge_service", lambda: knowledge_service)
    monkeypatch.setattr("app.admin.service.get_knowledge_service", lambda: knowledge_service)
    monkeypatch.setattr("app.knowledge.service.get_knowledge_service", lambda: knowledge_service)
    monkeypatch.setattr("app.knowledge.get_knowledge_service", lambda: knowledge_service)
    monkeypatch.setattr("app.knowledge.runner.get_knowledge_task_runner", lambda: runner)
    get_public_policy_retriever.cache_clear()

    client.cookies.clear()
    client.post("/api/v1/auth/register", json={"username": "member_policy", "password": TEST_PASSWORD})
    client.post("/api/v1/auth/login", json={"username": "member_policy", "password": TEST_PASSWORD})
    blocked_response = client.get("/api/v1/admin/policy-sources")
    assert blocked_response.status_code == 403

    client.cookies.clear()
    login_seed_admin_and_change_password()
    _, management_device = start_seed_super_admin_management_session()

    sources_response = client.get("/api/v1/admin/policy-sources")
    assert sources_response.status_code == 200
    source = sources_response.json()[0]
    assert source["source_id"] == "low-carbon-campus-action"
    assert source["metadata"]["source_kind"] == "demo_showcase"
    assert source["metadata"]["is_synthetic"] == "true"
    assert "gov.cn" not in source["source_url"]
    assert "国务院" not in source["source_label"]

    empty_status_response = client.get(f"/api/v1/admin/policy-sources/{source['source_id']}/status")
    assert empty_status_response.status_code == 200
    assert empty_status_response.json()["indexed"] is False
    assert empty_status_response.json()["item"] is None

    run_response = client.post(
        f"/api/v1/admin/policy-sources/{source['source_id']}/run",
        headers=action_headers(
            management_device,
            action_type="ADMIN_POLICY_SOURCE_RUN",
            target_type="policy_source",
            target_id=source["source_id"],
            payload={},
        ),
    )
    assert run_response.status_code == 200
    run_payload = run_response.json()
    assert run_payload["indexed"] is True
    assert run_payload["item"]["source_type"] == "public_policy_web"
    assert run_payload["item"]["visibility"] == "demo"
    assert run_payload["item"]["source_label"] == "演示样例"
    assert run_payload["latest_task"]["task_type"] == "crawl_ingest"
    assert run_payload["latest_task"]["status"] == "succeeded"
    assert run_payload["workflow"]["workflow_type"] == "policy_ingest"
    assert run_payload["workflow"]["status"] == "completed"
    assert run_payload["chunks"]
    assert run_payload["chunks"][0]["source_type"] == "public_policy_demo"
    assert run_payload["chunks"][0]["metadata"]["citation_source_type"] == "public_policy_demo"
    assert run_payload["chunks"][0]["metadata"]["citation_disclaimer"]

    chunks_response = client.get(f"/api/v1/admin/policy-sources/{source['source_id']}/chunks")
    assert chunks_response.status_code == 200
    assert chunks_response.json()[0]["metadata"]["original_source_type"] == "public_policy_web"
    assert chunks_response.json()[0]["source_type"] == "public_policy_demo"

    preview_response = client.get(
        f"/api/v1/admin/policy-sources/{source['source_id']}/retrieval-preview",
        params={"query": source["default_query"], "top_k": 5},
    )
    assert preview_response.status_code == 200
    preview_payload = preview_response.json()
    assert preview_payload["total_hits"] >= 1
    assert any(hit["matched_source"] for hit in preview_payload["hits"])
    matched_hits = [hit for hit in preview_payload["hits"] if hit["matched_source"]]
    assert matched_hits
    assert all(hit["source_type"] == "public_policy_demo" for hit in matched_hits)
    assert all("gov.cn" not in (hit["source_url"] or "") for hit in matched_hits)

    item_count = len(knowledge_service.list_admin_items(source_type="public_policy_web"))
    second_run_response = client.post(
        f"/api/v1/admin/policy-sources/{source['source_id']}/run",
        headers=action_headers(
            management_device,
            action_type="ADMIN_POLICY_SOURCE_RUN",
            target_type="policy_source",
            target_id=source["source_id"],
            payload={},
        ),
    )
    assert second_run_response.status_code == 200
    assert len(knowledge_service.list_admin_items(source_type="public_policy_web")) == item_count


def test_admin_policy_live_crawler_review_flow(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "carbonrag.sqlite3"
    auth_service = patch_test_auth_service(monkeypatch, db_path=db_path)
    auth_service.ensure_seed_admin_and_backfill()
    admin_service = build_admin_service(auth_service=auth_service, db_path=db_path)
    document = CrawledDocument(
        url="https://www.gov.cn/zhengce/admin-live-policy.html",
        title="Admin live policy sample",
        content="<html><body><p>Article 1 promotes carbon accounting.</p></body></html>",
        source_name="Official policy source",
    )
    scheduler = PolicyCrawlerScheduler(
        store=PolicyCrawlerStore(sqlite_db_path=db_path),
        provider=FakeCrawlerProvider(documents=[document]),
        candidate_dir=tmp_path / "candidates",
    )
    scheduler.start()
    knowledge_service = build_knowledge_service(db_path=db_path)
    runner = KnowledgeTaskRunner()
    patch_management_service(monkeypatch, db_path=db_path)
    monkeypatch.setattr("app.api.v1.endpoints.admin.get_admin_service", lambda: admin_service)
    monkeypatch.setattr("app.admin.service.get_policy_crawler_scheduler", lambda: scheduler)
    monkeypatch.setattr("app.knowledge.service.get_knowledge_service", lambda: knowledge_service)
    monkeypatch.setattr("app.knowledge.runner.get_knowledge_task_runner", lambda: runner)

    client.cookies.clear()
    client.post("/api/v1/auth/register", json={"username": "crawler_user", "password": TEST_PASSWORD})
    client.post("/api/v1/auth/login", json={"username": "crawler_user", "password": TEST_PASSWORD})
    blocked_response = client.get("/api/v1/admin/policy-crawler/sources")
    assert blocked_response.status_code == 403

    client.cookies.clear()
    login_seed_admin_and_change_password()
    _, management_device = start_seed_super_admin_management_session()

    status_response = client.get("/api/v1/admin/policy-crawler/status")
    assert status_response.status_code == 200
    assert status_response.json()["scheduled_enabled"] is False
    assert status_response.json()["auto_publish_enabled"] is False

    sources_response = client.get("/api/v1/admin/policy-crawler/sources")
    assert sources_response.status_code == 200
    assert any(item["source_id"] == "gov-cn-policy-library" for item in sources_response.json())

    import_response = client.post(
        "/api/v1/admin/policy-crawler/sources/recommended/import",
        headers=action_headers(
            management_device,
            action_type="POLICY_CRAWLER_RECOMMENDED_IMPORT",
            target_type="policy_crawler_source",
            target_id="recommended",
            payload={},
        ),
    )
    assert import_response.status_code == 200
    assert import_response.json()["imported_count"] >= 12
    assert import_response.json()["enabled_count"] <= 5

    create_payload = {
        "source_id": "custom-gov-source",
        "title": "自定义中国政府网源",
        "source_url": "https://www.gov.cn/zhengce/custom.html",
        "source_label": "中国政府网",
        "source_category": "国家政策",
        "topic_tags": ["双碳"],
        "required_keywords": ["碳"],
        "optional_keywords": ["碳达峰"],
        "parser_profile": "gov_policy_html",
        "max_depth": 1,
        "max_pages": 5,
        "review_required": True,
    }
    create_response = client.post(
        "/api/v1/admin/policy-crawler/sources",
        json=create_payload,
        headers=action_headers(
            management_device,
            action_type="POLICY_CRAWLER_SOURCE_CREATE",
            target_type="policy_crawler_source",
            target_id="new",
            payload=create_payload,
        ),
    )
    assert create_response.status_code == 200
    assert create_response.json()["is_enabled"] is False
    assert create_response.json()["source_category"] == "国家政策"

    dry_run_response = client.post("/api/v1/admin/policy-crawler/sources/custom-gov-source/dry-run")
    assert dry_run_response.status_code == 200
    assert dry_run_response.json()["source_id"] == "custom-gov-source"

    run_response = client.post(
        "/api/v1/admin/policy-crawler/sources/gov-cn-policy-library/run",
        headers=action_headers(
            management_device,
            action_type="POLICY_CRAWLER_SOURCE_RUN",
            target_type="policy_crawler_source",
            target_id="gov-cn-policy-library",
            payload={},
        ),
    )
    assert run_response.status_code == 200
    assert run_response.json()["status"] == "succeeded"

    candidates_response = client.get("/api/v1/admin/policy-crawler/candidates")
    assert candidates_response.status_code == 200
    candidates_page = candidates_response.json()
    assert candidates_page["total"] >= 1
    candidate = candidates_page["items"][0]
    assert candidate["status"] == "pending_review"
    assert candidate["metadata"]["candidate_summary"]
    assert candidate["metadata"]["candidate_content_length"] > 0
    assert candidate["metadata"]["seed_url"] == "https://www.gov.cn/zhengce/"
    assert candidate["metadata"]["policy_review_required"] is True
    assert candidate["metadata"]["matched_policy_keywords"]
    assert candidate["candidate_quality_score"] is not None
    assert candidate["extraction_quality_score"] is not None
    assert candidate["knowledge_item_id"] is None

    artifacts_response = client.get(f"/api/v1/admin/policy-crawler/candidates/{candidate['candidate_id']}/artifacts")
    assert artifacts_response.status_code == 200
    artifacts = artifacts_response.json()
    assert artifacts["candidate_id"] == candidate["candidate_id"]
    assert artifacts["markdown_exists"] is True
    assert artifacts["cleaned_exists"] is True
    assert artifacts["markdown_preview"]
    assert artifacts["cleaned_text_preview"]

    def fake_publish_to_rag(candidate_id: str, reviewed_by_user_id: str | None):
        scheduler.store.update_candidate_review(
            candidate_id=candidate_id,
            status="published",
            reviewed_by_user_id=reviewed_by_user_id,
            review_note="Published to RAG KB and quick pipeline completed.",
            metadata={
                "rag_kb_id": "kb-policy",
                "rag_doc_id": "rag-doc-policy",
                "rag_pipeline_status": "indexed",
                "rag_indexed_chunk_count": 2,
                "rag_search_smoke_passed": True,
            },
        )

    monkeypatch.setattr("app.admin.service.publish_crawled_candidate_to_rag_kb", fake_publish_to_rag)
    rag_publish_response = client.post(
        f"/api/v1/admin/policy-crawler/candidates/{candidate['candidate_id']}/publish-to-rag",
        headers=action_headers(
            management_device,
            action_type="POLICY_CRAWLER_CANDIDATE_PUBLISH_TO_RAG",
            target_type="policy_crawler_candidate",
            target_id=candidate["candidate_id"],
            payload={},
        ),
    )
    assert rag_publish_response.status_code == 200
    rag_candidate = rag_publish_response.json()
    assert rag_candidate["status"] == "published"
    assert rag_candidate["rag_kb_id"] == "kb-policy"
    assert rag_candidate["rag_doc_id"] == "rag-doc-policy"
    assert rag_candidate["rag_pipeline_status"] == "indexed"
    assert rag_candidate["rag_indexed_chunk_count"] == 2
    assert rag_candidate["rag_search_smoke_passed"] is True

    batch_payload = {
        "candidate_ids": [candidate["candidate_id"]],
        "target_kb_policy": "auto_crawler_default",
        "skip_duplicates": True,
    }
    batch_response = client.post(
        "/api/v1/admin/policy-crawler/candidates/batch-publish-to-rag",
        json=batch_payload,
        headers=action_headers(
            management_device,
            action_type="POLICY_CRAWLER_CANDIDATE_BATCH_PUBLISH_TO_RAG",
            target_type="policy_crawler_candidate",
            target_id="batch",
            payload=batch_payload,
        ),
    )
    assert batch_response.status_code == 200
    assert batch_response.json()["total"] == 1
    assert batch_response.json()["published"] == 1
    assert batch_response.json()["items"][0]["rag_doc_id"] == "rag-doc-policy"

    runs_response = client.get("/api/v1/admin/policy-crawler/runs")
    assert runs_response.status_code == 200
    runs_page = runs_response.json()
    assert runs_page["total"] >= 1
    assert runs_page["items"][0]["candidate_count"] == 1
    assert runs_page["items"][0]["metadata"]["auto_published_count"] == 0
    assert runs_page["items"][0]["metadata"]["auto_indexed_count"] == 0


def test_admin_policy_live_crawler_reject_flow(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "carbonrag.sqlite3"
    auth_service = patch_test_auth_service(monkeypatch, db_path=db_path)
    auth_service.ensure_seed_admin_and_backfill()
    admin_service = build_admin_service(auth_service=auth_service, db_path=db_path)
    document = CrawledDocument(
        url="https://www.gov.cn/zhengce/admin-reject-policy.html",
        title="Admin reject policy sample",
        content="<html><body><p>Article 1 promotes carbon accounting.</p></body></html>",
        source_name="Official policy source",
    )
    scheduler = PolicyCrawlerScheduler(
        store=PolicyCrawlerStore(sqlite_db_path=db_path),
        provider=FakeCrawlerProvider(documents=[document]),
        candidate_dir=tmp_path / "candidates",
        settings=Settings(rag_policy_live_crawler_auto_publish=False, rag_policy_live_crawler_scheduled_enabled=False),
    )
    scheduler.start()
    patch_management_service(monkeypatch, db_path=db_path)
    monkeypatch.setattr("app.api.v1.endpoints.admin.get_admin_service", lambda: admin_service)
    monkeypatch.setattr("app.admin.service.get_policy_crawler_scheduler", lambda: scheduler)

    client.cookies.clear()
    login_seed_admin_and_change_password()
    _, management_device = start_seed_super_admin_management_session()

    run_response = client.post(
        "/api/v1/admin/policy-crawler/sources/gov-cn-policy-library/run",
        headers=action_headers(
            management_device,
            action_type="POLICY_CRAWLER_SOURCE_RUN",
            target_type="policy_crawler_source",
            target_id="gov-cn-policy-library",
            payload={},
        ),
    )
    assert run_response.status_code == 200
    candidate = client.get("/api/v1/admin/policy-crawler/candidates").json()["items"][0]

    reject_response = client.post(
        f"/api/v1/admin/policy-crawler/candidates/{candidate['candidate_id']}/reject",
        headers=action_headers(
            management_device,
            action_type="POLICY_CRAWLER_CANDIDATE_REJECT",
            target_type="policy_crawler_candidate",
            target_id=candidate["candidate_id"],
            payload={},
        ),
    )
    assert reject_response.status_code == 200
    assert reject_response.json()["status"] == "rejected"
