## ADDED Requirements

### Requirement: Mattermost deployment is reproducible

CarbonRag SHALL document the Mattermost VPS deployment, channel setup, PAT setup, MCP configuration, and REST fallback scripts.

#### Scenario: A new seat joins coordination

- **WHEN** the seat receives a Mattermost account and PAT
- **THEN** they can configure local `MATTERMOST_TOKEN`
- **AND** validate channel read/search/post capability without receiving any secret from Git

### Requirement: Mattermost secrets remain local

CarbonRag SHALL ignore local Mattermost token files and coordination local config.

#### Scenario: A developer configures Mattermost locally

- **WHEN** they store a PAT in `.env.mattermost`, `.mattermost-token`, or `coordination.local.json`
- **THEN** Git does not include those files for commit

