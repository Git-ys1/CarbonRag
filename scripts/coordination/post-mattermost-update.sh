#!/usr/bin/env bash
set -euo pipefail

TYPE="${1:?TYPE is required}"
VERSION="${2:?VERSION is required}"
CHANGE_ID="${3:?CHANGE_ID is required}"
MESSAGE="${4:?MESSAGE is required}"
MODULE="${MODULE:-M8}"
RISK="${RISK:-low}"
SEAT="${SEAT:-#1}"
MATTERMOST_URL="${MATTERMOST_URL:?MATTERMOST_URL is required}"
MATTERMOST_TOKEN="${MATTERMOST_TOKEN:?MATTERMOST_TOKEN is required}"
MATTERMOST_TEAM="${MATTERMOST_TEAM:-carbonrag}"
MATTERMOST_CHANNEL="${MATTERMOST_CHANNEL:-carbonrag-control}"

SERVER="${MATTERMOST_URL%/}"
TEAM_ID="$(curl -fsS -H "Authorization: Bearer $MATTERMOST_TOKEN" "$SERVER/api/v4/teams/name/$MATTERMOST_TEAM" | python -c "import json,sys; print(json.load(sys.stdin)['id'])")"
CHANNEL_ID="$(curl -fsS -H "Authorization: Bearer $MATTERMOST_TOKEN" "$SERVER/api/v4/teams/$TEAM_ID/channels/name/$MATTERMOST_CHANNEL" | python -c "import json,sys; print(json.load(sys.stdin)['id'])")"
PREFIX="[$SEAT][$TYPE][$VERSION][change-id=$CHANGE_ID][module=$MODULE][risk=$RISK]"

python - "$CHANNEL_ID" "$PREFIX" "$MESSAGE" <<'PY' | curl -fsS \
  -H "Authorization: Bearer $MATTERMOST_TOKEN" \
  -H "Content-Type: application/json" \
  -d @- \
  "$SERVER/api/v4/posts"
import json
import sys

channel_id, prefix, message = sys.argv[1:4]
print(json.dumps({"channel_id": channel_id, "message": f"{prefix}\n{message}"}))
PY

echo

