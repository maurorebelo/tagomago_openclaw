---
name: twitter-nostr-sync
description: "Sync X/Twitter to Nostr (bridge.tagomago.me and nostr.tagomago.me). Two modes: (1) Batch import from tweets.js on demand; (2) Live sync from X timeline via xurl, 2x/day. Use when the user asks to sync tweets to Nostr, import archive, run live sync, schedule sync, or dedupe bridge events."
---

# Twitter → Nostr sync

This skill defines two ways to sync the user's X/Twitter to Nostr (bridge.tagomago.me and nostr.tagomago.me):

1. **Batch sync (on demand)** — Imports from a **tweets.js** file (Twitter export). Run when the user requests it or after uploading a new archive. Uses NIP-96 for media. Does not fetch from X API.
2. **Live sync (scheduled)** — Fetches the user's **X timeline via xurl** and publishes new tweets to the bridge, then to the target relay. Run **2x per day** (e.g. every 12h) so recent tweets appear on Nostr without re-exporting tweets.js.

**If OpenClaw does not list this skill:** Install it on the VPS so the Gateway sees it (same workspace dir as nostr-nak). Run `./skills/twitter-nostr-sync/scripts/install-on-vps.sh`. Optional: `OPENCLAW_WORKSPACE_HOST=/path/on/vps` if workspace is not `/docker/openclaw-b60d/data`. Then Refresh the Dashboard.

## When to use

- User asks to "sync my tweets to Nostr", "import Twitter archive", "run the Twitter sync", "set up live sync", or "run sync 2x per day".
- User asks to run a one-off batch import (tweets.js) or to start the live sync loop.

## Prerequisites

- **Batch:** Twitter archive `data/tweets.js` from a Twitter export (for batch import).
- **Live:** xurl with auth in `/data/.xurl` (see TOOLS.md); container has `xurl` in PATH.
- **Nostr keys:** Container or environment has `NOSTR_DAMUS_PRIVATE_HEX_KEY` (or `NOSTR_PRIVATE_KEY`) and `NOSTR_DAMUS_PUBLIC_HEX_KEY` (for republish).
- **VPS:** SSH access and container name from TOOLS.md or env (`NOSTR_REBROADCAST_SSH`, `NOSTR_REBROADCAST_CONTAINER`).

## Commands and scripts

All of these run **on the VPS** (or via SSH). Paths relative to workspace root. SSH host and container from TOOLS.md.

---

### Batch sync (on demand — uses tweets.js)

### 1. One-off import (tweets.js not yet on VPS)

If the archive or `tweets.js` must be sent to the VPS first, run (script copies file to VPS and runs import in container):

```bash
./scripts/run-import-on-vps.sh /path/to/data/tweets.js --upload-media --skip-existing
```

- `--upload-media`: upload images/videos to NIP-96 (nostr.tagomago.me).
- `--skip-existing`: only import tweets whose `created_at` is not already on the bridge (incremental).

### 2. One-off import (tweets.js already on VPS)

User uploaded the archive (or zip) to the VPS. Use the path **on the VPS**:

```bash
TWEETS_ON_VPS=/docker/openclaw-b60d/data/data/tweets.js ./scripts/run-import-on-vps.sh --upload-media --skip-existing
```

Adjust `TWEETS_ON_VPS` to the actual path on the VPS (see TOOLS.md).

### 3. Unzip a new Twitter zip on the VPS (if unzip not installed, use Python)

```bash
ssh $SSH_HOST "python3 -c \"
import zipfile
z = zipfile.ZipFile('/docker/openclaw-b60d/data/twitter-2026-03-08.zip')
z.extract('data/tweets.js', '/docker/openclaw-b60d/data')
\""
```

Then run import with `TWEETS_ON_VPS=/docker/openclaw-b60d/data/data/tweets.js` as above.

### 4. Republic bridge → nostr.tagomago.me (after import)

Copy all events from the bridge to the nostr relay (so they appear on nostr.tagomago.me):

```bash
./scripts/bridge-to-nostr-relay.sh
```

### 5. Dedupe on the bridge (kind 5 for duplicate events per created_at)

If there are duplicate events (same tweet imported twice), mark the non–NIP-96 copies as deleted (NIP-09) so clients hide them:

```bash
./scripts/run-dedupe-keep-nip96-on-vps.sh
```

### 6. Install batch sync loop inside the container (12h — still uses tweets.js)

Copies `twitter-archive-to-nostr` and batch sync scripts into the container and starts a 12-hour loop (batch only; source remains tweets.js).

```bash
./scripts/install-twitter-sync-loop-in-container.sh
```

