# Mattermost Channel Protocol

版本：V1.4.7B

## 频道

只建三个频道：

| 频道 | 用途 |
| --- | --- |
| `carbonrag-control` | PLAN、ACK、BLOCK、LOCK、DECISION、CHANGED、REVIEW_READY、ABORT |
| `carbonrag-review` | 早期 review、PR review、跨模块讨论 |
| `carbonrag-log` | GitHub webhook、CI、部署、GitNexus 摘要、自动日志 |

## 账号

初始账号：

- `t1-director`
- `t1-codex`
- `t2-director`
- `t2-codex`

后续席位按同样格式扩展：

- `t3-director`
- `t3-codex`

Codex 不使用人类账号 PAT。每个 Codex 只使用自己的 Mattermost Personal Access Token。

## carbonrag-control

必须使用机器可读消息前缀。不得把关键决策散落在无格式闲聊里。

允许消息类型：

- `PLAN`
- `ACK`
- `BLOCK`
- `LOCK`
- `UNLOCK`
- `DECISION`
- `CHANGED`
- `REVIEW_READY`
- `ABORT`

## carbonrag-review

用于早期审查，不替代 GitHub PR review。最终 approve / request changes 仍在 GitHub。

## carbonrag-log

用于自动日志。GitHub webhook 只发到这里，不发到 control。

