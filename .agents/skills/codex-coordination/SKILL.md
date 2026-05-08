---
name: codex-coordination
description: Use before and after code changes in CarbonRag multi-seat development. It enforces PLAN, LOCK, CHANGED, REVIEW_READY, and DECISION messages through Mattermost.
---

# Codex Coordination

Use this skill before and after non-trivial CarbonRag code or governance work.

## Before Editing

1. Read `AGENTS.md`, active OpenSpec change files, and relevant `openspec/specs/**`.
2. Verify `openspec validate --all`.
3. Check GitNexus status and inspect affected modules when GitNexus is available.
4. Read recent `carbonrag-control` messages.
5. Search for active `LOCK`, `BLOCK`, and `DECISION` messages.
6. Post `PLAN` before modifying files.
7. For API, DB, auth, deploy, model provider, carbon engine, RAG core, or cross-module changes, wait for #1 `ACK`.
8. For ordinary module-local changes, proceed only after confirming no active lock exists.

## After Editing

1. Post `CHANGED` with files touched, tests run, and remaining risks.
2. If implementation is ready for early review, post `REVIEW_READY`.
3. Before PR, summarize OpenSpec change-id, GitNexus impact result, test result, and remaining risks.

## Fallback

If MCP is unavailable, use `scripts/coordination/post-mattermost-update.ps1` or `.sh`.

Do not wait until PR time to disclose risky implementation decisions.

