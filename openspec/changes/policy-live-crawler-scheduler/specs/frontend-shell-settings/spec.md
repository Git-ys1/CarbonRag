## ADDED Requirements

### Requirement: Admin UI exposes live policy crawler review controls
CarbonRag SHALL expose live policy crawler controls in an admin-only product surface without changing normal chat or retrieval defaults.

#### Scenario: Admin views crawler status
- **WHEN** an admin opens the Admin page
- **THEN** CarbonRag shows crawler provider availability, scheduling mode, official source list, recent runs, and candidate counts
- **AND** the UI states that live crawler candidates require review before retrieval

#### Scenario: Admin manually runs a source
- **WHEN** an admin triggers a manual crawl for an allowlisted source
- **THEN** the UI calls the admin run API
- **AND** refreshes source/run/candidate status after the request completes

#### Scenario: Admin reviews candidate
- **WHEN** a candidate is pending review
- **THEN** the UI lets admins publish or reject it
- **AND** shows published, rejected, failed, unavailable, and empty states without crashing

#### Scenario: Missing crawler metadata is tolerated
- **WHEN** the backend omits optional crawler metadata fields
- **THEN** the Admin page still renders a clear fallback value

#### Scenario: Protected route behavior remains unchanged
- **WHEN** a non-admin or unauthenticated user attempts to access crawler controls
- **THEN** existing protected/admin route behavior applies
- **AND** no crawler operation is available from normal chat or public RAG pages
