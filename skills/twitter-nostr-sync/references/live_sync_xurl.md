# Live X → Nostr sync (xurl timeline, 2x/day)

Syncs **new tweets from the X timeline** to Nostr without using tweets.js. Uses `xurl timeline` (auth from `/data/.xurl`) and publishes to the bridge, then republishes to the target relay.

## How it works

1. **sync.js** (Node): runs `xurl timeline -n 100` with `HOME=/data`, parses JSON, loads `/data/.twitter-nostr-synced-ids` (set of already-synced tweet IDs). For each tweet not in the set, creates a Nostr kind-1 event (content = tweet text, tag `r` = tweet URL), signs with `NOSTR_DAMUS_PRIVATE_HEX_KEY`, publishes to the bridge. Appends new IDs to the file.
2. **run-live-x-nostr-sync.sh**: runs sync.js, then republishes bridge → target relay (same as batch script) so events appear on nostr.tagomago.me.
3. **run-live-x-nostr-sync-loop.sh**: loops every 12h and runs the script above.

## Requirements

- **Container:** `/data/.xurl` (xurl auth), `NOSTR_DAMUS_PRIVATE_HEX_KEY`, `NOSTR_DAMUS_PUBLIC_HEX_KEY`, `node`, `nak`, `xurl` in PATH.
- **In workspace:** `scripts/sync-x-timeline-to-nostr/` (sync.js + package.json) and `scripts/run-live-x-nostr-sync.sh`, `scripts/run-live-x-nostr-sync-loop.sh` (e.g. from repo at `/data` after git pull). Make the .sh executable: `chmod +x /data/scripts/run-live-x-nostr-sync.sh /data/scripts/run-live-x-nostr-sync-loop.sh`.

## Run once (manual)

```bash
docker exec openclaw-b60d-openclaw-1 /data/scripts/run-live-x-nostr-sync.sh
```

## Start 2x/day loop

```bash
docker exec -d openclaw-b60d-openclaw-1 /data/scripts/run-live-x-nostr-sync-loop.sh
```

Optional: `LIVE_X_NOSTR_INTERVAL_SEC=43200` (default 12h).

## Env (optional)

- `NOSTR_BRIDGE_RELAY` — default wss://bridge.tagomago.me
- `NOSTR_TARGET_RELAY` — default wss://nostr.tagomago.me
- `TWITTER_NOSTR_SYNCED_IDS` — path for synced tweet IDs file (default `/data/.twitter-nostr-synced-ids`)
- `XURL_TIMELINE_LIMIT` — number of tweets to fetch (default 100)

## Batch vs live

| | Batch | Live |
|---|--------|------|
| **Source** | tweets.js (export file) | xurl timeline (X API) |
| **When** | On demand (or 12h loop over same file) | 2x/day (new tweets since last run) |
| **Scripts** | cron-twitter-to-nostr-inside-container.sh, run-twitter-sync-loop.sh | run-live-x-nostr-sync.sh, run-live-x-nostr-sync-loop.sh |
| **Use case** | One-off or periodic import of archive | Near real-time sync without re-exporting |

You can run both: batch for historical archive, live for new tweets.
