from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the optional CarbonRag policy Scrapy crawler.")
    parser.add_argument("--request", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    request = json.loads(Path(args.request).read_text(encoding="utf-8"))
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    documents = _crawl(request)
    output_path.write_text(json.dumps(documents, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


def _crawl(request: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        from scrapy.crawler import CrawlerProcess
        from app.knowledge.policy_scrapy_spider import (
            CarbonRagPolicySpider,
            build_scrapy_settings,
            build_spider_kwargs,
        )
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("Scrapy is not installed. Install backend dependency `scrapy` first.") from exc

    documents: list[dict[str, Any]] = []
    process = CrawlerProcess(settings=build_scrapy_settings(request))
    process.crawl(CarbonRagPolicySpider, **build_spider_kwargs(request, documents=documents))
    process.start()
    return documents[: int(request.get("max_pages") or 8)]


if __name__ == "__main__":
    raise SystemExit(main())
