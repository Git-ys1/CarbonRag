# Open Collaboration Guide

版本：V1.2.5

## 目的

这份指南是 CarbonRag 所有席位共同遵守的开放协作协议。它解决四件事：

- 哪些协作资产必须提交到云端。
- 哪些本地资产必须继续忽略，以及如何在新机器上重建。
- OpenSpec、Codex、VS Code、终端分别负责什么。
- #1、#2、#3 如何开发、审查、测试、合并。

## 角色

- #1 首席团队：可以在 upstream 仓库开 `t1/v1.2/<topic>` 分支，进入 `main` 前仍要保留 OpenSpec、验证与审查记录。
- #2 / #3 后续席位：默认 fork-and-PR，不直接 push `main`。
- `Git-ys1`：`main` 最终管理员、PR 最终审查人、CODEOWNERS fallback owner。

## 分支

- `main`：稳定源码基线，也是所有席位 fork/clone 的共同入口。
- `t1/v1.2/<topic>`：#1 开发分支。
- `t2/v1.2/<topic>`：#2 fork 内开发分支。
- `hotfix/t1/v1.2/<topic>`：#1 紧急修复分支。
- `hotfix/t2/v1.2/<topic>`：#2 fork 内紧急修复分支。
- `release/cloud-stable`：历史兼容线，默认不再作为协作入口。

## OpenSpec 与 Codex 的边界

- OpenSpec 是规格、变更、任务、归档和协作规则层，不是后台服务。
- Codex 是读取 OpenSpec 后执行代码修改或辅助审查的 agent。
- GitNexus 是代码结构、调用链和影响范围分析层。
- Mattermost 是施工中实时协同层，用于 PLAN、ACK、BLOCK、LOCK、DECISION、CHANGED、REVIEW_READY。
- VS Code 是本地开发与 PR 审查环境。
- 终端是 OpenSpec、git、gh、测试命令的可信执行入口。

## 新功能纪律

新功能默认必须先有 OpenSpec change-id：

```text
openspec/changes/<change-id>/
```

Codex 施工前必须读取：

- `AGENTS.md`
- `openspec/AGENTS.md`
- `openspec/specs/**`
- 相关 `openspec/changes/<change-id>/**`
- `docs/governance/**`
- 相关模块文档

例外：

- docs-only 变更可以不建完整 change，但 PR 必须写明原因。
- emergency hotfix 可以先修，但必须在 PR 中补说明和后续 spec 同步计划。

## Mattermost 协同纪律

V1.4.7B 起，非平凡改动前必须检查 `carbonrag-control`。

- 普通模块内改动：发 PLAN，确认没有 active LOCK/BLOCK 后可继续。
- API、DB、auth、deploy、model provider、carbon engine、RAG core、跨模块改动：发 PLAN 后等待 #1 ACK。
- 阶段完成发 CHANGED。
- 开 PR 前发 REVIEW_READY。
- GitHub webhook 只进入 `carbonrag-log`，不替代控制频道。

## 必须提交到云端的协作资产

- `AGENTS.md`
- `openspec/**`
- `.codex/skills/**`
- `.github/CODEOWNERS`
- `.github/PULL_REQUEST_TEMPLATE.md`
- `.github/workflows/**`
- `docs/governance/**`
- `docs/architecture/**`
- `docs/PLAN/**`
- `scripts/dev-local.ps1`
- `scripts/dev-local.sh`
- `scripts/bootstrap.ps1`
- `scripts/bootstrap.sh`
- `.env.example`
- `frontend/.env.example`
- `frontend/.env.production`
- `README.md`

## 必须继续忽略的本地资产

这些文件不提交不是“缺少原版”，而是因为它们应由模板、脚本或依赖安装在每台机器上重建：

- `.env`
- `.env.local`
- `frontend/.env.local`
- `.venv/`
- `backend/.conda/`
- `node_modules/`
- `frontend/node_modules/`
- `.spec-gen/`
- `3rdparty/spec-gen/`
- `*.sqlite`
- `*.sqlite3`
- `*.db`
- `uploads/`
- `data/outputs/**`
- API key
- 本地模型路径
- 本地分析缓存

## #2 能不能本地测试

可以。#2 不需要你的本机 `.env`、SQLite、uploads 或 `.spec-gen/`。#2 需要的是：

- 云端仓库里的源码、OpenSpec、docs、scripts、env 模板。
- 自己机器上的 Node.js、Python、Git、OpenSpec CLI。
- 自己复制生成的 `.env` 和 `frontend/.env.local`。
- 自己本地生成的依赖目录和 SQLite runtime 数据。

## 标准验证顺序

每个席位拿到仓库后先跑：

```powershell
openspec list
openspec validate --all
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/bootstrap.ps1
```

开发本地联调再跑：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/dev-local.ps1
```

## 合并纪律

- #1 自有治理/文档基线可在完整验证后自审合入 `main`。
- #2/#3 必须 fork-and-PR。
- PR 必须填写 OpenSpec、模块、风险、验证和批准字段。
- #1 可以用 Codex 辅助审查，但最终 approve/request changes 必须由 #1 人工决定。
