# GitNexus + Codex MCP Checklist

版本：V1.4.7

## 安装状态

- [x] `gitnexus@rc` 已安装。
- [x] 本机版本：`1.6.4-rc.84`。
- [x] `codex mcp add gitnexus -- npx -y gitnexus@rc mcp` 已执行。
- [x] `codex mcp list` 能看到 `gitnexus`。

## 完整索引状态

- [x] `.gitnexus/lbug` 已生成。
- [x] `--embeddings` 已执行并生成语义向量。
- [x] `--skills` 已执行，生成 20 个 module-level skills。
- [x] `--verbose` 已执行，日志保存在本地 `logs/gitnexus/`。
- [x] `AGENTS.md` 已写入 GitNexus context。
- [x] `CLAUDE.md` 已写入 GitNexus context。

## 本机结论

最终成功命令：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/gitnexus-full-index.ps1 -Proxy "http://127.0.0.1:17891" -HfEndpoint "https://huggingface.co"
```

如果没有代理，使用默认脚本也可走 `hf-mirror.com`：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/gitnexus-full-index.ps1
```

## 必测查询

```powershell
gitnexus query carbon --limit 3
gitnexus impact CarbonCalculationEngine
gitnexus detect_changes
```

本机结果：

- `gitnexus query carbon` 同时返回 BM25 与 vector timing。
- `gitnexus impact CarbonCalculationEngine` 返回 LOW risk，影响 `carbon/service.py`、`report/service.py`、`calc_carbon.py` 等上游引用。
- `gitnexus detect_changes` 能识别当前文档/agent 指令改动影响范围。
- `gitnexus serve --host 127.0.0.1 --port 4747` 能启动 Web UI 服务，端口 `4747` 本机可连接。
- Web UI 已验证可进入 CarbonRag 图谱页，能看到文件树、画布、`8230 nodes / 15975 edges`，并能在 Code Inspector 中查看 `backend/app/carbon/engine.py`。
- 首次进入图谱时可能显示 `Downloading... 0.0 MB`，等待 30-60 秒；若仍无结果，按 runbook 检查 `/api/graph?repo=CarbonRag&stream=true`。

## Codex 使用口令

```text
先读取 AGENTS.md、openspec/specs/**、当前 openspec/changes/**。
然后使用 GitNexus MCP：
1. 读取 gitnexus://repos。
2. 读取 CarbonRag repo context。
3. 对本轮涉及模块执行 context / query。
4. 如果涉及改动，先执行 impact 或 detect_changes。
5. 给出影响面和风险后，再按 OpenSpec tasks 实现。
```

## 验收限制

VS Code Codex 插件的 MCP 可视化调用以实际插件 UI 为准；如果插件 UI 不暴露 MCP 调用日志，则以 Codex CLI `codex mcp list` 与 GitNexus CLI query/impact/detect_changes 作为最低可接受证据。

## 代理说明

有 Clash 时建议使用：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/gitnexus-full-index.ps1 -Proxy "http://127.0.0.1:17891" -HfEndpoint "https://huggingface.co"
```

如果不用代理，脚本默认走 `https://hf-mirror.com`。两种方式都不改变仓库源码，只影响本机下载 GitNexus embedding 模型和 LadybugDB 扩展。

## #2/#3 复刻检查

- [ ] 确认 Node / npm 可用。
- [ ] 执行 `npm install -g gitnexus@rc`。
- [ ] 确认 `gitnexus --version` 是 `1.6.4-rc.*`。
- [ ] 执行 `codex mcp add gitnexus -- npx -y gitnexus@rc mcp`。
- [ ] 执行完整索引脚本。
- [ ] 执行 `gitnexus query carbon --limit 3`。
- [ ] 执行 `gitnexus impact CarbonCalculationEngine`。
- [ ] 执行 `gitnexus detect_changes`。
- [ ] 记录本机是否需要代理、代理端口是多少。
