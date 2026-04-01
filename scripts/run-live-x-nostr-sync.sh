#!/usr/bin/env bash
#
# Runs INSIDE the OpenClaw container. Fetches X timeline via xurl, publishes new tweets to the bridge, then republishes bridge → target relay.
# Schedule 2x/day (every 12h) for near real-time sync. Does NOT use tweets.js.
#
# Expects: HOME=/data, /data/.xurl (for xurl), NOSTR_DAMUS_* in env, node/nak in PATH,
#          /data/scripts/sync-x-timeline-to-nostr/ with sync.js and package.json (or set SYNC_X_NOSTR_DIR).
#
# Usage: /data/scripts/run-live-x-nostr-sync.sh
# From host: docker exec openclaw-b60d-openclaw-1 /data/scripts/run-live-x-nostr-sync.sh
#
set -e

# Use xurl read-only wrapper (audit log + block post) when available
export PATH="/data/bin:${PATH:-/usr/local/bin:/usr/bin:/bin}"

SYNC_DIR="${SYNC_X_NOSTR_DIR:-/data/scripts/sync-x-timeline-to-nostr}"
BRIDGE_RELAY="${NOSTR_BRIDGE_RELAY:-wss://bridge.tagomago.me}"
TARGET_RELAY="${NOSTR_TARGET_RELAY:-wss://nostr.tagomago.me}"
PUBKEY="${NOSTR_DAMUS_PUBLIC_HEX_KEY:-}"

log() { echo "[$(date -Iseconds)] $*"; }

if [ ! -f "$SYNC_DIR/sync.js" ]; then
  log "Live sync script not found at $SYNC_DIR/sync.js — skip."
  exit 1
fi

cd "$SYNC_DIR"
npm install --omit=optional 2>/dev/null || true

export HOME="${HOME:-/data}"
export NOSTR_BRIDGE_RELAY="$BRIDGE_RELAY"

# 1) Fetch X timeline and publish new tweets to bridge
log "Live sync: xurl timeline → bridge $BRIDGE_RELAY..."
node sync.js || { log "Live sync failed."; exit 1; }

# 2) Republish bridge → target relay (so events appear on nostr.tagomago.me)
if [ -z "$PUBKEY" ]; then
  log "NOSTR_DAMUS_PUBLIC_HEX_KEY not set — skip republish."
  exit 0
fi

B="/tmp/live-sync-bridge-$$.jsonl"
log "Republishing bridge → $TARGET_RELAY..."
/data/bin/nak-real req -k 1 -a "$PUBKEY" -l 50000 "$BRIDGE_RELAY" 2>/dev/null > "$B" || true
n=$(wc -l < "$B" 2>/dev/null || echo 0)
repub=0
while read -r line; do
  [ -n "$line" ] && echo "$line" | /data/bin/nak-real event "$TARGET_RELAY" 2>/dev/null | grep -q success && repub=$((repub+1)) || true
done < "$B"
rm -f "$B"
log "Republished to $TARGET_RELAY: $repub"
exit 0
