## ADDED Requirements

### Requirement: Policy ingestion is showcase-ready through product surfaces
CarbonRag SHALL expose a reusable admin-facing policy ingestion source and status flow that uses the real three-stage ingestion pipeline.

#### Scenario: Admin seeds curated policy source
- **WHEN** an admin starts the curated policy source ingestion
- **THEN** CarbonRag creates or refreshes a shared `public_policy_web` knowledge item
- **AND** processes it through the existing `crawl_ingest` task and `policy_ingest` workflow
- **AND** indexes generated chunks as `public_policy` retrieval evidence

#### Scenario: Showcase source is repeatable
- **WHEN** the curated policy source ingestion is run multiple times
- **THEN** CarbonRag refreshes the same source-backed knowledge item
- **AND** does not create unbounded duplicate items

#### Scenario: Policy ingestion status is inspectable
- **WHEN** a policy source has been ingested
- **THEN** CarbonRag exposes item status, task status, workflow status, extracted policy metadata, chunk summaries, and retrieval preview data

#### Scenario: Showcase does not require live crawler dependencies
- **WHEN** the showcase-ready policy source is used
- **THEN** CarbonRag MUST NOT require Scrapy, Scrapyd, Docling, MinerU, OFDRW, or live network access

### Requirement: Policy ingestion showcase preserves default flows
CarbonRag SHALL keep existing RAG and carbon workflows unchanged unless an admin explicitly runs policy ingestion.

#### Scenario: Defaults remain unchanged
- **WHEN** policy ingestion showcase support is present but no admin ingestion action is run
- **THEN** `/ask`, RAG Lab, retrieval-only, calc, report, and session defaults continue to behave as before
