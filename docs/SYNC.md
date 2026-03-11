# Sync: GitHub ↔ Mac ↔ VPS /data

## Three places, one heart (VPS /data)

| Place | Role |
|-------|------|
| **GitHub** (tagomago_openclaw) | Versioned only: code, memory files, config example, sanitized config. No secrets, no skill data. |
| **Mac** (this workspace) | Same as GitHub **plus** a local **data/** that mirrors the non-git parts of VPS /data. Edit here, push to GitHub (git) or sync to VPS (rsync). **No OpenClaw runs here.** |
| **VPS** (Hostinger, container) | **Heart of OpenClaw.** `/data` = full workspace: repo (git) + `.openclaw/`, `.env`, **data/** (zips, DBs, etc.). Runs here. |

So: **GitHub** = what’s versioned; **VPS /data** = what runs; **Mac** = versioned copy + local mirror of **data/** so you can change things locally and sync to the VPS.

## What lives where

- **In the repo (GitHub):** Memory files, skills, docs, scripts, config example, sanitized config. No **data/**.
- **Only on VPS (not in GitHub):** `.openclaw/`, `.env`, and the contents of **data/** (zips, DuckDB, Notion/Nostr data, etc.).
- **Local data/ (Mac):** Mirror of **VPS /data/data/** — not in git, but synced with the VPS so you can edit locally and push to the VPS (or pull from the VPS).

## Keeping everything aligned

1. **Code + memory (GitHub):** Edit on Mac → `git push`. On VPS: `cd /data && git pull`.
2. **Dashboard config:** After changes in the OpenClaw dashboard, run on the VPS the sanitize script; commit/push `config/openclaw.sanitized.json`. See config/README.md.
3. **data/ (non-git):**
   - **Pull from VPS → Mac:** `./scripts/sync-data-from-vps.sh` (fills local **data/** from VPS).
   - **Push Mac → VPS:** `./scripts/sync-data-to-vps.sh` (sends local **data/** to VPS).
   - So you can work in **data/** on the Mac and then sync to the VPS without putting that in GitHub.

## VPS paths (for scripts)

- **On the host:** `VPS_DATA_PATH` = `/docker/openclaw-b60d/data` (default in scripts).
- **In the container:** `/data` (workspace root); **data/** = `/data/data/`.

Set once if different: `export VPS_DATA_HOST=hostinger-vps` and `export VPS_DATA_PATH=/docker/openclaw-b60d/data`.

## VPS quick sync (code + memory)

```bash
ssh hostinger-vps "docker exec openclaw-b60d-openclaw-1 sh -c 'cd /data && git pull origin master'"
```

## data/ sync (Mac ↔ VPS, not in GitHub)

```bash
./scripts/sync-data-from-vps.sh   # pull VPS → local data/
./scripts/sync-data-to-vps.sh     # push local data/ → VPS
```
