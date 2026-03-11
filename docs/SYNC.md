# Sync: GitHub ↔ Mac (repo only) ↔ VPS (OpenClaw)

## Three places

| Place | Role |
|-------|------|
| **GitHub** (tagomago_openclaw) | Source of truth for code, memory files, config example. No secrets, no skill data. |
| **Mac** (this workspace) | Repo clone only — edit skills, memory, docs, push to GitHub. **No OpenClaw runs here.** No need for `.openclaw/` or `.env` locally. Can hold skill data (zips, DBs) to sync to VPS if you want. |
| **VPS** (Hostinger, container) | **Only place OpenClaw runs.** Repo content via `git pull` in `/data`. Real `.openclaw/` and `.env` live here. Skill data (zips, DBs) lives here. |

## In the repo (GitHub)

- **Memory files:** AGENTS.md, MEMORY.md, USER.md, HEARTBEAT.md, IDENTITY.md, SOUL.md, BOOTSTRAP.md, memory/
- **Skills:** code, SKILL.md, agents/, scripts/ (no node_modules, no data)
- **Config example:** config/openclaw.json.example, config/README.md
- **Docs and scripts:** docs/, scripts/

## Not in the repo

- **Secrets:** .env, .env.*, .openclaw/openclaw.json, .openclaw/credentials/
- **Skill data:** *.zip, data/, *.duckdb, *.sqlite, Notion exports, Nostr relay dumps

## Keeping things aligned

1. **Code + memory:** Edit on Mac, push to GitHub. On VPS run `git pull` in `/data` to get latest.
2. **Config:** Edit only on VPS (or edit `config/openclaw.json.example` on Mac and apply changes on VPS). Document structure in the example and commit — no real tokens.
3. **Skill data:** Only on VPS (or sync Mac → VPS with rsync/scp if you keep copies on Mac). Never in GitHub.

## VPS quick sync

```bash
ssh hostinger-vps "docker exec openclaw-b60d-openclaw-1 sh -c 'cd /data && git pull origin master'"
```
