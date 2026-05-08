## Context

`policy-knowledge-three-stage-ingestion` established the backend flow:

`CrawledDocument -> stage -> parse -> normalize metadata -> build chunks -> index -> public retrieval`.

The remaining product gap is not a lack of core logic; it is that a reviewer cannot use the running app to understand the capability. A separate “demo page” would prove the code path, but it would not make CarbonRag itself feel ready. The better path is to expose a small, reusable policy ingestion source/status surface through the existing admin/knowledge/RAG validation experience.

## Goals / Non-Goals

**Goals:**
- Make policy ingestion demonstrable from the running product without requiring live network crawling.
- Use real `public_policy_web`, `crawl_ingest`, `policy_ingest`, chunk indexing, and public retrieval while marking the built-in sample as demo/showcase evidence.
- Let an admin start a curated policy source seed/refresh from an existing app surface.
- Let the user see item/task/workflow/chunk/retrieval evidence without reading logs.
- Keep the path repeatable and idempotent for rehearsals.

**Non-Goals:**
- No production crawler scheduler.
- No arbitrary URL crawler UI.
- No default live crawling.
- No mandatory Scrapy/Scrapyd/Docling/MinerU/OFDRW dependency.
- No changes to normal `/ask`, session, report, calc, or default RAG Lab behavior.

## Decisions

### Decision 1: Build A Showcase-Ready Synthetic Source, Not A Separate Demo Island

The first演示级 implementation SHALL add a curated built-in synthetic showcase source to the policy ingestion controls. It is a real `public_policy_web` item after ingestion, not an isolated demo object, but it MUST use demo visibility and retrieval source type `public_policy_demo`.

The built-in showcase source MUST NOT use a fake official URL, official agency, fake official document number, or official-looking copyright. Any citations, references, retrieval preview hits, or source summary counts from this source MUST clearly identify it as demo/showcase material rather than official public policy evidence.

Rationale:
- The user wants the project itself to be demonstrable.
- A seeded synthetic source makes presentations deterministic without polluting official policy evidence.
- The same surface can later expand into real source catalogs.

### Decision 2: Reuse Existing Admin/Knowledge And RAG Lab Surfaces

The frontend SHOULD add policy ingestion controls/status to existing admin or knowledge management pages, and retrieval validation to RAG Lab or a nearby existing RAG surface.

Rationale:
- This makes the feature feel like part of CarbonRag.
- It avoids a one-off page that will be thrown away.
- It matches the story: ingest policy knowledge, then retrieve it.

### Decision 3: Keep Backend APIs Reusable

Backend endpoints SHOULD use product-oriented names such as policy sources, ingestion run, status, workflow, chunks, and retrieval preview. They MUST remain admin-gated for state-changing ingestion.

Rationale:
- Later production source catalogs can build on the same API shape.
- Demo readiness and product readiness move in the same direction.

### Decision 4: Keep Showcase Seed Offline And Idempotent

The built-in seed source SHALL not require network access and SHALL refresh the same source URL based knowledge item on repeated runs.

Rationale:
- A live presentation should not fail because an official website is slow or unavailable.
- Repeated rehearsals should not pollute the database.

## Risks / Trade-offs

- [Risk] A fixture-backed source may be mistaken for live crawling. → Label it as a curated built-in synthetic showcase seed and keep live crawler controls disabled unless explicitly configured in a later change.
- [Risk] A synthetic fixture may be mistaken for official policy. → Use demo URL/source/metadata, index it as `public_policy_demo`, and show explicit non-official labeling in UI/API/tests.
- [Risk] Adding controls to existing pages can clutter the UI. → Keep the first version compact: run/refresh, status, metadata, chunks, retrieval preview.
- [Risk] Triggering ingestion from the UI can resemble the prior anti-pattern of retrieval triggering ingest. → Only explicit admin ingestion actions may run tasks; retrieval and `/ask` do not trigger ingestion.
- [Risk] The showcase might overpromise production readiness. → Show known limitations in UI/docs: no scheduler, no arbitrary URLs, no required Docling/MinerU/OFD production parser chain yet.
