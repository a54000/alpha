from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.main import app, get_disha_database_service


class FakeDishaDatabaseService:
    logged_events = []

    def sync_artifacts(self):
        return {"signals": 2, "positions": 1, "portfolio_snapshots": 1, "paper_events": 1}

    def log_operator_event(self, **kwargs):
        self.logged_events.append(kwargs)
        return kwargs

    def sync_status(self):
        return {
            "counts": {"signals": 2, "positions": 1, "portfolio_snapshots": 1, "paper_events": 1},
            "latest_sync_at": "2026-06-15T09:24:04",
        }

    def readiness(self):
        return {
            "status": "ok",
            "migration": {"current": "017", "expected": "017", "status": "ok"},
            "tables": {"disha_signals": {"exists": True, "status": "ok"}},
        }

    def audit_trail(self, limit: int = 100):
        return {
            "count": 1,
            "events": [{"event_type": "sync_status", "summary": "Latest artifact sync state", "limit": limit}],
        }

    def operator_events(self, limit: int = 100):
        return {
            "count": 1,
            "events": [{"action": "artifact_sync", "status": "succeeded", "limit": limit}],
        }

    def paper_workflow_events(self, limit: int = 100, event_date=None, session=None):
        return {
            "count": 1,
            "events": [{"workflow_type": "scanner_reconciliation", "status": "complete", "limit": limit, "event_date": event_date.isoformat() if event_date else None, "session": session}],
        }

    def append_paper_workflow_event(self, **kwargs):
        return {"workflow_event_id": "W1", **kwargs}

    def rows_to_csv(self, rows):
        if not rows:
            return ""
        headers = list(rows[0].keys())
        return ",".join(headers) + "\n" + "\n".join(",".join(str(row.get(header, "")) for header in headers) for row in rows)

    def paper_review_packet(self, event_date=None, session=None, limit: int = 500):
        return {
            "generated_at": "2026-06-15T10:00:00",
            "event_date": event_date.isoformat() if event_date else None,
            "session": session,
            "workflow_count": 1,
            "paper_event_count": 1,
            "audit_event_count": 1,
            "workflow_counts": {"scanner_reconciliation": 1},
            "blocked_items": [],
            "session_health": {"verdict": "GO", "completion_pct": 100},
            "workflow_events": [{"workflow_type": "scanner_reconciliation"}],
            "paper_events": [],
            "audit_events": [],
        }

    def paper_review_packet_markdown(self, event_date=None, session=None, limit: int = 500):
        return "# Disha Paper Trading Review Packet\n"

    def paper_session_health(self, event_date=None, session=None, limit: int = 500):
        return {
            "event_date": event_date.isoformat() if event_date else None,
            "session": session,
            "verdict": "GO",
            "completion_pct": 100,
            "missing_workflows": [],
            "unresolved_items": [],
            "checks": [],
        }

    def paper_milestone_tracker(self, limit: int = 5000):
        return {
            "sessions_logged": 1,
            "latest_session": 1,
            "verdict": "REVIEW",
            "milestones": [{"milestone": "Scanner reconciliation", "completed_sessions": 1, "target": 5}],
            "unresolved_items": [],
        }

    def paper_day1_launch_checklist(self, limit: int = 5000):
        return {
            "verdict": "READY",
            "ready_count": 8,
            "review_count": 0,
            "blocked_count": 0,
            "steps": [{"step_id": "scanner_run", "label": "Scanner output available", "status": "ready"}],
            "operator_flow": ["Run or sync scanner artifacts after market close."],
            "guardrails": ["No broker orders are placed from this checklist."],
        }

    def scanner_remediation(self):
        return {
            "status": "REVIEW",
            "primary_gap": "scanner_artifact_empty",
            "next_action": "Confirm whether zero signals is expected.",
            "artifact": {"signal_rows": 0, "signals_file": "signals.csv"},
            "database": {"synced_signal_rows": 0},
            "safe_actions": ["Record a scanner_reconciliation workflow note after manual verification."],
            "disabled_actions": ["place_order"],
        }

    def scanner_rerun_runbook(self):
        return {
            "status": "READY",
            "runbook_exists": True,
            "primary_command": ".\\.venv\\Scripts\\python.exe .\\mean_reversion_system\\scripts\\run_paper_scanner_dry_run.py",
            "research_override_command": ".\\.venv\\Scripts\\python.exe .\\mean_reversion_system\\scripts\\run_paper_scanner_dry_run.py --force-vcp-gate",
            "post_run_checks": ["Confirm summary scan_date is the latest completed market session."],
            "workflow_capture": {"workflow_type": "scanner_reconciliation"},
        }

    def scanner_reconciliation_suggestion(self):
        return {
            "suggested_payload": {
                "session": 1,
                "event_date": "2026-06-15",
                "workflow_type": "scanner_reconciliation",
                "status": "not_applicable",
                "symbol": None,
                "notes": "Scanner produced zero actionable signals.",
            },
            "review_action": "Append only if zero signals is expected.",
            "guardrails": ["This is a suggestion only; the operator must review before appending."],
        }

    def paper_day_closeout(self, event_date=None, session=None, limit: int = 500):
        return {
            "event_date": event_date.isoformat() if event_date else None,
            "session": session,
            "verdict": "REVIEW",
            "blockers": ["Missing workflow checks: mf_sweep."],
            "session_health": {"verdict": "REVIEW"},
            "scanner_suggestion": {"suggested_payload": {"status": "not_applicable"}},
            "milestones": {"verdict": "REVIEW"},
            "review_counts": {"workflow_count": 1, "paper_event_count": 1, "audit_event_count": 1},
            "export_links": {"review_packet_md": "/api/db/paper/review-packet.md?limit=500"},
        }

    def paper_workflow_gap_suggestion(self, event_date=None, session=None, limit: int = 500):
        return {
            "status": "review",
            "missing_workflows": ["session_checklist"],
            "suggested_payload": {
                "session": session or 1,
                "event_date": event_date.isoformat() if event_date else "2026-06-15",
                "workflow_type": "session_checklist",
                "status": "complete",
                "notes": "Session checklist reviewed.",
            },
            "review_action": "Review and append the suggested session_checklist workflow note if the evidence is correct.",
        }

    def signals(self, limit: int = 100):
        return {"count": 1, "signals": [{"symbol": "LTIM", "limit": limit}]}

    def positions(self, limit: int = 100):
        return {"count": 1, "positions": [{"symbol": "LTIM", "limit": limit}]}

    def portfolio_snapshots(self, limit: int = 100):
        return {"count": 1, "snapshots": [{"ready": True, "limit": limit}]}

    def paper_events(self, limit: int = 100):
        return {"count": 1, "events": [{"event_type": "paper_trade_log", "limit": limit}]}


