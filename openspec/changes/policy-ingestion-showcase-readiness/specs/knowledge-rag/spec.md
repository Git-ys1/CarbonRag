## ADDED Requirements

### Requirement: Policy ingestion is showcase-ready through product surfaces
CarbonRag SHALL expose a reusable admin-facing policy ingestion source and status flow that uses the real three-stage ingestion pipeline.

#### Scenario: Admin seeds curated showcase source
- **WHEN** an admin starts the curated showcase source ingestion
- **THEN** CarbonRag creates or refreshes a shared `public_policy_web` knowledge item
- **AND** processes it through the existing `crawl_ingest` task and `policy_ingest` workflow
- **AND** marks the item visibility as `demo`
- **AND** indexes generated chunks as `public_policy_demo` retrieval evidence
- **AND** citations, references, and source summaries identify the source as demo/showcase rather than official policy

#### Scenario: Showcase source is repeatable
- **WHEN** the curated showcase source ingestion is run multiple times
- **THEN** CarbonRag refreshes the same source-backed knowledge item
- **AND** does not create unbounded duplicate items

#### Scenario: Synthetic showcase cannot masquerade as official
- **WHEN** the built-in showcase source is listed, ingested, indexed, or retrieved
- **THEN** CarbonRag MUST NOT expose fake official URLs, fake official authorities, fake official document numbers, or official-looking copyright strings
- **AND** matched retrieval hits MUST NOT use `public_policy` as their source type

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
