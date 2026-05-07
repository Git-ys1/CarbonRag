from __future__ import annotations

import tempfile
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

import app.knowledge as knowledge_pkg  # noqa: E402
import app.knowledge.runner as runner_mod  # noqa: E402
import app.knowledge.service as service_mod  # noqa: E402
from app.knowledge.policy_ingestion import CrawledDocument  # noqa: E402
from app.knowledge.runner import KnowledgeTaskRunner  # noqa: E402
from app.knowledge.service import KnowledgeService  # noqa: E402
from app.knowledge.store import KnowledgeStore  # noqa: E402
from app.retrieval.public_retriever import get_public_policy_retriever  # noqa: E402


TITLE = "\u4f4e\u78b3\u97e7\u6027\u6821\u56ed\u5efa\u8bbe\u884c\u52a8\u65b9\u6848"
SOURCE_LABEL = "\u4e2d\u56fd\u653f\u5e9c\u7f51"
QUERY = "\u4f4e\u78b3\u97e7\u6027\u6821\u56ed \u78b3\u6838\u7b97"


class NoBootstrapKnowledgeService(KnowledgeService):
    def bootstrap_shared_library(self):  # type: ignore[override]
        return []


class FakeSessionService:
    knowledge_service = None


def main() -> int:
    checks: list[tuple[str, bool, str]] = []
    with tempfile.TemporaryDirectory(prefix="carbonrag-policy-verify-", ignore_cleanup_errors=True) as temp_dir:
        temp_root = Path(temp_dir)
        store = KnowledgeStore(sqlite_db_path=temp_root / "carbonrag.sqlite3")
        runner = KnowledgeTaskRunner()
        service = NoBootstrapKnowledgeService(store=store, session_service=FakeSessionService())
        _patch_service_singletons(service=service, runner=runner)
        get_public_policy_retriever.cache_clear()

        crawled = CrawledDocument(
            url="https://www.gov.cn/zhengce/content/policy-verify.htm",
            title=TITLE,
            content=f"""
            <html><head><title>{TITLE}</title></head>
            <body>
              <nav>\u9996\u9875 \u5bfc\u822a \u4e0d\u5e94\u8fdb\u5165\u6b63\u6587</nav>
              <h1>{TITLE}</h1>
              <p>\u6765\u6e90\uff1a{SOURCE_LABEL} \u53d1\u5e03\u65f6\u95f4\uff1a2026\u5e745\u67081\u65e5</p>
              <p>\u56fd\u529e\u53d1\u30142026\u30158\u53f7</p>
              <p>\u7b2c\u4e00\u6761 \u63a8\u52a8\u4f4e\u78b3\u97e7\u6027\u6821\u56ed\u5efa\u8bbe\uff0c\u5b8c\u5584\u78b3\u6838\u7b97\u3001\u8282\u80fd\u6539\u9020\u548c\u7eff\u8272\u4f4e\u78b3\u6559\u80b2\u3002</p>
            </body></html>
            """,
        )

        task = service.create_policy_item_from_crawled_document(
            crawled_document=crawled,
            staging_dir=temp_root / "staging",
        )
        processed = runner.run_once()
        refreshed_task = store.get_task(task.task_id)
        item = store.get_item(task.knowledge_item_id or "")
        workflow = store.get_latest_workflow_run(knowledge_item_id=task.knowledge_item_id or "")
        chunks = store.list_chunks(task.knowledge_item_id or "")

        get_public_policy_retriever.cache_clear()
        result = get_public_policy_retriever().search(question=QUERY, top_k=5)
        retrieval_hit = any(hit.knowledge_item_id == (item.knowledge_item_id if item else None) for hit in result.hits)
        first_chunk = chunks[0] if chunks else None

        checks.extend(
            [
                ("crawl_ingest task processed", task.task_id in processed, str(processed)),
                ("task succeeded", refreshed_task is not None and refreshed_task.status == "succeeded", getattr(refreshed_task, "status", None) or "missing"),
                ("knowledge item is public_policy_web", item is not None and item.source_type == "public_policy_web", getattr(item, "source_type", None) or "missing"),
                (
                    "policy_ingest workflow completed",
                    workflow is not None and workflow.workflow_type == "policy_ingest" and workflow.status == "completed" and workflow.current_node == "index_completed",
                    f"{getattr(workflow, 'workflow_type', None)} {getattr(workflow, 'status', None)} {getattr(workflow, 'current_node', None)}",
                ),
                ("chunks generated", bool(chunks), str(len(chunks))),
                ("chunk exposes public_policy", first_chunk is not None and first_chunk.source_type == "public_policy", getattr(first_chunk, "source_type", None) or "missing"),
                (
                    "publication_date extracted",
                    first_chunk is not None and first_chunk.metadata.get("publication_date") == "2026-05-01",
                    str(first_chunk.metadata.get("publication_date") if first_chunk else None),
                ),
                (
                    "source label preserved",
                    first_chunk is not None and first_chunk.metadata.get("issuing_authority") == SOURCE_LABEL,
                    str(first_chunk.metadata.get("issuing_authority") if first_chunk else None),
                ),
                (
                    "parser chain preserved",
                    first_chunk is not None and first_chunk.metadata.get("metadata", {}).get("parser_chain") == ["carbonrag-html:success"],
                    str(first_chunk.metadata.get("metadata", {}).get("parser_chain") if first_chunk else None),
                ),
                (
                    "boilerplate filtered",
                    first_chunk is not None and "\u4e0d\u5e94\u8fdb\u5165\u6b63\u6587" not in first_chunk.snippet,
                    first_chunk.snippet if first_chunk else "missing",
                ),
                ("public retrieval returns indexed policy chunk", retrieval_hit, str([(hit.knowledge_item_id, hit.score) for hit in result.hits])),
            ]
        )

    failed = False
    for label, passed, detail in checks:
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {label}: {detail}")
        failed = failed or not passed
    return 1 if failed else 0


def _patch_service_singletons(*, service: KnowledgeService, runner: KnowledgeTaskRunner) -> None:
    runner_mod.get_knowledge_task_runner = lambda: runner
    service_mod.get_knowledge_service = lambda: service
    knowledge_pkg.get_knowledge_service = lambda: service


if __name__ == "__main__":
    raise SystemExit(main())
