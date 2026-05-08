from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


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
        import scrapy
        from scrapy.crawler import CrawlerProcess
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("Scrapy is not installed. Install optional dependency `scrapy` first.") from exc

    documents: list[dict[str, Any]] = []
    max_pages = int(request.get("max_pages") or 50)
    start_urls = list(request.get("start_urls") or [])
    allowed_domains = list(request.get("allowed_domains") or [])

    class PolicySpider(scrapy.Spider):
        name = "carbonrag_policy_spider"
        custom_settings = {
            "LOG_ENABLED": False,
            "ROBOTSTXT_OBEY": bool(request.get("obey_robots", True)),
            "DOWNLOAD_DELAY": float(request.get("download_delay_seconds") or 0.0),
            "CONCURRENT_REQUESTS_PER_DOMAIN": int(request.get("concurrent_requests_per_domain") or 2),
            "DEPTH_LIMIT": int(request.get("max_depth") or 0),
            "CLOSESPIDER_PAGECOUNT": max_pages,
            "USER_AGENT": request.get("user_agent") or "CarbonRagPolicyCrawler/1.0 (+admin-reviewed)",
            "REQUEST_FINGERPRINTER_IMPLEMENTATION": "2.7",
        }

        def __init__(self) -> None:
            super().__init__()
            self.start_urls = start_urls
            self.allowed_domains = [_host(domain) for domain in allowed_domains]

        def parse(self, response):  # type: ignore[no-untyped-def]
            if len(documents) >= max_pages:
                return
            content_type = _content_type(response)
            body_text = _response_text(response)
            title = None
            if content_type == "text/html":
                title = response.css("title::text").get()
                for href in response.css("a::attr(href)").getall():
                    absolute_url = response.urljoin(href)
                    if _is_allowed_url(absolute_url, self.allowed_domains):
                        yield response.follow(absolute_url, callback=self.parse)

            documents.append(
                {
                    "url": str(response.url),
                    "title": title.strip() if isinstance(title, str) and title.strip() else None,
                    "content": body_text,
                    "content_type": content_type,
                    "status_code": int(getattr(response, "status", 200) or 200),
                    "source_name": _source_name(response.url),
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "metadata": {
                        "crawler_name": self.name,
                        "response_url": str(response.url),
                        "depth": response.meta.get("depth", 0),
                    },
                }
            )

    process = CrawlerProcess()
    process.crawl(PolicySpider)
    process.start()
    return documents[:max_pages]


def _content_type(response) -> str:  # type: ignore[no-untyped-def]
    raw = response.headers.get("Content-Type", b"")
    if isinstance(raw, bytes):
        value = raw.decode("latin-1", errors="ignore")
    else:
        value = str(raw)
    return (value.split(";", 1)[0].strip().lower() or "application/octet-stream")


def _response_text(response) -> str:  # type: ignore[no-untyped-def]
    try:
        return response.text
    except Exception:  # noqa: BLE001
        return response.body.decode("utf-8", errors="ignore")


def _host(value: str) -> str:
    parsed = urlparse(value if "://" in value else f"https://{value}")
    return (parsed.hostname or value).lower().strip(".")


def _is_allowed_url(url: str, allowed_domains: list[str]) -> bool:
    host = _host(url)
    return any(host == domain or host.endswith(f".{domain}") for domain in allowed_domains)


def _source_name(url: str) -> str | None:
    host = _host(url)
    if "ndrc.gov.cn" in host:
        return "国家发展和改革委员会"
    if "mee.gov.cn" in host:
        return "生态环境部"
    if "miit.gov.cn" in host:
        return "工业和信息化部"
    if "beijing.gov.cn" in host:
        return "北京市人民政府"
    if "gov.cn" in host:
        return "中国政府网"
    return None


if __name__ == "__main__":
    raise SystemExit(main())
