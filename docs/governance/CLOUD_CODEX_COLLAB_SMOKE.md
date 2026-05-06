# Cloud Codex Collaboration Smoke

版本：V1.2.6

## 结论

Codex 可以通过 GitHub 参与云端协作：创建分支、提交 docs-only 变更、推送到远端、打开 PR，并让 #1 用 GitHub CLI / Web / VS Code PR 扩展审查。

但 CarbonRag 不采用“#1 Codex 直接私聊 #2 Codex”的模式。多席位 Codex 协作必须通过可审计记录完成：

- OpenSpec change
- Git branch
- GitHub Issue
- Pull Request
- PR review comments
- development log

## 为什么不用私聊式 agent-to-agent

私聊式 agent-to-agent 难以审计，#1 很难确认它们讨论了什么、依据是什么、是否越界。CarbonRag 需要的是单一领导者可统领、可追溯、可回滚的协作模式。

## 推荐协作面

| 协作内容 | 事实源 |
| --- | --- |
| 任务意图 | OpenSpec change / GitHub Issue |
| 实现变更 | Git branch / Pull Request |
| 依据与开发日志 | Issue comment / PR comment |
| 审查结论 | GitHub review |
| 最终批准 | #1 human approval |

## 本轮 smoke 怎么验证

本轮使用 docs-only PR 验证云端协作链路：

1. 从 `main` 创建 `t1/v1.2/cloud-codex-collab-smoke`。
2. 创建 OpenSpec change `cloud-codex-collab-smoke`。
3. 只修改治理文档和 OpenSpec delta。
4. 推送分支到 GitHub。
5. 打开 PR 到 `main`。
6. #1 执行只读审查：

```powershell
gh pr checkout <PR编号>
git fetch origin main
git diff origin/main...HEAD
openspec validate --all
```

7. #1 人工决定 approve / comment / request changes。

## #2 后续怎么用

#2 每轮任务必须留下这些公开记录：

```text
Change ID:
Branch:
Issue/PR:
Today changed:
Evidence:
Verification:
Blocked by:
Need #1 decision:
```

这样 #1 的 Codex 可以读取 PR / Issue / OpenSpec，辅助审查；#2 的 Codex 也能读取同一份公开上下文继续开发。

## 不做

- 不建立私有 agent-to-agent 聊天桥。
- 不让 Codex 绕过 PR 直接合 `main`。
- 不把 Slack/微信群当最终事实源。
- 不在 smoke PR 里改业务代码。
