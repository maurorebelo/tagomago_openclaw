#!/usr/bin/env node
/**
 * Import tweets from Twitter archive (tweets.js) into Nostr relays.
 *
 * Usage:
 *   node import.js [--dry-run] [--limit N] [--skip-retweets]
 *
 * Env (required unless --dry-run):
 *   NOSTR_PRIVATE_HEX_KEY   signing key in hex
 *
 * Env (optional):
 *   NOSTR_BRIDGE_RELAY      default: wss://bridge.tagomago.me
 *   NOSTR_TARGET_RELAY      default: wss://nostr.tagomago.me
 *   NOSTR_NIP96_URL         NIP-96 server info URL for media upload
 *                           default: https://nostr.tagomago.me/.well-known/nostr/nip96.json
 *
 * Input:
 *   ../input/tweets.js            extracted from Twitter ZIP archive
 *   ../input/tweets_media/        optional — media files from ZIP
 *
 * State:
 *   ../state/imported-ids.json    tracks imported tweet IDs (never re-imported)
 */

import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'fs';
import { execSync } from 'child_process';
import { dirname, join, basename } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');

const TWEETS_JS    = join(ROOT, 'input', 'tweets.js');
const STATE_FILE   = join(ROOT, 'state', 'imported-ids.json');
const MEDIA_DIR    = join(ROOT, 'input', 'tweets_media');

const BRIDGE    = process.env.NOSTR_BRIDGE_RELAY  || 'wss://bridge.tagomago.me';
const TARGET    = process.env.NOSTR_TARGET_RELAY  || 'wss://nostr.tagomago.me';
const NIP96_URL = process.env.NOSTR_NIP96_URL     || 'https://nostr.tagomago.me/.well-known/nostr/nip96.json';
const PRIVKEY   = process.env.NOSTR_PRIVATE_HEX_KEY;

const DRY_RUN       = process.argv.includes('--dry-run');
const SKIP_RETWEETS = process.argv.includes('--skip-retweets');
const LIMIT = (() => {
  const i = process.argv.indexOf('--limit');
  return i >= 0 ? parseInt(process.argv[i + 1], 10) : Infinity;
})();

if (!PRIVKEY && !DRY_RUN) {
  console.error('Error: NOSTR_PRIVATE_HEX_KEY is required (or use --dry-run)');
  process.exit(1);
}

// ── Parse tweets.js ────────────────────────────────────────────────────────

const raw = readFileSync(TWEETS_JS, 'utf8');
// Strip the window.YTD.tweets.partN = wrapper
const json = raw.replace(/^window\.YTD\.tweets\.part\d+\s*=\s*/, '');
const tweets = JSON.parse(json).map(t => t.tweet);
console.log(`Loaded ${tweets.length} tweets from tweets.js`);

// ── Load state ─────────────────────────────────────────────────────────────

mkdirSync(join(ROOT, 'state'), { recursive: true });
let state = { imported: [], skipped_retweets: [] };
if (existsSync(STATE_FILE)) {
  state = { ...state, ...JSON.parse(readFileSync(STATE_FILE, 'utf8')) };
}
const importedSet = new Set(state.imported);
const skippedSet  = new Set(state.skipped_retweets);

// ── Filter & sort ──────────────────────────────────────────────────────────

const toProcess = tweets
  .filter(t => !importedSet.has(t.id_str) && !skippedSet.has(t.id_str))
  .sort((a, b) => new Date(a.created_at) - new Date(b.created_at));

console.log(`To process: ${toProcess.length} (${importedSet.size} imported, ${skippedSet.size} skipped)`);

// ── NIP-96 media upload ────────────────────────────────────────────────────

let nip96ApiUrl = null;

async function getNip96ApiUrl() {
  if (nip96ApiUrl) return nip96ApiUrl;
  try {
    const res = await fetch(NIP96_URL);
    const info = await res.json();
    nip96ApiUrl = info.api_url;
    return nip96ApiUrl;
  } catch {
    return null;
  }
}

