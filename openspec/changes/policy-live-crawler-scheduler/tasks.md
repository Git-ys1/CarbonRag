## 1. OpenSpec And Governance

- [x] 1.1 Add proposal, design, tasks, and spec deltas for `policy-live-crawler-scheduler`.
- [x] 1.2 Record #1 constrained ACK in implementation notes: manual/default disabled live crawling, review-first candidates, optional scheduled mode only by explicit config.
- [x] 1.3 Validate `openspec validate policy-live-crawler-scheduler --strict` and `openspec validate --all`.

## 2. Backend Persistence And Scheduler Boundary

- [x] 2.1 Add runtime schema for `policy_crawl_sources`, `policy_crawl_runs`, and `policy_crawl_candidates` in SQLite and PostgreSQL bootstrap paths.
- [x] 2.2 Add settings for manual/default crawler mode, optional scheduled mode, conservative Scrapy limits, timeout, and user-agent.
- [x] 2.3 Add `PolicyCrawlerScheduler` with startup/shutdown hooks, non-reentrant execution, status reporting, and safe `unavailable` state when Scrapy is missing or disabled.
- [x] 2.4 Seed official allowlisted sources idempotently without triggering live network fetches during startup.

## 3. Backend Review Flow And API

- [x] 3.1 Add service methods for listing sources, manually running one source, listing runs, listing candidates, publishing a candidate, and rejecting a candidate.
- [x] 3.2 Ensure crawl results create only `pending_review` candidates and do not create `public_policy_web` items before publish.
- [x] 3.3 Publish candidate through existing `create_policy_item_from_crawled_document` and `crawl_ingest`; reject candidate without indexing.
- [x] 3.4 Add admin-gated v1 endpoints for source list, run trigger, runs, candidates, publish, and reject.
- [x] 3.5 Preserve `/ask`, RAG Lab, retrieval-only, calc, report, and session defaults.

## 4. Frontend Admin UI

- [x] 4.1 Add typed admin API client functions and response types for live crawler source/run/candidate/review operations.
- [x] 4.2 Add Admin UI section for live policy crawler status, source list, manual run, recent runs, and pending candidates.
- [x] 4.3 Show unavailable/failed/pending/published/rejected states without crashing when fields are missing.
- [x] 4.4 Clearly state that automatic public crawling is disabled by default and candidates require admin review before retrieval.

## 5. Tests And Verification

- [x] 5.1 Add backend tests for allowlist validation, unavailable Scrapy fallback, non-reentrant scheduler, candidate staging, publish, reject, and retrieval isolation before publish.
- [x] 5.2 Add admin API tests for authorization and review actions.
- [x] 5.3 Add frontend typecheck/build coverage for crawler UI data shapes.
- [x] 5.4 Add or update a smoke verification script for the admin live crawler path without live network dependency.
- [x] 5.5 Run targeted tests, full backend regression, frontend typecheck/build, OpenSpec validation, `git diff --check`, and `gitnexus detect_changes`.

## 6. PR Readiness

- [x] 6.1 Update `日志/#2/V1.3.4/开发日志.md` with scope, #1 constraints, validation, and known limitations.
- [x] 6.2 Post Mattermost `CHANGED` and `REVIEW_READY` with GitNexus/OpenSpec/test results.
- [x] 6.3 Commit, push to #2 fork, and open PR to `Git-ys1/CarbonRag:main` with version `V1.3.4`.
