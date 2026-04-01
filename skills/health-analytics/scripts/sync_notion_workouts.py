#!/usr/bin/env python3
"""
Sync workout rows from Notion into DuckDB.

DB selection precedence:
1) --database-id
2) NOTION_WORKOUTS_DATABASE_ID
3) NOTION_DATABASE_ID
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any

import duckdb
import requests

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


def _default_db() -> str:
    return "/data/skills/health-analytics/data/duckdb/health.duckdb"


def _env_database_id() -> str:
    return os.environ.get("NOTION_WORKOUTS_DATABASE_ID") or os.environ.get("NOTION_DATABASE_ID", "")


def _database_id_source() -> str:
    return "NOTION_WORKOUTS_DATABASE_ID" if os.environ.get("NOTION_WORKOUTS_DATABASE_ID") else "NOTION_DATABASE_ID"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Sync Notion workouts into DuckDB")
    p.add_argument("--db", default=_default_db(), help="DuckDB file path")
    p.add_argument("--database-id", default=_env_database_id())
    p.add_argument("--api-key", default=os.environ.get("NOTION_API_KEY", ""))
    p.add_argument("--page-size", type=int, default=100)
    p.add_argument("--max-pages", type=int, default=0, help="Optional safety limit")
    return p.parse_args()


def _notion_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _as_float(v: Any) -> float | None:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _extract_title(prop: dict[str, Any]) -> str | None:
    arr = prop.get("title") or []
    text = "".join((x.get("plain_text") or "") for x in arr if isinstance(x, dict)).strip()
    return text or None


def _extract_rich_text(prop: dict[str, Any]) -> str | None:
    arr = prop.get("rich_text") or []
    text = "".join((x.get("plain_text") or "") for x in arr if isinstance(x, dict)).strip()
    return text or None


def _extract_select_name(prop: dict[str, Any]) -> str | None:
    sel = prop.get("select")
    if isinstance(sel, dict):
        return sel.get("name") or None
    return None


def _extract_date(prop: dict[str, Any]) -> str | None:
    d = prop.get("date")
    if isinstance(d, dict):
        return d.get("start") or None
    return None


def _extract_number(prop: dict[str, Any]) -> float | None:
    return _as_float(prop.get("number"))


def _extract_checkbox(prop: dict[str, Any]) -> bool | None:
    v = prop.get("checkbox")
    return bool(v) if isinstance(v, bool) else None


def _extract_multi_select(prop: dict[str, Any]) -> list[str] | None:
    arr = prop.get("multi_select")
    if not isinstance(arr, list):
        return None
    vals = [x.get("name") for x in arr if isinstance(x, dict) and x.get("name")]
    return vals or None


def _extract_formula(prop: dict[str, Any]) -> Any:
    f = prop.get("formula")
    if not isinstance(f, dict):
        return None
    t = f.get("type")
    if t in ("number", "string", "boolean", "date"):
        return f.get(t)
    return None


def _extract_rollup(prop: dict[str, Any]) -> Any:
    r = prop.get("rollup")
    if not isinstance(r, dict):
        return None
    t = r.get("type")
    if t in ("number", "date", "array"):
        return r.get(t)
    return None


def _property_value(prop: dict[str, Any]) -> Any:
    ptype = prop.get("type")
    if ptype == "title":
        return _extract_title(prop)
    if ptype == "rich_text":
        return _extract_rich_text(prop)
    if ptype == "select":
        return _extract_select_name(prop)
    if ptype == "multi_select":
        return _extract_multi_select(prop)
    if ptype == "number":
        return _extract_number(prop)
    if ptype == "date":
        return _extract_date(prop)
    if ptype == "checkbox":
        return _extract_checkbox(prop)
    if ptype == "formula":
        return _extract_formula(prop)
    if ptype == "rollup":
        return _extract_rollup(prop)
    if ptype == "status":
        st = prop.get("status") or {}
        return st.get("name") if isinstance(st, dict) else None
    return prop.get(ptype)


def _normalize_page(page: dict[str, Any], database_id: str) -> dict[str, Any]:
    props = page.get("properties", {}) if isinstance(page.get("properties"), dict) else {}

    flat: dict[str, Any] = {}
    for k, v in props.items():
        if isinstance(v, dict):
            flat[k] = _property_value(v)

    lower_map = {k.lower(): k for k in flat.keys()}

    def pick(*names: str) -> Any:
        for n in names:
            key = lower_map.get(n.lower())
            if key is not None:
                val = flat.get(key)
                if val not in (None, ""):
                    return val
        return None

    title = pick("name", "title", "workout", "treino")
    status = pick("status", "state", "estado")
    notes = pick("notes", "observations", "obs", "comentarios", "comments")
    date_start = pick("date", "data", "workout_date", "treino_data")
    duration = _as_float(pick("duration", "duration_min", "minutes", "minutos"))
    rpe = _as_float(pick("rpe", "effort"))
    load_kg = _as_float(pick("load", "carga", "kg", "peso"))
    sets_count = _as_float(pick("sets", "series"))
    reps_count = _as_float(pick("reps", "repetitions", "repeticoes"))

    date_local = None
    if isinstance(date_start, str) and len(date_start) >= 10:
        date_local = date_start[:10]

    return {
        "page_id": page.get("id"),
        "database_id": database_id,
        "created_time": page.get("created_time"),
        "last_edited_time": page.get("last_edited_time"),
        "archived": bool(page.get("archived", False) or page.get("is_archived", False)),
        "url": page.get("url"),
        "title": title,
        "date_local": date_local,
        "status": status,
        "duration_min": duration,
        "rpe": rpe,
        "load_kg": load_kg,
        "sets_count": sets_count,
        "reps_count": reps_count,
        "notes": notes,
        "properties_json": json.dumps(flat, ensure_ascii=False),
        "raw_json": json.dumps(page, ensure_ascii=False),
    }


def _fetch_all_pages(api_key: str, database_id: str, page_size: int, max_pages: int = 0) -> list[dict[str, Any]]:
    url = f"{NOTION_API}/databases/{database_id}/query"
    headers = _notion_headers(api_key)

    out: list[dict[str, Any]] = []
    cursor = None
    seen_cursors: set[str] = set()
    page_idx = 0

    while True:
        payload: dict[str, Any] = {"page_size": page_size}
        if cursor:
            payload["start_cursor"] = cursor

        r = requests.post(url, headers=headers, json=payload, timeout=(15, 60))
        if r.status_code >= 400:
            raise RuntimeError(f"Notion API error {r.status_code}: {r.text[:500]}")

        data = r.json()
        results = data.get("results") or []
        out.extend(results)

        page_idx += 1
        print(f"fetched_page={page_idx} rows={len(results)} total={len(out)}", flush=True)

        if max_pages and page_idx >= max_pages:
            break
        if not data.get("has_more"):
            break

        cursor = data.get("next_cursor")
        if not cursor:
            break
        if cursor in seen_cursors:
            break
        seen_cursors.add(cursor)

    return out


def _ensure_schema(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("CREATE SCHEMA IF NOT EXISTS wellness")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS wellness.notion_workouts (
            page_id VARCHAR PRIMARY KEY,
            database_id VARCHAR,
            created_time TIMESTAMP,
            last_edited_time TIMESTAMP,
            archived BOOLEAN,
            url VARCHAR,
            title VARCHAR,
            date_local DATE,
            status VARCHAR,
            duration_min DOUBLE,
            rpe DOUBLE,
            load_kg DOUBLE,
            sets_count DOUBLE,
            reps_count DOUBLE,
            notes VARCHAR,
            properties_json JSON,
            raw_json JSON,
            synced_at TIMESTAMP
        )
        """
    )


