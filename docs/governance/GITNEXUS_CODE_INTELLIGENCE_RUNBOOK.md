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

脚本等价于：

```powershell
gitnexus analyze --force --embeddings --skills --verbose
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

## 开工前固定顺序

```powershell
openspec validate --all
gitnexus status
gitnexus query <topic>
gitnexus impact <symbol>
```

不要只靠 `rg` 找文件就开始改复杂模块。

## 已知问题

- `gitnexus@1.6.3` 在本机和极小临时 repo 上均可复现原生崩溃，退出码 `-1073741819`。
- `--embeddings` 需要下载 HuggingFace 模型；网络失败时设置 `HF_ENDPOINT=https://hf-mirror.com` 或使用 Clash 代理。
- Windows 当前会使用 semantic exact-scan fallback，因为 VECTOR index 不可用。
- GitNexus 生成的 `.gitnexus/` 与 `logs/gitnexus/` 是本地资产，不提交。
- 运行 `gitnexus serve` 后如果从脚本启动，注意清理子 `node.exe` 进程，避免占用 `4747` 端口。

## 一遍过排错表

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `-1073741819` | `gitnexus@1.6.3` 原生崩溃 | `npm install -g gitnexus@rc` |
| `Analysis failed: fetch failed` | HuggingFace 模型下载失败 | 用 `-Proxy "http://127.0.0.1:17891"` 或默认 `hf-mirror.com` |
| `Database ID for ... lbug.wal does not match` | 半成品索引残留 | 删除 `.gitnexus/` 后重跑 |
| `VECTOR extension not supported` | Windows 当前 VECTOR 不可用 | 接受 exact-scan fallback |
| `gitnexus serve` 端口占用 | 上次 node 子进程未关 | 关闭对应 `node.exe` 或换端口 |
