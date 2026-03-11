#!/usr/bin/env bash
# Pull from VPS /data into local data/ (and optionally other non-git dirs).
# Run from repo root on the Mac. So you have a local mirror of what's on the VPS
# that isn't in GitHub, and can edit locally then push with sync-data-to-vps.sh.
#
# Requires: SSH host (default hostinger-vps) and VPS host path to workspace.
# Set once: VPS_DATA_HOST=hostinger-vps, VPS_DATA_PATH=/docker/openclaw-b60d/data

set -e
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

SSH_HOST="${VPS_DATA_HOST:-hostinger-vps}"
# Path on the VPS *host* where the workspace is mounted (same as /data in container)
VPS_ROOT="${VPS_DATA_PATH:-/docker/openclaw-b60d/data}"

EXCLUDE_FILE="$REPO_ROOT/scripts/rsync-exclude.txt"
if [[ ! -f "$EXCLUDE_FILE" ]]; then EXCLUDE_FILE=/dev/null; fi

echo "Pull from $SSH_HOST:$VPS_ROOT/data/ into local data/"
rsync -avz --exclude-from="$EXCLUDE_FILE" "$SSH_HOST:$VPS_ROOT/data/" "$REPO_ROOT/data/"

echo "Done. Local data/ is now in sync with VPS (pull)."
