# CarbonRag Mattermost Message Format

All Codex coordination messages must begin with a machine-readable prefix:

```text
[#<seat>][<TYPE>][<VERSION>][change-id=<change-id>][module=<module>][risk=<risk>]
```

Allowed message types:

- `PLAN`
- `ACK`
- `BLOCK`
- `LOCK`
- `UNLOCK`
- `DECISION`
- `CHANGED`
- `REVIEW_READY`
- `ABORT`

Example PLAN:

```text
[#2][PLAN][V1.4.8][change-id=carbon-inventory-trust-baseline][module=M6][risk=medium]
目标：
将 carbon inventory persistence 接入 V2 activity_items。

将改动：
backend/app/carbon/service.py
backend/app/carbon/storage.py
backend/tests/test_carbon_inventory_persistence.py

不会改动：
auth
RAG
frontend AskPage
deployment

需要 #1 确认：
是否允许新增 carbon_inventory 表。
```

Example ACK:

```text
[#1][ACK][V1.4.8][change-id=carbon-inventory-trust-baseline]
允许新增 carbon_inventory 表。
要求补 migration / SQLite fallback / PostgreSQL smoke。
```

Example BLOCK:

```text
[#1][BLOCK][V1.4.8][module=M2]
暂停修改 session/message persistence。该区域正在被 #1 排查。
```

Example CHANGED:

```text
[#2][CHANGED][V1.4.8][change-id=carbon-inventory-trust-baseline][risk=medium]
已改：
...

已跑测试：
...

未解决风险：
...
```

Example REVIEW_READY:

```text
[#2][REVIEW_READY][PR=draft][change-id=carbon-inventory-trust-baseline]
OpenSpec：已更新
GitNexus impact：已跑
测试：通过
需要 #1 早期审查
```

