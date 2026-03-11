#!/usr/bin/env node
/**
 * One-off: connect to a Nostr relay and try to fetch 1 event with different
 * REQ filter shapes. Logs what we send and what we get (events, EOSE, NOTICE).
 * Usage: node scripts/diagnose-relay.js
 * Env: NOSTR_RELAYS (default wss://bridge.tagomago.me), NOSTR_PUBKEYS (hex).
 */
import { SimplePool } from "nostr-tools";

const relay = (process.env.NOSTR_RELAYS || "wss://relay.damus.io").split(",")[0].trim();
const pubkey = (process.env.NOSTR_PUBKEYS || "e24616cde0fdbe0164d0831309aea3eb4ed61e320a3c37dc0048edc8ac49976b").split(",")[0].trim();
const pool = new SimplePool();

async function tryFilter(name, filter) {
  console.log("\n---", name, "---");
  console.log("Filter:", JSON.stringify(filter));
  return new Promise((resolve) => {
    const got = [];
    const sub = pool.subscribe(
      [relay],
      [filter],
      {
        onevent(ev) {
          got.push(ev);
          console.log("  EVENT:", ev.id.slice(0, 12), "kind:", ev.kind, "created_at:", ev.created_at);
        },
        oneose() {
          console.log("  EOSE");
        },
        onnotice(notice) {
          console.log("  NOTICE:", notice);
        },
      }
    );
    setTimeout(() => {
      sub.close();
      console.log("  Result: got", got.length, "event(s)");
      resolve(got.length);
    }, 5000);
  });
}

async function main() {
  console.log("Relay:", relay);
  console.log("Pubkey (first 16):", pubkey.slice(0, 16) + "...");

  // 1: minimal – kinds + authors only
  await tryFilter("Minimal (kinds + authors)", {
    kinds: [1],
    authors: [pubkey],
  });

  // 2: with since (e.g. 1 year ago)
  const since = Math.floor(Date.now() / 1000) - 365 * 86400;
  await tryFilter("With since only", {
    kinds: [1],
    authors: [pubkey],
    since,
  });

  // 3: with since + until
  const until = Math.floor(Date.now() / 1000);
  await tryFilter("With since + until", {
    kinds: [1],
    authors: [pubkey],
    since,
    until,
  });

  // 4: limit 1 (NIP-01 doesn't have limit; some relays support it anyway)
  await tryFilter("Minimal + limit 1", {
    kinds: [1],
    authors: [pubkey],
    limit: 1,
  });

  try { pool.close(); } catch (_) {}
  console.log("\nDone.");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
