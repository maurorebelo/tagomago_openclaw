# Public write gates (email, Nostr, X, workout writes, Gmail, destructive deletes)

Goal: the **OpenClaw agent** drafts or reads; **human approval on Telegram** (or TTY) performs **writes/deletes** from the **VPS host**, where credentials live. Aligns with `docs/openclaw_handoff_agent.md`.

## Reading order for implementers (including cloud agents)

Use this doc as the **primary checklist**. A cloud agent without SSH to the VPS can still align **repo policy, skills, and scripts**; **every shell step in §§1–5 must run on the VPS** (or whoever operates it), not “from the Mac” unless you explicitly use your own machine.

Read **in order**:

1. **This file** (`docs/public-write-gates.md`) — target architecture, PATH, wrappers, gog readonly, queues, checklist.
2. **`skills/publish-gate-confirm/SKILL.md`** — Telegram daemon, env vars, script paths, host vs container.
3. **`skills/email-outbox-confirm/SKILL.md`** — email enqueue only; points to publish-gate for host steps.
4. **`AGENTS.md`** — red lines: no `xurl post`, no `nak event`/`publish`, no `gog gmail send` from the agent; use enqueue + gate.
5. **`TOOLS.md`** — `/data/bin` wrappers, `nak`/`xurl` notes, pointer back here.

Optional background: **`docs/openclaw_handoff_agent.md`** (intent vs authority, no secrets in sandbox).

Do **not** commit SSH keys, Telegram tokens, SMTP passwords, or Nostr/X signing material to the repo — only document **variable names** and where they are set (host env, OpenClaw dashboard secrets scoped to the host daemon, etc.).

## Summary

| Channel | Agent may | Block in container | Approve + execute on host |
|--------|-----------|--------------------|---------------------------|
| **X / Twitter** | `xurl` read-only wrapper only | Wrapper at `/data/bin/xurl` → `xurl-real`; PATH: `/data/bin` **before** Linuxbrew | `publish-gate-confirm` Telegram daemon → `xurl-real post` (or `scripts/publish-pending.sh`) |
| **Nostr** | `nak` read-only wrapper | `/data/bin/nak` → `nak-real`; same PATH order | Telegram daemon → `nak-real event …` (signing key on host only) |
| **Gmail (gog)** | Read/search only | Re-auth with **`--gmail-scope readonly`** (gogcli) | Outbound mail: enqueue + Telegram email path, **not** `gog gmail send` |
| **SMTP email** | Enqueue JSON only | No SMTP secrets in container | `publish-gate-confirm` / email outbox Telegram daemon + SMTP on host |
| **Workout Notion write** | Enqueue JSON payload only | No direct write endpoint/token in container | `publish-gate-confirm` Telegram daemon POSTs approved payload to write endpoint |
| **Google Drive delete** | Read/list via gog only | `scripts/gog-readonly.sh` blocks `gog drive ... delete/remove/trash` | Enqueue JSON + Telegram approve; host runner deletes |
| **Notion delete** | Read/query in-container | No in-container delete endpoint in skills/tools | Enqueue JSON + Telegram approve; host runner deletes |

## 1. xurl (already standard here)

- Wrapper source: `scripts/xurl-readonly.sh` → installed as `/data/bin/xurl`, real binary as `/data/bin/xurl-real`.
- OpenClaw `tools.exec.pathPrepend` must start with `["/data/bin", "/data/linuxbrew/.linuxbrew/bin", …]`.
- Audit: `/data/.xurl-audit.log`.

## 2. nak (install read-only wrapper)

1. On the VPS **inside the container** (or on the host if `nak` is only on the volume):

   ```bash
   cp /data/linuxbrew/.linuxbrew/bin/nak /data/bin/nak-real
   cp /data/scripts/nak-readonly.sh /data/bin/nak
   chmod +x /data/bin/nak /data/bin/nak-real
   ```

   Adjust paths if your repo lives elsewhere; the script lives at `scripts/nak-readonly.sh` in this repo.

2. Ensure **`/data/bin` precedes** Linuxbrew in `pathPrepend` (same as xurl).

3. Audit log: `/data/.nak-audit.log` (override with `NAK_AUDIT_LOG`).

**Allowed:** `req`, `fetch`, `decode`, `encode`, `verify`, `gift unwrap`, `help`, `-h`, `--help`, `version`.  
**Blocked:** `event`, `publish`, `mount`, `admin`, `gift` (except `unwrap`), etc.

