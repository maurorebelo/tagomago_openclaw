#!/usr/bin/env bash
#
# Runs INSIDE the OpenClaw container. No SSH, no docker.
# Imports new tweets from TWEETS_JS_PATH to the bridge (NIP-96), then republishes to nostr.tagomago.me.
#
# Expects:
#   - TWEETS_JS_PATH (default: /data/twitter/data/tweets.js)
#   - IMPORT_DIR (default: /data/twitter-archive-to-nostr) — must contain import-tweets.js, package.json
#   - NOSTR_DAMUS_PRIVATE_HEX_KEY (or NOSTR_PRIVATE_KEY) in env
#   - node, npm, nak in PATH
#
# Usage: run from inside the container, e.g.:
#   /data/scripts/cron-twitter-to-nostr-inside-container.sh
# Or from host: docker exec openclaw-b60d-openclaw-1 /data/scripts/cron-twitter-to-nostr-inside-container.sh
#
set -e

TWEETS_JS_PATH="${TWEETS_JS_PATH:-/data/twitter/data/tweets.js}"
IMPORT_DIR="${IMPORT_DIR:-/data/twitter-archive-to-nostr}"
BRIDGE_RELAY="${NOSTR_BRIDGE_RELAY:-wss://bridge.tagomago.me}"
TARGET_RELAY="${NOSTR_TARGET_RELAY:-wss://nostr.tagomago.me}"
PUBKEY="${NOSTR_DAMUS_PUBLIC_HEX_KEY:-f5a49f2a2b378685e01a23f2df72f6eb5d8c4401871280f8fa96d1e666f2109c}"
NOSTR_BRIDGE_LIMIT="${NOSTR_BRIDGE_LIMIT:-50000}"
B="/tmp/cron-bridge-$$.jsonl"

log() { echo "[$(date -Iseconds)] $*"; }

if [ ! -f "$TWEETS_JS_PATH" ]; then
  log "tweets.js not found at $TWEETS_JS_PATH — skip import."
  exit 0
fi

if [ ! -f "$IMPORT_DIR/import-tweets.js" ]; then
  log "Import dir missing or no import-tweets.js at $IMPORT_DIR — skip."
  exit 1
fi

# 1) Import new tweets to bridge (--skip-existing, --upload-media)
log "Importing to $BRIDGE_RELAY (--skip-existing --upload-media)..."
cd "$IMPORT_DIR"
npm install --omit=optional 2>/dev/null || true
export NOSTR_RELAY="$BRIDGE_RELAY"
export NIP96_BASE_URL="${NIP96_BASE_URL:-https://nostr.tagomago.me}"
export NIP96_API_PATH="/api/v2/media"
export SKIP_EXISTING_RELAY="$BRIDGE_RELAY"
node import-tweets.js "$TWEETS_JS_PATH" --skip-existing --upload-media || { log "Import failed."; exit 1; }

# 2) Republish bridge -> nostr.tagomago.me
log "Republishing to $TARGET_RELAY..."
nak req -k 1 -a "$PUBKEY" -l "$NOSTR_BRIDGE_LIMIT" "$BRIDGE_RELAY" 2>/dev/null > "$B" || true
n=$(wc -l < "$B" 2>/dev/null || echo 0)
log "Events on bridge: $n"
if [ "$n" -eq 0 ]; then
  rm -f "$B"
  exit 0
fi
repub=0
while read -r line; do
  [ -n "$line" ] && echo "$line" | nak event "$TARGET_RELAY" 2>/dev/null | grep -q success && repub=$((repub+1)) || true
done < "$B"
rm -f "$B"
log "Republished to $TARGET_RELAY: $repub"
exit 0
