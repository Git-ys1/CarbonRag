## 1. OpenSpec And Scope Lock

- [x] 1.1 Create proposal, design, tasks, and knowledge-rag delta spec for policy three-stage ingestion.
- [x] 1.2 Validate the change and full OpenSpec set.
- [x] 1.3 Keep this change limited to optional/offline ingestion boundaries, without enabling live crawling by default.

## 2. Slice A: Offline Policy Ingestion Contracts

- [x] 2.1 Add crawler request/result contracts and official allowlist validation.
- [x] 2.2 Add `CrawlerProvider`, `FakeCrawlerProvider`, and safe disabled `ScrapyCrawlerProvider`.
- [x] 2.3 Add policy governance metadata and clause anchor normalization.
- [x] 2.4 Add optional OFD converter adapter stub.
- [x] 2.5 Add policy parser router for HTML/PDF/OFD without requiring Docling, MinerU, OFDRW, or Scrapy.

## 3. Slice B: Knowledge Compatibility

- [x] 3.1 Add `public_policy_web` knowledge source type and `crawl_ingest`/`crawl_refresh` task types.
- [x] 3.2 Preserve public retrieval compatibility by mapping policy web chunks to `public_policy`.
- [x] 3.3 Store policy metadata on chunks with additive metadata fields.

## 4. Slice C: Workflow Checkpoints

- [x] 4.1 Add policy workflow node names for crawl, staging, metadata normalization, parse, chunk, index, and completion.
- [x] 4.2 Add a `policy_ingest` workflow builder.
- [x] 4.3 Ensure policy workflow additions do not affect existing upload ingest workflows.

## 5. Slice D: Offline Verification

- [x] 5.1 Add unit tests for allowlist accept/reject behavior.
- [x] 5.2 Add unit tests for fake crawler output and disabled/unavailable Scrapy behavior.
- [x] 5.3 Add unit tests for HTML/PDF/OFD parser routing and optional dependency fallback.
- [x] 5.4 Add unit tests for policy metadata serialization and chunk metadata.
- [x] 5.5 Add integration-style fixture test for staging -> parsing -> governance -> chunks.
- [x] 5.6 Run targeted backend tests and OpenSpec validation.

## 6. Deferred Follow-Up Slices

## 6. Slice E: Scrapy Runner Smoke

- [x] 6.1 Implement a real optional Scrapy spider runner behind `ScrapyCrawlerProvider`.
- [x] 6.2 Add a local HTTP fixture smoke test proving Scrapy can crawl allowed pages.
- [x] 6.3 Keep Scrapy optional and disabled by default.
- [x] 6.4 Validate crawler tests, backend regression, OpenSpec, and PR readiness.

## 7. Deferred Follow-Up Slices

- Future: add Scrapyd deployment and scheduling docs only after local crawler boundary is stable.
- Future: add real OFDRW conversion integration after licensing and runtime shape are reviewed.
- Future: add admin UI controls for policy source catalogs after backend ingestion is validated.
