#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"

echo "[V1.7.4] GET ${BASE_URL}/healthz"
for attempt in $(seq 1 30); do
  if curl -fsS "${BASE_URL}/healthz"; then
    break
  fi
  if [ "${attempt}" = "30" ]; then
    echo "[V1.7.4] healthz did not become ready after ${attempt} attempts" >&2
    exit 1
  fi
  sleep 2
done
echo

echo "[V1.7.4] GET ${BASE_URL}/api/v1/system/info"
curl -fsS "${BASE_URL}/api/v1/system/info" || true
echo

echo "[V1.7.4] management relay endpoint is protected; unauthenticated status may return 401."
curl -sS -o /dev/null -w "%{http_code}\n" "${BASE_URL}/api/v1/management/relay/status" || true
