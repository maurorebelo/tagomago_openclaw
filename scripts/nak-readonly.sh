#!/usr/bin/env bash
# Read-only nak wrapper: allow query/decode/verify subcommands only.
# Blocks event, publish, mount, admin, and other write/network-publish paths.
# Install on VPS: copy to /data/bin/nak, move real binary to /data/bin/nak-real
# (same pattern as xurl). PATH must have /data/bin before Linuxbrew.

set -e
AUDIT_LOG="${NAK_AUDIT_LOG:-/data/.nak-audit.log}"
REAL="${NAK_REAL:-}"

if [ -z "$REAL" ]; then
  if [ -x "/data/bin/nak-real" ]; then
    REAL="/data/bin/nak-real"
  elif [ -x "/usr/local/bin/nak-real" ]; then
    REAL="/usr/local/bin/nak-real"
  else
    echo "nak-readonly: NAK_REAL not set and nak-real not found." >&2
    exit 1
  fi
fi

CMD="$*"
FIRST="${1:-}"
SECOND="${2:-}"

ALLOWED=0
case "$FIRST" in
  "" | -h | --help | help | version)
    ALLOWED=1
    ;;
  req | fetch | decode | encode | verify)
    ALLOWED=1
    ;;
  gift)
    if [ "$SECOND" = "unwrap" ]; then
      ALLOWED=1
    fi
    ;;
esac

log_line() {
  local status="$1"
  echo "$(date -Iseconds)	$status	nak $CMD" >> "$AUDIT_LOG" 2>/dev/null || true
}

if [ "$ALLOWED" -eq 0 ]; then
  log_line "BLOCKED"
  echo "nak-readonly: blocked: nak $CMD" >&2
  echo "Allowed: req, fetch, decode, encode, verify, gift unwrap, help. Blocked: event, publish, mount, admin, …" >&2
  exit 1
fi

log_line "ALLOWED"
exec "$REAL" "$@"
