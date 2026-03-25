#!/usr/bin/env bash
# Run on the VPS host to review and approve pending tweet drafts.
# Usage: publish-pending.sh
# Requires: xurl at /usr/local/bin/xurl with ~/.xurl credentials (write-capable).

set -euo pipefail

QUEUE_DIR="/docker/openclaw-b60d/data/pending-tweets"
LOG_FILE="/docker/openclaw-b60d/data/pending-tweets/publish.log"

if [[ ! -d "$QUEUE_DIR" ]]; then
  echo "No queue directory found at $QUEUE_DIR"
  exit 1
fi

shopt -s nullglob
DRAFTS=("$QUEUE_DIR"/*.json)

if [[ ${#DRAFTS[@]} -eq 0 ]]; then
  echo "No pending drafts."
  exit 0
fi

echo "--- Pending tweet drafts ---"
echo ""

for DRAFT_FILE in "${DRAFTS[@]}"; do
  [[ "$(basename "$DRAFT_FILE")" == "publish.log" ]] && continue

  DRAFT_ID=$(python3 -c "import json; d=json.load(open('$DRAFT_FILE')); print(d['id'])")
  TEXT=$(python3 -c "import json; d=json.load(open('$DRAFT_FILE')); print(d['text'])")
  REQUESTED_AT=$(python3 -c "import json; d=json.load(open('$DRAFT_FILE')); print(d['requested_at'])")

  echo "ID:        $DRAFT_ID"
  echo "Requested: $REQUESTED_AT"
  echo "Text:"
  echo ""
  echo "  $TEXT"
  echo ""
  read -rp "Publish this tweet? [y/n/q=quit] " ANSWER

  case "$ANSWER" in
    y|Y)
      echo "Publishing..."
      RESULT=$(xurl post --text "$TEXT" 2>&1)
      echo "$RESULT"
      python3 -c "
import json, datetime
d = json.load(open('$DRAFT_FILE'))
d['status'] = 'published'
d['published_at'] = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
d['result'] = '''$RESULT'''
open('$DRAFT_FILE', 'w').write(json.dumps(d, indent=2))
"
      echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) PUBLISHED $DRAFT_ID: $TEXT" >> "$LOG_FILE"
      mv "$DRAFT_FILE" "${DRAFT_FILE%.json}.published.json"
      echo "Done."
      ;;
    n|N)
      python3 -c "
import json, datetime
d = json.load(open('$DRAFT_FILE'))
d['status'] = 'rejected'
d['rejected_at'] = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
open('$DRAFT_FILE', 'w').write(json.dumps(d, indent=2))
"
      echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) REJECTED $DRAFT_ID" >> "$LOG_FILE"
      mv "$DRAFT_FILE" "${DRAFT_FILE%.json}.rejected.json"
      echo "Rejected."
      ;;
    q|Q)
      echo "Quit. Remaining drafts left in queue."
      exit 0
      ;;
    *)
      echo "Skipped."
      ;;
  esac
  echo ""
done

echo "All drafts reviewed."
