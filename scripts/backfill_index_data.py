#!/usr/bin/env python3
"""Backfill or incrementally refresh benchmark index data."""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.loaders.index_loader import IndexLoader
from db.session import build_session_factory


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load NIFTY500 benchmark data into index_prices_daily.")
    parser.add_argument("--index-name", default="NIFTY500", help="Internal benchmark name. Default: NIFTY500.")
    parser.add_argument("--start-date", default="2024-06-10", help="Inclusive start date, YYYY-MM-DD.")
    parser.add_argument(
        "--end-date",
        default=(date.today() + timedelta(days=1)).isoformat(),
        help="Inclusive end date, YYYY-MM-DD. Defaults to tomorrow so today's completed yfinance data is not missed.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    start_date = date.fromisoformat(args.start_date)
    end_date = date.fromisoformat(args.end_date)
    if end_date < start_date:
        raise ValueError("--end-date must be on or after --start-date")

    session_factory = build_session_factory()
    loader = IndexLoader(session_factory)

    print(f"Loading {args.index_name} data from {start_date} to {end_date} inclusive")
    result = loader.backfill(args.index_name, start_date, end_date)

    print(f"Rows upserted: {result.rows_loaded}")
    if result.failures:
        print(f"Failures: {result.failures}")

    return 0 if not result.failures else 1

if __name__ == "__main__":
    raise SystemExit(main())
