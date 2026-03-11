#!/usr/bin/env python3
"""
Pipeline unificado: Apple Health + Welltory -> tabela diária de correlação.

O script:
- lê export.xml do Apple Health
- extrai sono + atividade + sinais vitais principais
- lê um CSV do Welltory
- tenta mapear colunas comuns do Welltory automaticamente
- agrega tudo por dia
- junta sono da noite com a medição fisiológica do dia do despertar
- cria proxies de recuperação/stress
- exporta:
    - daily_merged_correlation_ready.csv
    - correlation_matrix_pearson.csv
    - correlation_matrix_spearman.csv
    - top_associations.csv

Uso:
    python welltory_apple_health_correlation.py /caminho/export.xml /caminho/welltory.csv
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd


# ---------------------------
# Apple Health
# ---------------------------

SLEEP_TYPE = "HKCategoryTypeIdentifierSleepAnalysis"

SLEEP_VALUE_MAP = {
    "HKCategoryValueSleepAnalysisInBed": "in_bed",
    "HKCategoryValueSleepAnalysisAwake": "awake",
    "HKCategoryValueSleepAnalysisAsleep": "asleep_unspecified",
    "HKCategoryValueSleepAnalysisAsleepCore": "asleep_core",
    "HKCategoryValueSleepAnalysisAsleepDeep": "asleep_deep",
    "HKCategoryValueSleepAnalysisAsleepREM": "asleep_rem",
}

QUANTITY_TYPES = {
    "HKQuantityTypeIdentifierHeartRate": "apple_heart_rate",
    "HKQuantityTypeIdentifierHeartRateVariabilitySDNN": "apple_hrv_sdnn",
    "HKQuantityTypeIdentifierRestingHeartRate": "apple_resting_hr",
    "HKQuantityTypeIdentifierRespiratoryRate": "apple_respiratory_rate",
    "HKQuantityTypeIdentifierOxygenSaturation": "apple_spo2",
    "HKQuantityTypeIdentifierStepCount": "steps_daily",
    "HKQuantityTypeIdentifierFlightsClimbed": "flights_climbed_daily",
    "HKQuantityTypeIdentifierActiveEnergyBurned": "active_kcal_daily",
    "HKQuantityTypeIdentifierBasalEnergyBurned": "basal_kcal_daily",
    "HKQuantityTypeIdentifierAppleExerciseTime": "exercise_minutes_daily",
    "HKQuantityTypeIdentifierVO2Max": "vo2max",
    "HKQuantityTypeIdentifierWalkingHeartRateAverage": "walking_hr_avg",
}

CATEGORY_TYPES = {
    "HKCategoryTypeIdentifierMindfulSession": "mindful_session"
}


def parse_dt(x: str) -> pd.Timestamp:
    return pd.to_datetime(x, errors="coerce")


def normalize_date_from_start(ts: pd.Series) -> pd.Series:
    return pd.to_datetime(ts).dt.date


def assign_sleep_date(start_series: pd.Series, boundary_hour: int = 15) -> pd.Series:
    sleep_date = pd.to_datetime(start_series).dt.normalize()
    mask = pd.to_datetime(start_series).dt.hour >= boundary_hour
    sleep_date = sleep_date.where(~mask, sleep_date + pd.Timedelta(days=1))
    return pd.to_datetime(sleep_date).dt.date


def parse_apple_health(xml_path: str | Path):
    xml_path = Path(xml_path)
    sleep_rows = []
    quantity_rows = []
    mindful_rows = []

    context = ET.iterparse(xml_path, events=("end",))
    for _, elem in context:
        if elem.tag != "Record":
            continue

        rtype = elem.attrib.get("type")
        start = parse_dt(elem.attrib.get("startDate"))
        end = parse_dt(elem.attrib.get("endDate"))

        if pd.isna(start) or pd.isna(end) or end < start:
            elem.clear()
            continue

        if rtype == SLEEP_TYPE:
            stage = SLEEP_VALUE_MAP.get(elem.attrib.get("value"))
            if stage:
                sleep_rows.append({
                    "start": start,
                    "end": end,
                    "stage": stage,
                    "source": elem.attrib.get("sourceName"),
                    "duration_minutes": (end - start).total_seconds() / 60.0,
                })
        elif rtype in QUANTITY_TYPES:
            quantity_rows.append({
                "start": start,
                "end": end,
                "metric": QUANTITY_TYPES[rtype],
                "value": pd.to_numeric(elem.attrib.get("value"), errors="coerce"),
                "unit": elem.attrib.get("unit"),
                "source": elem.attrib.get("sourceName"),
            })
        elif rtype in CATEGORY_TYPES:
            mindful_rows.append({
                "start": start,
                "end": end,
                "metric": CATEGORY_TYPES[rtype],
                "duration_minutes": (end - start).total_seconds() / 60.0,
            })

        elem.clear()

    sleep_df = pd.DataFrame(sleep_rows)
    qty_df = pd.DataFrame(quantity_rows)
    mindful_df = pd.DataFrame(mindful_rows)
    return sleep_df, qty_df, mindful_df


def build_daily_sleep(sleep_df: pd.DataFrame) -> pd.DataFrame:
    if sleep_df.empty:
        return pd.DataFrame(columns=["date_local"])

    df = sleep_df.copy()
    df["sleep_date"] = assign_sleep_date(df["start"])

    rows = []
    for sleep_date, g in df.groupby("sleep_date", sort=True):
        g = g.sort_values("start").reset_index(drop=True)
        asleep = g[g["stage"].isin(["asleep_unspecified", "asleep_core", "asleep_deep", "asleep_rem"])]
        awake = g[g["stage"] == "awake"]
        in_bed = g[g["stage"] == "in_bed"]

        sleep_duration = asleep["duration_minutes"].sum()
        in_bed_duration = in_bed["duration_minutes"].sum()
        deep_sleep = g.loc[g["stage"] == "asleep_deep", "duration_minutes"].sum()
        rem_sleep = g.loc[g["stage"] == "asleep_rem", "duration_minutes"].sum()
        core_sleep = g.loc[g["stage"] == "asleep_core", "duration_minutes"].sum()
        awake_minutes = awake["duration_minutes"].sum()
        efficiency = (sleep_duration / in_bed_duration * 100.0) if in_bed_duration > 0 else np.nan

        rows.append({
            "date_local": sleep_date,
            "bedtime": g["start"].min(),
            "wake_time": g["end"].max(),
            "sleep_duration_hours": round(sleep_duration / 60.0, 3),
            "in_bed_hours": round(in_bed_duration / 60.0, 3),
            "deep_sleep_hours": round(deep_sleep / 60.0, 3),
            "rem_sleep_hours": round(rem_sleep / 60.0, 3),
            "core_sleep_hours": round(core_sleep / 60.0, 3),
            "awake_hours": round(awake_minutes / 60.0, 3),
            "awakenings_count": int((awake["duration_minutes"] > 0).sum()),
            "sleep_efficiency_pct": round(efficiency, 2) if not pd.isna(efficiency) else np.nan,
            "sleep_sessions_count": int(len(g)),
        })

    return pd.DataFrame(rows)


def build_daily_apple_quantities(qty_df: pd.DataFrame, mindful_df: pd.DataFrame) -> pd.DataFrame:
    parts = []

    if not qty_df.empty:
        q = qty_df.copy()
        q["date_local"] = normalize_date_from_start(q["start"])

        # custom aggregation per metric
        agg_rows = []
        for (date_local, metric), g in q.groupby(["date_local", "metric"], sort=True):
            vals = pd.to_numeric(g["value"], errors="coerce").dropna()
            if vals.empty:
                continue

            if metric in {"steps_daily", "flights_climbed_daily", "active_kcal_daily", "basal_kcal_daily", "exercise_minutes_daily"}:
                value = vals.sum()
            elif metric in {"vo2max"}:
                value = vals.iloc[-1]
            else:
                value = vals.mean()

            agg_rows.append({
                "date_local": date_local,
                "metric": metric,
                "value": value,
            })

        if agg_rows:
            qwide = pd.DataFrame(agg_rows).pivot(index="date_local", columns="metric", values="value").reset_index()
            parts.append(qwide)

    if not mindful_df.empty:
        m = mindful_df.copy()
        m["date_local"] = normalize_date_from_start(m["start"])
        daily_m = (
            m.groupby("date_local", as_index=False)["duration_minutes"]
             .sum()
             .rename(columns={"duration_minutes": "mindful_minutes_daily"})
        )
        parts.append(daily_m)

    if not parts:
        return pd.DataFrame(columns=["date_local"])

    out = parts[0]
    for p in parts[1:]:
        out = out.merge(p, on="date_local", how="outer")
    return out


# ---------------------------
# Welltory
# ---------------------------

WELLTORY_CANDIDATES = {
    "timestamp": ["timestamp", "date", "datetime", "measured_at", "created_at", "time"],
    "RMSSD": ["rmssd", "rMSSD", "RMSSD"],
    "SDNN": ["sdnn", "SDNN"],
    "pNN50": ["pnn50", "PNN50", "pNN50"],
    "LF_HF_ratio": ["lf_hf", "lf/hf", "lf_hf_ratio", "LF/HF", "LF_HF_ratio"],
    "mean_HR": ["mean_hr", "heart_rate", "hr", "avg_hr", "meanHR"],
    "resting_HR": ["resting_hr", "rest_hr", "rhr", "restingHeartRate"],
    "measurement_quality": ["measurement_quality", "quality", "signal_quality"],
}


def standardize_columns(cols):
    out = []
    for c in cols:
        x = str(c).strip()
        x = x.replace(" ", "_")
        out.append(x)
    return out


def find_col(df: pd.DataFrame, candidates: list[str]):
    lower_map = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in lower_map:
            return lower_map[cand.lower()]
    return None


def load_welltory_csv(csv_path: str | Path) -> pd.DataFrame:
    csv_path = Path(csv_path)
    df = pd.read_csv(csv_path)
    df.columns = standardize_columns(df.columns)

    mapped = {}
    for std_name, candidates in WELLTORY_CANDIDATES.items():
        col = find_col(df, candidates)
        if col:
            mapped[std_name] = col

    if "timestamp" not in mapped:
        raise ValueError(
            "Não encontrei a coluna de timestamp no CSV do Welltory. "
            f"Colunas disponíveis: {list(df.columns)}"
        )

    out = pd.DataFrame()
    out["timestamp"] = pd.to_datetime(df[mapped["timestamp"]], errors="coerce")

    for std_name in ["RMSSD", "SDNN", "pNN50", "LF_HF_ratio", "mean_HR", "resting_HR", "measurement_quality"]:
        if std_name in mapped:
            out[std_name] = pd.to_numeric(df[mapped[std_name]], errors="coerce")

    out = out.dropna(subset=["timestamp"]).copy()
    out["date_local"] = out["timestamp"].dt.date
    return out


def pick_best_daily_measurement(w: pd.DataFrame) -> pd.DataFrame:
    if w.empty:
        return pd.DataFrame(columns=["date_local"])

    x = w.copy()

    def score_row(row):
        hour = row["timestamp"].hour
        quality = row.get("measurement_quality", np.nan)
        # manhã ganha pontos; proximidade do meio da manhã ajuda
        morning_bonus = 1 if 4 <= hour <= 12 else 0
        closeness = -abs(hour + row["timestamp"].minute / 60 - 8)
        q = 0 if pd.isna(quality) else quality
        return (morning_bonus * 1000) + (q * 10) + closeness

    x["_score"] = x.apply(score_row, axis=1)
    x = x.sort_values(["date_local", "_score"], ascending=[True, False])
    daily = x.groupby("date_local", as_index=False).first()
    return daily.drop(columns=["_score"])


# ---------------------------
# Features + correlations
# ---------------------------

def zscore(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    sd = s.std(skipna=True)
    if pd.isna(sd) or sd == 0:
        return pd.Series(np.nan, index=s.index)
    return (s - s.mean(skipna=True)) / sd


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.sort_values("date_local").reset_index(drop=True).copy()

    if "RMSSD" in out.columns:
        out["hrv_baseline_7d_rmssd"] = out["RMSSD"].rolling(7, min_periods=3).mean().shift(1)
        out["hrv_ratio_rmssd"] = out["RMSSD"] / out["hrv_baseline_7d_rmssd"]

    if "SDNN" in out.columns:
        out["sdnn_baseline_7d"] = out["SDNN"].rolling(7, min_periods=3).mean().shift(1)
        out["sdnn_ratio"] = out["SDNN"] / out["sdnn_baseline_7d"]

    if "mean_HR" in out.columns:
        out["hr_baseline_7d"] = out["mean_HR"].rolling(7, min_periods=3).mean().shift(1)
        out["hr_delta"] = out["mean_HR"] - out["hr_baseline_7d"]

    if "bedtime" in out.columns:
        bt = pd.to_datetime(out["bedtime"], errors="coerce")
        bedtime_minutes = bt.dt.hour * 60 + bt.dt.minute
        out["bedtime_minutes"] = bedtime_minutes
        out["sleep_consistency_shift_minutes"] = (bedtime_minutes - bedtime_minutes.rolling(7, min_periods=3).median().shift(1)).abs()

    if all(c in out.columns for c in ["sleep_duration_hours", "deep_sleep_hours", "sleep_efficiency_pct"]):
        out["sleep_score_custom"] = (
            zscore(out["sleep_duration_hours"]) * 0.5
            + zscore(out["deep_sleep_hours"]) * 0.3
            + zscore(out["sleep_efficiency_pct"]) * 0.2
        )

    if "steps_daily" in out.columns or "active_kcal_daily" in out.columns or "exercise_minutes_daily" in out.columns:
        components = []
        for c in ["steps_daily", "active_kcal_daily", "exercise_minutes_daily"]:
            if c in out.columns:
                components.append(zscore(out[c]))
        if components:
            out["activity_load_proxy"] = sum(components)

    if all(c in out.columns for c in ["apple_hrv_sdnn", "apple_resting_hr"]):
        out["apple_recovery_proxy"] = zscore(out["apple_hrv_sdnn"]) - zscore(out["apple_resting_hr"])
        if "apple_respiratory_rate" in out.columns:
            out["apple_recovery_proxy"] = out["apple_recovery_proxy"] - zscore(out["apple_respiratory_rate"])

    if all(c in out.columns for c in ["RMSSD", "SDNN", "mean_HR"]):
        out["recovery_proxy"] = zscore(out["RMSSD"]) + zscore(out["SDNN"]) - zscore(out["mean_HR"])

    stress_components = []
    if "RMSSD" in out.columns:
        stress_components.append(-zscore(out["RMSSD"]))
    if "SDNN" in out.columns:
        stress_components.append(-zscore(out["SDNN"]))
    if "mean_HR" in out.columns:
        stress_components.append(zscore(out["mean_HR"]))
    if "LF_HF_ratio" in out.columns:
        stress_components.append(zscore(out["LF_HF_ratio"]))
    if stress_components:
        out["stress_proxy"] = sum(stress_components)

    if "mindful_minutes_daily" in out.columns:
        out["mindfulness_flag"] = out["mindful_minutes_daily"] > 0

    for c in ["steps_daily", "active_kcal_daily", "exercise_minutes_daily", "workout_minutes_daily"]:
        if c in out.columns:
            out[f"{c}_lag1"] = out[c].shift(1)

    return out


def compute_correlations(df: pd.DataFrame):
    numeric = df.select_dtypes(include=[np.number]).copy()
    if numeric.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    pearson = numeric.corr(method="pearson")
    spearman = numeric.corr(method="spearman")

    focus_targets = [c for c in ["RMSSD", "SDNN", "mean_HR", "recovery_proxy", "stress_proxy", "hrv_ratio_rmssd"] if c in numeric.columns]
    focus_predictors = [c for c in numeric.columns if c not in focus_targets]

    rows = []
    for x in focus_predictors:
        for y in focus_targets:
            sub = df[[x, y]].dropna()
            if len(sub) < 8:
                continue
            p = sub[x].corr(sub[y], method="pearson")
            s = sub[x].corr(sub[y], method="spearman")
            rows.append({
                "predictor": x,
                "target": y,
                "n_pairs": len(sub),
                "pearson_r": p,
                "spearman_r": s,
                "abs_best_corr": max(abs(p) if pd.notna(p) else np.nan, abs(s) if pd.notna(s) else np.nan),
            })

    top = pd.DataFrame(rows)
    if not top.empty:
        top = top.sort_values(["abs_best_corr", "n_pairs"], ascending=[False, False]).reset_index(drop=True)

    return pearson, spearman, top


def main():
    if len(sys.argv) < 3:
        print("Uso: python welltory_apple_health_correlation.py /caminho/export.xml /caminho/welltory.csv")
        return 1

    apple_xml = Path(sys.argv[1])
    welltory_csv = Path(sys.argv[2])

    sleep_df, qty_df, mindful_df = parse_apple_health(apple_xml)
    daily_sleep = build_daily_sleep(sleep_df)
    daily_apple = build_daily_apple_quantities(qty_df, mindful_df)
    welltory_raw = load_welltory_csv(welltory_csv)
    welltory_daily = pick_best_daily_measurement(welltory_raw)

    merged = welltory_daily.merge(daily_sleep, on="date_local", how="left")
    merged = merged.merge(daily_apple, on="date_local", how="left")
    merged = add_features(merged)

    pearson, spearman, top = compute_correlations(merged)

    base_dir = welltory_csv.parent
    merged_path = base_dir / "daily_merged_correlation_ready.csv"
    pearson_path = base_dir / "correlation_matrix_pearson.csv"
    spearman_path = base_dir / "correlation_matrix_spearman.csv"
    top_path = base_dir / "top_associations.csv"

    merged.to_csv(merged_path, index=False)
    pearson.to_csv(pearson_path)
    spearman.to_csv(spearman_path)
    top.to_csv(top_path, index=False)

    print(f"Arquivo diário final: {merged_path}")
    print(f"Pearson: {pearson_path}")
    print(f"Spearman: {spearman_path}")
    print(f"Top associações: {top_path}")
    print(f"Dias finais: {len(merged)}")
    print(f"Colunas finais: {len(merged.columns)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
