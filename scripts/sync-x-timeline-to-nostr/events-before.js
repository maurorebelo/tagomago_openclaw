#!/usr/bin/env node
/**
 * List your kind-1 events that have created_at BEFORE a given event id.
 * Usage: BEFORE_EVENT_ID=6250c459... node events-before.js
 *        (or pass event id as first arg)
 * Env: NOSTR_DAMUS_PUBLIC_HEX_KEY, NOSTR_BRIDGE_RELAY, NOSTR_TARGET_RELAY, NOSTR_PUBLIC_RELAYS
 */
import { SimplePool } from 'nostr-tools';

const BRIDGE = process.env.NOSTR_BRIDGE_RELAY || 'wss://bridge.tagomago.me';
const TARGET = process.env.NOSTR_TARGET_RELAY || 'wss://nostr.tagomago.me';
const PUBLIC = (process.env.NOSTR_PUBLIC_RELAYS || 'wss://relay.damus.io,wss://nostr.land,wss://nos.lol,wss://relay.nostr.band').split(',').map((r) => r.trim()).filter(Boolean);
const RELAYS = [BRIDGE, TARGET, ...PUBLIC];

const eventId = process.env.BEFORE_EVENT_ID || process.argv[2];
if (!eventId) {
  console.error('Usage: BEFORE_EVENT_ID=<hex> node events-before.js   or   node events-before.js <event_id_hex>');
  process.exit(1);
}

const pubkey = process.env.NOSTR_DAMUS_PUBLIC_HEX_KEY;
if (!pubkey) {
  console.error('Set NOSTR_DAMUS_PUBLIC_HEX_KEY');
  process.exit(1);
}

async function fetchEventById(pool, id) {
  return new Promise((resolve) => {
    const out = [];
    const sub = pool.subscribe(RELAYS, { ids: [id], kinds: [1] }, {
      onevent: (ev) => out.push(ev),
      oneose: () => {
        sub.close();
        resolve(out[0] || null);
      },
    });
    setTimeout(() => {
      sub.close();
      resolve(out[0] || null);
    }, 15000);
  });
}

async function fetchOurKind1(pool) {
  return new Promise((resolve) => {
    const events = [];
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      try { sub.close(); } catch (_) {}
      resolve(events);
    };
    const sub = pool.subscribe(RELAYS, { kinds: [1], authors: [pubkey] }, {
      onevent: (ev) => events.push(ev),
      oneose: finish,
      onclose: () => finish(),
    });
    setTimeout(finish, 25000);
  });
}

async function main() {
  const pool = new SimplePool();
  const ref = await fetchEventById(pool, eventId);
  if (!ref) {
    console.error('Event not found:', eventId);
    try { pool.close(); } catch (_) {}
    process.exit(1);
  }
  const refTime = ref.created_at;
  const all = await fetchOurKind1(pool);
  const before = all.filter((ev) => ev.created_at < refTime).sort((a, b) => b.created_at - a.created_at);
  try { pool.close(); } catch (_) {}

  const ts = (t) => (t != null && !isNaN(t) ? new Date(Number(t) * 1000).toISOString() : String(t));
  console.log('Event', eventId.slice(0, 16) + '...', 'created_at', refTime, ts(refTime));
  console.log('Content (first 120 chars):', (ref.content || '').slice(0, 120));
  console.log('');
  console.log('Your kind-1 events BEFORE it (most recent first), max 15:');
  before.slice(0, 15).forEach((ev, i) => {
    console.log((i + 1) + '.', ev.id.slice(0, 16) + '...', 'created_at', ev.created_at, ts(ev.created_at));
    console.log('   ', (ev.content || '').slice(0, 100) + (ev.content && ev.content.length > 100 ? '...' : ''));
  });
  console.log('');
  console.log('Total before:', before.length);
}

main().catch((e) => {
  console.error(e.message || e);
  process.exit(1);
});
