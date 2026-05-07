# OpenSpec + Codex Workflow Runbook

版本：V1.2.5

## 核心判断

OpenSpec 不需要长期运行后台服务。它是规格和变更工作流。Codex 是执行者，可以处理 Git、OpenSpec、检查和提交，但必须按仓库纪律执行，不能自由发挥。

CarbonRag 已经是 brownfield 项目，已经有 `openspec/config.yaml` 和 `openspec/specs/**`。因此：

- 不要重复执行 `openspec init`。
- 当前工作区首次打通使用 `openspec update .`、`openspec list`、`openspec validate --all`。
- 如果 `openspec update .` 提示删除 `openspec/AGENTS.md`，默认回答 `n`，直到 #1 确认内容已迁移。

## 长期开发三步

OpenSpec 的长期开发流程固定为：

```text
propose -> apply -> archive
```

这三个词是阶段名，不是 PowerShell 顶层命令。当前本机 OpenSpec CLI 没有 `openspec propose`，也没有 `openspec apply`。

不要在 PowerShell 里运行：

```powershell
openspec propose
openspec-propose
/opsx:propose
```

当前本机真实可执行的 OpenSpec 命令是：

```powershell
openspec new change <change-id>
openspec status --change <change-id>
openspec instructions <artifact-id> --change <change-id>
openspec validate <change-id> --strict
openspec archive <change-id> --yes
```

## #1 日常最简流程

#1 不需要每轮手动记命令。正常开发时，把任务书交给 Codex，并明确一句：

```text
请按 CarbonRag OpenSpec 工作流开工。
```

Codex 应自动执行：

1. 从任务书派生或确认 `change-id`。
2. 读取 `AGENTS.md`、`openspec/AGENTS.md`、`openspec/specs/**`、`docs/governance/**`。
3. 运行 `openspec list`、`openspec validate --all`。
4. 用 `openspec new change <change-id>` 创建 change，或继续已有 change。
5. 生成或检查 proposal/design/tasks/delta spec。
6. 停在 propose 阶段等待 #1 审查，不直接改业务代码。

