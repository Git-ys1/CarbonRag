## Design

Mattermost is treated as a coordination control bus, not a casual chat room.

The durable system split is:

- OpenSpec: intent, scope, tasks, archive.
- GitNexus: code structure, call graph, impact, PR diff analysis.
- Mattermost: real-time PLAN, ACK, LOCK, BLOCK, DECISION, CHANGED, REVIEW_READY.
- GitHub: branch, PR, CI, review, merge source of truth.
- Codex: execution and review agent that must read the other layers first.

## Deployment Shape

- Use existing VPS `8.141.111.33`.
- Keep CarbonRag backend unchanged on Nginx `80 -> 127.0.0.1:8000`.
- Deploy Mattermost under `/srv/mattermost` and expose `8065` for the pilot.
- Long-term production should move Mattermost behind HTTPS and a domain, but that is outside this change.

## MCP Strategy

1. Prefer Mattermost Agents plugin HTTP MCP endpoint:
   `http://8.141.111.33:8065/plugins/mattermost-ai/mcp-server/mcp`
2. If plugin MCP is unavailable, use the official standalone Mattermost MCP server with `MM_SERVER_URL` and `MM_ACCESS_TOKEN`.
3. Keep REST posting scripts as a non-MCP fallback so PLAN/CHANGED/REVIEW_READY can still be posted from CI or terminals.

## Security

- Each Codex has its own Mattermost PAT.
- Human accounts and Codex accounts are separate.
- PATs live only in local environment variables or local ignored files.
- Repository examples use placeholders only.

