# PR Review Runbook

版本：V1.2.5

## 目标

固定 #1 如何审查 #2/#3 的 PR。Codex 可以辅助，但最终 approve/request changes 必须由 #1 人工决定。

## 工具

- GitHub Web PR 页面
- VS Code GitHub Pull Requests 扩展
- GitHub CLI `gh`
- Codex CLI 或 VS Code Codex
- OpenSpec CLI

## GitHub CLI 登录

```powershell
gh auth status
```

未登录时：

```powershell
gh auth login
```

登录后再检查：

```powershell
gh pr list
```

## Checkout PR

```powershell
cd F:\Project\CarbonRag
gh pr checkout <PR编号>
```

如果不用 gh，可在 GitHub PR 页面复制 checkout 命令，或用 VS Code GitHub Pull Requests 扩展 checkout。

## 查看差异

```powershell
git fetch origin main
git diff origin/main...HEAD
```

## 必跑检查

```powershell
openspec validate --all
```

V1.4.7 起，非 docs-only PR 还要跑 GitNexus 影响分析：

```powershell
gitnexus status
gitnexus detect_changes
```

如果索引不存在或过期：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/gitnexus-full-index.ps1 -Proxy "http://127.0.0.1:17891"
```

V1.4.7B 起，PR 审查还要检查 Mattermost 协同记录：

- PR 是否对应 `carbonrag-control` 中的 PLAN。
- 高风险改动是否有 #1 ACK。
- 是否有未解除的 BLOCK / LOCK。
- PR ready 前是否发过 REVIEW_READY。

后端：

```powershell
cd backend
python -m pytest
cd ..
```

前端：

```powershell
cd frontend
npm run typecheck
npm run build
cd ..
```

如果 PR 是 docs-only，可在 review 中说明为什么跳过某些业务测试。

## 让 Codex 辅助审查

给 Codex 的固定输入：

```text
你现在只做 PR 审查，不改代码。
请读取 AGENTS.md、openspec/specs/**、docs/governance/**、.github/PULL_REQUEST_TEMPLATE.md、.github/CODEOWNERS。
请审查 origin/main...HEAD 的 diff，并使用 GitNexus MCP 或 CLI 的 detect_changes / impact / context，判断：
1. 是否有 OpenSpec change-id
2. 是否越过模块边界
3. 是否修改 API / DB / 权限 / 部署 / 模型调用
4. Mattermost control 中是否有 PLAN / ACK / BLOCK / REVIEW_READY
5. 是否缺测试或缺文档
6. 是否应该 approve、comment、request changes
输出审查报告。
```

## 审查结论

Approve：

```powershell
gh pr review <PR编号> --approve
```

Request changes：

```powershell
gh pr review <PR编号> --request-changes -b "请先补齐 OpenSpec change-id、验证结果和模块影响说明。"
```

Comment：

```powershell
gh pr review <PR编号> --comment -b "这里有一个非阻塞建议：..."
```

## VS Code 审查路径

1. 安装 GitHub Pull Requests 扩展。
2. 登录 GitHub。
3. 在 Pull Requests 视图中打开 PR。
4. Checkout PR 到本地。
5. 运行 OpenSpec 和测试。
6. 用 Codex 只读审查 diff。
7. #1 人工决定 approve / request changes / comment。

## 不允许

- 不允许只看 Codex 结论就合并。
- 不允许没有 OpenSpec change-id 的功能 PR 进入 main。
- 不允许 #2/#3 直接 push main。
- 不允许把本地 `.env`、runtime data 或 API key 混进 PR。
