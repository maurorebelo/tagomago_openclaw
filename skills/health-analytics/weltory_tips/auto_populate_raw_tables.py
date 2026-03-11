#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import duckdb

RAW_SCHEMA_SQL = '''
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

CREATE TABLE IF NOT EXISTS wellness._autopopulate_audit (
    run_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    target_table VARCHAR,
    source_table VARCHAR,
    strategy VARCHAR,
    mapping_json JSON,
    inserted_rows BIGINT
);
'''

def qident(x: str) -> str:
    return '"' + x.replace('"', '""') + '"'

def fq(schema: str, table: str) -> str:
    return f'{qident(schema)}.{qident(table)}'

def norm(s: str) -> str:
    return re.sub(r'[^a-z0-9]+', '', s.lower())

def first_present(cols: List[str], candidates: List[str]) -> Optional[str]:
    nmap = {norm(c): c for c in cols}
    for cand in candidates:
        key = norm(cand)
        if key in nmap:
            return nmap[key]
    return None

def score_presence(cols: List[str], groups: List[List[str]]) -> int:
    score = 0
    for g in groups:
        if first_present(cols, g):
            score += 1
    return score

@dataclass
class TableMeta:
    schema: str
    table: str
    columns: List[str]

    @property
    def full_name(self) -> str:
        return f"{self.schema}.{self.table}"

