#!/usr/bin/env python3
"""
Load Apple Health sleep phases from export XML into DuckDB.
Run inside OpenClaw container (or on host with duckdb/pyarrow).
Paths: zip at /data/APPLE_HEALTH_data_export.zip, XML at export_path, DB at db_path.
"""
import os
import sys
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime

try:
    import duckdb
except ImportError:
    print("duckdb not installed; run: pip install duckdb")
    sys.exit(1)

# Paths (container: /data; host: set APPLE_HEALTH_DATA_DIR)
BASE = os.environ.get("APPLE_HEALTH_DATA_DIR", "/data")
ZIP_PATH = os.path.join(BASE, "APPLE_HEALTH_data_export.zip")
EXPORT_DIR = os.path.join(BASE, "apple_health_export")
XML_PATH = os.path.join(EXPORT_DIR, "exportar.xml")
# Use existing health-skill DuckDB (readable path; node-owned in container)
DB_PATH = os.path.join(BASE, "data", "health", "duckdb", "health.duckdb")


def extract_zip_if_needed():
    global XML_PATH
    if os.path.isfile(XML_PATH):
        return
    if not os.path.isfile(ZIP_PATH):
        raise FileNotFoundError(f"Zip not found: {ZIP_PATH}")
    os.makedirs(EXPORT_DIR, exist_ok=True)
    with zipfile.ZipFile(ZIP_PATH) as z:
        for name in z.namelist():
            if name.endswith("exportar.xml"):
                z.extract(name, EXPORT_DIR)
                extracted = os.path.join(EXPORT_DIR, name)
                if extracted != XML_PATH and os.path.isfile(extracted):
                    os.rename(extracted, XML_PATH)
                return
        z.extractall(BASE)
    for root, _, files in os.walk(BASE):
        for f in files:
            if f == "exportar.xml":
                XML_PATH = os.path.join(root, f)
                return
    raise FileNotFoundError(f"exportar.xml not found under {BASE}")


def parse_sleep_records(path):
    """Stream parse XML and yield sleep records as dicts."""
    for event, elem in ET.iterparse(path, events=("end",)):
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
        # Capture all Record attributes (first run missed device, sourceVersion, etc.)
        rec = {
            "start_date": elem.get("startDate"),
            "end_date": elem.get("endDate"),
            "value": value,
            "source_name": elem.get("sourceName") or "",
            "creation_date": elem.get("creationDate"),
            "device": elem.get("device") or "",
            "source_version": elem.get("sourceVersion") or "",
        }
        elem.clear()
        yield rec


def main():
    extract_zip_if_needed()
    print("XML path:", XML_PATH)
    print("DB path:", DB_PATH)

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = duckdb.connect(DB_PATH)
    # Recreate so new columns (device, source_version) are always present
    con.execute("DROP TABLE IF EXISTS sleep_phases")
    con.execute("""
        CREATE TABLE sleep_phases (
            start_date VARCHAR,
            end_date VARCHAR,
            value VARCHAR,
            source_name VARCHAR,
            creation_date VARCHAR,
            device VARCHAR,
            source_version VARCHAR
        )
    """)

    batch = []
    batch_size = 5000
    total = 0

    def insert_batch(rows):
        if not rows:
            return
        con.executemany(
            """
            INSERT INTO sleep_phases (start_date, end_date, value, source_name, creation_date, device, source_version)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    r["start_date"],
                    r["end_date"],
                    r["value"],
                    r["source_name"],
                    r["creation_date"],
                    r["device"],
                    r["source_version"],
                )
                for r in rows
            ],
        )

    for rec in parse_sleep_records(XML_PATH):
        batch.append(rec)
        if len(batch) >= batch_size:
            insert_batch(batch)
            total += len(batch)
            print(total, "rows")
            batch = []

    insert_batch(batch)
    total += len(batch)
    print("Total rows:", total)

    # summary
    for row in con.execute(
        "SELECT value, count(*) as n FROM sleep_phases GROUP BY value ORDER BY n DESC"
    ).fetchall():
        print(" ", row[0], row[1])

    con.close()
    print("Done. DuckDB:", DB_PATH)


if __name__ == "__main__":
    main()
