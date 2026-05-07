## Why

CarbonRag is moving into multi-seat development. OpenSpec defines intent, GitNexus provides code impact context, and GitHub remains the PR/CI source of truth, but #1/#2 Codex agents still need a real-time coordination layer before PR time.

## What Changes

- Define Mattermost as the CarbonRag multi-Codex coordination bus.
- Freeze the three-channel protocol: `carbonrag-control`, `carbonrag-review`, `carbonrag-log`.
- Add repo-scoped Codex coordination skill under `.agents/skills/codex-coordination/`.
- Add Mattermost MCP config example and REST fallback posting scripts.
- Update AGENTS, collaboration docs, PR review docs, quick start, and README with the coordination workflow.

## Out of Scope

- No CarbonRag product feature changes.
- No frontend UI changes.
- No RAG, carbon, report, auth, session, or runtime API changes.
- No real Mattermost token committed to the repository.

## Impact

- Affected specs: `governance`, `devops-release`.
- Affected runtime behavior: none.
- VPS service setup is required for full end-to-end verification; current public `8.141.111.33:8065` probe times out until Mattermost is deployed or the port is opened.

