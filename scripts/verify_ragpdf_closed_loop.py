from __future__ import annotations

import argparse
import json
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

import app.knowledge as knowledge_pkg  # noqa: E402
import app.knowledge.runner as runner_mod  # noqa: E402
import app.knowledge.service as service_mod  # noqa: E402
import app.retrieval.private_retriever as private_retriever_mod  # noqa: E402
from app.auth.service import AuthService  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.knowledge.runner import KnowledgeTaskRunner  # noqa: E402
from app.knowledge.service import KnowledgeService  # noqa: E402
from app.knowledge.store import KnowledgeStore  # noqa: E402
from app.rag.schemas import RagQueryParams  # noqa: E402
from app.rag.service import RagEngineService  # noqa: E402
from app.retrieval.private_retriever import PrivateSampleRetriever  # noqa: E402
from app.retrieval.schemas import RetrievalResult  # noqa: E402
from app.session.adapters.sqlite_store import SQLiteSessionStore  # noqa: E402


QUERY = "carbon accounting energy saving report"


@dataclass(frozen=True)
class FixtureFile:
    path: Path
    mime_type: str
    query_terms: tuple[str, ...]


class NoBootstrapKnowledgeService(KnowledgeService):
    def bootstrap_shared_library(self):  # type: ignore[override]
        return []


class FakeSessionService:
    knowledge_service = None


class EmptySearchRetriever:
    chunks: list = []

    def search(self, *, question: str, top_k: int = 5, **_: Any) -> RetrievalResult:
        return RetrievalResult(query=question, top_k=top_k, total_hits=0, hits=[])


def run_closed_loop(*, include_optional_pdf: bool = True) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="carbonrag-ragpdf-loop-", ignore_cleanup_errors=True) as temp_dir:
        temp_root = Path(temp_dir)
        fixture_dir = temp_root / "fixtures"
        fixture_dir.mkdir(parents=True, exist_ok=True)
        fixtures = _write_fixture_files(fixture_dir, include_optional_pdf=include_optional_pdf)

        store = KnowledgeStore(sqlite_db_path=temp_root / "carbonrag.sqlite3")
        owner_user_id = AuthService(sqlite_db_path=temp_root / "carbonrag.sqlite3").register(
            {
                "username": "ragpdf-loop-user",
                "password": "pass123456",
            }
        ).user_id
        session_store = SQLiteSessionStore(temp_root / "carbonrag.sqlite3")
        session_id = "ragpdf-loop-session"
        created_at = datetime.now(timezone.utc).isoformat()
        session_store.create_session(
            session_id=session_id,
            owner_user_id=owner_user_id,
            title="ragPdfSystem closed loop verification",
            created_at=created_at,
        )
        runner = KnowledgeTaskRunner()
        service = NoBootstrapKnowledgeService(store=store, session_service=FakeSessionService())

        with _patched_singletons(service=service, runner=runner):
            tasks = []
            for index, fixture in enumerate(fixtures, start=1):
                payload = session_store.create_uploaded_file(
                    file_id=f"ragpdf-loop-{index:02d}",
                    session_id=session_id,
                    filename=fixture.path.name,
                    size=fixture.path.stat().st_size,
                    mime_type=fixture.mime_type,
                    stored_at=datetime.now(timezone.utc).isoformat(),
                    storage_path=str(fixture.path),
                )
                tasks.append(
                    service.create_personal_item_from_upload(
                        owner_user_id=owner_user_id,
                        uploaded_file=payload.model_dump(),
                        storage_path=str(fixture.path),
                    )
                )

            processed_task_ids = runner.run_once()
            item_reports = []
            item_ids = []
            total_chunks = 0
            for task in tasks:
                item = store.get_item(task.knowledge_item_id or "")
                chunks = store.list_chunks(task.knowledge_item_id or "")
                refreshed_task = store.get_task(task.task_id)
                if item is not None:
                    item_ids.append(item.knowledge_item_id)
                total_chunks += len(chunks)
                item_reports.append(
                    {
                        "task_id": task.task_id,
                        "processed": task.task_id in processed_task_ids,
                        "task_status": refreshed_task.status if refreshed_task else None,
                        "knowledge_item_id": item.knowledge_item_id if item else None,
                        "title": item.title if item else None,
                        "source_type": item.source_type if item else None,
                        "parse_status": item.parse_status if item else None,
                        "ingest_status": item.ingest_status if item else None,
                        "index_status": item.index_status if item else None,
                        "chunk_count": len(chunks),
                        "first_chunk_metadata": chunks[0].metadata if chunks else {},
                    }
                )

            private_retriever = PrivateSampleRetriever()
            settings = get_settings().model_copy(
                update={
                    "rag_engine_enabled": True,
                    "rag_vector_enabled": False,
                    "rag_vector_backend": "current",
                }
            )
            rag_service = RagEngineService(
                settings=settings,
                public_retriever=EmptySearchRetriever(),  # type: ignore[arg-type]
                private_retriever=private_retriever,
                mixed_retriever=EmptySearchRetriever(),  # type: ignore[arg-type]
            )
            retrieval = rag_service.retrieve(
                RagQueryParams(
                    question=QUERY,
                    knowledge_scope="private_sample",
                    mode="mix",
                    top_k=5,
                    allowed_knowledge_item_ids=item_ids,
                    retrieval_strategy="bm25_only",
                )
            )

            checks = {
                "tasks_processed": len(processed_task_ids) == len(tasks),
                "items_indexed": all(item["index_status"] == "indexed" for item in item_reports),
                "chunks_generated": total_chunks >= len(fixtures),
                "retrieval_hit": retrieval.total_hits > 0,
                "references_returned": len(retrieval.references) > 0,
            }
            return {
                "status": "passed" if all(checks.values()) else "failed",
                "change_id": "ragpdf-parser-chunker-adapter",
                "query": QUERY,
                "checks": checks,
                "fixtures": [
                    {
                        "filename": fixture.path.name,
                        "mime_type": fixture.mime_type,
                        "query_terms": list(fixture.query_terms),
                    }
                    for fixture in fixtures
                ],
                "processed_task_ids": processed_task_ids,
                "items": item_reports,
                "retrieval": {
                    "total_hits": retrieval.total_hits,
                    "metadata": retrieval.metadata.model_dump(mode="json"),
                    "chunks": [chunk.model_dump(mode="json") for chunk in retrieval.chunks],
                    "references": [reference.model_dump(mode="json") for reference in retrieval.references],
                },
            }


