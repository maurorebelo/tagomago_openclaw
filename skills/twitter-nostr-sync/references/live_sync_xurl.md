# Live X → Nostr sync (xurl user tweets, 2x/day)

Syncs **your tweets only** via X API `GET /2/users/{id}/tweets` (not the home timeline). Auth from `/data/.xurl`. Publishes to the bridge, then republishes to the target relay.

## How it works

1. **sync.js** (Node): `xurl whoami` then `xurl '/2/users/{id}/tweets?max_results=100&tweet.fields=created_at,author_id'` (paginates if `XURL_USER_TWEETS_LIMIT` > 100), loads `/data/.twitter-nostr-synced-ids`. For each tweet not in the set, creates a Nostr kind-1 event (content = tweet text, tag `r` = tweet URL), signs with `NOSTR_DAMUS_PRIVATE_HEX_KEY`, publishes to the bridge. Appends new IDs to the file.
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

## Where events are published

Each new tweet is published to **all** of these (so others see them on public relays and your relays keep your copy):

- Your relays: `NOSTR_BRIDGE_RELAY` (bridge.tagomago.me), `NOSTR_TARGET_RELAY` (nostr.tagomago.me)
- Public relays: `NOSTR_PUBLIC_RELAYS` (comma-separated). Default: `wss://relay.damus.io,wss://nostr.land,wss://nos.lol,wss://relay.nostr.band`

Override `NOSTR_PUBLIC_RELAYS` to add or remove public relays.

## Env (optional)

- `NOSTR_BRIDGE_RELAY` — default wss://bridge.tagomago.me
- `NOSTR_TARGET_RELAY` — default wss://nostr.tagomago.me
- `NOSTR_PUBLIC_RELAYS` — comma-separated public relays (see above)
- `TWITTER_NOSTR_SYNCED_IDS` — path for synced tweet IDs file (default `/data/.twitter-nostr-synced-ids`)
- `XURL_USER_TWEETS_LIMIT` — max tweets to fetch (default 100; paginates in steps of 100). Legacy: `XURL_TIMELINE_LIMIT` still works.

## Batch vs live

| | Batch | Live |
|---|--------|------|
| **Source** | tweets.js (export file) | xurl `GET /2/users/{id}/tweets` (X API) |
| **When** | On demand (or 12h loop over same file) | 2x/day (new tweets since last run) |
| **Scripts** | cron-twitter-to-nostr-inside-container.sh, run-twitter-sync-loop.sh | run-live-x-nostr-sync.sh, run-live-x-nostr-sync-loop.sh |
| **Use case** | One-off or periodic import of archive | Near real-time sync without re-exporting |

You can run both: batch for historical archive, live for new tweets.

## Historical posts (tweets.js import) on public relays

Posts imported from tweets.js live only on your relays (bridge + nostr.tagomago.me) until you republish them to public relays. To push them so others see them on damus.io, nostr.land, etc.:

```bash
docker exec openclaw-b60d-openclaw-1 /data/scripts/republish-to-public-relays.sh
```

Uses `NOSTR_DAMUS_PUBLIC_HEX_KEY` and publishes each event from the bridge to `NOSTR_PUBLIC_RELAYS` (default: relay.damus.io, nostr.land, nos.lol, relay.nostr.band). Run once; can take a while if you have many events.
