# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## Twitter → Nostr sync

**Skill:** `skills/twitter-nostr-sync/SKILL.md` — use when the user asks to sync tweets to Nostr, import archive, or run/schedule the sync.

- **SSH host:** `hostinger-vps` (or set `NOSTR_REBROADCAST_SSH`)
- **Container:** `openclaw-b60d-openclaw-1` (or set `NOSTR_REBROADCAST_CONTAINER`)
- **VPS workspace (host path):** `/docker/openclaw-b60d/data` — use for rsync scripts (`VPS_DATA_PATH`); in container this is `/data`.
- **tweets.js on VPS:** `/docker/openclaw-b60d/data/data/tweets.js` (after unzipping archive under `/docker/openclaw-b60d/data/`)
- **Bridge:** wss://bridge.tagomago.me — **Target:** wss://nostr.tagomago.me

## VPS tools (not in default Hostinger install)

- **gog** (skill no dashboard): skill built-in do OpenClaw (vem no pacote). No dashboard, Skills → marcar **gog**. Depende do binário `gog`, que no VPS está instalado via Linuxbrew (fórmula gogcli) em `/data/linuxbrew`; config em `/data/.config/gogcli`. Ou seja: a *skill* é a "gog" no OpenClaw; o *binário* é gogcli no /data.

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Examples

```markdown
### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

Add whatever helps you do your job. This is your cheat sheet.
