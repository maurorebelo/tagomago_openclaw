#!/usr/bin/env bash
#
# Runs INSIDE the OpenClaw container. Loops every 12 hours and runs the live X→Nostr sync (xurl timeline → bridge → target).
# Start in background: docker exec -d openclaw-b60d-openclaw-1 /data/scripts/run-live-x-nostr-sync-loop.sh
#
LIVE_SYNC_SCRIPT="${LIVE_X_NOSTR_SYNC_SCRIPT:-/data/scripts/run-live-x-nostr-sync.sh}"
INTERVAL_SEC="${LIVE_X_NOSTR_INTERVAL_SEC:-43200}"

echo "[$(date -Iseconds)] Live X→Nostr sync loop started (interval ${INTERVAL_SEC}s = 12h). Script: $LIVE_SYNC_SCRIPT"
while true; do
  sleep "$INTERVAL_SEC"
  [ -x "$LIVE_SYNC_SCRIPT" ] && "$LIVE_SYNC_SCRIPT" || echo "[$(date -Iseconds)] Live sync script not executable or missing: $LIVE_SYNC_SCRIPT"
done
