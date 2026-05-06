## ADDED Requirements

### Requirement: New-seat onboarding smoke evidence is reviewable
CarbonRag SHALL allow #2/#3 onboarding smoke runs to be recorded as governance documentation that can be reviewed in a PR before feature work begins.

#### Scenario: New seat submits onboarding smoke PR
- **WHEN** a new seat verifies fork setup, OpenSpec status, local bootstrap, and local frontend/backend smoke checks
- **THEN** the PR includes a governance smoke record with the seat identity, branch, change id, validation commands, local smoke results, and PR target
