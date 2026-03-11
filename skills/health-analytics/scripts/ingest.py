#!/usr/bin/env python3
"""
Ingest one ZIP export (Apple Health or Weltory) into the health database,
then rebuild consolidated tables (wellness.raw_* and daily_features).
Usage: python ingest.py --zip <path> [--db PATH] [--workspace PATH] [--no-consolidate]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime

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


def detect_zip_type(zip_path: str) -> str:
    with zipfile.ZipFile(zip_path, "r") as z:
        names = z.namelist()
    if any("exportar.xml" in n or "export.xml" in n.lower() for n in names):
        return "apple_health"
    if any("rr.json" in n for n in names):
        return "weltory"
    raise ValueError(f"Unknown ZIP format: no exportar.xml nor rr.json in {zip_path}")


# ---- Apple Health ----

# Quantity types in export.xml → metric (see references/apple_health_quantities.md)
APPLE_QUANTITY_TYPES = {
    "HKQuantityTypeIdentifierStepCount": "steps",
    "HKQuantityTypeIdentifierAppleExerciseTime": "exercise_minutes",
    "HKQuantityTypeIdentifierActiveEnergyBurned": "active_kcal",
    "HKQuantityTypeIdentifierBasalEnergyBurned": "basal_kcal",
}


def _date_from_apple_ts(s: str | None):
    """Parse startDate to date_local (YYYY-MM-DD). Apple: '2020-01-06 00:14:28 -0300'."""
    if not s or not s.strip():
        return None
    s = s.strip()
    if len(s) >= 10:
        return s[:10]
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date().isoformat()
    except Exception:
        return None


def _parse_quantity_records(xml_path: str):
    """Stream-parse export.xml for the four quantity types; yield (date_local, metric, value)."""
    for event, elem in ET.iterparse(xml_path, events=("end",)):
        if elem.tag != "Record":
            elem.clear()
            continue
        rtype = elem.get("type")
        if rtype not in APPLE_QUANTITY_TYPES:
            elem.clear()
            continue
        date_local = _date_from_apple_ts(elem.get("startDate"))
        if not date_local:
            elem.clear()
            continue
        try:
            value = float(elem.get("value") or 0)
        except (TypeError, ValueError):
            elem.clear()
            continue
        metric = APPLE_QUANTITY_TYPES[rtype]
        elem.clear()
        yield (date_local, metric, value)


def _parse_sleep_records(xml_path: str):
    for event, elem in ET.iterparse(xml_path, events=("end",)):
        if elem.tag != "Record":
            elem.clear()
            continue
        if elem.get("type") != "HKCategoryTypeIdentifierSleepAnalysis":
            elem.clear()
            continue
        value = elem.get("value") or ""
        if not value.startswith("HKCategoryValueSleepAnalysis"):
            elem.clear()
            continue
        yield {
            "start_date": elem.get("startDate"),
            "end_date": elem.get("endDate"),
            "value": value,
            "source_name": elem.get("sourceName") or "",
            "creation_date": elem.get("creationDate"),
            "device": elem.get("device") or "",
            "source_version": elem.get("sourceVersion") or "",
        }
        elem.clear()


def ingest_apple_health(con: duckdb.DuckDBPyConnection, zip_path: str, extract_dir: str) -> dict:
    with zipfile.ZipFile(zip_path, "r") as z:
        xml_name = None
        for n in z.namelist():
            if n.endswith("exportar.xml") or (n.endswith(".xml") and "export" in n.lower()):
                xml_name = n
                break
        if not xml_name:
            raise FileNotFoundError(f"No export XML found in {zip_path}")
        z.extract(xml_name, extract_dir)
    xml_path = os.path.join(extract_dir, xml_name)

    con.execute("DELETE FROM sleep_phases")
    batch_size = 5000
    batch = []
    total = 0

    for rec in _parse_sleep_records(xml_path):
        batch.append((
            rec["start_date"],
            rec["end_date"],
            rec["value"],
            rec["source_name"],
            rec["creation_date"],
            rec["device"],
            rec["source_version"],
        ))
        if len(batch) >= batch_size:
            con.executemany(
                "INSERT INTO sleep_phases (start_date, end_date, value, source_name, creation_date, device, source_version) VALUES (?, ?, ?, ?, ?, ?, ?)",
                batch,
            )
            total += len(batch)
            batch = []

    if batch:
        con.executemany(
            "INSERT INTO sleep_phases (start_date, end_date, value, source_name, creation_date, device, source_version) VALUES (?, ?, ?, ?, ?, ?, ?)",
            batch,
        )
        total += len(batch)

    # Quantity types: aggregate by date_local and fill apple_quantity_daily (see references/apple_health_quantities.md)
    agg = defaultdict(lambda: {"steps": 0.0, "exercise_minutes": 0.0, "active_kcal": 0.0, "basal_kcal": 0.0})
    for date_local, metric, value in _parse_quantity_records(xml_path):
        if metric in agg[date_local]:
            agg[date_local][metric] += value
    quantity_rows = [
        (date_local, s["steps"], s["exercise_minutes"], s["active_kcal"], s["basal_kcal"])
        for date_local, s in sorted(agg.items())
    ]
    if quantity_rows:
        con.execute("DELETE FROM apple_quantity_daily")
        con.executemany(
            "INSERT INTO apple_quantity_daily (date_local, steps_daily, exercise_minutes_daily, active_kcal_daily, basal_kcal_daily) VALUES (?, ?, ?, ?, ?)",
            quantity_rows,
        )
        total += len(quantity_rows)

    return {"source": "apple_health", "rows_inserted": total, "rows_skipped": 0}


# ---- Weltory ----

def _parse_ts(s: str | None):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def ingest_weltory(con: duckdb.DuckDBPyConnection, zip_path: str, extract_dir: str) -> dict:
    with zipfile.ZipFile(zip_path, "r") as z:
        rr_name = "rr.json"
        for n in z.namelist():
            if n.endswith("rr.json"):
                rr_name = n
                break
        z.extract(rr_name, extract_dir)
    rr_path = os.path.join(extract_dir, rr_name)
    if os.path.dirname(rr_name):
        rr_path = os.path.join(extract_dir, rr_name)

    with open(rr_path, "r", encoding="utf-8") as f:
        items = json.load(f)
    if not isinstance(items, list):
        items = items.get("items", items) if isinstance(items, dict) else []

    con.execute("DELETE FROM weltory_rr")
    inserted = 0
    for row in items:
        if not isinstance(row, dict):
            continue
        ts = _parse_ts(row.get("time_start") or row.get("start") or row.get("timestamp"))
        if not ts:
            continue
        date_local = ts.date() if hasattr(ts, "date") else ts
        con.execute(
            """
            INSERT INTO weltory_rr (
                id, timestamp, date_local, rmssd, sdnn, pnn50, lf_hf_ratio, mean_hr, resting_hr,
                measurement_quality, time_start, time_end, duration, bpm,
                context_arousal_percent, context_energy_percent, resilience, source_name, device_name
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                str(row.get("id", "")),
                ts,
                date_local,
                row.get("rmssd"),
                row.get("sdnn"),
                row.get("pnn50"),
                row.get("lf_hf_ratio") or row.get("lf_hf"),
                row.get("bpm") or row.get("mean_hr") or row.get("heart_rate"),
                row.get("resting_hr"),
                row.get("measurement_quality") or row.get("quality"),
                str(row.get("time_start", "")),
                str(row.get("time_end", "")),
                row.get("duration"),
                row.get("bpm"),
                row.get("context_arousal_percent"),
                row.get("context_energy_percent"),
                row.get("resilience"),
                str(row.get("source_name", "")),
                str(row.get("device_name", "")),
            ],
        )
        inserted += 1

    return {"source": "weltory", "rows_inserted": inserted, "rows_skipped": 0}


