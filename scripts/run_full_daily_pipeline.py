#!/usr/bin/env python3
"""Controlled full daily workflow orchestrator for frozen Swing V2.1.

Runs:
  1. Angel data sync
  2. Market data validation
  3. Daily bar refresh
  4. Feature generation
  5. Swing V2.1 scoring
  6. Recommendation generation
  7. Paper portfolio update
  8. Monitoring report generation

The orchestrator tracks each step in `pipeline_runs` and stops downstream
steps on failure. It does not change strategy, scoring, or broker behavior.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import Column, Date, DateTime, Integer, MetaData, String, Table, Text, UniqueConstraint, create_engine, inspect, text
from sqlalchemy.engine import Engine

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


STEP_ORDER = [
    "angel_data_sync",
    "index_data_refresh",
    "market_data_validation",
    "daily_bar_refresh",
    "feature_generation",
    "swing_v2_1_scoring",
    "recommendation_generation",
    "decision_journal_capture",
    "paper_portfolio_update",
    "monitoring_report_generation",
]


@dataclass
class PipelineStep:
    name: str
    command: list[str]
    status: str = "pending"
    started_at: str | None = None
    completed_at: str | None = None
    returncode: int | None = None
    error_message: str | None = None
    stdout_tail: str | None = None
    stderr_tail: str | None = None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the full daily paper trading pipeline.")
    parser.add_argument("--business-date", default=date.today().isoformat())
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--pilot-schema", default="pilot_phase2a")
    parser.add_argument("--portfolio-id", type=int, default=int(os.environ.get("PAPER_PORTFOLIO_ID", "0") or 0))
    parser.add_argument("--portfolio-size", type=int, default=10)
    parser.add_argument("--max-candidate-rank", type=int, default=5)
    parser.add_argument("--paper-strategy-mode", default=os.environ.get("PAPER_STRATEGY_MODE", "sector_rotation_adx_r10_vwap25"))
    parser.add_argument("--benchmark-index", default=os.environ.get("BENCHMARK_INDEX", "NIFTY500"))
    parser.add_argument(
        "--universe-csv",
        default=os.environ.get("PILOT_UNIVERSE_CSV", "reports/nifty500_expansion_universe_symbols.csv"),
        help=(
            "Optional pilot universe CSV. Passed to Phase 2A as --universe-csv "
            "and Phase 2B as --nifty500-csv so daily runs keep the expanded universe."
        ),
    )
    parser.add_argument("--index-start-date", help="Optional inclusive start date for benchmark refresh. Defaults to business date minus 10 calendar days.")
    parser.add_argument("--scoring-start-date", default="2022-05-25")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--from-step", choices=STEP_ORDER)
    parser.add_argument("--sync-dry-run", action="store_true")
    parser.add_argument("--rebalance-paper", action="store_true")
    parser.add_argument("--output-json")
    return parser.parse_args(argv)


def tail(value: str, limit: int = 4000) -> str:
    return value[-limit:] if len(value) > limit else value


def build_steps(args: argparse.Namespace) -> list[PipelineStep]:
    py = args.python
    report_date = args.business_date
    business_date = date.fromisoformat(args.business_date)
    index_start_date = args.index_start_date or (business_date - timedelta(days=10)).isoformat()
    sync_cmd = [py, "scripts/sync_angel_daily_data.py"]
    if args.sync_dry_run:
        sync_cmd.append("--dry-run")
    universe_csv = str(args.universe_csv or "").strip()

    paper_cmd = [
        py,
        "-m",
        "app.paper_trading.daily_update",
        "--cycle-date",
        report_date,
        "--portfolio-id",
        str(args.portfolio_id),
        "--portfolio-size",
        str(args.portfolio_size),
        "--max-candidate-rank",
        str(args.max_candidate_rank),
        "--strategy-mode",
        args.paper_strategy_mode,
    ]
    if args.rebalance_paper:
        paper_cmd.append("--rebalance")

    candidate_recommendation_steps = [
        PipelineStep(
            "candidate_recommendation_generation",
            [
                py,
                "scripts/generate_sector_1m3m_pilot_recommendations.py",
                "--pilot-schema",
                args.pilot_schema,
                "--universe-csv",
                universe_csv,
                "--start-date",
                args.scoring_start_date,
                "--end-date",
                args.business_date,
                "--output-json",
                "reports/rolling10_1m3m_candidate_recommendations.json",
            ],
        )
    ]

    market_data_validation_cmd = [
        py,
        "scripts/run_phase2a_pilot_infrastructure.py",
        "--pilot-schema",
        args.pilot_schema,
        "--output-json",
        "reports/phase4b_market_data_validation.json",
        "--coverage-csv",
        "reports/phase4b_daily_bar_coverage.csv",
        "--issues-csv",
        "reports/phase4b_daily_bar_issues.csv",
    ]
    feature_generation_cmd = [
        py,
        "scripts/run_phase2b_pilot_feature_generation.py",
        "--pilot-schema",
        args.pilot_schema,
        "--output-json",
        "reports/phase4b_feature_validation.json",
        "--coverage-csv",
        "reports/phase4b_feature_coverage_by_symbol.csv",
        "--nulls-csv",
        "reports/phase4b_feature_null_rates.csv",
    ]
    if universe_csv:
        market_data_validation_cmd.extend(["--universe-csv", universe_csv])
        feature_generation_cmd.extend(["--nifty500-csv", universe_csv])
        scoring_universe_args = ["--universe-csv", universe_csv]
        recommendation_universe_args = ["--universe-csv", universe_csv]
    else:
        scoring_universe_args = []
        recommendation_universe_args = []

    return [
        PipelineStep("angel_data_sync", sync_cmd),
        PipelineStep(
            "index_data_refresh",
            [
                py,
                "scripts/backfill_index_data.py",
                "--index-name",
                args.benchmark_index,
                "--start-date",
                index_start_date,
                "--end-date",
                args.business_date,
            ],
        ),
        PipelineStep(
            "market_data_validation",
            market_data_validation_cmd,
        ),
        PipelineStep(
            "daily_bar_refresh",
            [
                py,
                "scripts/run_phase2a1_daily_bar_cleaning.py",
                "--pilot-schema",
                args.pilot_schema,
                "--output-json",
                "reports/phase4b_daily_bar_cleaning.json",
                "--repairs-csv",
                "reports/phase4b_daily_bar_repairs.csv",
                "--rejected-csv",
                "reports/phase4b_daily_bar_rejected_rows.csv",
            ],
        ),
        PipelineStep(
            "feature_generation",
            feature_generation_cmd,
        ),
        PipelineStep(
            "swing_v2_1_scoring",
            [
                py,
                "scripts/run_phase2c_pilot_scoring.py",
                "--pilot-schema",
                args.pilot_schema,
                "--start-date",
                args.scoring_start_date,
                *scoring_universe_args,
                "--output-json",
                "reports/phase4b_scoring_validation.json",
                "--coverage-csv",
                "reports/phase4b_scoring_coverage_by_date.csv",
                "--monthly-csv",
                "reports/phase4b_scoring_coverage_by_month.csv",
                "--distribution-csv",
                "reports/phase4b_score_distribution_by_date.csv",
                "--symbol-csv",
                "reports/phase4b_scoring_coverage_by_symbol.csv",
            ],
        ),
        PipelineStep(
            "recommendation_generation",
            [
                py,
                "scripts/run_phase2d_pilot_recommendations.py",
                "--pilot-schema",
                args.pilot_schema,
                *recommendation_universe_args,
                "--output-json",
                "reports/phase4b_recommendation_validation.json",
                "--coverage-csv",
                "reports/phase4b_recommendation_coverage_by_date.csv",
                "--symbol-csv",
                "reports/phase4b_recommendations_by_symbol.csv",
                "--distribution-csv",
                "reports/phase4b_recommendation_score_distribution.csv",
            ],
        ),
        *candidate_recommendation_steps,
        PipelineStep(
            "decision_journal_capture",
            [
                py,
                "scripts/capture_recommendation_decision_journal.py",
                "--business-date",
                report_date,
                "--recommendation-type",
                "swing_v2_1",
                "--pilot-schema",
                args.pilot_schema,
                "--output-json",
                "reports/phase5_1_decision_journal_capture.json",
            ],
        ),
        PipelineStep("paper_portfolio_update", paper_cmd),
        PipelineStep(
            "monitoring_report_generation",
            [
                py,
                "scripts/generate_daily_paper_report.py",
                "--report-date",
                report_date,
                "--portfolio-id",
                str(args.portfolio_id),
                "--output-md",
                f"reports/daily_paper_report_{report_date}.md",
            ],
        ),
    ]


def selected_steps(steps: list[PipelineStep], from_step: str | None) -> list[PipelineStep]:
    if not from_step:
        return steps
    index = next(i for i, step in enumerate(steps) if step.name == from_step)
    return steps[index:]


def make_engine(database_url: str | None) -> Engine | None:
    if not database_url:
        return None
    return create_engine(database_url, future=True)


def ensure_pipeline_runs_table(engine: Engine | None) -> None:
    if engine is None:
        return
    metadata = MetaData()
    Table(
        "pipeline_runs",
        metadata,
        Column("run_id", Integer, primary_key=True, autoincrement=True),
        Column("business_date", Date),
        Column("step_name", String(80)),
        Column("status", String(20), nullable=False),
        Column("started_at", DateTime),
        Column("completed_at", DateTime),
        Column("error_message", Text),
        Column("job_name", String(50)),
        Column("run_date", Date),
        Column("start_time", DateTime),
        Column("end_time", DateTime),
        Column("rows_processed", Integer),
        UniqueConstraint("business_date", "step_name", name="uq_pipeline_runs_business_date_step_name"),
    )
    metadata.create_all(engine, checkfirst=True)
    with engine.begin() as connection:
        inspector = inspect(connection)
        columns = {column["name"] for column in inspector.get_columns("pipeline_runs")}
        for column_name, ddl in {
            "business_date": "ALTER TABLE pipeline_runs ADD COLUMN business_date date",
            "step_name": "ALTER TABLE pipeline_runs ADD COLUMN step_name varchar(80)",
            "started_at": "ALTER TABLE pipeline_runs ADD COLUMN started_at timestamp",
            "completed_at": "ALTER TABLE pipeline_runs ADD COLUMN completed_at timestamp",
        }.items():
            if column_name not in columns:
                connection.execute(text(ddl))
        if connection.dialect.name == "postgresql":
            connection.execute(
                text(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS uq_pipeline_runs_business_date_step_name
                    ON pipeline_runs (business_date, step_name)
                    """
                )
            )
        elif connection.dialect.name == "sqlite":
            connection.execute(
                text(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS uq_pipeline_runs_business_date_step_name
                    ON pipeline_runs (business_date, step_name)
                    """
                )
            )


def previous_status(engine: Engine | None, business_date: date, step_name: str) -> str | None:
    if engine is None:
        return None
    try:
        with engine.connect() as connection:
            return connection.execute(
                text(
                    """
                    SELECT status
                    FROM pipeline_runs
                    WHERE business_date = :business_date AND step_name = :step_name
                    ORDER BY run_id DESC
                    LIMIT 1
                    """
                ),
                {"business_date": business_date, "step_name": step_name},
            ).scalar_one_or_none()
    except Exception:
        return None


def record_step(engine: Engine | None, business_date: date, step: PipelineStep) -> None:
    if engine is None:
        return
    started = datetime.fromisoformat(step.started_at) if step.started_at else None
    completed = datetime.fromisoformat(step.completed_at) if step.completed_at else None
    params = {
        "business_date": business_date,
        "step_name": step.name,
        "status": step.status,
        "started_at": started,
        "completed_at": completed,
        "error_message": step.error_message,
        "job_name": step.name[:50],
        "run_date": business_date,
        "start_time": started,
        "end_time": completed,
    }
    with engine.begin() as connection:
        dialect = connection.dialect.name
        if dialect == "postgresql":
            connection.execute(
                text(
                    """
                    INSERT INTO pipeline_runs (
                        business_date, step_name, status, started_at, completed_at, error_message,
                        job_name, run_date, start_time, end_time
                    )
                    VALUES (
                        :business_date, :step_name, :status, :started_at, :completed_at, :error_message,
                        :job_name, :run_date, :start_time, :end_time
                    )
                    ON CONFLICT (business_date, step_name) DO UPDATE SET
                        status = EXCLUDED.status,
                        started_at = EXCLUDED.started_at,
                        completed_at = EXCLUDED.completed_at,
                        error_message = EXCLUDED.error_message,
                        job_name = EXCLUDED.job_name,
                        run_date = EXCLUDED.run_date,
                        start_time = EXCLUDED.start_time,
                        end_time = EXCLUDED.end_time
                    """
                ),
                params,
            )
        else:
            existing = connection.execute(
                text(
                    """
                    SELECT run_id FROM pipeline_runs
                    WHERE business_date = :business_date AND step_name = :step_name
                    LIMIT 1
                    """
                ),
                params,
            ).scalar_one_or_none()
            if existing is None:
                connection.execute(
                    text(
                        """
                        INSERT INTO pipeline_runs (
                            business_date, step_name, status, started_at, completed_at, error_message,
                            job_name, run_date, start_time, end_time
                        )
                        VALUES (
                            :business_date, :step_name, :status, :started_at, :completed_at, :error_message,
                            :job_name, :run_date, :start_time, :end_time
                        )
                        """
                    ),
                    params,
                )
            else:
                connection.execute(
                    text(
                        """
                        UPDATE pipeline_runs
                           SET status = :status,
                               started_at = :started_at,
                               completed_at = :completed_at,
                               error_message = :error_message,
                               job_name = :job_name,
                               run_date = :run_date,
                               start_time = :start_time,
                               end_time = :end_time
                         WHERE run_id = :run_id
                        """
                    ),
                    {**params, "run_id": existing},
                )


def run_step(step: PipelineStep, dry_run: bool) -> PipelineStep:
    step.started_at = datetime.now(timezone.utc).isoformat()
    if dry_run:
        step.status = "dry_run"
        step.returncode = 0
        step.completed_at = datetime.now(timezone.utc).isoformat()
        return step
    completed = subprocess.run(step.command, cwd=REPO_ROOT, text=True, capture_output=True)
    step.returncode = completed.returncode
    step.stdout_tail = tail(completed.stdout)
    step.stderr_tail = tail(completed.stderr)
    step.status = "success" if completed.returncode == 0 else "failed"
    step.error_message = tail(completed.stderr or completed.stdout, 1000) if completed.returncode else None
    step.completed_at = datetime.now(timezone.utc).isoformat()
    return step


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    args = parse_args()
    business_date = date.fromisoformat(args.business_date)
    output_path = Path(args.output_json) if args.output_json else REPO_ROOT / "reports" / f"phase4b_full_daily_pipeline_{business_date.isoformat()}.json"
    engine = make_engine(args.database_url)
    if not args.dry_run:
        ensure_pipeline_runs_table(engine)

    planned = selected_steps(build_steps(args), args.from_step)
    completed: list[PipelineStep] = []
    skipped: list[PipelineStep] = []

    for step in planned:
        if args.resume and previous_status(engine, business_date, step.name) == "success":
            step.status = "skipped_success"
            skipped.append(step)
            continue
        result = run_step(step, args.dry_run)
        completed.append(result)
        if not args.dry_run:
            record_step(engine, business_date, result)
        if result.status == "failed":
            break

    failed = [step for step in completed if step.status == "failed"]
    report = {
        "generated_on": datetime.now(timezone.utc).isoformat(),
        "mode": "phase4b_full_daily_pipeline",
        "business_date": business_date.isoformat(),
        "dry_run": args.dry_run,
        "resume": args.resume,
        "from_step": args.from_step,
        "configuration": {
            "pilot_schema": args.pilot_schema,
            "universe_csv": args.universe_csv or None,
            "benchmark_index": args.benchmark_index,
            "paper_strategy_mode": args.paper_strategy_mode,
            "portfolio_size": args.portfolio_size,
            "max_candidate_rank": args.max_candidate_rank,
        },
        "constraints": {
            "strategy_changed": False,
            "scoring_changed": False,
            "broker_order_apis_connected": False,
            "orders_placed": False,
        },
        "summary": {
            "steps_planned": len(planned),
            "steps_completed": len(completed),
            "steps_skipped": len(skipped),
            "failed_steps": len(failed),
            "status": "failed" if failed else "success",
        },
        "steps": [asdict(step) for step in skipped + completed],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print(f"Wrote full daily pipeline summary: {output_path}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
