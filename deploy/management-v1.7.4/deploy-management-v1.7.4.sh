#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/carbonrag}"
BACKUP_DIR="${BACKUP_DIR:-/opt/carbonrag-backups/$(date +%Y%m%d-%H%M%S)}"
SERVICE_NAME="${SERVICE_NAME:-carbonrag}"

echo "[V1.7.4] backing up ${APP_DIR} to ${BACKUP_DIR}"
mkdir -p "${BACKUP_DIR}"
if [ -d "${APP_DIR}" ]; then
  rsync -a \
    --exclude ".git" \
    --exclude ".venv" \
    --exclude "node_modules" \
    --exclude "backend/.conda" \
    "${APP_DIR}/" "${BACKUP_DIR}/app/"
fi

cd "${APP_DIR}"
echo "[V1.7.4] fetching main"
git fetch origin main
git checkout main
git pull --ff-only origin main

echo "[V1.7.4] installing backend dependencies"
if [ -x ".venv/bin/python" ]; then
  .venv/bin/python -m pip install -r backend/requirements.txt
elif [ -x "backend/.conda/bin/python" ]; then
  backend/.conda/bin/python -m pip install -r backend/requirements.txt
elif [ -x "backend/.conda/Scripts/python.exe" ]; then
  backend/.conda/Scripts/python.exe -m pip install -r backend/requirements.txt
else
  python -m pip install -r backend/requirements.txt
fi

echo "[V1.7.4] installing frontend dependencies and building"
cd frontend
npm ci
npm run build
cd ..

echo "[V1.7.4] restarting ${SERVICE_NAME}"
systemctl restart "${SERVICE_NAME}"

echo "[V1.7.4] health check"
bash deploy/management-v1.7.4/health-check.sh
