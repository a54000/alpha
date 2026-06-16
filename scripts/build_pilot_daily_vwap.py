#!/usr/bin/env python3
"""Build persistent pilot daily VWAP from Angel 15-minute candles.

Writes only to the pilot schema in angel_data. This is a derived market-data
artifact used by research/reporting paths; it does not modify production tables
or strategy logic.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Persist pilot daily VWAP derived from ohlcv_15min.")
    parser.add_argument("--research-database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--angel-database-url", default=os.environ.get("ANGEL_DATABASE_URL"))
    parser.add_argument("--angel-database-name", default="angel_data")
    parser.add_argument("--pilot-schema", default="pilot_phase2a")
    parser.add_argument("--from-date", type=date.fromisoformat, default=None)
    parser.add_argument("--to-date", type=date.fromisoformat, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-json", default="reports/pilot_daily_vwap_build.json")
    return parser.parse_args()


def derive_angel_url(research_database_url: str | None, database_name: str) -> str | None:
    if not research_database_url:
        return None
    parts = urlsplit(research_database_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database_name}", parts.query, parts.fragment))


def create_table_sql(schema: str) -> str:
    return f"""
    CREATE TABLE IF NOT EXISTS {schema}.daily_vwap (
        symbol text NOT NULL,
        date date NOT NULL,
        daily_vwap numeric,
        bar_count integer NOT NULL,
        volume bigint,
        generated_at timestamp NOT NULL DEFAULT now(),
        PRIMARY KEY (symbol, date)
    )
    """


def build(args: argparse.Namespace) -> dict[str, object]:
    angel_url = args.angel_database_url or derive_angel_url(args.research_database_url, args.angel_database_name)
    if not angel_url:
        raise RuntimeError("ANGEL_DATABASE_URL or DATABASE_URL is required.")
    engine = create_engine(angel_url, future=True, pool_pre_ping=True)
    filters = []
    params: dict[str, object] = {}
    if args.from_date:
        filters.append("datetime::date >= :from_date")
        params["from_date"] = args.from_date
    if args.to_date:
        filters.append("datetime::date <= :to_date")
        params["to_date"] = args.to_date
    where_clause = "WHERE " + " AND ".join(filters) if filters else ""

    count_sql = text(
        f"""
        SELECT COUNT(*) AS rows,
               COUNT(DISTINCT symbol) AS symbols,
               MIN(datetime::date) AS first_date,
               MAX(datetime::date) AS last_date
        FROM (
            SELECT symbol, datetime::date
            FROM ohlcv_15min
            {where_clause}
            GROUP BY symbol, datetime::date
        ) d
        """
    )
    insert_sql = text(
        f"""
        INSERT INTO {args.pilot_schema}.daily_vwap (
            symbol, date, daily_vwap, bar_count, volume, generated_at
        )
        SELECT
            symbol,
            datetime::date AS date,
            SUM(((high + low + close) / 3.0) * volume) / NULLIF(SUM(volume), 0) AS daily_vwap,
            COUNT(*)::integer AS bar_count,
            SUM(volume)::bigint AS volume,
            now() AS generated_at
        FROM ohlcv_15min
        {where_clause}
        GROUP BY symbol, datetime::date
        ON CONFLICT (symbol, date) DO UPDATE SET
            daily_vwap = EXCLUDED.daily_vwap,
            bar_count = EXCLUDED.bar_count,
            volume = EXCLUDED.volume,
            generated_at = EXCLUDED.generated_at
        """
    )
    with engine.begin() as connection:
        estimate = connection.execute(count_sql, params).mappings().one()
        if not args.dry_run:
            connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {args.pilot_schema}"))
            connection.execute(text(create_table_sql(args.pilot_schema)))
            connection.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{args.pilot_schema}_daily_vwap_date ON {args.pilot_schema}.daily_vwap (date)"))
            connection.execute(insert_sql, params)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": bool(args.dry_run),
        "schema": args.pilot_schema,
        "table": "daily_vwap",
        "from_date": args.from_date.isoformat() if args.from_date else None,
        "to_date": args.to_date.isoformat() if args.to_date else None,
        "estimated_rows": int(estimate["rows"] or 0),
        "symbols": int(estimate["symbols"] or 0),
        "first_date": estimate["first_date"].isoformat() if estimate["first_date"] else None,
        "last_date": estimate["last_date"].isoformat() if estimate["last_date"] else None,
        "production_tables_modified": False,
    }


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    args = parse_args()
    report = build(args)
    output = REPO_ROOT / args.output_json
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"Wrote daily VWAP build report: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
