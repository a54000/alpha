#!/usr/bin/env python3
"""Backfill NIFTY500 index data for Relative Strength calculation."""

from __future__ import annotations

from datetime import date
from app.loaders.index_loader import IndexLoader
from db.session import build_session_factory

def main():
    session_factory = build_session_factory()
    loader = IndexLoader(session_factory)
    
    # Backfill from first stock data date to current date
    # Stock data starts around 2024-07-08
    start_date = date(2024, 6, 10)
    end_date = date(2026, 6, 11)
    
    print(f"Loading NIFTY500 data from {start_date} to {end_date}")
    result = loader.backfill("NIFTY500", start_date, end_date)
    
    print(f"Rows loaded: {result.rows_loaded}")
    if result.failures:
        print(f"Failures: {result.failures}")
    
    return 0 if not result.failures else 1

if __name__ == "__main__":
    raise SystemExit(main())
