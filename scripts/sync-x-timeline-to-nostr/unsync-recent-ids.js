#!/usr/bin/env node
/**
 * Remove from .twitter-nostr-synced-ids the tweet IDs that are YOUR tweets from the last N days,
 * so the next sync run will re-publish them to Nostr (e.g. after they were deleted by kind-5 or never synced).
 *
 * Usage: node unsync-recent-ids.js [--days=7]
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

function log(msg) {
  console.error(`[${new Date().toISOString()}] ${msg}`);
}

function fetchWhoami(env) {
  const out = execSync('xurl whoami', { encoding: 'utf8', env });
  const j = JSON.parse(out);
  return j?.data?.id || null;
}

function fetchTimeline(env, n) {
  const out = execSync(`xurl timeline -n ${n}`, { encoding: 'utf8', env });
  const j = JSON.parse(out);
  if (!j.data || !Array.isArray(j.data)) return [];
  return j.data;
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
  log(`Fetching whoami and timeline (-n 100, X API max)...`);
  const myXId = fetchWhoami(env);
  if (!myXId) {
    log('Could not get whoami');
    process.exit(1);
  }
  const timeline = fetchTimeline(env, 100);
  const since = Math.floor(Date.now() / 1000) - DAYS * 86400;
  const myRecentIds = [];
  for (const t of timeline) {
    if (t.author_id !== myXId || !t.id) continue;
    const ts = t.created_at
      ? (typeof t.created_at === 'string' ? Math.floor(new Date(t.created_at).getTime() / 1000) : parseInt(t.created_at, 10))
      : 0;
    if (ts >= since) myRecentIds.push(String(t.id));
  }
  log(`Your tweets in last ${DAYS} days (from timeline): ${myRecentIds.length}`);

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
