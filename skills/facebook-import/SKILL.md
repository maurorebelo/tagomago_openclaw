---
name: facebook-import
description: "Archive import: import historical Facebook posts from a Facebook data export (JSON) into Nostr relays. This is a one-time or periodic batch import from a downloaded archive — not a live sync. Use when the user wants to import their Facebook archive, publish old Facebook posts to Nostr, or re-run the Facebook import."
---

# facebook-import

**Archive import only** — imports posts from a downloaded "Facebook Data Export" (JSON) into Nostr.
This is not a live sync; it processes a ZIP you download manually from Facebook.
Preserves original timestamps. Skips posts with no text content (photo-only check-ins, etc.).

## File layout

```
skills/facebook-import/
├── input/
│   └── your_posts.json       ← extracted from Facebook ZIP (required)
├── state/
│   └── imported-ids.json     ← auto-created; tracks imported post IDs
└── scripts/
    └── import.js
```

## How to get the Facebook export

1. Facebook → Settings → Your Facebook Information → Download Your Information
2. Select: **Posts** (and optionally **Photos and Videos**)
3. Format: **JSON**, date range: all time, quality: low (media not needed unless you want photos)
4. Download ZIP → upload to `/data/skills/facebook-import/input/`

## Extracting the posts file

```bash
cd /data/skills/facebook-import/input
unzip -j /data/skills/facebook-import/input/facebook-*.zip \
  'your_activity_across_facebook/posts/your_posts_1.json' \
  -d .
mv your_posts_1.json your_posts.json
```

If Facebook split your posts across multiple files (`your_posts_1.json`, `your_posts_2.json`, …),
extract and merge them:
```bash
node -e "
const fs = require('fs');
const parts = fs.readdirSync('.').filter(f => f.match(/your_posts_\d+\.json/));
const all = parts.flatMap(f => JSON.parse(fs.readFileSync(f,'utf8')));
fs.writeFileSync('your_posts.json', JSON.stringify(all));
console.log('Merged', all.length, 'posts');
"
```

## Running the import

On the VPS, inside the container:

```bash
cd /data/skills/facebook-import
NOSTR_PRIVATE_HEX_KEY=<hex> node scripts/import.js
```

Flags:
- `--dry-run` — preview without publishing
- `--limit N` — import at most N posts (useful for testing)

## Env vars

| Var | Default |
|---|---|
| `NOSTR_PRIVATE_HEX_KEY` | required |
| `NOSTR_BRIDGE_RELAY` | `wss://bridge.tagomago.me` |
| `NOSTR_TARGET_RELAY` | `wss://nostr.tagomago.me` |

## What gets imported

- Posts with text content (`data[0].post`)
- Posts that are status updates, life events with captions, shared links with commentary
- Original timestamp preserved

## What gets skipped

- Posts with no text (photo albums, check-ins, reactions with no caption)
- Already-imported posts (tracked by content hash + timestamp in state file)

## State file

`state/imported-ids.json` — safe to interrupt and resume. Check progress:

```bash
node -e "const s = JSON.parse(require('fs').readFileSync('state/imported-ids.json')); console.log('imported:', s.imported.length)"
```

## Privacy note

The Facebook export includes ALL posts regardless of original audience (Friends, Public, Only me).
Review your posts before importing — once published to Nostr relays, they are public and cannot
be fully deleted from all relays.
