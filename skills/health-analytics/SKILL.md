---
name: health-analytics
description: Consolidate imported health data into daily_features, run correlation analysis between Apple Health, Weltory and sleep, generate reports and answer health questions from the local DuckDB. Use when the user asks for health trends, correlations, sleep analysis, HRV patterns, or wants to rebuild the consolidated tables after a new import.
---

# health-analytics

Consolidates, analyses, and queries health data from the shared DuckDB populated by `health-import`.

## Paths

| Item | Path in container |
|---|---|
| Shared DuckDB | `/data/skills/health-analytics/data/duckdb/health.duckdb` |
| Scripts | `/data/skills/health-analytics/scripts/` |
| Correlation scripts | `/data/skills/health-analytics/weltory_tips/` |
| References | `/data/skills/health-analytics/references/` |

## Rules

- Never claim data is up to date unless the DB was queried in this session.
- Do not give medical diagnoses; frame findings as observations and hypotheses grounded in the user's data.
- When data is incomplete or a metric is missing from `daily_features`, debug with the order in `references/daily_features_debug.md` before assuming it was never imported.
- Run `consolidate.py` after any new import before answering trend questions.

## Consolidation

Rebuild the normalised tables and `daily_features` from whatever is in the source tables:

```bash
cd /data/skills/health-analytics
python scripts/consolidate.py
# Full rebuild (clears raw_* first)
python scripts/consolidate.py --clear-raw
```

This runs `weltory_tips/auto_populate_raw_tables.py` then `02_daily_features.sql`.

## Correlation analysis

When the user asks for correlations between Weltory, Apple Health, and sleep:

1. Ensure `daily_features` is up to date: run `consolidate.py` if needed.
2. Run the SQL correlation queries:

```bash
duckdb /data/skills/health-analytics/data/duckdb/health.duckdb \
  < weltory_tips/03_correlation_queries.sql
```

3. Run the Python correlation script:

```bash
python weltory_tips/welltory_apple_health_correlation.py
```

4. Report results with concrete values; separate correlations from hypotheses; include plausibility commentary (sleep→HRV, activity→HRV, circadian rhythm).

See `references/pipeline_weltory_apple_health.md` for strategy and full script list.

## Query workflow

```bash
python scripts/query.py --question "<user-question>"
```

Base answers on returned values; include dates, exact numbers, source names; note when data coverage is incomplete.

## Notion sync (optional)

```bash
NOTION_API_KEY=<key> NOTION_DATABASE_ID=<id> python scripts/sync_notion_workouts.py
```

Upserts workouts into `notion_workouts` by Notion page ID.

## daily_features table

Central table built by `02_daily_features.sql`. Key columns:

- `date_local` — date of awakening (sleep associated to wake date, not start)
- Weltory: `mean_rmssd`, `mean_rr`, `energy`, `stress`, `resilience`
- Apple Health: `steps`, `active_cal`, `exercise_min`, `sleep_duration_h`
- Derived: `hrv_baseline`, `hrv_ratio`, `sleep_score`, `activity_load`, `lag_*`

## Debug: metric missing from daily_features

See `references/daily_features_debug.md` — order: (1) value in source table → (2) autopopulate maps it → (3) column name matches SQL → (4) `_daily_base` consumes the raw table.

## References

- **Pipeline strategy:** `references/pipeline_weltory_apple_health.md`
- **daily_features debug:** `references/daily_features_debug.md`
- **Schema and tables:** `references/schema.md`
- **VPS-specific notes:** `references/health_analytics_vps.md`
