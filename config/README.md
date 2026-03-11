# OpenClaw config (versioned)

This folder holds **sanitized / example** OpenClaw configuration so changes are tracked in GitHub. The real config lives in `.openclaw/` on each machine and is **not** committed (secrets, tokens, paths).

The real config lives **only on the VPS** (`/data/.openclaw/openclaw.json` and `.env`). Do not run OpenClaw locally.

When you change plugins, channels, models, gateway, or tools on the VPS, update the example here (with placeholders for secrets) so the repo stays aligned.

## Do not commit

- `.env` (any env file with keys/tokens)
- `.openclaw/openclaw.json` (contains tokens)
- `.openclaw/credentials/`