def client():
    FakeDishaDatabaseService.logged_events = []
    app.dependency_overrides[get_disha_database_service] = lambda: FakeDishaDatabaseService()
    return TestClient(app)


def test_disha_db_sync_endpoint():
    response = client().post("/api/db/sync", json={"confirmation_phrase": "SYNC DISHA"})

    assert response.status_code == 200
    assert response.json()["status"] == "synced"
    assert response.json()["counts"]["signals"] == 2
    statuses = [event["status"] for event in FakeDishaDatabaseService.logged_events]
    assert statuses == ["attempted", "succeeded"]


def test_disha_db_sync_rejects_missing_confirmation_phrase():
    response = client().post("/api/db/sync", json={"confirmation_phrase": ""})

    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid Disha sync confirmation phrase"
    assert FakeDishaDatabaseService.logged_events[0]["status"] == "rejected"
    assert FakeDishaDatabaseService.logged_events[0]["confirmation_status"] == "invalid"


def test_disha_operator_boundary_endpoint():
    response = client().get("/api/operator/boundary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["live_trading_enabled"] is False
    assert payload["orders_enabled"] is False
    assert payload["read_only_default"] is True
    assert payload["mutation_allowlist"][0]["path"] == "/api/db/sync"
    assert payload["mutation_allowlist"][0]["trading_effect"] == "none"


def test_disha_db_sync_status_endpoint():
    response = client().get("/api/db/sync/status")

    assert response.status_code == 200
    assert response.json()["latest_sync_at"] == "2026-06-15T09:24:04"
    assert response.json()["counts"]["paper_events"] == 1


def test_disha_db_readiness_endpoint():
    response = client().get("/api/db/readiness")

    assert response.status_code == 200
    assert response.json()["migration"]["current"] == "017"
    assert response.json()["tables"]["disha_signals"]["exists"] is True


def test_disha_db_audit_trail_endpoint():
    response = client().get("/api/db/audit/trail?limit=10")

    assert response.status_code == 200
    assert response.json()["events"][0]["event_type"] == "sync_status"
    assert response.json()["events"][0]["limit"] == 10


def test_disha_db_operator_audit_endpoint():
    response = client().get("/api/db/audit/operator?limit=10")

    assert response.status_code == 200
    assert response.json()["events"][0]["action"] == "artifact_sync"
    assert response.json()["events"][0]["limit"] == 10


def test_disha_db_paper_workflow_events_endpoint():
    response = client().get("/api/db/paper/workflow-events?limit=10&event_date=2026-06-15&session=1")

    assert response.status_code == 200
    assert response.json()["events"][0]["workflow_type"] == "scanner_reconciliation"
    assert response.json()["events"][0]["limit"] == 10
    assert response.json()["events"][0]["event_date"] == "2026-06-15"
    assert response.json()["events"][0]["session"] == 1


def test_disha_db_paper_workflow_events_export_endpoint():
    response = client().get("/api/db/paper/workflow-events/export.csv?limit=10")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "scanner_reconciliation" in response.text


def test_disha_db_audit_trail_export_endpoint():
    response = client().get("/api/db/audit/trail/export.csv?limit=10")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "sync_status" in response.text


def test_disha_db_paper_review_packet_endpoint():
    response = client().get("/api/db/paper/review-packet?event_date=2026-06-15&session=1")

    assert response.status_code == 200
    assert response.json()["event_date"] == "2026-06-15"
    assert response.json()["session"] == 1
    assert response.json()["workflow_count"] == 1
    assert response.json()["session_health"]["verdict"] == "GO"


def test_disha_db_paper_session_health_endpoint():
    response = client().get("/api/db/paper/session-health?event_date=2026-06-15&session=1")

    assert response.status_code == 200
    assert response.json()["event_date"] == "2026-06-15"
    assert response.json()["session"] == 1
    assert response.json()["verdict"] == "GO"


def test_disha_db_paper_day_closeout_endpoint():
    response = client().get("/api/db/paper/day-closeout?event_date=2026-06-15&session=1")

    assert response.status_code == 200
    assert response.json()["event_date"] == "2026-06-15"
    assert response.json()["session"] == 1
    assert response.json()["verdict"] == "REVIEW"


def test_disha_db_paper_workflow_gap_suggestion_endpoint():
    response = client().get("/api/db/paper/workflow-gap-suggestion?event_date=2026-06-15&session=1")

    assert response.status_code == 200
    assert response.json()["suggested_payload"]["workflow_type"] == "session_checklist"
    assert response.json()["suggested_payload"]["status"] == "complete"


def test_disha_db_paper_milestones_endpoint():
    response = client().get("/api/db/paper/milestones?limit=10")

    assert response.status_code == 200
    assert response.json()["verdict"] == "REVIEW"
    assert response.json()["milestones"][0]["target"] == 5


def test_disha_db_paper_day1_launch_checklist_endpoint():
    response = client().get("/api/db/paper/day1-launch-checklist?limit=10")

    assert response.status_code == 200
    assert response.json()["verdict"] == "READY"
    assert response.json()["steps"][0]["step_id"] == "scanner_run"


def test_disha_db_scanner_remediation_endpoint():
    response = client().get("/api/db/scanner/remediation")

    assert response.status_code == 200
    assert response.json()["status"] == "REVIEW"
    assert response.json()["primary_gap"] == "scanner_artifact_empty"


def test_disha_db_scanner_rerun_runbook_endpoint():
    response = client().get("/api/db/scanner/rerun-runbook")

    assert response.status_code == 200
    assert response.json()["status"] == "READY"
    assert "run_paper_scanner_dry_run.py" in response.json()["primary_command"]


def test_disha_db_scanner_reconciliation_suggestion_endpoint():
    response = client().get("/api/db/scanner/reconciliation-suggestion")

    assert response.status_code == 200
    assert response.json()["suggested_payload"]["workflow_type"] == "scanner_reconciliation"
    assert response.json()["suggested_payload"]["status"] == "not_applicable"


def test_disha_db_paper_review_packet_markdown_endpoint():
    response = client().get("/api/db/paper/review-packet.md?event_date=2026-06-15&session=1")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "Disha Paper Trading Review Packet" in response.text


def test_disha_db_append_paper_workflow_event_endpoint():
    response = client().post(
        "/api/db/paper/workflow-events",
        json={
            "session": 1,
            "event_date": "2026-06-15",
            "workflow_type": "scanner_reconciliation",
            "status": "complete",
            "symbol": "LTIM",
            "notes": "Matched expected signal.",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "appended"
    assert response.json()["event"]["workflow_type"] == "scanner_reconciliation"
    assert FakeDishaDatabaseService.logged_events[0]["action"] == "paper_workflow_append"


def test_disha_db_append_paper_workflow_event_rejects_invalid_type():
    response = client().post(
        "/api/db/paper/workflow-events",
        json={
            "session": 1,
            "event_date": "2026-06-15",
            "workflow_type": "trade_order",
            "status": "complete",
            "notes": "Nope.",
        },
    )

    assert response.status_code == 422


def test_disha_db_signals_endpoint():
    response = client().get("/api/db/signals?limit=10")

    assert response.status_code == 200
    assert response.json()["signals"][0]["limit"] == 10


def test_disha_db_positions_endpoint():
    response = client().get("/api/db/positions?limit=10")

    assert response.status_code == 200
    assert response.json()["positions"][0]["symbol"] == "LTIM"


def test_disha_db_portfolio_snapshots_endpoint():
    response = client().get("/api/db/portfolio/snapshots?limit=10")

    assert response.status_code == 200
    assert response.json()["snapshots"][0]["ready"] is True


def test_disha_db_paper_events_endpoint():
    response = client().get("/api/db/paper/events?limit=10")

    assert response.status_code == 200
    assert response.json()["events"][0]["event_type"] == "paper_trade_log"
