## ADDED Requirements

### Requirement: Admin policy crawler shows backend health
CarbonRag Admin SHALL show the active policy crawler backend and its availability before a user triggers a crawl.

#### Scenario: Local Scrapy backend status is visible
- **WHEN** the Admin policy crawler section loads
- **THEN** the page shows whether the active backend is local Scrapy
- **AND** shows whether local Scrapy is available, disabled, or unavailable

#### Scenario: Scrapyd backend status is visible
- **WHEN** the active backend is Scrapyd
- **THEN** the page shows remote daemon health, endpoint label, last run status, and failure reason when present
- **AND** the page does not expose secrets or raw credentials

#### Scenario: Review gate is visible
- **WHEN** crawled candidates are listed
- **THEN** the page clearly shows pending, published, and rejected states
- **AND** publish/reject actions remain admin-only
