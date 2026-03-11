#!/usr/bin/env python3
"""
Rebuild wellness.raw_* from source tables (autopopulate) then rebuild
normalised tables and daily_features from raw_* (02_daily_features.sql).
Run after ingest or when source data changed. Incremental by default (append to raw_*).
Usage: python consolidate.py [--db PATH] [--clear-raw] [--workspace PATH]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

try:
    import duckdb
except ImportError:
    print("duckdb not installed; run: pip install duckdb", file=sys.stderr)
    sys.exit(1)


def _script_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def _default_workspace() -> str:
    # scripts/ is inside skills/health-analytics/; workspace root is two levels up from script dir
    return os.path.normpath(os.path.join(_script_dir(), "..", "..", ".."))


def _default_db(workspace: str) -> str:
    return os.path.join(workspace, "data", "health", "duckdb", "health.duckdb")


def run_autopopulate(db_path: str, workspace: str, clear_raw: bool) -> dict:
    # Script lives inside the skill (weltory_tips moved under skills/health-analytics/)
    skill_root = os.path.normpath(os.path.join(_script_dir(), ".."))
    ap_script = os.path.join(skill_root, "weltory_tips", "auto_populate_raw_tables.py")
    if not os.path.isfile(ap_script):
        raise FileNotFoundError(
            f"auto_populate_raw_tables.py not found at {ap_script}; ensure weltory_tips is inside the skill"
        )
    cmd = [sys.executable, ap_script, db_path, "--schema", "wellness"]
    if clear_raw:
        cmd.append("--clear-targets")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=workspace)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"autopopulate failed with code {result.returncode}")
    try:
        return json.loads(result.stdout)
    except Exception:
        return {"output": result.stdout}


def run_02_daily_features(db_path: str) -> None:
    sql_path = os.path.join(_script_dir(), "02_daily_features.sql")
    if not os.path.isfile(sql_path):
        raise FileNotFoundError(f"02_daily_features.sql not found at {sql_path}")
    with open(sql_path, "r", encoding="utf-8") as f:
        sql = f.read()
    con = duckdb.connect(db_path)
    try:
        # Run entire script so TEMP tables persist across statements
        con.execute(sql)
    finally:
        con.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Consolidate source tables into raw_* and daily_features")
    parser.add_argument("--db", default=None, help="DuckDB path (default: <workspace>/data/health/duckdb/health.duckdb)")
    parser.add_argument("--workspace", default=None, help="Workspace root (default: parent of skills/health-analytics)")
    parser.add_argument("--clear-raw", action="store_true", help="Clear wellness.raw_* before autopopulate (full rebuild)")
    args = parser.parse_args()

    workspace = os.path.abspath(args.workspace or _default_workspace())
    db_path = os.path.abspath(args.db or _default_db(workspace))

    if not os.path.isfile(db_path):
        print(f"Database not found: {db_path}", file=sys.stderr)
        return 1

    try:
        report = run_autopopulate(db_path, workspace, args.clear_raw)
        print("Autopopulate:", json.dumps(report.get("inserted_rows", report), indent=2))
        run_02_daily_features(db_path)
        print("daily_features rebuilt.")
        return 0
    except Exception as e:
        print(str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
