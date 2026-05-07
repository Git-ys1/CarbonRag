## ADDED Requirements

### Requirement: Policy ingestion demo can seed a controlled fixture
CarbonRag SHALL provide an admin-only demo entrypoint that seeds a built-in official-policy fixture through the existing policy three-stage ingestion flow.

#### Scenario: Admin runs policy ingestion demo
- **WHEN** an admin starts the policy ingestion demo
- **THEN** CarbonRag creates or refreshes a shared `public_policy_web` knowledge item from a built-in fixture
- **AND** enqueues and processes a `crawl_ingest` task through the existing `policy_ingest` workflow
- **AND** generated chunks remain exposed as `public_policy` evidence

#### Scenario: Demo does not enable live crawling
- **WHEN** the demo entrypoint is used
- **THEN** CarbonRag MUST NOT require Scrapy, Scrapyd, Docling, MinerU, OFDRW, or live network access
- **AND** `RAG_ENABLE_POLICY_CRAWLER=false` remains a valid default

#### Scenario: Demo status is inspectable
- **WHEN** the demo fixture has been run
- **THEN** CarbonRag exposes the latest demo item status, task status, workflow status, extracted policy metadata, chunk count, and retrieval hit summary

#### Scenario: Demo run is repeatable
- **WHEN** the same demo fixture is run multiple times
- **THEN** CarbonRag refreshes the fixture-backed policy knowledge item rather than creating unbounded duplicates

### Requirement: Policy ingestion demo preserves default behavior
CarbonRag SHALL keep existing user-facing RAG and carbon workflows unchanged when the policy ingestion demo is added.

#### Scenario: Default flows remain unchanged
- **WHEN** the policy ingestion demo support is present but not actively run
- **THEN** `/ask`, RAG Lab, retrieval-only, calc, report, and session defaults continue to behave as before
