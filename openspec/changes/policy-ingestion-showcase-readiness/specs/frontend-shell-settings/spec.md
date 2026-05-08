## ADDED Requirements

### Requirement: Existing product surfaces show policy ingestion readiness
CarbonRag SHALL expose policy ingestion controls and status through existing protected/admin application surfaces rather than a separate throwaway demo page.

#### Scenario: Admin starts curated showcase ingestion from product UI
- **WHEN** an admin opens the relevant admin or knowledge management surface
- **THEN** the UI provides a clear control to seed or refresh the curated built-in showcase source
- **AND** the UI identifies that this is controlled synthetic demo/showcase material, not official policy and not live arbitrary crawling

#### Scenario: Admin observes ingestion pipeline status
- **WHEN** the curated policy source ingestion has run
- **THEN** the UI shows task status, workflow status, extracted metadata, generated chunks, and source URL

#### Scenario: User validates retrieval from RAG surface
- **WHEN** the curated showcase source has been indexed
- **THEN** the existing RAG validation surface can retrieve it and show demo/showcase evidence
- **AND** the evidence label makes clear it is not official public policy

#### Scenario: Non-admin users cannot start ingestion
- **WHEN** a non-admin user opens the app
- **THEN** they cannot run policy ingestion state-changing actions through the UI
