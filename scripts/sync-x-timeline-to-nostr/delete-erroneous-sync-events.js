#!/usr/bin/env node
/**
 * Publish NIP-09 (kind 5) deletions for Nostr events that have our pubkey but
 * reference tweets that are NOT ours (erroneous sync). Relays and clients will
 * hide those events.
 *
 * We can only delete events we signed (our pubkey). We cannot delete events
 * that have other people's pubkeys (e.g. republish sent them to relays; only
 * those authors can request deletion).
 *
 * Usage: node delete-erroneous-sync-events.js [--dry-run]
 *        node delete-erroneous-sync-events.js --last-hours=2 [--dry-run]
 *        node delete-erroneous-sync-events.js --since-event-id=<hex> [--dry-run]
 *
 * --last-hours=N       Delete ALL your kind-1 events from the last N hours.
 * --since-event-id=ID Delete this event and ALL your kind-1 with created_at >= its created_at.
 * Without either: use tweet-ID heuristic (only delete events referencing tweets not yours).
 *
 * Env: NOSTR_DAMUS_PUBLIC_HEX_KEY, NOSTR_DAMUS_PRIVATE_HEX_KEY, NOSTR_*_RELAY, HOME=/data for xurl
 */

import { execSync } from 'child_process';
import { fileURLToPath } from 'url';
import { dirname } from 'path';
import { finalizeEvent } from 'nostr-tools/pure';
import { SimplePool } from 'nostr-tools';

const __dirname = dirname(fileURLToPath(import.meta.url));

const BRIDGE_RELAY = process.env.NOSTR_BRIDGE_RELAY || 'wss://bridge.tagomago.me';
const TARGET_RELAY = process.env.NOSTR_TARGET_RELAY || 'wss://nostr.tagomago.me';
const PUBLIC_RELAYS_STR = process.env.NOSTR_PUBLIC_RELAYS || 'wss://relay.damus.io,wss://nostr.land,wss://nos.lol,wss://relay.nostr.band';
const ALL_RELAYS = [
  BRIDGE_RELAY,
  TARGET_RELAY,
  ...PUBLIC_RELAYS_STR.split(',').map((r) => r.trim()).filter(Boolean),
];
const TWITTER_STATUS_PREFIX = 'https://twitter.com/i/status/';
const dryRun = process.argv.includes('--dry-run');
const lastHoursArg = process.argv.find((a) => a.startsWith('--last-hours='));
const lastHours = lastHoursArg ? parseFloat(lastHoursArg.split('=')[1]) : null;
const sinceEventIdArg = process.argv.find((a) => a.startsWith('--since-event-id='));
const sinceEventId = sinceEventIdArg ? sinceEventIdArg.split('=')[1].trim() : null;

function log(msg) {
  console.error(`[${new Date().toISOString()}] ${msg}`);
}

function hexToBytes(hex) {
  const b = Buffer.from(hex.replace(/^0x/, ''), 'hex');
  if (b.length !== 32) throw new Error('Private key must be 32 bytes (64 hex chars)');
  return new Uint8Array(b);
}

function getOurTweetIds(env) {
  const whoamiOut = execSync('xurl whoami', { encoding: 'utf8', env });
  const whoami = JSON.parse(whoamiOut);
  const myXId = whoami?.data?.id;
  if (!myXId) throw new Error('xurl whoami did not return data.id');

  const timelineOut = execSync('xurl timeline -n 800', { encoding: 'utf8', env });
  const timeline = JSON.parse(timelineOut);
  const tweets = timeline?.data || [];
  const ourIds = new Set();
  for (const t of tweets) {
    if (t.author_id === myXId && t.id) ourIds.add(String(t.id));
  }
  return ourIds;
}

function tweetIdFromRTag(tag) {
  if (!Array.isArray(tag) || tag[0] !== 'r') return null;
  const url = tag[1];
  if (typeof url !== 'string' || !url.startsWith(TWITTER_STATUS_PREFIX)) return null;
  const id = url.slice(TWITTER_STATUS_PREFIX.length).split(/[/?]/)[0];
  return id || null;
}

async function fetchEventById(pool, relays, id) {
  return new Promise((resolve) => {
    const out = [];
    const sub = pool.subscribe(relays, { ids: [id], kinds: [1] }, {
      onevent: (ev) => out.push(ev),
      oneose: () => {
        sub.close();
        resolve(out[0] || null);
      },
    });
    setTimeout(() => {
      sub.close();
      resolve(out[0] || null);
    }, 15000);
  });
}

async function fetchOurKind1(pool, pubkey, relays) {
  return new Promise((resolve, reject) => {
    const events = [];
    let done = false;
    const finish = (evs) => {
      if (done) return;
      done = true;
      try {
        sub.close();
      } catch (_) {}
      resolve(evs);
    };
    const sub = pool.subscribe(relays, { kinds: [1], authors: [pubkey] }, {
      onevent: (ev) => events.push(ev),
      oneose: () => finish(events),
      onclose: (reason) => {
        if (!done) finish(events.length ? events : []);
      },
    });
    setTimeout(() => finish(events), 30000);
  });
}

