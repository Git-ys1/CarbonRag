## ADDED Requirements

### Requirement: Admin can view policy ingestion demo workbench
CarbonRag SHALL provide an authenticated admin-facing page for demonstrating controlled policy ingestion.

#### Scenario: Admin opens demo page
- **WHEN** an admin opens the policy ingestion demo workbench
- **THEN** the page shows the backend base URL, demo status, fixture title, fixture source URL, and a control to run the demo fixture ingestion

#### Scenario: Demo progress is visible
- **WHEN** the demo has run
- **THEN** the page shows task status, workflow status, extracted policy metadata, generated chunks, and public retrieval hits

#### Scenario: Demo page explains scope
- **WHEN** the page is displayed
- **THEN** it clearly indicates that the policy ingestion demo uses a controlled fixture and does not enable default live crawling or production crawler scheduling

#### Scenario: Non-admin users cannot access demo page
- **WHEN** a non-admin user attempts to open the policy ingestion demo workbench
- **THEN** the frontend follows the existing protected/admin route behavior
