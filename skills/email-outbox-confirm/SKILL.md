---
name: email-outbox-confirm
description: "Queue outbound email drafts from the OpenClaw agent without sending. Host sends after Telegram approval (unified daemon in publish-gate-confirm) or TTY. See docs/public-write-gates.md."
---

# Email outbox (draft → human confirm → send)

Same **authority split** as `docs/openclaw_handoff_agent.md` and **`docs/public-write-gates.md`**.

## Roles

| Where | What it may do |
|--------|----------------|
| **Inside the OpenClaw container** | Run **`enqueue-email-draft.py` only**. Writes JSON under `/data/.openclaw/email-outbox/pending/`. No SMTP, no `gog gmail send`, no `himalaya send`. |
| **VPS host** | Run **`publish-gate-confirm/scripts/telegram_approval_daemon.py`** (email + X + Nostr) or **`email-outbox-telegram.py`** here (thin wrapper to the same daemon). TTY email only: **`publish-gate-confirm/scripts/email-outbox-process.py`**. |

## Agent: enqueue

```bash
python3 /data/skills/email-outbox-confirm/scripts/enqueue-email-draft.py \
  --to "recipient@example.com" \
  --subject "Subject line" \
  --body "Email body..."
```

Or `--body-file /data/some-draft.txt`. Optional `--note`.

Tell Mauro the draft is queued for **Telegram approval** (if the daemon runs on the host).

## Host: Telegram + SMTP

Full env and procedures: **`skills/publish-gate-confirm/SKILL.md`** and **`docs/public-write-gates.md`**.

Typical:

```bash
cd /path/to/skills/publish-gate-confirm/scripts
export EMAIL_OUTBOX_ROOT="/docker/openclaw-b60d/data/.openclaw/email-outbox"
# TELEGRAM_* , SMTP_* …
python3 telegram_approval_daemon.py
```

## Scripts (this skill)

```
skills/email-outbox-confirm/
├── SKILL.md
├── agents/openai.yaml
└── scripts/
    ├── enqueue-email-draft.py   # agent / container
    └── email-outbox-telegram.py # wrapper → publish-gate-confirm daemon
```
