## Context

The team wants to know whether Codex can work "in the cloud GitHub repo" and whether that is suitable for multi-Codex collaboration. The answer is yes for repository-mediated collaboration: Codex can create branches, push commits, open PRs, and read review context through GitHub. It should not become an unlogged private agent-to-agent chat channel.

## Decision

Use GitHub as the shared coordination layer:

- OpenSpec change records the intent and acceptance criteria.
- Git branch contains the concrete diff.
- Pull Request contains reviewable changes and discussion.
- GitHub Issues or PR comments hold development logs and blocking questions.
- #1 remains the final human reviewer.

This smoke test is intentionally docs-only. It proves the path without risking business behavior.

## Smoke Flow

1. Create branch `t1/v1.2/cloud-codex-collab-smoke`.
2. Create OpenSpec change `cloud-codex-collab-smoke`.
3. Add docs-only governance note.
4. Validate OpenSpec.
5. Push branch to GitHub.
6. Open PR to `main`.
7. #1 uses `gh pr checkout`, `git diff origin/main...HEAD`, and `openspec validate --all` to review.
8. Do not auto-merge during smoke unless #1 explicitly approves.

## Non-Goals

- No direct private bridge between #1 Codex and #2 Codex.
- No new chat server.
- No GitHub branch protection changes in this smoke PR.
- No business-code change.
