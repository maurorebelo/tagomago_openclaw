#!/usr/bin/env bash
# Republish all kind-1 events from bridge (or target) to PUBLIC relays.
# Use for historical posts imported via tweets.js so they appear on damus.io, nostr.land, etc.
# Run inside container. Source = bridge by default.
#
# Usage: NOSTR_DAMUS_PUBLIC_HEX_KEY=hex ./republish-to-public-relays.sh
# Optional: NOSTR_REPUBLISH_SOURCE=wss://nostr.tagomago.me (default: bridge)

set -e
PUBKEY="${NOSTR_DAMUS_PUBLIC_HEX_KEY:?set NOSTR_DAMUS_PUBLIC_HEX_KEY}"
SOURCE="${NOSTR_REPUBLISH_SOURCE:-${NOSTR_BRIDGE_RELAY:-wss://bridge.tagomago.me}}"
PUBLIC_RELAYS_STR="${NOSTR_PUBLIC_RELAYS:-wss://relay.damus.io,wss://nostr.land,wss://nos.lol,wss://relay.nostr.band}"
B="/tmp/republish-to-public-$$.jsonl"

# --paginate: multiple REQs with decreasing 'until' until we have limit or no more (fetches full history)
echo "Fetching events from $SOURCE (paginated, up to 50000)..."
nak req -k 1 -a "$PUBKEY" -l 50000 --paginate --paginate-interval 1s "$SOURCE" 2>/dev/null > "$B" || true

# SAFETY: only republish events whose .pubkey matches PUBKEY (never publish others' events)
B_FILTERED="/tmp/republish-filtered-$$.jsonl"
while IFS= read -r line; do
  [ -z "$line" ] && continue
  if jq -e --arg pk "$PUBKEY" '.pubkey == $pk' <<< "$line" >/dev/null 2>&1; then
    echo "$line" >> "$B_FILTERED"
  fi
done < "$B"
rm -f "$B"
mv "$B_FILTERED" "$B" 2>/dev/null || touch "$B"

n=$(wc -l < "$B" 2>/dev/null || echo 0)
echo "Events with pubkey $PUBKEY: $n. Publishing ONLY these to public relays..."
echo "Public relays: $PUBLIC_RELAYS_STR"

repub=0
while IFS= read -r relay; do
  relay=$(echo "$relay" | tr -d ' ')
  [ -z "$relay" ] && continue
  count=0
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    if echo "$line" | nak event "$relay" 2>/dev/null | grep -q success; then count=$((count+1)); fi
  done < "$B"
  echo "  $relay: $count"
  repub=$((repub+count))
done < <(echo "$PUBLIC_RELAYS_STR" | tr ',' '\n')

rm -f "$B"
echo "Done. Total publishes: $repub"
