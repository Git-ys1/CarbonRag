# CarbonRag Agent Instructions

## OpenSpec First

Before implementing any non-trivial feature, read the relevant specs under `openspec/specs/**`.

Also read `docs/governance/OPEN_COLLABORATION_GUIDE.md` and the active `openspec/changes/<change-id>/**` when the task affects collaboration, review, release, or module boundaries.

Use this mapping first:

- M1 AI Runtime / Provider / Model Config: `openspec/specs/ai-runtime/spec.md`
- M2 Conversation / Session / Memory: `openspec/specs/conversation-memory/spec.md`
- M3 Frontend Chat UX / Theme / Settings: `openspec/specs/frontend-shell-settings/spec.md`
- M4 Auth / User / Admin Governance: `openspec/specs/auth-governance/spec.md`
- M5 Knowledge / File / RAG: `openspec/specs/knowledge-rag/spec.md`
- M6 Carbon / Report / Feedback: `openspec/specs/carbon-report-feedback/spec.md`
- M7 DevOps / CI / Release: `openspec/specs/devops-release/spec.md`
- M8 Spec / Governance / Project Docs: `openspec/specs/governance/spec.md`

## Change Discipline

- Do not start a new feature without an OpenSpec change id unless the task is explicitly docs-only or an emergency hotfix.
- When the user provides a non-trivial task book without a change id, Codex must derive a kebab-case change id, create or inspect `openspec/changes/<change-id>/`, and run the propose stage before implementation.
- The human does not need to manually run OpenSpec for every round. Codex owns the OpenSpec housekeeping in normal development: inspect specs, create change scaffolding, draft proposal/design/tasks/delta specs, validate, then wait for review before apply unless the user explicitly authorizes fast-track execution.
- PRs must state the OpenSpec change id, affected specs, affected modules, risks, verification, and approval state.
- `Git-ys1` is the final `main` reviewer and CODEOWNERS fallback owner.
- This repository is already initialized for OpenSpec. Do not run `openspec init` in this repo unless #1 explicitly requests a full re-initialization.
- `openspec update .` may be used to refresh instructions. If it asks to remove `openspec/AGENTS.md` or instruction files, default to preserving them until #1 confirms migration.
- Codex may operate Git for setup, branching, commits, pushes, and merges only within the active task goal and repository workflow. State-changing Git operations must have a clear reason and must not be destructive unless explicitly requested.

## Local Artifacts

Never commit:

- `.spec-gen/`
- `3rdparty/spec-gen/`
- local model paths
- API keys or credentials
- local agent session records
- runtime outputs under `data/outputs/`

Local-only ignored files are not missing source. Recreate them from templates, scripts, dependency installs, or local runtime commands.

## Worktree Safety

- Do not revert user changes unless explicitly asked.
- Keep generated drafts separate from manually reviewed specs.
- Treat `openspec/specs/**` as the current behavior source of truth and `openspec/changes/**` as proposed change work.

## GitNexus Code Intelligence Rule

Before modifying non-trivial backend, frontend, carbon, RAG, session, report, auth, deployment, or cross-module code, Codex must use GitNexus context first.

Required sequence:

1. Read the relevant OpenSpec change files and specs.
2. Run or verify `openspec validate --all`.
3. Verify GitNexus index status with `gitnexus status`.
4. Use GitNexus MCP or CLI to inspect affected modules.
5. For risky edits, run `gitnexus impact <symbol>` or `gitnexus detect_changes` before implementation.
6. After implementation, run tests and use GitNexus for post-change impact review.

Do not blindly edit files only from grep results when GitNexus is available. If GitNexus is unavailable, record the reason in the task notes and fall back to normal repo exploration.

## Multi-Codex Mattermost Coordination Rule

Before non-trivial edits, Codex must use the `codex-coordination` skill when Mattermost is available.

Required sequence:

1. Read `AGENTS.md`.
2. Read the active OpenSpec change and related specs.
3. Check GitNexus context when available.
4. Read recent messages from Mattermost `carbonrag-control`.
5. Search for active `LOCK`, `BLOCK`, and `DECISION` messages.
6. Post `PLAN` before editing.
7. For API, DB, auth, deployment, model provider, carbon engine, RAG core, or cross-module edits, wait for #1 `ACK`.
8. Respect `LOCK`, `BLOCK`, and `DECISION` messages.
9. Post `CHANGED` after meaningful milestones.
10. Post `REVIEW_READY` before opening PR.

Do not wait until PR to disclose risky implementation decisions.
Do not modify files under another active lock unless #1 explicitly approves.
If Mattermost is not reachable, record the reason in the task notes and continue only when the task is low-risk or #1 explicitly authorizes offline work.

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
