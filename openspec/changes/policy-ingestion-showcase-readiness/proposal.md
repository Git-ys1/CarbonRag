## Why

The policy ingestion backend can already prove the three-stage flow in tests and scripts, but CarbonRag itself is not yet smooth enough to demonstrate as a product. This change makes the existing application demo-ready by wiring policy ingestion into normal admin/knowledge and RAG validation surfaces instead of creating a separate throwaway demo.

## What Changes

- Add a product-facing policy ingestion showcase path inside the existing app experience:
  - admins can seed or refresh a curated built-in showcase source from the normal knowledge/admin surface;
  - the operation uses the real `crawl_ingest` and `policy_ingest` workflow;
  - the resulting `public_policy_web` item is visible as shared demo/showcase knowledge;
  - RAG Lab can immediately retrieve it and show the evidence as `public_policy_demo`, not official policy evidence.
- Add backend APIs that expose policy ingestion source/status/workflow/chunk/retrieval state in a reusable shape, not as one-off demo-only endpoints.
- Add frontend controls and status panels in existing protected/admin surfaces rather than a separate demo island.
- Add a rehearsable “showcase script” that checks the same product path end to end for local validation.
- Keep live network crawling optional and disabled by default; the showcase seed uses a controlled built-in synthetic fixture so presentations are stable and explicitly non-official.
- Keep `/ask`, session, report, calc, and existing RAG Lab defaults unchanged unless the user explicitly runs the showcase ingestion.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `knowledge-rag`: Make policy ingestion showcase-ready through reusable admin/source/status APIs that exercise the real three-stage ingestion flow.
- `frontend-shell-settings`: Surface policy ingestion readiness inside the existing app shell/admin/RAG validation experience.

## Impact

- Backend:
  - `backend/app/api/v1/endpoints/**`
  - `backend/app/admin/**`
  - `backend/app/knowledge/**`
  - `backend/tests/**`
- Frontend:
  - `frontend/src/api/**`
  - `frontend/src/pages/**`
  - `frontend/src/router/**`
  - `frontend/src/constants/navigation.ts`
  - `frontend/src/styles/global.css`
- Scripts/docs:
  - `scripts/verify_policy_ingestion.py` or companion showcase verification script
  - `日志/#2/V1.3.2/开发日志.md`

No new mandatory runtime dependency is expected.
