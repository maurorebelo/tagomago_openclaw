---
name: twitter-nostr-sync
description: "Sync Twitter archive to Nostr (bridge.tagomago.me and nostr.tagomago.me) with NIP-96 media. Use when the user asks to sync tweets to Nostr, import Twitter archive, run the Twitter→Nostr sync, schedule the sync (cron/loop), run a one-off import after uploading a new archive zip to the VPS, republish bridge to nostr relay, or dedupe duplicate events on the bridge (kind 5)."
---

# Twitter → Nostr sync

This skill defines how to sync the user's Twitter archive to their Nostr relays (bridge.tagomago.me and nostr.tagomago.me) with media uploaded via NIP-96.

**If OpenClaw does not list this skill:** Install it on the VPS so the Gateway sees it (same workspace dir as nostr-nak). Run `./skills/twitter-nostr-sync/scripts/install-on-vps.sh` (script SSHs to the VPS and deploys to the workspace skills dir). Optional: `OPENCLAW_WORKSPACE_HOST=/path/on/vps` if workspace is not `/docker/openclaw-b60d/data`. Then Refresh the Dashboard.

## When to use

- User asks to "sync my tweets to Nostr", "import Twitter archive to Nostr", "run the Twitter sync", or "update tweets on Nostr".
- User asks to install or schedule the sync inside the OpenClaw container (cron loop).
- User asks to run a one-off import (e.g. after uploading a new archive zip to the VPS).

## Prerequisites

- **Twitter archive:** `data/tweets.js` from a Twitter export (or the full zip unzipped so `data/tweets.js` exists).
- **Nostr keys:** Container or environment has `NOSTR_DAMUS_PRIVATE_HEX_KEY` (or `NOSTR_PRIVATE_KEY`) and optionally `NOSTR_DAMUS_PUBLIC_HEX_KEY`.
- **VPS:** SSH access to the host where the OpenClaw container runs; container name and host from TOOLS.md or env (`NOSTR_REBROADCAST_SSH`, `NOSTR_REBROADCAST_CONTAINER`).

## Commands and scripts

All of these run **on the VPS** (or via SSH to the VPS). Paths are relative to the workspace root. SSH host and container from TOOLS.md or env (`NOSTR_REBROADCAST_SSH`, `NOSTR_REBROADCAST_CONTAINER`).

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

### 6. Install sync loop inside the container (12h cron)

Copies `twitter-archive-to-nostr` and sync scripts into the container and starts a 12-hour loop that runs the sync inside the container. No host crontab needed.

```bash
./scripts/install-twitter-sync-loop-in-container.sh
```

Optional: set `TWEETS_ON_VPS` to the host path of `tweets.js` so the script copies it into the container:

```bash
TWEETS_ON_VPS=/docker/openclaw-b60d/data/data/tweets.js ./scripts/install-twitter-sync-loop-in-container.sh
```

### 7. Run sync once inside the container (manual)

If the loop is already installed:

```bash
ssh $SSH_HOST "docker exec $CONTAINER /data/scripts/cron-twitter-to-nostr-inside-container.sh"
```

## File layout in the repo

| Path | Purpose |
|------|--------|
| `skills/twitter-nostr-sync/scripts/install-on-vps.sh` | Install skill on VPS host so it appears in Gateway Dashboard (WORKSPACE SKILLS). |
| `scripts/run-import-on-vps.sh` | Import to bridge (NIP-96, --skip-existing); tweets.js path on VPS or path to send to VPS. |
| `scripts/bridge-to-nostr-relay.sh` | Republish bridge → nostr.tagomago.me. |
| `scripts/run-dedupe-keep-nip96-on-vps.sh` | Publish kind 5 for duplicates on bridge. |
| `scripts/install-twitter-sync-loop-in-container.sh` | Install and start 12h sync loop inside container. |
| `scripts/cron-twitter-to-nostr-inside-container.sh` | One-shot sync script (runs inside container). |
| `scripts/run-twitter-sync-loop.sh` | 12h loop wrapper (runs inside container). |
| `scripts/twitter-archive-to-nostr/` | Node project: `import-tweets.js`, `dedupe-keep-nip96.js`, `package.json`. |
| `docs/CRON_INSIDE_OPENCLAW.md` | Cron inside container: mount volumes, variables. |
| `docs/CRON_TWITTER_TO_NOSTR.md` | Host cron (alternative): 2×/day from host. |

## Environment variables (optional)

- `NOSTR_REBROADCAST_SSH` — SSH host (e.g. hostinger-vps).
- `NOSTR_REBROADCAST_CONTAINER` — Container name (e.g. openclaw-b60d-openclaw-1).
- `NOSTR_RELAY` / `NOSTR_BRIDGE_RELAY` — Bridge URL (default wss://bridge.tagomago.me).
- `TWEETS_ON_VPS` — Path on VPS to `tweets.js` when using run-import or install script.

Store user-specific values (SSH host, container, paths) in **TOOLS.md**; do not hardcode secrets in scripts.
