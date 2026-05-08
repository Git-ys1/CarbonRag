from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient  # noqa: E402

import app.api.v1.endpoints.admin as admin_endpoint_module  # noqa: E402
import app.api.v1.endpoints.auth as auth_endpoint_module  # noqa: E402
import app.admin.service as admin_service_module  # noqa: E402
import app.auth.dependencies as auth_dependencies_module  # noqa: E402
import app.auth.service as auth_service_module  # noqa: E402
import app.knowledge.runner as knowledge_runner_module  # noqa: E402
import app.knowledge.service as knowledge_service_module  # noqa: E402
import app.main as main_module  # noqa: E402
from app.admin.service import AdminService  # noqa: E402
from app.auth.service import AuthService  # noqa: E402
from app.knowledge.policy_ingestion import CrawledDocument, FakeCrawlerProvider  # noqa: E402
from app.knowledge.policy_live_crawler import PolicyCrawlerScheduler, PolicyCrawlerStore  # noqa: E402
from app.knowledge.runner import KnowledgeTaskRunner  # noqa: E402
from app.knowledge.service import KnowledgeService  # noqa: E402
from app.knowledge.store import KnowledgeStore  # noqa: E402
from app.main import app  # noqa: E402


def main() -> int:
    checks: list[str] = []
    with tempfile.TemporaryDirectory(prefix="carbonrag-policy-live-crawler-", ignore_cleanup_errors=True) as tmp_dir:
        root = Path(tmp_dir)
        db_path = root / "carbonrag.sqlite3"
        auth_service = AuthService(sqlite_db_path=db_path)
        auth_service.ensure_seed_admin_and_backfill()
        knowledge_service = KnowledgeService(store=KnowledgeStore(sqlite_db_path=db_path))
        runner = KnowledgeTaskRunner()
        admin_service = AdminService(auth_service=auth_service, sqlite_db_path=db_path)
        document = CrawledDocument(
            url="https://www.gov.cn/zhengce/verify-live-crawler.html",
            title="Verified live crawler policy candidate",
            content="<html><body><h1>Verified policy</h1><p>Article 1 promotes carbon accounting.</p></body></html>",
            source_name="Official policy source",
        )
        scheduler = PolicyCrawlerScheduler(
            store=PolicyCrawlerStore(sqlite_db_path=db_path),
            provider=FakeCrawlerProvider(documents=[document]),
            candidate_dir=root / "candidates",
        )

        auth_service_module.get_auth_service = lambda: auth_service
        auth_dependencies_module.get_auth_service = lambda: auth_service
        auth_endpoint_module.get_auth_service = lambda: auth_service
        admin_endpoint_module.get_admin_service = lambda: admin_service
        admin_service_module.get_policy_crawler_scheduler = lambda: scheduler
        knowledge_service_module.get_knowledge_service = lambda: knowledge_service
        knowledge_runner_module.get_knowledge_task_runner = lambda: runner
        main_module.get_policy_crawler_scheduler = lambda: scheduler

        with TestClient(app) as client:
            login_response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "123456"})
            assert login_response.status_code == 200, login_response.text
            change_response = client.post(
                "/api/v1/auth/change-password",
                json={"current_password": "123456", "new_password": "newpass123"},
            )
            assert change_response.status_code == 200, change_response.text
            checks.append("admin login")

            status_response = client.get("/api/v1/admin/policy-crawler/status")
            assert status_response.status_code == 200, status_response.text
            status_payload = status_response.json()
            assert status_payload["scheduled_enabled"] is False, status_payload
            checks.append("manual-default scheduler status")

            sources_response = client.get("/api/v1/admin/policy-crawler/sources")
            assert sources_response.status_code == 200, sources_response.text
            assert any(item["source_id"] == "gov-cn-policy-library" for item in sources_response.json())
            checks.append("official source list")

            run_response = client.post("/api/v1/admin/policy-crawler/sources/gov-cn-policy-library/run")
            assert run_response.status_code == 200, run_response.text
            assert run_response.json()["status"] == "succeeded", run_response.json()
            checks.append("manual crawl run")

            candidates_response = client.get("/api/v1/admin/policy-crawler/candidates")
            assert candidates_response.status_code == 200, candidates_response.text
            candidate = candidates_response.json()[0]
            assert candidate["status"] == "pending_review", candidate
            assert not knowledge_service.list_admin_items(source_type="public_policy_web")
            checks.append("pending candidate before indexing")

            publish_response = client.post(f"/api/v1/admin/policy-crawler/candidates/{candidate['candidate_id']}/publish")
            assert publish_response.status_code == 200, publish_response.text
            assert publish_response.json()["status"] == "published", publish_response.json()
            assert knowledge_service.list_admin_items(source_type="public_policy_web")
            checks.append("publish enqueues ingestion")

    print(json.dumps({"status": "ok", "checks": checks}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
