SELECT 'raw_welltory' AS table_name, COUNT(*) AS n FROM wellness.raw_welltory
UNION ALL
SELECT 'raw_apple_sleep_sessions', COUNT(*) FROM wellness.raw_apple_sleep_sessions
UNION ALL
SELECT 'raw_apple_quantities', COUNT(*) FROM wellness.raw_apple_quantities
UNION ALL
SELECT 'raw_apple_mindful_sessions', COUNT(*) FROM wellness.raw_apple_mindful_sessions
UNION ALL
SELECT '_autopopulate_audit', COUNT(*) FROM wellness._autopopulate_audit;

SELECT *
FROM wellness._autopopulate_audit
ORDER BY run_ts DESC, target_table;

SELECT
    COUNT(*) AS n_days,
    COUNT(DISTINCT date_local) AS distinct_days,
    MIN(date_local) AS min_day,
    MAX(date_local) AS max_day
FROM wellness.raw_welltory;

SELECT
    stage,
    COUNT(*) AS n_rows,
    ROUND(AVG(duration_minutes), 2) AS avg_minutes
FROM wellness.raw_apple_sleep_sessions
GROUP BY 1
ORDER BY 2 DESC;

SELECT
    metric,
    COUNT(*) AS n_rows,
    MIN(date_local) AS min_day,
    MAX(date_local) AS max_day
FROM wellness.raw_apple_quantities
GROUP BY 1
ORDER BY 2 DESC, 1;