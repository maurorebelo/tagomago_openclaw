-- Build normalised tables and daily_features from wellness.raw_* (from weltory_tips/02_build_daily_features.sql).
CREATE OR REPLACE TEMP TABLE _welltory_scored AS
SELECT
    *,
    (
        CASE WHEN EXTRACT('hour' FROM timestamp) BETWEEN 4 AND 12 THEN 1000 ELSE 0 END
        + COALESCE(measurement_quality, 0) * 10
        - ABS(EXTRACT('hour' FROM timestamp) + EXTRACT('minute' FROM timestamp) / 60.0 - 8)
    ) AS score_rank
FROM wellness.raw_welltory
WHERE timestamp IS NOT NULL;

CREATE OR REPLACE TABLE wellness.hrv_daily AS
WITH ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY date_local
            ORDER BY score_rank DESC, timestamp ASC
        ) AS rn
    FROM _welltory_scored
)
SELECT
    date_local,
    timestamp AS measurement_ts,
    rmssd,
    sdnn,
    pnn50,
    lf_hf_ratio,
    mean_hr,
    resting_hr,
    measurement_quality
FROM ranked
WHERE rn = 1;

CREATE OR REPLACE TABLE wellness.sleep_nights AS
SELECT
    sleep_date AS date_local,
    MIN(start_ts) AS bedtime,
    MAX(end_ts) AS wake_time,
    SUM(CASE WHEN stage IN ('asleep_unspecified','asleep_core','asleep_deep','asleep_rem') THEN duration_minutes ELSE 0 END) / 60.0 AS sleep_duration_hours,
    SUM(CASE WHEN stage = 'in_bed' THEN duration_minutes ELSE 0 END) / 60.0 AS in_bed_hours,
    SUM(CASE WHEN stage = 'asleep_deep' THEN duration_minutes ELSE 0 END) / 60.0 AS deep_sleep_hours,
    SUM(CASE WHEN stage = 'asleep_rem' THEN duration_minutes ELSE 0 END) / 60.0 AS rem_sleep_hours,
    SUM(CASE WHEN stage = 'asleep_core' THEN duration_minutes ELSE 0 END) / 60.0 AS core_sleep_hours,
    SUM(CASE WHEN stage = 'asleep_unspecified' THEN duration_minutes ELSE 0 END) / 60.0 AS unspecified_sleep_hours,
    SUM(CASE WHEN stage = 'awake' THEN duration_minutes ELSE 0 END) / 60.0 AS awake_hours,
    SUM(CASE WHEN stage = 'awake' AND duration_minutes > 0 THEN 1 ELSE 0 END) AS awakenings_count,
    CASE
        WHEN SUM(CASE WHEN stage = 'in_bed' THEN duration_minutes ELSE 0 END) > 0
        THEN 100.0 * SUM(CASE WHEN stage IN ('asleep_unspecified','asleep_core','asleep_deep','asleep_rem') THEN duration_minutes ELSE 0 END)
             / SUM(CASE WHEN stage = 'in_bed' THEN duration_minutes ELSE 0 END)
        ELSE NULL
    END AS sleep_efficiency_pct,
    COUNT(*) AS sleep_sessions_count
FROM wellness.raw_apple_sleep_sessions
GROUP BY 1;

CREATE OR REPLACE TABLE wellness.activity_daily AS
SELECT
    date_local,
    SUM(CASE WHEN metric = 'steps_daily' THEN value END) AS steps_daily,
    SUM(CASE WHEN metric = 'flights_climbed_daily' THEN value END) AS flights_climbed_daily,
    SUM(CASE WHEN metric = 'active_kcal_daily' THEN value END) AS active_kcal_daily,
    SUM(CASE WHEN metric = 'basal_kcal_daily' THEN value END) AS basal_kcal_daily,
    SUM(CASE WHEN metric = 'exercise_minutes_daily' THEN value END) AS exercise_minutes_daily,
    SUM(CASE WHEN metric = 'workout_minutes_daily' THEN value END) AS workout_minutes_daily,
    SUM(CASE WHEN metric = 'workout_sessions_daily' THEN value END) AS workout_sessions_daily
FROM wellness.raw_apple_quantities
GROUP BY 1;

