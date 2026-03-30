#!/usr/bin/env python3
"""Deprecated entrypoint: runs the unified daemon in publish-gate-confirm."""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

_skills = Path(__file__).resolve().parents[2]
_daemon = _skills / "publish-gate-confirm" / "scripts" / "telegram_approval_daemon.py"
if not _daemon.is_file():
    print(f"email-outbox-telegram: missing {_daemon}", file=sys.stderr)
    raise SystemExit(2)
runpy.run_path(str(_daemon), run_name="__main__")
