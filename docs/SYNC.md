# Sync: GitHub ↔ Local ↔ VPS

## Three places

| Place | Role |
|-------|------|
| **GitHub** (tagomago_openclaw) | Source of truth for code, memory files, config example. No secrets, no skill data. |
| **Local** (Mac workspace) | Clone of repo + local `.openclaw/` and `.env`. Can hold skill data (zips, DBs) synced with VPS. |
| **VPS** (Hostinger, container) | Same repo content via `git pull` + its own `.openclaw/` and `.env`. Holds skill data. |

## In the repo (GitHub)

- **Memory files:** AGENTS.md, MEMORY.md, USER.md, HEARTBEAT.md, IDENTITY.md, SOUL.md, BOOTSTRAP.md, memory/
- **Skills:** code, SKILL.md, agents/, scripts/ (no node_modules, no data)
- **Config example:** config/openclaw.json.example, config/README.md
- **Docs and scripts:** docs/, scripts/

## Not in the repo

- **Secrets:** .env, .env.*, .openclaw/openclaw.json, .openclaw/credentials/
- **Skill data:** *.zip, data/, *.duckdb, *.sqlite, Notion exports, Nostr relay dumps

## Keeping the three aligned

1. **Code + memory:** Push from local to GitHub; on VPS run `git pull` (in `/data`) to get latest.
2. **Config:** Edit on VPS or local; document structure/changes in `config/openclaw.json.example` and commit (no real tokens).
3. **Skill data:** Sync between local and VPS only (e.g. rsync, scp, or manual). Never push to GitHub.

## VPS quick sync

```bash
ssh hostinger-vps "docker exec openclaw-b60d-openclaw-1 sh -c 'cd /data && git pull origin master'"
```