# ---- Main ----

def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest Apple Health or Weltory ZIP into health DB and consolidate")
    parser.add_argument("--zip", required=True, help="Path to Apple Health or Weltory ZIP")
    parser.add_argument("--db", default=None, help="DuckDB path")
    parser.add_argument("--workspace", default=None, help="Workspace root")
    parser.add_argument("--no-consolidate", action="store_true", help="Skip running consolidate after ingest")
    parser.add_argument("--force", action="store_true", help="Re-ingest even if this ZIP was already imported (same path + mtime + size)")
    args = parser.parse_args()

    workspace = os.path.abspath(args.workspace or _default_workspace())
    db_path = os.path.abspath(args.db or _default_db(workspace))
    zip_path = os.path.abspath(args.zip)

    if not os.path.isfile(zip_path):
        print(f"ZIP not found: {zip_path}", file=sys.stderr)
        return 1
    if not os.path.isfile(db_path):
        print(f"Database not found: {db_path}; run init_db.py first.", file=sys.stderr)
        return 1

    try:
        zip_type = detect_zip_type(zip_path)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1

    file_mtime = os.path.getmtime(zip_path)
    file_size = os.path.getsize(zip_path)

    con = duckdb.connect(db_path)
    try:
        if not args.force:
            # Skip if same path + mtime + size already imported (or path-only if old schema)
            try:
                row = con.execute(
                    "SELECT ts FROM import_log WHERE path = ? AND file_mtime = ? AND file_size = ? ORDER BY ts DESC LIMIT 1",
                    [zip_path, file_mtime, file_size],
                ).fetchone()
            except duckdb.Error:
                row = con.execute(
                    "SELECT ts FROM import_log WHERE path = ? ORDER BY ts DESC LIMIT 1",
                    [zip_path],
                ).fetchone()
            if row:
                print(
                    json.dumps({
                        "status": "skipped",
                        "reason": "ZIP already imported (path + mtime + size unchanged)",
                        "path": zip_path,
                        "imported_at": str(row[0]),
                        "hint": "Use --force to re-ingest",
                    }, indent=2)
                )
                return 0
    finally:
        con.close()

    extract_dir = os.path.join(workspace, "data", "health", "extracted", datetime.now().strftime("%Y%m%d_%H%M%S"))
    os.makedirs(extract_dir, exist_ok=True)

    con = duckdb.connect(db_path)
    try:
        if zip_type == "apple_health":
            summary = ingest_apple_health(con, zip_path, extract_dir)
        else:
            summary = ingest_weltory(con, zip_path, extract_dir)

        try:
            con.execute(
                "INSERT INTO import_log (source, path, rows_inserted, rows_skipped, detail, file_mtime, file_size) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [summary["source"], zip_path, summary["rows_inserted"], summary["rows_skipped"], json.dumps(summary), file_mtime, file_size],
            )
        except duckdb.Error:
            con.execute(
                "INSERT INTO import_log (source, path, rows_inserted, rows_skipped, detail) VALUES (?, ?, ?, ?, ?)",
                [summary["source"], zip_path, summary["rows_inserted"], summary["rows_skipped"], json.dumps(summary)],
            )
    finally:
        con.close()

    print(json.dumps(summary, indent=2))

    if not args.no_consolidate:
        import subprocess
        consolidate = os.path.join(_script_dir(), "consolidate.py")
        r = subprocess.run(
            [sys.executable, consolidate, "--db", db_path, "--workspace", workspace, "--clear-raw"],
            cwd=workspace,
        )
        if r.returncode != 0:
            print("Consolidate failed; raw/consolidated tables may be stale.", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
