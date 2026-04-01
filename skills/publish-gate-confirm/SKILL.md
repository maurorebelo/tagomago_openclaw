---
name: publish-gate-confirm
description: "Telegram-approved writes/deletes: queue email, X (Twitter), Nostr kind 1 drafts, workout Notion writes, and destructive delete requests (Google Drive/Notion) as JSON; one dedicated host daemon executes only after inline Approve. Agent must not call gog gmail send, gog drive delete, nak event/publish, xurl post, direct Notion writes/deletes, or other direct outbound writes."
---

# Publish gate (Telegram)

One **dedicated Telegram bot** (not OpenClaw’s main bot) drives approvals for:

| Channel | Enqueue (container / agent) | Execute on host after approve |
|---------|----------------------------|-------------------------------|
| Email | `skills/email-outbox-confirm/scripts/enqueue-email-draft.py` | SMTP / msmtp via `outbox_common.send_mail` |
| X | `scripts/enqueue-tweet-draft.py` | `XURL_REAL_BIN` (default `/data/bin/xurl-real`) `post --text` |
| Nostr | `scripts/enqueue-nostr-draft.py` | `NAK_REAL_BIN` (default `/data/bin/nak-real`) `event -k 1 -c … relays…` |
| Workout Notion write | `scripts/enqueue-workout-write.py` | `WORKOUT_WRITE_URL` HTTP POST via `scripts/telegram_approval_daemon.py` |
| Google Drive delete | `scripts/enqueue-gdrive-delete.py` | `GDRIVE_DELETE_RUNNER <draft-json-path>` |
| Notion delete | `scripts/enqueue-notion-delete.py` | `NOTION_DELETE_RUNNER <draft-json-path>` |

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
| `GDRIVE_DELETE_QUEUE_DIR` | Google Drive delete queue root (default: `…/data/.openclaw/delete-gates/gdrive`) |
| `NOTION_DELETE_QUEUE_DIR` | Notion delete queue root (default: `…/data/.openclaw/delete-gates/notion`) |
| `XURL_REAL_BIN` | Real xurl on host (e.g. bind-mounted `…/data/bin/xurl-real`) |
| `NAK_REAL_BIN` | Real nak for signing (host must have key config / env nak expects) |
| `GDRIVE_DELETE_RUNNER` | Executable path. Called as `runner <draft-json-path>` on approve |
| `NOTION_DELETE_RUNNER` | Executable path. Called as `runner <draft-json-path>` on approve |
| `WORKOUT_WRITE_QUEUE_DIR` | Workout write queue root (default: `…/data/.openclaw/write-gates/workout`) |
| `WORKOUT_WRITE_URL` | Endpoint that receives approved workout payloads |
| `WORKOUT_WRITE_BEARER_TOKEN` | Optional bearer token for `WORKOUT_WRITE_URL` |
| `WORKOUT_WRITE_TIMEOUT_SEC` | Optional HTTP timeout (default: 30) |
| `SMTP_*` / `msmtp` | Same as email outbox for mail send |
| `TELEGRAM_DELETE_WEBHOOK=1` | Once, if this bot had a webhook |

## Run (VPS host)

```bash
cd /path/to/skills/publish-gate-confirm/scripts
export EMAIL_OUTBOX_ROOT="/docker/openclaw-b60d/data/.openclaw/email-outbox"
export TWEET_DRAFT_QUEUE_DIR="/docker/openclaw-b60d/data/pending-tweets"
export NOSTR_DRAFT_QUEUE_DIR="/docker/openclaw-b60d/data/.openclaw/nostr-outbox/pending"
export GDRIVE_DELETE_QUEUE_DIR="/docker/openclaw-b60d/data/.openclaw/delete-gates/gdrive"
export NOTION_DELETE_QUEUE_DIR="/docker/openclaw-b60d/data/.openclaw/delete-gates/notion"
export XURL_REAL_BIN="/docker/openclaw-b60d/data/bin/xurl-real"
export NAK_REAL_BIN="/docker/openclaw-b60d/data/linuxbrew/.linuxbrew/bin/nak"
export GDRIVE_DELETE_RUNNER="/absolute/path/to/host-gdrive-delete-runner"
export NOTION_DELETE_RUNNER="/absolute/path/to/host-notion-delete-runner"
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
├── enqueue-nostr-draft.py
├── enqueue-workout-write.py
├── enqueue-gdrive-delete.py
└── enqueue-notion-delete.py
```

Email enqueue stays in **`email-outbox-confirm`** for historical paths; behaviour matches this gate.
