#!/usr/bin/env node
/**
 * Import Facebook posts from a "Download Your Information" JSON export into Nostr.
 *
 * Usage:
 *   node import.js [--dry-run] [--limit N]
 *
 * Env (required unless --dry-run):
 *   NOSTR_PRIVATE_HEX_KEY   signing key in hex
 *
 * Env (optional):
 *   NOSTR_BRIDGE_RELAY      default: wss://bridge.tagomago.me
 *   NOSTR_TARGET_RELAY      default: wss://nostr.tagomago.me
 *
 * Input:
 *   ../input/your_posts.json    extracted from Facebook ZIP
 *
 * State:
 *   ../state/imported-ids.json  tracks imported post hashes (never re-imported)
 */

import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'fs';
import { createHash } from 'crypto';
import { execSync } from 'child_process';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');

const POSTS_FILE = join(ROOT, 'input', 'your_posts.json');
const STATE_FILE = join(ROOT, 'state', 'imported-ids.json');

const BRIDGE  = process.env.NOSTR_BRIDGE_RELAY || 'wss://bridge.tagomago.me';
const TARGET  = process.env.NOSTR_TARGET_RELAY || 'wss://nostr.tagomago.me';
const PRIVKEY = process.env.NOSTR_PRIVATE_HEX_KEY;

const DRY_RUN = process.argv.includes('--dry-run');
const LIMIT = (() => {
  const i = process.argv.indexOf('--limit');
  return i >= 0 ? parseInt(process.argv[i + 1], 10) : Infinity;
})();

if (!PRIVKEY && !DRY_RUN) {
  console.error('Error: NOSTR_PRIVATE_HEX_KEY is required (or use --dry-run)');
  process.exit(1);
}

if (!existsSync(POSTS_FILE)) {
  console.error(`Error: ${POSTS_FILE} not found.`);
  console.error('Extract your_posts.json from the Facebook ZIP into input/');
  process.exit(1);
}

// ── Parse posts ────────────────────────────────────────────────────────────

function fixEncoding(str) {
  // Facebook exports use Latin-1 encoded as UTF-8 in older exports.
  // Attempt to fix the most common case.
  try {
    return Buffer.from(str, 'latin1').toString('utf8');
  } catch {
    return str;
  }
}

function extractText(post) {
  // Handle both array and object forms of data
  const dataArr = Array.isArray(post.data) ? post.data : [];
  for (const item of dataArr) {
    if (item.post && typeof item.post === 'string') {
      return fixEncoding(item.post.trim());
    }
    if (item.update_timestamp) continue; // profile updates, skip
  }
  // Some older formats put text in post.title
  if (post.title && !post.title.includes('updated his') && !post.title.includes('updated her')
      && !post.title.includes('was') && post.title.length > 5) {
    return fixEncoding(post.title.trim());
  }
  return null;
}

function postId(post, text) {
  // Facebook doesn't expose post IDs in the data export.
  // Use timestamp + content hash as a stable identifier.
  const hash = createHash('md5').update(`${post.timestamp}:${text.slice(0, 200)}`).digest('hex');
  return hash;
}

const rawPosts = JSON.parse(readFileSync(POSTS_FILE, 'utf8'));
// The root can be an array of posts directly, or wrapped
const postsArray = Array.isArray(rawPosts) ? rawPosts : [rawPosts];

console.log(`Loaded ${postsArray.length} entries from your_posts.json`);

// ── Load state ─────────────────────────────────────────────────────────────

mkdirSync(join(ROOT, 'state'), { recursive: true });
let state = { imported: [] };
if (existsSync(STATE_FILE)) {
  state = { ...state, ...JSON.parse(readFileSync(STATE_FILE, 'utf8')) };
}
const importedSet = new Set(state.imported);

// ── Filter & sort ──────────────────────────────────────────────────────────

const toProcess = [];
for (const post of postsArray) {
  const text = extractText(post);
  if (!text) continue;                       // no text content
  if (text.length < 2) continue;             // too short to be meaningful

  const id = postId(post, text);
  if (importedSet.has(id)) continue;         // already imported

  toProcess.push({ post, text, id });
}

// Sort chronologically (oldest first)
toProcess.sort((a, b) => a.post.timestamp - b.post.timestamp);
console.log(`To process: ${toProcess.length} (${importedSet.size} already imported)`);

// ── Main import loop ───────────────────────────────────────────────────────

let imported = 0;
let errors = 0;

function saveState() {
  state.imported = [...importedSet];
  writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
}

for (const { post, text, id } of toProcess) {
  if (imported >= LIMIT) break;

  const created_at = post.timestamp;

  if (DRY_RUN) {
    const preview = text.replace(/\n/g, ' ').slice(0, 100);
    const dt = new Date(created_at * 1000).toISOString().slice(0, 10);
    console.log(`[dry-run] ${dt}: ${preview}`);
    imported++;
    continue;
  }

  // ── Sign and publish via nak ────────────────────────────────────────────
  const eventObj = {
    kind: 1,
    created_at,
    tags: [],
    content: text,
  };
  const eventJson = JSON.stringify(eventObj);

  try {
    execSync(
      `echo ${JSON.stringify(eventJson)} | nak event --sec ${PRIVKEY} ${BRIDGE} ${TARGET}`,
      { encoding: 'utf8', timeout: 30_000 }
    );
    importedSet.add(id);
    imported++;

    if (imported % 50 === 0) {
      saveState();
      console.log(`Progress: ${imported} imported, ${errors} errors`);
    }
  } catch (err) {
    errors++;
    console.error(`Failed (${new Date(created_at * 1000).toISOString().slice(0, 10)}): ${err.message.slice(0, 100)}`);
  }
}

saveState();
console.log('\nDone.');
console.log(`  Imported:       ${imported}`);
console.log(`  Errors:         ${errors}`);
console.log(`  Total in state: ${importedSet.size}`);
