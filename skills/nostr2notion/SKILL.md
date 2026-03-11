---
name: nostr2notion
description: "Bridge Nostr events to Notion. Use when the user wants to capture Nostr notes/events into a Notion database, run the Nostr→Notion bridge, or configure which relays/kinds/pubkeys to sync."
---

# Nostr → Notion bridge

This skill runs a small bridge that subscribes to Nostr relays and writes matching events into a Notion database (new page per event). **v1.1** adds backfill (all-time with time windows + EOSE), dedupe by `event.id`, rate-limit–safe write queue, and improved title/body.

## When to use

- User asks to "connect Nostr to Notion", "sync Nostr to Notion", "capture Nostr notes in Notion", or "run the nostr2notion bridge".
- User wants to capture notes (kind 1), DMs (kind 4), or other kinds into a Notion database.
- User wants **all-time backfill** (historical events) or **live-only** sync.
- User wants to configure filters (relays, pubkeys, hashtags) or the target Notion database.

## Directions supported

- **Nostr → Notion (default):** Subscribe to relays; when an event matches the filter, create a Notion page (dedupe by Event ID, queue + rate-limit handling).
- **Backfill (v1.1):** Set `BACKFILL=1` to iterate time windows (e.g. 7 days), wait for EOSE per window, dedupe, then write. Use for "all time" without overloading relays or Notion.
- **Notion → Nostr:** Not implemented; can be added later.

## Prerequisites

