#!/usr/bin/env python3
"""Run the Phase 3F daily paper trading operations sequence.

Execution order:
  1. Sync Angel candles
  2. Validate latest data
  3. Update daily bars
  4. Refresh features
  5. Compute Swing V2.1 scores
  6. Generate recommendations
  7. Update paper portfolio

This script orchestrates existing pilot/research components. It does not
change scoring, recommendation, or portfolio strategy rules.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


@dataclass
class CycleStep:
    name: str
    command: list[str]
    status: str = "pending"
    returncode: int | None = None
    started_at: str | None = None
    ended_at: str | None = None
    stdout_tail: str | None = None
    stderr_tail: str | None = None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the daily Angel-to-paper-trading cycle.")
    parser.add_argument("--cycle-date", default=date.today().isoformat())
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--dry-run", action="store_true", help="Print/report commands without executing them.")
    parser.add_argument("--sync-dry-run", action="store_true", help="Run Angel sync in dry-run mode.")
    parser.add_argument("--skip-sync", action="store_true")
    parser.add_argument("--skip-paper-update", action="store_true")
    parser.add_argument("--pilot-schema", default="pilot_phase2a")
    parser.add_argument("--scoring-start-date", default="2022-05-25")
    parser.add_argument("--portfolio-id", type=int, default=int(os.environ.get("PAPER_PORTFOLIO_ID", "0") or 0))
    parser.add_argument("--portfolio-size", type=int, default=10)
    parser.add_argument("--max-candidate-rank", type=int, default=5)
    parser.add_argument("--paper-strategy-mode", default=os.environ.get("PAPER_STRATEGY_MODE", "sector_rotation_adx_r10_vwap25"))
    parser.add_argument("--output-json", default="reports/phase3f_daily_cycle.json")
    return parser.parse_args(argv)


def tail(value: str, limit: int = 4000) -> str:
    return value[-limit:] if len(value) > limit else value


def build_steps(args: argparse.Namespace) -> list[CycleStep]:
    py = args.python
    steps: list[CycleStep] = []
    if not args.skip_sync:
        sync_cmd = [py, "scripts/sync_angel_daily_data.py"]
        if args.sync_dry_run:
            sync_cmd.append("--dry-run")
        steps.append(CycleStep("sync_angel_candles", sync_cmd))

    steps.extend(
        [
            CycleStep(
                "validate_latest_angel_data",
                [
                    py,
                    "scripts/run_phase2a_pilot_infrastructure.py",
                    "--pilot-schema",
                    args.pilot_schema,
                    "--output-json",
                    "reports/phase3f_latest_data_validation.json",
                    "--coverage-csv",
                    "reports/phase3f_daily_bar_coverage.csv",
                    "--issues-csv",
                    "reports/phase3f_daily_bar_issues.csv",
                ],
            ),
            CycleStep(
                "update_clean_daily_bars",
                [
                    py,
                    "scripts/run_phase2a1_daily_bar_cleaning.py",
                    "--pilot-schema",
                    args.pilot_schema,
                    "--output-json",
                    "reports/phase3f_daily_bar_cleaning.json",
                    "--repairs-csv",
                    "reports/phase3f_daily_bar_repairs.csv",
                    "--rejected-csv",
                    "reports/phase3f_daily_bar_rejected_rows.csv",
                ],
            ),
            CycleStep(
                "refresh_features",
                [
                    py,
                    "scripts/run_phase2b_pilot_feature_generation.py",
                    "--pilot-schema",
                    args.pilot_schema,
                    "--output-json",
                    "reports/phase3f_feature_validation.json",
                    "--coverage-csv",
                    "reports/phase3f_feature_coverage_by_symbol.csv",
                    "--nulls-csv",
                    "reports/phase3f_feature_null_rates.csv",
                ],
            ),
            CycleStep(
                "compute_scores",
                [
                    py,
                    "scripts/run_phase2c_pilot_scoring.py",
                    "--pilot-schema",
                    args.pilot_schema,
                    "--start-date",
                    args.scoring_start_date,
                    "--output-json",
                    "reports/phase3f_scoring_validation.json",
                    "--coverage-csv",
                    "reports/phase3f_scoring_coverage_by_date.csv",
                    "--monthly-csv",
                    "reports/phase3f_scoring_coverage_by_month.csv",
                    "--distribution-csv",
                    "reports/phase3f_score_distribution_by_date.csv",
                    "--symbol-csv",
                    "reports/phase3f_scoring_coverage_by_symbol.csv",
                ],
            ),
            CycleStep(
                "generate_recommendations",
                [
                    py,
                    "scripts/run_phase2d_pilot_recommendations.py",
                    "--pilot-schema",
                    args.pilot_schema,
                    "--output-json",
                    "reports/phase3f_recommendation_validation.json",
                    "--coverage-csv",
                    "reports/phase3f_recommendation_coverage_by_date.csv",
                    "--symbol-csv",
                    "reports/phase3f_recommendations_by_symbol.csv",
                    "--distribution-csv",
                    "reports/phase3f_recommendation_score_distribution.csv",
                ],
            ),
        ]
    )

    if args.paper_strategy_mode in {"sector_rotation_adx_r10_vwap25", "rolling10_1m3m_vwap25_paper"}:
        steps.append(
            CycleStep(
                "generate_candidate_recommendations",
                [
                    py,
                    "scripts/generate_sector_1m3m_pilot_recommendations.py",
                    "--pilot-schema",
                    args.pilot_schema,
                    "--start-date",
                    args.scoring_start_date,
                    "--end-date",
                    args.cycle_date,
                    "--output-json",
                    "reports/rolling10_1m3m_candidate_recommendations.json",
                ],
            )
        )

    if not args.skip_paper_update and args.portfolio_id:
        steps.append(
            CycleStep(
                "update_paper_portfolio",
                [
                    py,
                    "-m",
                    "app.paper_trading.daily_update",
                    "--cycle-date",
                    args.cycle_date,
                    "--portfolio-id",
                    str(args.portfolio_id),
                    "--portfolio-size",
                    str(args.portfolio_size),
                    "--max-candidate-rank",
                    str(args.max_candidate_rank),
                    "--strategy-mode",
                    args.paper_strategy_mode,
                ],
            )
        )
    return steps


def run_step(step: CycleStep, dry_run: bool) -> CycleStep:
    step.started_at = datetime.now(timezone.utc).isoformat()
    if dry_run:
        step.status = "dry_run"
        step.returncode = 0
        step.ended_at = datetime.now(timezone.utc).isoformat()
        return step

    completed = subprocess.run(step.command, cwd=REPO_ROOT, text=True, capture_output=True)
    step.returncode = completed.returncode
    step.status = "success" if completed.returncode == 0 else "failed"
    step.stdout_tail = tail(completed.stdout)
    step.stderr_tail = tail(completed.stderr)
    step.ended_at = datetime.now(timezone.utc).isoformat()
    return step


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    args = parse_args()
    steps = build_steps(args)
    completed_steps: list[CycleStep] = []

    for step in steps:
        completed = run_step(step, args.dry_run)
        completed_steps.append(completed)
        if completed.status == "failed":
            break

    report = {
        "generated_on": datetime.now(timezone.utc).isoformat(),
        "mode": "phase3f_daily_paper_cycle",
        "cycle_date": args.cycle_date,
        "dry_run": args.dry_run,
        "constraints": {
            "broker_order_apis_connected": False,
            "strategy_changed": False,
            "scoring_changed": False,
            "recommendations_changed": False,
        },
        "summary": {
            "steps_planned": len(steps),
            "steps_completed": len(completed_steps),
            "failed_steps": sum(1 for step in completed_steps if step.status == "failed"),
            "status": "failed" if any(step.status == "failed" for step in completed_steps) else "success",
        },
        "steps": [asdict(step) for step in completed_steps],
    }
    output_path = REPO_ROOT / args.output_json
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print(f"Wrote daily cycle report: {output_path}")
    return 1 if report["summary"]["failed_steps"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
