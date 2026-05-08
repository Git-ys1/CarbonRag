# GitNexus Code Intelligence Runbook

版本：V1.4.7

## 定位

GitNexus 是 CarbonRag 的本地代码结构感知工具。它负责回答“代码在哪、谁依赖谁、改哪里会影响什么”。OpenSpec 仍负责“做什么、为什么做、边界是什么”。

## 安装

本机实测 `gitnexus@1.6.3` 会在 Windows 上原生崩溃；GitHub issue #1406 的维护者建议先使用 rc 版本。因此 V1.4.7 冻结为：

```powershell
npm install -g gitnexus@rc
gitnexus --version
```

验收版本：`1.6.4-rc.84`。

不要用：

```powershell
npm install -g gitnexus
```

因为它会安装当前 latest `1.6.3`。

## Codex MCP 注册

```powershell
codex mcp add gitnexus -- npx -y gitnexus@rc mcp
codex mcp list
```

`codex mcp list` 中必须能看到 `gitnexus`。

## 完整索引

推荐使用脚本：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/gitnexus-full-index.ps1 -Proxy "http://127.0.0.1:17891"
```

如果没有 Clash 代理，脚本默认使用 `HF_ENDPOINT=https://hf-mirror.com`。代理可访问时建议走 `127.0.0.1:17891`，下载 HuggingFace 模型和 LadybugDB 扩展更稳定。

#1 本机成功命令：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/gitnexus-full-index.ps1 -Proxy "http://127.0.0.1:17891" -HfEndpoint "https://huggingface.co"
```

默认脚本会加 `--skip-agents-md`，只更新本地 `.gitnexus/` 和 generated skills，不改写 `AGENTS.md/CLAUDE.md`。这是日常开发推荐模式。

只有首次接入 GitNexus 或 #1 明确要刷新 agent context 时，才使用：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/gitnexus-full-index.ps1 -Proxy "http://127.0.0.1:17891" -UpdateAgentContext
```

脚本等价于：

```powershell
gitnexus analyze --force --embeddings --skills --verbose --skip-agents-md
gitnexus status
gitnexus list
```

注意：`gitnexus@1.6.4-rc.84` 支持 `--worker-timeout`，但本轮脚本不强制使用，避免不同版本 CLI 参数不兼容。

## 本机实测结果

V1.4.7 本机完整索引结果：

- GitNexus：`1.6.4-rc.84`
- 节点：`8,140`
- 边：`15,984`
- clusters：`340`
- processes：`300`
- module-level skills：`20` 个，生成到 `.claude/skills/generated/`
- agent context：已写入 `AGENTS.md` 与 `CLAUDE.md`

`.claude/skills/generated/` 是本地生成物，已加入 `.gitignore`。每个席位运行 full index 后会在本机生成自己的模块级 skills；
不要提交这些 generated skills，否则 GitNexus 下一次索引会把它们也当成仓库内容，造成模块分组抖动。

`--embeddings` 已成功生成。当前 Windows 平台提示 `VECTOR index` 不支持，语义查询使用 exact-scan fallback；这不是失败，只是性能降级。

## 常用命令

```powershell
gitnexus status
gitnexus list
gitnexus query carbon --limit 5
gitnexus context CarbonCalculationEngine
gitnexus impact CarbonCalculationEngine
gitnexus detect_changes
gitnexus serve
```

Web UI 验证：

```powershell
gitnexus serve --host 127.0.0.1 --port 4747
```

打开 `http://127.0.0.1:4747` 后应能看到本地 GitNexus Web UI。V1.4.7 本机已验证端口 `4747` 可连接。

首次点击 `CarbonRag` 仓库卡片时，页面可能停在 `Downloading... 0.0 MB` 一段时间；这是前端在消费
`/api/graph?repo=CarbonRag&stream=true` 的 NDJSON 图谱流。#1 本机实测图谱流约 7.5 MB，等待约 30-60 秒后可进入图谱页。
进入后应能看到文件树、图谱画布、`8230 nodes / 15975 edges` 统计，并可在 Code Inspector 中查看
`backend/app/carbon/engine.py` 等文件。

如果长时间无结果，先验证：

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:4747/ -TimeoutSec 10
Invoke-RestMethod http://127.0.0.1:4747/api/repos -TimeoutSec 10
curl.exe -sS --max-time 8 "http://127.0.0.1:4747/api/graph?repo=CarbonRag&stream=true" -o $env:TEMP\gitnexus-graph-sample.txt
Get-Item $env:TEMP\gitnexus-graph-sample.txt
```

看完 Web UI 后，如果要继续运行 `gitnexus detect_changes`、`gitnexus analyze` 或提交前检查，建议先关闭
`gitnexus serve`。Windows 上 serve 进程可能持有 `.gitnexus/lbug` 文件锁，导致 detect_changes 输出
`The process cannot access the file because another process has locked a portion of the file`。

```powershell
$ownerIds = Get-NetTCPConnection -LocalPort 4747 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($ownerId in $ownerIds) {
  if ($ownerId -and $ownerId -ne 0) {
    Stop-Process -Id $ownerId -Force
  }
}
```

## 开工前固定顺序

```powershell
openspec validate --all
gitnexus status
gitnexus query <topic>
gitnexus impact <symbol>
```

每次切分支、merge、commit 后，如果 `gitnexus status` 显示 stale，就重跑 full-index。`.gitnexus/` 是本地索引，不需要提交；不要为了让索引“跟上版本”去提交 `.gitnexus/`。

不要只靠 `rg` 找文件就开始改复杂模块。

## 已知问题

- `gitnexus@1.6.3` 在本机和极小临时 repo 上均可复现原生崩溃，退出码 `-1073741819`。
- `--embeddings` 需要下载 HuggingFace 模型；网络失败时设置 `HF_ENDPOINT=https://hf-mirror.com` 或使用 Clash 代理。
- Windows 当前会使用 semantic exact-scan fallback，因为 VECTOR index 不可用。
- GitNexus 生成的 `.gitnexus/` 与 `logs/gitnexus/` 是本地资产，不提交。
- GitNexus 生成的 `.claude/skills/generated/` 也是本地资产，不提交；通用 `.claude/skills/gitnexus/` 可以跟随仓库。
- 运行 `gitnexus serve` 后如果从脚本启动，注意清理子 `node.exe` 进程，避免占用 `4747` 端口。

## 一遍过排错表

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `-1073741819` | `gitnexus@1.6.3` 原生崩溃 | `npm install -g gitnexus@rc` |
| `Analysis failed: fetch failed` | HuggingFace 模型下载失败 | 用 `-Proxy "http://127.0.0.1:17891"` 或默认 `hf-mirror.com` |
| `Database ID for ... lbug.wal does not match` | 半成品索引残留 | 删除 `.gitnexus/` 后重跑 |
| `VECTOR extension not supported` | Windows 当前 VECTOR 不可用 | 接受 exact-scan fallback |
| `gitnexus serve` 端口占用 | 上次 node 子进程未关 | 关闭对应 `node.exe` 或换端口 |
| Web UI 卡在 `Downloading... 0.0 MB` | 图谱流较大或页面仍在解析 | 等待 30-60 秒；若仍无结果，检查 `/api/graph` 输出大小 |
| `detect_changes` 出现 lbug 文件锁 | `gitnexus serve` 正在占用图数据库 | 关闭 4747 对应 `node.exe` 后重跑 |
