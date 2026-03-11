SELECT
    COUNT(*) AS n_days,
    COUNT(rmssd) AS n_rmssd,
    COUNT(sleep_duration_hours) AS n_sleep,
    COUNT(steps_daily) AS n_steps,
    COUNT(apple_hrv_sdnn) AS n_apple_hrv
FROM wellness.daily_features;

WITH pairs AS (
    SELECT * FROM (
        VALUES
            ('sleep_duration_hours','rmssd'),
            ('deep_sleep_hours','rmssd'),
            ('sleep_efficiency_pct','rmssd'),
            ('awake_hours','rmssd'),
            ('awakenings_count','rmssd'),
            ('sleep_consistency_shift_minutes','rmssd'),
            ('sleep_duration_hours','stress_proxy'),
            ('deep_sleep_hours','stress_proxy'),
            ('sleep_efficiency_pct','stress_proxy'),
            ('steps_daily','recovery_proxy'),
            ('active_kcal_daily','recovery_proxy'),
            ('exercise_minutes_daily','recovery_proxy'),
            ('steps_daily_lag1','rmssd'),
            ('active_kcal_daily_lag1','rmssd'),
            ('exercise_minutes_daily_lag1','rmssd'),
            ('apple_hrv_sdnn','rmssd'),
            ('apple_resting_hr','mean_hr'),
            ('apple_respiratory_rate','stress_proxy'),
            ('mindful_minutes_daily','rmssd'),
            ('mindful_minutes_daily','stress_proxy')
    ) AS t(predictor, target)
)
SELECT
    predictor,
    target,
    CASE predictor
        WHEN 'sleep_duration_hours' THEN corr(sleep_duration_hours, CASE target WHEN 'rmssd' THEN rmssd WHEN 'mean_hr' THEN mean_hr WHEN 'recovery_proxy' THEN recovery_proxy WHEN 'stress_proxy' THEN stress_proxy END)
        WHEN 'deep_sleep_hours' THEN corr(deep_sleep_hours, CASE target WHEN 'rmssd' THEN rmssd WHEN 'mean_hr' THEN mean_hr WHEN 'recovery_proxy' THEN recovery_proxy WHEN 'stress_proxy' THEN stress_proxy END)
        WHEN 'sleep_efficiency_pct' THEN corr(sleep_efficiency_pct, CASE target WHEN 'rmssd' THEN rmssd WHEN 'mean_hr' THEN mean_hr WHEN 'recovery_proxy' THEN recovery_proxy WHEN 'stress_proxy' THEN stress_proxy END)
        WHEN 'awake_hours' THEN corr(awake_hours, CASE target WHEN 'rmssd' THEN rmssd WHEN 'mean_hr' THEN mean_hr WHEN 'recovery_proxy' THEN recovery_proxy WHEN 'stress_proxy' THEN stress_proxy END)
        WHEN 'awakenings_count' THEN corr(awakenings_count, CASE target WHEN 'rmssd' THEN rmssd WHEN 'mean_hr' THEN mean_hr WHEN 'recovery_proxy' THEN recovery_proxy WHEN 'stress_proxy' THEN stress_proxy END)
        WHEN 'sleep_consistency_shift_minutes' THEN corr(sleep_consistency_shift_minutes, CASE target WHEN 'rmssd' THEN rmssd WHEN 'mean_hr' THEN mean_hr WHEN 'recovery_proxy' THEN recovery_proxy WHEN 'stress_proxy' THEN stress_proxy END)
        WHEN 'steps_daily' THEN corr(steps_daily, CASE target WHEN 'rmssd' THEN rmssd WHEN 'mean_hr' THEN mean_hr WHEN 'recovery_proxy' THEN recovery_proxy WHEN 'stress_proxy' THEN stress_proxy END)
        WHEN 'active_kcal_daily' THEN corr(active_kcal_daily, CASE target WHEN 'rmssd' THEN rmssd WHEN 'mean_hr' THEN mean_hr WHEN 'recovery_proxy' THEN recovery_proxy WHEN 'stress_proxy' THEN stress_proxy END)
        WHEN 'exercise_minutes_daily' THEN corr(exercise_minutes_daily, CASE target WHEN 'rmssd' THEN rmssd WHEN 'mean_hr' THEN mean_hr WHEN 'recovery_proxy' THEN recovery_proxy WHEN 'stress_proxy' THEN stress_proxy END)
        WHEN 'steps_daily_lag1' THEN corr(steps_daily_lag1, CASE target WHEN 'rmssd' THEN rmssd WHEN 'mean_hr' THEN mean_hr WHEN 'recovery_proxy' THEN recovery_proxy WHEN 'stress_proxy' THEN stress_proxy END)
        WHEN 'active_kcal_daily_lag1' THEN corr(active_kcal_daily_lag1, CASE target WHEN 'rmssd' THEN rmssd WHEN 'mean_hr' THEN mean_hr WHEN 'recovery_proxy' THEN recovery_proxy WHEN 'stress_proxy' THEN stress_proxy END)
        WHEN 'exercise_minutes_daily_lag1' THEN corr(exercise_minutes_daily_lag1, CASE target WHEN 'rmssd' THEN rmssd WHEN 'mean_hr' THEN mean_hr WHEN 'recovery_proxy' THEN recovery_proxy WHEN 'stress_proxy' THEN stress_proxy END)
        WHEN 'apple_hrv_sdnn' THEN corr(apple_hrv_sdnn, CASE target WHEN 'rmssd' THEN rmssd WHEN 'mean_hr' THEN mean_hr WHEN 'recovery_proxy' THEN recovery_proxy WHEN 'stress_proxy' THEN stress_proxy END)
        WHEN 'apple_resting_hr' THEN corr(apple_resting_hr, CASE target WHEN 'rmssd' THEN rmssd WHEN 'mean_hr' THEN mean_hr WHEN 'recovery_proxy' THEN recovery_proxy WHEN 'stress_proxy' THEN stress_proxy END)
        WHEN 'apple_respiratory_rate' THEN corr(apple_respiratory_rate, CASE target WHEN 'rmssd' THEN rmssd WHEN 'mean_hr' THEN mean_hr WHEN 'recovery_proxy' THEN recovery_proxy WHEN 'stress_proxy' THEN stress_proxy END)
        WHEN 'mindful_minutes_daily' THEN corr(mindful_minutes_daily, CASE target WHEN 'rmssd' THEN rmssd WHEN 'mean_hr' THEN mean_hr WHEN 'recovery_proxy' THEN recovery_proxy WHEN 'stress_proxy' THEN stress_proxy END)
    END AS pearson_r
