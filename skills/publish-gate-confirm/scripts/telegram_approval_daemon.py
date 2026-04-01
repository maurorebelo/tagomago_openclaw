#!/usr/bin/env python3
"""
VPS host: one Telegram bot polls getUpdates and notifies on new drafts for:
  - Email (JSON in EMAIL_OUTBOX_ROOT/pending)
  - X / Twitter (JSON in TWEET_DRAFT_QUEUE_DIR, same shape as scripts/publish-pending.sh)
  - Nostr kind 1 (JSON in NOSTR_DRAFT_QUEUE_DIR)
  - Workout write requests (JSON in WORKOUT_WRITE_QUEUE_DIR/pending)
  - Google Drive delete requests (JSON in GDRIVE_DELETE_QUEUE_DIR/pending)
  - Notion delete requests (JSON in NOTION_DELETE_QUEUE_DIR/pending)

Uses a dedicated bot token (not OpenClaw's main bot). See SKILL.md and docs/public-write-gates.md.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

_scripts = Path(__file__).resolve().parent
if str(_scripts) not in sys.path:
    sys.path.insert(0, str(_scripts))

from outbox_common import (
    DEFAULT_HOST_ROOT,
    audit,
    audit_line,
    finalize_rejected,
    finalize_sent,
    load_draft,
    pending_files,
    send_mail,
)

STATE_NAME = "telegram-approver-state.json"
TELEGRAM_TEXT_MAX = 3500

DEFAULT_TWEET_QUEUE = Path("/docker/openclaw-b60d/data/pending-tweets")
DEFAULT_NOSTR_PENDING = Path("/docker/openclaw-b60d/data/.openclaw/nostr-outbox/pending")
DEFAULT_WORKOUT_WRITE_QUEUE = Path("/docker/openclaw-b60d/data/.openclaw/write-gates/workout")
DEFAULT_GDRIVE_DELETE_QUEUE = Path("/docker/openclaw-b60d/data/.openclaw/delete-gates/gdrive")
DEFAULT_NOTION_DELETE_QUEUE = Path("/docker/openclaw-b60d/data/.openclaw/delete-gates/notion")


def _state_dir() -> Path:
    return Path(os.environ.get("PUBLISH_GATE_STATE_DIR", os.environ.get("EMAIL_OUTBOX_ROOT", str(DEFAULT_HOST_ROOT))))


def _tweet_queue() -> Path:
    return Path(os.environ.get("TWEET_DRAFT_QUEUE_DIR", str(DEFAULT_TWEET_QUEUE)))


def _nostr_pending() -> Path:
    return Path(os.environ.get("NOSTR_DRAFT_QUEUE_DIR", str(DEFAULT_NOSTR_PENDING)))


def _nostr_outbox_root() -> Path:
    return _nostr_pending().parent


def _gdrive_delete_queue() -> Path:
    return Path(os.environ.get("GDRIVE_DELETE_QUEUE_DIR", str(DEFAULT_GDRIVE_DELETE_QUEUE)))


def _notion_delete_queue() -> Path:
    return Path(os.environ.get("NOTION_DELETE_QUEUE_DIR", str(DEFAULT_NOTION_DELETE_QUEUE)))


def _workout_write_queue() -> Path:
    return Path(os.environ.get("WORKOUT_WRITE_QUEUE_DIR", str(DEFAULT_WORKOUT_WRITE_QUEUE)))


def _load_state() -> dict:
    p = _state_dir() / STATE_NAME
    if not p.is_file():
        return {"telegram_offset": 0, "by_draft_id": {}}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        data.setdefault("by_draft_id", {})
        if "telegram_offset" not in data:
            lid = int(data.pop("last_update_id", 0) or 0)
            data["telegram_offset"] = 0 if lid == 0 else lid + 1
        data.setdefault("telegram_offset", 0)
        return data
    except (json.JSONDecodeError, OSError):
        return {"telegram_offset": 0, "by_draft_id": {}}


def _save_state(state: dict) -> None:
    root = _state_dir()
    root.mkdir(parents=True, exist_ok=True)
    tmp = root / (STATE_NAME + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(root / STATE_NAME)


def _tg_post(token: str, method: str, payload: dict) -> dict:
    url = f"https://api.telegram.org/bot{token}/{method}"
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = json.load(resp)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Telegram HTTP {e.code}: {err_body}") from e

    if not raw.get("ok"):
        raise RuntimeError(f"Telegram API error: {raw}")
    return raw["result"]


def _parse_allowlist() -> set[int]:
    raw = os.environ.get("TELEGRAM_APPROVAL_CHAT_IDS", "").strip()
    if not raw:
        raise RuntimeError("TELEGRAM_APPROVAL_CHAT_IDS is required")
    out: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if part:
            out.add(int(part))
    if not out:
        raise RuntimeError("TELEGRAM_APPROVAL_CHAT_IDS has no valid IDs")
    return out


def _notify_keyboard(cb_approve: str, cb_reject: str) -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "Approve", "callback_data": cb_approve},
                {"text": "Reject", "callback_data": cb_reject},
            ]
        ]
    }


def _send_notify(token: str, chat_id: int, text: str, keyboard: dict) -> tuple[int, int]:
    if len(text) > 4096:
        text = text[:4090] + "…"
    result = _tg_post(
        token,
        "sendMessage",
        {"chat_id": chat_id, "text": text, "reply_markup": keyboard},
    )
    return int(result["chat"]["id"]), int(result["message_id"])


def _answer_callback(token: str, cq_id: str, text: str) -> None:
    _tg_post(
        token,
        "answerCallbackQuery",
        {"callback_query_id": cq_id, "text": text[:200], "show_alert": False},
    )


def _edit_message(token: str, chat_id: int, message_id: int, text: str) -> None:
    _tg_post(
        token,
        "editMessageText",
        {"chat_id": chat_id, "message_id": message_id, "text": text[:4096]},
    )


def _parse_callback(data: str) -> tuple[str, str, bool] | None:
    """Returns (channel, draft_id, is_approve)."""
    if data.startswith("aw:"):
        return "workout_write", data[3:], True
    if data.startswith("rw:"):
        return "workout_write", data[3:], False
    if data.startswith("ag:"):
        return "gdrive_delete", data[3:], True
    if data.startswith("rgd:"):
        return "gdrive_delete", data[4:], False
    if data.startswith("anp:"):
        return "notion_delete", data[4:], True
    if data.startswith("rnp:"):
        return "notion_delete", data[4:], False
    if data.startswith("at:"):
        return "tweet", data[3:], True
    if data.startswith("rt:"):
        return "tweet", data[3:], False
    if data.startswith("an:"):
        return "nostr", data[3:], True
    if data.startswith("rn:"):
        return "nostr", data[3:], False
    if data.startswith("a:"):
        return "email", data[2:], True
    if data.startswith("r:") and not data.startswith("rt:"):
        return "email", data[2:], False
    return None


def _find_email_path(email_root: Path, draft_id: str) -> Path | None:
    for path in pending_files(email_root):
        rec = load_draft(path)
        if rec and rec.get("id") == draft_id:
            return path
    return None


def _tweet_pending_paths(queue: Path) -> list[Path]:
    if not queue.is_dir():
        return []
    out: list[Path] = []
    for p in sorted(queue.glob("*.json")):
        if p.name.endswith(".published.json") or p.name.endswith(".rejected.json"):
            continue
        out.append(p)
    return out


def _find_tweet_path(queue: Path, draft_id: str) -> Path | None:
    for path in _tweet_pending_paths(queue):
        rec = load_draft(path)
        if rec and rec.get("id") == draft_id:
            return path
    return None


def _find_nostr_path(pending_dir: Path, draft_id: str) -> Path | None:
    if not pending_dir.is_dir():
        return None
    for path in sorted(pending_dir.glob("*.json")):
        rec = load_draft(path)
        if rec and rec.get("id") == draft_id:
            return path
    return None


def _delete_pending_paths(queue_root: Path) -> list[Path]:
    pending = queue_root / "pending"
    if not pending.is_dir():
        return []
    return sorted(pending.glob("*.json"))


def _find_delete_path(queue_root: Path, draft_id: str) -> Path | None:
    for path in _delete_pending_paths(queue_root):
        rec = load_draft(path)
        if rec and rec.get("id") == draft_id:
            return path
    return None


def _post_workout_payload(record: dict) -> tuple[int, str]:
    url = os.environ.get("WORKOUT_WRITE_URL", "").strip()
    if not url:
        raise RuntimeError("WORKOUT_WRITE_URL is required")

    timeout_sec = int(os.environ.get("WORKOUT_WRITE_TIMEOUT_SEC", "30"))
    body = json.dumps(record.get("payload")).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    bearer = os.environ.get("WORKOUT_WRITE_BEARER_TOKEN", "").strip()
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            code = int(resp.getcode())
            raw = resp.read().decode("utf-8", errors="replace")
            return code, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {raw[:500]}") from e


def _workout_finalize(queue_root: Path, path: Path, record: dict, approved: bool, result: str = "", status_code: int = 0) -> None:
    draft_id = record.get("id", path.stem)
    now = datetime.now(timezone.utc).isoformat()
    if approved:
        record["status"] = "written"
        record["written_at"] = now
        record["http_status"] = status_code
        record["result"] = result[:1000]
        dest = queue_root / "sent" / path.name
        dest.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        path.unlink(missing_ok=True)
        event = "workout_written"
    else:
        record["status"] = "rejected"
        record["rejected_at"] = now
        dest = queue_root / "rejected" / path.name
        dest.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        path.unlink(missing_ok=True)
        event = "workout_rejected"
    audit_line(
        queue_root / "audit.log",
        {"event": event, "id": draft_id, "at": now},
    )


def _run_delete_runner(runner: str, record_path: Path) -> str:
    runner = runner.strip()
    if not runner:
        raise RuntimeError("Delete runner not configured")
    cmd = [runner, str(record_path)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180, env=os.environ.copy())
    out = ((r.stdout or "") + "\n" + (r.stderr or "")).strip()
    if r.returncode != 0:
        raise RuntimeError(out or f"runner exit {r.returncode}")
    return out


def _delete_finalize(queue_root: Path, path: Path, record: dict, approved: bool, result: str = "") -> None:
    draft_id = record.get("id", path.stem)
    now = datetime.now(timezone.utc).isoformat()
    if approved:
        record["status"] = "deleted"
        record["deleted_at"] = now
        record["result"] = result
        dest = queue_root / "sent" / path.name
        dest.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        path.unlink(missing_ok=True)
        event = "delete_sent"
    else:
        record["status"] = "rejected"
        record["rejected_at"] = now
        dest = queue_root / "rejected" / path.name
        dest.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        path.unlink(missing_ok=True)
        event = "delete_rejected"
    audit_line(
        queue_root / "audit.log",
        {"event": event, "id": draft_id, "at": now},
    )


def _run_xurl_post(text: str) -> str:
    bin_path = os.environ.get("XURL_REAL_BIN", "/data/bin/xurl-real")
    r = subprocess.run(
        [bin_path, "post", "--text", text],
        capture_output=True,
        text=True,
        timeout=120,
        env=os.environ.copy(),
    )
    out = (r.stdout or "") + (r.stderr or "")
    if r.returncode != 0:
        raise RuntimeError(out or f"xurl exit {r.returncode}")
    return out


def _run_nostr_event(content: str, relays: list[str]) -> None:
    if not relays:
        raise RuntimeError("No relays in draft")
    bin_path = os.environ.get("NAK_REAL_BIN", "/data/bin/nak-real")
    sec = (
        os.environ.get("NOSTR_PRIVATE_HEX_KEY", "").strip()
        or os.environ.get("NOSTR_DAMUS_PRIVATE_HEX_KEY", "").strip()
        or os.environ.get("NOSTR_PRIVATE_KEY", "").strip()
    )
    if not sec:
        raise RuntimeError(
            "No NOSTR private key configured for publish gate "
            "(set NOSTR_PRIVATE_HEX_KEY or NOSTR_DAMUS_PRIVATE_HEX_KEY in publish-gate.env)"
        )
    cmd = [bin_path, "event", "--sec", sec, "-k", "1", "-c", content, *relays]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=os.environ.copy())
    out = ((r.stdout or "") + "\n" + (r.stderr or "")).strip()
    if r.returncode != 0:
        raise RuntimeError(out or f"nak exit {r.returncode}")
    # nak can return RC=0 even when no relay accepted the publish.
    if "success" not in out.lower():
        raise RuntimeError(f"nak did not confirm relay publish success: {out[:400]}")


def _tweet_finalize(path: Path, record: dict, published: bool, tweet_queue: Path, result: str = "") -> None:
    log = tweet_queue / "publish.log"
    draft_id = record.get("id", path.stem)
    if published:
        record["status"] = "published"
        record["published_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        record["result"] = result
        dest = path.with_suffix(".published.json")
        dest.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        path.unlink(missing_ok=True)
        audit_line(
            tweet_queue / "publish-gate-audit.log",
            {"event": "tweet_sent", "id": draft_id, "at": record["published_at"]},
        )
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"{record['published_at']} PUBLISHED {draft_id}\n")
    else:
        record["status"] = "rejected"
        record["rejected_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        dest = path.with_suffix(".rejected.json")
        dest.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        path.unlink(missing_ok=True)
        audit_line(
            tweet_queue / "publish-gate-audit.log",
            {"event": "tweet_rejected", "id": draft_id, "at": record["rejected_at"]},
        )
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"{record['rejected_at']} REJECTED {draft_id}\n")


def _nostr_finalize(path: Path, record: dict, sent: bool, root: Path) -> None:
    draft_id = record.get("id", path.stem)
    if sent:
        record["sent_at"] = datetime.now(timezone.utc).isoformat()
        dest = root / "sent" / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{path.name}"
        dest.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        path.unlink(missing_ok=True)
        audit_line(
            root / "audit.log",
            {"event": "nostr_sent", "id": draft_id, "at": record["sent_at"], "path": str(dest)},
        )
    else:
        dest = root / "rejected" / path.name
        path.rename(dest)
        audit_line(
            root / "audit.log",
            {
                "event": "nostr_rejected",
                "id": draft_id,
                "at": datetime.now(timezone.utc).isoformat(),
                "path": str(dest),
            },
        )


def _resolve_path(
    channel: str,
    draft_id: str,
    email_root: Path,
    tweet_q: Path,
    nostr_p: Path,
    workout_q: Path,
    gdrive_q: Path,
    notion_q: Path,
) -> Path | None:
    if channel == "email":
        return _find_email_path(email_root, draft_id)
    if channel == "tweet":
        return _find_tweet_path(tweet_q, draft_id)
    if channel == "nostr":
        return _find_nostr_path(nostr_p, draft_id)
    if channel == "workout_write":
        return _find_delete_path(workout_q, draft_id)
    if channel == "gdrive_delete":
        return _find_delete_path(gdrive_q, draft_id)
    if channel == "notion_delete":
        return _find_delete_path(notion_q, draft_id)
    return None


def _prune_state(
    state: dict,
    email_root: Path,
    tweet_q: Path,
    nostr_p: Path,
    workout_q: Path,
    gdrive_q: Path,
    notion_q: Path,
) -> None:
    for did, meta in list(state.get("by_draft_id", {}).items()):
        ch = (meta or {}).get("channel", "email")
        if _resolve_path(ch, did, email_root, tweet_q, nostr_p, workout_q, gdrive_q, notion_q) is None:
            state["by_draft_id"].pop(did, None)


def _process_updates(
    token: str,
    state: dict,
    allowlist: set[int],
    email_root: Path,
    tweet_q: Path,
    nostr_p: Path,
    nostr_root: Path,
    workout_q: Path,
    gdrive_q: Path,
    notion_q: Path,
) -> None:
    offset = int(state.get("telegram_offset", 0))
    try:
        result = _tg_post(
            token,
            "getUpdates",
            {
                "offset": offset,
                "timeout": 25,
                "allowed_updates": ["callback_query"],
            },
        )
    except Exception as e:
        print(f"getUpdates error: {e}", file=sys.stderr)
        return

    if not result:
        return

    state["telegram_offset"] = result[-1]["update_id"] + 1

    for upd in result:
        cq = upd.get("callback_query")
        if not cq:
            continue

        if cq["from"]["id"] not in allowlist:
            _answer_callback(token, cq["id"], "Not authorized.")
            continue

        parsed = _parse_callback(cq.get("data") or "")
        if parsed is None:
            _answer_callback(token, cq["id"], "Unknown action.")
            continue

        channel, draft_id, is_approve = parsed
        chat_id = cq["message"]["chat"]["id"]
        message_id = cq["message"]["message_id"]

        path = _resolve_path(channel, draft_id, email_root, tweet_q, nostr_p, workout_q, gdrive_q, notion_q)
        if path is None:
            _answer_callback(token, cq["id"], "Draft gone.")
            try:
                _edit_message(token, chat_id, message_id, "Draft no longer pending.")
            except Exception:
                pass
            state["by_draft_id"].pop(draft_id, None)
            continue

        record = load_draft(path)
        if record is None:
            _answer_callback(token, cq["id"], "Invalid JSON.")
            continue

        try:
            if channel == "email":
                if is_approve:
                    send_mail(record)
                    finalize_sent(email_root, path, record)
                    _answer_callback(token, cq["id"], "Sent.")
                    _edit_message(token, chat_id, message_id, f"Email sent.\nTo: {record.get('to','')}")
                else:
                    finalize_rejected(email_root, path, record)
                    _answer_callback(token, cq["id"], "Rejected.")
                    _edit_message(token, chat_id, message_id, "Email rejected.")
            elif channel == "tweet":
                text = record.get("text", "")
                if is_approve:
                    out = _run_xurl_post(text)
                    _tweet_finalize(path, record, True, tweet_q, result=out)
                    _answer_callback(token, cq["id"], "Posted.")
                    _edit_message(token, chat_id, message_id, f"Posted to X.\n{text[:500]}")
                else:
                    _tweet_finalize(path, record, False, tweet_q)
                    _answer_callback(token, cq["id"], "Rejected.")
                    _edit_message(token, chat_id, message_id, "Tweet draft rejected.")
            elif channel == "nostr":
                if is_approve:
                    _run_nostr_event(record.get("content", ""), list(record.get("relays") or []))
                    _nostr_finalize(path, record, True, nostr_root)
                    _answer_callback(token, cq["id"], "Published.")
                    _edit_message(token, chat_id, message_id, "Nostr note published.")
                else:
                    _nostr_finalize(path, record, False, nostr_root)
                    _answer_callback(token, cq["id"], "Rejected.")
                    _edit_message(token, chat_id, message_id, "Nostr draft rejected.")
            elif channel == "workout_write":
                if is_approve:
                    status_code, response = _post_workout_payload(record)
                    _workout_finalize(workout_q, path, record, True, result=response, status_code=status_code)
                    _answer_callback(token, cq["id"], "Written.")
                    _edit_message(token, chat_id, message_id, f"Workout write approved.\nHTTP {status_code}")
                else:
                    _workout_finalize(workout_q, path, record, False)
                    _answer_callback(token, cq["id"], "Rejected.")
                    _edit_message(token, chat_id, message_id, "Workout write rejected.")
            elif channel == "gdrive_delete":
                if is_approve:
                    out = _run_delete_runner(os.environ.get("GDRIVE_DELETE_RUNNER", ""), path)
                    _delete_finalize(gdrive_q, path, record, True, result=out)
                    _answer_callback(token, cq["id"], "Deleted.")
                    _edit_message(token, chat_id, message_id, "Google Drive delete approved and executed.")
                else:
                    _delete_finalize(gdrive_q, path, record, False)
                    _answer_callback(token, cq["id"], "Rejected.")
                    _edit_message(token, chat_id, message_id, "Google Drive delete rejected.")
            elif channel == "notion_delete":
                if is_approve:
                    out = _run_delete_runner(os.environ.get("NOTION_DELETE_RUNNER", ""), path)
                    _delete_finalize(notion_q, path, record, True, result=out)
                    _answer_callback(token, cq["id"], "Deleted.")
                    _edit_message(token, chat_id, message_id, "Notion delete approved and executed.")
                else:
                    _delete_finalize(notion_q, path, record, False)
                    _answer_callback(token, cq["id"], "Rejected.")
                    _edit_message(token, chat_id, message_id, "Notion delete rejected.")
        except Exception as e:
            _answer_callback(token, cq["id"], f"Failed: {e}")
            audit_line(
                email_root / "audit.log",
                {
                    "event": f"{channel}_gate_failed",
                    "id": draft_id,
                    "error": str(e),
                    "at": datetime.now(timezone.utc).isoformat(),
                },
            )
            print(f"handler error: {e}", file=sys.stderr)
            continue

        state["by_draft_id"].pop(draft_id, None)


def _notify_chat_id(allowlist: set[int]) -> int:
    if len(allowlist) == 1:
        return next(iter(allowlist))
    cid = int(os.environ.get("TELEGRAM_NOTIFY_CHAT_ID", "").strip() or 0)
    if not cid:
        raise RuntimeError("TELEGRAM_NOTIFY_CHAT_ID required when multiple approvers")
    return cid


def _scan_email(token: str, state: dict, allowlist: set[int], email_root: Path) -> None:
    chat_id = _notify_chat_id(allowlist)
    for path in pending_files(email_root):
        record = load_draft(path)
        if not record or not record.get("id"):
            continue
        draft_id = record["id"]
        if draft_id in state["by_draft_id"]:
            continue
        body = record.get("body", "")
        text = (
            f"Email draft\nFile: {path.name}\nTo: {record.get('to','')}\n"
            f"Subject: {record.get('subject','')}\n\n{body[:TELEGRAM_TEXT_MAX]}"
        )
        if len(body) > TELEGRAM_TEXT_MAX:
            text += "\n… (truncated)"
        try:
            c_id, m_id = _send_notify(
                token,
                chat_id,
                text,
                _notify_keyboard(f"a:{draft_id}", f"r:{draft_id}"),
            )
        except Exception as e:
            print(f"email notify {path.name}: {e}", file=sys.stderr)
            continue
        state["by_draft_id"][draft_id] = {
            "channel": "email",
            "file": path.name,
            "chat_id": c_id,
            "message_id": m_id,
        }
        audit(
            email_root,
            {
                "event": "telegram_notified",
                "channel": "email",
                "id": draft_id,
                "at": datetime.now(timezone.utc).isoformat(),
            },
        )


def _scan_tweets(token: str, state: dict, allowlist: set[int], tweet_q: Path) -> None:
    if not tweet_q.is_dir():
        return
    chat_id = _notify_chat_id(allowlist)
    for path in _tweet_pending_paths(tweet_q):
        record = load_draft(path)
        if not record or not record.get("id"):
            continue
        draft_id = record["id"]
        if draft_id in state["by_draft_id"]:
            continue
        text_body = record.get("text", "")
        msg = f"X / Twitter draft\nFile: {path.name}\n\n{text_body[:TELEGRAM_TEXT_MAX]}"
        if len(text_body) > TELEGRAM_TEXT_MAX:
            msg += "\n… (truncated)"
        try:
            c_id, m_id = _send_notify(
                token,
                chat_id,
                msg,
                _notify_keyboard(f"at:{draft_id}", f"rt:{draft_id}"),
            )
        except Exception as e:
            print(f"tweet notify {path.name}: {e}", file=sys.stderr)
            continue
        state["by_draft_id"][draft_id] = {
            "channel": "tweet",
            "file": path.name,
            "chat_id": c_id,
            "message_id": m_id,
        }
        audit_line(
            tweet_q / "publish-gate-audit.log",
            {
                "event": "telegram_notified",
                "channel": "tweet",
                "id": draft_id,
                "at": datetime.now(timezone.utc).isoformat(),
            },
        )


def _scan_nostr(token: str, state: dict, allowlist: set[int], nostr_p: Path) -> None:
    if not nostr_p.is_dir():
        return
    chat_id = _notify_chat_id(allowlist)
    for path in sorted(nostr_p.glob("*.json")):
        record = load_draft(path)
        if not record or not record.get("id"):
            continue
        draft_id = record["id"]
        if draft_id in state["by_draft_id"]:
            continue
        content = record.get("content", "")
        relays = record.get("relays") or []
        msg = (
            f"Nostr kind:1 draft\nFile: {path.name}\nRelays: {relays}\n\n"
            f"{content[:TELEGRAM_TEXT_MAX]}"
        )
        if len(content) > TELEGRAM_TEXT_MAX:
            msg += "\n… (truncated)"
        try:
            c_id, m_id = _send_notify(
                token,
                chat_id,
                msg,
                _notify_keyboard(f"an:{draft_id}", f"rn:{draft_id}"),
            )
        except Exception as e:
            print(f"nostr notify {path.name}: {e}", file=sys.stderr)
            continue
        state["by_draft_id"][draft_id] = {
            "channel": "nostr",
            "file": path.name,
            "chat_id": c_id,
            "message_id": m_id,
        }
        audit_line(
            _nostr_outbox_root() / "audit.log",
            {
                "event": "telegram_notified",
                "channel": "nostr",
                "id": draft_id,
                "at": datetime.now(timezone.utc).isoformat(),
            },
        )


def _scan_workout_write(token: str, state: dict, allowlist: set[int], queue_root: Path) -> None:
    chat_id = _notify_chat_id(allowlist)
    for path in _delete_pending_paths(queue_root):
        record = load_draft(path)
        if not record or not record.get("id"):
            continue
        draft_id = record["id"]
        if draft_id in state["by_draft_id"]:
            continue
        payload_preview = json.dumps(record.get("payload"), ensure_ascii=False)
        msg = (
            "Workout write request\n"
            f"File: {path.name}\n"
            f"Label: {record.get('label', '')}\n"
            f"Reason: {record.get('reason', '')}\n\n"
            f"{payload_preview[:TELEGRAM_TEXT_MAX]}"
        )
        if len(payload_preview) > TELEGRAM_TEXT_MAX:
            msg += "\n… (truncated)"
        try:
            c_id, m_id = _send_notify(
                token,
                chat_id,
                msg,
                _notify_keyboard(f"aw:{draft_id}", f"rw:{draft_id}"),
            )
        except Exception as e:
            print(f"workout write notify {path.name}: {e}", file=sys.stderr)
            continue
        state["by_draft_id"][draft_id] = {
            "channel": "workout_write",
            "file": path.name,
            "chat_id": c_id,
            "message_id": m_id,
        }
        audit_line(
            queue_root / "audit.log",
            {
                "event": "telegram_notified",
                "channel": "workout_write",
                "id": draft_id,
                "at": datetime.now(timezone.utc).isoformat(),
            },
        )


def _scan_gdrive_delete(token: str, state: dict, allowlist: set[int], queue_root: Path) -> None:
    chat_id = _notify_chat_id(allowlist)
    for path in _delete_pending_paths(queue_root):
        record = load_draft(path)
        if not record or not record.get("id"):
            continue
        draft_id = record["id"]
        if draft_id in state["by_draft_id"]:
            continue
        msg = (
            "Google Drive delete request\n"
            f"File: {path.name}\n"
            f"Drive file id: {record.get('target_id', '')}\n"
            f"Label: {record.get('target_label', '')}\n"
            f"Reason: {record.get('reason', '')}"
        )
        try:
            c_id, m_id = _send_notify(
                token,
                chat_id,
                msg[:TELEGRAM_TEXT_MAX],
                _notify_keyboard(f"ag:{draft_id}", f"rgd:{draft_id}"),
            )
        except Exception as e:
            print(f"gdrive delete notify {path.name}: {e}", file=sys.stderr)
            continue
        state["by_draft_id"][draft_id] = {
            "channel": "gdrive_delete",
            "file": path.name,
            "chat_id": c_id,
            "message_id": m_id,
        }
        audit_line(
            queue_root / "audit.log",
            {
                "event": "telegram_notified",
                "channel": "gdrive_delete",
                "id": draft_id,
                "at": datetime.now(timezone.utc).isoformat(),
            },
        )


def _scan_notion_delete(token: str, state: dict, allowlist: set[int], queue_root: Path) -> None:
    chat_id = _notify_chat_id(allowlist)
    for path in _delete_pending_paths(queue_root):
        record = load_draft(path)
        if not record or not record.get("id"):
            continue
        draft_id = record["id"]
        if draft_id in state["by_draft_id"]:
            continue
        msg = (
            "Notion delete request\n"
            f"File: {path.name}\n"
            f"Page id: {record.get('target_id', '')}\n"
            f"Label: {record.get('target_label', '')}\n"
            f"Reason: {record.get('reason', '')}"
        )
        try:
            c_id, m_id = _send_notify(
                token,
                chat_id,
                msg[:TELEGRAM_TEXT_MAX],
                _notify_keyboard(f"anp:{draft_id}", f"rnp:{draft_id}"),
            )
        except Exception as e:
            print(f"notion delete notify {path.name}: {e}", file=sys.stderr)
            continue
        state["by_draft_id"][draft_id] = {
            "channel": "notion_delete",
            "file": path.name,
            "chat_id": c_id,
            "message_id": m_id,
        }
        audit_line(
            queue_root / "audit.log",
            {
                "event": "telegram_notified",
                "channel": "notion_delete",
                "id": draft_id,
                "at": datetime.now(timezone.utc).isoformat(),
            },
        )


def main() -> int:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("TELEGRAM_BOT_TOKEN required", file=sys.stderr)
        return 2
    try:
        allowlist = _parse_allowlist()
    except Exception as e:
        print(e, file=sys.stderr)
        return 2

    email_root = Path(os.environ.get("EMAIL_OUTBOX_ROOT", str(DEFAULT_HOST_ROOT)))
    tweet_q = _tweet_queue()
    nostr_p = _nostr_pending()
    nostr_root = _nostr_outbox_root()
    workout_q = _workout_write_queue()
    gdrive_q = _gdrive_delete_queue()
    notion_q = _notion_delete_queue()

    for d in (
        email_root / "pending",
        email_root / "sent",
        email_root / "rejected",
        tweet_q,
        nostr_p,
        nostr_root / "sent",
        nostr_root / "rejected",
        workout_q / "pending",
        workout_q / "sent",
        workout_q / "rejected",
        gdrive_q / "pending",
        gdrive_q / "sent",
        gdrive_q / "rejected",
        notion_q / "pending",
        notion_q / "sent",
        notion_q / "rejected",
    ):
        d.mkdir(parents=True, exist_ok=True)

    if not email_root.is_dir():
        print(f"EMAIL_OUTBOX_ROOT not a directory: {email_root}", file=sys.stderr)
        return 2

    if os.environ.get("TELEGRAM_DELETE_WEBHOOK", "").strip() in ("1", "true", "yes"):
        try:
            _tg_post(token, "deleteWebhook", {})
            print("deleteWebhook ok", file=sys.stderr)
        except Exception as e:
            print(f"deleteWebhook: {e}", file=sys.stderr)

    print(
        "telegram_approval_daemon: email + tweet + nostr + workout_write + gdrive_delete + notion_delete. Ctrl+C to stop.",
        file=sys.stderr,
    )

    while True:
        state = _load_state()
        try:
            _prune_state(state, email_root, tweet_q, nostr_p, workout_q, gdrive_q, notion_q)
            _process_updates(token, state, allowlist, email_root, tweet_q, nostr_p, nostr_root, workout_q, gdrive_q, notion_q)
            _scan_email(token, state, allowlist, email_root)
            _scan_tweets(token, state, allowlist, tweet_q)
            _scan_nostr(token, state, allowlist, nostr_p)
            _scan_workout_write(token, state, allowlist, workout_q)
            _scan_gdrive_delete(token, state, allowlist, gdrive_q)
            _scan_notion_delete(token, state, allowlist, notion_q)
        except Exception as e:
            print(f"loop error: {e}", file=sys.stderr)
        _save_state(state)
        time.sleep(0.5)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Stopped.", file=sys.stderr)
        raise SystemExit(0)
