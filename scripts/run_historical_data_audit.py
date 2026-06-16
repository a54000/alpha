#!/usr/bin/env python3
"""Run the read-only historical data expansion audit."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app.research.historical_data_audit import run_historical_data_audit
from db.session import build_session_factory


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit historical data coverage before extending Swing V2.1.")
    parser.add_argument("--source-database-url", default=os.environ.get("ANGEL_DATABASE_URL"))
    parser.add_argument("--source-table", default=os.environ.get("ANGEL_OHLCV_15MIN_TABLE", "ohlcv_15min"))
    parser.add_argument("--min-years", type=int, default=5)
    parser.add_argument("--discontinuity-threshold-pct", type=float, default=40.0)
    parser.add_argument("--output", default="reports/historical_data_expansion_audit.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    session_factory = build_session_factory()
    audit = run_historical_data_audit(
        session_factory,
        source_database_url=args.source_database_url,
        source_table=args.source_table,
        min_years=args.min_years,
        discontinuity_threshold_pct=args.discontinuity_threshold_pct,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = audit.to_dict()
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(json.dumps(payload, indent=2))
    print(f"\nWrote audit report: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
