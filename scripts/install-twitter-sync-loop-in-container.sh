#!/usr/bin/env bash
#
# Run from host (Mac or VPS). Copies sync scripts and twitter-archive-to-nostr into the
# OpenClaw container and starts the 12h Twitter→Nostr sync loop inside the container.
#
# Prereq: tweets.js must be available inside the container at /data/twitter/data/tweets.js
# (copy or mount; see docs/CRON_INSIDE_OPENCLAW.md).
#
# Usage: ./scripts/install-twitter-sync-loop-in-container.sh
#
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
IMPORT_DIR="$SCRIPT_DIR/twitter-archive-to-nostr"
SSH_HOST="${NOSTR_REBROADCAST_SSH:-hostinger-vps}"
CONTAINER="${NOSTR_REBROADCAST_CONTAINER:-openclaw-b60d-openclaw-1}"

if [ ! -d "$IMPORT_DIR" ] || [ ! -f "$IMPORT_DIR/import-tweets.js" ]; then
  echo "Error: $IMPORT_DIR with import-tweets.js not found."
  exit 1
fi

REMOTE_TMP="/tmp/twitter-sync-$$"
EXCLUDEFILE=$(mktemp) && echo 'node_modules' > "$EXCLUDEFILE" && trap "rm -f $EXCLUDEFILE" EXIT

echo "Copying twitter-archive-to-nostr into container..."
tar -c -X "$EXCLUDEFILE" -C "$(dirname "$IMPORT_DIR")" "$(basename "$IMPORT_DIR")" -f - | ssh "$SSH_HOST" "mkdir -p $REMOTE_TMP && cat > $REMOTE_TMP/twitter-archive-to-nostr.tar"
ssh "$SSH_HOST" "docker cp $REMOTE_TMP/twitter-archive-to-nostr.tar $CONTAINER:/tmp/ && docker exec $CONTAINER bash -c 'mkdir -p /data && tar xf /tmp/twitter-archive-to-nostr.tar -C /data && rm /tmp/twitter-archive-to-nostr.tar'"

echo "Copying scripts into container..."
scp -q "$SCRIPT_DIR/cron-twitter-to-nostr-inside-container.sh" "$SCRIPT_DIR/run-twitter-sync-loop.sh" "$SSH_HOST:$REMOTE_TMP/"
ssh "$SSH_HOST" "docker exec $CONTAINER mkdir -p /data/scripts && docker cp $REMOTE_TMP/cron-twitter-to-nostr-inside-container.sh $REMOTE_TMP/run-twitter-sync-loop.sh $CONTAINER:/data/scripts/ && docker exec $CONTAINER chmod +x /data/scripts/cron-twitter-to-nostr-inside-container.sh /data/scripts/run-twitter-sync-loop.sh && rm -rf $REMOTE_TMP"

# Optional: if tweets.js exists on host at common path, copy into container
TWEETS_HOST="${TWEETS_ON_VPS:-/docker/openclaw-b60d/data/data/tweets.js}"
if ssh "$SSH_HOST" "[ -f '$TWEETS_HOST' ]" 2>/dev/null; then
  echo "Copying tweets.js from host into container..."
  ssh "$SSH_HOST" "docker exec $CONTAINER mkdir -p /data/twitter/data && docker cp $TWEETS_HOST $CONTAINER:/data/twitter/data/tweets.js"
fi

echo "Starting sync loop in container (12h interval)..."
ssh "$SSH_HOST" "docker exec -d $CONTAINER /data/scripts/run-twitter-sync-loop.sh"

echo "Done. Sync runs inside the container every 12h. See docs/CRON_INSIDE_OPENCLAW.md."
echo "If tweets.js was not copied, ensure /data/twitter/data/tweets.js exists in the container (set TWEETS_ON_VPS or copy manually)."
