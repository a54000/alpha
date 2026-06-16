#!/usr/bin/env python3
"""Read-only audit for the Angel SmartAPI 15-minute database."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from db.session import build_session_factory


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit Angel SmartAPI 15-minute OHLCV data without modifying data.")
    parser.add_argument("--angel-database-url", default=os.environ.get("ANGEL_DATABASE_URL"))
    parser.add_argument("--research-database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--database-name", default="angel_data")
    parser.add_argument("--table", default="ohlcv_15min")
    parser.add_argument("--output", default="reports/angel_data_audit.json")
    parser.add_argument("--max-symbol-examples", type=int, default=75)
    return parser.parse_args()


def derive_angel_url(research_database_url: str | None, database_name: str) -> str | None:
    if not research_database_url:
        return None
    parts = urlsplit(research_database_url)
    path = f"/{database_name}"
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))


def current_research_symbols(research_database_url: str | None) -> list[str]:
    if not research_database_url:
        return []
    session_factory = build_session_factory(research_database_url)
    with session_factory() as session:
        snapshot_date = session.execute(text("SELECT MAX(date) FROM universe_snapshot WHERE index_name = 'NSE500'")).scalar()
        if snapshot_date is not None:
            rows = session.execute(
                text(
                    """
                    SELECT symbol
                    FROM universe_snapshot
                    WHERE index_name = 'NSE500' AND date = :snapshot_date
                    ORDER BY symbol
                    """
                ),
                {"snapshot_date": snapshot_date},
            ).scalars()
            return list(rows)
        rows = session.execute(
            text("SELECT symbol FROM symbol_master WHERE nse500 = true ORDER BY symbol")
        ).scalars()
        return list(rows)


def audit_angel_data(
    *,
    angel_database_url: str,
    research_symbols: list[str],
    table_name: str,
    max_symbol_examples: int,
) -> dict[str, object]:
    engine = create_engine(angel_database_url, future=True)
    with engine.connect() as connection:
        table_exists = connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = current_schema()
                  AND table_name = :table_name
                """
            ),
            {"table_name": table_name},
        ).scalar_one()
        if int(table_exists) == 0:
            return {
                "status": "blocked",
                "reason": f"Table not found in angel_data: {table_name}",
                "table": table_name,
            }

        total_rows = int(connection.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar_one())
        distinct_symbols = int(connection.execute(text(f"SELECT COUNT(DISTINCT symbol) FROM {table_name}")).scalar_one())
        date_range = connection.execute(
            text(f"SELECT MIN(datetime)::date, MAX(datetime)::date FROM {table_name}")
        ).one()

        per_symbol_rows = connection.execute(
            text(
                f"""
                SELECT symbol,
                       COUNT(*) AS rows,
                       COUNT(DISTINCT datetime::date) AS trading_days,
                       MIN(datetime)::date AS earliest_date,
                       MAX(datetime)::date AS latest_date,
                       MIN(datetime) AS earliest_timestamp,
                       MAX(datetime) AS latest_timestamp
                FROM {table_name}
                GROUP BY symbol
                ORDER BY symbol
                """
            )
        ).mappings().all()

        source_symbols = {row["symbol"] for row in per_symbol_rows}
        missing_symbols = [symbol for symbol in research_symbols if symbol not in source_symbols]

        duplicate_summary = connection.execute(
            text(
                f"""
                WITH duplicate_groups AS (
                    SELECT symbol, datetime, COUNT(*) AS duplicate_count
                    FROM {table_name}
                    GROUP BY symbol, datetime
                    HAVING COUNT(*) > 1
                )
                SELECT COUNT(*) AS duplicate_groups,
                       COALESCE(SUM(duplicate_count - 1), 0) AS duplicate_extra_rows,
                       COUNT(DISTINCT symbol) AS affected_symbols
                FROM duplicate_groups
                """
            )
        ).mappings().one()

        duplicate_examples = connection.execute(
            text(
                f"""
                SELECT symbol, datetime, COUNT(*) AS duplicate_count
                FROM {table_name}
                GROUP BY symbol, datetime
                HAVING COUNT(*) > 1
                ORDER BY duplicate_count DESC, symbol, datetime
                LIMIT :limit
                """
            ),
            {"limit": max_symbol_examples},
        ).mappings().all()

        ohlc_summary = connection.execute(
            text(
                f"""
                SELECT
                    COUNT(*) FILTER (
                        WHERE high < low
                           OR high < open
                           OR high < close
                           OR low > open
                           OR low > close
                    ) AS invalid_rows,
                    COUNT(DISTINCT symbol) FILTER (
                        WHERE high < low
                           OR high < open
                           OR high < close
                           OR low > open
                           OR low > close
                    ) AS affected_symbols
                FROM {table_name}
                """
            )
        ).mappings().one()

        ohlc_examples = connection.execute(
            text(
                f"""
                SELECT symbol, datetime, open, high, low, close
                FROM {table_name}
                WHERE high < low
                   OR high < open
                   OR high < close
                   OR low > open
                   OR low > close
                ORDER BY symbol, datetime
                LIMIT :limit
                """
            ),
            {"limit": max_symbol_examples},
        ).mappings().all()

        volume_summary = connection.execute(
            text(
                f"""
                SELECT
                    COUNT(*) FILTER (WHERE volume IS NULL) AS null_volume_rows,
                    COUNT(*) FILTER (WHERE volume = 0) AS zero_volume_rows,
                    COUNT(DISTINCT symbol) FILTER (WHERE volume IS NULL OR volume = 0) AS affected_symbols
                FROM {table_name}
                """
            )
        ).mappings().one()

        gap_rows = connection.execute(
            text(
                f"""
                WITH source_calendar AS (
                    SELECT DISTINCT datetime::date AS trading_date
                    FROM {table_name}
                ),
                symbol_ranges AS (
                    SELECT symbol, MIN(datetime)::date AS first_date, MAX(datetime)::date AS last_date
                    FROM {table_name}
                    GROUP BY symbol
                ),
                expected AS (
                    SELECT sr.symbol, sc.trading_date
                    FROM symbol_ranges sr
                    JOIN source_calendar sc
                      ON sc.trading_date BETWEEN sr.first_date AND sr.last_date
                ),
                actual AS (
                    SELECT DISTINCT symbol, datetime::date AS trading_date
                    FROM {table_name}
                )
                SELECT e.symbol,
                       COUNT(*) AS missing_trading_days,
                       MIN(e.trading_date) AS first_missing_date,
                       MAX(e.trading_date) AS last_missing_date
                FROM expected e
                LEFT JOIN actual a
                  ON a.symbol = e.symbol
                 AND a.trading_date = e.trading_date
                WHERE a.symbol IS NULL
                GROUP BY e.symbol
                ORDER BY missing_trading_days DESC, e.symbol
                LIMIT :limit
                """
            ),
            {"limit": max_symbol_examples},
        ).mappings().all()

        day_coverage = connection.execute(
            text(
                f"""
                SELECT datetime::date AS trading_date,
                       COUNT(DISTINCT symbol) AS symbols,
                       COUNT(*) AS rows
                FROM {table_name}
                GROUP BY datetime::date
                ORDER BY datetime::date
                """
            )
        ).mappings().all()

    sparse_symbols = [
        row
        for row in per_symbol_rows
        if row["trading_days"] < max(1, int(0.9 * max((item["trading_days"] for item in per_symbol_rows), default=0)))
    ][:max_symbol_examples]

    exclusion_candidates = sorted(
        set(missing_symbols)
        | {row["symbol"] for row in gap_rows if row["missing_trading_days"] > 20}
        | {row["symbol"] for row in ohlc_examples}
        | {row["symbol"] for row in duplicate_examples},
    )

    hard_failures = [
        int(duplicate_summary["duplicate_extra_rows"] or 0) > 0,
        int(ohlc_summary["invalid_rows"] or 0) > 0,
        len(missing_symbols) > 0,
    ]
    suitability = "conditional" if any(hard_failures) else "suitable"

    return {
        "status": "completed",
        "generated_on": date.today().isoformat(),
        "database": "angel_data",
        "table": table_name,
        "summary": {
            "total_rows": total_rows,
            "distinct_symbol_count": distinct_symbols,
            "earliest_date": str(date_range[0]) if date_range[0] else None,
            "latest_date": str(date_range[1]) if date_range[1] else None,
            "research_symbol_count": len(research_symbols),
            "missing_symbol_count": len(missing_symbols),
            "suitability": suitability,
        },
        "per_symbol_coverage": [dict(row) for row in per_symbol_rows[:max_symbol_examples]],
        "missing_symbols": missing_symbols,
        "data_gaps_by_symbol": [dict(row) for row in gap_rows],
        "duplicate_records": {
            "summary": dict(duplicate_summary),
            "examples": [dict(row) for row in duplicate_examples],
        },
        "ohlc_consistency": {
            "summary": dict(ohlc_summary),
            "examples": [dict(row) for row in ohlc_examples],
        },
        "volume_completeness": dict(volume_summary),
        "trading_day_coverage": {
            "total_trading_days": len(day_coverage),
            "first_10_days": [dict(row) for row in day_coverage[:10]],
            "last_10_days": [dict(row) for row in day_coverage[-10:]],
            "lowest_symbol_count_days": sorted(
                [dict(row) for row in day_coverage],
                key=lambda row: (row["symbols"], row["trading_date"]),
            )[:max_symbol_examples],
        },
        "sparse_symbol_examples": [dict(row) for row in sparse_symbols],
        "exclusion_candidates": exclusion_candidates[:max_symbol_examples],
        "research_conclusion": {
            "complete_enough_for_research": suitability == "suitable",
            "daily_bars_can_be_derived": int(ohlc_summary["invalid_rows"] or 0) == 0
            and int(duplicate_summary["duplicate_extra_rows"] or 0) == 0,
            "notes": [
                "Daily bars should be derived only after duplicate and OHLC issues are resolved or excluded.",
                "Gap counts use the Angel source-wide trading calendar between each symbol's first and last date.",
                "This audit is read-only and does not aggregate or modify data.",
            ],
        },
    }