async function main() {
  const pubkey = process.env.NOSTR_DAMUS_PUBLIC_HEX_KEY;
  const privHex = process.env.NOSTR_DAMUS_PRIVATE_HEX_KEY || process.env.NOSTR_PRIVATE_KEY;
  if (!pubkey || !privHex) {
    log('Set NOSTR_DAMUS_PUBLIC_HEX_KEY and NOSTR_DAMUS_PRIVATE_HEX_KEY');
    process.exit(1);
  }

  const env = { ...process.env, HOME: process.env.HOME || '/data' };
  const pool = new SimplePool();

  let toDelete = [];

  if (sinceEventId) {
    log('Mode: delete event ' + sinceEventId.slice(0, 16) + '... and ALL your kind-1 with created_at >= its created_at');
    const ref = await fetchEventById(pool, ALL_RELAYS, sinceEventId);
    if (!ref) {
      log('Event not found: ' + sinceEventId);
      try { pool.close(); } catch (_) {}
      process.exit(1);
    }
    const sinceTs = ref.created_at;
    log('Reference event created_at: ' + sinceTs + ' (' + new Date(sinceTs * 1000).toISOString() + ')');
    const events = await fetchOurKind1(pool, pubkey, ALL_RELAYS);
    for (const ev of events) {
      if (ev.created_at >= sinceTs) toDelete.push(ev.id);
    }
    log('Found ' + events.length + ' kind-1 events; ' + toDelete.length + ' to delete (this event + all after).');
  } else if (lastHours != null && lastHours > 0) {
    const since = Math.floor(Date.now() / 1000) - Math.round(lastHours * 3600);
    log('Mode: delete ALL your kind-1 events from the last ' + lastHours + ' hour(s) (since ' + new Date(since * 1000).toISOString() + ')');
    const events = await fetchOurKind1(pool, pubkey, ALL_RELAYS);
    for (const ev of events) {
      if (ev.created_at >= since) toDelete.push(ev.id);
    }
    log('Found ' + events.length + ' kind-1 events; ' + toDelete.length + ' in time window.');
  } else {
    log('Fetching your tweet IDs from X (whoami + timeline -n 800)...');
    let ourTweetIds;
    try {
      ourTweetIds = getOurTweetIds(env);
    } catch (e) {
      log('Failed to get our tweet IDs: ' + e.message);
      process.exit(1);
    }
    log('Your tweet IDs from timeline: ' + ourTweetIds.size);

    log('Fetching your kind-1 events with Twitter "r" tag from relays...');
    const events = await fetchOurKind1(pool, pubkey, ALL_RELAYS);
    const withR = events.filter((ev) => (ev.tags || []).some((t) => tweetIdFromRTag(t)));
    log('Found ' + withR.length + ' kind-1 events with r tag');

    for (const ev of withR) {
      const tags = ev.tags || [];
      for (const tag of tags) {
        const tweetId = tweetIdFromRTag(tag);
        if (tweetId && !ourTweetIds.has(tweetId)) {
          toDelete.push(ev.id);
          break;
        }
      }
    }
  }

  if (toDelete.length === 0) {
    log('No events to delete.');
    try {
      pool.close();
    } catch (e) {
      log('Pool close: ' + (e && e.message));
    }
    return;
  }

  const unique = [...new Set(toDelete)];
  log('Event IDs to mark as deleted (NIP-09): ' + unique.length);

  if (dryRun) {
    unique.slice(0, 10).forEach((id) => log('  ' + id));
    if (unique.length > 10) log('  ... and ' + (unique.length - 10) + ' more');
    log('Dry-run: not publishing kind-5. Run without --dry-run to publish.');
    try {
      pool.close();
    } catch (e) {
      log('Pool close: ' + (e && e.message));
    }
    process.exit(0);
  }

  const sk = hexToBytes(privHex);
  const CHUNK = 100;
  for (let i = 0; i < unique.length; i += CHUNK) {
    const chunk = unique.slice(i, i + CHUNK);
    const tags = chunk.map((id) => ['e', id]);
    const deletionEvent = finalizeEvent(
      { kind: 5, created_at: Math.floor(Date.now() / 1000), tags, content: 'Erroneous sync: not my tweets. NIP-09 deletion.' },
      sk
    );
    await pool.publish(ALL_RELAYS, deletionEvent);
    log('Published kind-5 deletion for ' + chunk.length + ' events.');
  }

  try {
    pool.close();
  } catch (e) {
    log('Pool close: ' + (e && e.message));
  }
  log('Done. Relays and NIP-09 clients will hide those events.');
}

main().catch((e) => {
  log(e.message || e);
  process.exit(1);
});
