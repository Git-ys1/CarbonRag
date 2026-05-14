from __future__ import annotations

import base64
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urldefrag, urlparse

import scrapy


SPIDER_NAME = "carbonrag_policy_spider"
DEFAULT_USER_AGENT = "CarbonRagPolicyCrawler/1.0 (+official-policy-knowledge)"
TEXTUAL_CONTENT_TYPES = {
    "application/json",
    "application/xml",
    "application/xhtml+xml",
    "text/html",
    "text/markdown",
    "text/plain",
    "text/xml",
}


class CarbonRagPolicySpider(scrapy.Spider):
    name = SPIDER_NAME

    def __init__(
        self,
        *,
        start_urls_json: str = "[]",
        allowed_domains_json: str = "[]",
        max_depth: str | int = 1,
        max_pages: str | int = 8,
        metadata_json: str = "{}",
        documents: list[dict[str, Any]] | None = None,
        documents_output_path: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.start_urls = _json_list(start_urls_json)
        self.seed_urls = {_canonical_url(url) for url in self.start_urls}
        self.allowed_domains = [_host(domain) for domain in _json_list(allowed_domains_json)]
        self.seed_hosts = {_host(url) for url in self.start_urls}
        self.max_depth = max(0, int(max_depth or 0))
        self.max_pages = max(1, int(max_pages or 8))
        self.metadata = _json_dict(metadata_json)
        self.documents = documents if documents is not None else []
        self.documents_output_path = documents_output_path
        self._seen_urls: set[str] = set()

    def parse(self, response):  # type: ignore[no-untyped-def]
        if len(self.documents) >= self.max_pages:
            return
        canonical_url = _canonical_url(str(response.url))
        if canonical_url in self._seen_urls:
            return
        self._seen_urls.add(canonical_url)

        content_type = _content_type(response)
        document = _document_from_response(response, content_type=content_type, metadata=self.metadata)
        if _should_capture_document(
            url=canonical_url,
            title=document.get("title"),
            content_type=content_type,
            depth=int(response.meta.get("depth", 0) or 0),
            is_seed_url=canonical_url in self.seed_urls,
        ):
            self.documents.append(document)

        current_depth = int(response.meta.get("depth", 0) or 0)
        if content_type != "text/html" or len(self.documents) >= self.max_pages or current_depth > self.max_depth:
            return
        hrefs = response.css("a::attr(href)").getall()
        hrefs.sort(key=lambda href: 0 if _looks_like_policy_url(response.urljoin(href)) else 1)
        for href in hrefs:
            absolute_url = _canonical_url(response.urljoin(href))
            if absolute_url in self._seen_urls:
                continue
            if _is_allowed_url(absolute_url, self.allowed_domains) and _is_seed_host_url(absolute_url, self.seed_hosts):
                yield response.follow(absolute_url, callback=self.parse, dont_filter=True)

    def closed(self, reason: str) -> None:
        del reason
        if not self.documents_output_path:
            return
        output_path = Path(self.documents_output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(self.documents, ensure_ascii=False, indent=2), encoding="utf-8")


def build_scrapy_settings(request: dict[str, Any]) -> dict[str, Any]:
    timeout_seconds = float(request.get("timeout_seconds") or 120.0)
    download_delay = float(request.get("download_delay_seconds") or 1.0)
    return {
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": max(0.1, download_delay),
        "AUTOTHROTTLE_MAX_DELAY": max(10.0, download_delay * 5),
        "CLOSESPIDER_PAGECOUNT": int(request.get("max_pages") or 8),
        "CLOSESPIDER_TIMEOUT": timeout_seconds,
        "CONCURRENT_REQUESTS_PER_DOMAIN": int(request.get("concurrent_requests_per_domain") or 1),
        "COOKIES_ENABLED": False,
        "DEPTH_LIMIT": max(1, int(request.get("max_depth") or 0) + 1),
        "DNSCACHE_ENABLED": True,
        "DOWNLOAD_DELAY": download_delay,
        "DOWNLOAD_MAXSIZE": 25 * 1024 * 1024,
        "DOWNLOAD_TIMEOUT": timeout_seconds,
        "DOWNLOAD_WARNSIZE": 10 * 1024 * 1024,
        "FEED_EXPORT_ENCODING": "utf-8",
        "HTTPPROXY_ENABLED": True,
        "LOG_ENABLED": False,
        "REDIRECT_ENABLED": True,
        "REQUEST_FINGERPRINTER_IMPLEMENTATION": "2.7",
        "RETRY_ENABLED": True,
        "RETRY_HTTP_CODES": [408, 429, 500, 502, 503, 504, 522, 524],
        "RETRY_TIMES": 2,
        "ROBOTSTXT_OBEY": bool(request.get("obey_robots", True)),
        "TELNETCONSOLE_ENABLED": False,
        "USER_AGENT": request.get("user_agent") or DEFAULT_USER_AGENT,
    }


def build_spider_kwargs(
    request: dict[str, Any],
    *,
    documents: list[dict[str, Any]] | None = None,
    documents_output_path: str | None = None,
) -> dict[str, Any]:
    return {
        "start_urls_json": json.dumps(list(request.get("start_urls") or []), ensure_ascii=False),
        "allowed_domains_json": json.dumps(list(request.get("allowed_domains") or []), ensure_ascii=False),
        "max_depth": str(int(request.get("max_depth") or 0)),
        "max_pages": str(int(request.get("max_pages") or 8)),
        "metadata_json": json.dumps(dict(request.get("metadata") or {}), ensure_ascii=False),
        "documents": documents,
        "documents_output_path": documents_output_path,
    }


def _document_from_response(response, *, content_type: str, metadata: dict[str, Any]) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    body = bytes(response.body or b"")
    content, transfer_encoding = _content_payload(response=response, content_type=content_type, body=body)
    title = None
    if content_type == "text/html":
        title = response.css("title::text").get()
    return {
        "url": _canonical_url(str(response.url)),
        "title": title.strip() if isinstance(title, str) and title.strip() else None,
        "content": content,
        "content_type": content_type,
        "status_code": int(getattr(response, "status", 200) or 200),
        "source_name": _source_name(str(response.url)),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            **metadata,
            "crawler_name": SPIDER_NAME,
            "response_url": str(response.url),
            "depth": response.meta.get("depth", 0),
            "content_length": len(body),
            "content_sha256": hashlib.sha256(body).hexdigest(),
            "content_transfer_encoding": transfer_encoding,
        },
    }


