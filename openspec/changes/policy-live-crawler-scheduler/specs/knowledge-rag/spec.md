## ADDED Requirements

### Requirement: Policy crawler stages live official results for review
CarbonRag SHALL provide an admin-controlled live policy crawler path that fetches only official allowlisted sources and stages results as review candidates before indexing.

#### Scenario: Official sources are seeded without automatic fetch
- **WHEN** CarbonRag starts with default settings
- **THEN** official policy crawler sources are available for admin inspection
- **AND** no live public crawl is started automatically
- **AND** application startup does not require Scrapy or Scrapyd

#### Scenario: Manual crawl uses safe limits
- **WHEN** an admin manually runs an official policy source
- **THEN** CarbonRag validates the source URL against the official allowlist before fetching
- **AND** uses robots compliance, low concurrency, download delay, depth limit, page limit, timeout, and user-agent settings
- **AND** records a policy crawl run with status, counts, timestamps, and error details

#### Scenario: Non-allowlisted source is rejected
- **WHEN** a crawl source or URL is outside the official allowlist
- **THEN** CarbonRag rejects it before network access
- **AND** records a clear validation error

#### Scenario: Scrapy unavailable does not break startup
- **WHEN** Scrapy is not installed or policy crawling is disabled
- **THEN** CarbonRag startup still succeeds
- **AND** the crawler status is reported as `unavailable` or `disabled`

#### Scenario: Crawl results enter pending review
- **WHEN** a live crawl returns documents
- **THEN** CarbonRag creates `policy_crawl_candidates` with `status=pending_review`
- **AND** does not create or refresh `public_policy_web` knowledge items before admin publication
- **AND** does not expose those candidates through `/ask`, RAG Lab, or retrieval-only public retrieval

#### Scenario: Admin publishes accepted candidate
- **WHEN** an admin publishes a pending review candidate
- **THEN** CarbonRag creates or refreshes a shared `public_policy_web` knowledge item
- **AND** enqueues `crawl_ingest`
- **AND** records the published candidate status and linked knowledge item

#### Scenario: Admin rejects candidate
- **WHEN** an admin rejects a pending review candidate
- **THEN** CarbonRag records `status=rejected`
- **AND** does not enqueue ingestion
- **AND** the rejected candidate remains outside public retrieval

#### Scenario: Optional scheduler remains explicit
- **WHEN** scheduled live crawling is not explicitly enabled
- **THEN** CarbonRag does not run recurring public crawls
- **AND** manual admin-triggered runs remain available when the crawler provider is available

### Requirement: Policy crawler persistence is runtime-bootstrap compatible
CarbonRag SHALL bootstrap policy crawler runtime tables through the existing runtime database schema path.

#### Scenario: SQLite runtime schema includes crawler tables
- **WHEN** the SQLite runtime database initializes
- **THEN** `policy_crawl_sources`, `policy_crawl_runs`, and `policy_crawl_candidates` exist

#### Scenario: PostgreSQL runtime schema includes crawler tables
- **WHEN** the PostgreSQL runtime database initializes
- **THEN** `policy_crawl_sources`, `policy_crawl_runs`, and `policy_crawl_candidates` exist

#### Scenario: Existing databases upgrade additively
- **WHEN** an existing runtime database starts after this change
- **THEN** crawler tables are created if missing
- **AND** existing knowledge, workflow, and retrieval tables are not rewritten
