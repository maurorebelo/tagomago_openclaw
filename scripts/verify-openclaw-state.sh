#!/usr/bin/env bash
# Phase 1 of OpenClaw install alignment: read-only checks on the VPS.
# Run from repo root. Uses NOSTR_REBROADCAST_SSH, NOSTR_REBROADCAST_CONTAINER.
# Records: config workspace, skills on disk, permissions.
set -e

SSH_HOST="${NOSTR_REBROADCAST_SSH:-hostinger-vps}"
CONTAINER="${NOSTR_REBROADCAST_CONTAINER:-openclaw-b60d-openclaw-1}"

echo "=== OpenClaw state (VPS: $SSH_HOST, container: $CONTAINER) ==="
echo ""

echo "--- 1. Config: agents.defaults.workspace and skills.load ---"
ssh "$SSH_HOST" "docker exec $CONTAINER node -e \"
const fs = require('fs');
const p = '/data/.openclaw/openclaw.json';
let c;
try { c = JSON.parse(fs.readFileSync(p, 'utf8')); } catch (e) { console.log('Error:', e.message); process.exit(1); }
console.log('agents.defaults.workspace:', c.agents?.defaults?.workspace ?? '(missing)');
console.log('skills.load:', c.skills?.load ? JSON.stringify(c.skills.load, null, 2) : '(missing)');
\""
echo ""

echo "--- 2. Skills on disk: /data/skills/ ---"
ssh "$SSH_HOST" "docker exec $CONTAINER ls -la /data/skills/"
echo ""

echo "--- 3. One skill (twitter-nostr-sync): SKILL.md and agents/ ---"
ssh "$SSH_HOST" "docker exec $CONTAINER sh -c 'ls -la /data/skills/twitter-nostr-sync/ 2>/dev/null || echo \"(dir missing)\"; ls -la /data/skills/twitter-nostr-sync/agents/ 2>/dev/null || echo \"(agents missing)\"'"
echo ""

echo "--- 4. Permissions: who runs and can write data/health ---"
ssh "$SSH_HOST" "docker exec $CONTAINER sh -c 'id; ls -la /data/data/health/duckdb 2>/dev/null || echo \"(path missing)\"'"
echo ""

echo "=== End of state dump. Compare agents.defaults.workspace to \"/data\" and ensure skills list matches deployed skills. ==="
