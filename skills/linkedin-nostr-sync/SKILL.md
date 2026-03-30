---
name: linkedin-nostr-sync
description: "Sync LinkedIn posts to Nostr. Two modes: (1) Batch import from a LinkedIn archive export (CSV); (2) Live sync of new posts via LinkedIn API, 2x/day. Use when the user asks to sync LinkedIn to Nostr, run the LinkedIn live sync, set up scheduled sync, or check LinkedIn sync status."
---

# LinkedIn → Nostr sync

Two modes, same as twitter-nostr-sync:

1. **Batch import (archive)** — processes a LinkedIn data export ZIP. Use `linkedin-import` skill for this. That skill handles the CSV extraction and deduplication.
2. **Live sync (API, 2x/day)** — fetches new LinkedIn posts via the official LinkedIn Posts API and publishes to Nostr. Runs on a 12h schedule.

---

## Live sync — how it works

Fetches posts from `GET /rest/posts?author={person_urn}&q=author` (LinkedIn API v202401).
Only processes posts created since the last sync (tracked in state file).
Publishes each post as a Nostr kind:1 event via `nak`, preserving original timestamp.

---

## Prerequisites (one-time setup)

LinkedIn live sync requires OAuth 2.0 credentials. This is a one-time setup.

### 1. Create a LinkedIn Developer app

1. Go to [linkedin.com/developers](https://www.linkedin.com/developers/apps/new)
2. Create an app (name: e.g. "My Nostr Sync", company: your LinkedIn company page or create one)
3. Under **Products**, add:
   - **Sign In with LinkedIn using OpenID Connect** (auto-approved)
   - **Share on LinkedIn** (auto-approved — gives `r_member_social` read access)
4. Under **Auth**, add redirect URL: `http://localhost:3000/callback`
5. Copy **Client ID** and **Client Secret**

### 2. Run the auth setup script (one-time)

On the VPS, inside the container:

```bash
cd /data/skills/linkedin-nostr-sync
node scripts/auth.js --client-id <ID> --client-secret <SECRET>
```

This opens an authorization URL. Open it in your browser, log in to LinkedIn, authorize.
The script captures the callback on `localhost:3000` and saves tokens to `/data/.linkedin`.

> If running on a remote VPS: the script will print the URL and a local redirect port.
> Forward the port first: `ssh -L 3000:localhost:3000 hostinger-vps`
> Then open the URL in your Mac browser.

### 3. Verify

```bash
node scripts/sync.js --dry-run
```

Should print your LinkedIn person ID and recent posts.

---

## Running the sync

### One-off sync (manual)

```bash
cd /data/skills/linkedin-nostr-sync
NOSTR_PRIVATE_HEX_KEY=<hex> node scripts/sync.js
```

### Live sync loop (2x/day, every 12h)

```bash
docker exec -d openclaw-b60d-openclaw-1 /data/skills/linkedin-nostr-sync/scripts/run-sync-loop.sh
```

Check logs: `cat /data/skills/linkedin-nostr-sync/state/sync.log`

### Flags

- `--dry-run` — fetch and preview without publishing
- `--limit N` — publish at most N posts per run
- `--since <ISO date>` — override last-sync date (e.g. `--since 2024-01-01`)

---

## Env vars

| Var | Default |
|---|---|
| `NOSTR_PRIVATE_HEX_KEY` | required (or set in `/data/.linkedin`) |
| `NOSTR_BRIDGE_RELAY` | `wss://bridge.tagomago.me` |
| `NOSTR_TARGET_RELAY` | `wss://nostr.tagomago.me` |
| `LINKEDIN_CONFIG` | `/data/.linkedin` (tokens file path) |

---

## Config file: `/data/.linkedin`

```json
{
  "client_id": "...",
  "client_secret": "...",
  "access_token": "...",
  "refresh_token": "...",
  "person_id": "urn:li:person:...",
  "token_expires_at": 1234567890
}
```

**Keep this file on the VPS host only, not in the container at rest.**
The sync loop sources it at runtime.

---

## File layout

```
skills/linkedin-nostr-sync/
├── SKILL.md
├── state/
│   ├── sync-state.json     ← auto-created; last sync time + published post IDs
│   └── sync.log            ← append-only log
└── scripts/
    ├── sync.js             ← main sync: fetch LinkedIn posts, publish to Nostr
    ├── auth.js             ← OAuth 2.0 setup (one-time)
    └── run-sync-loop.sh    ← 12h loop
```

---

## Token refresh

LinkedIn access tokens expire in 60 days. Refresh tokens expire in 365 days.
`sync.js` automatically refreshes the access token when it's within 7 days of expiry.
Re-run `auth.js` if the refresh token has also expired.

---

## Safety

- Only fetches posts authored by the authenticated account (filtered by `author` URN).
- Only publishes posts with `visibility: PUBLIC`.
- State file prevents re-publishing already-synced posts.
