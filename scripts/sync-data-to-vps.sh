#!/usr/bin/env bash
# Push local data/ to VPS /data/data/. Run from repo root on the Mac after
# you've made local changes you want on the VPS.
#
# Requires: VPS_DATA_HOST, VPS_DATA_PATH (see sync-data-from-vps.sh).

set -e
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

SSH_HOST="${VPS_DATA_HOST:-hostinger-vps}"
VPS_ROOT="${VPS_DATA_PATH:-/docker/openclaw-b60d/data}"

EXCLUDE_FILE="$REPO_ROOT/scripts/rsync-exclude.txt"
if [[ ! -f "$EXCLUDE_FILE" ]]; then EXCLUDE_FILE=/dev/null; fi

if [[ ! -d "$REPO_ROOT/data" ]]; then
  echo "No local data/ folder. Create it or run sync-data-from-vps.sh first."
  exit 1
fi

echo "Push local data/ to $SSH_HOST:$VPS_ROOT/data/"
rsync -avz --exclude-from="$EXCLUDE_FILE" "$REPO_ROOT/data/" "$SSH_HOST:$VPS_ROOT/data/"

echo "Done. VPS /data/data/ is now in sync with local (push)."
