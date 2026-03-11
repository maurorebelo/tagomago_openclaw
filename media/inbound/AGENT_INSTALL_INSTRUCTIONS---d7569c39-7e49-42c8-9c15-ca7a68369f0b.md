# Install instructions for the OpenClaw agent

This file tells the agent owner how to install and wire the `health_analytics` skill into OpenClaw.

## Goal

Enable OpenClaw to:

- ingest Apple Health ZIP exports
- ingest Weltory ZIP exports
- incrementally update one persistent DuckDB database
- optionally sync structured workout series from Notion
- answer chat questions from the local database

## 1. Create the workspace directories

From the machine running OpenClaw:

```bash
mkdir -p ~/.openclaw/workspace/data/health/{imports,extracted,logs,cache}
mkdir -p ~/.openclaw/workspace/skills/health-analytics/scripts
mkdir -p ~/.openclaw/workspace/skills/health-analytics/references
```

If you use a non-default workspace, replace `~/.openclaw/workspace` with that path.

## 2. Install the skill file

Save the provided `SKILL.md` to:

```text
~/.openclaw/workspace/skills/health-analytics/SKILL.md
```

OpenClaw loads workspace skills from `<workspace>/skills`. Workspace skills override shared and bundled skills.

## 3. Add the Python scripts

Create these files in:

```text
~/.openclaw/workspace/skills/health-analytics/scripts/
```

Required:

- `init_db.py`
- `ingest.py`
- `query.py`

Optional but recommended:

- `sync_notion_workouts.py`

What each script should do:

### `init_db.py`

- create `data/health/health.duckdb`
- create all tables and indexes
- create `import_log`

### `ingest.py`

- accept `--zip <path>`
- detect Apple Health vs Weltory
- unpack the archive into `data/health/extracted/<timestamp>/`
- parse files
- upsert records
- dedupe by native id when present, otherwise by `timestamp + metric + source`
- append a full import audit entry
- print a compact JSON summary

### `query.py`

- accept `--question "..."`
- map the question to safe SQL
- query DuckDB
- return JSON containing stats, date range, and optional chart data

### `sync_notion_workouts.py`

- read `NOTION_API_KEY`
- read `NOTION_DATABASE_ID`
- fetch workout rows from the Notion database
- upsert by Notion page id

## 4. Make sure the environment has the required tools

Required executables:

- `python3`
- `unzip`
- `duckdb`
- `sqlite3`
- `jq`
- `curl`

Recommended Python packages:

```bash
pip install duckdb pandas requests python-dateutil xmltodict lxml
```

## 5. Enable the right OpenClaw capabilities

The agent should have:

- workspace filesystem access
- `exec`
- permission to run Python scripts
- access to the `data/` directory inside the workspace

If using Docker sandboxing, bind the workspace data path so the scripts can persist the database.

Example intent:

- keep the database in the workspace
- allow read/write access to `data/health`
- do not run on an ephemeral temp directory

## 6. Add a short instruction to `AGENTS.md`

Append something like this to the workspace `AGENTS.md`:

```md
When a user uploads Apple Health or Weltory ZIP exports, use the health_analytics skill.
Keep the persistent database in `data/health/health.duckdb`.
Do incremental updates only.
If workout-series analysis is requested, sync the Notion workout database first when credentials are available.
Never answer health trend questions from memory when the database can be queried.
```

## 7. Configure Notion access

If workout series should sync from Notion, provide:

- `NOTION_API_KEY`
- `NOTION_DATABASE_ID`

Make sure the Notion integration is shared with the target database.

If API access is not available, use a periodic CSV export and ingest that instead.

## 8. Start a fresh OpenClaw session

After installing the skill and scripts:

- start a new session, or
- restart the gateway, or
- refresh skills if your setup supports it

The new skill must be visible to the agent before testing.

## 9. First test sequence

1. Run `init_db.py`
2. Upload one Apple Health ZIP
3. Ask: `import this zip into my health database`
4. Ask: `show my resting heart rate trend over 90 days`
5. Upload one Weltory ZIP
6. Ask: `update my database with this export`
7. Sync Notion workouts
8. Ask: `did poor sleep affect the day after heavy workouts?`
9. Ask: `what can I do to improve sleep and energy?`

## 10. Expected behavior

After installation, OpenClaw should:

- keep one persistent DuckDB database
- update it incrementally
- maintain an audit log
- answer chat questions from actual query results
- join physiological data with Notion workout data when available

## 11. What this file does not include

This file does not include the parser implementations.

It only defines how the skill is installed and wired into OpenClaw. The actual value comes from the Python scripts.
