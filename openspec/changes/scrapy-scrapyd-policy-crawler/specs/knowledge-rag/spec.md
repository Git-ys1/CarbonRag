## ADDED Requirements

### Requirement: Policy crawler can use local Scrapy or optional Scrapyd
CarbonRag SHALL support a policy crawler backend boundary that can run official policy crawls through local Scrapy or an explicitly configured Scrapyd daemon.

#### Scenario: Local Scrapy is the default enabled crawler backend
- **WHEN** policy crawling is enabled and no crawler backend override is configured
- **THEN** CarbonRag uses the local `ScrapyCrawlerProvider`
- **AND** existing disabled/unavailable behavior remains safe when Scrapy is not installed

#### Scenario: Scrapyd backend is optional
- **WHEN** `RAG_POLICY_CRAWLER_BACKEND=scrapyd` is configured
- **THEN** CarbonRag checks the configured Scrapyd endpoint before scheduling a crawl
- **AND** reports `unavailable` without blocking application startup if the daemon cannot be reached

#### Scenario: Backends share crawl safety constraints
- **WHEN** a policy crawl is run through local Scrapy or Scrapyd
- **THEN** CarbonRag validates official-domain allowlist before execution
- **AND** applies robots, depth/page limit, download delay, per-domain concurrency, timeout, and user-agent constraints

#### Scenario: Crawled results remain review gated
- **WHEN** local Scrapy or Scrapyd returns crawled documents
- **THEN** CarbonRag stores them as `pending_review` candidates
- **AND** does not index them into `public_policy_web` until an admin publishes the candidate

#### Scenario: Default flows remain unchanged
- **WHEN** the crawler backend boundary is added
- **THEN** `/ask`, RAG Lab, retrieval-only, calc, report, and session defaults continue to work without crawler execution
