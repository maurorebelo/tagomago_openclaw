# TOOLS.md - Environment Reference

Quick-reference for paths, binaries, and setup facts. Procedures live in the relevant skill.

---

## VPS / Container

| Item | Value |
|------|-------|
| SSH host | `hostinger-vps` |
| Container | `openclaw-b60d-openclaw-1` |
| Workspace (container) | `/data` |
| Workspace (host) | `/docker/openclaw-b60d/data` |
| Config | `/data/.openclaw/openclaw.json` |

---

## Telegram file uploads

Files arrive at `/data/.openclaw/media/inbound/` with UUID names — **not** the original filename. Files do not persist across container restarts.

To find the most recent file:
```bash
ls -lt /data/.openclaw/media/inbound/ | head -5
```

**For PDFs: always use the `nano-pdf` bundled skill.** Never read the raw PDF directly.

---

## Verified binaries

## Toda.bio DB quick facts (2026-03-31)
- Postgres EC2: `i-00dd892cdd1941be1` (Name `DATABASE_biob_todabio`) — Public IP `72.44.46.213` — port `5432`
- Connectivity check from this container (python socket): **can connect to `72.44.46.213:5432`**; cannot reach private `172.31.17.146:5432` (timeout).
- Container does **not** have `nc` or `psql` installed; use python socket for port checks.
- DB credentials live in aws-broker secret/env (Hostinger). Not exposed as env vars in this container by default.
- (User-confirmed) `psql` auth with app creds (`TODABIO_V2_PGUSER`/`TODABIO_V2_PGPASSWORD`) against DB `biob_todabio_v2` works.

| Tool | Path | Notes |
|------|------|-------|
| `xurl` | `/data/bin/xurl` | Read-only wrapper. Logs to `/data/.xurl-audit.log`. Real binary at `/data/bin/xurl-real`. |
| `nak` | `/data/bin/nak` (recommended) | Read-only wrapper (`scripts/nak-readonly.sh`) → `nak-real`. Logs `/data/.nak-audit.log`. Without wrapper, Linuxbrew `nak` can still publish — fix PATH. |
| `gog` | `/data/bin/gog` (recommended) | Read-only wrapper (`scripts/gog-readonly.sh`) → `gog-real`. Blocks `gmail send` and Drive destructive commands in-container. |
| `tesseract` | `/usr/bin/tesseract` | OCR. Languages: eng, por, ita |

Before using any CLI tool, verify with `which <tool>`. If missing, say so — do not fabricate output.

---

## Write gates (email, X, Nostr, Gmail)

Canonical doc: **`docs/public-write-gates.md`** (includes **reading order for cloud agents** at the top).

- **Telegram approvals:** `skills/publish-gate-confirm/` — one daemon for email + X + Nostr drafts and destructive delete gates (Google Drive/Notion).
- **gog / Gmail:** re-auth with `gog auth add … --services gmail --gmail-scope readonly --force-consent` so the agent cannot send mail via API.
- **Delete gates:** enqueue with `enqueue-gdrive-delete.py` / `enqueue-notion-delete.py`; host daemon runs `GDRIVE_DELETE_RUNNER` / `NOTION_DELETE_RUNNER` after Telegram approval.
- **Cron / host jobs** that must publish should call **`nak-real`** / **`xurl-real`** by absolute path, not the agent `PATH`.

---

## xurl (X/Twitter)

- Tokens read from `/data/.xurl` (YAML). If missing, see `skills/twitter-nostr-sync/SKILL.md`.
- **Never post to X from the agent.** xurl wrapper is read-only: `whoami`, `timeline`, `GET /2/users/{id}/tweets` only. To post: `enqueue-tweet-draft.py` + host daemon.
- exec PATH must have `/data/bin` before Linuxbrew — otherwise the real xurl bypasses the wrapper.
- Script to write tokens from env: `scripts/write-xurl-from-env.js`

---

## Nostr

- Main account pubkey: `NOSTR_DAMUS_PUBLIC_HEX_KEY` env var (or see USER.md for npub).
- Relays: `wss://nostr.tagomago.me`, `wss://bridge.tagomago.me`
- For "my last note": see `skills/twitter-nostr-sync/SKILL.md`.
- **Agent:** use wrapped `nak` only (`req`, etc.). **Publish:** `enqueue-nostr-draft.py` in `publish-gate-confirm` + Telegram on host.
