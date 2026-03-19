# Twitter / Nostr sync — rollback pointer and findings

## What “take back” can and cannot do

- **Can:** Restore the **git repo** to a state **before** the live X→Nostr sync existed (see branch below). On the VPS: `git fetch && git checkout rollback/pre-live-sync` (or merge that branch as you prefer).
- **Cannot:** Remove tweets already posted on **X**, or events already on **Nostr relays**, from here. That requires X / relay / client actions, not this repo.

## Rollback branch (before live sync ever existed)

- **Branch:** `rollback/pre-live-sync`
- **Commit:** `628d299` — last commit *before* `9e02987` (“add live sync (xurl timeline 2x/day)…”).

That point has **no** `scripts/sync-x-timeline-to-nostr/`, **no** `run-live-x-nostr-sync.sh`, **no** live sync loop — only batch import from `tweets.js` as documented earlier.

## Findings: does the live sync post to Twitter?

**No.** In every version we shipped, `scripts/sync-x-timeline-to-nostr/sync.js` only:

1. Calls **read** APIs via `xurl` (`whoami`, then later `timeline` or `GET /2/users/{id}/tweets`).
2. **Writes only to Nostr** (`nostr-tools` `pool.publish` to bridge / target / public relays).

There is **no** `xurl post`, **no** `POST /2/tweets`, **no** Twitter write in that file or in `run-live-x-nostr-sync.sh` (only `node sync.js` + `nak` for Nostr).

So **if new posts appeared on your X timeline**, they were **not** created by the sync script’s intended code path. Possibilities include: another process or user calling **`xurl` by full path** (bypassing `/data/bin` wrapper), another app with OAuth, manual posting, or confusion with RTs / feed. The VPS **audit log** (`/data/.xurl-audit.log`) only sees calls that use the **wrapped** `xurl` in `PATH`.

## Chronology (recent commits touching this)

See `git log` from `628d299` to `HEAD`: live sync added, then republish safety, author filter, user-tweets endpoint, xurl read-only wrapper, delete/unsync helpers, etc.

---

*Written for transparency after user request to take back changes and find out what happened.*
