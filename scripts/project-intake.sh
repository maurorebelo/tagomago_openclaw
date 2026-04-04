#!/usr/bin/env bash
# Stage an uploaded file into a project inbox.
# Usage:
#   project-intake.sh <project-slug> [source-file]
# Examples:
#   project-intake.sh todabio
#   project-intake.sh jacqueline-chat "/data/.openclaw/media/inbound/file_3---uuid.zip"

set -euo pipefail

PROJECT_SLUG="${1:-}"
SOURCE_FILE="${2:-}"

if [[ -z "$PROJECT_SLUG" ]]; then
  echo "Usage: project-intake.sh <project-slug> [source-file]" >&2
  exit 1
fi

INBOUND_DIR="/data/.openclaw/media/inbound"
PROJECT_INBOX="/data/projects/${PROJECT_SLUG}/inbox"

mkdir -p "$PROJECT_INBOX"
if [[ "$(id -u)" -eq 0 ]] && id node >/dev/null 2>&1; then
  chown -R node:node "/data/projects/${PROJECT_SLUG}"
fi

if [[ -z "$SOURCE_FILE" ]]; then
  SOURCE_FILE="$(ls -t "$INBOUND_DIR" 2>/dev/null | head -n 1 || true)"
  if [[ -z "$SOURCE_FILE" ]]; then
    echo "ERROR: no files found in ${INBOUND_DIR}" >&2
    exit 1
  fi
  SOURCE_FILE="${INBOUND_DIR}/${SOURCE_FILE}"
fi

if [[ ! -f "$SOURCE_FILE" ]]; then
  echo "ERROR: file not found: $SOURCE_FILE" >&2
  exit 1
fi

BASENAME="$(basename "$SOURCE_FILE")"

# If filename follows the pattern "<name>---<uuid>.<ext>", keep only "<name>.<ext>".
if [[ "$BASENAME" == *---* ]]; then
  LEFT="${BASENAME%%---*}"
  RIGHT="${BASENAME##*.}"
  if [[ "$LEFT" != "$BASENAME" && "$RIGHT" != "$BASENAME" ]]; then
    BASENAME="${LEFT}.${RIGHT}"
  fi
fi

DEST_PATH="${PROJECT_INBOX}/${BASENAME}"

# Avoid overwrite collisions by appending a timestamp.
if [[ -e "$DEST_PATH" ]]; then
  TS="$(date +%Y%m%d-%H%M%S)"
  EXT="${BASENAME##*.}"
  NAME="${BASENAME%.*}"
  DEST_PATH="${PROJECT_INBOX}/${NAME}-${TS}.${EXT}"
fi

cp -f "$SOURCE_FILE" "$DEST_PATH"
if [[ "$(id -u)" -eq 0 ]] && id node >/dev/null 2>&1; then
  chown node:node "$DEST_PATH"
fi
echo "$DEST_PATH"
