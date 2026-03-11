#!/usr/bin/env bash
# Install this skill on the VPS host so it appears in the Gateway Dashboard (WORKSPACE SKILLS).
# Run from workspace; script SSHs to the VPS and deploys the skill to the workspace skills dir.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$SKILL_ROOT/.." && pwd)"
SSH_HOST="${NOSTR_REBROADCAST_SSH:-hostinger-vps}"
WORKSPACE_HOST="${OPENCLAW_WORKSPACE_HOST:-/docker/openclaw-b60d/data}"
SKILLS_HOST="${WORKSPACE_HOST}/skills"

echo "Installing twitter-nostr-sync on VPS $SSH_HOST at $SKILLS_HOST/twitter-nostr-sync"
cd "$REPO_ROOT"
LOCAL_TAR="/tmp/twitter-nostr-sync-deploy.tar"
REMOTE_TAR="/tmp/twitter-nostr-sync-deploy.tar"
tar -c -C "$SKILL_ROOT" . -f "$LOCAL_TAR"
scp -q "$LOCAL_TAR" "$SSH_HOST:$REMOTE_TAR"
ssh "$SSH_HOST" "mkdir -p $SKILLS_HOST/twitter-nostr-sync && cd $SKILLS_HOST/twitter-nostr-sync && tar xf $REMOTE_TAR 2>/dev/null; rm -f $REMOTE_TAR"
rm -f "$LOCAL_TAR"
echo "Done. Refresh the Gateway Dashboard."
