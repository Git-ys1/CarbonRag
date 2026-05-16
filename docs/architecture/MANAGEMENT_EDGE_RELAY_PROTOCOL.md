# Management Edge Relay Protocol

## 目标

V1.7.4 将管理鉴权从“角色判断”升级为“角色 + 设备 + 签名帧 + Relay + 一次性 ACK + 审计”。

## 设备密钥

前端使用 WebCrypto 生成 `ECDSA P-256` 密钥对。私钥保存在浏览器 IndexedDB，不上传服务器。公钥以 JWK JSON 字符串登记到 `admin_devices.device_public_key`。

## 帧签名

前端对去掉 `signature` 字段后的 canonical JSON 进行 ECDSA-SHA256 签名。服务器解析 JWK 公钥并验签。

签名帧字段：

```json
{
  "frame_type": "SA_HELLO",
  "protocol_version": "1.0",
  "user_id": "...",
  "device_id": "...",
  "timestamp": "2026-05-16T00:00:00.000Z",
  "nonce": "...",
  "requested_action": "ENTER_SUPER_ADMIN_CONSOLE",
  "payload_hash": "...",
  "signature": "base64url..."
}
```

## Nonce

`management_nonces` 持久化已见 nonce。重复 nonce 返回 `409`。过期 nonce 可清理，但在有效窗口内必须全局不可重复。

## Relay

`SA_HELLO` 或 `AD_HELLO` 成功后，后端创建 `edge_relay_sessions` connected 会话。`super_admin` 同时只能有一个 connected Relay。

前端每 30 秒 heartbeat。服务端发现过期 Relay 后，高权限接口必须拒绝。

## ACTION ACK

高风险动作前，前端调用：

`POST /api/v1/management/action/request`

请求体绑定：

- `device_id`
- `action_type`
- `target_type`
- `target_id`
- `payload_hash`

正式业务请求必须带：

- `X-Management-Action-Request-Id`
- `X-Management-Payload-Hash`

后端校验通过后立即写入 `consumed_at`，ACK 不能复用。

## WebSocket

`/api/v1/management/relay/ws` 仅作为 Relay 心跳和后续管理消息通道。连接必须校验：

- Origin。
- cookie session。
- 用户角色。
- active Relay。
- 消息 JSON schema 和大小。

WebSocket 连接成功不代表所有管理操作被授权。

## 受控服务器运维

`/api/v1/management/server-ops/commands/{command_id}/run` 只执行 allowlist 命令，不接受任意命令字符串。执行前要求：

- super_admin。
- active SA Relay。
- one-time ACTION ACK。
- 二次确认 `confirm=true`。
- `ENABLE_WEB_SSH_TERMINAL=true`。

命令输出最多 200KB，超时 30 秒，并写入 `management_audit_logs`。
