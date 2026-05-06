## ADDED Requirements

### Requirement: Multi-Codex collaboration uses GitHub as the shared record

CarbonRag SHALL use OpenSpec changes, GitHub branches, Issues, Pull Requests, PR comments, and development logs as the durable coordination surface for multi-Codex collaboration.

#### Scenario: Another seat uses Codex for development

- **WHEN** #2 or another seat uses Codex to implement a task
- **THEN** the work is represented by an OpenSpec change id, a branch, and a PR or issue record readable by #1
- **AND** #1 can review the diff, rationale, validation, and logs without relying on private agent-to-agent chat

### Requirement: Cloud collaboration smoke tests avoid production behavior changes

CarbonRag SHALL use docs-only PRs for first-time GitHub collaboration smoke tests unless #1 explicitly approves a production-impacting test.

#### Scenario: #1 tests cloud PR workflow

- **WHEN** #1 validates whether Codex can work through GitHub PRs
- **THEN** the smoke PR avoids business code, API, DB, auth, model, deployment, and UI changes
- **AND** the PR remains available for review workflow testing before any merge decision
