#!/usr/bin/env python3
"""Queue a Nostr kind:1 draft (JSON only). Host runs nak-real event after Telegram approval."""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_PENDING = Path("/data/.openclaw/nostr-outbox/pending")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--content", required=True, help="Note text (plain)")
    p.add_argument(
        "--relay",
        action="append",
        dest="relays",
        default=[],
        help="Relay URL (repeatable), e.g. wss://nostr.tagomago.me",
    )
    p.add_argument("--note", default="")
    args = p.parse_args()

    if not args.relays:
        print("enqueue-nostr-draft: need at least one --relay", file=sys.stderr)
        return 2

    pending = Path(os.environ.get("NOSTR_DRAFT_QUEUE_DIR", str(DEFAULT_PENDING)))
    root = pending.parent
    for sub in (pending, root / "sent", root / "rejected"):
        sub.mkdir(parents=True, exist_ok=True)

    draft_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": draft_id,
        "content": args.content,
        "relays": args.relays,
        "note": args.note,
        "created_at": now,
        "source": "enqueue-nostr-draft.py",
    }
    slug = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = pending / f"{slug}_{draft_id[:8]}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    audit = root / "audit.log"
    with open(audit, "a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {"event": "enqueued", "channel": "nostr", "id": draft_id, "at": now},
                ensure_ascii=False,
            )
            + "\n"
        )

    print(f"Queued nostr draft id={draft_id}")
    print(f"File: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