CREATE OR REPLACE TABLE wellness.physiology_daily AS
SELECT
    q.date_local,
    AVG(CASE WHEN metric = 'apple_hrv_sdnn' THEN value END) AS apple_hrv_sdnn,
    AVG(CASE WHEN metric = 'apple_resting_hr' THEN value END) AS apple_resting_hr,
    AVG(CASE WHEN metric = 'apple_heart_rate' THEN value END) AS apple_heart_rate,
    AVG(CASE WHEN metric = 'apple_respiratory_rate' THEN value END) AS apple_respiratory_rate,
    AVG(CASE WHEN metric = 'apple_spo2' THEN value END) AS apple_spo2,
    MAX(CASE WHEN metric = 'vo2max' THEN value END) AS vo2max,
    AVG(CASE WHEN metric = 'walking_hr_avg' THEN value END) AS walking_hr_avg,
    m.mindful_minutes_daily
FROM wellness.raw_apple_quantities q
LEFT JOIN (
    SELECT date_local, SUM(duration_minutes) AS mindful_minutes_daily
    FROM wellness.raw_apple_mindful_sessions
    GROUP BY 1
) m USING (date_local)
GROUP BY q.date_local, m.mindful_minutes_daily;

CREATE OR REPLACE TEMP TABLE _daily_base AS
SELECT
    h.date_local,
    h.measurement_ts,
    h.rmssd,
    h.sdnn,
    h.pnn50,
    h.lf_hf_ratio,
    h.mean_hr,
    h.resting_hr,
    h.measurement_quality,

    s.bedtime,
    s.wake_time,
    s.sleep_duration_hours,
    s.in_bed_hours,
    s.deep_sleep_hours,
    s.rem_sleep_hours,
    s.core_sleep_hours,
    s.unspecified_sleep_hours,
    s.awake_hours,
    s.awakenings_count,
    s.sleep_efficiency_pct,
    s.sleep_sessions_count,

    a.steps_daily,
    a.flights_climbed_daily,
    a.active_kcal_daily,
    a.basal_kcal_daily,
    a.exercise_minutes_daily,
    a.workout_minutes_daily,
    a.workout_sessions_daily,

    p.apple_hrv_sdnn,
    p.apple_resting_hr,
    p.apple_heart_rate,
    p.apple_respiratory_rate,
    p.apple_spo2,
    p.vo2max,
    p.walking_hr_avg,
    p.mindful_minutes_daily
FROM wellness.hrv_daily h
LEFT JOIN wellness.sleep_nights s USING (date_local)
LEFT JOIN wellness.activity_daily a USING (date_local)
LEFT JOIN wellness.physiology_daily p USING (date_local);

