## Why

CarbonRag can already ingest a controlled synthetic policy showcase source, but it still cannot operate a real official-policy source catalog safely. The next step is to add a live crawler control plane that can fetch only allowlisted official sources, stage results as review candidates, and let an admin publish accepted documents into the existing policy ingestion pipeline.

This change intentionally follows #1's constrained approval: live public crawling is not automatically enabled by default. The default product behavior is safe/manual; scheduled crawling is only a configurable future-ready capability.

## What Changes

- Add a live policy crawler control plane:
  - official source catalog with strict allowlist validation;
  - crawl run records with availability, status, counts, and errors;
  - pending review candidates produced from crawl results;
  - admin publish/reject actions for candidates.
- Add a lightweight `PolicyCrawlerScheduler` boundary:
  - starts safely with the app but defaults to manual mode;
  - prevents re-entrant runs;
  - supports future scheduled runs only when explicitly configured;
  - degrades to `unavailable` when Scrapy is not installed or disabled.
- Add runtime persistence for:
  - `policy_crawl_sources`;
  - `policy_crawl_runs`;
  - `policy_crawl_candidates`.
- Add admin APIs and UI for:
  - source list and status;
  - manual run trigger;
  - run history;
  - candidate list;
  - publish/reject review.
- Keep `/ask`, RAG Lab, retrieval-only, calc, report, and session defaults unchanged. Crawled candidates are not searchable until an admin publishes them.

## Capabilities

### New Capabilities

- `knowledge-rag`: Official-policy live crawler candidates are staged for admin review before indexing.
- `frontend-shell-settings`: Admin UI exposes live crawler sources, runs, candidates, and review actions.

### Modified Capabilities

- `knowledge-rag`: Policy ingestion gains a safe live-source control plane while preserving the existing disabled-by-default crawler boundary and review-first behavior.

## Impact

- Backend:
  - `backend/app/core/config.py`
  - `backend/app/main.py`
  - `backend/app/runtime_db/schema.py`
  - `backend/app/knowledge/**`
  - `backend/app/admin/**`
  - `backend/app/api/v1/endpoints/admin.py`
  - `backend/tests/**`
- Frontend:
  - `frontend/src/services/admin.ts`
  - `frontend/src/types/admin.ts`
  - `frontend/src/pages/AdminPlaceholderPage/**`
- Scripts/docs:
  - `scripts/verify_policy_live_crawler.py`
  - `日志/#2/V1.3.4/开发日志.md`

No new mandatory dependency is introduced. Scrapy remains optional.
