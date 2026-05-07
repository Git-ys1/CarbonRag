# Mattermost + Codex Coordination Runbook

版本：V1.4.7B

## 当前状态

V1.4.7B 仓库侧协议、skill、脚本和文档已落地。公网探测 `http://8.141.111.33:8065` 当前超时，说明 VPS 上 Mattermost 还未部署、未启动，或阿里云安全组/防火墙未放行 `8065`。

本轮真实联调需要 #1 提供 VPS SSH/sudo 权限，或由 #1 在服务器上执行部署命令。

## VPS 部署建议

CarbonRag 后端继续使用 `80 -> 127.0.0.1:8000`。Mattermost 试点先独立监听 `8065`，不改现有 Nginx 后端。

推荐目录：

```bash
mkdir -p /srv/mattermost
cd /srv/mattermost
```

部署建议：

1. 安装 Docker 与 Docker Compose。
2. 使用 Mattermost 官方 Docker Compose 模板。
3. 设置 `DOMAIN=8.141.111.33` 或服务器实际域名。
4. 启动后确认 `curl http://127.0.0.1:8065`。
5. 在阿里云安全组放行 TCP `8065`。
6. 本地确认 `curl http://8.141.111.33:8065`。

长期建议：绑定域名并配置 HTTPS；试点阶段可先用 HTTP。

## Mattermost 初始化

创建 team：

```text
carbonrag
```

创建频道：

```text
carbonrag-control
carbonrag-review
carbonrag-log
```

创建账号：

```text
t1-director
t1-codex
t2-director
t2-codex
```

启用 Personal Access Tokens，并分别为 `t1-codex` / `t2-codex` 生成 PAT。

## Codex MCP 配置

仓库示例：

```text
docs/governance/examples/codex-mattermost-config.example.toml
```

本地 `~/.codex/config.toml` 增加：

```toml
[mcp_servers.mattermost]
url = "http://8.141.111.33:8065/plugins/mattermost-ai/mcp-server/mcp"
bearer_token_env_var = "MATTERMOST_TOKEN"
enabled = true
required = true
tool_timeout_sec = 60
enabled_tools = ["read_channel", "search_posts", "create_post", "read_post", "get_channel_info"]
```

本地 PowerShell：

```powershell
$env:MATTERMOST_URL="http://8.141.111.33:8065"
$env:MATTERMOST_TOKEN="<t1-codex 或 t2-codex 的 PAT>"
$env:MATTERMOST_TEAM="carbonrag"
$env:MATTERMOST_CHANNEL="carbonrag-control"
codex mcp list
```

## Standalone MCP fallback

如果 Mattermost Agents 插件 HTTP MCP 不可用，不放弃 Mattermost。改用官方 standalone MCP server，环境变量仍为：

```powershell
$env:MM_SERVER_URL="http://8.141.111.33:8065"
$env:MM_ACCESS_TOKEN=$env:MATTERMOST_TOKEN
```

然后把 Codex MCP server 配成 stdio 方式。具体命令以当时安装的 Mattermost MCP Server 包说明为准，并记录到本文件。

## REST fallback

如果 MCP 尚未通，可以先用 REST 脚本发消息：

```powershell
$env:MATTERMOST_URL="http://8.141.111.33:8065"
$env:MATTERMOST_TOKEN="<t1-codex PAT>"
$env:MATTERMOST_TEAM="carbonrag"
$env:MATTERMOST_CHANNEL="carbonrag-control"

powershell -NoProfile -ExecutionPolicy Bypass -File scripts/coordination/post-mattermost-update.ps1 `
  -Type PLAN `
  -Version V1.4.7B `
  -ChangeId multi-codex-coordination-bus `
  -Module M8 `
  -Risk low `
  -Message "验证 Mattermost 协同总线。"
```

## 验收

- `curl http://8.141.111.33:8065` 可达。
- `t1-director` 能看到三个频道。
- `t1-codex` PAT 能读写 `carbonrag-control`。
- Codex MCP 能读频道、搜索 ACK/BLOCK、创建 PLAN。
- 完成一次 PLAN -> ACK -> CHANGED -> REVIEW_READY。
- 完成一次 BLOCK 后 Codex 停止施工。

