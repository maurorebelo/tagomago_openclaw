---
name: health-analytics
description: "Ingest Apple Health and Weltory ZIP exports into a persistent local DuckDB; build consolidated tables (raw → normalised → daily_features) and update them on new imports; optionally sync Notion workouts; answer health questions and run correlation analyses from the local database. Use when the user uploads a health ZIP, asks to update the DB, or asks health/trend/correlation questions."
---

# Health Analytics

Use this skill when the user uploads an Apple Health or Weltory ZIP, asks to update the health database, sync Notion workouts, or asks health questions that must be answered from the local database. When the user asks for **correlation analysis** between Welltory, Apple Health and sleep, **run the proposed correlation analysis** (see Correlation analysis below).

## Paths (workspace-relative)

- **Workspace root:** Directory that contains `skills/` (e.g. repo root or container `/data`). The database and imports live under workspace.
- database: `data/health/duckdb/health.duckdb` (single DuckDB; in container `/data/data/health/duckdb/health.duckdb`; must be writable by node)
- imports: `data/health/imports`
- extracted: `data/health/extracted`
- logs: `data/health/logs`
- cache: `data/health/cache`

Scripts live in the skill `scripts/` dir (e.g. `skills/health-analytics/scripts/`). Run from workspace root or with paths adjusted.

**Apple Health export:** Raw export is **XML** (not JSON). Zip path in this setup: `/data/APPLE_HEALTH_data_export.zip`; main file inside: `apple_health_export/exportar.xml`. Ingest **sleep phases** and all other Apple Health data from this XML into the **same** DuckDB. See [references/apple_health_export.md](references/apple_health_export.md) for paths, Record types (e.g. `HKCategoryTypeIdentifierSleepAnalysis`), and table `sleep_phases`.

## Rules

- Never claim data was imported unless the import script completed successfully.
- Never rebuild the database if it already exists unless the user explicitly asks.
- **Não rodar nova extração (ingest) a não ser que o ZIP/XML/JSON tenham mudado.** O ingest verifica path + mtime + size do ficheiro; se já tiver importado esse mesmo ficheiro, ignora e devolve `status: skipped` (use `--force` para forçar re-import). Ajustes de parse e população do DB fazem-se sem repetir extração desnecessária.
- Always ingest incrementally; deduplicate by native source record id when present, else by `timestamp + metric + source`.
- Always append an audit record to the import log.
- Prefer DuckDB for storage and SQL, Python for parsing.
- When answering health questions, query the database first; use exact dates, values, and source names; state uncertainty when data is incomplete.
- Do not give medical advice as diagnosis; frame suggestions as observations and hypotheses grounded in the user's data.

## Pipeline: import → consolidated tables

The skill owns the full flow from ZIP import to consolidated DuckDB as in `weltory_tips/estrategia_pipeline_duckdb_openclaw.md` (inside the skill):

1. **init_db.py** — Creates the DB, wellness schema (01_schema.sql), and source tables (`sleep_phases`, `weltory_rr`, `import_log`).
2. **ingest.py** — Detects Apple Health vs Weltory ZIP, unpacks, parses XML or rr.json, upserts into source tables, **then runs consolidate** so `wellness.raw_*`, normalised tables, and `wellness.daily_features` are rebuilt. **Skip:** if the same file (path + mtime + size) was already imported, ingest skips and returns `status: skipped`; use `--force` to re-ingest. Focus further work on parse/DB population adjustments, not re-running extraction unless the ZIP/XML/JSON change.
3. **consolidate.py** — (Runnable alone.) Runs `weltory_tips/auto_populate_raw_tables.py` (inside the skill) then `02_daily_features.sql`. Use `--clear-raw` for a full rebuild.

## Ingestion workflow

