## Why

The policy three-stage ingestion foundation can be verified through backend tests and scripts, but it is not yet easy to demonstrate to a reviewer or stakeholder from the running application. This change creates a small, controlled demo path so CarbonRag can show policy collection, parsing, governance metadata, indexing, and retrieval without enabling production crawling.

## What Changes

- Add a demo-only policy ingestion workbench that can seed one or more built-in official-policy fixture documents into the existing `crawl_ingest` flow.
- Add backend demo endpoints for starting the fixture ingestion, reading the latest demo status, and querying demo retrieval results.
- Add a frontend workbench panel reachable from the protected app shell for admins, showing:
  - backend base URL and demo mode status;
  - fixture source title, URL, stage/task/workflow status;
  - extracted policy metadata, generated chunks, and retrieval hits.
- Keep live Scrapy crawling disabled by default and do not introduce Docling, MinerU, OFDRW, Scrapyd, or external network crawling as required demo dependencies.
- Keep `/ask`, RAG Lab, retrieval-only, calc, report, and session defaults unchanged.
- Extend the stable verification script and tests so the demo path can be rehearsed before showing the app.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `knowledge-rag`: Add a demo-mode policy ingestion scenario that exercises existing policy three-stage ingestion through a controlled fixture and exposes traceable demo status.
- `frontend-shell-settings`: Add an admin-facing policy ingestion demo workbench entry that visualizes the controlled fixture ingestion flow.

## Impact

- Backend:
  - `backend/app/api/v1/endpoints/**`
  - `backend/app/knowledge/**`
  - `backend/tests/**`
- Frontend:
  - `frontend/src/pages/**`
  - `frontend/src/api/**`
  - `frontend/src/router/**`
  - `frontend/src/constants/navigation.ts`
  - `frontend/src/styles/global.css`
- Scripts/docs:
  - `scripts/verify_policy_ingestion.py`
  - `日志/#2/V1.3.2/开发日志.md`

No new mandatory runtime dependency is expected.
