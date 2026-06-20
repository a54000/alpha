#!/usr/bin/env python3
"""Prepare targeted Nifty 500 expansion inputs from the universe audit.

Reads reports/nifty500_backfill_status.csv plus reports/nifty500_universe_gap.csv and writes:
  - reports/nifty500_expansion_universe_symbols.csv
  - reports/nifty500_needs_angel_backfill_symbols.csv
  - reports/nifty500_backfill_batches/batch_XXX.csv
  - reports/nifty500_backfill_batches/batch_XXX.txt

This script does not connect to databases or call Angel APIs.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare Nifty 500 expansion batch files.")
    parser.add_argument("--gap-csv", default="reports/nifty500_universe_gap.csv")
    parser.add_argument("--status-csv", default="reports/nifty500_backfill_status.csv")
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--out-dir", default="reports/nifty500_backfill_batches")
    parser.add_argument("--universe-csv", default="reports/nifty500_expansion_universe_symbols.csv")
    parser.add_argument("--backfill-csv", default="reports/nifty500_needs_angel_backfill_symbols.csv")
    parser.add_argument("--summary-json", default="reports/nifty500_expansion_batch_plan.json")
    return parser.parse_args()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    gap_rows = read_rows(REPO_ROOT / args.gap_csv)
    status_rows = read_rows(REPO_ROOT / args.status_csv)
    fieldnames = ["symbol", "angel_token", "exchange", "nifty_industry", "company_name", "reason"]
    expansion_rows = [
        {
            "symbol": row["symbol"],
            "angel_token": row.get("angel_token") or "",
            "exchange": "NSE",
            "nifty_industry": row.get("nifty_industry") or "",
            "company_name": row.get("company_name") or "",
            "reason": row.get("reason") or "",
        }
        for row in status_rows
        if row.get("reason") in {"usable", "needs_angel_backfill", "needs_daily_aggregation", "needs_feature_generation"}
    ]
    gap_by_symbol = {row["symbol"]: row for row in gap_rows}
    backfill_rows = [
        {
            "symbol": row["symbol"],
            "angel_token": gap_by_symbol.get(row["symbol"], {}).get("angel_token") or "",
            "exchange": "NSE",
            "nifty_industry": gap_by_symbol.get(row["symbol"], {}).get("nifty_industry") or "",
            "company_name": gap_by_symbol.get(row["symbol"], {}).get("company_name") or "",
            "reason": row.get("reason") or "",
        }
        for row in status_rows
        if row.get("reason") == "needs_angel_backfill"
    ]

    write_csv(REPO_ROOT / args.universe_csv, expansion_rows, fieldnames)
    write_csv(REPO_ROOT / args.backfill_csv, backfill_rows, fieldnames)

    out_dir = REPO_ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    batches: list[dict[str, object]] = []
    for batch_index, start in enumerate(range(0, len(backfill_rows), args.batch_size), start=1):
        batch = backfill_rows[start : start + args.batch_size]
        batch_csv = out_dir / f"batch_{batch_index:03d}.csv"
        batch_txt = out_dir / f"batch_{batch_index:03d}.txt"
        write_csv(batch_csv, batch, fieldnames)
        symbols = [row["symbol"] for row in batch]
        batch_txt.write_text(",".join(symbols), encoding="utf-8")
        batches.append(
            {
                "batch": batch_index,
                "symbols": len(symbols),
                "csv": str(batch_csv),
                "symbols_arg_file": str(batch_txt),
                "first_symbol": symbols[0] if symbols else None,
                "last_symbol": symbols[-1] if symbols else None,
            }
        )

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "gap_csv": str(REPO_ROOT / args.gap_csv),
        "status_csv": str(REPO_ROOT / args.status_csv),
        "expansion_universe_symbols": len(expansion_rows),
        "backfill_symbols": len(backfill_rows),
        "batch_size": args.batch_size,
        "batches": batches,
    }
    summary_path = REPO_ROOT / args.summary_json
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
