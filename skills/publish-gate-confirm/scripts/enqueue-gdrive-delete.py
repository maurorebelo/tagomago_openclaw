#!/usr/bin/env python3
"""Queue a Google Drive delete request for Telegram approval on host."""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_QUEUE = Path("/data/.openclaw/delete-gates/gdrive")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--file-id", required=True, help="Google Drive file id")
    p.add_argument("--label", default="", help="Human label (name/path)")
    p.add_argument("--reason", default="", help="Why this delete is requested")
    args = p.parse_args()

    root = Path(os.environ.get("GDRIVE_DELETE_QUEUE_DIR", str(DEFAULT_QUEUE)))
    pending = root / "pending"
    for d in (pending, root / "sent", root / "rejected"):
        d.mkdir(parents=True, exist_ok=True)

    draft_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": draft_id,
        "target_id": args.file_id,
        "target_label": args.label,
        "reason": args.reason,
        "requested_at": now,
        "source": "enqueue-gdrive-delete.py",
    }
    slug = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = pending / f"{slug}_{draft_id[:8]}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    with open(root / "audit.log", "a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {"event": "enqueued", "channel": "gdrive_delete", "id": draft_id, "at": now},
                ensure_ascii=False,
            )
            + "\n"
        )

    print(f"Queued Google Drive delete request id={draft_id}")
    print(f"File: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
