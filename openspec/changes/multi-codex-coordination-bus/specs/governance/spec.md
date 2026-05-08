## ADDED Requirements

### Requirement: Mattermost coordinates multi-Codex work

CarbonRag SHALL use Mattermost as the real-time coordination layer for multi-seat Codex work.

#### Scenario: Codex prepares non-trivial work

- **WHEN** Codex prepares a non-trivial change
- **THEN** it reads the active OpenSpec change
- **AND** checks GitNexus context when available
- **AND** reads recent `carbonrag-control` messages
- **AND** posts a PLAN before editing

### Requirement: High-risk changes wait for #1 ACK

CarbonRag SHALL require #1 acknowledgement before API, DB, auth, deployment, model provider, carbon engine, RAG core, or cross-module edits proceed.

#### Scenario: Codex posts a risky PLAN

- **WHEN** a PLAN declares a high-risk module or cross-module change
- **THEN** Codex waits for a matching #1 ACK before implementation

### Requirement: Mattermost messages are machine-readable

CarbonRag SHALL use a structured message prefix for PLAN, ACK, BLOCK, LOCK, UNLOCK, DECISION, CHANGED, and REVIEW_READY messages.

#### Scenario: #2 Codex checks coordination state

- **WHEN** #2 Codex searches recent coordination messages
- **THEN** it can identify active BLOCK, LOCK, ACK, and DECISION messages from the structured prefix

