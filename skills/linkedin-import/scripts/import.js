#!/usr/bin/env node
/**
 * Import LinkedIn posts and articles from a data export CSV into Nostr.
 *
 * Usage:
 *   node import.js [--dry-run] [--limit N] [--skip-articles] [--skip-posts]
 *
 * Env (required unless --dry-run):
 *   NOSTR_PRIVATE_HEX_KEY   signing key in hex
 *
 * Env (optional):
 *   NOSTR_BRIDGE_RELAY      default: wss://bridge.tagomago.me
 *   NOSTR_TARGET_RELAY      default: wss://nostr.tagomago.me
 *
 * Input:
 *   ../input/Shares.csv      posts export from LinkedIn
 *   ../input/Articles.csv    articles export (optional)
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

const SHARES_FILE   = join(ROOT, 'input', 'Shares.csv');
const ARTICLES_FILE = join(ROOT, 'input', 'Articles.csv');
const STATE_FILE    = join(ROOT, 'state', 'imported-ids.json');

const BRIDGE  = process.env.NOSTR_BRIDGE_RELAY || 'wss://bridge.tagomago.me';
const TARGET  = process.env.NOSTR_TARGET_RELAY || 'wss://nostr.tagomago.me';
const PRIVKEY = process.env.NOSTR_PRIVATE_HEX_KEY;

const DRY_RUN        = process.argv.includes('--dry-run');
const SKIP_ARTICLES  = process.argv.includes('--skip-articles');
const SKIP_POSTS     = process.argv.includes('--skip-posts');
const LIMIT = (() => {
  const i = process.argv.indexOf('--limit');
  return i >= 0 ? parseInt(process.argv[i + 1], 10) : Infinity;
})();

if (!PRIVKEY && !DRY_RUN) {
  console.error('Error: NOSTR_PRIVATE_HEX_KEY is required (or use --dry-run)');
  process.exit(1);
}

// ── CSV parser (handles quoted fields with embedded commas/newlines) ────────

function parseCSV(text) {
  const rows = [];
  let headers = null;
  let i = 0;

  while (i < text.length) {
    const row = [];
    while (i < text.length && text[i] !== '\n') {
      let field = '';
      if (text[i] === '"') {
        i++; // skip opening quote
        while (i < text.length) {
          if (text[i] === '"' && text[i + 1] === '"') {
            field += '"';
            i += 2;
          } else if (text[i] === '"') {
            i++; // skip closing quote
            break;
          } else {
            field += text[i++];
          }
        }
      } else {
        while (i < text.length && text[i] !== ',' && text[i] !== '\n') {
          field += text[i++];
        }
      }
      row.push(field.trim());
      if (text[i] === ',') i++;
    }
    if (text[i] === '\n') i++;

    if (row.every(f => f === '')) continue; // blank line

    if (!headers) {
      headers = row;
    } else {
      const obj = {};
      headers.forEach((h, idx) => { obj[h] = row[idx] ?? ''; });
      rows.push(obj);
    }
  }
  return rows;
}

function parseDate(str) {
  // LinkedIn dates: "2024-01-15 10:30:00 UTC" or "2024-01-15T10:30:00.000Z"
  if (!str) return null;
  const d = new Date(str.replace(' UTC', 'Z').replace(' ', 'T'));
  if (isNaN(d.getTime())) return null;
  return Math.floor(d.getTime() / 1000);
}

function makeHash(timestamp, text) {
  return createHash('md5').update(`${timestamp}:${text.slice(0, 200)}`).digest('hex');
}

// ── Load state ─────────────────────────────────────────────────────────────

mkdirSync(join(ROOT, 'state'), { recursive: true });
let state = { imported: [] };
if (existsSync(STATE_FILE)) {
  state = { ...state, ...JSON.parse(readFileSync(STATE_FILE, 'utf8')) };
}
const importedSet = new Set(state.imported);

// ── Parse sources ──────────────────────────────────────────────────────────

const items = []; // { created_at, content, id, source }

// Shares (posts)
if (!SKIP_POSTS && existsSync(SHARES_FILE)) {
  const rows = parseCSV(readFileSync(SHARES_FILE, 'utf8'));
  console.log(`Loaded ${rows.length} shares from Shares.csv`);

  for (const row of rows) {
    const text = (row['ShareCommentary'] || '').trim();
    if (!text) continue; // reshare with no comment

    const ts = parseDate(row['Date']);
    if (!ts) continue;

    let content = text;
    const link = (row['ShareLink'] || '').trim();
    if (link && !content.includes(link)) {
      content += `\n\n${link}`;
    }

    const id = makeHash(ts, text);
    if (!importedSet.has(id)) {
      items.push({ created_at: ts, content, id, source: 'post' });
    }
  }
}

// Articles
if (!SKIP_ARTICLES && existsSync(ARTICLES_FILE)) {
  const rows = parseCSV(readFileSync(ARTICLES_FILE, 'utf8'));
  console.log(`Loaded ${rows.length} articles from Articles.csv`);

  for (const row of rows) {
    const title   = (row['Title'] || '').trim();
    const body    = (row['Content'] || row['Body'] || '').trim();
    const url     = (row['Url'] || row['URL'] || '').trim();
    const dateStr = row['PublishedAt'] || row['Published'] || row['Date'] || '';

    if (!title && !body) continue;

    const ts = parseDate(dateStr);
    if (!ts) continue;

    // Compose content: title as first line, body, then URL
    const parts = [];
    if (title) parts.push(title);
    if (body) parts.push(body);
    if (url) parts.push(url);
    const content = parts.join('\n\n');

    const id = makeHash(ts, title + body.slice(0, 100));
    if (!importedSet.has(id)) {
      items.push({ created_at: ts, content, id, source: 'article' });
    }
  }
}

// Sort chronologically (oldest first)
items.sort((a, b) => a.created_at - b.created_at);
console.log(`To process: ${items.length} (${importedSet.size} already imported)`);

// ── Main import loop ───────────────────────────────────────────────────────

let imported = 0;
let errors = 0;

function saveState() {
  state.imported = [...importedSet];
  writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
}

for (const item of items) {
  if (imported >= LIMIT) break;

  if (DRY_RUN) {
    const dt = new Date(item.created_at * 1000).toISOString().slice(0, 10);
    const preview = item.content.replace(/\n/g, ' ').slice(0, 100);
    console.log(`[dry-run] [${item.source}] ${dt}: ${preview}`);
    imported++;
    continue;
  }

  // ── Sign and publish via nak ────────────────────────────────────────────
  const eventObj = {
    kind: 1,
    created_at: item.created_at,
    tags: [],
    content: item.content,
  };
  const eventJson = JSON.stringify(eventObj);

  try {
    execSync(
      `echo ${JSON.stringify(eventJson)} | nak event --sec ${PRIVKEY} ${BRIDGE} ${TARGET}`,
      { encoding: 'utf8', timeout: 30_000 }
    );
    importedSet.add(item.id);
    imported++;

    if (imported % 50 === 0) {
      saveState();
      console.log(`Progress: ${imported} imported, ${errors} errors`);
    }
  } catch (err) {
    errors++;
    const dt = new Date(item.created_at * 1000).toISOString().slice(0, 10);
    console.error(`Failed [${item.source}] ${dt}: ${err.message.slice(0, 100)}`);
  }
}

saveState();
console.log('\nDone.');
console.log(`  Imported:       ${imported}`);
console.log(`  Errors:         ${errors}`);
console.log(`  Total in state: ${importedSet.size}`);
