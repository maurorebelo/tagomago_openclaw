#!/usr/bin/env node
/**
 * Remove from .twitter-nostr-synced-ids the tweet IDs that are YOUR tweets from the last N days,
 * so the next sync run will re-publish them to Nostr (e.g. after they were deleted by kind-5 or never synced).
 *
 * Usage: node unsync-recent-ids.js [--days=7]
 *        node unsync-recent-ids.js --all   (remove ALL your tweet IDs from last ~500 user tweets, so sync re-publishes; may duplicate some on Nostr)
 * Env: HOME=/data, PATH with /data/bin first for xurl wrapper.
 */
import { execSync } from 'child_process';
import { readFileSync, writeFileSync, mkdirSync } from 'fs';
import { dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SYNCED_IDS_PATH = process.env.TWITTER_NOSTR_SYNCED_IDS || '/data/.twitter-nostr-synced-ids';
const daysArg = process.argv.find((a) => a.startsWith('--days='));
const DAYS = daysArg ? parseInt(daysArg.split('=')[1], 10) : 7;
const ALL_IN_TIMELINE = process.argv.includes('--all');

function log(msg) {
  console.error(`[${new Date().toISOString()}] ${msg}`);
}

function fetchWhoami(env) {
  const out = execSync('xurl whoami', { encoding: 'utf8', env });
  const j = JSON.parse(out);
  return j?.data?.id || null;
}

/** GET /2/users/{id}/tweets — only your posts (not home timeline). */
function fetchMyTweets(env, myXId, maxTotal) {
  const tweets = [];
  let paginationToken = '';
  const cap = Math.min(Math.max(1, maxTotal), 800);
  while (tweets.length < cap) {
    const pageSize = Math.min(100, cap - tweets.length);
    let path = `/2/users/${myXId}/tweets?max_results=${pageSize}&tweet.fields=created_at,author_id`;
    if (paginationToken) path += `&pagination_token=${encodeURIComponent(paginationToken)}`;
    const out = execSync(`xurl ${JSON.stringify(path)}`, { encoding: 'utf8', env });
    const j = JSON.parse(out);
    if (!j.data || !Array.isArray(j.data) || j.data.length === 0) break;
    tweets.push(...j.data);
    paginationToken = j.meta?.next_token;
    if (!paginationToken) break;
  }
  return tweets;
}

function loadSyncedIds() {
  try {
    const s = readFileSync(SYNCED_IDS_PATH, 'utf8');
    return new Set(s.trim().split('\n').filter(Boolean));
  } catch {
    return new Set();
  }
}

function main() {
  const env = { ...process.env, HOME: process.env.HOME || '/data' };
  log(`Fetching whoami and your tweets (GET /2/users/{id}/tweets, up to 800)...`);
  const myXId = fetchWhoami(env);
  if (!myXId) {
    log('Could not get whoami');
    process.exit(1);
  }
  const timeline = fetchMyTweets(env, myXId, ALL_IN_TIMELINE ? 500 : 800);
  const since = Math.floor(Date.now() / 1000) - DAYS * 86400;
  const myRecentIds = [];
  for (const t of timeline) {
    if (!t.id || (t.author_id != null && String(t.author_id) !== String(myXId))) continue;
    if (ALL_IN_TIMELINE) {
      myRecentIds.push(String(t.id));
    } else {
      const ts = t.created_at
        ? (typeof t.created_at === 'string' ? Math.floor(new Date(t.created_at).getTime() / 1000) : parseInt(t.created_at, 10))
        : 0;
      if (ts >= since) myRecentIds.push(String(t.id));
    }
  }
  log(ALL_IN_TIMELINE ? `Your tweets (fetched): ${myRecentIds.length}` : `Your tweets in last ${DAYS} days (from fetch): ${myRecentIds.length}`);

  const synced = loadSyncedIds();
  const toRemove = myRecentIds.filter((id) => synced.has(id));
  if (toRemove.length === 0) {
    log('None of those IDs are in synced-ids; nothing to remove. Run sync to publish any that are missing.');
    return;
  }
  toRemove.forEach((id) => synced.delete(id));
  mkdirSync(dirname(SYNCED_IDS_PATH), { recursive: true });
  writeFileSync(SYNCED_IDS_PATH, [...synced].sort().join('\n') + '\n', 'utf8');
  log(`Removed ${toRemove.length} IDs from synced-ids. Next sync will re-publish them.`);
  log(`Ids: ${toRemove.slice(0, 15).join(', ')}${toRemove.length > 15 ? ' ...' : ''}`);
}

main();
