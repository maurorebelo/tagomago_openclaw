# OpenClaw config (versioned)

This folder holds **sanitized / example** OpenClaw configuration so changes are tracked in GitHub. The real config lives in `.openclaw/` on each machine and is **not** committed (secrets, tokens, paths).

- **On VPS:** `/data/.openclaw/openclaw.json` (and `.env` for secrets).
- **Locally:** `.openclaw/` and `.env` stay out of the repo.

When you change plugins, channels, models, gateway, or tools on one install, update the example here (with placeholders for secrets) so the other install and the repo stay aligned.

## Do not commit

- `.env` (any env file with keys/tokens)
- `.openclaw/openclaw.json` (contains tokens)
- `.openclaw/credentials/`
