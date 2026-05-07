## ADDED Requirements

### Requirement: Existing product surfaces show policy ingestion readiness
CarbonRag SHALL expose policy ingestion controls and status through existing protected/admin application surfaces rather than a separate throwaway demo page.

#### Scenario: Admin starts curated policy ingestion from product UI
- **WHEN** an admin opens the relevant admin or knowledge management surface
- **THEN** the UI provides a clear control to seed or refresh the curated official-policy source
- **AND** the UI identifies that this is a controlled built-in source, not live arbitrary crawling

#### Scenario: Admin observes ingestion pipeline status
- **WHEN** the curated policy source ingestion has run
- **THEN** the UI shows task status, workflow status, extracted metadata, generated chunks, and source URL

#### Scenario: User validates retrieval from RAG surface
- **WHEN** the curated policy source has been indexed
- **THEN** the existing RAG validation surface can retrieve it and show public policy evidence

#### Scenario: Non-admin users cannot start ingestion
- **WHEN** a non-admin user opens the app
- **THEN** they cannot run policy ingestion state-changing actions through the UI
