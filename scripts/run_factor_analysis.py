#!/usr/bin/env python3
"""Run factor analysis on the database.

This script analyzes the predictive power of individual scoring components
by computing their correlation with forward returns.
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta

from app.research.factor_analysis import FactorAnalyzer
from db.session import build_session_factory


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Run factor analysis on scoring components",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    
    parser.add_argument(
        "--horizon",
        type=int,
        default=20,
        help="Forward return horizon in days",
    )
    
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="Start date in YYYY-MM-DD format",
    )
    
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="End date in YYYY-MM-DD format",
    )
    
    parser.add_argument(
        "--factor",
        type=str,
        default=None,
        help="Single factor name to analyze (if omitted, analyze all supported factors)",
    )
    
    return parser.parse_args()


def main() -> int:
    """Run factor analysis on supported factors."""
    args = parse_args()
    
    session_factory = build_session_factory()
    analyzer = FactorAnalyzer(session_factory)
    
    # Supported factors
    all_factor_names = [
        'rs_rank_pct',
        'volume_ratio',
        'adx_14',
        'rsi_14',
        'macd_hist',
        'stoch_k',
        'pct_from_52w_high',
        'bb_width',
    ]
    
    # Filter factors if --factor argument provided
    if args.factor:
        if args.factor not in all_factor_names:
            print(f"Error: Factor '{args.factor}' is not supported.")
            print(f"Supported factors: {', '.join(all_factor_names)}")
            return 1
        factor_names = [args.factor]
    else:
        factor_names = all_factor_names
    
    # Parse dates or use defaults (last 6 months)
    if args.start_date:
        start_date = date.fromisoformat(args.start_date)
    else:
        end_date = date.today() if not args.end_date else date.fromisoformat(args.end_date)
        start_date = end_date - timedelta(days=180)
    
    if args.end_date:
        end_date = date.fromisoformat(args.end_date)
    else:
        end_date = date.today()
    
    # Validate horizon
    if args.horizon <= 0:
        print("Error: Horizon must be a positive integer.")
        return 1
    
    print("Running factor analysis")
    print(f"Date Range: {start_date} to {end_date}")
    print(f"Forward Horizon: {args.horizon}d")
    print(f"Factors: {', '.join(factor_names)}")
    print("-" * 80)
    
    results = analyzer.run(factor_names, start_date, end_date, horizon_days=args.horizon)
    
    for result in results:
        print(f"\nFactor: {result.factor_name}")
        print(f"  Sample Size: {result.sample_size}")
        print(f"  Pearson Correlation: {result.pearson_correlation:.4f}" if result.pearson_correlation else "  Pearson Correlation: N/A")
        print(f"  Spearman IC: {result.spearman_ic:.4f}" if result.spearman_ic else "  Spearman IC: N/A")
        print(f"  Average Return: {result.average_return:.4f}" if result.average_return else "  Average Return: N/A")
        print(f"  Median Return: {result.median_return:.4f}" if result.median_return else "  Median Return: N/A")
        print(f"  Top Bucket Return: {result.top_bucket_return:.4f}" if result.top_bucket_return else "  Top Bucket Return: N/A")
        print(f"  Bottom Bucket Return: {result.bottom_bucket_return:.4f}" if result.bottom_bucket_return else "  Bottom Bucket Return: N/A")
    
    print("\n" + "-" * 80)
    print(f"Analysis complete. {len(results)} factor(s) analyzed.")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
