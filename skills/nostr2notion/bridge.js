#!/usr/bin/env node
/**
 * Nostr → Notion bridge (v1.1).
 * - Live: subscribes to relays and creates a Notion page for each matching event.
 * - Backfill: iterates time windows (since/until), waits for EOSE, dedupes, then writes.
 *
 * Env: NOTION_API_KEY, NOTION_DATABASE_ID, NOSTR_RELAYS (required)
 *      Loaded from process.env or from .env in this directory (if dotenv is present).
 *      NOSTR_KINDS, NOSTR_PUBKEYS, NOSTR_HASHTAGS (optional filters)
 *      NOTION_TITLE_PROPERTY, NOTION_EVENT_ID_PROPERTY (optional)
 *      NOTION_NOSTR_URI_PROPERTY (optional: URL column, e.g. "Nostr URI" → https://njump.me/<id>)
 *      BACKFILL=1, BACKFILL_CHUNK_DAYS=7, BACKFILL_START_UNTIL (optional)
 *      NOTION_CONCURRENCY=1, NOTION_RETRY_AFTER_429_MS=60000 (optional)
 */

import "dotenv/config";
import { SimplePool } from "nostr-tools";
import { Client } from "@notionhq/client";

const NOTION_API_KEY = process.env.NOTION_API_KEY;
const NOTION_DATABASE_ID = process.env.NOTION_DATABASE_ID;
const NOTION_TITLE_PROPERTY = process.env.NOTION_TITLE_PROPERTY || "Title";
/** Property used for dedupe (must exist in DB as rich_text). */
const NOTION_EVENT_ID_PROPERTY = process.env.NOTION_EVENT_ID_PROPERTY || "Event ID";
/** Optional: URL property for Nostr link (e.g. "Nostr URI"). If set, writes https://njump.me/<event_id>. */
const NOTION_NOSTR_URI_PROPERTY = process.env.NOTION_NOSTR_URI_PROPERTY || "";
const NOSTR_RELAYS = (process.env.NOSTR_RELAYS || "").split(",").map((r) => r.trim()).filter(Boolean);
const NOSTR_KINDS = (process.env.NOSTR_KINDS || "1").split(",").map((k) => parseInt(k.trim(), 10)).filter((n) => !Number.isNaN(n));
const NOSTR_PUBKEYS = (process.env.NOSTR_PUBKEYS || "").split(",").map((p) => p.trim()).filter(Boolean);
const NOSTR_HASHTAGS = (process.env.NOSTR_HASHTAGS || "").split(",").map((t) => t.trim().replace(/^#/, "")).filter(Boolean);

const BACKFILL = process.env.BACKFILL === "1" || process.env.BACKFILL === "true";
const BACKFILL_CHUNK_DAYS = Math.max(1, parseInt(process.env.BACKFILL_CHUNK_DAYS || "7", 10));
const BACKFILL_START_UNTIL = process.env.BACKFILL_START_UNTIL ? parseInt(process.env.BACKFILL_START_UNTIL, 10) : null;
/** Set to 0 to omit `until` from the REQ filter (some relays reply "could not parse command" if they don't support until). */
const BACKFILL_USE_UNTIL = process.env.BACKFILL_USE_UNTIL !== "0";

const NOTION_CONCURRENCY = Math.min(5, Math.max(1, parseInt(process.env.NOTION_CONCURRENCY || "1", 10)));
const NOTION_RETRY_AFTER_429_MS = parseInt(process.env.NOTION_RETRY_AFTER_429_MS || "60000", 10);

if (!NOTION_API_KEY || !NOTION_DATABASE_ID) {
  console.error("Missing NOTION_API_KEY or NOTION_DATABASE_ID");
  process.exit(1);
}
if (NOSTR_RELAYS.length === 0) {
  console.error("Missing NOSTR_RELAYS (comma-separated relay URLs)");
  process.exit(1);
}

const notion = new Client({ auth: NOTION_API_KEY });
const pool = new SimplePool();

function buildFilter(overrides = {}) {
  const filter = { kinds: NOSTR_KINDS.length ? NOSTR_KINDS : [1], ...overrides };
  if (NOSTR_PUBKEYS.length) filter.authors = NOSTR_PUBKEYS;
  if (NOSTR_HASHTAGS.length) filter["#t"] = NOSTR_HASHTAGS;
  return filter;
}

function truncate(str, max = 2000) {
  if (typeof str !== "string") return "";
  return str.length <= max ? str : str.slice(0, max) + "...";
}

/** Title: first ~80 chars of content, or fallback `${kind} ${id.slice(0,8)} @ ${date}` */
function titleFor(ev) {
  const content = (ev.content || "").trim().replace(/\s+/g, " ");
  if (content.length) return truncate(content, 80);
  const date = new Date(ev.created_at * 1000).toISOString().slice(0, 10);
  return `${ev.kind} ${ev.id.slice(0, 8)} @ ${date}`;
}

/** Body: full content + metadata */
function bodyFor(ev, relay = "") {
  const meta = [`id: ${ev.id}`, `created_at: ${ev.created_at}`, `kind: ${ev.kind}`, `pubkey: ${ev.pubkey.slice(0, 16)}…`];
  if (relay) meta.push(`relay: ${relay}`);
  if (ev.tags && ev.tags.length) meta.push(`tags: ${JSON.stringify(ev.tags)}`);
  return `${(ev.content || "(no content)").trim()}\n\n---\n${meta.join("\n")}`;
}

/** Check if a page with this Event ID already exists (dedupe). */
async function notionPageExistsByEventId(eventId) {
  try {
    const res = await notion.databases.query({
      database_id: NOTION_DATABASE_ID,
      filter: {
        property: NOTION_EVENT_ID_PROPERTY,
        rich_text: { equals: eventId },
      },
      page_size: 1,
    });
    return res.results.length > 0;
  } catch (e) {
    if (e.code === "object_not_found" || e.message?.includes("property")) {
      console.warn(`Notion: property "${NOTION_EVENT_ID_PROPERTY}" may not exist; add a rich_text column for dedupe.`);
    }
    return false;
  }
}

/** Create one page; on 429, sleep and retry once. */
async function createNotionPage(ev, relay = "") {
  const eventId = ev.id;
  const title = titleFor(ev);
  const body = bodyFor(ev, relay);

  const doCreate = async () => {
    const properties = {
      [NOTION_TITLE_PROPERTY]: {
        title: [{ type: "text", text: { content: truncate(title, 100) } }],
      },
      [NOTION_EVENT_ID_PROPERTY]: {
        rich_text: [{ type: "text", text: { content: eventId } }],
      },
    };
    if (NOTION_NOSTR_URI_PROPERTY) {
      properties[NOTION_NOSTR_URI_PROPERTY] = {
        url: `https://njump.me/${eventId}`,
      };
    }
    return await notion.pages.create({
      parent: { database_id: NOTION_DATABASE_ID },
      properties,
      children: [
        {
          object: "block",
          type: "paragraph",
          paragraph: {
            rich_text: [{ type: "text", text: { content: truncate(body, 2000) } }],
          },
        },
      ],
    });
  };

  try {
    await doCreate();
    console.log("Notion page created for", ev.id.slice(0, 12));
  } catch (err) {
    if (err.code === 429 || err.status === 429) {
      console.warn("Notion rate limit (429), waiting", NOTION_RETRY_AFTER_429_MS, "ms...");
      await new Promise((r) => setTimeout(r, NOTION_RETRY_AFTER_429_MS));
      try {
        await doCreate();
        console.log("Notion page created for", ev.id.slice(0, 12), "(after retry)");
      } catch (e2) {
        console.error("Notion create failed after retry:", e2.message);
      }
    } else {
      console.error("Notion create failed:", err.message);
    }
  }
}

/** Process events through a queue (concurrency 1–N). */
const writeQueue = [];
let running = 0;

async function enqueue(ev, relay = "") {
  return new Promise((resolve) => {
    writeQueue.push({ ev, relay, resolve });
    pump();
  });
}

async function pump() {
  if (running >= NOTION_CONCURRENCY || writeQueue.length === 0) return;
  const { ev, relay, resolve } = writeQueue.shift();
  running++;
  const exists = await notionPageExistsByEventId(ev.id);
  if (exists) {
    console.log("Skip duplicate", ev.id.slice(0, 12));
    running--;
    resolve();
    pump();
    return;
  }
  await createNotionPage(ev, relay);
  running--;
  resolve();
  pump();
}

// ---------- Live mode ----------
function runLive() {
  const filter = buildFilter();
  console.log("[live] Subscribing to", NOSTR_RELAYS.length, "relays, filter", JSON.stringify(filter));

  const sub = pool.subscribeMany(
    NOSTR_RELAYS,
    filter,
    {
      onevent(ev) {
        enqueue(ev);
      },
    }
  );

  process.on("SIGINT", () => {
    sub.close();
    pool.close();
    process.exit(0);
  });
}

// ---------- Backfill mode: time windows + EOSE ----------
function runBackfill() {
  const chunkSeconds = BACKFILL_CHUNK_DAYS * 86400;
  let until = BACKFILL_START_UNTIL != null && BACKFILL_START_UNTIL > 0 ? BACKFILL_START_UNTIL : Math.floor(Date.now() / 1000);
  let totalCreated = 0;

  function nextWindow() {
    const since = Math.max(0, until - chunkSeconds);
    const filter = buildFilter({ since, ...(BACKFILL_USE_UNTIL ? { until } : {}) });
    return { since, until, filter };
  }

  async function processWindow({ since, until, filter }) {
    return new Promise((resolve) => {
      const collected = [];
      let eoseCount = 0;
      const relayCount = NOSTR_RELAYS.length;

      const sub = pool.subscribeMany(
        NOSTR_RELAYS,
        filter,
        {
          onevent(ev) {
            collected.push(ev);
          },
          oneose() {
            eoseCount++;
            if (eoseCount >= relayCount) {
              sub.close();
              resolve(collected);
            }
          },
        }
      );

      // Fallback: if no EOSE after 30s, assume window done
      setTimeout(() => {
        if (eoseCount < relayCount) {
          try { sub.close(); } catch (_) {}
          resolve(collected);
        }
      }, 30000);
    });
  }

  (async () => {
    console.log("[backfill] BACKFILL_CHUNK_DAYS=", BACKFILL_CHUNK_DAYS, "BACKFILL_START_UNTIL=", BACKFILL_START_UNTIL ?? "now", "BACKFILL_USE_UNTIL=", BACKFILL_USE_UNTIL);

    while (true) {
      const win = nextWindow();
      if (win.until <= 0) break;
      const sinceDate = new Date(win.since * 1000).toISOString().slice(0, 10);
      const untilDate = new Date(win.until * 1000).toISOString().slice(0, 10);
      console.log("[backfill] window", sinceDate, "→", untilDate);

      const batch = await processWindow(win);
      const seen = new Set();
      const deduped = batch.filter((ev) => {
        if (seen.has(ev.id)) return false;
        seen.add(ev.id);
        return true;
      });

      for (const ev of deduped) {
        await enqueue(ev);
      }
      totalCreated += deduped.length;
      console.log("[backfill] got", batch.length, "events, deduped", deduped.length, "total so far", totalCreated);

      until = win.since;
      if (until <= 0) break;
    }

    console.log("[backfill] done. Flushing queue...");
    while (writeQueue.length > 0 || running > 0) {
      await new Promise((r) => setTimeout(r, 200));
    }
    try { pool.close(); } catch (_) {}
    process.exit(0);
  })().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}

if (BACKFILL) {
  runBackfill();
} else {
  runLive();
}
