#!/usr/bin/env bash
# Read-only xurl wrapper: allows whoami, timeline (legacy), and GET /2/users/{id}/tweets (your tweets only).
# Blocks post and other write APIs.

set -e
AUDIT_LOG="${XURL_AUDIT_LOG:-/data/.xurl-audit.log}"
REAL="${XURL_REAL:-}"

if [ -z "$REAL" ]; then
  # Fallback: common locations
  if [ -x "/usr/local/bin/xurl-real" ]; then
    REAL="/usr/local/bin/xurl-real"
  elif [ -x "/data/bin/xurl-real" ]; then
    REAL="/data/bin/xurl-real"
  else
    echo "xurl-readonly: XURL_REAL not set and xurl-real not found. Set XURL_REAL to the real xurl binary." >&2
    exit 1
  fi
fi

CMD="$*"
FIRST_ARG="${1:-}"

ALLOWED=0
case "$FIRST_ARG" in
  whoami)   ALLOWED=1 ;;
  timeline) ALLOWED=1 ;;
  *)
    # GET /2/users/NUMERIC_ID/tweets?... (list only your own tweets; read-only)
    if [[ "$FIRST_ARG" =~ ^/2/users/[0-9]+/tweets ]]; then
      ALLOWED=1
    fi
    ;;
esac

log_line() {
  local status="$1"
  echo "$(date -Iseconds)	$status	xurl $CMD" >> "$AUDIT_LOG" 2>/dev/null || true
}

if [ "$ALLOWED" -eq 0 ]; then
  log_line "BLOCKED"
  echo "xurl-readonly: Allowed: whoami, timeline, /2/users/{id}/tweets. Blocked: xurl $CMD" >&2
  exit 1
fi

log_line "ALLOWED"
exec "$REAL" "$@"
