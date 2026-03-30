#!/usr/bin/env python3
"""
TTY review for email drafts only (VPS host). For Telegram use telegram_approval_daemon.py.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_scripts = Path(__file__).resolve().parent
if str(_scripts) not in sys.path:
    sys.path.insert(0, str(_scripts))

from outbox_common import (
    DEFAULT_HOST_ROOT,
    audit,
    finalize_rejected,
    finalize_sent,
    load_draft,
    pending_files,
    send_mail,
)


def main() -> int:
    root = Path(os.environ.get("EMAIL_OUTBOX_ROOT", str(DEFAULT_HOST_ROOT)))
    if not root.is_dir():
        print(f"email-outbox-process: root missing: {root}", file=sys.stderr)
        return 2

    pending = pending_files(root)
    if not pending:
        print("No pending drafts.")
        return 0

    if not sys.stdin.isatty():
        print("email-outbox-process: need a TTY.", file=sys.stderr)
        return 2

    for path in pending:
        record = load_draft(path)
        if record is None:
            print(f"Skip invalid {path}", file=sys.stderr)
            continue

        print("---")
        print(f"File: {path.name}")
        print(f"To: {record.get('to', '')}")
        print(f"Subject: {record.get('subject', '')}")
        print(record.get("body", ""))
        print("---")

        ans = input("Send? [y/N/q] ").strip().lower()
        if ans == "q":
            return 0
        if ans != "y":
            finalize_rejected(root, path, record)
            continue

        try:
            send_mail(record)
        except Exception as e:
            print(f"Send failed: {e}", file=sys.stderr)
            audit(
                root,
                {
                    "event": "send_failed",
                    "id": record.get("id", ""),
                    "error": str(e),
                    "at": datetime.now(timezone.utc).isoformat(),
                },
            )
            return 1

        print(f"Sent → {finalize_sent(root, path, record).name}")

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
