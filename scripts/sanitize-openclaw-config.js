#!/usr/bin/env node
/**
 * Reads OpenClaw config from the container's .openclaw/openclaw.json,
 * redacts secrets, and writes config/openclaw.sanitized.json so the repo
 * reflects dashboard state without committing tokens.
 *
 * Run on the VPS (inside the OpenClaw container or with OPENCLAW_CONFIG
 * pointing at the config file):
 *   node /data/scripts/sanitize-openclaw-config.js
 *
 * Then commit and push config/openclaw.sanitized.json from the repo.
 */

const fs = require('fs');
const path = require('path');

const configPath = process.env.OPENCLAW_CONFIG || path.join(process.cwd(), '.openclaw', 'openclaw.json');
const outPath = process.env.SANITIZED_OUTPUT || path.join(process.cwd(), 'config', 'openclaw.sanitized.json');

const SECRET_KEYS = new Set([
  'botToken', 'apiKey', 'token', 'secret', 'password', 'auth'
]);

function redact(obj, key) {
  if (SECRET_KEYS.has(key)) return '<REDACTED>';
  if (key.toLowerCase().includes('token') || key.toLowerCase().includes('apikey')) return '<REDACTED>';
  return undefined; // no redaction
}

function sanitize(obj) {
  if (obj === null || typeof obj !== 'object') return obj;
  if (Array.isArray(obj)) return obj.map(item => sanitize(item));
  const out = {};
  for (const [k, v] of Object.entries(obj)) {
    const replacement = redact(obj, k);
    out[k] = replacement !== undefined ? replacement : sanitize(v);
  }
  return out;
}

let raw;
try {
  raw = fs.readFileSync(configPath, 'utf8');
} catch (e) {
  console.error('Cannot read config at', configPath, e.message);
  process.exit(1);
}

let config;
try {
  config = JSON.parse(raw);
} catch (e) {
  console.error('Invalid JSON in config', e.message);
  process.exit(1);
}

const sanitized = sanitize(config);
const dir = path.dirname(outPath);
if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
fs.writeFileSync(outPath, JSON.stringify(sanitized, null, 2), 'utf8');
console.log('Wrote', outPath);