async function uploadMedia(filePath) {
  const apiUrl = await getNip96ApiUrl();
  if (!apiUrl) return null;

  // Build NIP-98 auth event (kind 27235)
  let authEvent;
  try {
    authEvent = execSync(
      `nak event -k 27235 --tag u=${apiUrl} --tag method=POST --sec ${PRIVKEY}`,
      { encoding: 'utf8' }
    ).trim();
  } catch {
    return null;
  }
  const authBase64 = Buffer.from(authEvent).toString('base64');

  try {
    const form = new FormData();
    const fileData = readFileSync(filePath);
    form.append('file', new Blob([fileData]), basename(filePath));

    const res = await fetch(apiUrl, {
      method: 'POST',
      headers: { Authorization: `Nostr ${authBase64}` },
      body: form,
    });

    const data = await res.json();
    // NIP-96 response contains a nip94_event with url tag
    return data?.nip94_event?.tags?.find(t => t[0] === 'url')?.[1] ?? null;
  } catch {
    return null;
  }
}

// ── Main import loop ───────────────────────────────────────────────────────

let imported = 0;
let skipped  = 0;
let errors   = 0;

function saveState() {
  state.imported           = [...importedSet];
  state.skipped_retweets   = [...skippedSet];
  writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
}

for (const tweet of toProcess) {
  if (imported >= LIMIT) break;

  const isRetweet = (tweet.full_text || tweet.text || '').startsWith('RT @');

  if (isRetweet && SKIP_RETWEETS) {
    skippedSet.add(tweet.id_str);
    skipped++;
    continue;
  }

  const created_at = Math.floor(new Date(tweet.created_at).getTime() / 1000);
  let content = tweet.full_text || tweet.text || '';

  // ── Handle media ─────────────────────────────────────────────────────────
  const mediaEntities = [
    ...(tweet.entities?.media        ?? []),
    ...(tweet.extended_entities?.media ?? []),
  ].filter((m, i, arr) => arr.findIndex(x => x.id_str === m.id_str) === i);

  const uploadedUrls = [];

  for (const m of mediaEntities) {
    const mediaFilename = m.media_url_https.split('/').pop();
    // Twitter archive names media files as: <tweet_id>-<filename>
    const localPath = join(MEDIA_DIR, `${tweet.id_str}-${mediaFilename}`);

    if (!DRY_RUN && existsSync(localPath)) {
      // eslint-disable-next-line no-await-in-loop
      const uploadedUrl = await uploadMedia(localPath);
      if (uploadedUrl) {
        uploadedUrls.push(uploadedUrl);
        content = content.replace(m.url, uploadedUrl);
      } else {
        // Fallback: replace t.co with original Twitter CDN URL
        content = content.replace(m.url, m.media_url_https);
      }
    } else {
      // Replace t.co shortlinks with the original URL
      content = content.replace(m.url, m.media_url_https);
    }
  }

  // ── Build tags ────────────────────────────────────────────────────────────
  // Preserve media as imeta tags when uploaded via NIP-96
  const imetaTags = uploadedUrls.map(u => ['imeta', `url ${u}`]);

  if (DRY_RUN) {
    console.log(`[dry-run] ${tweet.id_str} (${tweet.created_at}): ${content.substring(0, 100)}`);
    imported++;
    continue;
  }

  // ── Sign and publish via nak ──────────────────────────────────────────────
  const eventObj = {
    kind: 1,
    created_at,
    tags: imetaTags,
    content,
  };
  const eventJson = JSON.stringify(eventObj);

  try {
    execSync(
      `echo ${JSON.stringify(eventJson)} | nak event --sec ${PRIVKEY} ${BRIDGE} ${TARGET}`,
      { encoding: 'utf8', timeout: 30_000 }
    );
    importedSet.add(tweet.id_str);
    imported++;

    if (imported % 50 === 0) {
      saveState();
      console.log(`Progress: ${imported} imported, ${errors} errors`);
    }
  } catch (err) {
    errors++;
    console.error(`Failed ${tweet.id_str}: ${err.message.substring(0, 120)}`);
  }
}

saveState();
console.log(`\nDone.`);
console.log(`  Imported:       ${imported}`);
console.log(`  Skipped (RT):   ${skipped}`);
console.log(`  Errors:         ${errors}`);
console.log(`  Total in state: ${importedSet.size + skippedSet.size}`);
