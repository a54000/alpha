#!/usr/bin/env python3
"""Phase 2A five-year validation pilot infrastructure.

Reads:
  - angel_data.ohlcv_15min
  - reports/phase1b_alias_proposals.csv

Writes:
  - Pilot-only schema/tables in angel_data
  - Data-quality reports under reports/

Does not:
  - Modify production research tables
  - Rebuild features
  - Generate scores
  - Generate recommendations
  - Run backtests
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


@dataclass(frozen=True)
class ExactMatchSymbol:
    security_proposal_id: str
    angel_symbol: str
    research_symbol: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Phase 2A pilot daily bars in an isolated Angel schema.")
    parser.add_argument("--alias-proposals", default="reports/phase1b_alias_proposals.csv")
    parser.add_argument("--research-database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--angel-database-url", default=os.environ.get("ANGEL_DATABASE_URL"))
    parser.add_argument("--angel-database-name", default="angel_data")
    parser.add_argument("--source-table", default="ohlcv_15min")
    parser.add_argument("--pilot-schema", default="pilot_phase2a")
    parser.add_argument("--output-json", default="reports/phase2a_pilot_data_quality.json")
    parser.add_argument("--coverage-csv", default="reports/phase2a_daily_bar_coverage.csv")
    parser.add_argument("--issues-csv", default="reports/phase2a_daily_bar_issues.csv")
    return parser.parse_args()


def derive_angel_url(research_database_url: str | None, database_name: str) -> str | None:
    if not research_database_url:
        return None
    parts = urlsplit(research_database_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database_name}", parts.query, parts.fragment))


def load_exact_match_symbols(path: Path) -> list[ExactMatchSymbol]:
    by_security: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["alias_reason"] != "exact" or row["confidence"] != "high" or row["review_status"] != "approved":
                continue
            bucket = by_security.setdefault(row["security_proposal_id"], {})
            bucket[row["source"]] = row["symbol"]

    symbols: list[ExactMatchSymbol] = []
    for security_id, values in sorted(by_security.items()):
        research_symbol = values.get("research")
        angel_symbol = values.get("angel")
        if research_symbol and angel_symbol and research_symbol == angel_symbol:
            symbols.append(
                ExactMatchSymbol(
                    security_proposal_id=security_id,
                    research_symbol=research_symbol,
                    angel_symbol=angel_symbol,
                )
            )
    return symbols


def create_pilot_schema(connection, schema: str) -> None:
    connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
    connection.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {schema}.exact_match_universe (
                security_proposal_id text PRIMARY KEY,
                research_symbol text NOT NULL,
                angel_symbol text NOT NULL UNIQUE,
                loaded_at timestamp DEFAULT now()
            )
            """
        )
    )
    connection.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {schema}.daily_bars (
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
                has_opening_bar boolean NOT NULL,
                has_closing_bar boolean NOT NULL,
                is_partial_day boolean NOT NULL,
                source_table text NOT NULL,
                created_at timestamp DEFAULT now(),
                PRIMARY KEY (symbol, date)
            )
            """
        )
    )
    connection.execute(text(f"CREATE INDEX IF NOT EXISTS ix_phase2a_daily_bars_date ON {schema}.daily_bars (date)"))
    connection.execute(text(f"CREATE INDEX IF NOT EXISTS ix_phase2a_daily_bars_symbol_date ON {schema}.daily_bars (symbol, date)"))


def load_universe(connection, schema: str, symbols: list[ExactMatchSymbol]) -> None:
    connection.execute(text(f"TRUNCATE TABLE {schema}.exact_match_universe"))
    if not symbols:
        return
    connection.execute(
        text(
            f"""
            INSERT INTO {schema}.exact_match_universe (security_proposal_id, research_symbol, angel_symbol)
            VALUES (:security_proposal_id, :research_symbol, :angel_symbol)
            """
        ),
        [asdict(symbol) for symbol in symbols],
    )


def aggregate_daily_bars(connection, schema: str, source_table: str) -> int:
    connection.execute(text(f"TRUNCATE TABLE {schema}.daily_bars"))
    result = connection.execute(
        text(
            f"""
            WITH filtered AS (
                SELECT
                    o.symbol,
                    o.datetime,
                    o.datetime::date AS date,
                    o.open,
                    o.high,
                    o.low,
                    o.close,
                    o.volume
                FROM {source_table} o
                JOIN {schema}.exact_match_universe u
                  ON u.angel_symbol = o.symbol
                WHERE (o.datetime::time >= TIME '09:15')
                  AND (o.datetime::time <= TIME '15:15')
            ),
            grouped AS (
                SELECT
                    symbol,
                    date,
                    (ARRAY_AGG(open ORDER BY datetime ASC))[1] AS open,
                    MAX(high) AS high,
                    MIN(low) AS low,
                    (ARRAY_AGG(close ORDER BY datetime DESC))[1] AS close,
                    SUM(COALESCE(volume, 0))::bigint AS volume,
                    COUNT(*)::int AS bar_count,
                    MIN(datetime) AS first_bar_at,
                    MAX(datetime) AS last_bar_at
                FROM filtered
                GROUP BY symbol, date
            )
            INSERT INTO {schema}.daily_bars (
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
                has_opening_bar,
                has_closing_bar,
                is_partial_day,
                source_table
            )
            SELECT
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
                first_bar_at::time = TIME '09:15' AS has_opening_bar,
                last_bar_at::time = TIME '15:15' AS has_closing_bar,
                bar_count < 25 AS is_partial_day,
                :source_table AS source_table
            FROM grouped
            """
        ),
        {"source_table": source_table},
    )
    return int(result.rowcount or 0)


def fetch_quality_report(connection, schema: str, source_table: str) -> dict[str, object]:
    summary = connection.execute(
        text(
            f"""
            SELECT
                COUNT(*) AS daily_rows,
                COUNT(DISTINCT symbol) AS symbols,
                MIN(date) AS earliest_date,
                MAX(date) AS latest_date,
                COUNT(*) FILTER (WHERE is_partial_day) AS partial_days,
                COUNT(*) FILTER (WHERE NOT has_opening_bar) AS missing_opening_bar_days,
                COUNT(*) FILTER (WHERE NOT has_closing_bar) AS missing_closing_bar_days,
                COUNT(*) FILTER (
                    WHERE open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL
                       OR high < low OR high < open OR high < close OR low > open OR low > close
                       OR open <= 0 OR high <= 0 OR low <= 0 OR close <= 0
                ) AS invalid_ohlc_days,
                COUNT(*) FILTER (WHERE volume IS NULL) AS null_volume_days,
                COUNT(*) FILTER (WHERE volume = 0) AS zero_volume_days
            FROM {schema}.daily_bars
            """
        )
    ).mappings().one()

    source_duplicates = connection.execute(
        text(
            f"""
            WITH duplicate_groups AS (
                SELECT o.symbol, o.datetime, COUNT(*) AS duplicate_count
                FROM {source_table} o
                JOIN {schema}.exact_match_universe u
                  ON u.angel_symbol = o.symbol
                GROUP BY o.symbol, o.datetime
                HAVING COUNT(*) > 1
            )
            SELECT
                COUNT(*) AS duplicate_groups,
                COALESCE(SUM(duplicate_count - 1), 0) AS duplicate_extra_rows,
                COUNT(DISTINCT symbol) AS affected_symbols
            FROM duplicate_groups
            """
        )
    ).mappings().one()

    coverage = connection.execute(
        text(
            f"""
            WITH source_calendar AS (
                SELECT DISTINCT datetime::date AS trading_date
                FROM {source_table}
            ),
            symbol_ranges AS (
                SELECT symbol, MIN(date) AS first_date, MAX(date) AS last_date
                FROM {schema}.daily_bars
                GROUP BY symbol
            ),
            expected AS (
                SELECT sr.symbol, sc.trading_date
                FROM symbol_ranges sr
                JOIN source_calendar sc
                  ON sc.trading_date BETWEEN sr.first_date AND sr.last_date
            ),
            actual AS (
                SELECT symbol, date AS trading_date
                FROM {schema}.daily_bars
            ),
            gaps AS (
                SELECT e.symbol, COUNT(*) AS missing_trading_days
                FROM expected e
                LEFT JOIN actual a
                  ON a.symbol = e.symbol
                 AND a.trading_date = e.trading_date
                WHERE a.symbol IS NULL
                GROUP BY e.symbol
            )
            SELECT
                b.symbol,
                COUNT(*) AS daily_rows,
                MIN(b.date) AS first_date,
                MAX(b.date) AS last_date,
                COUNT(*) FILTER (WHERE b.is_partial_day) AS partial_days,
                COUNT(*) FILTER (WHERE NOT b.has_opening_bar) AS missing_opening_bar_days,
                COUNT(*) FILTER (WHERE NOT b.has_closing_bar) AS missing_closing_bar_days,
                COALESCE(MAX(g.missing_trading_days), 0) AS missing_trading_days
            FROM {schema}.daily_bars b
            LEFT JOIN gaps g ON g.symbol = b.symbol
            GROUP BY b.symbol
            ORDER BY b.symbol
            """
        )
    ).mappings().all()

    issues = connection.execute(
        text(
            f"""
            SELECT
                symbol,
                date,
                open,
                high,
                low,
                close,
                volume,
                bar_count,
                has_opening_bar,
                has_closing_bar,
                is_partial_day,
                CASE
                    WHEN open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL THEN 'null_ohlc'
                    WHEN high < low OR high < open OR high < close OR low > open OR low > close THEN 'invalid_ohlc'
                    WHEN open <= 0 OR high <= 0 OR low <= 0 OR close <= 0 THEN 'non_positive_price'
                    WHEN NOT has_opening_bar THEN 'missing_opening_bar'
                    WHEN NOT has_closing_bar THEN 'missing_closing_bar'
                    WHEN is_partial_day THEN 'partial_day'
                    WHEN volume = 0 THEN 'zero_volume'
                    ELSE 'none'
                END AS issue_type
            FROM {schema}.daily_bars
            WHERE open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL
               OR high < low OR high < open OR high < close OR low > open OR low > close
               OR open <= 0 OR high <= 0 OR low <= 0 OR close <= 0
               OR NOT has_opening_bar
               OR NOT has_closing_bar
               OR is_partial_day
               OR volume = 0
            ORDER BY symbol, date
            LIMIT 10000
            """
        )
    ).mappings().all()

    return {
        "generated_on": date.today().isoformat(),
        "mode": "phase2a_pilot_infrastructure",
        "production_tables_modified": False,
        "features_rebuilt": False,
        "scores_generated": False,
        "backtests_run": False,
        "summary": {key: str(value) if hasattr(value, "isoformat") else value for key, value in dict(summary).items()},
        "source_duplicate_summary": dict(source_duplicates),
        "coverage": [dict(row) for row in coverage],
        "issues": [dict(row) for row in issues],
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

    exact_symbols = load_exact_match_symbols(REPO_ROOT / args.alias_proposals)
    if len(exact_symbols) != 285:
        raise RuntimeError(f"Expected 285 exact-match securities, found {len(exact_symbols)}")

    engine = create_engine(angel_url, future=True)
    with engine.begin() as connection:
        create_pilot_schema(connection, args.pilot_schema)
        load_universe(connection, args.pilot_schema, exact_symbols)
        aggregated_rows = aggregate_daily_bars(connection, args.pilot_schema, args.source_table)
        report = fetch_quality_report(connection, args.pilot_schema, args.source_table)

    report["exact_match_security_count"] = len(exact_symbols)
    report["aggregated_daily_rows"] = aggregated_rows
    report_path = REPO_ROOT / args.output_json
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, default=json_default), encoding="utf-8")
    write_csv(REPO_ROOT / args.coverage_csv, report["coverage"])
    write_csv(REPO_ROOT / args.issues_csv, report["issues"])

    compact = {
        "exact_match_security_count": len(exact_symbols),
        "aggregated_daily_rows": aggregated_rows,
        "summary": report["summary"],
        "source_duplicate_summary": report["source_duplicate_summary"],
        "coverage_csv": str(REPO_ROOT / args.coverage_csv),
        "issues_csv": str(REPO_ROOT / args.issues_csv),
        "report_json": str(report_path),
    }
    print(json.dumps(compact, indent=2, default=json_default))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
