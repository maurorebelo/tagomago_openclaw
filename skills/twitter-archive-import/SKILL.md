---
name: twitter-archive-import
description: Import historical tweets from a Twitter/X archive export (tweets.js) into Nostr relays, with NIP-96 media upload and deduplication tracking. Use when the user wants to import their Twitter archive, re-run the tweet import, check import progress, or add a new archive export.
---

# twitter-archive-import

Imports tweets from a Twitter/X ZIP archive export into two Nostr relays: the bridge relay and the NIP-96 relay (with original media).

## File layout

```
skills/twitter-archive-import/
├── input/
│   ├── tweets.js          ← extracted from ZIP (required)
│   ├── tweets_media/      ← optional; media files from ZIP named <tweet_id>-<filename>
│   └── twitter-*.zip      ← original ZIP archives (source)
├── state/
│   └── imported-ids.json  ← auto-created; tracks imported + skipped tweet IDs
└── scripts/
    └── import.js
```

## Running the import

On the VPS, inside the container:

```bash
cd /data/skills/twitter-archive-import
NOSTR_PRIVATE_HEX_KEY=<hex> node scripts/import.js
```

Flags:
- `--dry-run` — preview without publishing
- `--limit N` — import at most N tweets (useful for testing)
- `--skip-retweets` — record RTs in state as skipped (won't import them)

## Env vars

| Var | Default |
|---|---|
| `NOSTR_PRIVATE_HEX_KEY` | required |
| `NOSTR_BRIDGE_RELAY` | `wss://bridge.tagomago.me` |
| `NOSTR_TARGET_RELAY` | `wss://nostr.tagomago.me` |
| `NOSTR_NIP96_URL` | `https://nostr.tagomago.me/.well-known/nostr/nip96.json` |

## Extracting tweets.js from ZIP

```bash
cd /data/skills/twitter-archive-import/input
unzip -j ../input/twitter-2026-03-08.zip 'data/tweets.js' 'data/tweets_media/*' -d .
```

This places `tweets.js` and the `tweets_media/` folder directly in `input/`.

## State file

`state/imported-ids.json` is appended on every run. It is safe to interrupt and resume — already-imported IDs are never re-published. Check progress:

```bash
node -e "const s = JSON.parse(require('fs').readFileSync('state/imported-ids.json')); console.log('imported:', s.imported.length, 'skipped:', (s.skipped_retweets||[]).length)"
```

## Media handling

If `input/tweets_media/` exists, the script uploads each file to the NIP-96 server (NIP-98 auth via `nak`) and replaces the original URL in the tweet content. Falls back to the original Twitter CDN URL if upload fails or the local file is missing.
