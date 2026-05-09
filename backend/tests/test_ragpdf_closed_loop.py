from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.verify_ragpdf_closed_loop import format_report, run_closed_loop


def test_ragpdf_closed_loop_indexes_and_retrieves_fixture_documents() -> None:
    report = run_closed_loop(include_optional_pdf=False)

    assert report["status"] == "passed"
    assert report["checks"]["tasks_processed"] is True
    assert report["checks"]["items_indexed"] is True
    assert report["checks"]["chunks_generated"] is True
    assert report["checks"]["retrieval_hit"] is True
    assert report["retrieval"]["total_hits"] >= 1
    assert report["retrieval"]["references"]
    assert {item["source_type"] for item in report["items"]} == {"uploaded_file"}
    assert all(item["chunk_count"] >= 1 for item in report["items"])


def test_ragpdf_closed_loop_report_is_human_readable() -> None:
    report = run_closed_loop(include_optional_pdf=False)

    rendered = format_report(report)

    assert "Status: passed" in rendered
    assert "Checks:" in rendered
    assert "Indexed files:" in rendered
    assert "Retrieval hits:" in rendered
