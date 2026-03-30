#!/usr/bin/env python3
"""
Queue an email draft for host-side confirmation and send.
Safe to run inside the OpenClaw container: no network send, no SMTP secrets.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Default matches in-container workspace; override with EMAIL_OUTBOX_ROOT if needed.
DEFAULT_ROOT = Path("/data/.openclaw/email-outbox")


def _ensure_dirs(root: Path) -> None:
    (root / "pending").mkdir(parents=True, exist_ok=True)
    (root / "sent").mkdir(parents=True, exist_ok=True)
    (root / "rejected").mkdir(parents=True, exist_ok=True)


def _audit(root: Path, event: dict) -> None:
    line = json.dumps(event, ensure_ascii=False) + "\n"
    with open(root / "audit.log", "a", encoding="utf-8") as f:
        f.write(line)


def _basic_email_check(addr: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", addr.strip()))


def main() -> int:
    p = argparse.ArgumentParser(description="Queue email draft (no send).")
    p.add_argument("--to", required=True, help="Recipient address")
    p.add_argument("--subject", required=True)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--body", help="Plain-text body")
    g.add_argument("--body-file", type=Path, help="File with plain-text body")
    p.add_argument("--note", default="", help="Optional context for humans/audit")
    p.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_ROOT,
        help="Outbox root directory",
    )
    args = p.parse_args()
    args.root = Path(os.environ.get("EMAIL_OUTBOX_ROOT", str(args.root)))

    to_addr = args.to.strip()
    if not _basic_email_check(to_addr):
        print("enqueue-email-draft: invalid --to address", file=sys.stderr)
        return 2

    if args.body_file is not None:
        body = args.body_file.read_text(encoding="utf-8")
    else:
        body = args.body or ""

    _ensure_dirs(args.root)
    draft_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": draft_id,
        "to": to_addr,
        "subject": args.subject,
        "body": body,
        "note": args.note,
        "created_at": now,
        "source": "enqueue-email-draft.py",
    }
    slug = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = args.root / "pending" / f"{slug}_{draft_id[:8]}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    _audit(
        args.root,
        {
            "event": "enqueued",
            "id": draft_id,
            "to": to_addr,
            "subject": args.subject,
            "path": str(path),
            "at": now,
        },
    )

    print(f"Queued draft id={draft_id}")
    print(f"File: {path}")
    print("Approve on the VPS host: publish-gate-confirm/scripts/telegram_approval_daemon.py (or TTY email-outbox-process.py there).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
