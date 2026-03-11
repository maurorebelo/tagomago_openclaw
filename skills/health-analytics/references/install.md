# Install and wire health-analytics

## Goal

- Ingest Apple Health and Weltory ZIP exports
- Incrementally update one persistent DuckDB database
- Optionally sync workout series from Notion
- Answer chat questions from the local database

## 1. Create workspace directories

```bash
mkdir -p <workspace>/data/health/{imports,extracted,logs,cache}
mkdir -p <workspace>/skills/health-analytics/scripts
mkdir -p <workspace>/skills/health-analytics/references
```

Replace `<workspace>` with the OpenClaw workspace root (e.g. `~/.openclaw/workspace` or `/data` in container).

## 2. Skill and scripts

- SKILL.md and this folder live under `skills/health-analytics/`.
- Required scripts in `scripts/`: `init_db.py`, `ingest.py`, `query.py`.
- Optional: `sync_notion_workouts.py`.

See SKILL.md and the script docstrings for contracts.

## 3. Environment

- Executables: `python3`, `unzip`, `duckdb`, `sqlite3`, `jq`, `curl`.
- Python: `pip install duckdb pandas requests python-dateutil xmltodict lxml`
- Notion (optional): `NOTION_API_KEY`, `NOTION_DATABASE_ID`.

## 4. OpenClaw capabilities

- Workspace filesystem and exec; Python allowed; persistent `data/health` (bind mount in Docker if needed).

## 5. AGENTS.md snippet

Append to workspace `AGENTS.md`:

```md
When a user uploads Apple Health or Weltory ZIP exports, use the health_analytics skill.
Keep the persistent database in `data/health/health.duckdb`. Do incremental updates only.
If workout-series analysis is requested, sync the Notion workout database first when credentials are available.
Never answer health trend questions from memory when the database can be queried.
```

## 6. First test sequence

1. Run `init_db.py`
2. Import one Apple Health ZIP
3. Ask resting heart rate trend
4. Import one Weltory ZIP
5. Sync Notion workouts (if configured)
6. Ask sleep/workout and improvement questions

## 7. Not included here

Parser implementations are not included; the value comes from implementing the Python scripts per the contracts in this skill.
