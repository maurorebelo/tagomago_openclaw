#!/usr/bin/env bash
# Run on the VPS, inside the OpenClaw container (or with cwd = workspace root).
# Sanitizes .openclaw/openclaw.json and writes config/openclaw.sanitized.json
# so the repo reflects dashboard state. Then you can commit and push from Mac,
# or (if VPS has git push configured) uncomment the git commands below.
#
# Usage (from host):
#   ssh hostinger-vps "docker exec openclaw-b60d-openclaw-1 /data/scripts/sync-openclaw-config-to-repo.sh"
#
# Or inside the container:
#   cd /data && ./scripts/sync-openclaw-config-to-repo.sh

set -e
cd /data
node scripts/sanitize-openclaw-config.js
echo "Sanitized config written to config/openclaw.sanitized.json"

# Optional: commit and push from VPS (requires git remote and credentials)
# git add config/openclaw.sanitized.json
# git diff --staged --quiet && echo "No changes" || git commit -m "chore: sync OpenClaw dashboard config (sanitized)"
# git push origin master
