## Why

CarbonRag is moving into multi-seat development, but the team still needs proof that Codex-assisted collaboration can happen through GitHub without bypassing #1 review control. This smoke test verifies the safe path: OpenSpec change, branch, docs-only commit, GitHub PR, and review readiness.

## What Changes

- Add a docs-only smoke record for using GitHub PRs as the shared coordination surface between #1 Codex and other seats' Codex sessions.
- Clarify that Codex instances should not rely on private agent-to-agent chat; they should exchange durable context through OpenSpec changes, Issues, PRs, review comments, and development logs.
- Create a test PR without merging it automatically, so #1 can validate the review workflow.
- No business code, UI, API, DB, model, auth, retrieval, report, calc, or deployment behavior changes.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `governance`: Document the cloud PR smoke workflow as the approved collaboration test path for multi-Codex work.

## Impact

- Affected docs: `docs/governance/CLOUD_CODEX_COLLAB_SMOKE.md`.
- Affected specs: `openspec/specs/governance/spec.md` through a governance delta.
- No runtime code or production behavior impact.
