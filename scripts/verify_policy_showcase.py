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
import app.knowledge as knowledge_module  # noqa: E402
import app.knowledge.runner as knowledge_runner_module  # noqa: E402
import app.knowledge.service as knowledge_service_module  # noqa: E402
from app.admin.service import AdminService  # noqa: E402
from app.auth.service import AuthService  # noqa: E402
from app.knowledge import KnowledgeService  # noqa: E402
from app.knowledge.runner import KnowledgeTaskRunner  # noqa: E402
from app.knowledge.store import KnowledgeStore  # noqa: E402
from app.main import app  # noqa: E402
from app.retrieval.public_retriever import get_public_policy_retriever  # noqa: E402


def main() -> int:
    checks: list[str] = []
    with tempfile.TemporaryDirectory(prefix="carbonrag-policy-showcase-", ignore_cleanup_errors=True) as tmp_dir:
        db_path = Path(tmp_dir) / "carbonrag.sqlite3"
        auth_service = AuthService(sqlite_db_path=db_path)
        auth_service.ensure_seed_admin_and_backfill()
        knowledge_service = KnowledgeService(store=KnowledgeStore(sqlite_db_path=db_path))
        runner = KnowledgeTaskRunner()
        admin_service = AdminService(auth_service=auth_service, sqlite_db_path=db_path)

        auth_service_module.get_auth_service = lambda: auth_service
        auth_dependencies_module.get_auth_service = lambda: auth_service
        auth_endpoint_module.get_auth_service = lambda: auth_service
        admin_endpoint_module.get_admin_service = lambda: admin_service
        admin_service_module.get_knowledge_service = lambda: knowledge_service
        knowledge_module.get_knowledge_service = lambda: knowledge_service
        knowledge_service_module.get_knowledge_service = lambda: knowledge_service
        knowledge_runner_module.get_knowledge_task_runner = lambda: runner
        get_public_policy_retriever.cache_clear()

        with TestClient(app) as client:
            login_response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "123456"})
            assert login_response.status_code == 200, login_response.text
            change_response = client.post(
                "/api/v1/auth/change-password",
                json={"current_password": "123456", "new_password": "newpass123"},
            )
            assert change_response.status_code == 200, change_response.text
            checks.append("admin login and password change")

            sources_response = client.get("/api/v1/admin/policy-sources")
            assert sources_response.status_code == 200, sources_response.text
            sources = sources_response.json()
            assert sources, "no built-in policy showcase source"
            source = sources[0]
            checks.append("policy source list")

            run_response = client.post(f"/api/v1/admin/policy-sources/{source['source_id']}/run")
            assert run_response.status_code == 200, run_response.text
            run_payload = run_response.json()
            assert run_payload["indexed"] is True, run_payload
            assert run_payload["item"]["source_type"] == "public_policy_web", run_payload
            assert run_payload["item"]["visibility"] == "demo", run_payload
            assert "gov.cn" not in run_payload["source"]["source_url"], run_payload
            assert run_payload["chunks"], run_payload
            assert run_payload["chunks"][0]["source_type"] == "public_policy_demo", run_payload
            checks.append("policy ingest run")

            status_response = client.get(f"/api/v1/admin/policy-sources/{source['source_id']}/status")
            assert status_response.status_code == 200, status_response.text
            status_payload = status_response.json()
            assert status_payload["workflow"]["status"] == "completed", status_payload
            checks.append("workflow status")

            chunks_response = client.get(f"/api/v1/admin/policy-sources/{source['source_id']}/chunks")
            assert chunks_response.status_code == 200, chunks_response.text
            chunks_payload = chunks_response.json()
            assert chunks_payload and chunks_payload[0]["source_type"] == "public_policy_demo", chunks_payload
            assert chunks_payload[0]["metadata"]["citation_disclaimer"], chunks_payload
            checks.append("showcase demo chunks")

            preview_response = client.get(
                f"/api/v1/admin/policy-sources/{source['source_id']}/retrieval-preview",
                params={"query": source["default_query"], "top_k": 5},
            )
            assert preview_response.status_code == 200, preview_response.text
            preview_payload = preview_response.json()
            assert any(hit["matched_source"] for hit in preview_payload["hits"]), preview_payload
            assert any(hit["source_type"] == "public_policy_demo" for hit in preview_payload["hits"]), preview_payload
            assert all(not (hit["matched_source"] and hit["source_type"] == "public_policy") for hit in preview_payload["hits"]), preview_payload
            checks.append("retrieval preview")

            item_count = len(knowledge_service.list_admin_items(source_type="public_policy_web"))
            second_run_response = client.post(f"/api/v1/admin/policy-sources/{source['source_id']}/run")
            assert second_run_response.status_code == 200, second_run_response.text
            assert len(knowledge_service.list_admin_items(source_type="public_policy_web")) == item_count
            checks.append("idempotent refresh")

    print(json.dumps({"status": "ok", "checks": checks}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
