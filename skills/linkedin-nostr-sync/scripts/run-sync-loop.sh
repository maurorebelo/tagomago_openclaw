#!/usr/bin/env bash
# Run LinkedIn → Nostr sync every 12 hours.
# Start in background: docker exec -d <container> /data/skills/linkedin-nostr-sync/scripts/run-sync-loop.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INTERVAL="${LINKEDIN_NOSTR_INTERVAL_SEC:-43200}"  # default: 12h

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] LinkedIn sync loop starting (interval: ${INTERVAL}s)"

while true; do
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Running sync..."
  node "$SCRIPT_DIR/sync.js" 2>&1 || echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Sync failed (non-fatal)"
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Next run in ${INTERVAL}s"
  sleep "$INTERVAL"
done
