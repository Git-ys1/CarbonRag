## Why

CarbonRag already has a safe policy crawler boundary and review-first ingestion flow, but the crawler layer is still a local optional adapter. To make the policy knowledge three-stage ingestion usable in real operations, CarbonRag should formally adopt Scrapy as the official local crawler runtime and reserve Scrapyd as an optional remote daemon for deployment environments that need managed spider execution.

The user-provided second URL `https://github.com/scrapy/scrap` is not a valid GitHub repository. This change treats the intended upstream as `scrapy/scrapyd`, consistent with the previous CarbonRag crawler planning.

## What Changes

- Treat `scrapy/scrapy` as the official local crawling engine behind `ScrapyCrawlerProvider`.
- Add a `ScrapydCrawlerProvider` boundary for remote daemon scheduling and run polling.
- Keep Scrapyd optional and disabled by default.
- Add configuration for crawler backend selection:
  - `RAG_POLICY_CRAWLER_BACKEND=local_scrapy`
  - `RAG_POLICY_CRAWLER_BACKEND=scrapyd`
- Add configuration for Scrapyd endpoint and project/spider identity without storing credentials in code.
- Keep official-domain allowlist, robots, depth/page limits, download delay, timeout, and pending-review gates mandatory for both backends.
- Expose backend status in Admin policy crawler UI.
- Do not copy Scrapy or Scrapyd source code into CarbonRag; use them as open-source dependencies/adapters.

## Capabilities

### New Capabilities

- `knowledge-rag`: Policy crawler provider selection between local Scrapy and optional Scrapyd remote execution.
- `frontend-shell-settings`: Admin crawler view shows active backend, availability, remote daemon health, run id, and failure reason.

### Modified Capabilities

- `knowledge-rag`: Existing `ScrapyCrawlerProvider` becomes the default official local crawler runtime while preserving review-first ingestion.

## Impact

- Backend:
  - `backend/app/core/config.py`
  - `backend/app/knowledge/policy_ingestion.py`
  - `backend/app/knowledge/policy_live_crawler.py`
  - `backend/app/admin/**`
  - `backend/tests/test_policy_live_crawler.py`
- Frontend:
  - `frontend/src/pages/AdminPlaceholderPage/**`
  - `frontend/src/services/admin.ts`
  - `frontend/src/types/admin.ts`
- Docs / governance:
  - OpenSpec change files
  - #2 development log

## Constraints

- Do not crawl arbitrary user URLs.
- Do not bypass robots.txt.
- Do not index crawled results before admin review.
- Do not make Scrapyd a mandatory local dependency.
- Do not expose Scrapyd without admin-only API protection.
- Do not store Scrapyd credentials or tokens in the repo.
- Do not change `/ask`, RAG Lab, retrieval-only, calc, report, or session defaults.

## Upstream References

- `scrapy/scrapy`: BSD-3-Clause Python crawling/scraping framework.
- `scrapy/scrapyd`: BSD-3-Clause service daemon for running Scrapy spiders.
