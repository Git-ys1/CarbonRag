## ADDED Requirements

### Requirement: Policy web ingestion is controlled and optional
CarbonRag SHALL provide a disabled-by-default policy crawler boundary for official public policy sources.

#### Scenario: Policy crawler disabled by default
- **WHEN** no policy crawler setting is configured
- **THEN** CarbonRag keeps crawler execution disabled
- **AND** application startup does not require Scrapy or Scrapyd

#### Scenario: Official domain allowlist is enforced
- **WHEN** a policy crawl request targets a URL outside the official allowlist
- **THEN** CarbonRag rejects the request before fetching content

#### Scenario: Fake crawler supports offline tests
- **WHEN** tests run policy crawl ingestion
- **THEN** CarbonRag can use a fake crawler provider without network access

#### Scenario: Scrapy crawler runs only when explicitly available
- **WHEN** Scrapy is installed and policy crawling is explicitly enabled
- **THEN** CarbonRag can crawl allowlisted pages through `ScrapyCrawlerProvider`
- **AND** the crawler remains unavailable or disabled otherwise

### Requirement: Policy documents use three-stage ingestion
CarbonRag SHALL process official policy knowledge through collection, parsing, and governance normalization before indexing.

#### Scenario: Crawled document is staged before indexing
- **WHEN** a crawler returns a policy document
- **THEN** CarbonRag stages the crawled document before parsing and chunk indexing

#### Scenario: Crawled document enters knowledge task indexing
- **WHEN** a staged crawled policy document is accepted into the knowledge service
- **THEN** CarbonRag creates or refreshes a shared `public_policy_web` knowledge item
- **AND** enqueues a `crawl_ingest` task
- **AND** records the `policy_ingest` workflow checkpoints through parsing, metadata normalization, chunking, and indexing

#### Scenario: HTML/PDF/OFD parsing routes safely
- **WHEN** a staged policy document is HTML
- **THEN** CarbonRag extracts readable text without requiring Docling or MinerU
- **AND** common navigation, footer, sidebar, share, script, style, and breadcrumb boilerplate is excluded
- **AND** lightweight page metadata such as publication date and source label is preserved when visible in the page text
- **WHEN** a staged policy document is PDF
- **THEN** CarbonRag may prefer Docling and fall back through existing parser providers
- **AND** the parsed document keeps policy context such as `source_type=public_policy_web`, original source URL, and parser chain metadata
- **WHEN** a staged policy document is OFD
- **THEN** CarbonRag only attempts OFD conversion through an optional converter adapter
- **AND** conversion metadata is preserved when converted content routes through the parser registry

#### Scenario: Policy governance metadata is normalized
- **WHEN** a policy document is parsed
- **THEN** CarbonRag records policy metadata fields for issuing authority, document number, publication date, effective date, expiry status, region, industry, topic tags, clause anchors, and source URL where available

### Requirement: Policy web chunks remain retrieval-compatible
CarbonRag SHALL index policy web chunks so existing public retrieval behavior remains compatible.

#### Scenario: Public policy web chunks expose existing evidence source type
- **WHEN** a `public_policy_web` knowledge item is chunked
- **THEN** generated retrieval chunks use the existing `public_policy` source type
- **AND** chunk metadata preserves source URL, crawl metadata, content hash, and clause anchors

#### Scenario: Indexed policy web chunks participate in public retrieval
- **WHEN** a `public_policy_web` knowledge item is indexed
- **THEN** public policy BM25 retrieval can return its chunks as `public_policy` evidence
- **AND** existing public policy corpus retrieval remains available

#### Scenario: Default flows remain unchanged
- **WHEN** policy ingestion support is added
- **THEN** `/ask`, RAG Lab, retrieval-only, calc, report, and session defaults continue to work without enabling the crawler
