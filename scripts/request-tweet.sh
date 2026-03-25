#!/usr/bin/env bash
# Agent calls this to queue a tweet draft for human approval.
# Usage: request-tweet.sh "tweet text here"
# Writes a draft to /data/pending-tweets/ and prints the draft ID.

set -euo pipefail

QUEUE_DIR="/data/pending-tweets"
mkdir -p "$QUEUE_DIR"

TEXT="${1:-}"
if [[ -z "$TEXT" ]]; then
  echo "ERROR: no tweet text provided" >&2
  echo "Usage: request-tweet.sh \"tweet text\"" >&2
  exit 1
fi

DRAFT_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"
DRAFT_FILE="$QUEUE_DIR/$DRAFT_ID.json"

cat > "$DRAFT_FILE" <<EOF
{
  "id": "$DRAFT_ID",
  "text": $(python3 -c "import json,sys; print(json.dumps(sys.argv[1]))" "$TEXT"),
  "requested_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "status": "pending"
}
EOF

echo "DRAFT QUEUED: $DRAFT_ID"
echo "Text: $TEXT"
echo "Awaiting human approval. Run publish-pending.sh on the VPS to review."
