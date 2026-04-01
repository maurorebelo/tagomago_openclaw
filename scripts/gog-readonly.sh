#!/usr/bin/env bash
# Read-only gog wrapper for agent path.
# Blocks outbound Gmail send while allowing reads.

set -e
AUDIT_LOG="${GOG_AUDIT_LOG:-/data/.gog-audit.log}"
REAL="${GOG_REAL:-}"

if [ -z "$REAL" ]; then
  if [ -x "/data/bin/gog-real" ]; then
    REAL="/data/bin/gog-real"
  elif [ -x "/data/linuxbrew/.linuxbrew/bin/gog" ]; then
    REAL="/data/linuxbrew/.linuxbrew/bin/gog"
  else
    echo "gog-readonly: GOG_REAL not set and gog real binary not found." >&2
    exit 1
  fi
fi

CMD="$*"
A1="${1:-}"
A2="${2:-}"
A3="${3:-}"

log_line() {
  local status="$1"
  echo "$(date -Iseconds)	$status	gog $CMD" >> "$AUDIT_LOG" 2>/dev/null || true
}

if [ "$A1" = "gmail" ] && [ "$A2" = "send" ]; then
  log_line "BLOCKED"
  echo "gog-readonly: blocked: gog gmail send" >&2
  exit 1
fi

# Drive destructive ops must run on host via publish gate.
if [ "$A1" = "drive" ]; then
  if [ "$A2" = "delete" ] || [ "$A2" = "remove" ] || [ "$A2" = "trash" ]; then
    log_line "BLOCKED"
    echo "gog-readonly: blocked: gog drive $A2 (use Telegram approval queue on host)" >&2
    exit 1
  fi
  if [ "$A2" = "files" ] && { [ "$A3" = "delete" ] || [ "$A3" = "remove" ] || [ "$A3" = "trash" ]; }; then
    log_line "BLOCKED"
    echo "gog-readonly: blocked: gog drive files $A3 (use Telegram approval queue on host)" >&2
    exit 1
  fi
fi

log_line "ALLOWED"
exec "$REAL" "$@"
