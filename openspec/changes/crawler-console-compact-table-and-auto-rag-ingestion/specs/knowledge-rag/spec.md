## MODIFIED Requirements

### Requirement: Knowledge/RAG exposes a product-grade knowledge base spine

CarbonRag SHALL expose crawler candidates as a scalable reviewed ingestion workflow rather than a fixed-size debug list.

#### Scenario: Admin reviews crawler candidates in a paginated table

- **WHEN** an admin opens the crawler candidate console
- **THEN** candidates are shown in a paginated table with status, source, RAG status, topic class, query, and run filters
- **AND** no hard-coded first-eight candidate limit is applied.

#### Scenario: Admin inspects a crawler candidate before publishing

- **WHEN** an admin opens a crawler candidate detail drawer
- **THEN** CarbonRag shows overview metadata, artifact preview entry, RAG publish status, quality diagnostics, and raw metadata
- **AND** long text stays out of the table row.

#### Scenario: Admin explicitly crawls and auto-ingests qualified candidates

- **WHEN** an admin runs a source with `auto_rag_ingest_enabled=true`
- **THEN** CarbonRag applies the V1.7.3 artifact and quality gates to each candidate
- **AND** publishes only qualified candidates to the system crawler KB quick pipeline
- **AND** records attempted, indexed, failed, skipped, and target KB summary fields on the run.

#### Scenario: Batch publish respects ingestion gates

- **WHEN** an admin batch publishes selected candidates to RAG
- **THEN** CarbonRag returns published, skipped, and failed item details
- **AND** duplicate or low-quality candidates are skipped or failed with explicit reasons rather than silently marked published.
