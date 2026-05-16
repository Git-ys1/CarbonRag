# V1.7.4 VPS Management Deploy

本说明用于真实 VPS 联调，但不记录服务器 SSH 凭据。

## 原则

- SSH 凭据只由负责人在授权终端或 SSH agent 中提供。
- 不把密码、私钥、连接串写入 Git、日志、任务书或 `.env.example`。
- 部署前先备份代码和数据库。
- 部署后必须检查 health endpoint 和 management relay endpoint。

## 建议步骤

```bash
mkdir -p /opt/carbonrag-management-v1.7.4
cd /opt/carbonrag-management-v1.7.4
git clone <CarbonRag repository url> carbonrag
cd carbonrag
bash deploy/management-v1.7.4/deploy-management-v1.7.4.sh
```

如服务器已有 `/opt/carbonrag`，设置：

```bash
export APP_DIR=/opt/carbonrag
export SERVICE_NAME=carbonrag
bash deploy/management-v1.7.4/deploy-management-v1.7.4.sh
```

当前 CarbonRag VPS 的服务目录是 `/srv/carbonrag/app`，服务名是 `carbonrag`，使用：

```bash
APP_DIR=/srv/carbonrag/app SERVICE_NAME=carbonrag bash deploy/management-v1.7.4/deploy-management-v1.7.4.sh
```

脚本会优先复用仓库根目录 `.venv/bin/python`，其次再尝试 `backend/.conda`，避免服务器部署时误跑系统 Python。备份会排除 `.git`、`.venv`、`node_modules` 和 `backend/.conda`，避免把虚拟环境和前端依赖包复制进备份目录。

如果目标服务器只用于管理中继联调，且现有 `.venv` 已能 import `app.main`，可以跳过全量依赖安装和前端构建，避免拉取 RAG/模型相关大依赖：

```bash
APP_DIR=/srv/carbonrag/app \
SERVICE_NAME=carbonrag \
SKIP_BACKEND_DEPENDENCIES=true \
SKIP_FRONTEND_BUILD=true \
bash deploy/management-v1.7.4/deploy-management-v1.7.4.sh
```

## 验收

- `/healthz` 可访问。
- `/api/v1/system/info` 可访问或明确返回受保护状态。
- `/api/v1/management/relay/status` 未登录时应返回受保护状态。
- SuperAdminPage 能登记设备并建立 SA Relay。