Cron jobs or host scripts that **must** publish (e.g. X→Nostr sync) should call **`/data/bin/nak-real`** explicitly with an absolute path, or run outside the agent `PATH`.

## 3. gog / Gmail + Drive delete blocking

gogcli uses the **Gmail API** (not SMTP). Sending requires modify scopes; read-only does not.

1. Re-authenticate the account with **readonly** Gmail scope (from [gogcli README](https://github.com/steipete/gogcli)):

   ```bash
   gog auth add you@gmail.com --services gmail --gmail-scope readonly --force-consent
   ```

   Use your real address and follow the OAuth flow. If the account was previously authorized with full Gmail access, **`--force-consent`** is important so Google re-issues narrower scopes.

2. Confirm: `gog gmail labels list` works; **`gog gmail send`** should fail with a permission/scope error.

3. Install `scripts/gog-readonly.sh` as `/data/bin/gog` (real binary at `/data/bin/gog-real`), and keep `/data/bin` first in `pathPrepend`.

4. Outbound mail from the agent must go through the **email outbox** (`enqueue-email-draft.py` + host approval), not gog send.

5. Google Drive destructive commands from the agent (`gog drive ... delete/remove/trash`) must be blocked by wrapper and rerouted through Telegram-approved host deletion.

## 4. Telegram approval daemon (email + X + Nostr + workout + delete gates)

Skill: **`publish-gate-confirm`** — `skills/publish-gate-confirm/SKILL.md`.

- **Dedicated Telegram bot** (do **not** reuse OpenClaw’s main bot token): one long-running `getUpdates` loop; OpenClaw already consumes the other bot.
- Host env: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_APPROVAL_CHAT_IDS`, optional `TELEGRAM_NOTIFY_CHAT_ID`, `EMAIL_OUTBOX_ROOT`, optional tweet/Nostr queue dirs, plus host-only tools (`SMTP_*`, `xurl-real`, `nak-real`, signing config).

Queues:

| Queue | Env (host path examples) | Enqueue (container) |
|-------|--------------------------|---------------------|
| Email | `EMAIL_OUTBOX_ROOT` | `enqueue-email-draft.py` (email-outbox-confirm) |
| X post | `TWEET_DRAFT_QUEUE_DIR` (default `/data/pending-tweets`) | `enqueue-tweet-draft.py` |
| Nostr note | `NOSTR_DRAFT_QUEUE_DIR` (default `/data/.openclaw/nostr-outbox/pending`) | `enqueue-nostr-draft.py` |
| Workout write | `WORKOUT_WRITE_QUEUE_DIR` (default `/data/.openclaw/write-gates/workout`) | `enqueue-workout-write.py` |
| GDrive delete | `GDRIVE_DELETE_QUEUE_DIR` (default `/data/.openclaw/delete-gates/gdrive`) | `enqueue-gdrive-delete.py` |
| Notion delete | `NOTION_DELETE_QUEUE_DIR` (default `/data/.openclaw/delete-gates/notion`) | `enqueue-notion-delete.py` |

Run the daemon from `skills/publish-gate-confirm/scripts/` on the **VPS host** (see skill).

Required host executors for delete gates:

- `GDRIVE_DELETE_RUNNER`: executable called as `runner <draft-json-path>` on approve.
- `NOTION_DELETE_RUNNER`: executable called as `runner <draft-json-path>` on approve.

## 5. Operational checklist

- [ ] `pathPrepend`: `/data/bin` first.
- [ ] `/data/bin/xurl` + `/data/bin/xurl-real` present.
- [ ] `/data/bin/nak` + `/data/bin/nak-real` present.
- [ ] gog Gmail auth is **readonly** (or gog disabled for agents that must not send).
- [ ] No `NOSTR_*` **private** keys in container env for interactive agents if policy is “queue only” (cron may still use secrets on host).
- [ ] Telegram approval bot running under `systemd`/`tmux` on host.
- [ ] Write-capable **xurl** / **nak** configs only on host paths the agent cannot execute directly.
- [ ] `gog` wrapper installed and blocking Drive deletes in-container.
- [ ] `GDRIVE_DELETE_RUNNER` and `NOTION_DELETE_RUNNER` configured on host.

## 6. Optional: OpenClaw tool policy

If the dashboard supports restricting which skills or binaries the agent may invoke, disable or sandbox **gog** “send” actions and any tool that bypasses `/data/bin` wrappers.
