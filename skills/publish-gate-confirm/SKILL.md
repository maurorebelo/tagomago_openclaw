---
name: publish-gate-confirm
description: "Telegram-approved public writes: queue email, X (Twitter), or Nostr kind 1 drafts as JSON; a dedicated host daemon notifies Mauro and sends only after inline Approve. Agent must not call gog gmail send, nak event/publish, or xurl post. Pairs with docs/public-write-gates.md and read-only /data/bin wrappers for xurl and nak."
---

# Publish gate (Telegram)

One **dedicated Telegram bot** (not OpenClaw’s main bot) drives approvals for:

| Channel | Enqueue (container / agent) | Execute on host after approve |
|---------|----------------------------|-------------------------------|
| Email | `skills/email-outbox-confirm/scripts/enqueue-email-draft.py` | SMTP / msmtp via `outbox_common.send_mail` |
| X | `scripts/enqueue-tweet-draft.py` | `XURL_REAL_BIN` (default `/data/bin/xurl-real`) `post --text` |
| Nostr | `scripts/enqueue-nostr-draft.py` | `NAK_REAL_BIN` (default `/data/bin/nak-real`) `event -k 1 -c … relays…` |

Paths in this skill are under `skills/publish-gate-confirm/scripts/`.

## Host env

| Variable | Purpose |
|----------|---------|
| `TELEGRAM_BOT_TOKEN` | Approval bot |
| `TELEGRAM_APPROVAL_CHAT_IDS` | Comma-separated user ids allowed to tap buttons |
| `TELEGRAM_NOTIFY_CHAT_ID` | If multiple approvers: chat id where messages appear |
| `PUBLISH_GATE_STATE_DIR` | Where `telegram-approver-state.json` lives (default: `EMAIL_OUTBOX_ROOT`) |
| `EMAIL_OUTBOX_ROOT` | Email queue root (pending/sent/rejected) |
| `TWEET_DRAFT_QUEUE_DIR` | Tweet JSON directory (default host: `/docker/openclaw-b60d/data/pending-tweets`) |
| `NOSTR_DRAFT_QUEUE_DIR` | Nostr pending dir (default: `…/data/.openclaw/nostr-outbox/pending`) |
| `XURL_REAL_BIN` | Real xurl on host (e.g. bind-mounted `…/data/bin/xurl-real`) |
| `NAK_REAL_BIN` | Real nak for signing (host must have key config / env nak expects) |
| `SMTP_*` / `msmtp` | Same as email outbox for mail send |
| `TELEGRAM_DELETE_WEBHOOK=1` | Once, if this bot had a webhook |

## Run (VPS host)

```bash
cd /path/to/skills/publish-gate-confirm/scripts
export EMAIL_OUTBOX_ROOT="/docker/openclaw-b60d/data/.openclaw/email-outbox"
export TWEET_DRAFT_QUEUE_DIR="/docker/openclaw-b60d/data/pending-tweets"
export NOSTR_DRAFT_QUEUE_DIR="/docker/openclaw-b60d/data/.openclaw/nostr-outbox/pending"
export XURL_REAL_BIN="/docker/openclaw-b60d/data/bin/xurl-real"
export NAK_REAL_BIN="/docker/openclaw-b60d/data/linuxbrew/.linuxbrew/bin/nak"
# … plus TELEGRAM_* and SMTP_*
python3 telegram_approval_daemon.py
```

TTY-only email (no Telegram): `python3 email-outbox-process.py` (same folder).

## Read-only agent tools

See **`docs/public-write-gates.md`**: `/data/bin/xurl` + `/data/bin/nak` wrappers, **`gog auth … --gmail-scope readonly`**, and `pathPrepend` order.

## Scripts

```
skills/publish-gate-confirm/scripts/
├── telegram_approval_daemon.py
├── email-outbox-process.py
├── outbox_common.py
├── enqueue-tweet-draft.py
└── enqueue-nostr-draft.py
```

Email enqueue stays in **`email-outbox-confirm`** for historical paths; behaviour matches this gate.
