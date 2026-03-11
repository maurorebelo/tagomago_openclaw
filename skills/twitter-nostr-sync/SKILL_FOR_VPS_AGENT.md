# Texto do skill para o agente no VPS

Copia o bloco abaixo e cola na conversa com o outro agente. Pedir: fazer o skill **twitter-nostr-sync** aparecer em WORKSPACE SKILLS no Gateway Dashboard; o skill já está no host em `/docker/openclaw-b60d/data/skills/twitter-nostr-sync` mas o Dashboard não o lista.

---

## Caminhos no VPS

- **Workspace no host:** `/docker/openclaw-b60d/data`
- **Skill no host (já instalado):** `/docker/openclaw-b60d/data/skills/twitter-nostr-sync/`
  - Contém: `SKILL.md`, `agents/openai.yaml`, `scripts/install-on-vps.sh`
- **Se o container montar esse dir em `/data`:** o skill no container é `/data/skills/twitter-nostr-sync/`
- **Container:** `openclaw-b60d-openclaw-1`
- **Config OpenClaw no container:** `/data/.openclaw/openclaw.json`
- **tweets.js no host:** `/docker/openclaw-b60d/data/data/tweets.js`
- **No container (sync, import):** `/data/twitter/data/tweets.js`, `/data/scripts/`, `/data/twitter-archive-to-nostr/`

O nostr-nak aparece em WORKSPACE SKILLS; o twitter-nostr-sync está na mesma pasta `skills/` no host mas não aparece. Verificar: onde o Gateway lê o workspace (path de workspace root); se precisa de `skills.load.extraDirs` em `openclaw.json`; ou se é preciso reiniciar o Gateway para rescannar.

---

## Conteúdo do SKILL.md (twitter-nostr-sync)

```
---
name: twitter-nostr-sync
description: "Sync Twitter archive to Nostr (bridge.tagomago.me and nostr.tagomago.me) with NIP-96 media. Use when the user asks to sync tweets to Nostr, import Twitter archive, run the Twitter→Nostr sync, schedule the sync (cron/loop), run a one-off import after uploading a new archive zip to the VPS, republish bridge to nostr relay, or dedupe duplicate events on the bridge (kind 5)."
---

# Twitter → Nostr sync

This skill defines how to sync the user's Twitter archive to their Nostr relays (bridge.tagomago.me and nostr.tagomago.me) with media uploaded via NIP-96.

**If OpenClaw does not list this skill:** The skill folder is at `/docker/openclaw-b60d/data/skills/twitter-nostr-sync` on the host (same workspace dir as nostr-nak). Ensure the Gateway uses that workspace path and rescans; or add it to `skills.load.extraDirs` in `/data/.openclaw/openclaw.json` in the container. Then Refresh the Dashboard.

## When to use

- User asks to "sync my tweets to Nostr", "import Twitter archive to Nostr", "run the Twitter sync", or "update tweets on Nostr".
- User asks to install or schedule the sync inside the OpenClaw container (cron loop).
- User asks to run a one-off import (e.g. after uploading a new archive zip to the VPS).

## Prerequisites

- **Twitter archive:** `data/tweets.js` from a Twitter export. On VPS host: `/docker/openclaw-b60d/data/data/tweets.js`. In container (if mounted): `/data/twitter/data/tweets.js`.
- **Nostr keys:** Container or environment has `NOSTR_DAMUS_PRIVATE_HEX_KEY` (or `NOSTR_PRIVATE_KEY`) and optionally `NOSTR_DAMUS_PUBLIC_HEX_KEY`.
- **Container:** `openclaw-b60d-openclaw-1`.

## Paths on the VPS

**Host:**
- Workspace root: `/docker/openclaw-b60d/data`
- Skill: `/docker/openclaw-b60d/data/skills/twitter-nostr-sync/` (SKILL.md, agents/openai.yaml, scripts/install-on-vps.sh)
- tweets.js: `/docker/openclaw-b60d/data/data/tweets.js`
- Twitter zip (ex.): `/docker/openclaw-b60d/data/twitter-2026-03-08.zip`

**Inside container (paths comuns se /data for mount do workspace):**
- Skill: `/data/skills/twitter-nostr-sync/`
- OpenClaw config: `/data/.openclaw/openclaw.json`
- tweets.js: `/data/twitter/data/tweets.js`
- Import Node project: `/data/twitter-archive-to-nostr/` (import-tweets.js, package.json)
- Scripts sync: `/data/scripts/cron-twitter-to-nostr-inside-container.sh`, `/data/scripts/run-twitter-sync-loop.sh`

## Commands (run on VPS host or in container)

### 1. One-off import (tweets.js on VPS host)

From host, if you have the repo and run scripts via SSH from outside, use the repo scripts. From inside the container (tweets.js at /data/twitter/data/tweets.js):

```bash
# No container
cd /data/twitter-archive-to-nostr
export NOSTR_RELAY=wss://bridge.tagomago.me
export NIP96_BASE_URL=https://nostr.tagomago.me
export SKIP_EXISTING_RELAY=wss://bridge.tagomago.me
node import-tweets.js /data/twitter/data/tweets.js --skip-existing --upload-media
```

### 2. Unzip Twitter zip on host (if unzip not installed)

```bash
python3 -c "
import zipfile
z = zipfile.ZipFile('/docker/openclaw-b60d/data/twitter-2026-03-08.zip')
z.extract('data/tweets.js', '/docker/openclaw-b60d/data')
"
```

### 3. Republish bridge → nostr.tagomago.me

Uses `nak`: from container, fetch events from bridge and publish to target relay (see repo script `scripts/bridge-to-nostr-relay.sh` for logic).

### 4. Dedupe on bridge (kind 5)

From container: run `node dedupe-keep-nip96.js` from `/data/twitter-archive-to-nostr/` (see repo script `scripts/run-dedupe-keep-nip96-on-vps.sh`).

### 5. Sync loop (12h) inside container

Scripts: `/data/scripts/cron-twitter-to-nostr-inside-container.sh` (one-shot), `/data/scripts/run-twitter-sync-loop.sh` (loop). Start loop: `docker exec -d openclaw-b60d-openclaw-1 /data/scripts/run-twitter-sync-loop.sh`

## Environment variables

- `NOSTR_RELAY` / bridge: wss://bridge.tagomago.me
- Target relay: wss://nostr.tagomago.me
- `NOSTR_DAMUS_PRIVATE_HEX_KEY` (or `NOSTR_PRIVATE_KEY`) in container
- `TWEETS_ON_VPS` or path to tweets.js: `/docker/openclaw-b60d/data/data/tweets.js` (host) or `/data/twitter/data/tweets.js` (container)
```

---

(Fim do texto para o outro agente.)
