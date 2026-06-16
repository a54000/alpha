from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine, text


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_orchestrator():
    name = "run_full_daily_pipeline"
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_build_steps_has_required_order():
    orchestrator = load_orchestrator()
    args = orchestrator.parse_args(["--business-date", "2026-06-12", "--portfolio-id", "1"])

    steps = orchestrator.build_steps(args)

    assert [step.name for step in steps] == orchestrator.STEP_ORDER


def test_from_step_selects_suffix():
    orchestrator = load_orchestrator()
    args = orchestrator.parse_args(["--business-date", "2026-06-12", "--portfolio-id", "1"])
    steps = orchestrator.build_steps(args)

    selected = orchestrator.selected_steps(steps, "swing_v2_1_scoring")

    assert [step.name for step in selected] == [
        "swing_v2_1_scoring",
        "recommendation_generation",
        "decision_journal_capture",
        "paper_portfolio_update",
        "monitoring_report_generation",
    ]


def test_dry_run_does_not_execute_subprocess(monkeypatch):
    orchestrator = load_orchestrator()
    called = False

    def fake_run(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("subprocess.run should not be called in dry-run")

    monkeypatch.setattr(orchestrator.subprocess, "run", fake_run)
    step = orchestrator.PipelineStep("angel_data_sync", ["python", "nope.py"])

    result = orchestrator.run_step(step, dry_run=True)

    assert result.status == "dry_run"
    assert result.returncode == 0
    assert called is False


def test_pipeline_run_tracking_is_idempotent_for_step():
    orchestrator = load_orchestrator()
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    business_date = date(2026, 6, 12)
    orchestrator.ensure_pipeline_runs_table(engine)

    first = orchestrator.PipelineStep(
        "angel_data_sync",
        ["python", "x.py"],
        status="failed",
        started_at="2026-06-12T09:00:00+00:00",
        completed_at="2026-06-12T09:01:00+00:00",
        error_message="boom",
    )
    second = orchestrator.PipelineStep(
        "angel_data_sync",
        ["python", "x.py"],
        status="success",
        started_at="2026-06-12T09:02:00+00:00",
        completed_at="2026-06-12T09:03:00+00:00",
    )

    orchestrator.record_step(engine, business_date, first)
    orchestrator.record_step(engine, business_date, second)

    with engine.connect() as connection:
        rows = connection.execute(text("SELECT step_name, status, error_message FROM pipeline_runs")).mappings().all()

    assert len(rows) == 1
    assert rows[0]["step_name"] == "angel_data_sync"
    assert rows[0]["status"] == "success"
    assert rows[0]["error_message"] is None


def test_resume_detects_successful_previous_step():
    orchestrator = load_orchestrator()
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    business_date = date(2026, 6, 12)
    orchestrator.ensure_pipeline_runs_table(engine)
    step = orchestrator.PipelineStep(
        "feature_generation",
        ["python", "x.py"],
        status="success",
        started_at="2026-06-12T09:00:00+00:00",
        completed_at="2026-06-12T09:01:00+00:00",
    )
    orchestrator.record_step(engine, business_date, step)

    assert orchestrator.previous_status(engine, business_date, "feature_generation") == "success"
