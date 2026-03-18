# Twitter→Nostr sync cron inside the OpenClaw container

The sync (import new tweets to bridge + republish to nostr.tagomago.me) can run **inside** the OpenClaw container on a 12-hour loop, so you don't need a separate host crontab.

## What runs inside the container

1. **`scripts/cron-twitter-to-nostr-inside-container.sh`** — One-shot sync: reads `tweets.js`, imports new tweets to the bridge (NIP-96), republishes to nostr.tagomago.me.
2. **`scripts/run-twitter-sync-loop.sh`** — Loops every 12h and runs the sync script above.

Both scripts expect to run **inside** the container (they use `node`, `nak`, and env vars like `NOSTR_DAMUS_*`).

## Requirements inside the container

- **`/data/twitter/data/tweets.js`** — Updated Twitter archive `data/tweets.js` (e.g. from unzipping the latest archive). You can mount a host path here.
- **`/data/twitter-archive-to-nostr/`** — The Node project with `import-tweets.js`, `package.json`, and deps. Must be present so the sync can run `node import-tweets.js`.
- **`/data/scripts/`** — The two scripts above (or set `TWITTER_SYNC_SCRIPT` to their path).
- **Env** — Container must have `NOSTR_DAMUS_PRIVATE_HEX_KEY` (or `NOSTR_PRIVATE_KEY`) and optionally `NOSTR_DAMUS_PUBLIC_HEX_KEY` (for `nak`).

## Option A: Mount volumes and start the loop

On the **host** (VPS), ensure the container has:

1. **Twitter data** — e.g. host path `/docker/openclaw-b60d/data` (with `data/tweets.js` from the unzipped archive) mounted as `/data/twitter` in the container, so that `tweets.js` is at `/data/twitter/data/tweets.js`.
2. **Import code** — Copy or mount the repo's `scripts/twitter-archive-to-nostr` into the container at `/data/twitter-archive-to-nostr` (so `import-tweets.js` and `package.json` are there).
3. **Scripts** — Copy or mount `cron-twitter-to-nostr-inside-container.sh` and `run-twitter-sync-loop.sh` into the container (e.g. under `/data/scripts/`) and make them executable.

Then start the loop in the background (from the host):

```bash
docker exec -d openclaw-b60d-openclaw-1 /data/scripts/run-twitter-sync-loop.sh
```

(Adjust container name if needed.) The loop runs every 12h; first run is 12h after container start unless you run the sync script once manually first.

## Option B: One-time setup via copy (no compose change)

If you prefer not to change compose/volumes, you can copy files in and start the loop once:

1. **Copy twitter-archive-to-nostr** into the container (from the repo on your Mac, or from the host if the repo is there).

2. **Copy scripts** and make them executable.

3. **Ensure tweets.js is available** — e.g. copy from host into container, or mount. If you already have it at `/docker/openclaw-b60d/data/data/tweets.js` on the host, copy into container at `/data/twitter/data/tweets.js`.

4. **Start the loop**:

```bash
docker exec -d openclaw-b60d-openclaw-1 /data/scripts/run-twitter-sync-loop.sh
```

**Note:** Anything copied with `docker cp` is lost if the container is recreated. For a permanent setup, use volumes/mounts (Option A) or add these copies to your image/build.

## Variables (optional)

- **`TWEETS_JS_PATH`** — Override path to `tweets.js` (default: `/data/twitter/data/tweets.js`).
- **`IMPORT_DIR`** — Override path to the Node import project (default: `/data/twitter-archive-to-nostr`).
- **`TWITTER_SYNC_INTERVAL_SEC`** — Loop interval in seconds (default: 43200 = 12h).
- **`NOSTR_BRIDGE_RELAY`** / **`NOSTR_TARGET_RELAY`** — Bridge and target relay URLs.

## Run sync once (manual)

```bash
docker exec openclaw-b60d-openclaw-1 /data/scripts/cron-twitter-to-nostr-inside-container.sh
```

## Summary

- **Cron runs inside OpenClaw** — No host crontab; the container runs the 12h loop.
- **Sync still depends on the container** — If the container is down, the sync doesn't run.
- **Keep `tweets.js` updated** — Replace (or update the mounted file) when you have a new Twitter archive so the next sync run imports only new tweets (--skip-existing).