def format_report(report: dict[str, Any]) -> str:
    lines = [
        f"Status: {report['status']}",
        f"Change: {report['change_id']}",
        f"Query: {report['query']}",
        "",
        "Checks:",
    ]
    for name, passed in report["checks"].items():
        lines.append(f"- {'PASS' if passed else 'FAIL'} {name}")
    lines.extend(["", "Indexed files:"])
    for item in report["items"]:
        lines.append(
            "- {title}: task={task_status}, parse={parse_status}, ingest={ingest_status}, "
            "index={index_status}, chunks={chunk_count}".format(**item)
        )
    lines.extend(["", f"Retrieval hits: {report['retrieval']['total_hits']}"])
    for chunk in report["retrieval"]["chunks"][:3]:
        lines.append(f"- {chunk['title']} :: {chunk['snippet'][:120]}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify ragPdfSystem-inspired CarbonRag ingest-to-retrieval loop.")
    parser.add_argument("--json", action="store_true", help="Print the full JSON report.")
    parser.add_argument("--no-pdf", action="store_true", help="Skip the optional generated PDF fixture.")
    args = parser.parse_args(argv)

    report = run_closed_loop(include_optional_pdf=not args.no_pdf)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_report(report))
    return 0 if report["status"] == "passed" else 1


def _write_fixture_files(root: Path, *, include_optional_pdf: bool) -> list[FixtureFile]:
    html = root / "dual_carbon_policy.html"
    html.write_text(
        """
        <html>
          <head><title>Dual Carbon Policy Brief</title></head>
          <body>
            <h1>Dual Carbon Policy Brief</h1>
            <p>Carbon accounting and energy saving retrofits are key actions for small enterprises.</p>
            <p>Reports should cite policy evidence, implementation region, and expected emission reduction.</p>
          </body>
        </html>
        """,
        encoding="utf-8",
    )
    csv = root / "enterprise_energy.csv"
    csv.write_text(
        "facility,measure,annual_saving\n"
        "office,lighting energy saving retrofit,12000 kWh\n"
        "boiler,carbon accounting baseline,8 tCO2e\n",
        encoding="utf-8",
    )
    markdown = root / "report_outline.md"
    markdown.write_text(
        "# Carbon Report Outline\n\n"
        "The project report background should describe dual carbon policy, enterprise application, "
        "carbon accounting, subsidy readiness, and energy saving measures.\n",
        encoding="utf-8",
    )
    fixtures = [
        FixtureFile(html, "text/html", ("carbon accounting", "energy saving")),
        FixtureFile(csv, "text/csv", ("lighting", "carbon accounting")),
        FixtureFile(markdown, "text/markdown", ("report", "dual carbon")),
    ]
    if include_optional_pdf:
        pdf_fixture = _try_write_pdf_fixture(root)
        if pdf_fixture is not None:
            fixtures.append(pdf_fixture)
    return fixtures


def _try_write_pdf_fixture(root: Path) -> FixtureFile | None:
    try:
        from reportlab.pdfgen import canvas
    except Exception:  # noqa: BLE001
        return None

    pdf = root / "policy_reference.pdf"
    c = canvas.Canvas(str(pdf))
    c.drawString(72, 760, "Policy Reference")
    c.drawString(72, 735, "Carbon accounting evidence supports energy saving project reports.")
    c.drawString(72, 710, "Enterprises should keep source documents and emission reduction metadata.")
    c.save()
    return FixtureFile(pdf, "application/pdf", ("carbon accounting", "evidence"))


@contextmanager
def _patched_singletons(*, service: KnowledgeService, runner: KnowledgeTaskRunner) -> Iterator[None]:
    original_runner = runner_mod.get_knowledge_task_runner
    original_service_mod = service_mod.get_knowledge_service
    original_knowledge_pkg = knowledge_pkg.get_knowledge_service
    original_private_get_service = private_retriever_mod.get_knowledge_service
    try:
        runner_mod.get_knowledge_task_runner = lambda: runner
        service_mod.get_knowledge_service = lambda: service
        knowledge_pkg.get_knowledge_service = lambda: service
        private_retriever_mod.get_knowledge_service = lambda: service
        yield
    finally:
        runner_mod.get_knowledge_task_runner = original_runner
        service_mod.get_knowledge_service = original_service_mod
        knowledge_pkg.get_knowledge_service = original_knowledge_pkg
        private_retriever_mod.get_knowledge_service = original_private_get_service


if __name__ == "__main__":
    raise SystemExit(main())
