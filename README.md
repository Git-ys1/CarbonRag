# CarbonRag

当前状态：`V1.4.7 GitNexus 结构感知工作流试点 / V1.4.x 碳核算主线由 #1 负责 / V1.3.x RAG 主线由 #2 负责`

CarbonRag 是面向中小企业低碳管理场景的 AI 工作台。项目目标不是做一个泛用聊天壳，而是把“政策问答、私有知识、碳核算、报告生成、反馈闭环、多人治理”整合成一套可试用、可部署、可协作演进的垂直系统。

## 现在先看什么？

- 新人和 #2/#3 入场：先看 [快速上手.md](快速上手.md)
- 全体协作规则：看 [开发公告.md](开发公告.md)
- OpenSpec + Codex 怎么开工：看 [docs/governance/OPENSPEC_CODEX_WORKFLOW_RUNBOOK.md](docs/governance/OPENSPEC_CODEX_WORKFLOW_RUNBOOK.md)
- GitNexus + Codex MCP 怎么跑：看 [docs/governance/GITNEXUS_CODE_INTELLIGENCE_RUNBOOK.md](docs/governance/GITNEXUS_CODE_INTELLIGENCE_RUNBOOK.md)
- Mattermost + Codex 多 Agent 协同怎么跑：看 [docs/governance/MATTERMOST_CODEX_COORDINATION_RUNBOOK.md](docs/governance/MATTERMOST_CODEX_COORDINATION_RUNBOOK.md)
- PR 怎么审：看 [docs/governance/PR_REVIEW_RUNBOOK.md](docs/governance/PR_REVIEW_RUNBOOK.md)
- 本地怎么跑：看 [docs/DEVELOPMENT_BOOTSTRAP.md](docs/DEVELOPMENT_BOOTSTRAP.md)
- 云端怎么部署：看 [docs/deploy/VPS_BACKEND_DEPLOY.md](docs/deploy/VPS_BACKEND_DEPLOY.md) 和 [docs/deploy/NETLIFY_FRONTEND.md](docs/deploy/NETLIFY_FRONTEND.md)

## 当前开发公告

### V1.3.x：RAG / LightRAG 主线由 #2 正统负责

#2 团队当前专攻 `LightRAG-inspired RAG architecture` 与后续 V1.3.x 实现。#1 不在 V1.3.x 中抢线开发，只负责：

- 审查 #2 的 OpenSpec 提案、PR、测试和实现边界。
- 确认许可证、模块边界、fallback、安全默认值。
- 在 #2 阶段性成果到达 PR 后做最终 review / approve / request changes。

当前原则：V1.3.x 的 RAG 代码成果等 #2 完成最小可验证功能后再进入 `main`，不把半成品提前发布到主线。

### V1.4.x：碳核算主线由 #1 负责

#1 团队从 V1.4.0 起专攻碳核算能力。目标是把现有 `calc-carbon` 从最小三项活动数据计算，推进到更接近企业试用需要的碳核算模块。

V1.4.x 初步方向：

- 扩展活动数据结构与核算项目表达。
- 强化排放因子管理、来源、版本与引用。
- 增强计算结果持久化、可追溯性和报告衔接。
- 保持与 session、report、feedback、auth 数据隔离一致。
- 不打乱 #2 的 V1.3.x RAG 主线。

详见 [docs/PLAN/V1.4.0.md](docs/PLAN/V1.4.0.md)。

## 已具备的产品能力

### 会话与问答

- 支持 session conversation workbench。
- 支持 `public / private_sample / mixed` 三种 ask scope。
- 支持 grounded citations。
- 支持用户隔离，只能访问自己的会话、报告、反馈、计算结果与上传资产。
- 支持 session summary / context compaction / memory state 的基础能力。

### 知识库

- 支持个人知识库与管理员共享知识库。
- 上传文件进入知识任务流。
- 支持 parse / ingest / index 状态。
- 支持失败重试、管理员扫描、重建与任务查看。
- private / mixed 检索以当前 session 已挂接知识条目为边界。

### 碳核算

当前 `calc-carbon` 已支持：

- 旧三字段输入：`electricity_kwh`、`natural_gas_m3`、`diesel_l`。
- 新 V1.4.4 输入：`activity_items[]`。
- Scope 1 stationary/mobile combustion 基础核算。
- Scope 2 purchased electricity location-based 核算。
- 分项排放量、总排放量、因子来源 citation。
- factor snapshot、unit conversion trace、formula trace、source summary、warnings。
- 结果持久化并可按 session 关联。

