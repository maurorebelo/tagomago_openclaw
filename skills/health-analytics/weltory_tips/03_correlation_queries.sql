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

-- Quantile analysis: steps quintiles vs avg_rmssd (detect optimal zone)
WITH steps_quantiles AS (
    SELECT
        rmssd,
        steps_daily,
        NTILE(5) OVER (ORDER BY steps_daily) AS q
    FROM wellness.daily_features
    WHERE steps_daily IS NOT NULL
      AND rmssd IS NOT NULL
)
SELECT
    q AS steps_bucket,
    COUNT(*) AS n,
    ROUND(AVG(steps_daily), 0) AS avg_steps,
    ROUND(AVG(rmssd), 2) AS avg_rmssd
FROM steps_quantiles
GROUP BY q
ORDER BY q;

-- Sleep deficit: sleep_delta vs baseline (30d rolling), often stronger HRV signal than raw duration
WITH sleep_baseline AS (
    SELECT
        date_local,
        sleep_duration_hours,
        rmssd,
        AVG(sleep_duration_hours) OVER (
            ORDER BY date_local
            ROWS BETWEEN 30 PRECEDING AND CURRENT ROW
        ) AS baseline_sleep
    FROM wellness.daily_features
    WHERE sleep_duration_hours IS NOT NULL AND rmssd IS NOT NULL
),
sleep_deficit AS (
    SELECT
        date_local,
        rmssd,
        sleep_duration_hours,
        baseline_sleep,
        sleep_duration_hours - baseline_sleep AS sleep_delta
    FROM sleep_baseline
)
SELECT
    CASE
        WHEN sleep_delta < -1 THEN 'sleep_deficit'
        WHEN sleep_delta BETWEEN -1 AND 1 THEN 'normal_sleep'
        WHEN sleep_delta > 1 THEN 'extra_sleep'
    END AS sleep_state,
    COUNT(*) AS n,
    ROUND(AVG(rmssd), 2) AS avg_rmssd
FROM sleep_deficit
GROUP BY sleep_state
ORDER BY avg_rmssd;

-- Exercise recovery curve: exercise impacts HRV with delay (same_day vs lag1/lag2/lag3)
WITH ex_lags AS (
    SELECT
        exercise_minutes_daily,
        rmssd,
        LAG(exercise_minutes_daily, 1) OVER (ORDER BY date_local) AS exercise_minutes_daily_lag1,
        LAG(exercise_minutes_daily, 2) OVER (ORDER BY date_local) AS exercise_minutes_daily_lag2,
        LAG(exercise_minutes_daily, 3) OVER (ORDER BY date_local) AS exercise_minutes_daily_lag3
    FROM wellness.daily_features
    WHERE exercise_minutes_daily IS NOT NULL AND rmssd IS NOT NULL
)
SELECT
    corr(exercise_minutes_daily, rmssd) AS same_day,
    corr(exercise_minutes_daily_lag1, rmssd) AS lag1,
    corr(exercise_minutes_daily_lag2, rmssd) AS lag2,
    corr(exercise_minutes_daily_lag3, rmssd) AS lag3
FROM ex_lags;

-- Interaction: exercise improves HRV only when sleep is good (good_sleep vs poor_sleep, exercise vs no exercise)
SELECT
    CASE
        WHEN sleep_efficiency_pct >= 90 THEN 'good_sleep'
        ELSE 'poor_sleep'
    END AS sleep_quality,
    AVG(rmssd) FILTER (WHERE exercise_minutes_daily > 30) AS rmssd_exercise,
    AVG(rmssd) FILTER (WHERE exercise_minutes_daily <= 30) AS rmssd_no_exercise
FROM wellness.daily_features
WHERE sleep_efficiency_pct IS NOT NULL AND rmssd IS NOT NULL
GROUP BY sleep_quality
ORDER BY sleep_quality;