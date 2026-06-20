#!/usr/bin/env python3
"""Validate NIFTY500 index data loaded into index_prices_daily."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import select, func
from db.session import build_session_factory
from db.models import IndexPricesDaily

def main():
    session_factory = build_session_factory()
    
    with session_factory() as session:
        # Row count
        row_count = session.execute(
            select(func.count()).select_from(IndexPricesDaily).where(IndexPricesDaily.index_name == "NIFTY500")
        ).scalar()
        
        # Min date
        min_date = session.execute(
            select(func.min(IndexPricesDaily.date)).where(IndexPricesDaily.index_name == "NIFTY500")
        ).scalar()
        
        # Max date
        max_date = session.execute(
            select(func.max(IndexPricesDaily.date)).where(IndexPricesDaily.index_name == "NIFTY500")
        ).scalar()
        
        # Check for missing dates
        all_dates = session.execute(
            select(IndexPricesDaily.date)
            .where(IndexPricesDaily.index_name == "NIFTY500")
            .order_by(IndexPricesDaily.date)
        ).scalars().all()
        
        # Check for null close prices
        null_close_count = session.execute(
            select(func.count())
            .select_from(IndexPricesDaily)
            .where(IndexPricesDaily.index_name == "NIFTY500", IndexPricesDaily.close.is_(None))
        ).scalar()
        
    
    print(f"Row count: {row_count}")
    print(f"Min date: {min_date}")
    print(f"Max date: {max_date}")
    print(f"Null close prices: {null_close_count}")
    
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
