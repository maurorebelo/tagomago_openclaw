#!/usr/bin/env bash
#
# Runs INSIDE the OpenClaw container. Loops forever: every 12 hours runs the Twitter→Nostr sync.
# Run in background so the main process can keep running, e.g.:
#   nohup /data/scripts/run-twitter-sync-loop.sh >> /data/log/twitter-sync.log 2>&1 &
#
# Or from host (start loop in background):
#   docker exec -d openclaw-b60d-openclaw-1 /data/scripts/run-twitter-sync-loop.sh
#
# Requires: cron-twitter-to-nostr-inside-container.sh and its dependencies (see CRON_INSIDE_OPENCLAW.md).
#
SYNC_SCRIPT="${TWITTER_SYNC_SCRIPT:-/data/scripts/cron-twitter-to-nostr-inside-container.sh}"
INTERVAL_SEC="${TWITTER_SYNC_INTERVAL_SEC:-43200}"

echo "[$(date -Iseconds)] Twitter→Nostr sync loop started (interval ${INTERVAL_SEC}s = 12h). Script: $SYNC_SCRIPT"
while true; do
  sleep "$INTERVAL_SEC"
  [ -x "$SYNC_SCRIPT" ] && "$SYNC_SCRIPT" || echo "[$(date -Iseconds)] Sync script not executable or missing: $SYNC_SCRIPT"
done
