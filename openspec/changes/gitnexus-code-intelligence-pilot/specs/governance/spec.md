## ADDED Requirements

### Requirement: GitNexus informs non-trivial code changes

CarbonRag SHALL use GitNexus code intelligence before non-trivial backend, frontend, carbon, RAG, session, report, auth, deployment, or cross-module edits when GitNexus is available.

#### Scenario: Codex prepares to edit complex code

- **WHEN** Codex prepares a non-trivial code change
- **THEN** it validates OpenSpec first
- **AND** verifies GitNexus index status
- **AND** uses GitNexus query, context, impact, or detect_changes before implementation

### Requirement: GitNexus local indexes are not shared source

CarbonRag SHALL keep GitNexus generated database and diagnostic logs out of Git while tracking reusable scripts and operating instructions.

#### Scenario: A contributor clones main

- **WHEN** the contributor needs GitNexus context
- **THEN** they recreate `.gitnexus/` locally with tracked scripts and docs
- **AND** they do not expect `.gitnexus/` or `logs/gitnexus/` to be present in the repository

### Requirement: GitNexus does not replace OpenSpec

CarbonRag SHALL treat OpenSpec as the intent and change-governance source of truth, while GitNexus only provides code-structure and impact context.

#### Scenario: A new feature is proposed

- **WHEN** a feature changes product behavior
- **THEN** an OpenSpec change remains required
- **AND** GitNexus may be used to map affected modules and blast radius
