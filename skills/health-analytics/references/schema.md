# Suggested schema and behavior

## Core tables

Scripts should maintain tables such as:

- `import_log` — audit of each import (source, path, timestamp, rows inserted/skipped)
- `sleep_phases` — raw sleep stages from Apple Health XML (start_date, end_date, value, source_name, creation_date, device, source_version)
- `sleep_daily`
- `heart_rate_samples`
- `heart_rate_intervals`
- `steps_daily`
- `calories_daily`
- `exercise_sessions`
- `medications`
- `notion_workouts` — synced from Notion by page id

## Dedupe policy

- Primary: native record id + source
- Fallback: timestamp + metric + source
- Keep audit rows even when all data rows were duplicates

## Failure handling

- Unknown ZIP format: stop and explain
- Parser failure: log and report affected source/file
- Query not answerable: say what data is missing

## High-priority questions

Handle well: resting heart rate trend; sleep duration and consistency; sleep vs energy; sleep vs next-day heart rate/intervals; medication adherence; exercise volume and intensity; steps and calories trends; anomalies; “what can I do to improve sleep and energy”.

For improvement questions: query recent sleep, exercise, heart rate, medication, workout load; identify patterns; separate correlations from hypotheses; give practical suggestions grounded in data; avoid overstating causality.
