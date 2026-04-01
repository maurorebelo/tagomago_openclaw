#!/usr/bin/env python3
"""Queue a workout write request (JSON payload) for Telegram approval on host."""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_QUEUE = Path("/data/.openclaw/write-gates/workout")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--payload-file", required=True, help="Path to JSON file that will be POSTed on approve")
    p.add_argument("--label", default="", help="Human label for this workout write")
    p.add_argument("--reason", default="", help="Why this write is requested")
    args = p.parse_args()

    payload_path = Path(args.payload_file)
    if not payload_path.is_file():
        print(f"payload file not found: {payload_path}", file=sys.stderr)
        return 2

    try:
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"invalid payload JSON: {e}", file=sys.stderr)
        return 2

    root = Path(os.environ.get("WORKOUT_WRITE_QUEUE_DIR", str(DEFAULT_QUEUE)))
    pending = root / "pending"
    for d in (pending, root / "sent", root / "rejected"):
        d.mkdir(parents=True, exist_ok=True)

    draft_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": draft_id,
        "label": args.label,
        "reason": args.reason,
        "payload": payload,
        "requested_at": now,
        "source": "enqueue-workout-write.py",
    }
    slug = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = pending / f"{slug}_{draft_id[:8]}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    with open(root / "audit.log", "a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {"event": "enqueued", "channel": "workout_write", "id": draft_id, "at": now},
                ensure_ascii=False,
            )
            + "\n"
        )

    print(f"Queued workout write request id={draft_id}")
    print(f"File: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
