#!/usr/bin/env node
/**
 * Live sync: fetch YOUR tweets only via X API GET /2/users/{id}/tweets (not the home timeline).
 * Publishes to: your relays (bridge + nostr.tagomago.me) + public relays (damus, nostr.land, etc.)
 *
 * Usage: node sync.js [--dry-run]
 * Env: NOSTR_DAMUS_PRIVATE_HEX_KEY, NOSTR_BRIDGE_RELAY, NOSTR_TARGET_RELAY,
 *       NOSTR_PUBLIC_RELAYS, HOME=/data for xurl,
 *       XURL_USER_TWEETS_LIMIT (default 100, max ~3200 with pagination; API max 100 per request)
 */

import { execSync } from 'child_process';
import { readFileSync, writeFileSync, mkdirSync } from 'fs';
import { dirname } from 'path';
import { fileURLToPath } from 'url';
import { finalizeEvent } from 'nostr-tools/pure';
import { SimplePool } from 'nostr-tools';

const __dirname = dirname(fileURLToPath(import.meta.url));

const BRIDGE_RELAY = process.env.NOSTR_BRIDGE_RELAY || 'wss://bridge.tagomago.me';
const TARGET_RELAY = process.env.NOSTR_TARGET_RELAY || 'wss://nostr.tagomago.me';
// Public relays so others see your notes; your relays (bridge + target) keep your copy
const PUBLIC_RELAYS_STR = process.env.NOSTR_PUBLIC_RELAYS || 'wss://relay.damus.io,wss://nostr.land,wss://nos.lol,wss://relay.nostr.band';
const ALL_RELAYS = [
  BRIDGE_RELAY,
  TARGET_RELAY,
  ...PUBLIC_RELAYS_STR.split(',').map((r) => r.trim()).filter(Boolean),
];
const SYNCED_IDS_PATH = process.env.TWITTER_NOSTR_SYNCED_IDS || '/data/.twitter-nostr-synced-ids';
const USER_TWEETS_LIMIT = parseInt(
  process.env.XURL_USER_TWEETS_LIMIT || process.env.XURL_TIMELINE_LIMIT || '100',
  10
);
const dryRun = process.argv.includes('--dry-run');

function log(msg) {
  console.error(`[${new Date().toISOString()}] ${msg}`);
}

function hexToBytes(hex) {
  const b = Buffer.from(hex.replace(/^0x/, ''), 'hex');
  if (b.length !== 32) throw new Error('Private key must be 32 bytes (64 hex chars)');
  return new Uint8Array(b);
}

function loadSyncedIds() {
  try {
    const s = readFileSync(SYNCED_IDS_PATH, 'utf8');
    return new Set(s.trim().split('\n').filter(Boolean));
  } catch {
    return new Set();
  }
}

function saveSyncedIds(ids) {
  mkdirSync(dirname(SYNCED_IDS_PATH), { recursive: true });
  writeFileSync(SYNCED_IDS_PATH, [...ids].sort().join('\n') + '\n', 'utf8');
}

function fetchWhoami(env) {
  const out = execSync('xurl whoami', { encoding: 'utf8', env });
  const j = JSON.parse(out);
  return j?.data?.id || null;
}

/** X API v2: only tweets composed by this user (not home timeline). Paginates up to USER_TWEETS_LIMIT. */
function fetchMyTweets(env, myXId, maxTotal) {
  const tweets = [];
  let paginationToken = '';
  const cap = Math.min(Math.max(1, maxTotal), 3200);
  while (tweets.length < cap) {
    const pageSize = Math.min(100, cap - tweets.length);
    let path = `/2/users/${myXId}/tweets?max_results=${pageSize}&tweet.fields=created_at,author_id`;
    if (paginationToken) path += `&pagination_token=${encodeURIComponent(paginationToken)}`;
    const out = execSync(`xurl ${JSON.stringify(path)}`, { encoding: 'utf8', env });
    const j = JSON.parse(out);
    if (j.errors && j.errors.length) {
      throw new Error(j.errors.map((e) => e.detail || e.message || JSON.stringify(e)).join('; '));
    }
    if (!j.data || !Array.isArray(j.data) || j.data.length === 0) break;
    tweets.push(...j.data);
    paginationToken = j.meta?.next_token;
    if (!paginationToken) break;
  }
  return tweets;
}

async function main() {
  const privHex = process.env.NOSTR_DAMUS_PRIVATE_HEX_KEY || process.env.NOSTR_PRIVATE_KEY;
  if (!privHex) {
    log('Missing NOSTR_DAMUS_PRIVATE_HEX_KEY or NOSTR_PRIVATE_KEY');
    process.exit(1);
  }

  const env = { ...process.env, HOME: process.env.HOME || '/data' };
  let myXId;
  try {
    myXId = fetchWhoami(env);
  } catch (e) {
    log('xurl whoami failed: ' + e.message);
    process.exit(1);
  }
  if (!myXId) {
    log('Could not get authenticated user id from xurl whoami');
    process.exit(1);
  }

  let timeline;
  try {
    timeline = fetchMyTweets(env, myXId, USER_TWEETS_LIMIT);
  } catch (e) {
    log('xurl /2/users/.../tweets failed: ' + e.message);
    process.exit(1);
  }

  if (timeline.length === 0) {
    log('No tweets returned for your user (GET /2/users/{id}/tweets)');
    return;
  }

  // Defense in depth: API should only return your tweets
  timeline = timeline.filter((t) => !t.author_id || String(t.author_id) === String(myXId));
  if (timeline.length === 0) {
    log('No tweets after author filter. Nothing to sync.');
    return;
  }

  const syncedIds = loadSyncedIds();
  const sk = hexToBytes(privHex);
  const pool = new SimplePool();
  const relayUrls = ALL_RELAYS;
  let published = 0;

  // Process newest first (API returns reverse chronological)
  for (const tweet of timeline) {
    const id = tweet.id;
    if (!id || syncedIds.has(id)) continue;

    const content = typeof tweet.text === 'string' ? tweet.text : '';
    const created_at = tweet.created_at
      ? (typeof tweet.created_at === 'string'
          ? Math.floor(new Date(tweet.created_at).getTime() / 1000)
          : parseInt(tweet.created_at, 10))
      : Math.floor(Date.now() / 1000);

    const eventTemplate = {
      kind: 1,
      created_at,
      tags: [['r', `https://twitter.com/i/status/${id}`]],
      content,
    };

    if (dryRun) {
      log(`[dry-run] would publish tweet ${id}: ${content.slice(0, 50)}...`);
      syncedIds.add(id);
      published++;
      continue;
    }

    try {
      const signed = finalizeEvent(eventTemplate, sk);
      await pool.publish(relayUrls, signed);
      syncedIds.add(id);
      published++;
      log(`Published tweet ${id}`);
    } catch (e) {
      log(`Failed to publish ${id}: ${e.message}`);
    }
  }

  try {
    pool.close();
  } catch (e) {
    log(`Pool close: ${e.message}`);
  }
  if (published > 0 && !dryRun) {
    try {
      saveSyncedIds(syncedIds);
    } catch (e) {
      log(`Save synced ids: ${e.message}`);
    }
  }
  log(`Done. New tweets synced: ${published}`);
}

// Exit 0 on error so the shell script still runs republish (bridge → target relay)
process.on('unhandledRejection', (e) => {
  log(e && (e.message || e));
  process.exit(0);
});
main().catch((e) => {
  log(e.message || e);
  process.exit(0);
});
