#!/usr/bin/env python3
"""Recompute RS features with corrected benchmark-relative formulas."""

from __future__ import annotations

from datetime import date
from app.indicators.compute_features import FeatureComputer
from db.session import build_session_factory

def main():
    session_factory = build_session_factory()
    computer = FeatureComputer(session_factory)
    
    # Recompute features with corrected RS formulas
    # Use the same date range as stock data
    start_date = date(2024, 7, 8)
    end_date = date(2026, 6, 11)
    
    print(f"Recomputing RS features from {start_date} to {end_date}")
    report = computer.generate(start_date=start_date, end_date=end_date)
    
    print(f"Symbols processed: {report.symbols_processed}")
    print(f"Rows written: {report.rows_written}")
    if report.failures:
        print(f"Failures: {report.failures}")
    
    return 0 if not report.failures else 1

if __name__ == "__main__":
    raise SystemExit(main())
