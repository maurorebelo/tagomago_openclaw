#!/usr/bin/env bash
# Read-only xurl wrapper: only allows whoami and timeline. Logs every invocation; blocks post and any other subcommand.
# Install: put this script as "xurl" in a dir that appears before the real xurl in PATH (e.g. /data/bin),
# and set XURL_REAL to the real xurl binary (e.g. /usr/local/bin/xurl or $(which xurl) before installing the wrapper).
#
# Usage from agent/scripts: call "xurl" as usual; only "xurl whoami" and "xurl timeline ..." succeed.

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

# Allow only whoami and timeline (timeline with any args)
ALLOWED=0
case "$FIRST_ARG" in
  whoami)   ALLOWED=1 ;;
  timeline) ALLOWED=1 ;;
esac

log_line() {
  local status="$1"
  echo "$(date -Iseconds)	$status	xurl $CMD" >> "$AUDIT_LOG" 2>/dev/null || true
}

if [ "$ALLOWED" -eq 0 ]; then
  log_line "BLOCKED"
  echo "xurl-readonly: Only 'xurl whoami' and 'xurl timeline ...' are allowed. Blocked: xurl $CMD" >&2
  exit 1
fi

log_line "ALLOWED"
exec "$REAL" "$@"
