#!/usr/bin/env python3
"""Run prepared Nifty 500 Angel backfill batches safely.

By default this runs sync_angel_daily_data.py in dry-run mode. Pass --execute
to perform live Angel API calls.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Nifty 500 backfill batches.")
    parser.add_argument("--batch-dir", default="reports/nifty500_backfill_batches")
    parser.add_argument("--from-date", default="2021-06-14")
    parser.add_argument("--to-date", required=True)
    parser.add_argument("--start-batch", type=int, default=1)
    parser.add_argument("--end-batch", type=int)
    parser.add_argument("--execute", action="store_true", help="Perform live Angel API sync. Default is dry-run.")
    parser.add_argument("--sleep-between-batches", type=float, default=120.0)
    parser.add_argument("--sleep-seconds", type=float, default=1.5)
    parser.add_argument("--rate-limit-sleep-seconds", type=float, default=180.0)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--summary-json", default="reports/nifty500_backfill_batches_summary.json")
    return parser.parse_args()


def batch_number(path: Path) -> int:
    return int(path.stem.split("_")[-1])


def main() -> int:
    args = parse_args()
    batch_dir = REPO_ROOT / args.batch_dir
    batch_files = sorted(batch_dir.glob("batch_*.txt"), key=batch_number)
    selected = [
        path
        for path in batch_files
        if batch_number(path) >= args.start_batch and (args.end_batch is None or batch_number(path) <= args.end_batch)
    ]
    results: list[dict[str, object]] = []
    for index, batch_file in enumerate(selected, start=1):
        number = batch_number(batch_file)
        symbols = batch_file.read_text(encoding="utf-8").strip()
        if not symbols:
            continue
        output_json = REPO_ROOT / "reports" / f"nifty500_backfill_batch_{number:03d}.json"
        cmd = [
            args.python,
            "scripts/sync_angel_daily_data.py",
            "--symbols",
            symbols,
            "--from-date",
            args.from_date,
            "--to-date",
            args.to_date,
            "--output-json",
            str(output_json),
            "--sleep-seconds",
            str(args.sleep_seconds),
            "--rate-limit-sleep-seconds",
            str(args.rate_limit_sleep_seconds),
            "--retries",
            str(args.retries),
            "--log-level",
            "INFO",
        ]
        if not args.execute:
            cmd.append("--dry-run")
        started = datetime.now(timezone.utc).isoformat()
        completed = None
        status = "unknown"
        returncode = None
        print(f"Running batch {number} ({'live' if args.execute else 'dry-run'})")
        try:
            completed_process = subprocess.run(cmd, cwd=REPO_ROOT, check=False)
            returncode = completed_process.returncode
            status = "success" if returncode == 0 else "failed"
        finally:
            completed = datetime.now(timezone.utc).isoformat()
        results.append(
            {
                "batch": number,
                "symbols": len([symbol for symbol in symbols.split(",") if symbol]),
                "mode": "live" if args.execute else "dry_run",
                "status": status,
                "returncode": returncode,
                "started_at": started,
                "completed_at": completed,
                "output_json": str(output_json),
            }
        )
        if status != "success":
            break
        if args.execute and index < len(selected):
            time.sleep(args.sleep_between_batches)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "live" if args.execute else "dry_run",
        "from_date": args.from_date,
        "to_date": args.to_date,
        "batches_requested": len(selected),
        "batches_completed": sum(1 for row in results if row["status"] == "success"),
        "failed_batches": [row for row in results if row["status"] != "success"],
        "results": results,
    }
    output_path = REPO_ROOT / args.summary_json
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if not payload["failed_batches"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
