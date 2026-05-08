from fastapi.testclient import TestClient

from app.admin.service import AdminService
from app.knowledge import KnowledgeService
from app.knowledge.runner import KnowledgeTaskRunner
from app.knowledge.store import KnowledgeStore
from app.knowledge.policy_ingestion import CrawledDocument, FakeCrawlerProvider
from app.knowledge.policy_live_crawler import PolicyCrawlerScheduler, PolicyCrawlerStore
from app.main import app
from app.retrieval.public_retriever import get_public_policy_retriever
from tests.test_helpers import TEST_PASSWORD, patch_test_auth_service

client = TestClient(app)


def build_admin_service(*, auth_service, db_path):
    return AdminService(auth_service=auth_service, sqlite_db_path=db_path)


def build_knowledge_service(*, db_path):
    return KnowledgeService(store=KnowledgeStore(sqlite_db_path=db_path))


def login_seed_admin_and_change_password() -> None:
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


def test_admin_routes_require_admin_role_and_password_change(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "carbonrag.sqlite3"
    auth_service = patch_test_auth_service(monkeypatch, db_path=db_path)
    auth_service.ensure_seed_admin_and_backfill()
    admin_service = build_admin_service(auth_service=auth_service, db_path=db_path)
    knowledge_service = build_knowledge_service(db_path=db_path)
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
    monkeypatch.setattr("app.api.v1.endpoints.admin.get_admin_service", lambda: admin_service)
    monkeypatch.setattr("app.private_samples.catalog.get_knowledge_service", lambda: knowledge_service)

    client.cookies.clear()
    login_seed_admin_and_change_password()

    register_response = client.post(
        "/api/v1/auth/register",
        json={"username": "member_two", "password": TEST_PASSWORD},
    )
    user_id = register_response.json()["user"]["user_id"]

    users_response = client.get("/api/v1/admin/users")
    assert users_response.status_code == 200
    assert any(item["user_id"] == user_id for item in users_response.json())

    update_response = client.patch(
        f"/api/v1/admin/users/{user_id}",
        json={"role": "admin", "is_active": True},
    )
    assert update_response.status_code == 200
    assert update_response.json()["role"] == "admin"

    reset_response = client.post(f"/api/v1/admin/users/{user_id}/reset-password")
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
    )
    assert update_private_sample_response.status_code == 200
    assert update_private_sample_response.json()["doc_id"] == doc_id

    refresh_response = client.post(
        "/api/v1/admin/knowledge-refresh-tasks",
        json={"scope": "public_policy"},
    )
    assert refresh_response.status_code == 200
    assert refresh_response.json()["status"] == "succeeded"

    scan_response = client.post("/api/v1/admin/knowledge-tasks/scan")
    assert scan_response.status_code == 200
    assert isinstance(scan_response.json(), list)

    feedback_response = client.get("/api/v1/admin/feedback/overview")
    assert feedback_response.status_code == 200

    system_response = client.get("/api/v1/admin/system/status")
    assert system_response.status_code == 200
    assert system_response.json()["total_users"] >= 2


def test_admin_policy_showcase_source_runs_to_retrievable_demo_policy(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "carbonrag.sqlite3"
    auth_service = patch_test_auth_service(monkeypatch, db_path=db_path)
    auth_service.ensure_seed_admin_and_backfill()
    admin_service = build_admin_service(auth_service=auth_service, db_path=db_path)
    knowledge_service = build_knowledge_service(db_path=db_path)
    runner = KnowledgeTaskRunner()
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

    run_response = client.post(f"/api/v1/admin/policy-sources/{source['source_id']}/run")
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
    second_run_response = client.post(f"/api/v1/admin/policy-sources/{source['source_id']}/run")
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

    status_response = client.get("/api/v1/admin/policy-crawler/status")
    assert status_response.status_code == 200
    assert status_response.json()["scheduled_enabled"] is False

    sources_response = client.get("/api/v1/admin/policy-crawler/sources")
    assert sources_response.status_code == 200
    assert any(item["source_id"] == "gov-cn-policy-library" for item in sources_response.json())

    run_response = client.post("/api/v1/admin/policy-crawler/sources/gov-cn-policy-library/run")
    assert run_response.status_code == 200
    assert run_response.json()["status"] == "succeeded"

    candidates_response = client.get("/api/v1/admin/policy-crawler/candidates")
    assert candidates_response.status_code == 200
    candidate = candidates_response.json()[0]
    assert candidate["status"] == "pending_review"

    runs_response = client.get("/api/v1/admin/policy-crawler/runs")
    assert runs_response.status_code == 200
    assert runs_response.json()[0]["candidate_count"] == 1

    publish_response = client.post(f"/api/v1/admin/policy-crawler/candidates/{candidate['candidate_id']}/publish")
    assert publish_response.status_code == 200
    assert publish_response.json()["status"] == "published"
    assert publish_response.json()["knowledge_item_id"]

    second_publish_response = client.post(f"/api/v1/admin/policy-crawler/candidates/{candidate['candidate_id']}/publish")
    assert second_publish_response.status_code == 400


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
    )
    scheduler.start()
    monkeypatch.setattr("app.api.v1.endpoints.admin.get_admin_service", lambda: admin_service)
    monkeypatch.setattr("app.admin.service.get_policy_crawler_scheduler", lambda: scheduler)

    client.cookies.clear()
    login_seed_admin_and_change_password()

    run_response = client.post("/api/v1/admin/policy-crawler/sources/gov-cn-policy-library/run")
    assert run_response.status_code == 200
    candidate = client.get("/api/v1/admin/policy-crawler/candidates").json()[0]

    reject_response = client.post(f"/api/v1/admin/policy-crawler/candidates/{candidate['candidate_id']}/reject")
    assert reject_response.status_code == 200
    assert reject_response.json()["status"] == "rejected"
