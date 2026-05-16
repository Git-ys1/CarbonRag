#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/carbonrag}"
cd "${APP_DIR}"
git fetch origin main
git checkout main
git pull --ff-only origin main
systemctl restart "${SERVICE_NAME:-carbonrag}"
