## Context

The archived `policy-knowledge-three-stage-ingestion` change provides backend contracts and a verified service-layer ingestion path:

`CrawledDocument -> stage -> parse -> normalize metadata -> build chunks -> index -> public retrieval`.

The current gap is presentation. A stakeholder cannot yet open the running app and watch this flow happen, because there is no route, endpoint, or UI control dedicated to a safe demo. The demo must not enable live crawling by default, must not depend on Scrapy/Docling/MinerU/OFD tooling, and must not alter the default ask/RAG/calc/report flows.

## Goals / Non-Goals

**Goals:**
- Provide an admin-only demo workbench that seeds a built-in policy fixture through the existing `crawl_ingest` service path.
- Show task, item, workflow, metadata, chunk, and retrieval status in a way that is easy to explain during a live demo.
- Keep the demo deterministic, offline-capable, and repeatable.
- Preserve existing policy ingestion boundaries so this is a thin demo layer, not a second ingestion implementation.

**Non-Goals:**
- No production crawler source management.
- No live official website crawling as the default demo path.
- No Scrapyd scheduling.
- No Docling/MinerU/OFDRW installation requirement.
- No changes to `/ask`, RAG Lab default behavior, retrieval-only default behavior, calc, report, or session flows.

## Decisions

### Decision 1: Use Built-In Fixtures For The First Demo

The demo entrypoint SHALL seed one or more curated HTML policy fixtures represented as `CrawledDocument` payloads.

Rationale:
- This avoids network instability and official-site template drift during demos.
- It exercises the same service path as real crawler results.
- It avoids enabling live crawling before admin source controls exist.

Alternative considered: call `ScrapyCrawlerProvider` from the demo button. This is deferred because it depends on optional packages, network availability, robots behavior, and allowlist configuration.

### Decision 2: Add A Small Admin API Surface

Add a minimal backend API under the existing v1 router, guarded by admin auth:

- `POST /api/v1/policy-ingestion-demo/run`
- `GET /api/v1/policy-ingestion-demo/status`
- `GET /api/v1/policy-ingestion-demo/retrieval`

Rationale:
- Keeps demo operations explicit and inspectable.
- Reuses existing `KnowledgeService.create_policy_item_from_crawled_document` and task runner.
- Avoids placing demo-only behavior inside RAG Lab retrieval endpoints.

### Decision 3: Add A Dedicated Demo Workbench Page

Add an admin-only frontend page, for example `/policy-ingestion-demo`, with a navigation entry visible to admins.

Rationale:
- The demo has a different story than RAG Lab: it is about ingestion, not only retrieval.
- A dedicated page can show the pipeline steps, task status, extracted metadata, chunks, and retrieval hits without crowding existing lab UI.

### Decision 4: Keep The Demo Idempotent

Running the demo repeatedly SHALL refresh the same fixture-backed `public_policy_web` item instead of creating unbounded duplicates.

Rationale:
- Demo rehearsals should not pollute the local runtime database.
- Existing source URL based refresh behavior already supports this shape.

## Risks / Trade-offs

- [Risk] A demo fixture can look synthetic and less impressive than a real government page. → Use realistic official-style title, source URL, document number, publication date, clause text, and policy vocabulary.
- [Risk] Adding admin UI can imply production crawler support. → Label the page as a demo fixture flow and state that live crawler source management is not enabled.
- [Risk] Running ingestion from a request can look like the earlier “retrieval triggers ingest” anti-pattern. → Keep it behind an explicit admin demo run endpoint, not inside `/ask` or retrieval.
- [Risk] Frontend/backend state can drift if task processing is asynchronous. → First version may call existing queued-task processing synchronously from the explicit demo endpoint and return status, while still recording the task/workflow.
