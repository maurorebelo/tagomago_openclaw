---
name: linkedin-import
description: "Archive import: import historical LinkedIn posts and articles from a LinkedIn data export (CSV) into Nostr relays. This is a one-time or periodic batch import from a downloaded archive — not a live sync. Use when the user wants to import their LinkedIn archive, publish old LinkedIn posts to Nostr, or re-run the LinkedIn import. For live sync of new LinkedIn posts, use the linkedin-nostr-sync skill."
---

# linkedin-import

**Archive import only** — imports posts and articles from a downloaded "LinkedIn Data Export" (CSV) into Nostr.
This is not a live sync; it processes a ZIP you download manually from LinkedIn (takes ~24h to generate).
For live sync of new posts as you publish them, use **linkedin-nostr-sync**.
Preserves original timestamps. Handles both short posts (Shares.csv) and long-form articles (Articles.csv).

## File layout

```
skills/linkedin-import/
├── input/
│   ├── Shares.csv            ← extracted from LinkedIn ZIP (posts)
│   └── Articles.csv          ← optional (long-form articles)
├── state/
│   └── imported-ids.json     ← auto-created; tracks imported post hashes
└── scripts/
    └── import.js
```

## How to get the LinkedIn export

1. LinkedIn → Me → Settings & Privacy → Data Privacy → Get a copy of your data
2. Select **Posts**, **Articles** (and optionally other items — they are ignored by this script)
3. Request archive → LinkedIn emails a download link within 24h
4. Download ZIP → upload to `/data/skills/linkedin-import/input/`

## Extracting the CSV files

```bash
cd /data/skills/linkedin-import/input
unzip -j /data/skills/linkedin-import/input/Basic_LinkedInDataExport_*.zip \
  'Shares.csv' 'Articles.csv' -d .
```

## Running the import

On the VPS, inside the container:

```bash
cd /data/skills/linkedin-import
NOSTR_PRIVATE_HEX_KEY=<hex> node scripts/import.js
```

Flags:
- `--dry-run` — preview without publishing
- `--limit N` — import at most N posts (useful for testing)
- `--skip-articles` — skip Articles.csv (posts only)
- `--skip-posts` — skip Shares.csv (articles only)

## Env vars

| Var | Default |
|---|---|
| `NOSTR_PRIVATE_HEX_KEY` | required |
| `NOSTR_BRIDGE_RELAY` | `wss://bridge.tagomago.me` |
| `NOSTR_TARGET_RELAY` | `wss://nostr.tagomago.me` |

## What gets imported

**From Shares.csv:**
- `ShareCommentary` — your post text
- `ShareLink` appended when present (the URL you shared)
- Original `Date` timestamp preserved

**From Articles.csv:**
- `Title` + `Content` (body text)
- `Url` appended so readers can find the original
- Original `PublishedAt` timestamp preserved

## What gets skipped

- Shares with empty `ShareCommentary` (reshares with no comment)
- Already-imported posts (tracked by content hash in state file)

## State file

`state/imported-ids.json` — safe to interrupt and resume. Check progress:

```bash
node -e "const s = JSON.parse(require('fs').readFileSync('state/imported-ids.json')); console.log('imported:', s.imported.length)"
```

## Privacy note

LinkedIn posts are generally public, but some may have been posted to connections only.
Review your export before importing — once on Nostr relays, content is public and persistent.