def _should_capture_document(*, url: str, title: Any, content_type: str, depth: int, is_seed_url: bool) -> bool:
    if not _is_textual_content_type(content_type):
        return True
    if content_type != "text/html":
        return True
    if _looks_like_listing_or_search_page(url=url, title=title):
        return False
    if is_seed_url and not (_looks_like_policy_detail_url(url) or _looks_like_policy_title(title)):
        return False
    return _looks_like_policy_detail_url(url) or _looks_like_policy_title(title)


def _looks_like_policy_url(url: str) -> bool:
    lowered = url.lower()
    tokens = (
        "/zhengce/",
        "/zcfb/",
        "/zcwj/",
        "/xxgk/",
        "/gongbao/",
        "/content/",
        "policy",
        "zcjd",
        "tzgg",
    )
    return any(token in lowered for token in tokens)


def _looks_like_policy_detail_url(url: str) -> bool:
    lowered = url.lower()
    detail_tokens = (
        "/zhengce/content/",
        "/content/",
        "/t20",
        "_",
        ".htm",
        ".html",
        ".pdf",
        ".ofd",
    )
    return _looks_like_policy_url(url) and any(token in lowered for token in detail_tokens)


def _looks_like_listing_or_search_page(*, url: str, title: Any) -> bool:
    lowered = url.lower()
    path = urlparse(lowered).path.rstrip("/")
    listing_tokens = (
        "policydocumentlibrary",
        "/search/",
        "/sousuo/",
        "search?",
        "?q=",
        "index.htm",
        "index.html",
        "/zcjd/",
    )
    if path and "." not in path.rsplit("/", 1)[-1] and not re.search(r"/t20\d{6}_", path):
        return True
    if lowered.rstrip("/").endswith(("/zhengce", "/zcfb", "/zcwj", "/xxgk", "/gongbao", "/tzgg", "/gg")):
        return True
    if any(token in lowered for token in listing_tokens):
        return True
    if not isinstance(title, str):
        return False
    normalized_title = title.strip()
    generic_titles = (
        "政策文件库",
        "政策文件",
        "政策公开",
        "政策发布",
        "搜索",
        "检索",
        "公告",
        "通知公告",
    )
    return normalized_title in generic_titles or normalized_title.endswith("政策文件库")


def _looks_like_policy_title(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    title = value.strip()
    if not title:
        return False
    tokens = ("政策", "通知", "公告", "办法", "方案", "意见", "规划", "规定", "标准", "指南", "决定")
    return any(token in title for token in tokens)


def _content_payload(*, response, content_type: str, body: bytes) -> tuple[str, str]:  # type: ignore[no-untyped-def]
    if _is_textual_content_type(content_type):
        try:
            return response.text, "text"
        except Exception:  # noqa: BLE001
            return body.decode("utf-8", errors="ignore"), "text"
    return base64.b64encode(body).decode("ascii"), "base64"


def _content_type(response) -> str:  # type: ignore[no-untyped-def]
    raw = response.headers.get("Content-Type", b"")
    if isinstance(raw, bytes):
        value = raw.decode("latin-1", errors="ignore")
    else:
        value = str(raw)
    return (value.split(";", 1)[0].strip().lower() or "application/octet-stream")


def _is_textual_content_type(content_type: str) -> bool:
    return content_type in TEXTUAL_CONTENT_TYPES or content_type.startswith("text/")


def _canonical_url(url: str) -> str:
    clean_url, _fragment = urldefrag(url)
    return clean_url


def _host(value: str) -> str:
    parsed = urlparse(value if "://" in value else f"https://{value}")
    return (parsed.hostname or value).lower().strip(".")


def _is_allowed_url(url: str, allowed_domains: list[str]) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = _host(url)
    return any(host == domain or host.endswith(f".{domain}") for domain in allowed_domains)


def _is_seed_host_url(url: str, seed_hosts: set[str]) -> bool:
    host = _host(url)
    return not seed_hosts or host in seed_hosts


def _source_name(url: str) -> str | None:
    host = _host(url)
    if "ndrc.gov.cn" in host:
        return "NDRC"
    if "mee.gov.cn" in host:
        return "MEE"
    if "miit.gov.cn" in host:
        return "MIIT"
    if "beijing.gov.cn" in host:
        return "Beijing Government"
    if "gov.cn" in host:
        return "Gov.cn"
    return None


def _json_list(value: str) -> list[str]:
    try:
        parsed = json.loads(value or "[]")
    except json.JSONDecodeError:
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def _json_dict(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
