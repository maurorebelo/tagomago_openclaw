#!/usr/bin/env bash
# Republish all kind-1 events from bridge to target relay. Run inside container.
# Usage: NOSTR_DAMUS_PUBLIC_HEX_KEY=hex ./republish-bridge-to-nostr.sh

set -e
PUBKEY="${NOSTR_DAMUS_PUBLIC_HEX_KEY:?set NOSTR_DAMUS_PUBLIC_HEX_KEY}"
BRIDGE="${NOSTR_BRIDGE_RELAY:-wss://bridge.tagomago.me}"
TARGET="${NOSTR_TARGET_RELAY:-wss://nostr.tagomago.me}"
B="/tmp/republish-bridge-$$.jsonl"
/data/bin/nak-real req -k 1 -a "$PUBKEY" -l 50000 "$BRIDGE" 2>/dev/null > "$B" || true
n=$(wc -l < "$B" 2>/dev/null || echo 0)
echo "Events on bridge: $n. Republishing to $TARGET..."
repub=0
while read -r line; do
  [ -n "$line" ] && echo "$line" | /data/bin/nak-real event "$TARGET" 2>/dev/null | grep -q success && repub=$((repub+1)) || true
done < "$B"
rm -f "$B"
echo "Republished: $repub"
