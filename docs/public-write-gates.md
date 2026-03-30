# Public write gates (email, Nostr, X, Gmail)

Goal: the **OpenClaw agent** drafts or reads; **human approval on Telegram** (or TTY) performs **sends/posts** from the **VPS host**, where credentials live. Aligns with `docs/openclaw_handoff_agent.md`.

## Summary

| Channel | Agent may | Block in container | Approve + execute on host |
|--------|-----------|--------------------|---------------------------|
| **X / Twitter** | `xurl` read-only wrapper only | Wrapper at `/data/bin/xurl` → `xurl-real`; PATH: `/data/bin` **before** Linuxbrew | `publish-gate-confirm` Telegram daemon → `xurl-real post` (or `scripts/publish-pending.sh`) |
| **Nostr** | `nak` read-only wrapper | `/data/bin/nak` → `nak-real`; same PATH order | Telegram daemon → `nak-real event …` (signing key on host only) |
| **Gmail (gog)** | Read/search only | Re-auth with **`--gmail-scope readonly`** (gogcli) | Outbound mail: enqueue + Telegram email path, **not** `gog gmail send` |
| **SMTP email** | Enqueue JSON only | No SMTP secrets in container | `publish-gate-confirm` / email outbox Telegram daemon + SMTP on host |

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

## 3. gog / Gmail (no send from agent)

gogcli uses the **Gmail API** (not SMTP). Sending requires modify scopes; read-only does not.

1. Re-authenticate the account with **readonly** Gmail scope (from [gogcli README](https://github.com/steipete/gogcli)):

   ```bash
   gog auth add you@gmail.com --services gmail --gmail-scope readonly --force-consent
   ```

   Use your real address and follow the OAuth flow. If the account was previously authorized with full Gmail access, **`--force-consent`** is important so Google re-issues narrower scopes.

2. Confirm: `gog gmail labels list` works; **`gog gmail send`** should fail with a permission/scope error.

3. Outbound mail from the agent must go through the **email outbox** (`enqueue-email-draft.py` + host approval), not gog send.

## 4. Telegram approval daemon (email + X + Nostr)

Skill: **`publish-gate-confirm`** — `skills/publish-gate-confirm/SKILL.md`.

- **Dedicated Telegram bot** (do **not** reuse OpenClaw’s main bot token): one long-running `getUpdates` loop; OpenClaw already consumes the other bot.
- Host env: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_APPROVAL_CHAT_IDS`, optional `TELEGRAM_NOTIFY_CHAT_ID`, `EMAIL_OUTBOX_ROOT`, optional tweet/Nostr queue dirs, plus host-only tools (`SMTP_*`, `xurl-real`, `nak-real`, signing config).

Queues:

| Queue | Env (host path examples) | Enqueue (container) |
|-------|--------------------------|---------------------|
| Email | `EMAIL_OUTBOX_ROOT` | `enqueue-email-draft.py` (email-outbox-confirm) |
| X post | `TWEET_DRAFT_QUEUE_DIR` (default `/data/pending-tweets`) | `enqueue-tweet-draft.py` |
| Nostr note | `NOSTR_DRAFT_QUEUE_DIR` (default `/data/.openclaw/nostr-outbox/pending`) | `enqueue-nostr-draft.py` |

Run the daemon from `skills/publish-gate-confirm/scripts/` on the **VPS host** (see skill).

## 5. Operational checklist

- [ ] `pathPrepend`: `/data/bin` first.
- [ ] `/data/bin/xurl` + `/data/bin/xurl-real` present.
- [ ] `/data/bin/nak` + `/data/bin/nak-real` present.
- [ ] gog Gmail auth is **readonly** (or gog disabled for agents that must not send).
- [ ] No `NOSTR_*` **private** keys in container env for interactive agents if policy is “queue only” (cron may still use secrets on host).
- [ ] Telegram approval bot running under `systemd`/`tmux` on host.
- [ ] Write-capable **xurl** / **nak** configs only on host paths the agent cannot execute directly.

## 6. Optional: OpenClaw tool policy

If the dashboard supports restricting which skills or binaries the agent may invoke, disable or sandbox **gog** “send” actions and any tool that bypasses `/data/bin` wrappers.
