#!/usr/bin/env node
/**
 * Live sync: fetch X timeline via xurl, publish new tweets to Nostr bridge.
 * Run inside OpenClaw container (or env with xurl, HOME=/data, NOSTR_DAMUS_*).
 * Schedule 2x/day (e.g. every 12h) for near real-time sync.
 *
 * Usage: node sync.js [--dry-run]
 * Env: NOSTR_DAMUS_PRIVATE_HEX_KEY (or NOSTR_PRIVATE_KEY), NOSTR_BRIDGE_RELAY (default wss://bridge.tagomago.me),
 *       HOME=/data so xurl finds /data/.xurl
 */

import { execSync } from 'child_process';
import { readFileSync, writeFileSync, mkdirSync } from 'fs';
import { dirname } from 'path';
import { fileURLToPath } from 'url';
import { finalizeEvent } from 'nostr-tools/pure';
import { SimplePool } from 'nostr-tools';

const __dirname = dirname(fileURLToPath(import.meta.url));

const BRIDGE_RELAY = process.env.NOSTR_BRIDGE_RELAY || 'wss://bridge.tagomago.me';
const SYNCED_IDS_PATH = process.env.TWITTER_NOSTR_SYNCED_IDS || '/data/.twitter-nostr-synced-ids';
const XURL_LIMIT = parseInt(process.env.XURL_TIMELINE_LIMIT || '100', 10);
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

function fetchTimeline() {
  const env = { ...process.env, HOME: process.env.HOME || '/data' };
  const out = execSync(`xurl timeline -n ${XURL_LIMIT}`, { encoding: 'utf8', env });
  const j = JSON.parse(out);
  if (!j.data || !Array.isArray(j.data)) return [];
  return j.data;
}

async function main() {
  const privHex = process.env.NOSTR_DAMUS_PRIVATE_HEX_KEY || process.env.NOSTR_PRIVATE_KEY;
  if (!privHex) {
    log('Missing NOSTR_DAMUS_PRIVATE_HEX_KEY or NOSTR_PRIVATE_KEY');
    process.exit(1);
  }

  let timeline;
  try {
    timeline = fetchTimeline();
  } catch (e) {
    log('xurl timeline failed: ' + e.message);
    process.exit(1);
  }

  if (timeline.length === 0) {
    log('No tweets in timeline');
    return;
  }

  const syncedIds = loadSyncedIds();
  const sk = hexToBytes(privHex);
  const pool = new SimplePool();
  const relayUrls = [BRIDGE_RELAY];
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

main().catch((e) => {
  log(e.message || e);
  process.exit(1);
});
