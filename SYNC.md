# Sync: GitHub ↔ Mac ↔ VPS /data

**Canonical = VPS.** The VPS is the source of truth. Local and GitHub only have what the VPS has (or what we sync from it). We do not add folders (e.g. docs/, media/) that don’t exist on the VPS.

## Three places, one heart (VPS /data)

| Place | Role |
|-------|------|
| **VPS** (Hostinger, container) | **Canonical.** `/data` = full workspace. What runs here is truth. |
| **GitHub** (tagomago_openclaw) | Versioned copy: code, memory files, config example, sanitized config. No secrets, no skill data. Only what belongs with the canonical VPS. |
| **Mac** (this workspace) | Same as GitHub **plus** local **data/** mirror of VPS /data/data. Edit here, push to GitHub or sync to VPS. **No OpenClaw runs here.** |

## What lives where

- **In the repo (GitHub):** Memory files (`memory/`, MEMORY.md, AGENTS.md, etc.), skills (with their **references/** — VPS-specific docs live inside each skill), scripts, config example, sanitized config. No **data/**.
- **Only on VPS (not in GitHub):** `.openclaw/`, `.env`, **data/** (zips, DBs, etc.).
- **Local data/ (Mac):** Mirror of **VPS /data/data/** — rsync pull/push.

**Reorganization:** Former top-level `docs/` and `media/inbound/` were removed (canonical = VPS, which didn’t have them). Their useful content is now inside skills: e.g. `skills/health-analytics/references/apple_health_sleep_vps.md`, `health_analytics_vps.md`; `skills/twitter-nostr-sync/references/cron_inside_container.md`. **memory/** stays — it’s the agent’s daily/long-term memory and exists on the VPS; keep it in the repo and in sync.

## Keeping everything aligned

1. **Code + memory:** Edit on Mac → `git push`. On VPS: ensure origin is set and run `git pull` when you want to pull from GitHub.
2. **Dashboard config:** After dashboard changes, on VPS run the sanitize script; commit/push `config/openclaw.sanitized.json`. See config/README.md.
3. **data/ (non-git):** `./scripts/sync-data-from-vps.sh` (VPS → Mac), `./scripts/sync-data-to-vps.sh` (Mac → VPS).

## VPS paths

- **Host:** `VPS_DATA_PATH` = `/docker/openclaw-b60d/data`. **Container:** `/data`.

## Commands

```bash
./scripts/sync-data-from-vps.sh   # pull VPS → local data/
./scripts/sync-data-to-vps.sh     # push local data/ → VPS
```
