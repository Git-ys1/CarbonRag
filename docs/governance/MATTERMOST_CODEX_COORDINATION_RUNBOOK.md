# Mattermost + Codex Coordination Runbook

版本：V1.4.7B

## 当前状态

V1.4.7B 仓库侧协议、skill、脚本和文档已落地。Mattermost 试点服务已部署在：

```text
http://8.141.111.33:8065
```

当前已验证：

- 公网访问 `http://8.141.111.33:8065` 返回 `200 OK`。
- VPS 本机访问 Mattermost 返回 `200 OK`。
- `carbonrag` team 已存在。
- `carbonrag-control`、`carbonrag-review`、`carbonrag-log` 三个频道已存在。
- `t1-codex` / `t2-codex` PAT 可通过 Mattermost REST API 读取账号信息。
- `carbonrag-control` 已跑通过一次 `PLAN -> ACK -> CHANGED -> REVIEW_READY` 测试消息。
- standalone Mattermost MCP 已跑通 `tools/list`、`read_channel`、`create_post`。
- 内置 Mattermost AI HTTP MCP 端点 `/plugins/mattermost-ai/mcp-server/mcp` 当前返回 `404`，因此 HTTP MCP 暂缓，当前正式试点口径为 standalone MCP。

注意：PAT 和账号密码只能保存在本地或服务器 root-only 文件中，不得提交仓库。若凭据曾出现在聊天、截图或公共文档中，应立即轮换。

## 可视化查看方式

Mattermost 本身就是可视化协同界面，不需要 CarbonRag 额外再做一个容器来“看发帖”。

推荐查看方式：

1. 在浏览器打开 `http://8.141.111.33:8065`。
2. 使用 `t1-director` 或对应人类账号登录。
3. 进入 `carbonrag` team。
4. 查看三个频道：
   - `carbonrag-control`：施工计划、ACK、BLOCK、CHANGED、REVIEW_READY。
   - `carbonrag-review`：早期 review 和 PR 讨论。
   - `carbonrag-log`：自动日志、CI、GitHub webhook、GitNexus 摘要。

频道纪律：

- `carbonrag-control` 不做普通聊天，不做长讨论，只放结构化控制消息。
- 人类闲聊、技术讨论、PR 讨论放 `carbonrag-review` 或私聊。
- 自动日志、CI、GitHub webhook、GitNexus 摘要放 `carbonrag-log`。
- 这样做是为了让 Codex 能可靠搜索 `ACK`、`BLOCK`、`DECISION`，避免控制消息被闲聊淹没。

VS Code 中可选两种方式：

- 使用 VS Code 内置 Simple Browser 或浏览器预览扩展打开 `http://8.141.111.33:8065`，相当于把 Mattermost 网页嵌进 VS Code。
- 继续让 Codex / 脚本通过 REST 或 MCP 读写频道；这属于机器接口，不提供可视化聊天窗口。

结论：人类看状态用 Mattermost Web UI；Codex 自动协作用 REST/MCP；暂时不需要为 CarbonRag 自己开发一套发帖可视化容器。

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

### 当前 #1 本机状态

#1 本机已完成 standalone MCP 配置：

```text
C:\Users\yusu\.codex\mcp\bin\mattermost-mcp-server.exe
C:\Users\yusu\.codex\mcp\mattermost-mcp.ps1
```

Codex 本机配置 `C:\Users\yusu\.codex\config.toml` 中已存在：

```toml
[mcp_servers.mattermost]
command = "powershell"
args = ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "C:\\Users\\yusu\\.codex\\mcp\\mattermost-mcp.ps1"]
```

`codex mcp list` 应能看到：

```text
mattermost  powershell  ... mattermost-mcp.ps1  enabled
```

当前 smoke 结果：

```text
tool_count: 15
read_channel: ok
create_post: ok
```

### 2026-05-08 #1 可见性复测

#1 Codex 使用 `t1-codex` 身份完成了真实读写复测：

```text
当前账号：t1-codex
读取 carbonrag-control：成功
读取 carbonrag-review：成功
向 carbonrag-control 发送 [#1][CHANGED]：成功
读取最新 carbonrag-control 消息确认回显：成功
```

