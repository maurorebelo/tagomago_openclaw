# OpenClaw config (versioned)

This folder holds **sanitized / example** OpenClaw configuration so changes are tracked in GitHub. The real config lives in `.openclaw/` on the VPS and is **not** committed (secrets, tokens).

The real config lives **only on the VPS** (`/data/.openclaw/openclaw.json` and `.env`). Do not run OpenClaw locally.

## Keeping the repo in sync with the dashboard

So you don’t have to remember whether dashboard changes are in GitHub:

1. **After you change anything in the OpenClaw dashboard** (skills, plugins, channels, models, etc.), run on the VPS:
   ```bash
   ssh hostinger-vps "docker exec openclaw-b60d-openclaw-1 sh -c 'cd /data && node scripts/sanitize-openclaw-config.js'"
   ```
   That writes `config/openclaw.sanitized.json` (structure only, no tokens).

2. **Get that file into GitHub** in one of two ways:
   - **Preferred (once set up):** On the VPS, configure git so it can push to GitHub (SSH key or token). Then run the full sync script so it also commits and pushes:
     ```bash
     ssh hostinger-vps "docker exec openclaw-b60d-openclaw-1 sh -c 'cd /data && ./scripts/sync-openclaw-config-to-repo.sh'"
     ```
     Uncomment the `git add` / `git commit` / `git push` lines in `scripts/sync-openclaw-config-to-repo.sh`. After that, one command after any dashboard change keeps the repo in sync; on the Mac you just `git pull`.
   - **Without VPS push:** After step 1, copy the file from the VPS to the Mac (e.g. `scp`), then commit and push from the Mac.

Result: the repo (and anyone reading it) always sees the same shape as the dashboard, without any secrets.

- **Script:** `scripts/sanitize-openclaw-config.js` (writes `config/openclaw.sanitized.json`).
- **Wrapper:** `scripts/sync-openclaw-config-to-repo.sh` (runs the script; optionally git add/commit/push if you uncomment and have credentials on the VPS).

## Exec PATH hardening

If the agent uses the `xurl` read-only wrapper in `/data/bin`, the OpenClaw config on the VPS must keep `/data/bin` ahead of Linuxbrew in `tools.exec.pathPrepend`:

```json
"tools": {
  "exec": {
    "host": "gateway",
    "security": "full",
    "ask": "off",
    "pathPrepend": [
      "/data/bin",
      "/data/linuxbrew/.linuxbrew/bin"
    ]
  }
}
```

Why this matters: if `/data/linuxbrew/.linuxbrew/bin` comes first, agent `exec` can resolve the real `xurl` binary before the wrapper, bypassing both the write block and `/data/.xurl-audit.log`.

## Skills

- **Workspace skills** (in this repo): live in `skills/` and are deployed to `/data/skills/` on the VPS (health-analytics, twitter-nostr-sync, nostr2notion, etc.).
- **Built-in skills** (ship with OpenClaw): e.g. **gog** — enabled in Dashboard → Skills. The gog skill requires the `gog` binary, installed on the VPS via Linuxbrew (gogcli) in `/data/linuxbrew`. Document any enabled built-in skill here so the repo reflects what the dashboard has.

## Do not commit

- `.env` (any env file with keys/tokens)
- `.openclaw/openclaw.json` (contains tokens)
- `.openclaw/credentials/`
