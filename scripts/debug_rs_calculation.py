#!/usr/bin/env python3
"""Debug RS calculation to identify why values are too large."""

from __future__ import annotations

from datetime import date
import pandas as pd
from sqlalchemy import select, text
from db.session import build_session_factory

def main():
    session_factory = build_session_factory()
    
    with session_factory() as session:
        # Get sample index data using raw SQL
        result = session.execute(text("""
            SELECT date, close 
            FROM index_prices_daily 
            WHERE index_name = 'NIFTY500' 
            ORDER BY date DESC 
            LIMIT 25
        """)).all()
        
        print("Index data (last 25 rows):")
        index_closes = []
        for row in result:
            if row[1] is not None:
                index_closes.append(float(row[1]))
                print(f"  {row[0]}: close={row[1]}")
            else:
                print(f"  {row[0]}: close=NULL")
        
        # Get sample stock data for TRENT using raw SQL
        result = session.execute(text("""
            SELECT date, close 
            FROM prices_daily 
            WHERE symbol = 'TRENT' 
            ORDER BY date DESC 
            LIMIT 25
        """)).all()
        
        print("\nStock data for TRENT (last 25 rows):")
        stock_closes = []
        for row in result:
            stock_closes.append(float(row[1]))
            print(f"  {row[0]}: close={row[1]}")
        
        # Calculate returns manually
        index_closes = list(reversed(index_closes))
        stock_closes = list(reversed(stock_closes))
        
        print("\nManual calculation:")
        if len(index_closes) > 20:
            index_return_20d = (index_closes[-1] - index_closes[-21]) / index_closes[-21]
            print(f"Index 20d return: {index_return_20d}")
        
        if len(stock_closes) > 20:
            stock_return_20d = (stock_closes[-1] - stock_closes[-21]) / stock_closes[-21]
            print(f"Stock 20d return: {stock_return_20d}")
            
            if len(index_closes) > 20:
                rs = stock_return_20d / index_return_20d
                print(f"RS (stock/index): {rs}")
    
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
