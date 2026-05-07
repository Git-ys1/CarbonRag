# Multi-Codex Coordination Protocol

版本：V1.4.7B

## 定位

Mattermost 是 CarbonRag 的施工中实时协同层，不是普通聊天群。

固定分工：

- OpenSpec：做什么、为什么做、边界和任务。
- GitNexus：代码在哪、依赖谁、影响面多大。
- Mattermost：PLAN、ACK、LOCK、BLOCK、DECISION、CHANGED、REVIEW_READY。
- GitHub：分支、PR、CI、review、merge。
- Codex：读取上述上下文后执行。

## 必须等待 #1 ACK 的改动

以下改动必须先在 `carbonrag-control` 发 PLAN，并等待 #1 ACK：

- API 契约
- 数据库 schema / migration / persistence
- auth / permission / user isolation
- deployment / env / cloud
- model provider / AI runtime
- carbon engine
- RAG core / retriever / parser / index
- 跨 M1-M8 模块改动

## 不需要等待 ACK 的改动

模块内小文档、测试补充、低风险 typo 或局部脚本整理，可以发 PLAN 后继续，但仍要确认没有 active LOCK/BLOCK。

## 阻断规则

- `BLOCK` 优先级高于所有 PLAN。
- `LOCK` 表示某个模块或文件组正在被席位占用。
- 任何 Codex 看到相关 BLOCK/LOCK 后必须停止修改，除非 #1 明确 UNLOCK 或 ACK。

## 消息格式

格式定义见 `.agents/skills/codex-coordination/references/message-format.md`。

