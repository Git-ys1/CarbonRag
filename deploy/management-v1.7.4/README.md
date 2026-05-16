# CarbonRag Management V1.7.4 Deployment Bundle

这个目录只放可复制到任意 VPS 的部署脚本和说明，不包含 SSH 凭据。

推荐 VPS 工作目录：

`/opt/carbonrag-management-v1.7.4/`

部署流程：

1. 在授权终端登录服务器。
2. 创建隔离工作目录。
3. 拉取 CarbonRag 仓库 main。
4. 运行 `deploy-management-v1.7.4.sh`。
5. 运行 `health-check.sh`。

脚本不会写入或读取 SSH 密码。凭据由负责人在本地授权终端或 SSH agent 提供。
