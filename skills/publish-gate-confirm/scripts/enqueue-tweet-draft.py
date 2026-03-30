#!/usr/bin/env python3
"""Queue an X post draft (JSON only). Host Telegram daemon runs xurl-real post after approval."""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_QUEUE = Path("/data/pending-tweets")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--text", required=True, help="Tweet text (plain)")
    p.add_argument("--note", default="", help="Optional context for humans")
    args = p.parse_args()

    qdir = Path(os.environ.get("TWEET_DRAFT_QUEUE_DIR", str(DEFAULT_QUEUE)))
    qdir.mkdir(parents=True, exist_ok=True)

    draft_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    record = {
        "id": draft_id,
        "text": args.text,
        "note": args.note,
        "requested_at": now,
        "source": "enqueue-tweet-draft.py",
    }
    slug = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = qdir / f"{slug}_{draft_id[:8]}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    log = qdir / "publish-gate-audit.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {"event": "enqueued", "channel": "tweet", "id": draft_id, "at": now},
                ensure_ascii=False,
            )
            + "\n"
        )

    print(f"Queued tweet draft id={draft_id}")
    print(f"File: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
