## ADDED Requirements

### Requirement: GitNexus setup is reproducible from tracked scripts

CarbonRag SHALL provide tracked scripts and docs for reproducing GitNexus indexing on #1 and later seats' machines.

#### Scenario: A developer wants code intelligence

- **WHEN** GitNexus is installed
- **THEN** the developer can run the tracked GitNexus full-index script
- **AND** the script performs embeddings, skills generation, verbose diagnostics, status, and repository listing

### Requirement: GitNexus local artifacts stay ignored

CarbonRag SHALL ignore `.gitnexus/` and `logs/gitnexus/` because they are local generated artifacts.

#### Scenario: Full indexing completes

- **WHEN** GitNexus creates `.gitnexus/lbug` and diagnostic logs
- **THEN** Git status does not include those generated artifacts for commit
