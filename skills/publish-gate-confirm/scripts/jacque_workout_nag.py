#!/usr/bin/env python3
"""
Nag Mauro in Jacque's style when workout gap is too long.

Logic:
- Read latest workout date from the workout Notion read endpoint (`/last`).
- If latest workout is older than N days, send a Telegram message.
- Keep sending reminders during the day until a workout appears for today.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

DEFAULT_LAST_URL = "https://cool-shape-6be4letreinononotion.x95ghbs9dk.workers.dev/last"
DEFAULT_STATE_PATH = "/writer-state/jacque-workout-nag-state.json"
DEFAULT_OPENCLAW_CONFIG = "/data/.openclaw/openclaw.json"
DEFAULT_TZ = "America/Sao_Paulo"
DEFAULT_GRACE_DAYS = 2
DEFAULT_MIN_HOURS_BETWEEN_NAGS = 3
DEFAULT_MEASURES_INTERVAL_DAYS = 90


@dataclass
class Config:
    last_url: str
    state_path: Path
    openclaw_config_path: Path
    tz: ZoneInfo
    grace_days: int
    min_hours_between_nags: int
    measures_interval_days: int
    token: str
    chat_id: int | None


def _read_json_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return raw
    except (OSError, json.JSONDecodeError):
        return {}
    return {}


def _token_from_openclaw_config(path: Path) -> str:
    cfg = _read_json_file(path)
    channels = cfg.get("channels")
    if not isinstance(channels, dict):
        return ""
    telegram = channels.get("telegram")
    if not isinstance(telegram, dict):
        return ""
    token = telegram.get("botToken")
    return str(token).strip() if token else ""


def _load_config() -> Config:
    openclaw_config_path = Path(os.environ.get("JACQUE_OPENCLAW_CONFIG", DEFAULT_OPENCLAW_CONFIG))
    token = (
        os.environ.get("JACQUE_BOT_TOKEN", "").strip()
        or os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        or _token_from_openclaw_config(openclaw_config_path)
    )
    if not token:
        raise RuntimeError(
            "Telegram bot token not found. Set JACQUE_BOT_TOKEN/TELEGRAM_BOT_TOKEN or configure channels.telegram.botToken in openclaw.json."
        )

    chat_raw = os.environ.get("JACQUE_CHAT_ID", "").strip() or os.environ.get("TELEGRAM_NOTIFY_CHAT_ID", "").strip()
    if not chat_raw:
        allowlist = os.environ.get("TELEGRAM_APPROVAL_CHAT_IDS", "").strip()
        if allowlist:
            chat_raw = allowlist.split(",")[0].strip()

    return Config(
        last_url=os.environ.get("JACQUE_WORKOUT_LAST_URL", DEFAULT_LAST_URL).strip(),
        state_path=Path(os.environ.get("JACQUE_STATE_PATH", DEFAULT_STATE_PATH)),
        openclaw_config_path=openclaw_config_path,
        tz=ZoneInfo(os.environ.get("JACQUE_TIMEZONE", DEFAULT_TZ)),
        grace_days=int(os.environ.get("JACQUE_GRACE_DAYS", str(DEFAULT_GRACE_DAYS))),
        min_hours_between_nags=int(
            os.environ.get("JACQUE_MIN_HOURS_BETWEEN_NAGS", str(DEFAULT_MIN_HOURS_BETWEEN_NAGS))
        ),
        measures_interval_days=int(
            os.environ.get("JACQUE_MEASURES_INTERVAL_DAYS", str(DEFAULT_MEASURES_INTERVAL_DAYS))
        ),
        token=token,
        chat_id=int(chat_raw) if chat_raw else None,
    )


def _http_json(url: str, timeout: int = 20) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            # Cloudflare blocks Python's default UA on this endpoint.
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) OpenClawWorkoutNag/1.0",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _send_telegram(token: str, chat_id: int, text: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text[:4096]}
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API error: {data}")


def _load_state(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _latest_workout_date(payload: dict) -> datetime.date:
    gyms = payload.get("gyms") or {}
    all_dates: list[datetime.date] = []
    for rows in gyms.values():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            raw = str(row.get("date", "")).strip()
            if not raw:
                continue
            all_dates.append(datetime.strptime(raw, "%Y-%m-%d").date())
    if not all_dates:
        raise RuntimeError("No workout dates found in /last payload")
    return max(all_dates)


def _build_message(days_without: int, last_date: str, attempt: int) -> str:
    templates = [
        "Psiu... so pra lembrar treino hoje. 😬",
        "Agora serio... to ate com saudades. Vai treinar hoje, sem sumir.",
        "Nao reclama... ta melhor que eu! Arruma 40 min e faz.",
        "Tem que forcar a barra. Crianca da trabalho e voce precisa de resistencia 😅",
        "Sem drama. Um passo por vez. Hoje tem treino sim.",
    ]
    opener = templates[attempt % len(templates)]
    if attempt > 0:
        opener = f"{opener}\n\n(voltei pra encher o saco ate voce treinar hoje)"
    return (
        f"{opener}\n\n"
        f"Ultimo treino no Notion: {last_date} ({days_without} dias sem treino).\n"
        "Me manda um ok quando terminar o treino de hoje."
    )


def _maybe_send_measures_reminder(cfg: Config, state: dict, now: datetime, chat_id: int) -> None:
    today = now.date()
    today_str = today.isoformat()

    last_raw = str(state.get("last_measures_reminder_date", "")).strip()
    if not last_raw:
        # First run: initialize anchor without notifying.
        state["last_measures_reminder_date"] = today_str
        return

    try:
        last_date = datetime.strptime(last_raw, "%Y-%m-%d").date()
    except ValueError:
        state["last_measures_reminder_date"] = today_str
        return

    if today == last_date:
        return

    if (today - last_date).days < cfg.measures_interval_days:
        return

    msg = (
        "Psiu... ja bateu 90 dias das ultimas medidas.\n\n"
        "Hoje voce vai tirar e me mandar:\n"
        "- cintura\n"
        "- peito\n"
        "- braco\n"
        "- coxa\n"
        "- peso\n\n"
        "Sem drama. Um passo por vez."
    )
    _send_telegram(cfg.token, chat_id, msg)
    state["last_measures_reminder_date"] = today_str


def main() -> int:
    cfg = _load_config()
    now = datetime.now(cfg.tz)
    today = now.date()
    today_str = today.isoformat()

    state = _load_state(cfg.state_path)
    chat_id = cfg.chat_id or int(state.get("chat_id", 0) or 0) or None
    if chat_id is None:
        raise RuntimeError(
            "Chat ID missing. Set JACQUE_CHAT_ID once (it will be saved in state) or TELEGRAM_NOTIFY_CHAT_ID."
        )

    _maybe_send_measures_reminder(cfg, state, now, chat_id)
    payload = _http_json(cfg.last_url)
    last_workout = _latest_workout_date(payload)
    last_workout_str = last_workout.isoformat()
    gap_days = (today - last_workout).days

    state["last_seen_workout_date"] = last_workout_str
    state["last_checked_at"] = now.isoformat()

    if last_workout == today:
        state["last_ok_day"] = today_str
        state["nag_attempt_today"] = 0
        _save_state(cfg.state_path, state)
        print(f"OK: trained today ({today_str}).")
        return 0

    if gap_days <= cfg.grace_days:
        state["nag_attempt_today"] = 0
        _save_state(cfg.state_path, state)
        print(f"OK: gap {gap_days} days <= grace {cfg.grace_days}.")
        return 0

    last_nag_at_raw = str(state.get("last_nag_at", "")).strip()
    last_nag_day = str(state.get("last_nag_day", "")).strip()
    attempts_today = int(state.get("nag_attempt_today", 0))

    if last_nag_at_raw:
        try:
            last_nag_at = datetime.fromisoformat(last_nag_at_raw)
            elapsed_h = (now - last_nag_at).total_seconds() / 3600.0
            if last_nag_day == today_str and elapsed_h < cfg.min_hours_between_nags:
                _save_state(cfg.state_path, state)
                print(
                    f"SKIP: last nag {elapsed_h:.1f}h ago; minimum is {cfg.min_hours_between_nags}h."
                )
                return 0
        except ValueError:
            pass

    if last_nag_day != today_str:
        attempts_today = 0

    msg = _build_message(gap_days, last_workout_str, attempts_today)
    _send_telegram(cfg.token, chat_id, msg)

    state["last_nag_at"] = now.isoformat()
    state["last_nag_day"] = today_str
    state["nag_attempt_today"] = attempts_today + 1
    state["chat_id"] = chat_id
    _save_state(cfg.state_path, state)
    print(f"NAG_SENT: day={today_str} attempt={state['nag_attempt_today']} gap_days={gap_days}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {e.code}: {body[:400]}")
