#!/usr/bin/env python3
"""
Create the health DuckDB and all tables: wellness schema (01_schema.sql)
plus source tables for ingest (sleep_phases, weltory_rr, import_log).
Paths: default DB at data/health/duckdb/health.duckdb relative to workspace.
Exit 0 on success. Idempotent: does not drop existing DB.
"""
from __future__ import annotations

import argparse
import os
import sys

try:
    import duckdb
except ImportError:
    print("duckdb not installed; run: pip install duckdb", file=sys.stderr)
    sys.exit(1)


def _script_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def _default_workspace() -> str:
    return os.path.normpath(os.path.join(_script_dir(), "..", "..", ".."))


def _default_db(workspace: str) -> str:
    return os.path.join(workspace, "data", "health", "duckdb", "health.duckdb")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create health DuckDB and tables")
    parser.add_argument("--db", default=None, help="DuckDB path")
    parser.add_argument("--workspace", default=None, help="Workspace root")
    args = parser.parse_args()

    workspace = os.path.abspath(args.workspace or _default_workspace())
    db_path = os.path.abspath(args.db or _default_db(workspace))

    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    con = duckdb.connect(db_path)

    # Run 01_schema.sql (wellness schema + raw_* + normalised + daily_features)
    schema_path = os.path.join(_script_dir(), "01_schema.sql")
    if not os.path.isfile(schema_path):
        print(f"01_schema.sql not found at {schema_path}", file=sys.stderr)
        return 1
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    for raw in schema_sql.split(";"):
        s = raw.strip()
        while s and (s.startswith("--") or s.split("\n")[0].strip() == ""):
            s = "\n".join(s.split("\n")[1:]).strip() if "\n" in s else ""
        if not s:
            continue
        con.execute(s)

    # Source tables used by ingest; autopopulate reads these into wellness.raw_*
    con.execute("""
        CREATE TABLE IF NOT EXISTS sleep_phases (
            start_date VARCHAR,
            end_date VARCHAR,
            value VARCHAR,
            source_name VARCHAR,
            creation_date VARCHAR,
            device VARCHAR,
            source_version VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS weltory_rr (
            id VARCHAR,
            timestamp TIMESTAMP,
            date_local DATE,
            rmssd DOUBLE,
            sdnn DOUBLE,
            pnn50 DOUBLE,
            lf_hf_ratio DOUBLE,
            mean_hr DOUBLE,
            resting_hr DOUBLE,
            measurement_quality DOUBLE,
            time_start VARCHAR,
            time_end VARCHAR,
            duration DOUBLE,
            bpm DOUBLE,
            context_arousal_percent DOUBLE,
            context_energy_percent DOUBLE,
            resilience DOUBLE,
            source_name VARCHAR,
            device_name VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS import_log (
            source VARCHAR,
            path VARCHAR,
            ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            rows_inserted INTEGER,
            rows_skipped INTEGER,
            detail VARCHAR,
            file_mtime DOUBLE,
            file_size BIGINT
        )
    """)
    # Add verification columns if missing (existing DBs created before we had these)
    try:
        con.execute("ALTER TABLE import_log ADD COLUMN file_mtime DOUBLE")
    except Exception:
        pass
    try:
        con.execute("ALTER TABLE import_log ADD COLUMN file_size BIGINT")
    except Exception:
        pass
    # Apple Health quantity aggregates (steps, exercise, energy) — ingest fills from export.xml
    con.execute("""
        CREATE TABLE IF NOT EXISTS apple_quantity_daily (
            date_local DATE,
            steps_daily DOUBLE,
            exercise_minutes_daily DOUBLE,
            active_kcal_daily DOUBLE,
            basal_kcal_daily DOUBLE
        )
    """)

    con.close()
    print("DB initialized:", db_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
