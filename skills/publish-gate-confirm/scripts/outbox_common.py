"""
Shared helpers for publish-gate-confirm (host-side processors only).
"""
from __future__ import annotations

import json
import os
import smtplib
import subprocess
from datetime import datetime, timezone
from email.mime.text import MIMEText
from pathlib import Path

DEFAULT_HOST_ROOT = Path("/docker/openclaw-b60d/data/.openclaw/email-outbox")


def audit(root: Path, event: dict) -> None:
    line = json.dumps(event, ensure_ascii=False) + "\n"
    with open(root / "audit.log", "a", encoding="utf-8") as f:
        f.write(line)


def audit_line(log_path: Path, event: dict) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event, ensure_ascii=False) + "\n"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line)


def send_mail(record: dict) -> None:
    if os.environ.get("SMTP_HOST", "").strip():
        _send_smtp(record)
        return
    _send_msmtp(record)


def _send_smtp(record: dict) -> None:
    host = os.environ.get("SMTP_HOST", "").strip()
    if not host:
        raise RuntimeError("SMTP_HOST not set")

    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "")
    from_addr = os.environ.get("SMTP_FROM", "").strip()
    if not from_addr:
        raise RuntimeError("SMTP_FROM not set")

    use_tls = os.environ.get("SMTP_STARTTLS", "1").strip() in ("1", "true", "yes", "on")

    msg = MIMEText(record["body"], "plain", "utf-8")
    msg["Subject"] = record["subject"]
    msg["From"] = from_addr
    msg["To"] = record["to"]

    with smtplib.SMTP(host, port, timeout=60) as smtp:
        if use_tls:
            smtp.starttls()
        if user:
            smtp.login(user, password)
        smtp.sendmail(from_addr, [record["to"]], msg.as_string())


def _send_msmtp(record: dict) -> None:
    from_addr = os.environ.get("SMTP_FROM", "").strip()
    lines: list[str] = []
    if from_addr:
        lines.append(f"From: {from_addr}")
    lines.extend(
        [
            f"To: {record['to']}",
            f"Subject: {record['subject']}",
            "MIME-Version: 1.0",
            'Content-Type: text/plain; charset="utf-8"',
            "",
            record["body"],
        ]
    )
    raw = "\n".join(lines).encode("utf-8")
    r = subprocess.run(
        ["msmtp", "-t"],
        input=raw,
        capture_output=True,
        timeout=120,
    )
    if r.returncode != 0:
        err = (r.stderr or b"").decode("utf-8", errors="replace")
        raise RuntimeError(f"msmtp failed ({r.returncode}): {err}")


def pending_files(root: Path) -> list[Path]:
    d = root / "pending"
    if not d.is_dir():
        return []
    return sorted(d.glob("*.json"))


def finalize_sent(root: Path, path: Path, record: dict) -> Path:
    draft_id = record.get("id", path.stem)
    sent_name = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{path.name}"
    dest = root / "sent" / sent_name
    record["sent_at"] = datetime.now(timezone.utc).isoformat()
    dest.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    path.unlink(missing_ok=True)
    audit(
        root,
        {
            "event": "sent",
            "id": draft_id,
            "to": record.get("to", ""),
            "subject": record.get("subject", ""),
            "path": str(dest),
            "at": record["sent_at"],
        },
    )
    return dest


def finalize_rejected(root: Path, path: Path, record: dict) -> Path:
    draft_id = record.get("id", path.stem)
    dest = root / "rejected" / path.name
    path.rename(dest)
    audit(
        root,
        {
            "event": "rejected",
            "id": draft_id,
            "path": str(dest),
            "at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return dest


def load_draft(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