1. Ensure the database exists: run `python scripts/init_db.py` (from skill dir or workspace).
2. Run `python scripts/ingest.py --zip <path-to-zip>`. Ingest detects Apple vs Weltory, parses, writes to source tables, then runs consolidate so consolidated tables are up to date.
   - **Verificação:** se o mesmo ZIP (mesmo path + mtime + size) já tiver sido importado, o ingest devolve `"status": "skipped"` e não repete a extração. Use `--force` para forçar re-import (ex.: após alterar o parse).
3. Summarize: source detected, rows inserted, date range. Tell the user what questions can now be answered.

## Notion sync workflow

1. Check for `NOTION_API_KEY` and `NOTION_DATABASE_ID`.
2. Run `python scripts/sync_notion_workouts.py`; upsert into `notion_workouts` by Notion page id.
3. If credentials are missing, say so and do not pretend the sync ran.

## Query workflow

1. Run `python scripts/query.py --question "<user-question>"`.
2. Base the answer on returned results; include concrete values, dates, trends; separate correlations from hypotheses.

## Correlation analysis

When the user asks for **correlation analysis** between Welltory, Apple Health and sleep (or daily features / pipeline insights):

1. Ensure consolidated tables exist (run `scripts/consolidate.py` if needed).
2. **Run the proposed correlation analysis** using scripts in **weltory_tips/** (inside the skill, at `skills/health-analytics/weltory_tips/`):
   - `weltory_tips/03_correlation_queries.sql` — run against `wellness.daily_features`: coverage counts, Pearson/Spearman pairs, and **quantile analysis** (steps in quintiles vs avg_rmssd to detect optimal zone, e.g. “HRV optimal ≈ 7k–10k steps”). From container: `/data/skills/health-analytics/weltory_tips/03_correlation_queries.sql`.
   - `weltory_tips/welltory_apple_health_correlation.py` — Welltory ↔ Apple Health correlation.
3. Report results with concrete values and plausibility; separate correlations from hypotheses. See [references/pipeline_weltory_apple_health.md](references/pipeline_weltory_apple_health.md) for strategy and script list.

**Deploy:** The install script deploys the skill (which includes `weltory_tips`); a single deploy puts everything under `skills/health-analytics/` on the VPS.

## Required tools and env

- Tools: `python3`, `duckdb`, `sqlite3`, `unzip`, `jq`, `curl`; filesystem and exec access to workspace.
- Python packages: `duckdb`, `pandas`, `requests`, `python-dateutil`, `xmltodict` or `lxml`. Install before running ingest on a fresh system (e.g. `pip install duckdb pandas python-dateutil`; plus `xmltodict` or `lxml` for XML).
- Notion (optional): `NOTION_API_KEY`, `NOTION_DATABASE_ID`.

**Métrica em falta em daily_features** — Pode ser por: (1) não entrou no ingest; (2) entrou mas não foi mapeada; (3) foi mapeada com nome diferente; (4) foi para uma tabela raw que `_daily_base` não consome. **Ordem de debug:** ver [references/daily_features_debug.md](references/daily_features_debug.md): 1) valor na fonte (XML/JSON); 2) ingest escreve em tabela de origem; 3) autopopulate lê essa coluna; 4) nome da métrica = o que 02_daily_features.sql espera; 5) a raw alimenta _daily_base.

## References

- **Install and wiring:** See [references/install.md](references/install.md).
- **Schema and tables:** See [references/schema.md](references/schema.md).
- **Métrica em falta em daily_features (causas e ordem de debug):** See [references/daily_features_debug.md](references/daily_features_debug.md).
- **Apple Health export (XML, sleep phases, single DB):** See [references/apple_health_export.md](references/apple_health_export.md).
- **Weltory export (JSON, stress/energy/health em rr.json e data_flow):** See [references/weltory_export.md](references/weltory_export.md).
- **Pipeline Welltory + Apple Health + sono (estratégia e scripts em weltory_tips):** See [references/pipeline_weltory_apple_health.md](references/pipeline_weltory_apple_health.md).
