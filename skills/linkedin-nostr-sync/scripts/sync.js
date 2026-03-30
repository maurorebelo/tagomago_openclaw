#!/usr/bin/env node
/**
 * Sync new LinkedIn posts to Nostr.
 *
 * Usage:
 *   node sync.js [--dry-run] [--limit N] [--since <ISO date>]
 *
 * Env:
 *   NOSTR_PRIVATE_HEX_KEY   (or set in config file)
 *   LINKEDIN_CONFIG         path to config file (default: /data/.linkedin)
 *   NOSTR_BRIDGE_RELAY      default: wss://bridge.tagomago.me
 *   NOSTR_TARGET_RELAY      default: wss://nostr.tagomago.me
 */

import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'fs';
import { execSync } from 'child_process';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT       = join(__dirname, '..');
const STATE_FILE = join(ROOT, 'state', 'sync-state.json');
const LOG_FILE   = join(ROOT, 'state', 'sync.log');

const CONFIG_PATH = process.env.LINKEDIN_CONFIG || '/data/.linkedin';
const BRIDGE      = process.env.NOSTR_BRIDGE_RELAY || 'wss://bridge.tagomago.me';
const TARGET      = process.env.NOSTR_TARGET_RELAY  || 'wss://nostr.tagomago.me';

const DRY_RUN = process.argv.includes('--dry-run');
const LIMIT   = (() => { const i = process.argv.indexOf('--limit'); return i >= 0 ? parseInt(process.argv[i+1],10) : Infinity; })();
const SINCE   = (() => { const i = process.argv.indexOf('--since'); return i >= 0 ? new Date(process.argv[i+1]) : null; })();

// ── Config & state ─────────────────────────────────────────────────────────

function loadConfig() {
  if (!existsSync(CONFIG_PATH)) {
    console.error(`Config not found: ${CONFIG_PATH}`);
    console.error('Run: node scripts/auth.js --client-id <ID> --client-secret <SECRET>');
    process.exit(1);
  }
  return JSON.parse(readFileSync(CONFIG_PATH, 'utf8'));
}

function saveConfig(config) {
  writeFileSync(CONFIG_PATH, JSON.stringify(config, null, 2), { mode: 0o600 });
}

mkdirSync(join(ROOT, 'state'), { recursive: true });

let state = { lastSyncAt: null, publishedIds: [] };
if (existsSync(STATE_FILE)) {
  state = { ...state, ...JSON.parse(readFileSync(STATE_FILE, 'utf8')) };
}
const publishedSet = new Set(state.publishedIds);

function saveState() {
  state.publishedIds = [...publishedSet];
  writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
}

function log(msg) {
  const line = `[${new Date().toISOString()}] ${msg}`;
  console.log(line);
  try { writeFileSync(LOG_FILE, line + '\n', { flag: 'a' }); } catch {}
}

// ── LinkedIn API ──────────────────────────────────────────────────────────

async function refreshToken(config) {
  if (!config.refresh_token) {
    log('No refresh token — re-run auth.js to get new tokens');
    process.exit(1);
  }
  const res = await fetch('https://www.linkedin.com/oauth/v2/accessToken', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type:    'refresh_token',
      refresh_token: config.refresh_token,
      client_id:     config.client_id,
      client_secret: config.client_secret,
    }),
  });
  const data = await res.json();
  if (!data.access_token) {
    log('Token refresh failed: ' + JSON.stringify(data));
    log('Re-run: node scripts/auth.js --client-id ... --client-secret ...');
    process.exit(1);
  }
  config.access_token     = data.access_token;
  config.token_expires_at = Math.floor(Date.now() / 1000) + (data.expires_in || 5184000);
  if (data.refresh_token) config.refresh_token = data.refresh_token;
  saveConfig(config);
  log('Token refreshed.');
  return config;
}

async function ensureFreshToken(config) {
  const now     = Math.floor(Date.now() / 1000);
  const expires = config.token_expires_at || 0;
  if (expires - now < 7 * 86400) {
    log('Token expires soon — refreshing...');
    config = await refreshToken(config);
  }
  return config;
}

