# CarbonRag Claude/Codex Instructions

## OpenSpec First

Before implementing non-trivial changes, read `AGENTS.md`, the relevant `openspec/specs/**`, and the active `openspec/changes/<change-id>/**`.

OpenSpec defines what to build and why. GitNexus provides code intelligence and impact analysis. Do not treat GitNexus as a replacement for OpenSpec or human review.

## GitNexus First For Code Impact

Before modifying backend, frontend, carbon, RAG, session, report, auth, deployment, or cross-module code:

1. Verify `openspec validate --all`.
2. Verify `gitnexus status`.
3. Use GitNexus context/query/impact/detect_changes before changing code.
4. Report high-risk blast radius before implementation.

## Mattermost Coordination

Before non-trivial edits, read recent Mattermost `carbonrag-control` messages and post a structured PLAN when Mattermost is available.

For API, DB, auth, deployment, model provider, carbon engine, RAG core, or cross-module edits, wait for #1 ACK before implementation.

Respect LOCK, BLOCK, and DECISION messages. Post CHANGED after meaningful milestones and REVIEW_READY before PR.

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **CarbonRag** (8132 symbols, 15982 relationships, 300 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/CarbonRag/context` | Codebase overview, check index freshness |
| `gitnexus://repo/CarbonRag/clusters` | All functional areas |
| `gitnexus://repo/CarbonRag/processes` | All execution flows |
| `gitnexus://repo/CarbonRag/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |
| Work in the Tests area (255 symbols) | `.claude/skills/generated/tests/SKILL.md` |
| Work in the Rag area (189 symbols) | `.claude/skills/generated/rag/SKILL.md` |
| Work in the Knowledge area (106 symbols) | `.claude/skills/generated/knowledge/SKILL.md` |
| Work in the Services area (71 symbols) | `.claude/skills/generated/services/SKILL.md` |
| Work in the Providers area (59 symbols) | `.claude/skills/generated/providers/SKILL.md` |
| Work in the Endpoints area (52 symbols) | `.claude/skills/generated/endpoints/SKILL.md` |
| Work in the AskPage area (52 symbols) | `.claude/skills/generated/askpage/SKILL.md` |
| Work in the Adapters area (48 symbols) | `.claude/skills/generated/adapters/SKILL.md` |
| Work in the Retrieval area (41 symbols) | `.claude/skills/generated/retrieval/SKILL.md` |
| Work in the Memory area (38 symbols) | `.claude/skills/generated/memory/SKILL.md` |
| Work in the Settings area (36 symbols) | `.claude/skills/generated/settings/SKILL.md` |
| Work in the Auth area (33 symbols) | `.claude/skills/generated/auth/SKILL.md` |
| Work in the Session area (29 symbols) | `.claude/skills/generated/session/SKILL.md` |
| Work in the Carbon area (26 symbols) | `.claude/skills/generated/carbon/SKILL.md` |
| Work in the Admin area (25 symbols) | `.claude/skills/generated/admin/SKILL.md` |
| Work in the Report area (21 symbols) | `.claude/skills/generated/report/SKILL.md` |
| Work in the RagLabPage area (21 symbols) | `.claude/skills/generated/raglabpage/SKILL.md` |
| Work in the Theme area (20 symbols) | `.claude/skills/generated/theme/SKILL.md` |
| Work in the Tools area (18 symbols) | `.claude/skills/generated/tools/SKILL.md` |
| Work in the Scripts area (15 symbols) | `.claude/skills/generated/scripts/SKILL.md` |

<!-- gitnexus:end -->