Optional: `TWEETS_ON_VPS=/docker/openclaw-b60d/data/data/tweets.js` so the script copies tweets.js into the container.

### 7. Run batch sync once inside the container (manual)

```bash
ssh $SSH_HOST "docker exec $CONTAINER /data/scripts/cron-twitter-to-nostr-inside-container.sh"
```

---

### Live sync (xurl timeline → Nostr, 2x/day)

Does **not** use tweets.js. Fetches the user's X timeline via `xurl timeline` and publishes new tweets to the bridge, then republishes to the target relay. Schedule every 12h for near real-time sync.

### 8. Run live sync once (manual)

Inside the container: ensure `scripts/sync-x-timeline-to-nostr/` is present (e.g. under `/data/scripts/`), then:

```bash
docker exec $CONTAINER /data/scripts/run-live-x-nostr-sync.sh
```

Requires: `/data/.xurl` (xurl auth), `NOSTR_DAMUS_PRIVATE_HEX_KEY`, `NOSTR_DAMUS_PUBLIC_HEX_KEY`, `node`, `nak`, `xurl` in PATH.

### 9. Start live sync loop (2x/day)

Runs the live sync script every 12 hours. Start in background:

```bash
docker exec -d $CONTAINER /data/scripts/run-live-x-nostr-sync-loop.sh
```

Optional env: `LIVE_X_NOSTR_INTERVAL_SEC=43200` (default 12h). New tweets are tracked in `/data/.twitter-nostr-synced-ids` so each run only publishes tweets not yet synced.

## Safety

- **Live sync:** `xurl timeline` returns the *home* timeline (user + followed accounts). The sync must publish **only** tweets where `author_id === xurl whoami.data.id`. `sync.js` enforces this; do not remove the filter.
- **Republish to public relays:** Only publish events where `event.pubkey === NOSTR_DAMUS_PUBLIC_HEX_KEY`. `republish-to-public-relays.sh` filters with `jq` before publishing; do not bypass.
- Events already sent to public relays cannot be unpublished.

## File layout in the repo

| Path | Purpose |
|------|--------|
| `skills/twitter-nostr-sync/scripts/install-on-vps.sh` | Install skill on VPS so it appears in Gateway (WORKSPACE SKILLS). |
| **Batch (on demand)** | |
| `scripts/run-import-on-vps.sh` | Import tweets.js to bridge (NIP-96, --skip-existing). |
| `scripts/cron-twitter-to-nostr-inside-container.sh` | One-shot batch sync (reads tweets.js, imports to bridge, republishes). |
| `scripts/run-twitter-sync-loop.sh` | 12h loop that runs batch sync (still tweets.js). |
| `scripts/install-twitter-sync-loop-in-container.sh` | Install batch sync loop in container. |
| `scripts/twitter-archive-to-nostr/` | Node project: `import-tweets.js`, `dedupe-keep-nip96.js`, `package.json`. |
| **Live (xurl, 2x/day)** | |
| `scripts/sync-x-timeline-to-nostr/sync.js` | Fetches xurl timeline, publishes new tweets to bridge (Node + nostr-tools). |
| `scripts/run-live-x-nostr-sync.sh` | One-shot live sync (xurl → bridge → republish to target). |
| `scripts/run-live-x-nostr-sync-loop.sh` | 12h loop that runs live sync. |
| **Shared** | |
| `scripts/bridge-to-nostr-relay.sh` | Republish bridge → nostr.tagomago.me. |
| `scripts/republish-bridge-to-nostr.sh` | One-shot: bridge → nostr.tagomago.me. |
| `scripts/republish-to-public-relays.sh` | One-shot: bridge (or target) → public relays (damus.io, nostr.land, etc.). Use for historical tweets.js imports. |
| `scripts/run-dedupe-keep-nip96-on-vps.sh` | Dedupe duplicates on bridge (kind 5). |
| `references/cron_inside_container.md` | Batch cron inside container: mounts, env. |
| `SYNC.md` | Repo sync (canonical = VPS). |

## Environment variables (optional)

- `NOSTR_REBROADCAST_SSH` — SSH host (e.g. hostinger-vps).
- `NOSTR_REBROADCAST_CONTAINER` — Container name (e.g. openclaw-b60d-openclaw-1).
- `NOSTR_RELAY` / `NOSTR_BRIDGE_RELAY` — Bridge URL (default wss://bridge.tagomago.me).
- `TWEETS_ON_VPS` — Path on VPS to `tweets.js` when using run-import or install script.

Store user-specific values (SSH host, container, paths) in **TOOLS.md**; do not hardcode secrets in scripts.