- **Notion:** Integration token with access to the target database. Create an integration at [notion.so/my-integrations](https://www.notion.so/my-integrations), then share the database with it. Add a **rich_text** property **Event ID** (or set `NOTION_EVENT_ID_PROPERTY`) for dedupe.
- **Nostr:** Relays (e.g. `wss://bridge.tagomago.me`). The bridge sends a **single** filter per REQ (NIP-01); some relays reject when the client sends an array of filters as the third element. Optional: filter by kinds, pubkeys, or hashtags via env.
- **Node.js** in the environment where the bridge runs (workspace or VPS container).

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `NOTION_API_KEY` | Yes | Notion integration token (starts with `ntn_` or `secret_`). |
| `NOTION_DATABASE_ID` | Yes | Target database ID (UUID from the database URL). |
| `NOTION_TITLE_PROPERTY` | No | Name of the title property (default `Title`; use `Name` if your DB uses that). |
| `NOTION_EVENT_ID_PROPERTY` | No | Rich-text property used for dedupe (default `Event ID`). Must exist in DB. |
| `NOTION_NOSTR_URI_PROPERTY` | No | If set, name of a **URL** property (e.g. `Nostr URI`). Bridge writes `https://njump.me/<event_id>`. Leave unset to skip. |
| `NOSTR_RELAYS` | Yes | Comma-separated relay URLs (e.g. `wss://bridge.tagomago.me`). |
| `NOSTR_KINDS` | No | Comma-separated kinds to sync (default `1`). |
| `NOSTR_PUBKEYS` | No | Comma-separated hex pubkeys to filter (e.g. `e24616cde0fdbe0164d0831309aea3eb4ed61e320a3c37dc0048edc8ac49976b`). |
| `NOSTR_HASHTAGS` | No | Comma-separated hashtags (e.g. `#openclaw,#nostr`). |
| **Backfill (v1.1)** | | |
| `BACKFILL` | No | Set `1` to run in backfill mode (time windows + EOSE). |
| `BACKFILL_CHUNK_DAYS` | No | Days per window (default `7`). |
| `BACKFILL_START_UNTIL` | No | Unix timestamp for “until”; default = now. Omit to start from now and go backwards. |
| `BACKFILL_USE_UNTIL` | No | Set to `0` to omit `until` from the REQ filter. Use if the relay returns “could not parse command” (some bridges don’t support `until`). Default: use `until`. |
| **Rate limit** | | |
| `NOTION_CONCURRENCY` | No | Max concurrent Notion writes (default `1`; use 1–3 to avoid 429). |
| `NOTION_RETRY_AFTER_429_MS` | No | Ms to wait before retry on 429 (default `60000`). |

Store secrets in Keychain (Mac) or in the OpenClaw container env (VPS); do not commit them.

## Commands

All paths relative to the workspace root. The bridge runs in Node; run it **on the VPS** (inside the OpenClaw container or on the host) so it has access to relays and Notion API.

### 1. Install dependencies (first time)

```bash
cd skills/nostr2notion && npm install
```

### 2. Run the bridge (Nostr → Notion)

**Live (default):** subscribes and creates pages as events arrive; dedupes by Event ID and uses a write queue.

```bash
cd skills/nostr2notion && node bridge.js
```

**Backfill (all-time):** iterates time windows (e.g. 7 days), waits for EOSE, dedupes, then writes. Use when you want historical events without overloading.

```bash
export BACKFILL=1
export BACKFILL_CHUNK_DAYS=7
# optional: BACKFILL_START_UNTIL=<unix> to resume from a given time
node bridge.js
```

Ensure env is set (e.g. export or `.env` or container env):

```bash
export NOTION_API_KEY="ntn_..."
export NOTION_DATABASE_ID="..."
export NOSTR_RELAYS="wss://bridge.tagomago.me"
export NOSTR_KINDS="1"
export NOSTR_PUBKEYS="e24616cde0fdbe0164d0831309aea3eb4ed61e320a3c37dc0048edc8ac49976b"
# optional: NOSTR_HASHTAGS="#tag1,#tag2", NOTION_EVENT_ID_PROPERTY="Event ID"
node bridge.js
```

The process runs until stopped (Ctrl+C). It subscribes to the relays, and for each matching event creates a new page in the Notion database with title (event id or date) and body (content + metadata).

### 3. Run on VPS (inside container)

Copy the skill to the VPS workspace (or mount the repo), then inside the container:

```bash
cd /data/.openclaw/workspace/skills/nostr2notion && npm install && node bridge.js
```

To run in the background (e.g. with `nohup` or a process manager):

```bash
nohup node bridge.js >> /data/.openclaw/workspace/skills/nostr2notion/bridge.log 2>&1 &
```

**Single managed instance (agent):** Use one log file in the workspace: `skills/nostr2notion/bridge.log` (in container: `/data/skills/nostr2notion/bridge.log`). So the agent can inspect output without redirecting to `/tmp`. Ensure the skill dir is owned by the user the agent runs as (e.g. `chown -R node:node /data/skills/nostr2notion` as root); then the agent can append to the log and stop only its own bridge with `pkill -u $(whoami) -f 'node.*bridge.js'` (avoids killing root-owned processes).

### 4. Notion database shape (v1.1)

- **Title** (title property): first ~80 chars of event content, or fallback `{kind} {id.slice(0,8)} @ {date}`.
- **Event ID** (rich_text): full event id for dedupe; **must exist** so the bridge can skip duplicates. Name can be overridden with `NOTION_EVENT_ID_PROPERTY`.
- **Nostr URI** (optional): add a **URL** property (e.g. `Nostr URI`) and set `NOTION_NOSTR_URI_PROPERTY=Nostr URI` to fill it with `https://njump.me/<event_id>`. Omit to leave empty.
- **Body** (paragraph block): full content + metadata (id, created_at, kind, pubkey, relay, tags).

Create a Notion database with at least **Title** and **Event ID** (rich_text); share it with the integration.

## File layout

| Path | Purpose |
|------|---------|
| `skills/nostr2notion/SKILL.md` | This file. |
| `skills/nostr2notion/package.json` | Node deps: nostr-tools, ws, @notionhq/client. |
| `skills/nostr2notion/bridge.js` | Bridge v1.1: live + backfill (windows + EOSE), dedupe by Event ID, queue + 429 retry, title/body. |
| `scripts/run-nostr2notion-bridge.sh` | Run bridge locally or `--vps` inside OpenClaw container. |

## Optional: Notion → Nostr

To publish a Nostr note when a Notion page is updated, you would need either:

- A Notion webhook (if available) calling a small HTTP server that publishes to Nostr, or
- Polling the Notion API and diffing; on change, sign and publish an event (requires a Nostr private key in env). Not included in v1.
