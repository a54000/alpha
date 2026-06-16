from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine, inspect

from app.api.disha_db_service import DishaDatabaseService, create_tables_for_tests
from app.api.disha_service import DishaReadService


def write_artifacts(root: Path) -> DishaReadService:
    paper = root / "results" / "sprint_2_8"
    regime = root / "results" / "sprint_2_1"
    paper.mkdir(parents=True)
    regime.mkdir(parents=True)
    (paper / "day0_scanner_dry_run_signals.csv").write_text(
        "scan_date,symbol,v4b_entry_signal,vcp_entry_signal,market_regime,vcp_market_gate,close\n"
        "2026-06-13,LTIM,true,false,RANGING,false,4820.5\n"
        "2026-06-13,TRENT,false,true,UPTREND,true,6120.0\n",
        encoding="utf-8",
    )
    (paper / "day0_scanner_dry_run_summary.json").write_text(
        json.dumps({"scan_date": "2026-06-13", "symbols_scanned": 2}),
        encoding="utf-8",
    )
    (paper / "position_ledger.csv").write_text(
        "trade_id,sleeve,symbol,entry_date,entry_price,shares,planned_exit_date,stop_loss,status,exit_date,exit_price,pnl,notes\n"
        "T1,V4B,LTIM,2026-06-14,4820,10,2026-07-04,4650,OPEN,,,,paper\n",
        encoding="utf-8",
    )
    (paper / "paper_trade_log.csv").write_text(
        "session,date,scanner_run,v4b_entry_signals,v4b_exit_signals,vcp_entry_signals,vcp_exit_signals,idle_capital,mf_action,mf_invest_amount,mf_redeem_amount,mf_balance,mf_nav_source_confirmed,redemption_workflow_tested,bid_ask_spread_checked,caveat_notes\n"
        "1,2026-06-13,Y,1,0,1,0,,REVIEW_CASH_NEEDS,,,,Y,N,N,test\n",
        encoding="utf-8",
    )
    (paper / "mf_sweep_log.csv").write_text(
        "session,date,time,portfolio_equity,v4b_deployed_value,vcp_deployed_value,idle_capital,action,amount,nav,units,mf_balance,settlement_status,notes\n",
        encoding="utf-8",
    )
    (paper / "fill_quality_log.csv").write_text(
        "session,date,symbol,expected_fill,actual_fill,slippage_pct,notes\n",
        encoding="utf-8",
    )
    (paper / "scanner_reconciliation_log.csv").write_text(
        "session,date,symbol,scanner_signal,expected_signal,match,notes\n",
        encoding="utf-8",
    )
    (paper / "paper_trading_status.json").write_text(
        json.dumps(
            {
                "ready": True,
                "sessions_logged": 1,
                "scanner_reconciliations": 0,
                "mf_sweep_events": 0,
                "fill_checks": 0,
                "open_positions_logged": 1,
            }
        ),
        encoding="utf-8",
    )
    (paper / "LOCKED_RULES.yaml").write_text("portfolio:\n  name: Disha Mean Reversion Setup\n", encoding="utf-8")
    (root / "results" / "RESEARCH_PHASE_COMPLETE.md").write_text("# DISHA\n", encoding="utf-8")
    (regime / "daily_regime_labels.csv").write_text("session_date,regime_label\n2026-06-13,UPTREND\n", encoding="utf-8")
    return DishaReadService(root=root)


def test_create_disha_tables_for_tests():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_tables_for_tests(engine)

    tables = set(inspect(engine).get_table_names())
    assert "disha_signals" in tables
    assert "disha_positions" in tables
    assert "disha_portfolio_snapshots" in tables
    assert "disha_paper_events" in tables
    assert "disha_operator_audit" in tables
    assert "disha_paper_workflow_events" in tables


def test_sync_artifacts_imports_signals_positions_snapshots_and_events(tmp_path):
    artifact_service = write_artifacts(tmp_path / "mean_reversion_system")
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_tables_for_tests(engine)
    service = DishaDatabaseService(engine=engine, artifact_service=artifact_service)

    counts = service.sync_artifacts()

    assert counts == {"signals": 2, "positions": 1, "portfolio_snapshots": 1, "paper_events": 1}
    assert service.signals()["signals"][0]["symbol"] in {"LTIM", "TRENT"}
    assert service.positions()["positions"][0]["trade_id"] == "T1"
    assert service.portfolio_snapshots()["snapshots"][0]["ready"] is True
    assert service.paper_events()["events"][0]["event_type"] == "paper_trade_log"


def test_sync_artifacts_is_idempotent(tmp_path):
    artifact_service = write_artifacts(tmp_path / "mean_reversion_system")
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_tables_for_tests(engine)
    service = DishaDatabaseService(engine=engine, artifact_service=artifact_service)

    first = service.sync_artifacts()
    second = service.sync_artifacts()

    assert first == second
    assert service.signals()["count"] == 2


