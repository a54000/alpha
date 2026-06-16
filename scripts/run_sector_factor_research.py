#!/usr/bin/env python3
"""Run Phase 6.5C sector factor research."""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.research.sector_factor_analysis import SectorFactorAnalyzer
from db.session import build_session_factory


DEFAULT_FACTORS = ["rank_3m", "sector_return_1m", "sector_return_3m", "sector_return_6m"]
DEFAULT_HORIZONS = [5, 10, 20, 60]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run sector leadership factor research",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--start-date", type=str, default=None, help="Start date in YYYY-MM-DD format")
    parser.add_argument("--end-date", type=str, default=None, help="End date in YYYY-MM-DD format")
    parser.add_argument("--factor", action="append", choices=DEFAULT_FACTORS, help="Sector factor to analyze")
    parser.add_argument("--horizon", action="append", type=int, choices=DEFAULT_HORIZONS, help="Forward horizon")
    parser.add_argument(
        "--report-path",
        type=Path,
        default=Path("docs/SECTOR_FACTOR_RESEARCH.md"),
        help="Markdown report output path",
    )
    parser.add_argument(
        "--json-path",
        type=Path,
        default=Path("reports/sector_factor_results.json"),
        help="JSON results output path",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    end_date = date.fromisoformat(args.end_date) if args.end_date else date.today()
    start_date = date.fromisoformat(args.start_date) if args.start_date else end_date - timedelta(days=365)
    factors = args.factor or DEFAULT_FACTORS
    horizons = args.horizon or DEFAULT_HORIZONS

    analyzer = SectorFactorAnalyzer(build_session_factory())
    results = analyzer.run(factors, horizons, start_date, end_date)
    analyzer.write_outputs(results, args.report_path, args.json_path, start_date, end_date)

    print("Sector factor research complete")
    print(f"Date Range: {start_date} to {end_date}")
    print(f"Factors: {', '.join(factors)}")
    print(f"Horizons: {', '.join(f'{horizon}d' for horizon in horizons)}")
    print(f"Markdown: {args.report_path}")
    print(f"JSON: {args.json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
