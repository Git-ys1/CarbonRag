## Why

CarbonRag has entered multi-seat development. OpenSpec already governs intent and scope, but #1 still needs a reliable code-structure layer before editing or reviewing complex changes. GitNexus is introduced as a local code intelligence layer for call graph, impact, clusters, processes, semantic query, and PR diff analysis.

## What Changes

- Add GitNexus installation, indexing, MCP, and PR review workflow documentation.
- Add full-index scripts for Windows and shell users.
- Commit GitNexus-generated agent context and module-level skills so Codex has shared instructions.
- Keep `.gitnexus/` and diagnostic logs local-only.
- Record V1.4.7 findings: `gitnexus@1.6.3` is unstable on this machine; `gitnexus@1.6.4-rc.84` plus proxy/HF mirror completes full indexing.

## Out of Scope

- No product feature changes.
- No UI changes.
- No RAG, carbon, report, auth, session, or deployment runtime changes.
- No copying GitNexus UI or source code into CarbonRag.

## Impact

- Affected specs: `governance`, `devops-release`.
- Affected docs/scripts: GitNexus runbooks, PR review workflow, OpenSpec/Codex workflow, scripts, README, quick start.
- Runtime behavior: unchanged.