def _upsert_rows(con: duckdb.DuckDBPyConnection, rows: list[dict[str, Any]]) -> int:
    sql = """
    INSERT INTO wellness.notion_workouts (
        page_id, database_id, created_time, last_edited_time, archived, url, title,
        date_local, status, duration_min, rpe, load_kg, sets_count, reps_count,
        notes, properties_json, raw_json, synced_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(page_id) DO UPDATE SET
        database_id=excluded.database_id,
        created_time=excluded.created_time,
        last_edited_time=excluded.last_edited_time,
        archived=excluded.archived,
        url=excluded.url,
        title=excluded.title,
        date_local=excluded.date_local,
        status=excluded.status,
        duration_min=excluded.duration_min,
        rpe=excluded.rpe,
        load_kg=excluded.load_kg,
        sets_count=excluded.sets_count,
        reps_count=excluded.reps_count,
        notes=excluded.notes,
        properties_json=excluded.properties_json,
        raw_json=excluded.raw_json,
        synced_at=excluded.synced_at
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    params = [
        (
            r["page_id"],
            r["database_id"],
            r["created_time"],
            r["last_edited_time"],
            r["archived"],
            r["url"],
            r["title"],
            r["date_local"],
            r["status"],
            r["duration_min"],
            r["rpe"],
            r["load_kg"],
            r["sets_count"],
            r["reps_count"],
            r["notes"],
            r["properties_json"],
            r["raw_json"],
            now,
        )
        for r in rows
        if r.get("page_id")
    ]
    if not params:
        return 0
    con.executemany(sql, params)
    return len(params)


def main() -> None:
    args = _parse_args()
    if not args.api_key or not args.database_id:
        raise SystemExit("NOTION_API_KEY and workout database id required")

    pages = _fetch_all_pages(args.api_key, args.database_id, args.page_size, args.max_pages)
    rows = [_normalize_page(p, args.database_id) for p in pages if isinstance(p, dict)]

    con = duckdb.connect(args.db)
    try:
        _ensure_schema(con)
        upserted = _upsert_rows(con, rows)
        total = con.execute("SELECT COUNT(*) FROM wellness.notion_workouts").fetchone()[0]
    finally:
        con.close()

    print(json.dumps({
        "database_id": args.database_id,
        "database_id_source": _database_id_source(),
        "pages_fetched": len(pages),
        "rows_upserted": upserted,
        "table_rows_total": int(total),
        "db": args.db,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
