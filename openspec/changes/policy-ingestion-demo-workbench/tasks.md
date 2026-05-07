## 1. Backend Demo Service

- [ ] 1.1 Add a deterministic policy ingestion demo fixture using realistic official-policy HTML, URL, title, document number, publication date, and policy terms.
- [ ] 1.2 Add a small demo service that runs the fixture through `KnowledgeService.create_policy_item_from_crawled_document`, processes queued `crawl_ingest`, and returns item/task/workflow/chunk/retrieval status.
- [ ] 1.3 Add admin-only v1 API endpoints for run, status, and retrieval summary without enabling live crawler execution.
- [ ] 1.4 Ensure repeated demo runs refresh the same `public_policy_web` source instead of creating unbounded duplicates.

## 2. Frontend Demo Workbench

- [ ] 2.1 Add typed frontend API client functions for policy ingestion demo run/status/retrieval.
- [ ] 2.2 Add an admin-only policy ingestion demo page showing backend base URL, fixture source, run control, task/workflow status, extracted metadata, chunks, and retrieval hits.
- [ ] 2.3 Add admin navigation and routing for the demo page while preserving existing protected-route behavior.
- [ ] 2.4 Add clear in-page scope copy that the demo uses a controlled fixture and does not enable production live crawling or scheduling.

## 3. Verification

- [ ] 3.1 Extend backend tests for demo run/status/retrieval, idempotent refresh, admin auth protection, and default flow isolation.
- [ ] 3.2 Extend frontend typecheck/build coverage so missing demo metadata or empty retrieval hits do not crash the page.
- [ ] 3.3 Update `scripts/verify_policy_ingestion.py` or add a companion script to verify the demo API path from local backend.
- [ ] 3.4 Update `日志/#2/V1.3.2/开发日志.md` with demo-level verification steps and known limitations.

## 4. Validation

- [ ] 4.1 Run targeted backend tests for policy ingestion and demo endpoints.
- [ ] 4.2 Run backend full regression.
- [ ] 4.3 Run frontend typecheck and build.
- [ ] 4.4 Run `openspec validate policy-ingestion-demo-workbench --strict` and `openspec validate --all`.
- [ ] 4.5 Confirm `git diff --check` passes and no runtime artifacts, secrets, `.env`, node_modules, virtualenvs, generated DBs, or cache files are staged.
