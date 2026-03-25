---
name: health-import
description: Parse and ingest Apple Health ZIP exports (XML) and Weltory ZIP exports (JSON) into the shared health DuckDB. Use when the user uploads a new health export, asks to re-import or fix parsing, adds a new data type (steps, sleep phases, HRV, energy), or reports missing metrics after import.
---

# health-import

Ingests raw Apple Health and Weltory exports into the shared DuckDB. The downstream analysis skill (`health-analytics`) reads from this database.

## Paths

| Item | Path in container |
|---|---|
| Apple Health ZIP | `/data/skills/health-import/input/APPLE_HEALTH_data_export.zip` |
| Weltory ZIP | `/data/skills/health-import/input/WELTORY_data_export.zip` |
| Extracted files | `/data/skills/health-import/input/extracted/` |
| Shared DuckDB | `/data/skills/health-analytics/data/duckdb/health.duckdb` |
| Scripts | `/data/skills/health-import/scripts/` |
| References | `/data/skills/health-import/references/` |

## Apple Health format

The native Apple Health export is **XML** — not JSON. The main file is `apple_health_export/exportar.xml` inside the ZIP.

Use `iterparse` (streaming) to handle the large XML file.

### Key record types

| Type | Notes |
|---|---|
| `HKCategoryTypeIdentifierSleepAnalysis` | Sleep phases — values: `AsleepCore`, `AsleepDeep`, `AsleepREM`, `Awake`, `InBed`, `AsleepUnspecified` |
| `HKQuantityTypeIdentifierStepCount` | Steps |
| `HKQuantityTypeIdentifierActiveEnergyBurned` | Active cal |
| `HKQuantityTypeIdentifierBasalEnergyBurned` | Resting cal |
| `HKQuantityTypeIdentifierAppleExerciseTime` | Exercise min |
| `HKQuantityTypeIdentifierHeartRate` | HR |
| `HKQuantityTypeIdentifierHeartRateVariabilitySDNN` | HRV |

See `references/apple_health_export.md` and `references/apple_health_quantities.md` for full field list.

### Known parsing challenges

- `exportar.xml` is very large; always use streaming (`iterparse`), never load into memory
- `sourceName` varies (iPhone, Apple Watch, third-party apps) — deduplicate by source priority
- Sleep records overlap across sources; prefer Watch over iPhone records when both present
- Quantity records have `unit` attribute — validate expected unit before inserting
- Dates are ISO 8601 with timezone offset (`2024-03-01 22:00:00 +0100`) — parse with `python-dateutil`
- Some records have `nil` or missing values — skip silently, log count

## Weltory format

Weltory export ZIP contains **only JSON** — no XML.

| File | Content |
|---|---|
| `rr.json` | Main data: `context_arousal_percent` (stress), `context_energy_percent`, `resilience`, `mean_rr`, `rmssd`, `pnn50` |
| `data_flow_*.json` | Same structure; `data.result.items` is often empty in exports |
| `profile.json` | User profile |

See `references/weltory_export.md` for full field reference.

## Ingest workflow

```bash
cd /data/skills/health-import

# 1. Init DB (idempotent — safe to run again)
python scripts/init_db.py

# 2. Ingest Apple Health
python scripts/ingest.py --zip input/APPLE_HEALTH_data_export.zip

# 3. Ingest Weltory
python scripts/ingest.py --zip input/WELTORY_data_export.zip

# Force re-import of the same file
python scripts/ingest.py --zip input/APPLE_HEALTH_data_export.zip --force
```

- If the same ZIP (path + mtime + size) was already imported, ingest returns `status: skipped` — use `--force` to re-import after fixing parsing
- Always append an audit record to the import log
- After ingest, trigger `consolidate` in health-analytics to rebuild daily_features

## Required packages

```bash
pip install duckdb pandas python-dateutil lxml
```

## Debug: metric missing after import

1. Check raw XML/JSON — is the value there?
2. Check import log — did the row count increase?
3. Check the source table in DuckDB — is the row present?
4. Check column mapping in ingest script — correct field name?
5. See `references/daily_features_debug.md` in health-analytics for downstream consolidation issues
