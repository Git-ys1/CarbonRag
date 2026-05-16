#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"

echo "[V1.7.4] GET ${BASE_URL}/healthz"
curl -fsS "${BASE_URL}/healthz"
echo

echo "[V1.7.4] GET ${BASE_URL}/api/v1/system/info"
curl -fsS "${BASE_URL}/api/v1/system/info" || true
echo

echo "[V1.7.4] management relay endpoint is protected; unauthenticated status may return 401."
curl -sS -o /dev/null -w "%{http_code}\n" "${BASE_URL}/api/v1/management/relay/status" || true
