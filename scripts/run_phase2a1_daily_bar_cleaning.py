#!/usr/bin/env python3
"""Phase 2A.1 deterministic cleaning for pilot daily bars.

Reads:
  - angel_data.pilot_phase2a.daily_bars

Writes:
  - angel_data.pilot_phase2a.daily_bars_clean
  - angel_data.pilot_phase2a.daily_bar_cleaning_audit
  - cleaning reports under reports/

Does not:
  - Modify original pilot daily bars
  - Modify production research tables
  - Rebuild features, scores, recommendations, or backtests
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean Phase 2A pilot daily bars without modifying originals.")
    parser.add_argument("--research-database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--angel-database-url", default=os.environ.get("ANGEL_DATABASE_URL"))
    parser.add_argument("--angel-database-name", default="angel_data")
    parser.add_argument("--pilot-schema", default="pilot_phase2a")
    parser.add_argument("--output-json", default="reports/phase2a1_cleaning_audit.json")
    parser.add_argument("--rejected-csv", default="reports/phase2a1_rejected_daily_bars.csv")
    parser.add_argument("--repairs-csv", default="reports/phase2a1_repaired_daily_bars.csv")
    return parser.parse_args()


def derive_angel_url(research_database_url: str | None, database_name: str) -> str | None:
    if not research_database_url:
        return None
    parts = urlsplit(research_database_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database_name}", parts.query, parts.fragment))


def create_cleaning_tables(connection, schema: str) -> None:
    connection.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {schema}.daily_bars_clean (
                symbol text NOT NULL,
                date date NOT NULL,
                open numeric,
                high numeric,
                low numeric,
                close numeric,
                volume bigint,
                bar_count integer NOT NULL,
                first_bar_at timestamptz,
                last_bar_at timestamptz,
                source_table text NOT NULL,
                original_open numeric,
                original_high numeric,
                original_low numeric,
                original_close numeric,
                cleaning_action text NOT NULL,
                cleaning_rule text NOT NULL,
                cleaning_notes text,
                cleaned_at timestamp DEFAULT now(),
                PRIMARY KEY (symbol, date)
            )
            """
        )
    )
    connection.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {schema}.daily_bar_cleaning_audit (
                audit_id bigserial PRIMARY KEY,
                symbol text NOT NULL,
                date date NOT NULL,
                action text NOT NULL,
                rule_name text NOT NULL,
                reason text NOT NULL,
                original_open numeric,
                original_high numeric,
                original_low numeric,
                original_close numeric,
                cleaned_open numeric,
                cleaned_high numeric,
                cleaned_low numeric,
                cleaned_close numeric,
                volume bigint,
                bar_count integer,
                has_opening_bar boolean,
                has_closing_bar boolean,
                is_partial_day boolean,
                audited_at timestamp DEFAULT now()
            )
            """
        )
    )
    connection.execute(text(f"CREATE INDEX IF NOT EXISTS ix_phase2a_clean_date ON {schema}.daily_bars_clean (date)"))
    connection.execute(text(f"CREATE INDEX IF NOT EXISTS ix_phase2a_clean_symbol_date ON {schema}.daily_bars_clean (symbol, date)"))
    connection.execute(text(f"CREATE INDEX IF NOT EXISTS ix_phase2a_cleaning_audit_action ON {schema}.daily_bar_cleaning_audit (action)"))
    connection.execute(text(f"CREATE INDEX IF NOT EXISTS ix_phase2a_cleaning_audit_symbol_date ON {schema}.daily_bar_cleaning_audit (symbol, date)"))


def clean_daily_bars(connection, schema: str) -> None:
    connection.execute(text(f"TRUNCATE TABLE {schema}.daily_bars_clean"))
    connection.execute(text(f"TRUNCATE TABLE {schema}.daily_bar_cleaning_audit RESTART IDENTITY"))

    connection.execute(
        text(
            f"""
            WITH classified AS (
                SELECT
                    b.*,
                    CASE
                        WHEN open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL THEN 'filter'
                        WHEN open <= 0 OR high <= 0 OR low <= 0 OR close <= 0 THEN 'filter'
                        WHEN NOT has_opening_bar THEN 'filter'
                        WHEN NOT has_closing_bar THEN 'filter'
                        WHEN is_partial_day THEN 'filter'
                        WHEN high < low OR high < open OR high < close OR low > open OR low > close THEN 'repair'
                        ELSE 'retain'
                    END AS action,
                    CASE
                        WHEN open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL THEN 'filter_null_ohlc'
                        WHEN open <= 0 OR high <= 0 OR low <= 0 OR close <= 0 THEN 'filter_non_positive_price'
                        WHEN NOT has_opening_bar THEN 'filter_missing_opening_bar'
                        WHEN NOT has_closing_bar THEN 'filter_missing_closing_bar'
                        WHEN is_partial_day THEN 'filter_partial_session'
                        WHEN high < low OR high < open OR high < close OR low > open OR low > close THEN 'repair_ohlc_bounds'
                        ELSE 'retain_clean_bar'
                    END AS rule_name,
                    CASE
                        WHEN high < low OR high < open OR high < close OR low > open OR low > close
                            THEN GREATEST(open, high, low, close)
                        ELSE high
                    END AS cleaned_high,
                    CASE
                        WHEN high < low OR high < open OR high < close OR low > open OR low > close
                            THEN LEAST(open, high, low, close)
                        ELSE low
                    END AS cleaned_low
                FROM {schema}.daily_bars b
            )
            INSERT INTO {schema}.daily_bars_clean (
                symbol,
                date,
                open,
                high,
                low,
                close,
                volume,
                bar_count,
                first_bar_at,
                last_bar_at,
                source_table,
                original_open,
                original_high,
                original_low,
                original_close,
                cleaning_action,
                cleaning_rule,
                cleaning_notes
            )
            SELECT
                symbol,
                date,
                open,
                cleaned_high,
                cleaned_low,
                close,
                volume,
                bar_count,
                first_bar_at,
                last_bar_at,
                source_table,
                open,
                high,
                low,
                close,
                action,
                rule_name,
                CASE
                    WHEN action = 'repair' THEN 'Repaired high/low to bound open/high/low/close; original OHLC retained in lineage columns.'
                    ELSE 'Retained without changes.'
                END
            FROM classified
            WHERE action IN ('retain', 'repair')
            """
        )
    )

    connection.execute(
        text(
            f"""
            WITH classified AS (
                SELECT
                    b.*,
                    CASE
                        WHEN open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL THEN 'filter'
                        WHEN open <= 0 OR high <= 0 OR low <= 0 OR close <= 0 THEN 'filter'
                        WHEN NOT has_opening_bar THEN 'filter'
                        WHEN NOT has_closing_bar THEN 'filter'
                        WHEN is_partial_day THEN 'filter'
                        WHEN high < low OR high < open OR high < close OR low > open OR low > close THEN 'repair'
                        ELSE 'retain'
                    END AS action,
                    CASE
                        WHEN open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL THEN 'filter_null_ohlc'
                        WHEN open <= 0 OR high <= 0 OR low <= 0 OR close <= 0 THEN 'filter_non_positive_price'
                        WHEN NOT has_opening_bar THEN 'filter_missing_opening_bar'
                        WHEN NOT has_closing_bar THEN 'filter_missing_closing_bar'
                        WHEN is_partial_day THEN 'filter_partial_session'
                        WHEN high < low OR high < open OR high < close OR low > open OR low > close THEN 'repair_ohlc_bounds'
                        ELSE 'retain_clean_bar'
                    END AS rule_name,
                    CASE
                        WHEN high < low OR high < open OR high < close OR low > open OR low > close
                            THEN GREATEST(open, high, low, close)
                        ELSE high
                    END AS cleaned_high,
                    CASE
                        WHEN high < low OR high < open OR high < close OR low > open OR low > close
                            THEN LEAST(open, high, low, close)
                        ELSE low
                    END AS cleaned_low
                FROM {schema}.daily_bars b
            )
            INSERT INTO {schema}.daily_bar_cleaning_audit (
                symbol,
                date,
                action,
                rule_name,
                reason,
                original_open,
                original_high,
                original_low,
                original_close,
                cleaned_open,
                cleaned_high,
                cleaned_low,
                cleaned_close,
                volume,
                bar_count,
                has_opening_bar,
                has_closing_bar,
                is_partial_day
            )
            SELECT
                symbol,
                date,
                action,
                rule_name,
                CASE
                    WHEN action = 'filter' THEN 'Rejected from clean daily bars by deterministic cleaning rule.'
                    WHEN action = 'repair' THEN 'Repaired into clean daily bars by deterministic OHLC bound rule.'
                    ELSE 'Retained in clean daily bars without repair.'
                END,
                open,
                high,
                low,
                close,
                open,
                cleaned_high,
                cleaned_low,
                close,
                volume,
                bar_count,
                has_opening_bar,
                has_closing_bar,
                is_partial_day
            FROM classified
            """
        )
    )


def fetch_report(connection, schema: str) -> dict[str, object]:
    summary = connection.execute(
        text(
            f"""
            SELECT
                (SELECT COUNT(*) FROM {schema}.daily_bars) AS source_rows,
                (SELECT COUNT(*) FROM {schema}.daily_bars_clean) AS clean_rows,
                COUNT(*) FILTER (WHERE action = 'retain') AS retained_rows,
                COUNT(*) FILTER (WHERE action = 'repair') AS repaired_rows,
                COUNT(*) FILTER (WHERE action = 'filter') AS rejected_rows,
                COUNT(DISTINCT symbol) FILTER (WHERE action <> 'retain') AS impacted_symbols,
                COUNT(DISTINCT date) FILTER (WHERE action <> 'retain') AS impacted_dates
            FROM {schema}.daily_bar_cleaning_audit
            """
        )
    ).mappings().one()

    by_rule = connection.execute(
        text(
            f"""
            SELECT action, rule_name, COUNT(*) AS rows,
                   COUNT(DISTINCT symbol) AS symbols,
                   COUNT(DISTINCT date) AS dates
            FROM {schema}.daily_bar_cleaning_audit
            GROUP BY action, rule_name
            ORDER BY action, rows DESC
            """
        )
    ).mappings().all()

    impacted_symbols = connection.execute(
        text(
            f"""
            SELECT symbol,
                   COUNT(*) FILTER (WHERE action = 'repair') AS repaired_rows,
                   COUNT(*) FILTER (WHERE action = 'filter') AS rejected_rows,
                   COUNT(*) FILTER (WHERE action <> 'retain') AS total_impacted_rows
            FROM {schema}.daily_bar_cleaning_audit
            GROUP BY symbol
            HAVING COUNT(*) FILTER (WHERE action <> 'retain') > 0
            ORDER BY total_impacted_rows DESC, symbol
            LIMIT 50
            """
        )
    ).mappings().all()

    impacted_dates = connection.execute(
        text(
            f"""
            SELECT date,
                   COUNT(*) FILTER (WHERE action = 'repair') AS repaired_rows,
                   COUNT(*) FILTER (WHERE action = 'filter') AS rejected_rows,
                   COUNT(*) FILTER (WHERE action <> 'retain') AS total_impacted_rows
            FROM {schema}.daily_bar_cleaning_audit
            GROUP BY date
            HAVING COUNT(*) FILTER (WHERE action <> 'retain') > 0
            ORDER BY total_impacted_rows DESC, date
            LIMIT 50
            """
        )
    ).mappings().all()

    return {
        "generated_on": date.today().isoformat(),
        "mode": "phase2a1_daily_bar_cleaning",
        "production_tables_modified": False,
        "features_rebuilt": False,
        "scores_generated": False,
        "recommendations_generated": False,
        "backtests_run": False,
        "summary": dict(summary),
        "by_rule": [dict(row) for row in by_rule],
        "top_impacted_symbols": [dict(row) for row in impacted_symbols],
        "top_impacted_dates": [dict(row) for row in impacted_dates],
    }


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def json_default(value):
    return str(value)


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    args = parse_args()
    research_url = args.research_database_url or os.environ.get("DATABASE_URL")
    angel_url = args.angel_database_url or derive_angel_url(research_url, args.angel_database_name)
    if not angel_url:
        raise RuntimeError("Angel database URL is required. Set ANGEL_DATABASE_URL or DATABASE_URL.")

    engine = create_engine(angel_url, future=True)
    with engine.begin() as connection:
        create_cleaning_tables(connection, args.pilot_schema)
        clean_daily_bars(connection, args.pilot_schema)
        report = fetch_report(connection, args.pilot_schema)

        rejected = connection.execute(
            text(
                f"""
                SELECT *
                FROM {args.pilot_schema}.daily_bar_cleaning_audit
                WHERE action = 'filter'
                ORDER BY symbol, date
                """
            )
        ).mappings().all()
        repairs = connection.execute(
            text(
                f"""
                SELECT *
                FROM {args.pilot_schema}.daily_bar_cleaning_audit
                WHERE action = 'repair'
                ORDER BY symbol, date
                """
            )
        ).mappings().all()

    output_json = REPO_ROOT / args.output_json
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2, default=json_default), encoding="utf-8")
    write_csv(REPO_ROOT / args.rejected_csv, [dict(row) for row in rejected])
    write_csv(REPO_ROOT / args.repairs_csv, [dict(row) for row in repairs])

    print(json.dumps(report["summary"], indent=2, default=json_default))
    print(f"Wrote cleaning audit: {output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