FROM pairs, wellness.daily_features
GROUP BY predictor, target
ORDER BY ABS(pearson_r) DESC NULLS LAST;

WITH ranked AS (
    SELECT
        *,
        RANK() OVER (ORDER BY sleep_duration_hours) AS r_sleep_duration_hours,
        RANK() OVER (ORDER BY deep_sleep_hours) AS r_deep_sleep_hours,
        RANK() OVER (ORDER BY sleep_efficiency_pct) AS r_sleep_efficiency_pct,
        RANK() OVER (ORDER BY awake_hours) AS r_awake_hours,
        RANK() OVER (ORDER BY steps_daily) AS r_steps_daily,
        RANK() OVER (ORDER BY exercise_minutes_daily) AS r_exercise_minutes_daily,
        RANK() OVER (ORDER BY steps_daily_lag1) AS r_steps_daily_lag1,
        RANK() OVER (ORDER BY exercise_minutes_daily_lag1) AS r_exercise_minutes_daily_lag1,
        RANK() OVER (ORDER BY mindful_minutes_daily) AS r_mindful_minutes_daily,
        RANK() OVER (ORDER BY rmssd) AS r_rmssd,
        RANK() OVER (ORDER BY recovery_proxy) AS r_recovery_proxy,
        RANK() OVER (ORDER BY stress_proxy) AS r_stress_proxy
    FROM wellness.daily_features
)
SELECT
    corr(r_sleep_duration_hours, r_rmssd) AS spearman_sleep_duration_rmssd,
    corr(r_deep_sleep_hours, r_rmssd) AS spearman_deep_sleep_rmssd,
    corr(r_sleep_efficiency_pct, r_rmssd) AS spearman_sleep_efficiency_rmssd,
    corr(r_awake_hours, r_stress_proxy) AS spearman_awake_stress,
    corr(r_steps_daily, r_recovery_proxy) AS spearman_steps_recovery,
    corr(r_exercise_minutes_daily, r_recovery_proxy) AS spearman_exercise_recovery,
    corr(r_steps_daily_lag1, r_rmssd) AS spearman_steps_lag1_rmssd,
    corr(r_exercise_minutes_daily_lag1, r_rmssd) AS spearman_exercise_lag1_rmssd,
    corr(r_mindful_minutes_daily, r_rmssd) AS spearman_mindful_rmssd
FROM ranked;