当前官方电力因子种子使用生态环境部、国家统计局 2023 年电力二氧化碳排放因子；燃料因子仍为 demo，不用于正式审计。

### 报告生成

- 支持 `policy_summary`
- 支持 `mixed_analysis`
- 支持 `carbon_summary`
- 报告绑定 session。
- 报告可引用 ask citations 与 calc results。
- 报告可保存、重开、编辑。

### 反馈闭环

- Ask 与 calc/report 结果可提交反馈。
- 反馈写入运行时数据库。
- 管理员可查看反馈概览，但不直接读取普通用户正文内容。

### 身份与治理

- 使用 `HttpOnly Cookie` 服务端会话。
- 支持注册、登录、登出、改密。
- 角色：`user / admin`。
- 初始管理员：`admin / 123456`，首次登录强制改密。
- 如果 `admin` 账号丢失、被禁用或不可用，在注册页输入 `admin / 123456` 可恢复初始管理员并强制改密。

## 运行模式

### local-dev

本地开发环境，允许试错和破坏性验证。

- 前端：`http://127.0.0.1:5173`
- 后端：`http://127.0.0.1:8000`
- 前端 API：`http://127.0.0.1:8000/api`
- 数据库：SQLite fallback

启动：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/dev-local.ps1
```

### cloud-stable / main 发布基线

云端稳定验证环境。

- 前端：Netlify
- 后端：VPS
- 前端 API：`/api`
- 数据库：PostgreSQL
- 当前文档默认口径：`main` 是稳定源码与公网默认发布基线。

本地和云端不共享运行时数据。会话历史、报告、计算结果、反馈在两边不同是正常现象。

## 分支与协作纪律

- `main`：稳定源码基线和当前公网默认发布基线。
- `t1/v1.4/<topic>`：#1 V1.4.x 碳核算开发分支。
- `t2/v1.3/<topic>`：#2 V1.3.x RAG 开发分支。
- `t2/v1.2/<topic>`：#2 入场与治理验证历史分支。
- `release/cloud-stable`：保留兼容发布线，不再作为默认文档口径。

规则：

- `Git-ys1` 是 `main` 最终管理员和 PR 最终审查人。
- #2/#3 及后续席位必须 fork-and-PR。
- #1 可做自审与合并，但必须留下 OpenSpec / 验证 / PR 或提交记录。
- PR 必须声明 OpenSpec change-id、影响模块、风险、验证结果和审批状态。
- 不允许把半成品 feature 分支直接污染 `main`。

## OpenSpec 工作方式

CarbonRag 是 brownfield 项目，OpenSpec 已完成初始化，不要重复运行 `openspec init`。

日常开工前：

```powershell
openspec list
openspec validate --all
```

新功能默认流程：

1. `propose`：先创建 `openspec/changes/<change-id>/`，写 proposal / design / tasks / delta spec。
2. `apply`：审查通过后再让 Codex 按 tasks 实现。
3. `archive`：验证通过后归档变更，把增量规范合入主规格。

注意：`propose / apply / archive` 是工作阶段，不是 PowerShell 里的顶层命令。具体命令与手动文件结构见 [docs/governance/OPENSPEC_CODEX_WORKFLOW_RUNBOOK.md](docs/governance/OPENSPEC_CODEX_WORKFLOW_RUNBOOK.md)。

## GitNexus 结构感知工作方式

V1.4.7 起，#1 团队引入 GitNexus 作为本地代码知识图谱和影响分析工具。

推荐安装：

```powershell
npm install -g gitnexus@rc
codex mcp add gitnexus -- npx -y gitnexus@rc mcp
```

推荐索引：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/gitnexus-full-index.ps1 -Proxy "http://127.0.0.1:17891"
```

原则：

- OpenSpec 管“做什么、为什么、边界”。
- GitNexus 管“代码在哪、依赖谁、影响面多大”。
- Codex 读取 OpenSpec + GitNexus 后再改代码。

`.gitnexus/` 和 `logs/gitnexus/` 是本地生成物，不提交。

## Mattermost 多 Agent 协同方式

V1.4.7B 起，Mattermost 被定义为施工中的实时协同总线。

固定分工：