CREATE OR REPLACE TABLE wellness.daily_features AS
WITH base AS (
    SELECT
        *,
        AVG(rmssd) OVER (ORDER BY date_local ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING) AS rmssd_baseline_7d,
        AVG(sdnn) OVER (ORDER BY date_local ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING) AS sdnn_baseline_7d,
        AVG(mean_hr) OVER (ORDER BY date_local ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING) AS hr_baseline_7d,
        EXTRACT('hour' FROM bedtime) * 60.0 + EXTRACT('minute' FROM bedtime) AS bedtime_minutes,
        MEDIAN(EXTRACT('hour' FROM bedtime) * 60.0 + EXTRACT('minute' FROM bedtime)) OVER (
            ORDER BY date_local ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING
        ) AS bedtime_median_7d,
        LAG(steps_daily, 1) OVER (ORDER BY date_local) AS steps_daily_lag1,
        LAG(active_kcal_daily, 1) OVER (ORDER BY date_local) AS active_kcal_daily_lag1,
        LAG(exercise_minutes_daily, 1) OVER (ORDER BY date_local) AS exercise_minutes_daily_lag1,
        LAG(workout_minutes_daily, 1) OVER (ORDER BY date_local) AS workout_minutes_daily_lag1
    FROM _daily_base
),
stats AS (
    SELECT
        AVG(rmssd) AS mean_rmssd, STDDEV_SAMP(rmssd) AS sd_rmssd,
        AVG(sdnn) AS mean_sdnn, STDDEV_SAMP(sdnn) AS sd_sdnn,
        AVG(mean_hr) AS mean_mean_hr, STDDEV_SAMP(mean_hr) AS sd_mean_hr,
        AVG(lf_hf_ratio) AS mean_lf_hf, STDDEV_SAMP(lf_hf_ratio) AS sd_lf_hf,
        AVG(sleep_duration_hours) AS mean_sleep_dur, STDDEV_SAMP(sleep_duration_hours) AS sd_sleep_dur,
        AVG(deep_sleep_hours) AS mean_deep_sleep, STDDEV_SAMP(deep_sleep_hours) AS sd_deep_sleep,
        AVG(sleep_efficiency_pct) AS mean_sleep_eff, STDDEV_SAMP(sleep_efficiency_pct) AS sd_sleep_eff,
        AVG(steps_daily) AS mean_steps, STDDEV_SAMP(steps_daily) AS sd_steps,
        AVG(active_kcal_daily) AS mean_active_kcal, STDDEV_SAMP(active_kcal_daily) AS sd_active_kcal,
        AVG(exercise_minutes_daily) AS mean_ex_min, STDDEV_SAMP(exercise_minutes_daily) AS sd_ex_min,
        AVG(apple_hrv_sdnn) AS mean_apple_hrv, STDDEV_SAMP(apple_hrv_sdnn) AS sd_apple_hrv,
        AVG(apple_resting_hr) AS mean_apple_rhr, STDDEV_SAMP(apple_resting_hr) AS sd_apple_rhr,
        AVG(apple_respiratory_rate) AS mean_resp, STDDEV_SAMP(apple_respiratory_rate) AS sd_resp
    FROM base
)
SELECT
    b.*,
    CASE WHEN b.rmssd_baseline_7d IS NOT NULL AND b.rmssd_baseline_7d != 0 THEN b.rmssd / b.rmssd_baseline_7d END AS hrv_ratio_rmssd,
    CASE WHEN b.sdnn_baseline_7d IS NOT NULL AND b.sdnn_baseline_7d != 0 THEN b.sdnn / b.sdnn_baseline_7d END AS sdnn_ratio,
    CASE WHEN b.hr_baseline_7d IS NOT NULL THEN b.mean_hr - b.hr_baseline_7d END AS hr_delta,

    CASE
        WHEN s.sd_sleep_dur IS NOT NULL AND s.sd_deep_sleep IS NOT NULL AND s.sd_sleep_eff IS NOT NULL
        THEN ((b.sleep_duration_hours - s.mean_sleep_dur) / NULLIF(s.sd_sleep_dur, 0)) * 0.5
           + ((b.deep_sleep_hours - s.mean_deep_sleep) / NULLIF(s.sd_deep_sleep, 0)) * 0.3
           + ((b.sleep_efficiency_pct - s.mean_sleep_eff) / NULLIF(s.sd_sleep_eff, 0)) * 0.2
    END AS sleep_score_custom,

    CASE
        WHEN s.sd_rmssd IS NOT NULL AND s.sd_sdnn IS NOT NULL AND s.sd_mean_hr IS NOT NULL
        THEN ((b.rmssd - s.mean_rmssd) / NULLIF(s.sd_rmssd, 0))
           + ((b.sdnn - s.mean_sdnn) / NULLIF(s.sd_sdnn, 0))
           - ((b.mean_hr - s.mean_mean_hr) / NULLIF(s.sd_mean_hr, 0))
    END AS recovery_proxy,

    CASE
        WHEN s.sd_rmssd IS NOT NULL OR s.sd_sdnn IS NOT NULL OR s.sd_mean_hr IS NOT NULL OR s.sd_lf_hf IS NOT NULL
        THEN -((b.rmssd - s.mean_rmssd) / NULLIF(s.sd_rmssd, 0))
           - ((b.sdnn - s.mean_sdnn) / NULLIF(s.sd_sdnn, 0))
           + ((b.mean_hr - s.mean_mean_hr) / NULLIF(s.sd_mean_hr, 0))
           + ((b.lf_hf_ratio - s.mean_lf_hf) / NULLIF(s.sd_lf_hf, 0))
    END AS stress_proxy,

    CASE
        WHEN s.sd_steps IS NOT NULL OR s.sd_active_kcal IS NOT NULL OR s.sd_ex_min IS NOT NULL
        THEN ((b.steps_daily - s.mean_steps) / NULLIF(s.sd_steps, 0))
           + ((b.active_kcal_daily - s.mean_active_kcal) / NULLIF(s.sd_active_kcal, 0))
           + ((b.exercise_minutes_daily - s.mean_ex_min) / NULLIF(s.sd_ex_min, 0))
    END AS activity_load_proxy,

    CASE
        WHEN s.sd_apple_hrv IS NOT NULL AND s.sd_apple_rhr IS NOT NULL
        THEN ((b.apple_hrv_sdnn - s.mean_apple_hrv) / NULLIF(s.sd_apple_hrv, 0))
           - ((b.apple_resting_hr - s.mean_apple_rhr) / NULLIF(s.sd_apple_rhr, 0))
           - ((b.apple_respiratory_rate - s.mean_resp) / NULLIF(s.sd_resp, 0))
    END AS apple_recovery_proxy,

    ABS(b.bedtime_minutes - b.bedtime_median_7d) AS sleep_consistency_shift_minutes
FROM base b
CROSS JOIN stats s;