class AutoPopulator:
    def __init__(self, db_path: str, schema: str = 'wellness', clear_targets: bool = False):
        self.db_path = db_path
        self.schema = schema
        self.clear_targets = clear_targets
        self.con = duckdb.connect(db_path)

    def setup(self) -> None:
        self.con.execute(RAW_SCHEMA_SQL)
        if self.clear_targets:
            for t in [
                'raw_welltory',
                'raw_apple_sleep_sessions',
                'raw_apple_quantities',
                'raw_apple_mindful_sessions',
            ]:
                self.con.execute(f"DELETE FROM {fq(self.schema, t)}")

    def list_tables(self) -> List[TableMeta]:
        rows = self.con.execute("""
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_type = 'BASE TABLE'
            ORDER BY 1, 2
        """).fetchall()

        out = []
        for schema, table in rows:
            if schema == self.schema and table.startswith('raw_'):
                continue
            cols = [r[0] for r in self.con.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = ? AND table_name = ?
                ORDER BY ordinal_position
            """, [schema, table]).fetchall()]
            out.append(TableMeta(schema, table, cols))
        return out

    def insert_audit(self, target: str, source: str, strategy: str, mapping: Dict, inserted_rows: int) -> None:
        self.con.execute(
            f"""
            INSERT INTO {fq(self.schema, '_autopopulate_audit')}
            (target_table, source_table, strategy, mapping_json, inserted_rows)
            VALUES (?, ?, ?, ?, ?)
            """,
            [target, source, strategy, json.dumps(mapping), inserted_rows],
        )

    def candidate_welltory(self, tables: List[TableMeta]) -> List[Tuple[int, TableMeta]]:
        scored = []
        for t in tables:
            cols = t.columns
            score = 0
            if first_present(cols, ['timestamp', 'datetime', 'date', 'created_at', 'measured_at', 'time']):
                score += 3
            score += 2 * score_presence(cols, [
                ['rmssd'],
                ['sdnn'],
                ['pnn50'],
                ['lf_hf_ratio', 'lf/hf', 'lf_hf', 'lfhf'],
                ['mean_hr', 'heart_rate', 'avg_hr', 'hr'],
                ['resting_hr', 'rest_hr', 'rhr'],
                ['measurement_quality', 'quality', 'signal_quality'],
            ])
            if 'welltory' in norm(t.table) or 'hrv' in norm(t.table):
                score += 2
            if score >= 5:
                scored.append((score, t))
        return sorted(scored, key=lambda x: (-x[0], x[1].full_name))

    def candidate_sleep(self, tables: List[TableMeta]) -> List[Tuple[int, TableMeta]]:
        scored = []
        for t in tables:
            cols = t.columns
            score = 0
            if first_present(cols, ['start_ts', 'start', 'startDate', 'start_time', 'from']):
                score += 2
            if first_present(cols, ['end_ts', 'end', 'endDate', 'end_time', 'to']):
                score += 2
            if first_present(cols, ['stage', 'value', 'sleep_stage', 'category_value']):
                score += 2
            if first_present(cols, ['type', 'record_type', 'category_type']):
                score += 1
            if 'sleep' in norm(t.table):
                score += 3
            # Prefer sleep_phases (Apple Health) over sleep_events when both exist
            if 'phase' in norm(t.table):
                score += 2
            if score >= 5:
                scored.append((score, t))
        return sorted(scored, key=lambda x: (-x[0], x[1].full_name))

    def candidate_quantities(self, tables: List[TableMeta]) -> List[Tuple[int, TableMeta]]:
        scored = []
        for t in tables:
            cols = t.columns
            score = 0
            if first_present(cols, ['metric', 'type', 'record_type', 'quantity_type', 'name']):
                score += 2
            if first_present(cols, ['value', 'val', 'measurement_value']):
                score += 2
            if first_present(cols, ['start_ts', 'start', 'startDate', 'date', 'timestamp']):
                score += 2
            if first_present(cols, ['end_ts', 'end', 'endDate']):
                score += 1
            if first_present(cols, ['unit']):
                score += 1
            if 'apple' in norm(t.table) or 'health' in norm(t.table) or 'quantity' in norm(t.table):
                score += 2
            # Wide daily format (e.g. apple_quantity_daily: date_local + steps_daily, active_kcal_daily, ...)
            if first_present(cols, ['date_local', 'date', 'day']) and first_present(
                cols, ['steps_daily', 'active_kcal_daily', 'exercise_minutes_daily', 'steps', 'basal_kcal_daily']
            ):
                score += 5
            if t.table == 'apple_quantity_daily' or 'apple_quantity_daily' in norm(t.table):
                score += 3
            if score >= 5:
                scored.append((score, t))
        return sorted(scored, key=lambda x: (-x[0], x[1].full_name))

    def candidate_mindful(self, tables: List[TableMeta]) -> List[Tuple[int, TableMeta]]:
        scored = []
        for t in tables:
            cols = t.columns
            score = 0
            if first_present(cols, ['start_ts', 'start', 'startDate', 'date', 'timestamp']):
                score += 2
            if first_present(cols, ['end_ts', 'end', 'endDate', 'duration_minutes', 'duration']):
                score += 2
            if first_present(cols, ['type', 'record_type', 'metric', 'category_type', 'name']):
                score += 2
            if 'mindful' in norm(t.table) or 'meditat' in norm(t.table):
                score += 3
            if score >= 5:
                scored.append((score, t))
        return sorted(scored, key=lambda x: (-x[0], x[1].full_name))

    def _expr_ts(self, col: Optional[str], fallback: str = 'NULL') -> str:
        if not col:
            return fallback
        # Apple Health export uses "YYYY-MM-DD HH:MM:SS -0300" (space before tz); normalize for DuckDB
        normalized = f"REPLACE(REPLACE(TRIM(CAST({qident(col)} AS VARCHAR)), ' -', '-'), ' +', '+')"
        return f"TRY_CAST({normalized} AS TIMESTAMP)"

    def _expr_num(self, col: Optional[str], fallback: str = 'NULL') -> str:
        if not col:
            return fallback
        return f"TRY_CAST({qident(col)} AS DOUBLE)"

    def populate_welltory(self, t: TableMeta) -> int:
        cols = t.columns
        mapping = {
            'timestamp': first_present(cols, ['timestamp', 'datetime', 'date', 'created_at', 'measured_at', 'time']),
            'rmssd': first_present(cols, ['rmssd']),
            'sdnn': first_present(cols, ['sdnn']),
            'pnn50': first_present(cols, ['pnn50']),
            'lf_hf_ratio': first_present(cols, ['lf_hf_ratio', 'lf/hf', 'lf_hf', 'lfhf']),
            'mean_hr': first_present(cols, ['mean_hr', 'heart_rate', 'avg_hr', 'hr']),
            'resting_hr': first_present(cols, ['resting_hr', 'rest_hr', 'rhr']),
            'measurement_quality': first_present(cols, ['measurement_quality', 'quality', 'signal_quality']),
        }
        if not mapping['timestamp']:
            return 0

        sql = f"""
        INSERT INTO {fq(self.schema, 'raw_welltory')}
        (source_table, row_id, timestamp, date_local, rmssd, sdnn, pnn50, lf_hf_ratio, mean_hr, resting_hr, measurement_quality, raw_json)
        SELECT
            '{t.full_name}',
            ROW_NUMBER() OVER (),
            {self._expr_ts(mapping['timestamp'])},
            CAST({self._expr_ts(mapping['timestamp'])} AS DATE),
            {self._expr_num(mapping['rmssd'])},
            {self._expr_num(mapping['sdnn'])},
            {self._expr_num(mapping['pnn50'])},
            {self._expr_num(mapping['lf_hf_ratio'])},
            {self._expr_num(mapping['mean_hr'])},
            {self._expr_num(mapping['resting_hr'])},
            {self._expr_num(mapping['measurement_quality'])},
            NULL::JSON
        FROM {fq(t.schema, t.table)}
        WHERE {self._expr_ts(mapping['timestamp'])} IS NOT NULL
        """
        before = self.con.execute(f"SELECT COUNT(*) FROM {fq(self.schema, 'raw_welltory')}").fetchone()[0]
        self.con.execute(sql)
        after = self.con.execute(f"SELECT COUNT(*) FROM {fq(self.schema, 'raw_welltory')}").fetchone()[0]
        inserted = after - before
        self.insert_audit('raw_welltory', t.full_name, 'direct_column_mapping', mapping, inserted)
        return inserted

    def populate_sleep(self, t: TableMeta) -> int:
        cols = t.columns
        c_start = first_present(cols, ['start_ts', 'start', 'startDate', 'start_time', 'from'])
        c_end = first_present(cols, ['end_ts', 'end', 'endDate', 'end_time', 'to'])
        c_stage = first_present(cols, ['stage', 'value', 'sleep_stage', 'category_value'])
        c_type = first_present(cols, ['type', 'record_type', 'category_type'])
        c_source = first_present(cols, ['source_name', 'source', 'device', 'app'])

        if not c_start or not c_end:
            return 0

        stage_expr = 'NULL'
        if c_stage:
            stage_expr = f"""
            CASE
                WHEN LOWER(CAST({qident(c_stage)} AS VARCHAR)) LIKE '%deep%' THEN 'asleep_deep'
                WHEN LOWER(CAST({qident(c_stage)} AS VARCHAR)) LIKE '%rem%' THEN 'asleep_rem'
                WHEN LOWER(CAST({qident(c_stage)} AS VARCHAR)) LIKE '%core%' OR LOWER(CAST({qident(c_stage)} AS VARCHAR)) LIKE '%light%' THEN 'asleep_core'
                WHEN LOWER(CAST({qident(c_stage)} AS VARCHAR)) LIKE '%awake%' THEN 'awake'
                WHEN LOWER(CAST({qident(c_stage)} AS VARCHAR)) LIKE '%inbed%' OR LOWER(CAST({qident(c_stage)} AS VARCHAR)) LIKE '%in_bed%' THEN 'in_bed'
                WHEN LOWER(CAST({qident(c_stage)} AS VARCHAR)) LIKE '%asleep%' THEN 'asleep_unspecified'
                ELSE NULL
            END
            """

        filters = [f"{self._expr_ts(c_start)} IS NOT NULL", f"{self._expr_ts(c_end)} IS NOT NULL"]
        if c_type:
            filters.append(f"(LOWER(CAST({qident(c_type)} AS VARCHAR)) LIKE '%sleep%' OR LOWER(CAST({qident(c_type)} AS VARCHAR)) LIKE '%sleepanalysis%')")
        elif c_stage:
            filters.append(f"({stage_expr}) IS NOT NULL")

        source_expr = f"CAST({qident(c_source)} AS VARCHAR)" if c_source else 'NULL'

        sql = f"""
        INSERT INTO {fq(self.schema, 'raw_apple_sleep_sessions')}
        (source_table, row_id, start_ts, end_ts, sleep_date, stage, duration_minutes, source_name)
        SELECT
            '{t.full_name}',
            ROW_NUMBER() OVER (),
            {self._expr_ts(c_start)},
            {self._expr_ts(c_end)},
            CAST(
                CASE
                    WHEN EXTRACT('hour' FROM {self._expr_ts(c_start)}) >= 15
                    THEN CAST({self._expr_ts(c_start)} AS DATE) + 1
                    ELSE CAST({self._expr_ts(c_start)} AS DATE)
                END
            AS DATE),
            {stage_expr},
            EXTRACT(EPOCH FROM ({self._expr_ts(c_end)} - {self._expr_ts(c_start)})) / 60.0,
            {source_expr}
        FROM {fq(t.schema, t.table)}
        WHERE {' AND '.join(filters)}
          AND {self._expr_ts(c_end)} >= {self._expr_ts(c_start)}
        """
        before = self.con.execute(f"SELECT COUNT(*) FROM {fq(self.schema, 'raw_apple_sleep_sessions')}").fetchone()[0]
        self.con.execute(sql)
        after = self.con.execute(f"SELECT COUNT(*) FROM {fq(self.schema, 'raw_apple_sleep_sessions')}").fetchone()[0]
        inserted = after - before
        self.insert_audit(
            'raw_apple_sleep_sessions',
            t.full_name,
            'sleep_stage_mapping',
            {'start': c_start, 'end': c_end, 'stage': c_stage, 'type': c_type, 'source': c_source},
            inserted
        )
        return inserted

    def populate_quantities(self, t: TableMeta) -> int:
        cols = t.columns
        c_metric = first_present(cols, ['metric', 'type', 'record_type', 'quantity_type', 'name'])
        c_value = first_present(cols, ['value', 'val', 'measurement_value'])
        c_unit = first_present(cols, ['unit'])
        c_start = first_present(cols, ['start_ts', 'start', 'startDate', 'timestamp', 'date'])
        c_end = first_present(cols, ['end_ts', 'end', 'endDate'])
        c_source = first_present(cols, ['source_name', 'source', 'device', 'app'])

        before = self.con.execute(f"SELECT COUNT(*) FROM {fq(self.schema, 'raw_apple_quantities')}").fetchone()[0]

        if c_metric and c_value and c_start:
            metric_expr = f"""
            CASE
                WHEN LOWER(CAST({qident(c_metric)} AS VARCHAR)) LIKE '%heart_rate_variability_sdnn%' OR LOWER(CAST({qident(c_metric)} AS VARCHAR)) LIKE '%hrv_sdnn%' THEN 'apple_hrv_sdnn'
                WHEN LOWER(CAST({qident(c_metric)} AS VARCHAR)) LIKE '%restingheart%' OR LOWER(CAST({qident(c_metric)} AS VARCHAR)) LIKE '%resting_heart%' THEN 'apple_resting_hr'
                WHEN LOWER(CAST({qident(c_metric)} AS VARCHAR)) LIKE '%heartrate%' OR LOWER(CAST({qident(c_metric)} AS VARCHAR)) LIKE '%heart_rate%' THEN 'apple_heart_rate'
                WHEN LOWER(CAST({qident(c_metric)} AS VARCHAR)) LIKE '%respiratory%' THEN 'apple_respiratory_rate'
                WHEN LOWER(CAST({qident(c_metric)} AS VARCHAR)) LIKE '%oxygensaturation%' OR LOWER(CAST({qident(c_metric)} AS VARCHAR)) LIKE '%spo2%' THEN 'apple_spo2'
                WHEN LOWER(CAST({qident(c_metric)} AS VARCHAR)) LIKE '%stepcount%' OR LOWER(CAST({qident(c_metric)} AS VARCHAR)) LIKE '%steps%' THEN 'steps_daily'
                WHEN LOWER(CAST({qident(c_metric)} AS VARCHAR)) LIKE '%flightsclimbed%' OR LOWER(CAST({qident(c_metric)} AS VARCHAR)) LIKE '%flights%' THEN 'flights_climbed_daily'
                WHEN LOWER(CAST({qident(c_metric)} AS VARCHAR)) LIKE '%activeenergy%' OR LOWER(CAST({qident(c_metric)} AS VARCHAR)) LIKE '%active_kcal%' THEN 'active_kcal_daily'
                WHEN LOWER(CAST({qident(c_metric)} AS VARCHAR)) LIKE '%basalenergy%' OR LOWER(CAST({qident(c_metric)} AS VARCHAR)) LIKE '%basal_kcal%' THEN 'basal_kcal_daily'
                WHEN LOWER(CAST({qident(c_metric)} AS VARCHAR)) LIKE '%exercise%' THEN 'exercise_minutes_daily'
                WHEN LOWER(CAST({qident(c_metric)} AS VARCHAR)) LIKE '%vo2max%' THEN 'vo2max'
                WHEN LOWER(CAST({qident(c_metric)} AS VARCHAR)) LIKE '%walkingheartrateaverage%' OR LOWER(CAST({qident(c_metric)} AS VARCHAR)) LIKE '%walking_hr_avg%' THEN 'walking_hr_avg'
                WHEN LOWER(CAST({qident(c_metric)} AS VARCHAR)) LIKE '%workout_minutes%' THEN 'workout_minutes_daily'
                WHEN LOWER(CAST({qident(c_metric)} AS VARCHAR)) LIKE '%workout_sessions%' THEN 'workout_sessions_daily'
                ELSE NULL
            END
            """
            source_expr = f"CAST({qident(c_source)} AS VARCHAR)" if c_source else 'NULL'
            end_expr = self._expr_ts(c_end, self._expr_ts(c_start))
            sql = f"""
            INSERT INTO {fq(self.schema, 'raw_apple_quantities')}
            (source_table, row_id, start_ts, end_ts, date_local, metric, value, unit, source_name)
            SELECT
                '{t.full_name}',
                ROW_NUMBER() OVER (),
                {self._expr_ts(c_start)},
                {end_expr},
                CAST({self._expr_ts(c_start)} AS DATE),
                {metric_expr},
                {self._expr_num(c_value)},
                {f"CAST({qident(c_unit)} AS VARCHAR)" if c_unit else 'NULL'},
                {source_expr}
            FROM {fq(t.schema, t.table)}
            WHERE {self._expr_ts(c_start)} IS NOT NULL
              AND {self._expr_num(c_value)} IS NOT NULL
              AND ({metric_expr}) IS NOT NULL
            """
            self.con.execute(sql)
            after = self.con.execute(f"SELECT COUNT(*) FROM {fq(self.schema, 'raw_apple_quantities')}").fetchone()[0]
            inserted = after - before
            self.insert_audit(
                'raw_apple_quantities',
                t.full_name,
                'long_metric_mapping',
                {'metric': c_metric, 'value': c_value, 'start': c_start, 'end': c_end, 'unit': c_unit, 'source': c_source},
                inserted
            )
            return inserted

        c_date = first_present(cols, ['date_local', 'date', 'day', 'timestamp'])
        if not c_date:
            return 0

        wide_metric_map = {
            'steps_daily': first_present(cols, ['steps_daily', 'steps', 'step_count']),
            'flights_climbed_daily': first_present(cols, ['flights_climbed_daily', 'flights_climbed', 'flights']),
            'active_kcal_daily': first_present(cols, ['active_kcal_daily', 'active_energy', 'active_energy_burned', 'active_kcal']),
            'basal_kcal_daily': first_present(cols, ['basal_kcal_daily', 'basal_energy', 'basal_energy_burned', 'basal_kcal']),
            'exercise_minutes_daily': first_present(cols, ['exercise_minutes_daily', 'exercise_minutes', 'apple_exercise_time']),
            'workout_minutes_daily': first_present(cols, ['workout_minutes_daily', 'workout_minutes']),
            'workout_sessions_daily': first_present(cols, ['workout_sessions_daily', 'workout_sessions']),
            'apple_hrv_sdnn': first_present(cols, ['apple_hrv_sdnn', 'hrv_sdnn', 'heart_rate_variability_sdnn']),
            'apple_resting_hr': first_present(cols, ['apple_resting_hr', 'resting_hr', 'resting_heart_rate']),
            'apple_heart_rate': first_present(cols, ['apple_heart_rate', 'heart_rate']),
            'apple_respiratory_rate': first_present(cols, ['apple_respiratory_rate', 'respiratory_rate']),
            'apple_spo2': first_present(cols, ['apple_spo2', 'oxygen_saturation', 'spo2']),
            'vo2max': first_present(cols, ['vo2max']),
            'walking_hr_avg': first_present(cols, ['walking_hr_avg', 'walking_heart_rate_average']),
        }

        unions = []
        for metric, col in wide_metric_map.items():
            if not col:
                continue
            unions.append(f"""
            SELECT
                '{t.full_name}' AS source_table,
                ROW_NUMBER() OVER () AS row_id,
                TRY_CAST({qident(c_date)} AS TIMESTAMP) AS start_ts,
                TRY_CAST({qident(c_date)} AS TIMESTAMP) AS end_ts,
                CAST(TRY_CAST({qident(c_date)} AS TIMESTAMP) AS DATE) AS date_local,
                '{metric}' AS metric,
                TRY_CAST({qident(col)} AS DOUBLE) AS value,
                NULL::VARCHAR AS unit,
                NULL::VARCHAR AS source_name
            FROM {fq(t.schema, t.table)}
            WHERE TRY_CAST({qident(c_date)} AS TIMESTAMP) IS NOT NULL
              AND TRY_CAST({qident(col)} AS DOUBLE) IS NOT NULL
            """)

        if not unions:
            return 0

        sql = f"""
        INSERT INTO {fq(self.schema, 'raw_apple_quantities')}
        (source_table, row_id, start_ts, end_ts, date_local, metric, value, unit, source_name)
        {' UNION ALL '.join(unions)}
        """
        self.con.execute(sql)
        after = self.con.execute(f"SELECT COUNT(*) FROM {fq(self.schema, 'raw_apple_quantities')}").fetchone()[0]
        inserted = after - before
        self.insert_audit('raw_apple_quantities', t.full_name, 'wide_daily_unpivot', wide_metric_map, inserted)
        return inserted

    def populate_mindful(self, t: TableMeta) -> int:
        cols = t.columns
        c_start = first_present(cols, ['start_ts', 'start', 'startDate', 'timestamp', 'date'])
        c_end = first_present(cols, ['end_ts', 'end', 'endDate'])
        c_duration = first_present(cols, ['duration_minutes', 'duration', 'minutes'])
        c_type = first_present(cols, ['type', 'record_type', 'metric', 'category_type', 'name'])
        c_value = first_present(cols, ['mindful_minutes_daily', 'mindful_minutes'])

        before = self.con.execute(f"SELECT COUNT(*) FROM {fq(self.schema, 'raw_apple_mindful_sessions')}").fetchone()[0]

        if c_start and (c_end or c_duration) and c_type:
            end_expr = self._expr_ts(c_end) if c_end else f"{self._expr_ts(c_start)} + (TRY_CAST({qident(c_duration)} AS DOUBLE) * INTERVAL '1 minute')"
            sql = f"""
            INSERT INTO {fq(self.schema, 'raw_apple_mindful_sessions')}
            (source_table, row_id, start_ts, end_ts, date_local, duration_minutes)
            SELECT
                '{t.full_name}',
                ROW_NUMBER() OVER (),
                {self._expr_ts(c_start)},
                {end_expr},
                CAST({self._expr_ts(c_start)} AS DATE),
                EXTRACT(EPOCH FROM ({end_expr} - {self._expr_ts(c_start)})) / 60.0
            FROM {fq(t.schema, t.table)}
            WHERE {self._expr_ts(c_start)} IS NOT NULL
              AND LOWER(CAST({qident(c_type)} AS VARCHAR)) LIKE '%mindful%'
            """
            self.con.execute(sql)
            after = self.con.execute(f"SELECT COUNT(*) FROM {fq(self.schema, 'raw_apple_mindful_sessions')}").fetchone()[0]
            inserted = after - before
            self.insert_audit(
                'raw_apple_mindful_sessions',
                t.full_name,
                'mindful_type_filter',
                {'start': c_start, 'end': c_end, 'duration': c_duration, 'type': c_type},
                inserted
            )
            return inserted

        if c_start and c_value:
            sql = f"""
            INSERT INTO {fq(self.schema, 'raw_apple_mindful_sessions')}
            (source_table, row_id, start_ts, end_ts, date_local, duration_minutes)
            SELECT
                '{t.full_name}',
                ROW_NUMBER() OVER (),
                TRY_CAST({qident(c_start)} AS TIMESTAMP),
                TRY_CAST({qident(c_start)} AS TIMESTAMP) + (TRY_CAST({qident(c_value)} AS DOUBLE) * INTERVAL '1 minute'),
                CAST(TRY_CAST({qident(c_start)} AS TIMESTAMP) AS DATE),
                TRY_CAST({qident(c_value)} AS DOUBLE)
            FROM {fq(t.schema, t.table)}
            WHERE TRY_CAST({qident(c_start)} AS TIMESTAMP) IS NOT NULL
              AND TRY_CAST({qident(c_value)} AS DOUBLE) IS NOT NULL
            """
            self.con.execute(sql)
            after = self.con.execute(f"SELECT COUNT(*) FROM {fq(self.schema, 'raw_apple_mindful_sessions')}").fetchone()[0]
            inserted = after - before
            self.insert_audit(
                'raw_apple_mindful_sessions',
                t.full_name,
                'wide_daily_mindful',
                {'date': c_start, 'mindful_minutes': c_value},
                inserted
            )
            return inserted

        return 0

    def run(self) -> Dict:
        self.setup()
        tables = self.list_tables()

        result = {
            'db_path': self.db_path,
            'tables_scanned': [t.full_name for t in tables],
            'selected_sources': {},
            'inserted_rows': {},
        }

        welltory_cands = self.candidate_welltory(tables)
        sleep_cands = self.candidate_sleep(tables)
        quantity_cands = self.candidate_quantities(tables)
        mindful_cands = self.candidate_mindful(tables)

        inserted = {
            'raw_welltory': 0,
            'raw_apple_sleep_sessions': 0,
            'raw_apple_quantities': 0,
            'raw_apple_mindful_sessions': 0,
        }

        if welltory_cands:
            src = welltory_cands[0][1]
            result['selected_sources']['raw_welltory'] = src.full_name
            inserted['raw_welltory'] = self.populate_welltory(src)

        if sleep_cands:
            src = sleep_cands[0][1]
            result['selected_sources']['raw_apple_sleep_sessions'] = src.full_name
            inserted['raw_apple_sleep_sessions'] = self.populate_sleep(src)

        qty_sources = []
        for _, src in quantity_cands[:4]:
            qty_sources.append(src.full_name)
            inserted['raw_apple_quantities'] += self.populate_quantities(src)
        if qty_sources:
            result['selected_sources']['raw_apple_quantities'] = qty_sources

        if mindful_cands:
            src = mindful_cands[0][1]
            result['selected_sources']['raw_apple_mindful_sessions'] = src.full_name
            inserted['raw_apple_mindful_sessions'] = self.populate_mindful(src)

        result['inserted_rows'] = inserted
        result['final_counts'] = {
            'raw_welltory': self.con.execute(f"SELECT COUNT(*) FROM {fq(self.schema, 'raw_welltory')}").fetchone()[0],
            'raw_apple_sleep_sessions': self.con.execute(f"SELECT COUNT(*) FROM {fq(self.schema, 'raw_apple_sleep_sessions')}").fetchone()[0],
            'raw_apple_quantities': self.con.execute(f"SELECT COUNT(*) FROM {fq(self.schema, 'raw_apple_quantities')}").fetchone()[0],
            'raw_apple_mindful_sessions': self.con.execute(f"SELECT COUNT(*) FROM {fq(self.schema, 'raw_apple_mindful_sessions')}").fetchone()[0],
        }
        return result

def main() -> int:
    parser = argparse.ArgumentParser(description='Popula wellness.raw_* automaticamente a partir da DuckDB atual.')
    parser.add_argument('db_path', help='Caminho para o arquivo .duckdb')
    parser.add_argument('--schema', default='wellness', help='Schema de destino')
    parser.add_argument('--clear-targets', action='store_true', help='Limpa as raw_* antes de inserir')
    parser.add_argument('--report-json', default=None, help='Salva um relatório JSON opcional')
    args = parser.parse_args()

    ap = AutoPopulator(args.db_path, schema=args.schema, clear_targets=args.clear_targets)
    result = ap.run()

    print(json.dumps(result, indent=2, ensure_ascii=False))
    if args.report_json:
        with open(args.report_json, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

    return 0

if __name__ == '__main__':
    raise SystemExit(main())