- OpenSpec 管“做什么、为什么、边界”。
- GitNexus 管“代码在哪、影响面多大”。
- Mattermost 管“PLAN、ACK、BLOCK、LOCK、DECISION、CHANGED、REVIEW_READY”。
- GitHub 管“PR、CI、review、merge”。

试点入口计划使用：

```text
http://8.141.111.33:8065
```

当前 `8065` 端口若不可达，说明 VPS 尚未部署 Mattermost 或安全组未放行。配置和验收见 [docs/governance/MATTERMOST_CODEX_COORDINATION_RUNBOOK.md](docs/governance/MATTERMOST_CODEX_COORDINATION_RUNBOOK.md)。

## 新席位本地启动

#2/#3 从自己的 fork 开始：

```powershell
git clone https://github.com/<your-github-username>/CarbonRag.git
cd CarbonRag
git remote add upstream https://github.com/Git-ys1/CarbonRag.git
git fetch upstream
git switch -c t2/v1.3/onboarding-smoke upstream/main
openspec list
openspec validate --all
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/bootstrap.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/dev-local.ps1
```

忽略文件不是“缺原版”，而是应由模板或依赖安装重建：

- `.env` 来自 `.env.example`
- `frontend/.env.local` 来自 `frontend/.env.example`
- `node_modules/` 来自 `npm ci`
- Python 环境来自 `scripts/bootstrap.ps1` 或 `backend/requirements.txt`
- SQLite / runtime / uploads 是本地实验数据
- `.spec-gen/` 是本地分析缓存

## 主要目录

- `backend/`：FastAPI 后端。
- `frontend/`：React/Vite 前端。
- `data/`：公共政策样本、private sample、因子数据。
- `openspec/`：规格库与变更提案。
- `docs/governance/`：协作、PR、OpenSpec、席位规则。
- `docs/architecture/`：架构流与模块边界。
- `docs/PLAN/`：版本施工计划。
- `scripts/`：bootstrap、local-dev、部署辅助脚本。

## 核心文档索引

- [快速上手.md](快速上手.md)
- [开发公告.md](开发公告.md)
- [docs/API_BOUNDARY_DRAFT.md](docs/API_BOUNDARY_DRAFT.md)
- [docs/DEVELOPMENT_BOOTSTRAP.md](docs/DEVELOPMENT_BOOTSTRAP.md)
- [docs/GIT_WORKFLOW.md](docs/GIT_WORKFLOW.md)
- [docs/GIT_RELEASE_FLOW.md](docs/GIT_RELEASE_FLOW.md)
- [docs/governance/OPEN_COLLABORATION_GUIDE.md](docs/governance/OPEN_COLLABORATION_GUIDE.md)
- [docs/governance/SEAT_ONBOARDING_RUNBOOK.md](docs/governance/SEAT_ONBOARDING_RUNBOOK.md)
- [docs/governance/OPENSPEC_CODEX_WORKFLOW_RUNBOOK.md](docs/governance/OPENSPEC_CODEX_WORKFLOW_RUNBOOK.md)
- [docs/governance/GITNEXUS_CODE_INTELLIGENCE_RUNBOOK.md](docs/governance/GITNEXUS_CODE_INTELLIGENCE_RUNBOOK.md)
- [docs/governance/GITNEXUS_CODEX_MCP_CHECKLIST.md](docs/governance/GITNEXUS_CODEX_MCP_CHECKLIST.md)
- [docs/governance/PR_REVIEW_RUNBOOK.md](docs/governance/PR_REVIEW_RUNBOOK.md)
- [docs/architecture/MODULE_BOUNDARY_MAP.md](docs/architecture/MODULE_BOUNDARY_MAP.md)
- [docs/PLAN/V1.4.0.md](docs/PLAN/V1.4.0.md)

## 当前公开 API 概览

### 公开接口

- `GET /healthz`

### 已登录用户接口

- auth：注册、登录、登出、me、改密。
- sessions：创建、列表、详情、改标题、ask。
- files / knowledge：上传、知识条目、任务、session 挂接。
- calc-carbon：碳核算。
- feedback：反馈。
- reports：报告生成、读取、编辑、session 报告列表。
- memory-notes：后端预留的用户级长期记忆接口。

### 管理员接口

- system status
- users
- feedback overview
- private samples
- knowledge items / tasks
- knowledge scan / rebuild / retry

完整边界见 [docs/API_BOUNDARY_DRAFT.md](docs/API_BOUNDARY_DRAFT.md)。
