# V1.7.4 Management Policy V1.2

## 角色边界

`user` 是普通用户，只使用问答、文件、知识库、碳计算器、碳因子库、报告等普通业务功能。普通用户不参与 Management Relay，不绑定管理设备，不访问管理员后台。

`admin` 是管理员，可以进入普通管理后台，但必须由 `super_admin` 创建或恢复授权。管理员需要绑定已审批设备。管理员可以管理用户、爬虫、知识库、候选文档等，高风险修改必须申请一次性 `ACTION_ACK`。

`super_admin` 是超级管理员，全系统唯一，只能绑定一台 active 设备，只允许一个 active Relay 会话。超级管理员可以创建、禁用、删除 admin，审批旧 admin 恢复权限，查看审计日志，并在受控条件下使用服务器运维面板。

## 普通业务与管理业务隔离

普通业务页面不得调用：

- `/v1/management/*`
- `/v1/admin/*`
- `/super-admin`
- `/management/relay/ws`
- `/management/ssh-terminal/*`

管理后台必须调用 Management Relay。超级管理员后台必须调用 `SA_HELLO` 帧。普通用户看不到管理入口，admin 看不到 super-admin 入口。

## 设备绑定

设备绑定不使用 MAC 作为凭据。MAC 只能做提示展示。

真正凭据是设备密钥对：

- 本机保存私钥。
- 服务器保存公钥。
- 每次管理握手由私钥签名。
- 服务器使用登记公钥验签。

V1.7.4 使用 WebCrypto `ECDSA P-256 + SHA-256` 生成设备签名密钥。私钥保存在浏览器 IndexedDB 中，不上传服务器。

## SA/AD 帧

`SA_HELLO` 用于 super_admin，`AD_HELLO` 用于 admin。两者都必须包含：

- `frame_type`
- `protocol_version`
- `user_id`
- `device_id`
- `timestamp`
- `nonce`
- `requested_action`
- `payload_hash`
- `signature`

服务器必须校验：

- 用户角色正确。
- 设备已审批。
- 签名有效。
- timestamp 在允许窗口内。
- nonce 未使用。
- requested_action 在权限范围内。
- payload_hash 与本次动作一致。

## Relay 与 ACK

Relay 是在线高权限通道，不是万能通行证。

- 进入管理后台需要一次 ENTER ACK。
- 执行高风险动作需要一次 ACTION ACK。
- ACTION ACK 必须绑定 `action_type + target_type + target_id + payload_hash`。
- ACTION ACK 必须一次性使用，过期或已消费即失效。

## WebSocket 规则

生产环境只能使用 WSS。握手必须校验 Origin，连接后仍要做消息级授权。不能认为 WebSocket 连接成功就等于所有操作都被授权。

## 受控服务器运维

V1.7.4 不提供浏览器裸 SSH 终端，只提供受控服务器运维面板：

- 查看服务状态。
- 查看最近日志。
- 运行健康检查。
- 查看 Git HEAD。
- 运行受控更新脚本。
- 重启 carbonrag 服务。

危险命令默认禁止。每条命令必须写入审计日志。SSH 凭据不得返回前端，不得写入 Git、日志、任务书或 `.env.example`。
