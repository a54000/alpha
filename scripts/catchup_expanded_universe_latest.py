#!/usr/bin/env python3
"""Catch up expanded Nifty 500 pilot symbols missing the latest clean bar.

Default mode is report-only. Use --execute to run targeted Angel sync and
downstream pilot rebuild steps.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


REPO_ROOT = Path(__file__).resolve().parents[1]
IST = ZoneInfo("Asia/Kolkata")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Catch up expanded pilot universe symbols missing latest clean bars.")
    parser.add_argument("--research-database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--angel-database-url", default=os.environ.get("ANGEL_DATABASE_URL"))
    parser.add_argument("--angel-database-name", default="angel_data")
    parser.add_argument("--pilot-schema", default="pilot_phase2a")
    parser.add_argument("--universe-status-csv", default="reports/nifty500_backfill_status.csv")
    parser.add_argument("--universe-csv", default="reports/nifty500_expansion_universe_symbols.csv")
    parser.add_argument("--target-date", help="Target clean-bar date. Defaults to max(date) in daily_bars_clean.")
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--sleep-seconds", type=float, default=1.0)
    parser.add_argument("--rate-limit-sleep-seconds", type=float, default=300.0)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--execute", action="store_true", help="Run sync and downstream rebuild steps.")
    parser.add_argument("--sync-dry-run", action="store_true", help="Pass --dry-run to targeted Angel sync.")
    parser.add_argument("--skip-sync", action="store_true", help="Only rerun aggregation/clean/features.")
    parser.add_argument("--skip-features", action="store_true", help="Skip Phase 2B feature generation.")
    parser.add_argument("--output-json", default="reports/nifty500_latest_bar_catchup.json")
    parser.add_argument("--gap-csv", default="reports/nifty500_latest_bar_gaps.csv")
    return parser.parse_args()


def derive_angel_url(research_database_url: str | None, database_name: str) -> str | None:
    if not research_database_url:
        return None
    parts = urlsplit(research_database_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database_name}", parts.query, parts.fragment))


def read_ready_symbols(path: Path) -> list[str]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    symbols = [
        str(row.get("symbol") or "").strip().upper()
        for row in rows
        if str(row.get("status") or "").strip().lower() == "ready"
    ]
    return sorted({symbol for symbol in symbols if symbol})


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def latest_target_date(engine, schema: str, override: str | None) -> date:
    if override:
        return date.fromisoformat(override)
    with engine.connect() as connection:
        latest = connection.execute(text(f"SELECT MAX(date) FROM {schema}.daily_bars_clean")).scalar_one()
    if latest is None:
        raise RuntimeError(f"No clean daily bars found in {schema}.daily_bars_clean.")
    return latest


def find_gaps(engine, schema: str, ready_symbols: list[str], target: date) -> list[dict[str, object]]:
    if not ready_symbols:
        return []
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                f"""
                WITH ready(symbol) AS (
                    SELECT unnest(:symbols)
                ),
                latest_clean AS (
                    SELECT symbol, MAX(date) AS latest_clean_date
                    FROM {schema}.daily_bars_clean
                    WHERE symbol = ANY(:symbols)
                    GROUP BY symbol
                ),
                latest_candle AS (
                    SELECT symbol, MAX(datetime) AS latest_candle_at
                    FROM ohlcv_15min
                    WHERE symbol = ANY(:symbols)
                    GROUP BY symbol
                )
                SELECT r.symbol,
                       c.latest_clean_date,
                       k.latest_candle_at
                FROM ready r
                LEFT JOIN latest_clean c ON c.symbol = r.symbol
                LEFT JOIN latest_candle k ON k.symbol = r.symbol
                WHERE c.latest_clean_date IS DISTINCT FROM :target
                ORDER BY c.latest_clean_date DESC NULLS FIRST, r.symbol
                """
            ),
            {"symbols": ready_symbols, "target": target},
        ).mappings().all()
    return [
        {
            "symbol": row["symbol"],
            "latest_clean_date": row["latest_clean_date"].isoformat() if row["latest_clean_date"] else "",
            "latest_candle_at": row["latest_candle_at"].isoformat() if row["latest_candle_at"] else "",
            "target_date": target.isoformat(),
        }
        for row in rows
    ]


def command_result(command: list[str], execute: bool) -> dict[str, object]:
    if not execute:
        return {"command": command, "status": "planned", "returncode": None}
    completed = subprocess.run(command, cwd=REPO_ROOT, text=True, capture_output=True)
    return {
        "command": command,
        "status": "success" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
    }


def batched(items: list[str], size: int) -> list[list[str]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def catchup_from_date(gaps: list[dict[str, object]], target: date) -> str:
    parsed = [
        date.fromisoformat(str(row["latest_clean_date"]))
        for row in gaps
        if row.get("latest_clean_date")
    ]
    start = (min(parsed) + timedelta(days=1)) if parsed else target
    return datetime.combine(start, time.min, tzinfo=IST).isoformat()


def target_to_datetime(target: date) -> str:
    return datetime.combine(target, time(hour=15, minute=30), tzinfo=IST).isoformat()


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    args = parse_args()
    research_url = args.research_database_url or os.environ.get("DATABASE_URL")
    angel_url = args.angel_database_url or os.environ.get("ANGEL_DATABASE_URL") or derive_angel_url(research_url, args.angel_database_name)
    if not angel_url:
        raise RuntimeError("ANGEL_DATABASE_URL or DATABASE_URL is required.")

    engine = create_engine(angel_url, future=True)
    ready_symbols = read_ready_symbols(REPO_ROOT / args.universe_status_csv)
    target = latest_target_date(engine, args.pilot_schema, args.target_date)
    gaps = find_gaps(engine, args.pilot_schema, ready_symbols, target)
    write_csv(
        REPO_ROOT / args.gap_csv,
        gaps,
        ["symbol", "latest_clean_date", "latest_candle_at", "target_date"],
    )

    commands: list[dict[str, object]] = []
    gap_symbols = [str(row["symbol"]) for row in gaps]
    if gap_symbols and not args.skip_sync:
        from_date = catchup_from_date(gaps, target)
        to_date = target_to_datetime(target)
        for batch in batched(gap_symbols, max(1, args.batch_size)):
            command = [
                sys.executable,
                "scripts/sync_angel_daily_data.py",
                "--symbols",
                ",".join(batch),
                "--from-date",
                from_date,
                "--to-date",
                to_date,
                "--sleep-seconds",
                str(args.sleep_seconds),
                "--rate-limit-sleep-seconds",
                str(args.rate_limit_sleep_seconds),
                "--retries",
                str(args.retries),
                "--output-json",
                "reports/nifty500_latest_bar_sync.json",
            ]
            if args.sync_dry_run:
                command.append("--dry-run")
            commands.append(command_result(command, args.execute))
            if commands[-1]["status"] == "failed":
                break

    if not any(item["status"] == "failed" for item in commands):
        rebuild_commands = [
            [
                sys.executable,
                "scripts/run_phase2a_pilot_infrastructure.py",
                "--pilot-schema",
                args.pilot_schema,
                "--universe-csv",
                args.universe_csv,
                "--output-json",
                "reports/nifty500_catchup_phase2a_data_quality.json",
                "--coverage-csv",
                "reports/nifty500_catchup_phase2a_coverage.csv",
                "--issues-csv",
                "reports/nifty500_catchup_phase2a_issues.csv",
            ],
            [
                sys.executable,
                "scripts/run_phase2a1_daily_bar_cleaning.py",
                "--pilot-schema",
                args.pilot_schema,
                "--output-json",
                "reports/nifty500_catchup_phase2a1_cleaning.json",
                "--rejected-csv",
                "reports/nifty500_catchup_phase2a1_rejected.csv",
                "--repairs-csv",
                "reports/nifty500_catchup_phase2a1_repairs.csv",
            ],
        ]
        if not args.skip_features:
            rebuild_commands.append(
                [
                    sys.executable,
                    "scripts/run_phase2b_pilot_feature_generation.py",
                    "--pilot-schema",
                    args.pilot_schema,
                    "--nifty500-csv",
                    args.universe_csv,
                    "--output-json",
                    "reports/nifty500_catchup_phase2b_features.json",
                ]
            )
        for command in rebuild_commands:
            commands.append(command_result(command, args.execute))
            if commands[-1]["status"] == "failed":
                break

    report = {
        "generated_at": datetime.now(tz=IST).isoformat(),
        "mode": "nifty500_latest_bar_catchup",
        "execute": args.execute,
        "sync_dry_run": args.sync_dry_run,
        "pilot_schema": args.pilot_schema,
        "target_date": target.isoformat(),
        "ready_symbols": len(ready_symbols),
        "symbols_missing_target_clean_bar": len(gaps),
        "gap_csv": str(REPO_ROOT / args.gap_csv),
        "commands": commands,
        "status": "failed" if any(item["status"] == "failed" for item in commands) else "success",
    }
    output_path = REPO_ROOT / args.output_json
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ["status", "target_date", "ready_symbols", "symbols_missing_target_clean_bar", "execute"]}, indent=2))
    print(f"Wrote catch-up report: {output_path}")
    return 1 if report["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