本次复测说明：

- `carbonrag-control` 中能看到 #1/#2 人类账号的普通聊天，但这不符合频道纪律；后续普通聊天应迁到 `carbonrag-review` 或私聊。
- PR #6 的正式驳回同步发到了 `carbonrag-review`，因此只看 `carbonrag-control` 会看不到那条消息。
- `carbonrag-control` 只保留 `PLAN / ACK / BLOCK / DECISION / CHANGED / REVIEW_READY`，这样 Codex 才能可靠搜索控制信号。
- 人类查看消息使用 Mattermost Web UI；Codex 自动读写使用 MCP 或 REST fallback。

真实 PAT 不写入 `config.toml`。启动 Codex 前必须在本机用户环境变量中设置：

| 使用者 | 应使用的 Mattermost 账号 | `MATTERMOST_TOKEN` 填写来源 |
| --- | --- | --- |
| #1 本机 Codex | `t1-codex` | #1 凭据清单中 `[tokens_raw] t1-codex` 对应的 PAT |
| #2 本机 Codex | `t2-codex` | #2 凭据清单中 `[tokens_raw] t2-codex` 对应的 PAT |
| #3 本机 Codex | `t3-codex` | 后续由 #1 创建并单独发放 |

PowerShell 设置命令：

```powershell
[Environment]::SetEnvironmentVariable("MATTERMOST_TOKEN", "<把对应 codex 账号的 PAT 粘贴在这里>", "User")
```

设置后重启 VS Code / Codex，使新环境变量生效。不要把 PAT 写入 `config.toml`、`.env`、截图、PR、开发日志或公告。

临时验证当前 PowerShell 会话可以这样写：

```powershell
$env:MATTERMOST_TOKEN="<把对应 codex 账号的 PAT 粘贴在这里>"
codex mcp list
```

如果只是当前窗口临时设置，关闭 PowerShell 后会失效；如果用 `[Environment]::SetEnvironmentVariable(..., "User")`，需要重启 VS Code / Codex 才会生效。

### #1 当前调用经验

当前最稳的调用路径是：

```text
Codex -> ~/.codex/config.toml -> mattermost-mcp.ps1 -> mattermost-mcp-server.exe -> Mattermost REST API
```

关键点：

- `MATTERMOST_TOKEN` 必须是 Codex 专用账号 PAT，不是人类账号密码。
- #1 用 `t1-codex` PAT，#2 用 `t2-codex` PAT。
- 设置用户级环境变量后必须重启 VS Code / Codex。
- 如果 `codex mcp list` 能看到 `mattermost ... enabled`，说明 Codex 已加载 MCP server 配置。
- 如果 Codex MCP UI 暂时看不到调用细节，可用 REST fallback 或本机 MCP smoke 脚本验证读写。

最小 REST 验证命令：

```powershell
$base = "http://8.141.111.33:8065"
$headers = @{ Authorization = "Bearer $env:MATTERMOST_TOKEN" }
Invoke-RestMethod -Headers $headers -Uri "$base/api/v4/users/me"
```

能返回当前用户，例如 `t1-codex`，说明 PAT 可用。

### HTTP MCP 配置草案

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

注意：当前 Mattermost 内置 HTTP MCP 端点仍返回 `404`，因此上面的 HTTP 配置只作为后续升级目标。现阶段优先使用 #1 本机已配置的 standalone MCP。

## Standalone MCP fallback

如果 Mattermost Agents 插件 HTTP MCP 不可用，不放弃 Mattermost。改用官方 standalone MCP server，环境变量为：

```powershell
$env:MM_SERVER_URL="http://8.141.111.33:8065"
$env:MM_ACCESS_TOKEN=$env:MATTERMOST_TOKEN
```

#1 本机实际采用 wrapper 方式，由 `mattermost-mcp.ps1` 自动设置 `MM_SERVER_URL` 和 `MM_ACCESS_TOKEN` 后启动 `mattermost-mcp-server.exe`。

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