def test_sync_status_reports_counts_and_timestamp(tmp_path):
    artifact_service = write_artifacts(tmp_path / "mean_reversion_system")
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_tables_for_tests(engine)
    service = DishaDatabaseService(engine=engine, artifact_service=artifact_service)
    service.sync_artifacts()

    status = service.sync_status()

    assert status["counts"]["signals"] == 2
    assert status["counts"]["positions"] == 1
    assert status["counts"]["portfolio_snapshots"] == 1
    assert status["counts"]["paper_events"] == 1
    assert status["latest_sync_at"] is not None


def test_db_readiness_reports_migration_and_tables(tmp_path):
    artifact_service = write_artifacts(tmp_path / "mean_reversion_system")
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_tables_for_tests(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        connection.exec_driver_sql("INSERT INTO alembic_version (version_num) VALUES ('017')")
    service = DishaDatabaseService(engine=engine, artifact_service=artifact_service)

    readiness = service.readiness()

    assert readiness["status"] == "ok"
    assert readiness["migration"]["current"] == "017"
    assert readiness["tables"]["disha_signals"]["exists"] is True
    assert readiness["tables"]["disha_operator_audit"]["exists"] is True
    assert readiness["tables"]["disha_paper_workflow_events"]["exists"] is True


def test_audit_trail_includes_sync_readiness_and_paper_events(tmp_path):
    artifact_service = write_artifacts(tmp_path / "mean_reversion_system")
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_tables_for_tests(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        connection.exec_driver_sql("INSERT INTO alembic_version (version_num) VALUES ('017')")
    service = DishaDatabaseService(engine=engine, artifact_service=artifact_service)
    service.sync_artifacts()

    audit = service.audit_trail()

    event_types = {event["event_type"] for event in audit["events"]}
    assert "sync_status" in event_types
    assert "db_readiness" in event_types
    assert "paper_trade_log" in event_types


def test_operator_audit_events_are_logged_and_included_in_audit_trail(tmp_path):
    artifact_service = write_artifacts(tmp_path / "mean_reversion_system")
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_tables_for_tests(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        connection.exec_driver_sql("INSERT INTO alembic_version (version_num) VALUES ('017')")
    service = DishaDatabaseService(engine=engine, artifact_service=artifact_service)

    logged = service.log_operator_event(
        action="artifact_sync",
        status="rejected",
        confirmation_status="invalid",
        summary="Artifact sync rejected: invalid confirmation phrase",
        raw_payload={"confirmation_supplied": False},
    )
    operator_events = service.operator_events()
    audit = service.audit_trail()

    assert logged["action"] == "artifact_sync"
    assert operator_events["events"][0]["status"] == "rejected"
    assert any(event["event_type"] == "operator_artifact_sync" for event in audit["events"])


def test_paper_workflow_events_are_append_only_and_included_in_audit_trail(tmp_path):
    artifact_service = write_artifacts(tmp_path / "mean_reversion_system")
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_tables_for_tests(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        connection.exec_driver_sql("INSERT INTO alembic_version (version_num) VALUES ('017')")
    service = DishaDatabaseService(engine=engine, artifact_service=artifact_service)

    event = service.append_paper_workflow_event(
        session=1,
        event_date=date(2026, 6, 15),
        workflow_type="scanner_reconciliation",
        status="complete",
        symbol="LTIM",
        notes="Scanner output matched backtest expected signal.",
        raw_payload={"matched": True},
    )
    workflow_events = service.paper_workflow_events()
    filtered_events = service.paper_workflow_events(event_date=date(2026, 6, 15), session=1)
    empty_filtered_events = service.paper_workflow_events(event_date=date(2026, 6, 16), session=1)
    audit = service.audit_trail()

    assert event["workflow_type"] == "scanner_reconciliation"
    assert workflow_events["count"] == 1
    assert filtered_events["count"] == 1
    assert empty_filtered_events["count"] == 0
    assert workflow_events["events"][0]["symbol"] == "LTIM"
    assert any(item["event_type"] == "paper_workflow_scanner_reconciliation" for item in audit["events"])


def test_paper_review_packet_and_csv_exports(tmp_path):
    artifact_service = write_artifacts(tmp_path / "mean_reversion_system")
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_tables_for_tests(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        connection.exec_driver_sql("INSERT INTO alembic_version (version_num) VALUES ('017')")
    service = DishaDatabaseService(engine=engine, artifact_service=artifact_service)
    service.append_paper_workflow_event(
        session=1,
        event_date=date(2026, 6, 15),
        workflow_type="fill_quality",
        status="mismatch",
        symbol="TRENT",
        notes="Actual fill exceeded expected slippage.",
        raw_payload={"slippage_pct": 0.2},
    )

    packet = service.paper_review_packet(event_date=date(2026, 6, 15), session=1)
    markdown = service.paper_review_packet_markdown(event_date=date(2026, 6, 15), session=1)
    csv_text = service.rows_to_csv(packet["workflow_events"])

    assert packet["workflow_count"] == 1
    assert packet["session"] == 1
    assert packet["blocked_items"][0]["status"] == "mismatch"
    assert packet["session_health"]["verdict"] == "NO_GO"
    assert "Disha Paper Trading Review Packet" in markdown
    assert "Actual fill exceeded expected slippage" in csv_text


def test_paper_session_health_verdicts(tmp_path):
    artifact_service = write_artifacts(tmp_path / "mean_reversion_system")
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_tables_for_tests(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        connection.exec_driver_sql("INSERT INTO alembic_version (version_num) VALUES ('017')")
    service = DishaDatabaseService(engine=engine, artifact_service=artifact_service)

    assert service.paper_session_health(event_date=date(2026, 6, 15))["verdict"] == "REVIEW"

    for workflow_type in ["session_checklist", "scanner_reconciliation", "mf_sweep", "fill_quality"]:
        service.append_paper_workflow_event(
            session=1,
            event_date=date(2026, 6, 15),
            workflow_type=workflow_type,
            status="complete",
            notes=f"{workflow_type} done.",
        )
    go_health = service.paper_session_health(event_date=date(2026, 6, 15), session=1)
    assert go_health["verdict"] == "GO"
    assert go_health["completion_pct"] == 100

    service.append_paper_workflow_event(
        session=1,
        event_date=date(2026, 6, 15),
        workflow_type="fill_quality",
        status="mismatch",
        notes="Fill slippage exceeded threshold.",
    )
    assert service.paper_session_health(event_date=date(2026, 6, 15), session=1)["verdict"] == "NO_GO"


def test_paper_milestone_tracker_reports_progress_and_verdicts(tmp_path):
    artifact_service = write_artifacts(tmp_path / "mean_reversion_system")
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_tables_for_tests(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        connection.exec_driver_sql("INSERT INTO alembic_version (version_num) VALUES ('017')")
    service = DishaDatabaseService(engine=engine, artifact_service=artifact_service)

    service.append_paper_workflow_event(
        session=1,
        event_date=date(2026, 6, 15),
        workflow_type="scanner_reconciliation",
        status="complete",
        notes="Scanner checked.",
    )
    partial = service.paper_milestone_tracker()
    assert partial["verdict"] == "REVIEW"
    assert partial["sessions_logged"] == 1
    assert partial["milestones"][0]["completed_sessions"] == 1

    for session in range(1, 31):
        for workflow_type in ["scanner_reconciliation", "mf_sweep", "fill_quality"]:
            service.append_paper_workflow_event(
                session=session,
                event_date=date(2026, 6, 15),
                workflow_type=workflow_type,
                status="complete",
                notes=f"{workflow_type} complete.",
            )
    complete = service.paper_milestone_tracker()
    assert complete["verdict"] == "GO"
    assert all(item["status"] == "complete" for item in complete["milestones"])

    service.append_paper_workflow_event(
        session=30,
        event_date=date(2026, 6, 15),
        workflow_type="fill_quality",
        status="blocked",
        notes="Fill check unresolved.",
    )
    assert service.paper_milestone_tracker()["verdict"] == "NO_GO"


def test_paper_day1_launch_checklist_summarizes_operator_readiness(tmp_path):
    artifact_service = write_artifacts(tmp_path / "mean_reversion_system")
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_tables_for_tests(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        connection.exec_driver_sql("INSERT INTO alembic_version (version_num) VALUES ('017')")
    service = DishaDatabaseService(engine=engine, artifact_service=artifact_service)
    service.sync_artifacts()
    service.append_paper_workflow_event(
        session=1,
        event_date=date(2026, 6, 15),
        workflow_type="scanner_reconciliation",
        status="complete",
        notes="Scanner checked.",
    )

    checklist = service.paper_day1_launch_checklist()

    assert checklist["verdict"] == "READY"
    assert checklist["blocked_count"] == 0
    assert checklist["ready_count"] == len(checklist["steps"])
    step_ids = {step["step_id"] for step in checklist["steps"]}
    assert "scanner_run" in step_ids
    assert "operator_boundary" in step_ids
    assert any("No broker orders" in item for item in checklist["guardrails"])


def test_scanner_remediation_distinguishes_sync_gap_from_ready_state(tmp_path):
    artifact_service = write_artifacts(tmp_path / "mean_reversion_system")
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_tables_for_tests(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        connection.exec_driver_sql("INSERT INTO alembic_version (version_num) VALUES ('017')")
    service = DishaDatabaseService(engine=engine, artifact_service=artifact_service)

    before_sync = service.scanner_remediation()
    assert before_sync["status"] == "REVIEW"
    assert before_sync["primary_gap"] == "db_sync_missing_signals"
    assert before_sync["artifact"]["signal_rows"] == 2
    assert before_sync["database"]["synced_signal_rows"] == 0

    service.sync_artifacts()
    after_sync = service.scanner_remediation()
    assert after_sync["status"] == "READY"
    assert after_sync["primary_gap"] == "none"
    assert after_sync["database"]["synced_signal_rows"] == 2


def test_scanner_rerun_runbook_exposes_existing_command_and_checks(tmp_path):
    artifact_service = write_artifacts(tmp_path / "mean_reversion_system")
    runbook = artifact_service.paper / "DAY_1_SCANNER_RUNBOOK.md"
    runbook.write_text("# Day 1 Scanner Runbook\n", encoding="utf-8")
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_tables_for_tests(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        connection.exec_driver_sql("INSERT INTO alembic_version (version_num) VALUES ('017')")
    service = DishaDatabaseService(engine=engine, artifact_service=artifact_service)

    payload = service.scanner_rerun_runbook()

    assert payload["status"] == "READY"
    assert payload["runbook_exists"] is True
    assert "run_paper_scanner_dry_run.py" in payload["primary_command"]
    assert "--force-vcp-gate" in payload["research_override_command"]
    assert payload["workflow_capture"]["workflow_type"] == "scanner_reconciliation"
    assert any("Do not change scanner thresholds" in item for item in payload["guardrails"])


def test_scanner_reconciliation_suggestion_maps_empty_scan_to_not_applicable(tmp_path):
    artifact_service = write_artifacts(tmp_path / "mean_reversion_system")
    (artifact_service.paper / "day0_scanner_dry_run_signals.csv").write_text(
        "scan_date,symbol,v4b_entry_signal,vcp_entry_signal,market_regime,vcp_market_gate,close\n",
        encoding="utf-8",
    )
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_tables_for_tests(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        connection.exec_driver_sql("INSERT INTO alembic_version (version_num) VALUES ('017')")
    service = DishaDatabaseService(engine=engine, artifact_service=artifact_service)

    suggestion = service.scanner_reconciliation_suggestion()
    payload = suggestion["suggested_payload"]

    assert payload["workflow_type"] == "scanner_reconciliation"
    assert payload["status"] == "not_applicable"
    assert "zero actionable signals" in payload["notes"]
    assert "operator must review" in suggestion["guardrails"][0]


def test_paper_day_closeout_combines_health_suggestion_milestones_and_exports(tmp_path):
    artifact_service = write_artifacts(tmp_path / "mean_reversion_system")
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_tables_for_tests(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        connection.exec_driver_sql("INSERT INTO alembic_version (version_num) VALUES ('017')")
    service = DishaDatabaseService(engine=engine, artifact_service=artifact_service)
    service.append_paper_workflow_event(
        session=1,
        event_date=date(2026, 6, 15),
        workflow_type="scanner_reconciliation",
        status="not_applicable",
        notes="Zero signal day confirmed.",
    )

    closeout = service.paper_day_closeout(event_date=date(2026, 6, 15), session=1)

    assert closeout["verdict"] == "REVIEW"
    assert "mf_sweep" in closeout["session_health"]["missing_workflows"]
    assert closeout["scanner_suggestion"]["suggested_payload"]["workflow_type"] == "scanner_reconciliation"
    assert "review-packet.md" in closeout["export_links"]["review_packet_md"]


def test_paper_workflow_gap_suggestion_prefers_first_missing_workflow(tmp_path):
    artifact_service = write_artifacts(tmp_path / "mean_reversion_system")
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_tables_for_tests(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        connection.exec_driver_sql("INSERT INTO alembic_version (version_num) VALUES ('017')")
    service = DishaDatabaseService(engine=engine, artifact_service=artifact_service)
    service.append_paper_workflow_event(
        session=1,
        event_date=date(2026, 6, 15),
        workflow_type="scanner_reconciliation",
        status="not_applicable",
        notes="Zero signal day confirmed.",
    )

    suggestion = service.paper_workflow_gap_suggestion(event_date=date(2026, 6, 15), session=1)

    assert suggestion["status"] == "review"
    assert suggestion["missing_workflows"][0] == "session_checklist"
    assert suggestion["suggested_payload"]["workflow_type"] == "session_checklist"
    assert suggestion["suggested_payload"]["status"] == "complete"