async function fetchPosts(config, sinceMs) {
  const headers = {
    'Authorization':              `Bearer ${config.access_token}`,
    'LinkedIn-Version':           '202401',
    'X-Restli-Protocol-Version':  '2.0.0',
    'Content-Type':               'application/json',
  };

  let posts = [];
  let start = 0;
  const count = 20;

  while (true) {
    const url = new URL('https://api.linkedin.com/rest/posts');
    url.searchParams.set('author', config.person_id);
    url.searchParams.set('q', 'author');
    url.searchParams.set('count', count);
    url.searchParams.set('start', start);
    url.searchParams.set('sortBy', 'LAST_MODIFIED');

    const res = await fetch(url.toString(), { headers });
    if (!res.ok) {
      const text = await res.text();
      log(`LinkedIn API error ${res.status}: ${text.slice(0, 200)}`);
      break;
    }
    const data = await res.json();
    const elements = data.elements || [];
    if (elements.length === 0) break;

    for (const post of elements) {
      const createdMs = post.created?.time || post.publishedAt || 0;
      // Stop if we've gone past our sync window
      if (sinceMs && createdMs < sinceMs) {
        return posts;
      }
      posts.push(post);
    }

    if (elements.length < count) break;
    start += count;
  }

  return posts;
}

function extractContent(post) {
  // Main text (commentary)
  let text = (post.commentary || '').trim();

  // For article posts, append the article URL
  const article = post.content?.article;
  if (article) {
    const articleUrl = article.source || article.landingPage?.landingPageUrl || '';
    const articleTitle = article.title || '';
    if (articleTitle && !text.includes(articleTitle)) {
      text = text ? `${text}\n\n${articleTitle}` : articleTitle;
    }
    if (articleUrl && !text.includes(articleUrl)) {
      text += `\n\n${articleUrl}`;
    }
  }

  return text.trim();
}

// ── Main ──────────────────────────────────────────────────────────────────

let config = loadConfig();
const PRIVKEY = process.env.NOSTR_PRIVATE_HEX_KEY || config.nostr_private_key;

if (!PRIVKEY && !DRY_RUN) {
  console.error('Error: NOSTR_PRIVATE_HEX_KEY is required (or set nostr_private_key in config)');
  process.exit(1);
}

log(`LinkedIn → Nostr sync starting${DRY_RUN ? ' (dry-run)' : ''}`);
log(`Person: ${config.person_id}`);

config = await ensureFreshToken(config);

// Determine since time
let sinceMs = null;
if (SINCE) {
  sinceMs = SINCE.getTime();
} else if (state.lastSyncAt) {
  // Fetch posts created after last sync (with 1h overlap to avoid gaps)
  sinceMs = new Date(state.lastSyncAt).getTime() - 3600_000;
}

log(`Fetching posts${sinceMs ? ` since ${new Date(sinceMs).toISOString().slice(0,10)}` : ' (all)'}...`);

const posts = await fetchPosts(config, sinceMs);
log(`Fetched ${posts.length} posts from LinkedIn`);

// Filter: public, not already published, has content
const toPublish = posts.filter(post => {
  if (post.visibility !== 'PUBLIC') return false;
  const postId = post.id;
  if (publishedSet.has(postId)) return false;
  const content = extractContent(post);
  return content.length > 0;
});

log(`To publish: ${toPublish.length} (${posts.length - toPublish.length} skipped)`);

let published = 0;
let errors    = 0;

for (const post of toPublish) {
  if (published >= LIMIT) break;

  const content    = extractContent(post);
  const created_at = Math.floor((post.created?.time || Date.now()) / 1000);
  const postId     = post.id;
  const dt         = new Date(created_at * 1000).toISOString().slice(0, 10);

  if (DRY_RUN) {
    console.log(`[dry-run] ${dt}: ${content.replace(/\n/g, ' ').slice(0, 120)}`);
    published++;
    continue;
  }

  const eventObj = { kind: 1, created_at, tags: [], content };
  const eventJson = JSON.stringify(eventObj);

  try {
    execSync(
      `echo ${JSON.stringify(eventJson)} | nak event --sec ${PRIVKEY} ${BRIDGE} ${TARGET}`,
      { encoding: 'utf8', timeout: 30_000 }
    );
    publishedSet.add(postId);
    published++;
    log(`Published: ${dt} — ${content.slice(0, 80)}`);
  } catch (err) {
    errors++;
    log(`Failed ${postId}: ${err.message.slice(0, 100)}`);
  }
}

if (!DRY_RUN) {
  state.lastSyncAt = new Date().toISOString();
  saveState();
}

log(`Done: ${published} published, ${errors} errors`);
