# Tasks

## 1. Upstream And Boundary Confirmation

- [x] 1.1 Record `scrapy/scrapy` and intended `scrapy/scrapyd` upstream roles and licenses in task notes / development log.
- [x] 1.2 Confirm current `ScrapyCrawlerProvider`, `PolicySpider`, `PolicyCrawlerScheduler`, and pending-review publish flow with GitNexus impact before editing.
- [x] 1.3 Keep `scrapy/scrap` typo documented as invalid and avoid depending on that repository.

## 2. Backend Provider Boundary

- [x] 2.1 Add crawler backend configuration with default `local_scrapy`.
- [x] 2.2 Add `ScrapydCrawlerProvider` with `describe()` and `crawl()` methods matching existing `CrawlerProvider` protocol.
- [x] 2.3 Add Scrapyd healthcheck and schedule/poll behavior using mocked HTTP in tests.
- [x] 2.4 Ensure local Scrapy and Scrapyd both apply the same allowlist, robots, rate-limit, depth/page, timeout, and user-agent constraints.
- [x] 2.5 Ensure Scrapyd unavailable or misconfigured states do not break app startup or Admin page loading.

## 3. Admin API / UI

- [x] 3.1 Extend crawler status response with `crawler_backend`, `local_scrapy_available`, `scrapyd_available`, `scrapyd_endpoint_label`, and `external_job_id` where relevant.
- [x] 3.2 Update Admin policy crawler UI to show backend status and remote failure reasons.
- [x] 3.3 Preserve existing publish/reject behavior and pending-review gate.

## 4. Tests

- [x] 4.1 Test backend selection defaults to local Scrapy.
- [x] 4.2 Test Scrapyd disabled/unavailable does not crash startup.
- [x] 4.3 Test Scrapyd mocked successful run stages only `pending_review` candidates.
- [x] 4.4 Test non-allowlisted URL is rejected before local or remote crawl execution.
- [x] 4.5 Test unpublished candidates do not enter public retrieval and published candidates still use existing `crawl_ingest`.
- [x] 4.6 Test Admin UI handles local, scrapyd unavailable, failed, and pending states.

## 5. Validation

- [x] 5.1 Run targeted policy crawler backend tests.
- [x] 5.2 Run backend full regression.
- [x] 5.3 Run frontend typecheck/build.
- [x] 5.4 Run `openspec validate scrapy-scrapyd-policy-crawler --strict` and `openspec validate --all`.
- [x] 5.5 Run `git diff --check` and `gitnexus detect_changes`.
- [x] 5.6 Send Mattermost `CHANGED` / `REVIEW_READY` with GitNexus summary before PR.
