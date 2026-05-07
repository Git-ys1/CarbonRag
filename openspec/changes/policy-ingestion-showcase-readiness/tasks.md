## 1. Backend Showcase Source

- [ ] 1.1 Add a curated built-in official-policy source fixture with realistic HTML, URL, title, document number, publication date, source label, and carbon-policy terms.
- [ ] 1.2 Add reusable backend service methods for listing showcase policy sources, running/refreshing the curated source through `crawl_ingest`, and reading item/task/workflow/chunk status.
- [ ] 1.3 Add admin-gated v1 API endpoints for policy source list, run/refresh, status, chunks, and retrieval preview.
- [ ] 1.4 Ensure repeated runs refresh the same `public_policy_web` item and do not create unbounded duplicates.

## 2. Product UI Integration

- [ ] 2.1 Add typed frontend API functions and response types for policy source list, run/refresh, status, chunks, and retrieval preview.
- [ ] 2.2 Integrate policy ingestion controls/status into an existing admin or knowledge management surface instead of a standalone demo page.
- [ ] 2.3 Show the ingestion pipeline as product state: source, task status, workflow status, extracted metadata, chunks, and source URL.
- [ ] 2.4 Add a retrieval validation path from the existing RAG surface so the indexed policy can be queried and shown as `public_policy` evidence.
- [ ] 2.5 Make the UI clear that the curated source is built-in/offline and live crawler scheduling is not enabled yet.

## 3. Verification

- [ ] 3.1 Add backend tests for source list, run/refresh, status, chunks, retrieval preview, idempotency, admin protection, and default flow isolation.
- [ ] 3.2 Add frontend typecheck/build coverage so missing policy metadata, empty chunks, or empty retrieval hits do not crash the integrated UI.
- [ ] 3.3 Update `scripts/verify_policy_ingestion.py` or add a showcase verification script for the product API path.
- [ ] 3.4 Update `日志/#2/V1.3.2/开发日志.md` with showcase-level verification steps and known limitations.

## 4. Validation

- [ ] 4.1 Run targeted backend tests for policy ingestion and showcase endpoints.
- [ ] 4.2 Run backend full regression.
- [ ] 4.3 Run frontend typecheck and build.
- [ ] 4.4 Run `openspec validate policy-ingestion-showcase-readiness --strict` and `openspec validate --all`.
- [ ] 4.5 Confirm `git diff --check` passes and no runtime artifacts, secrets, `.env`, node_modules, virtualenvs, generated DBs, or cache files are staged.
