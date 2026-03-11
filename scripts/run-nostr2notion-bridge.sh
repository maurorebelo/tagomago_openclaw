#!/usr/bin/env bash
# Run the Nostr→Notion bridge (skills/nostr2notion).
# Usage: ./scripts/run-nostr2notion-bridge.sh [--vps]
#   No args: run in current env (requires NOTION_API_KEY, NOTION_DATABASE_ID, NOSTR_RELAYS).
#   --vps: run inside the OpenClaw container on the VPS (uses NOSTR_REBROADCAST_SSH, NOSTR_REBROADCAST_CONTAINER).

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SKILL_DIR="$REPO_ROOT/skills/nostr2notion"
SSH_HOST="${NOSTR_REBROADCAST_SSH:-hostinger-vps}"
CONTAINER="${NOSTR_REBROADCAST_CONTAINER:-openclaw-b60d-openclaw-1}"

if [[ "${1:-}" == "--vps" ]]; then
  echo "Running nostr2notion bridge inside container $CONTAINER on $SSH_HOST..."
  ssh "$SSH_HOST" "docker exec $CONTAINER bash -c 'cd /data/.openclaw/workspace/skills/nostr2notion && npm install --no-audit --no-fund 2>/dev/null; node bridge.js'"
else
  if [[ ! -d "$SKILL_DIR" ]]; then
    echo "Skill dir not found: $SKILL_DIR"
    exit 1
  fi
  cd "$SKILL_DIR"
  if [[ ! -d node_modules ]]; then
    npm install --no-audit --no-fund
  fi
  node bridge.js
fi