如果 #1 想在终端里手动预创建 change，使用仓库脚本：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/openspec-start-change.ps1 -Id <change-id> -Goal "<一句话目标>" -Domain <domain>
```

这个脚本不是后台服务，只是一次性创建 change 并打印可复制给 Codex 的标准提示词。

### 第一步：propose 阶段

目标：让 Codex 分析当前代码库和规格，生成 `proposal.md`、delta spec、`design.md`、`tasks.md`。这一步不写业务代码。

PowerShell 里先创建 change：

```powershell
openspec new change <change-id>
openspec status --change <change-id>
```

再按 `status` 输出的 artifact id 获取写作说明：

```powershell
openspec instructions <artifact-id> --change <change-id>
```

然后把下面这段发给 Codex，不是发给 PowerShell：

```text
执行本轮 OpenSpec propose 阶段。
你可以处理 Git 和 OpenSpec，但必须遵守 AGENTS.md、openspec/AGENTS.md、openspec/specs/**、docs/governance/**。
先检查当前工作区、当前分支、远端状态、OpenSpec 状态和未忽略文件。
不要重复 openspec init。
如需运行 openspec update .，遇到删除 openspec/AGENTS.md 或 instruction 文件的提示，默认选择 n。
先输出你准备执行的 Git/OpenSpec 步骤；只有安全的只读检查可以直接执行。
涉及 commit、push、merge、rebase、删除、reset 的操作，必须说明原因和目标后再执行。
本轮 change-id: <change-id>。
本轮目标: <一句话目标>。
只做 propose：生成或检查 proposal.md、design.md、tasks.md、specs/<domain>/spec.md。
生成后停止，等待 #1 审查，不要 apply。
```

写完 propose 产物后校验：

```powershell
openspec validate <change-id> --strict
openspec validate --all
```

### 第二步：apply 阶段

目标：#1 审查通过后，让 Codex 按 `tasks.md` 实现代码。

当前 OpenSpec CLI 不提供 `openspec apply` 顶层命令。`apply` 的实际含义是：Codex 读取 `openspec/changes/<change-id>/**` 和相关主规格，然后按 `tasks.md` 改代码。

```text
执行本轮 OpenSpec apply 阶段。
change-id: <change-id>。
先读取 openspec/changes/<change-id>/** 和相关 openspec/specs/**。
严格按 tasks.md 实现。
不要擅自扩大范围。
涉及 commit、push、merge、rebase、删除、reset 的操作，必须说明原因和目标后再执行。
实现后运行本轮要求的测试，并汇总结果。
```

### 第三步：archive 阶段

目标：验证通过后，把 delta spec 合并进 `openspec/specs/**`，并保留归档记录。

这一步有真实 CLI 命令：

```powershell
openspec archive <change-id> --yes
openspec validate --all
```

```text
执行本轮 OpenSpec archive 阶段。
change-id: <change-id>。
先确认 tasks.md 全部完成、测试通过、文档已同步。
然后归档 change，把增量规格合并进 openspec/specs/**。
归档后运行 openspec validate --all。
```

## `openspec show governance` 是什么？

`openspec show governance` 只是查看协作规则，不是查看“当前要做什么”。当前要做什么，要看：

```powershell
openspec list
openspec show <change-id>
```

如果需要中文解释，看：

```text
docs/governance/GOVERNANCE_SPEC_CN.md
```

## 每轮流程

### 1. Codex 先检查

Codex 先执行或建议：

```powershell
git status -sb
git branch --show-current
openspec list
openspec validate --all
```

从 V1.4.7 起，复杂代码改动还要检查 GitNexus：

```powershell
gitnexus status
gitnexus query <topic>
gitnexus impact <symbol>
```

如果本机尚未索引：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/gitnexus-full-index.ps1 -Proxy "http://127.0.0.1:17891"
```

OpenSpec 负责变更边界；GitNexus 负责代码结构和影响范围。

从 V1.4.7B 起，多席位非平凡改动还要检查 Mattermost：

```powershell
$env:MATTERMOST_URL="http://8.141.111.33:8065"
$env:MATTERMOST_TEAM="carbonrag"
$env:MATTERMOST_CHANNEL="carbonrag-control"
```

Codex 必须读取 `carbonrag-control` 最近消息，确认没有 active `BLOCK` / `LOCK` / 冲突 `DECISION`，再发 `PLAN`。
涉及 API、DB、auth、deployment、model provider、carbon engine、RAG core 或跨模块改动时，必须等 #1 `ACK` 后才能进入 apply。

如果任务需要同步远端，Codex 可以执行只读：

```powershell
git fetch origin
```

是否切分支、提交、推送，由 Codex 根据任务目标提出并执行，但必须遵守 PR 和 main 纪律。

### 2. 刷新 OpenSpec 指令

```powershell
openspec update .
openspec list
openspec validate --all
```

如果 `openspec update .` 提示清理 `openspec/AGENTS.md`，默认选 `n`。

### 3. 创建 change

优先使用真实 OpenSpec CLI：

```powershell
openspec new change <change-id>
openspec status --change <change-id>
openspec instructions <artifact-id> --change <change-id>
```

如果 CLI 或 Codex skill 不可用，再手动创建：

```text
openspec/changes/<change-id>/proposal.md
openspec/changes/<change-id>/design.md
openspec/changes/<change-id>/tasks.md
openspec/changes/<change-id>/specs/<domain>/spec.md
```

### 4. 编写 proposal

至少写清：

- 为什么要改
- 改什么
- 不改什么
- 影响模块
- 验收方式

### 5. validate change

```powershell
openspec validate <change-id> --strict
```

若 CLI 对单个 change 的命令格式因版本不同失败，执行：

```powershell
openspec validate --all
```

并把失败原因写入 PR。

### 6. 让 Codex 执行 propose 阶段

给 Codex 的固定输入模板：

```text
先读取 AGENTS.md、openspec/AGENTS.md、openspec/specs/**、openspec/changes/<change-id>/**、docs/governance/** 和相关架构文档。
本轮 change-id: <change-id>。
先生成或检查 proposal/design/tasks/delta spec。
生成后停止，等待 #1 审查。
不允许无 change-id 直接 apply。
如果 OpenSpec skill 不可自动调用，请按文档手动读取和执行。
```

### 7. 审查通过后执行 apply 阶段

只有 proposal/design/tasks/delta spec 审查通过后，才让 Codex apply。apply 阶段仍然要按 tasks 执行，并在每个高风险 Git 操作前说明目的。

## Codex 只读审查模板

```text
你现在只做只读审查，不改代码。
请读取 AGENTS.md、openspec/specs/**、docs/governance/**、.github/PULL_REQUEST_TEMPLATE.md、.github/CODEOWNERS。
请审查 origin/main...HEAD 的 diff，判断：
1. 是否有 OpenSpec change-id
2. 是否越过模块边界
3. 是否修改 API / DB / 权限 / 部署 / 模型调用
4. 是否缺测试或缺文档
5. 应该 approve、comment 还是 request changes
输出审查报告。
```

## 什么时候 archive

当一个 change 已经实现、测试通过、PR 合并，才执行 archive。未实现或只处于 proposal 的 change 留在 `openspec/changes/**`。

```powershell
openspec archive <change-id> --yes
openspec validate --all
```

## spec-gen 的位置

spec-gen 只用于 brownfield baseline draft：

- 可本地 clone 到 `3rdparty/spec-gen`
- 输出在 `.spec-gen/`
- 生成内容必须人工校验
- 不提交 `.spec-gen/` 或 `3rdparty/spec-gen/`
- 最终事实源仍是 `openspec/specs/**`
