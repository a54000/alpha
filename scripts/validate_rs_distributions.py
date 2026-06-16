#!/usr/bin/env python3
"""Validate RS feature distributions after recomputation."""

from __future__ import annotations

from sqlalchemy import select, func
from db.session import build_session_factory
from db.models import FeaturesDaily

def main():
    session_factory = build_session_factory()
    
    with session_factory() as session:
        # Get statistics for rs_vs_nifty_20d
        stats_20d = session.execute(
            select(
                func.count(FeaturesDaily.rs_vs_nifty_20d),
                func.min(FeaturesDaily.rs_vs_nifty_20d),
                func.max(FeaturesDaily.rs_vs_nifty_20d),
                func.avg(FeaturesDaily.rs_vs_nifty_20d),
                func.stddev(FeaturesDaily.rs_vs_nifty_20d)
            ).where(FeaturesDaily.rs_vs_nifty_20d.isnot(None))
        ).one()
        
        # Get statistics for rs_vs_nifty_60d
        stats_60d = session.execute(
            select(
                func.count(FeaturesDaily.rs_vs_nifty_60d),
                func.min(FeaturesDaily.rs_vs_nifty_60d),
                func.max(FeaturesDaily.rs_vs_nifty_60d),
                func.avg(FeaturesDaily.rs_vs_nifty_60d),
                func.stddev(FeaturesDaily.rs_vs_nifty_60d)
            ).where(FeaturesDaily.rs_vs_nifty_60d.isnot(None))
        ).one()
        
        # Get statistics for rs_rank_pct
        stats_rank = session.execute(
            select(
                func.count(FeaturesDaily.rs_rank_pct),
                func.min(FeaturesDaily.rs_rank_pct),
                func.max(FeaturesDaily.rs_rank_pct),
                func.avg(FeaturesDaily.rs_rank_pct)
            ).where(FeaturesDaily.rs_rank_pct.isnot(None))
        ).one()
        
        # Check for infinite values
        inf_20d = session.execute(
            select(func.count()).where(FeaturesDaily.rs_vs_nifty_20d == float('inf'))
        ).scalar()
        
        inf_60d = session.execute(
            select(func.count()).where(FeaturesDaily.rs_vs_nifty_60d == float('inf'))
        ).scalar()
        
        # Check for NaN values
        nan_20d = session.execute(
            select(func.count()).where(FeaturesDaily.rs_vs_nifty_20d.is_(None))
        ).scalar()
        
        nan_60d = session.execute(
            select(func.count()).where(FeaturesDaily.rs_vs_nifty_60d.is_(None))
        ).scalar()
        
        print("RS vs Nifty 20d Statistics:")
        print(f"  Count: {stats_20d[0]}")
        print(f"  Min: {stats_20d[1]}")
        print(f"  Max: {stats_20d[2]}")
        print(f"  Mean: {stats_20d[3]}")
        print(f"  StdDev: {stats_20d[4]}")
        print(f"  Infinite values: {inf_20d}")
        print(f"  NaN values: {nan_20d}")
        
        print("\nRS vs Nifty 60d Statistics:")
        print(f"  Count: {stats_60d[0]}")
        print(f"  Min: {stats_60d[1]}")
        print(f"  Max: {stats_60d[2]}")
        print(f"  Mean: {stats_60d[3]}")
        print(f"  StdDev: {stats_60d[4]}")
        print(f"  Infinite values: {inf_60d}")
        print(f"  NaN values: {nan_60d}")
        
        print("\nRS Rank Percentile Statistics:")
        print(f"  Count: {stats_rank[0]}")
        print(f"  Min: {stats_rank[1]}")
        print(f"  Max: {stats_rank[2]}")
        print(f"  Mean: {stats_rank[3]}")
        
        # Check if values are in expected range
        print("\nValidation:")
        if stats_20d[2] < 10000 and stats_20d[1] > -10000:
            print("  rs_vs_nifty_20d: PASS (values in expected range)")
        else:
            print("  rs_vs_nifty_20d: FAIL (values outside expected range)")
        
        if stats_60d[2] < 10000 and stats_60d[1] > -10000:
            print("  rs_vs_nifty_60d: PASS (values in expected range)")
        else:
            print("  rs_vs_nifty_60d: FAIL (values outside expected range)")
        
        if inf_20d == 0 and inf_60d == 0:
            print("  Infinite values: PASS (no infinite values)")
        else:
            print("  Infinite values: FAIL (found infinite values)")
        
        if stats_rank[2] <= 100 and stats_rank[1] >= 0:
            print("  rs_rank_pct: PASS (values in 0-100 range)")
        else:
            print("  rs_rank_pct: FAIL (values outside 0-100 range)")
    
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