def json_default(value):
    return str(value)


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    args = parse_args()
    research_url = args.research_database_url or os.environ.get("DATABASE_URL")
    angel_url = args.angel_database_url or derive_angel_url(research_url, args.database_name)

    if not angel_url:
        payload = {
            "status": "blocked",
            "reason": "ANGEL_DATABASE_URL is not set and DATABASE_URL could not be used to derive angel_data URL.",
            "database": args.database_name,
            "table": args.table,
        }
    else:
        try:
            research_symbols = current_research_symbols(research_url)
            payload = audit_angel_data(
                angel_database_url=angel_url,
                research_symbols=research_symbols,
                table_name=args.table,
                max_symbol_examples=args.max_symbol_examples,
            )
        except Exception as exc:
            payload = {
                "status": "blocked",
                "generated_on": date.today().isoformat(),
                "database": args.database_name,
                "table": args.table,
                "reason": str(exc),
                "research_conclusion": {
                    "complete_enough_for_research": False,
                    "daily_bars_can_be_derived": False,
                    "notes": ["Audit could not connect to the Angel database; no data was modified."],
                },
            }

    output_path = REPO_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, default=json_default), encoding="utf-8")
    print(json.dumps(payload, indent=2, default=json_default))
    print(f"\nWrote audit report: {output_path}")
    return 0 if payload.get("status") == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
