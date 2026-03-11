#!/usr/bin/env bash
# Deploy health-analytics skill (includes weltory_tips inside the skill) to the VPS workspace.
# Run from repo root. Uses NOSTR_REBROADCAST_SSH, OPENCLAW_WORKSPACE_HOST.
# After deploy, run test: ssh hostinger-vps 'docker exec openclaw-b60d-openclaw-1 bash -c "python3 /data/skills/health-analytics/scripts/init_db.py --workspace /data && python3 /data/skills/health-analytics/scripts/consolidate.py --workspace /data --clear-raw"'
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$SKILL_ROOT/../.." && pwd)"
SSH_HOST="${NOSTR_REBROADCAST_SSH:-hostinger-vps}"
CONTAINER="${NOSTR_REBROADCAST_CONTAINER:-openclaw-b60d-openclaw-1}"
WORKSPACE_HOST="${OPENCLAW_WORKSPACE_HOST:-/docker/openclaw-b60d/data}"

echo "Deploying health-analytics to $SSH_HOST ($WORKSPACE_HOST)"
cd "$REPO_ROOT"

# Pack skill only (weltory_tips is inside skills/health-analytics/weltory_tips)
TAR_SKILL="/tmp/health-analytics-deploy.tar"
(cd "$SKILL_ROOT" && COPYFILE_DISABLE=1 tar -c -f "$TAR_SKILL" . 1>/dev/null 2>/dev/null)

# Copy to VPS
scp -q "$TAR_SKILL" "$SSH_HOST:/tmp/health-analytics-deploy.tar"

# Extract on VPS
ssh "$SSH_HOST" "mkdir -p $WORKSPACE_HOST/skills/health-analytics $WORKSPACE_HOST/data/health/duckdb && \
  cd $WORKSPACE_HOST/skills/health-analytics && tar xf /tmp/health-analytics-deploy.tar && \
  rm -f /tmp/health-analytics-deploy.tar"

# So that the container user (node) can write the DB (adjust UID if needed)
ssh "$SSH_HOST" "chown -R 1000:1000 $WORKSPACE_HOST/data/health 2>/dev/null || true"

rm -f "$TAR_SKILL"
echo "Done. Skill at $WORKSPACE_HOST/skills/health-analytics (includes weltory_tips)"

