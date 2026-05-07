# GitNexus Graph Visualization Study

版本：V1.4.7

## 研究边界

GitNexus 许可证为 `PolyForm-Noncommercial-1.0.0`。CarbonRag 后续可能对外展示、参赛或商业化延展，因此本轮只学习图谱表达思想，不复制 GitNexus UI、图渲染代码或实现细节。

## GitNexus 图谱表达

GitNexus 本机索引 CarbonRag 后生成：

- nodes：代码实体，例如 File、Function、Class、Method、Property、Process、Community。
- edges：代码关系，例如 imports、calls、defines、has_method、has_property、member_of。
- clusters：按代码社区聚类，形成 Tests、Rag、Knowledge、Carbon、AskPage 等功能区。
- processes：执行流或跨社区调用链，用来理解“一个入口最终走到哪里”。

## 对 CarbonRag 的启发

GitNexus 图谱是代码知识图谱。CarbonRag 未来要做的是企业低碳知识图谱，两者不能直接混用，但表达方式可借鉴：

- 用节点表达实体。
- 用边表达依据、计算、归属、生成关系。
- 用 cluster 表达业务域。
- 用 process 表达从用户问题到检索、计算、报告的链路。

## CarbonRag 知识图谱第一版建议

节点：

- `Policy`
- `Standard`
- `EmissionFactor`
- `ActivityItem`
- `CarbonInventory`
- `Report`
- `PrivateKnowledgeFile`
- `Session`
- `Citation`
- `Organization`
- `Facility`

边：

- `cites`
- `uses_factor`
- `calculated_from`
- `belongs_to_session`
- `generated_report`
- `derived_from_file`
- `applies_to_region`
- `applies_to_scope`

## 不借的部分

- 不复制 GitNexus Web UI。
- 不复制 GitNexus 图数据库 schema。
- 不把 GitNexus `.gitnexus/lbug` 作为 CarbonRag 业务数据。
- 不把代码图谱能力暴露给普通 CarbonRag 用户。

## 后续方向

CarbonRag 可以在 V1.5.x 之后考虑自有“低碳知识图谱”页面，但它应基于 CarbonRag 的 policy / factor / inventory / report 数据模型实现，而不是复刻 GitNexus。
