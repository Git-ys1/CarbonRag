## Design

GitNexus is adopted as a local development tool, not a product dependency. The repository tracks the operating rules, scripts, and generated skill files; local indexes and logs remain ignored.

## Decisions

- Use `gitnexus@rc` until upstream releases a stable version after `1.6.3`.
- Keep Codex MCP registration global with `codex mcp add gitnexus -- npx -y gitnexus@rc mcp` until a stable release newer than `1.6.3` is available.
- Use `scripts/gitnexus-full-index.ps1` as #1's standard Windows entrypoint.
- Use `HF_ENDPOINT=https://hf-mirror.com` by default and allow `-Proxy http://127.0.0.1:17891` for Clash.
- Commit `.claude/skills/**/SKILL.md` because `AGENTS.md` and `CLAUDE.md` reference those paths.
- Do not commit `.gitnexus/` or `logs/gitnexus/`.

## Known Tool Behavior

- `gitnexus@1.6.3` can crash on this Windows machine even for a tiny repo.
- `gitnexus@1.6.4-rc.84` completes full CarbonRag indexing.
- Windows currently uses semantic exact-scan fallback when VECTOR index is unavailable.
