# Tracked Collaboration Asset Inventory

版本：V1.2.5

## 目的

明确哪些文件必须进入云端，哪些必须继续忽略。原则是：协作所需的源码、规格、脚本、模板、文档必须提交；机器本地状态、密钥、依赖缓存、运行时数据必须忽略。

## 必须提交

- `AGENTS.md`
- `openspec/**`
- `.codex/skills/**`
- `.claude/skills/gitnexus/**`
- `.github/CODEOWNERS`
- `.github/PULL_REQUEST_TEMPLATE.md`
- `.github/workflows/**`
- `docs/governance/**`
- `docs/architecture/**`
- `docs/PLAN/**`
- `docs/deploy/**`
- `docs/DEVELOPMENT_BOOTSTRAP.md`
- `scripts/bootstrap.ps1`
- `scripts/bootstrap.sh`
- `scripts/dev-local.ps1`
- `scripts/dev-local.sh`
- `.env.example`
- `frontend/.env.example`
- `frontend/.env.production`
- `README.md`
- 产品或 UX 审查文档，只要不包含密钥、私人信息或本地路径秘密

## 必须忽略

- `.env`
- `.env.local`
- `frontend/.env.local`
- `.venv/`
- `backend/.venv/`
- `backend/.conda/`
- `node_modules/`
- `frontend/node_modules/`
- `.spec-gen/`
- `.gitnexus/`
- `.claude/skills/generated/`
- `3rdparty/spec-gen/`
- `*.sqlite`
- `*.sqlite3`
- `*.db`
- `uploads/`
- `data/outputs/**`
- `.pytest_cache/`
- `.vite/`
- `frontend/dist/`
- `*.log`
- `logs/gitnexus/`
- API key
- 本地模型路径
- 本地 agent session
- IDE 私有配置

## 可选提交

- 人工审查后的 spec-gen 摘要文档。
- 已脱敏的产品审查文件。
- 可复现的架构图、流程图、发布说明。
- 不含真实客户数据的样例数据。

## 绝对禁止提交

- 真实 API key、数据库密码、令牌、cookie。
- 真实企业客户数据、真实合同、真实账单、真实员工信息。
- 本地 `.env` 或生产 `/etc/carbonrag/carbonrag.env` 内容。
- 本地模型权重、模型缓存、私有向量库索引。
- 未脱敏的日志、截图、导出数据。

## 忽略文件不是“原版缺失”

新席位从云端拿不到 `.env`、`node_modules/`、SQLite、uploads 是正确的。

恢复方式：

- `.env` 从 `.env.example` 复制。
- `frontend/.env.local` 从 `frontend/.env.example` 复制。
- `node_modules/` 由 `npm ci` 生成。
- Python 环境由 bootstrap 或 `python -m venv .venv` 生成。
- SQLite/runtime/upload 数据由本地运行生成。
- `.spec-gen/` 由本地 spec-gen analyze 重新生成。
- `.claude/skills/generated/` 由 `gitnexus analyze --skills` 重新生成；不要提交，否则会被下一轮索引再次读入并造成模块 skill 抖动。

## V1.2.5 本地清点命令

```powershell
git status --ignored -sb
git ls-files
git ls-files -o --exclude-standard
git check-ignore -v .spec-gen/test.txt
git check-ignore -v 3rdparty/spec-gen/test.txt
git check-ignore -v .env
```

验收标准：未忽略文件必须被提交或明确处理；被忽略文件必须能由模板、脚本或本地运行重建。
