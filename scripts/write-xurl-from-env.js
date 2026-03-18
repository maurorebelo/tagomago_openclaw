#!/usr/bin/env node
/**
 * Writes /data/.xurl from env vars (no shell expansion).
 * Run in container after deploy so xurl gets correct OAuth 1.0a credentials.
 *
 * Env: X_API_KEY, X_API_KEY_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET
 *      X_BEARER_TOKEN (optional)
 *
 * Usage: node /data/scripts/write-xurl-from-env.js [outputPath]
 *        outputPath defaults to /data/.xurl
 */

const fs = require('fs');
const path = require('path');

function escapeYaml(str) {
  if (str == null || str === '') return '""';
  const s = String(str);
  if (/^[a-zA-Z0-9_-]+$/.test(s)) return s;
  return '"' + s.replace(/\\/g, '\\\\').replace(/"/g, '\\"') + '"';
}

const outPath = process.argv[2] || path.join(process.env.HOME || '/data', '.xurl');
const consumerKey = process.env.X_API_KEY || '';
const consumerSecret = process.env.X_API_KEY_SECRET || '';
const accessToken = process.env.X_ACCESS_TOKEN || '';
const tokenSecret = process.env.X_ACCESS_TOKEN_SECRET || '';
const bearerToken = process.env.X_BEARER_TOKEN || '';

if (!consumerKey || !consumerSecret || !accessToken || !tokenSecret) {
  console.error('Missing env: X_API_KEY, X_API_KEY_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET');
  process.exit(1);
}

const yaml = `apps:
  default:
    client_id: ${escapeYaml(consumerKey)}
    client_secret: ${escapeYaml(consumerSecret)}
    default_user: default
    oauth1_token:
      type: oauth1
      oauth1:
        access_token: ${escapeYaml(accessToken)}
        token_secret: ${escapeYaml(tokenSecret)}
        consumer_key: ${escapeYaml(consumerKey)}
        consumer_secret: ${escapeYaml(consumerSecret)}
${bearerToken ? `    bearer_token:\n      type: bearer\n      bearer: ${escapeYaml(bearerToken)}\n` : ''}default_app: default
`;

const dir = path.dirname(outPath);
if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
fs.writeFileSync(outPath, yaml, 'utf8');

try {
  const stat = fs.statSync(outPath);
  if (process.getuid && process.getuid() === 0 && stat.uid !== 1000) {
    fs.chownSync(outPath, 1000, 1000);
  }
} catch (_) {}

console.log('Wrote', outPath);
