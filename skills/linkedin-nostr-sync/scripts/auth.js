#!/usr/bin/env node
/**
 * LinkedIn OAuth 2.0 setup (one-time).
 *
 * Usage:
 *   node auth.js --client-id <ID> --client-secret <SECRET> [--port 3000]
 *
 * Opens an authorization URL, starts a local HTTP server on --port to capture
 * the callback, exchanges the code for tokens, and saves to LINKEDIN_CONFIG
 * (default: /data/.linkedin).
 *
 * If running on a remote VPS, first forward the port:
 *   ssh -L 3000:localhost:3000 hostinger-vps
 * Then run this script inside the container and open the URL on your Mac.
 */

import { createServer } from 'http';
import { writeFileSync, readFileSync, existsSync } from 'fs';
import { createHash, randomBytes } from 'crypto';
import { URL, URLSearchParams } from 'url';

const CONFIG_PATH = process.env.LINKEDIN_CONFIG || '/data/.linkedin';

// ── Args ───────────────────────────────────────────────────────────────────

function getArg(flag, required = false) {
  const i = process.argv.indexOf(flag);
  const val = i >= 0 ? process.argv[i + 1] : null;
  if (required && !val) {
    console.error(`Error: ${flag} is required`);
    process.exit(1);
  }
  return val;
}

const CLIENT_ID     = getArg('--client-id', true);
const CLIENT_SECRET = getArg('--client-secret', true);
const PORT          = parseInt(getArg('--port') || '3000', 10);
const REDIRECT_URI  = `http://localhost:${PORT}/callback`;

const SCOPES = ['openid', 'profile', 'r_basicprofile', 'r_member_social'].join(' ');

// ── PKCE ──────────────────────────────────────────────────────────────────

const state   = randomBytes(16).toString('hex');
const verifier = randomBytes(32).toString('base64url');
const challenge = createHash('sha256').update(verifier).digest('base64url');

// ── Auth URL ──────────────────────────────────────────────────────────────

const authUrl = new URL('https://www.linkedin.com/oauth/v2/authorization');
authUrl.searchParams.set('response_type', 'code');
authUrl.searchParams.set('client_id', CLIENT_ID);
authUrl.searchParams.set('redirect_uri', REDIRECT_URI);
authUrl.searchParams.set('state', state);
authUrl.searchParams.set('scope', SCOPES);
authUrl.searchParams.set('code_challenge', challenge);
authUrl.searchParams.set('code_challenge_method', 'S256');

console.log('\n=== LinkedIn OAuth Setup ===\n');
console.log(`If on a remote VPS, forward the port first in another terminal:`);
console.log(`  ssh -L ${PORT}:localhost:${PORT} hostinger-vps\n`);
console.log('Open this URL in your browser:\n');
console.log(authUrl.toString());
console.log('\nWaiting for callback on port', PORT, '...\n');

// ── Callback server ────────────────────────────────────────────────────────

const server = createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  if (url.pathname !== '/callback') {
    res.end('Not found');
    return;
  }

  const code         = url.searchParams.get('code');
  const returnedState = url.searchParams.get('state');

  if (returnedState !== state) {
    res.end('State mismatch — possible CSRF. Please retry.');
    server.close();
    process.exit(1);
  }

  if (!code) {
    const error = url.searchParams.get('error_description') || url.searchParams.get('error') || 'unknown';
    res.end(`Authorization failed: ${error}`);
    server.close();
    process.exit(1);
  }

  res.end('<h2>Authorization successful! You can close this tab.</h2>');

  // ── Exchange code for tokens ──────────────────────────────────────────
  try {
    const tokenRes = await fetch('https://www.linkedin.com/oauth/v2/accessToken', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        grant_type:    'authorization_code',
        code,
        redirect_uri:  REDIRECT_URI,
        client_id:     CLIENT_ID,
        client_secret: CLIENT_SECRET,
        code_verifier: verifier,
      }),
    });
    const tokens = await tokenRes.json();

    if (!tokens.access_token) {
      console.error('Token exchange failed:', JSON.stringify(tokens));
      server.close();
      process.exit(1);
    }

    // ── Get person ID via /v2/userinfo ──────────────────────────────────
    const profileRes = await fetch('https://api.linkedin.com/v2/userinfo', {
      headers: { Authorization: `Bearer ${tokens.access_token}` },
    });
    const profile = await profileRes.json();
    const personId = profile.sub ? `urn:li:person:${profile.sub}` : null;

    if (!personId) {
      console.error('Could not get person ID from userinfo:', JSON.stringify(profile));
      server.close();
      process.exit(1);
    }

    const config = {
      client_id:         CLIENT_ID,
      client_secret:     CLIENT_SECRET,
      access_token:      tokens.access_token,
      refresh_token:     tokens.refresh_token || null,
      person_id:         personId,
      token_expires_at:  Math.floor(Date.now() / 1000) + (tokens.expires_in || 5184000),
    };

    writeFileSync(CONFIG_PATH, JSON.stringify(config, null, 2), { mode: 0o600 });

    console.log(`\n✓ Tokens saved to ${CONFIG_PATH}`);
    console.log(`  Person ID: ${personId}`);
    console.log(`  Token expires: ${new Date(config.token_expires_at * 1000).toISOString().slice(0, 10)}`);
    console.log('\nRun: node scripts/sync.js --dry-run   to verify.\n');

  } catch (err) {
    console.error('Error:', err.message);
    process.exit(1);
  }

  server.close();
});

server.listen(PORT);
