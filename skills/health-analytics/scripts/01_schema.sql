-- Consolidated schema for health-analytics skill (from weltory_tips/01_duckdb_schema.sql).
-- raw_* use source_table so auto_populate_raw_tables.py can insert without schema change.
CREATE SCHEMA IF NOT EXISTS wellness;

CREATE TABLE IF NOT EXISTS wellness.raw_welltory (
    source_table VARCHAR,
    row_id BIGINT,
    timestamp TIMESTAMP,
    date_local DATE,
    rmssd DOUBLE,
    sdnn DOUBLE,
    pnn50 DOUBLE,
    lf_hf_ratio DOUBLE,
    mean_hr DOUBLE,
    resting_hr DOUBLE,
    measurement_quality DOUBLE,
    raw_json JSON
);

CREATE TABLE IF NOT EXISTS wellness.raw_apple_sleep_sessions (
    source_table VARCHAR,
    row_id BIGINT,
    start_ts TIMESTAMP,
    end_ts TIMESTAMP,
    sleep_date DATE,
    stage VARCHAR,
    duration_minutes DOUBLE,
    source_name VARCHAR
);

CREATE TABLE IF NOT EXISTS wellness.raw_apple_quantities (
    source_table VARCHAR,
    row_id BIGINT,
    start_ts TIMESTAMP,
    end_ts TIMESTAMP,
    date_local DATE,
    metric VARCHAR,
    value DOUBLE,
    unit VARCHAR,
    source_name VARCHAR
);

CREATE TABLE IF NOT EXISTS wellness.raw_apple_mindful_sessions (
    source_table VARCHAR,
    row_id BIGINT,
    start_ts TIMESTAMP,
    end_ts TIMESTAMP,
    date_local DATE,
    duration_minutes DOUBLE
);

CREATE TABLE IF NOT EXISTS wellness.sleep_nights (
    date_local DATE PRIMARY KEY,
    bedtime TIMESTAMP,
    wake_time TIMESTAMP,
    sleep_duration_hours DOUBLE,
    in_bed_hours DOUBLE,
    deep_sleep_hours DOUBLE,
    rem_sleep_hours DOUBLE,
    core_sleep_hours DOUBLE,
    unspecified_sleep_hours DOUBLE,
    awake_hours DOUBLE,
    awakenings_count INTEGER,
    sleep_efficiency_pct DOUBLE,
    sleep_sessions_count INTEGER
);

CREATE TABLE IF NOT EXISTS wellness.hrv_daily (
    date_local DATE PRIMARY KEY,
    measurement_ts TIMESTAMP,
    rmssd DOUBLE,
    sdnn DOUBLE,
    pnn50 DOUBLE,
    lf_hf_ratio DOUBLE,
    mean_hr DOUBLE,
    resting_hr DOUBLE,
    measurement_quality DOUBLE
);

CREATE TABLE IF NOT EXISTS wellness.activity_daily (
    date_local DATE PRIMARY KEY,
    steps_daily DOUBLE,
    flights_climbed_daily DOUBLE,
    active_kcal_daily DOUBLE,
    basal_kcal_daily DOUBLE,
    exercise_minutes_daily DOUBLE,
    workout_minutes_daily DOUBLE,
    workout_sessions_daily DOUBLE
);

CREATE TABLE IF NOT EXISTS wellness.physiology_daily (
    date_local DATE PRIMARY KEY,
    apple_hrv_sdnn DOUBLE,
    apple_resting_hr DOUBLE,
    apple_heart_rate DOUBLE,
    apple_respiratory_rate DOUBLE,
    apple_spo2 DOUBLE,
    vo2max DOUBLE,
    walking_hr_avg DOUBLE,
    mindful_minutes_daily DOUBLE
);

CREATE TABLE IF NOT EXISTS wellness.daily_features (
    date_local DATE PRIMARY KEY,
    measurement_ts TIMESTAMP,

    rmssd DOUBLE,
    sdnn DOUBLE,
    pnn50 DOUBLE,
    lf_hf_ratio DOUBLE,
    mean_hr DOUBLE,
    resting_hr DOUBLE,
    measurement_quality DOUBLE,

    bedtime TIMESTAMP,
    wake_time TIMESTAMP,
    sleep_duration_hours DOUBLE,
    in_bed_hours DOUBLE,
    deep_sleep_hours DOUBLE,
    rem_sleep_hours DOUBLE,
    core_sleep_hours DOUBLE,
    unspecified_sleep_hours DOUBLE,
    awake_hours DOUBLE,
    awakenings_count INTEGER,
    sleep_efficiency_pct DOUBLE,
    sleep_sessions_count INTEGER,

    steps_daily DOUBLE,
    flights_climbed_daily DOUBLE,
    active_kcal_daily DOUBLE,
    basal_kcal_daily DOUBLE,
    exercise_minutes_daily DOUBLE,
    workout_minutes_daily DOUBLE,
    workout_sessions_daily DOUBLE,

    apple_hrv_sdnn DOUBLE,
    apple_resting_hr DOUBLE,
    apple_heart_rate DOUBLE,
    apple_respiratory_rate DOUBLE,
    apple_spo2 DOUBLE,
    vo2max DOUBLE,
    walking_hr_avg DOUBLE,
    mindful_minutes_daily DOUBLE,

    rmssd_baseline_7d DOUBLE,
    sdnn_baseline_7d DOUBLE,
    hr_baseline_7d DOUBLE,
    hrv_ratio_rmssd DOUBLE,
    sdnn_ratio DOUBLE,
    hr_delta DOUBLE,
    sleep_score_custom DOUBLE,
    recovery_proxy DOUBLE,
    stress_proxy DOUBLE,
    activity_load_proxy DOUBLE,
    apple_recovery_proxy DOUBLE,
    bedtime_minutes DOUBLE,
    sleep_consistency_shift_minutes DOUBLE,
    steps_daily_lag1 DOUBLE,
    active_kcal_daily_lag1 DOUBLE,
    exercise_minutes_daily_lag1 DOUBLE,
    workout_minutes_daily_lag1 DOUBLE
);
