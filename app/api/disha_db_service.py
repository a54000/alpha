"""Database-backed Disha sync and read service."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import sqlalchemy as sa
from sqlalchemy.engine import Engine

from app.api.disha_db import (
    create_disha_tables,
    disha_operator_audit,
    disha_paper_events,
    disha_paper_workflow_events,
    disha_portfolio_snapshots,
    disha_positions,
    disha_signals,
)
from app.api.disha_service import DishaReadService, DishaReadServiceError

EXPECTED_ALEMBIC_HEAD = "017"
REQUIRED_PAPER_WORKFLOWS = ["session_checklist", "scanner_reconciliation", "mf_sweep", "fill_quality"]
PAPER_MILESTONES = [
    {
        "milestone": "Scanner reconciliation",
        "session_range": "1-5",
        "workflow_type": "scanner_reconciliation",
        "target": 5,
    },
    {
        "milestone": "MF workflow validation",
        "session_range": "1-20",
        "workflow_type": "mf_sweep",
        "target": 20,
    },
    {
        "milestone": "09:15 fill quality",
        "session_range": "1-30",
        "workflow_type": "fill_quality",
        "target": 30,
    },
]
DAY1_LAUNCH_STEPS = [
    {
        "step_id": "api_readiness",
        "label": "API artifact readiness",
        "evidence": "Readiness endpoint can load locked rules, scanner, paper, and regime artifacts.",
    },
    {
        "step_id": "db_readiness",
        "label": "DB readiness",
        "evidence": "Disha app tables and Alembic migration state are available.",
    },
    {
        "step_id": "artifact_sync",
        "label": "Artifact sync state",
        "evidence": "Scanner, position, snapshot, and paper artifacts have been synced into app tables.",
    },
    {
        "step_id": "scanner_run",
        "label": "Scanner output available",
        "evidence": "Synced signal rows exist for Day 1 scanner reconciliation.",
    },
    {
        "step_id": "workflow_capture",
        "label": "Workflow capture ready",
        "evidence": "Paper workflow notes can record scanner, MF sweep, fill-quality, and session checks.",
    },
    {
        "step_id": "review_exports",
        "label": "Review exports ready",
        "evidence": "Daily review packet and workflow/audit exports are available.",
    },
    {
        "step_id": "milestone_tracker",
        "label": "Milestone tracker ready",
        "evidence": "30-session paper milestone tracker is reporting a readiness verdict.",
    },
    {
        "step_id": "operator_boundary",
        "label": "Trading boundary locked",
        "evidence": "Trading, order placement, and MF execution actions remain disabled.",
    },
]


class DishaDatabaseServiceError(RuntimeError):
    """Raised when Disha app table sync/read fails."""


def make_engine(database_url: str | None = None) -> Engine:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass
    url = database_url or os.environ.get("DATABASE_URL")
    if not url:
        raise DishaDatabaseServiceError("DATABASE_URL is required for Disha database endpoints.")
    return sa.create_engine(url, future=True)


class DishaDatabaseService:
    """Sync existing Disha files into app tables and read them back."""

    def __init__(self, engine: Engine | None = None, artifact_service: DishaReadService | None = None) -> None:
        self.engine = engine or make_engine()
        self.artifacts = artifact_service or DishaReadService()

    def sync_artifacts(self) -> dict[str, int]:
        """Import current Disha artifacts into app tables without mutating source files."""

        counts = {
            "signals": 0,
            "positions": 0,
            "portfolio_snapshots": 0,
            "paper_events": 0,
        }
        signal_rows = self._signal_rows()
        position_rows = self._position_rows()
        snapshot_rows = self._snapshot_rows()
        event_rows = self._paper_event_rows()
        with self.engine.begin() as connection:
            connection.execute(disha_signals.delete())
            connection.execute(disha_positions.delete())
            connection.execute(disha_portfolio_snapshots.delete())
            connection.execute(disha_paper_events.delete())
            if signal_rows:
                connection.execute(disha_signals.insert(), signal_rows)
            if position_rows:
                connection.execute(disha_positions.insert(), position_rows)
            if snapshot_rows:
                connection.execute(disha_portfolio_snapshots.insert(), snapshot_rows)
            if event_rows:
                connection.execute(disha_paper_events.insert(), event_rows)
        counts["signals"] = len(signal_rows)
        counts["positions"] = len(position_rows)
        counts["portfolio_snapshots"] = len(snapshot_rows)
        counts["paper_events"] = len(event_rows)
        return counts

    def signals(self, limit: int = 100) -> dict[str, Any]:
        rows = self._fetch_rows(disha_signals, disha_signals.c.scan_date.desc(), limit)
        return {"count": len(rows), "signals": rows}

    def positions(self, limit: int = 100) -> dict[str, Any]:
        rows = self._fetch_rows(disha_positions, disha_positions.c.created_at.desc(), limit)
        return {"count": len(rows), "positions": rows}

    def portfolio_snapshots(self, limit: int = 100) -> dict[str, Any]:
        rows = self._fetch_rows(disha_portfolio_snapshots, disha_portfolio_snapshots.c.created_at.desc(), limit)
        return {"count": len(rows), "snapshots": rows}

    def paper_events(self, limit: int = 100) -> dict[str, Any]:
        rows = self._fetch_rows(disha_paper_events, disha_paper_events.c.created_at.desc(), limit)
        return {"count": len(rows), "events": rows}

    def sync_status(self) -> dict[str, Any]:
        """Return current Disha app table counts and latest synced timestamp."""

        tables = {
            "signals": disha_signals,
            "positions": disha_positions,
            "portfolio_snapshots": disha_portfolio_snapshots,
            "paper_events": disha_paper_events,
        }
        try:
            with self.engine.connect() as connection:
                counts: dict[str, int] = {}
                latest_values: list[datetime] = []
                for name, table in tables.items():
                    counts[name] = int(connection.execute(sa.select(sa.func.count()).select_from(table)).scalar_one())
                    latest = connection.execute(sa.select(sa.func.max(table.c.created_at))).scalar_one()
                    if latest is not None:
                        latest_values.append(latest)
                latest_sync_at = max(latest_values).isoformat() if latest_values else None
                return {"counts": counts, "latest_sync_at": latest_sync_at}
        except Exception as exc:
            raise DishaDatabaseServiceError(f"Unable to read Disha sync status: {exc}") from exc

    def readiness(self) -> dict[str, Any]:
        """Return read-only database readiness checks for Disha."""

        expected_tables = [
            "disha_users",
            "disha_signals",
            "disha_positions",
            "disha_portfolio_snapshots",
            "disha_paper_events",
            "disha_operator_audit",
            "disha_paper_workflow_events",
        ]
        try:
            inspector = sa.inspect(self.engine)
            existing_tables = set(inspector.get_table_names())
            table_checks = {table: {"exists": table in existing_tables, "status": "ok" if table in existing_tables else "missing"} for table in expected_tables}
            with self.engine.connect() as connection:
                version = connection.execute(sa.text("SELECT version_num FROM alembic_version LIMIT 1")).scalar()
            migration_status = "ok" if version == EXPECTED_ALEMBIC_HEAD else "degraded"
            tables_status = "ok" if all(item["exists"] for item in table_checks.values()) else "degraded"
            return {
                "status": "ok" if migration_status == "ok" and tables_status == "ok" else "degraded",
                "migration": {
                    "current": version,
                    "expected": EXPECTED_ALEMBIC_HEAD,
                    "status": migration_status,
                },
                "tables": table_checks,
            }
        except Exception as exc:
            raise DishaDatabaseServiceError(f"Unable to read Disha DB readiness: {exc}") from exc

    def audit_trail(self, limit: int = 100) -> dict[str, Any]:
        """Return an operational audit trail derived from synced Disha state."""

        events: list[dict[str, Any]] = []
        try:
            sync = self.sync_status()
            if sync.get("latest_sync_at"):
                events.append(
                    {
                        "event_time": sync["latest_sync_at"],
                        "event_type": "sync_status",
                        "severity": "info",
                        "summary": "Latest artifact sync state",
                        "details": sync,
                    }
                )
            readiness = self.readiness()
            events.append(
                {
                    "event_time": datetime.now().isoformat(),
                    "event_type": "db_readiness",
                    "severity": "info" if readiness.get("status") == "ok" else "warning",
                    "summary": f"DB readiness {readiness.get('status', 'unknown')}",
                    "details": readiness,
                }
            )
            paper_rows = self.paper_events(limit=limit).get("events", [])
            workflow_rows = self.paper_workflow_events(limit=limit).get("events", [])
            operator_rows = self.operator_events(limit=limit).get("events", [])
            for row in operator_rows:
                events.append(
                    {
                        "event_time": row.get("event_time"),
                        "event_type": f"operator_{row.get('action')}",
                        "severity": "warning" if row.get("status") == "rejected" else "info",
                        "summary": row.get("summary") or row.get("status"),
                        "details": row,
                    }
                )
            for row in paper_rows:
                details = row.get("raw_payload") or {}
                caveat_notes = details.get("caveat_notes") if isinstance(details, dict) else None
                events.append(
                    {
                        "event_time": row.get("event_date") or row.get("created_at"),
                        "event_type": row.get("event_type"),
                        "severity": "info",
                        "summary": caveat_notes or row.get("action") or row.get("event_type"),
                        "details": row,
                    }
                )
            for row in workflow_rows:
                events.append(
                    {
                        "event_time": row.get("event_time"),
                        "event_type": f"paper_workflow_{row.get('workflow_type')}",
                        "severity": "warning" if row.get("status") in {"blocked", "mismatch"} else "info",
                        "summary": row.get("notes") or row.get("status"),
                        "details": row,
                    }
                )
            events.sort(key=lambda item: str(item.get("event_time") or ""), reverse=True)
            return {"count": len(events[:limit]), "events": events[:limit]}
        except Exception as exc:
            raise DishaDatabaseServiceError(f"Unable to build Disha audit trail: {exc}") from exc

    def log_operator_event(
        self,
        *,
        action: str,
        status: str,
        summary: str,
        confirmation_status: str | None = None,
        source: str = "api",
        raw_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Append an operator action audit event."""

        now = datetime.now()
        payload = self._jsonable(raw_payload or {})
        row = {
            "audit_id": self._id("operator", now.isoformat(), action, status, confirmation_status, json.dumps(payload, sort_keys=True)),
            "event_time": now,
            "action": action,
            "status": status,
            "confirmation_status": confirmation_status,
            "source": source,
            "summary": summary,
            "raw_payload": payload,
        }
        try:
            with self.engine.begin() as connection:
                connection.execute(disha_operator_audit.insert(), row)
            return self._jsonable(row)
        except Exception as exc:
            raise DishaDatabaseServiceError(f"Unable to log Disha operator event: {exc}") from exc

    def operator_events(self, limit: int = 100) -> dict[str, Any]:
        rows = self._fetch_rows(disha_operator_audit, disha_operator_audit.c.event_time.desc(), limit)
        return {"count": len(rows), "events": rows}

    def append_paper_workflow_event(
        self,
        *,
        session: int,
        event_date: date,
        workflow_type: str,
        status: str,
        notes: str,
        symbol: str | None = None,
        raw_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Append a paper-trading workflow note without mutating source artifacts."""

        now = datetime.now()
        payload = self._jsonable(raw_payload or {})
        row = {
            "workflow_event_id": self._id("paper_workflow", now.isoformat(), session, event_date, workflow_type, status, symbol, notes),
            "event_time": now,
            "session": session,
            "event_date": event_date,
            "workflow_type": workflow_type,
            "status": status,
            "symbol": self._str_or_none(symbol),
            "notes": notes,
            "raw_payload": payload,
        }
        try:
            with self.engine.begin() as connection:
                connection.execute(disha_paper_workflow_events.insert(), row)
            return self._jsonable(row)
        except Exception as exc:
            raise DishaDatabaseServiceError(f"Unable to append Disha paper workflow event: {exc}") from exc

    def paper_workflow_events(self, limit: int = 100, event_date: date | None = None, session: int | None = None) -> dict[str, Any]:
        filters = []
        if event_date is not None:
            filters.append(disha_paper_workflow_events.c.event_date == event_date)
        if session is not None:
            filters.append(disha_paper_workflow_events.c.session == session)
        rows = self._fetch_rows(disha_paper_workflow_events, disha_paper_workflow_events.c.event_time.desc(), limit, filters=filters)
        return {"count": len(rows), "events": rows}

    def paper_review_packet(self, event_date: date | None = None, session: int | None = None, limit: int = 500) -> dict[str, Any]:
        """Build a daily paper-trading review packet from DB-backed operating evidence."""

        workflow = self.paper_workflow_events(limit=limit, event_date=event_date, session=session)["events"]
        audit = self.audit_trail(limit=limit)["events"]
        paper = self.paper_events(limit=limit)["events"]
        health = self.paper_session_health(event_date=event_date, session=session, limit=limit)
        if event_date is not None:
            expected = event_date.isoformat()
            paper = [row for row in paper if str(row.get("event_date")) == expected]
        if session is not None:
            paper = [row for row in paper if row.get("session") == session]
        workflow_counts: dict[str, int] = {}
        for row in workflow:
            key = str(row.get("workflow_type") or "unknown")
            workflow_counts[key] = workflow_counts.get(key, 0) + 1
        blocked = [row for row in workflow if row.get("status") in {"blocked", "mismatch"}]
        return {
            "generated_at": datetime.now().isoformat(),
            "event_date": event_date.isoformat() if event_date else None,
            "session": session,
            "workflow_count": len(workflow),
            "paper_event_count": len(paper),
            "audit_event_count": len(audit),
            "workflow_counts": workflow_counts,
            "blocked_items": blocked,
            "session_health": health,
            "workflow_events": workflow,
            "paper_events": paper,
            "audit_events": audit,
        }

    def paper_session_health(self, event_date: date | None = None, session: int | None = None, limit: int = 500) -> dict[str, Any]:
        """Summarize paper-trading workflow completion and readiness."""

        workflow = self.paper_workflow_events(limit=limit, event_date=event_date, session=session)["events"]
        latest_by_type: dict[str, dict[str, Any]] = {}
        for row in workflow:
            workflow_type = str(row.get("workflow_type") or "")
            if workflow_type and workflow_type not in latest_by_type:
                latest_by_type[workflow_type] = row
        checks = []
        for workflow_type in REQUIRED_PAPER_WORKFLOWS:
            row = latest_by_type.get(workflow_type)
            status = row.get("status") if row else "missing"
            checks.append(
                {
                    "workflow_type": workflow_type,
                    "status": status,
                    "complete": status in {"complete", "not_applicable"},
                    "event_time": row.get("event_time") if row else None,
                    "notes": row.get("notes") if row else None,
                }
            )
        unresolved = [row for row in workflow if row.get("status") in {"blocked", "mismatch", "pending"}]
        missing = [item for item in checks if item["status"] == "missing"]
        completion_pct = round((sum(1 for item in checks if item["complete"]) / len(checks)) * 100, 2)
        if unresolved:
            verdict = "NO_GO"
        elif missing:
            verdict = "REVIEW"
        else:
            verdict = "GO"
        return {
            "generated_at": datetime.now().isoformat(),
            "event_date": event_date.isoformat() if event_date else None,
            "session": session,
            "verdict": verdict,
            "completion_pct": completion_pct,
            "required_workflows": REQUIRED_PAPER_WORKFLOWS,
            "checks": checks,
            "missing_workflows": [item["workflow_type"] for item in missing],
            "unresolved_items": unresolved,
            "workflow_event_count": len(workflow),
        }

    def paper_milestone_tracker(self, limit: int = 5_000) -> dict[str, Any]:
        """Track progress against the 30-session paper-trading operating plan."""

        workflow = self.paper_workflow_events(limit=limit)["events"]
        sessions = sorted({int(row["session"]) for row in workflow if row.get("session") is not None})
        completed_by_type: dict[str, set[int]] = {item["workflow_type"]: set() for item in PAPER_MILESTONES}
        unresolved = []
        for row in workflow:
            status = row.get("status")
            workflow_type = str(row.get("workflow_type") or "")
            session = row.get("session")
            if status in {"blocked", "mismatch", "pending"}:
                unresolved.append(row)
            if status in {"complete", "not_applicable"} and workflow_type in completed_by_type and session is not None:
                completed_by_type[workflow_type].add(int(session))
        milestones = []
        for item in PAPER_MILESTONES:
            completed = len(completed_by_type[item["workflow_type"]])
            target = int(item["target"])
            pct = round(min(100.0, (completed / target) * 100), 2)
            milestones.append(
                {
                    **item,
                    "completed_sessions": completed,
                    "remaining_sessions": max(0, target - completed),
                    "completion_pct": pct,
                    "status": "complete" if completed >= target else "in_progress" if completed > 0 else "not_started",
                }
            )
        if unresolved:
            verdict = "NO_GO"
        elif all(item["status"] == "complete" for item in milestones):
            verdict = "GO"
        else:
            verdict = "REVIEW"
        return {
            "generated_at": datetime.now().isoformat(),
            "sessions_logged": len(sessions),
            "first_session": sessions[0] if sessions else None,
            "latest_session": sessions[-1] if sessions else None,
            "milestones": milestones,
            "unresolved_items": unresolved,
            "verdict": verdict,
        }

    def paper_day1_launch_checklist(self, limit: int = 5_000) -> dict[str, Any]:
        """Build a guided Day 1 launch checklist from existing read-only evidence."""

        readiness = self.artifacts.readiness()
        db_readiness = self.readiness()
        sync_status = self.sync_status()
        signal_count = self.signals(limit=1)["count"]
        workflow_count = self.paper_workflow_events(limit=1)["count"]
        review_packet = self.paper_review_packet(limit=limit)
        milestones = self.paper_milestone_tracker(limit=limit)
        checks_by_id = {
            "api_readiness": {
                "status": "ready" if readiness.get("status") in {"ok", "ready"} else "review",
                "details": readiness,
            },
            "db_readiness": {
                "status": "ready" if db_readiness.get("status") == "ok" else "review",
                "details": db_readiness,
            },
            "artifact_sync": {
                "status": "ready" if all(int(value or 0) > 0 for value in sync_status.get("counts", {}).values()) else "review",
                "details": sync_status,
            },
            "scanner_run": {
                "status": "ready" if signal_count > 0 else "review",
                "details": {"synced_signal_rows": signal_count},
            },
            "workflow_capture": {
                "status": "ready",
                "details": {
                    "workflow_note_count": workflow_count,
                    "allowed_workflows": REQUIRED_PAPER_WORKFLOWS,
                },
            },
            "review_exports": {
                "status": "ready",
                "details": {
                    "workflow_count": review_packet["workflow_count"],
                    "paper_event_count": review_packet["paper_event_count"],
                    "audit_event_count": review_packet["audit_event_count"],
                },
            },
            "milestone_tracker": {
                "status": "ready" if milestones.get("verdict") in {"GO", "REVIEW"} else "blocked",
                "details": milestones,
            },
            "operator_boundary": {
                "status": "ready",
                "details": {
                    "orders_enabled": False,
                    "live_trading_enabled": False,
                    "disabled_actions": ["place_order", "modify_order", "cancel_order", "redeem_mf", "invest_mf"],
                },
            },
        }
        steps = []
        for item in DAY1_LAUNCH_STEPS:
            check = checks_by_id[item["step_id"]]
            steps.append({**item, **check})
        blocked = [item for item in steps if item["status"] == "blocked"]
        review = [item for item in steps if item["status"] == "review"]
        if blocked:
            verdict = "NO_GO"
        elif review:
            verdict = "REVIEW"
        else:
            verdict = "READY"
        return {
            "generated_at": datetime.now().isoformat(),
            "verdict": verdict,
            "ready_count": sum(1 for item in steps if item["status"] == "ready"),
            "review_count": len(review),
            "blocked_count": len(blocked),
            "steps": steps,
            "operator_flow": [
                "Run or sync scanner artifacts after market close.",
                "Record session_checklist and scanner_reconciliation workflow notes.",
                "Record MF sweep validation when idle capital is reviewed.",
                "Record fill_quality notes for any entry orders.",
                "Export the daily review packet and check session health before closing the day.",
            ],
            "guardrails": [
                "No broker orders are placed from this checklist.",
                "No MF investment or redemption is executed from this checklist.",
                "No strategy parameters or trading rules are changed.",
            ],
        }

    def scanner_remediation(self) -> dict[str, Any]:
        """Explain scanner readiness gaps and the safest next operator action."""

        readiness = self.artifacts.readiness()
        scanner = self.artifacts.signals_today()
        sync_status = self.sync_status()
        db_signal_count = int(sync_status.get("counts", {}).get("signals") or 0)
        artifact_signal_count = int(scanner.get("count") or 0)
        signals_file = str(scanner.get("source") or readiness.get("scanner", {}).get("signals_file") or "")
        artifact_exists = bool(readiness.get("artifact_checks", {}).get("scanner_signals", {}).get("exists"))
        artifact_modified_at = readiness.get("artifact_checks", {}).get("scanner_signals", {}).get("modified_at")
        if not artifact_exists:
            status = "NO_GO"
            primary_gap = "scanner_artifact_missing"
            next_action = "Run the existing scanner process to create the scanner signal artifact, then return here and sync artifacts."
        elif artifact_signal_count == 0:
            status = "REVIEW"
            primary_gap = "scanner_artifact_empty"
            next_action = "Confirm whether zero signals is expected for the scan date. If expected, record scanner_reconciliation as not_applicable; if not expected, rerun the scanner artifact producer."
        elif db_signal_count == 0:
            status = "REVIEW"
            primary_gap = "db_sync_missing_signals"
            next_action = "Use the guarded Sync Artifacts action to import scanner rows into Disha app tables."
        else:
            status = "READY"
            primary_gap = "none"
            next_action = "Proceed with Day 1 scanner reconciliation against expected backtest signals."
        return {
            "generated_at": datetime.now().isoformat(),
            "status": status,
            "primary_gap": primary_gap,
            "next_action": next_action,
            "artifact": {
                "exists": artifact_exists,
                "signals_file": signals_file,
                "modified_at": artifact_modified_at,
                "signal_rows": artifact_signal_count,
                "summary": scanner.get("summary", {}),
            },
            "database": {
                "synced_signal_rows": db_signal_count,
                "sync_counts": sync_status.get("counts", {}),
                "latest_sync_at": sync_status.get("latest_sync_at"),
            },
            "safe_actions": [
                "Open the guarded Sync Artifacts confirmation when artifact rows exist but DB rows are stale.",
                "Record a scanner_reconciliation workflow note after manual verification.",
                "Export the review packet after scanner remediation is resolved.",
            ],
            "disabled_actions": ["place_order", "modify_order", "cancel_order", "redeem_mf", "invest_mf"],
        }

    def scanner_rerun_runbook(self) -> dict[str, Any]:
        """Return the existing scanner rerun process as read-only operator guidance."""

        remediation = self.scanner_remediation()
        runbook_path = self.artifacts.paper / "DAY_1_SCANNER_RUNBOOK.md"
        runbook_exists = runbook_path.exists()
        return {
            "generated_at": datetime.now().isoformat(),
            "status": "READY" if runbook_exists else "REVIEW",
            "runbook_path": str(runbook_path),
            "runbook_exists": runbook_exists,
            "primary_command": r".\.venv\Scripts\python.exe .\mean_reversion_system\scripts\run_paper_scanner_dry_run.py",
            "research_override_command": r".\.venv\Scripts\python.exe .\mean_reversion_system\scripts\run_paper_scanner_dry_run.py --force-vcp-gate",
            "working_directory": str(self.artifacts.root.parent),
            "expected_outputs": [
                str(self.artifacts.paper / "day0_scanner_dry_run_summary.json"),
                str(self.artifacts.paper / "day0_scanner_dry_run_signals.csv"),
            ],
            "post_run_checks": [
                "Confirm summary scan_date is the latest completed market session.",
                "Confirm symbols_scanned is close to the expected liquid universe size.",
                "Confirm signal row count matches v4b_signals + vcp_signals in the summary.",
                "Run guarded artifact sync if signal rows are present or if the scanner output changed.",
                "Record scanner_reconciliation workflow evidence as complete or not_applicable.",
                "Re-open scanner remediation and Day 1 launch checklist before closing the session.",
            ],
            "current_remediation": remediation,
            "workflow_capture": {
                "workflow_type": "scanner_reconciliation",
                "complete_status": "complete",
                "zero_signal_status": "not_applicable",
                "blocked_status": "blocked",
            },
            "guardrails": [
                "Do not change scanner thresholds or strategy parameters during paper trading.",
                "Do not use the research override for production paper-trading evidence unless explicitly labelled as research-only.",
                "Do not place orders, redeem MF units, or invest idle cash from this runbook.",
            ],
        }

    def scanner_reconciliation_suggestion(self) -> dict[str, Any]:
        """Suggest a scanner reconciliation workflow note for operator review."""

        remediation = self.scanner_remediation()
        artifact = remediation.get("artifact", {})
        database = remediation.get("database", {})
        summary = artifact.get("summary") if isinstance(artifact, dict) else {}
        primary_gap = str(remediation.get("primary_gap") or "unknown")
        if primary_gap == "none":
            status = "complete"
            review_action = "Review scanner rows against expected backtest signals before appending."
            notes = (
                f"Scanner reconciliation complete: artifact rows={artifact.get('signal_rows')}, "
                f"DB synced signal rows={database.get('synced_signal_rows')}, "
                f"scan_date={summary.get('scan_date', 'unknown')}."
            )
        elif primary_gap == "scanner_artifact_empty":
            status = "not_applicable"
            review_action = "Append only if zero signals is expected for this scan date."
            notes = (
                f"Scanner produced zero actionable signals for scan_date={summary.get('scan_date', 'unknown')} "
                f"after scanning {summary.get('symbols_scanned', 'unknown')} symbols; "
                f"market_regime={(summary.get('market') or {}).get('regime_label', 'unknown')}; "
                f"v4b_signals={summary.get('v4b_signals', 0)}; vcp_signals={summary.get('vcp_signals', 0)}. "
                "Marked not_applicable after operator confirms zero-signal day is expected."
            )
        else:
            status = "blocked"
            review_action = "Resolve the scanner remediation gap before marking reconciliation complete."
            notes = f"Scanner reconciliation blocked: {primary_gap}. Next action: {remediation.get('next_action')}"
        return {
            "generated_at": datetime.now().isoformat(),
            "suggested_payload": {
                "session": 1,
                "event_date": date.today().isoformat(),
                "workflow_type": "scanner_reconciliation",
                "status": status,
                "symbol": None,
                "notes": notes,
            },
            "review_action": review_action,
            "source_remediation": remediation,
            "guardrails": [
                "This is a suggestion only; the operator must review before appending.",
                "Appending the note does not place orders or change strategy rules.",
                "Use blocked if the scanner output is malformed, stale, or unreconciled.",
            ],
        }

    def paper_day_closeout(self, event_date: date | None = None, session: int | None = None, limit: int = 500) -> dict[str, Any]:
        """Combine daily paper-trading evidence into an end-of-day closeout view."""

        health = self.paper_session_health(event_date=event_date, session=session, limit=limit)
        suggestion = self.scanner_reconciliation_suggestion()
        milestones = self.paper_milestone_tracker(limit=5_000)
        packet = self.paper_review_packet(event_date=event_date, session=session, limit=limit)
        blockers = []
        if health.get("verdict") == "NO_GO":
            blockers.append("Session health has blocked, mismatch, or pending workflow items.")
        if health.get("missing_workflows"):
            blockers.append(f"Missing workflow checks: {', '.join(health.get('missing_workflows', []))}.")
        if suggestion.get("suggested_payload", {}).get("status") == "blocked":
            blockers.append("Scanner reconciliation suggestion is blocked.")
        if milestones.get("verdict") == "NO_GO":
            blockers.append("Paper milestone tracker has unresolved items.")
        if blockers:
            verdict = "NO_GO" if health.get("verdict") == "NO_GO" or milestones.get("verdict") == "NO_GO" else "REVIEW"
        elif health.get("verdict") == "GO":
            verdict = "CLOSED"
        else:
            verdict = "REVIEW"
        export_query = f"limit={limit}"
        if event_date is not None:
            export_query += f"&event_date={event_date.isoformat()}"
        if session is not None:
            export_query += f"&session={session}"
        return {
            "generated_at": datetime.now().isoformat(),
            "event_date": event_date.isoformat() if event_date else None,
            "session": session,
            "verdict": verdict,
            "blockers": blockers,
            "session_health": health,
            "scanner_suggestion": suggestion,
            "milestones": milestones,
            "review_counts": {
                "workflow_count": packet["workflow_count"],
                "paper_event_count": packet["paper_event_count"],
                "audit_event_count": packet["audit_event_count"],
                "blocked_items": len(packet["blocked_items"]),
            },
            "export_links": {
                "workflow_csv": f"/api/db/paper/workflow-events/export.csv?{export_query}",
                "audit_csv": "/api/db/audit/trail/export.csv?limit=500",
                "review_packet_md": f"/api/db/paper/review-packet.md?{export_query}",
            },
            "operator_closeout_steps": [
                "Confirm scanner reconciliation note is appended or intentionally deferred.",
                "Confirm session health has no unexpected missing checks.",
                "Confirm MF sweep and fill-quality evidence are recorded when applicable.",
                "Export the review packet and archive it with the paper-trading notes.",
                "Review milestone progress before ending the session.",
            ],
            "guardrails": [
                "Closeout is evidence review only.",
                "No orders, scanner runs, or MF actions are executed.",
                "No strategy rules or parameters are changed.",
            ],
        }

    def paper_workflow_gap_suggestion(self, event_date: date | None = None, session: int | None = None, limit: int = 500) -> dict[str, Any]:
        """Suggest the next missing closeout workflow note for operator review."""

        health = self.paper_session_health(event_date=event_date, session=session, limit=limit)
        missing = list(health.get("missing_workflows") or [])
        target = missing[0] if missing else None
        event_date_value = event_date or date.today()
        session_value = session if session is not None else 1
        note_templates = {
            "session_checklist": "Session checklist reviewed: scanner state, paper ledger, MF workflow, fill-quality tracking, and closeout exports checked by operator.",
            "mf_sweep": "MF sweep reviewed: idle capital and next-session cash needs checked. Mark not_applicable only if no invest/redeem action is required.",
            "fill_quality": "Fill-quality reviewed: no entry fills required for this session, or fills will be captured separately before closeout.",
        }
        if target is None:
            suggested_payload = None
            review_action = "No missing workflow checks remain for the selected closeout scope."
            status = "complete"
        else:
            suggested_status = "not_applicable" if target in {"mf_sweep", "fill_quality"} else "complete"
            suggested_payload = {
                "session": session_value,
                "event_date": event_date_value.isoformat(),
                "workflow_type": target,
                "status": suggested_status,
                "symbol": None,
                "notes": note_templates.get(target, f"{target} reviewed by operator."),
            }
            review_action = f"Review and append the suggested {target} workflow note if the evidence is correct."
            status = "review"
        return {
            "generated_at": datetime.now().isoformat(),
            "status": status,
            "missing_workflows": missing,
            "suggested_payload": suggested_payload,
            "review_action": review_action,
            "session_health": health,
            "guardrails": [
                "This is a suggestion only; the operator must review before appending.",
                "Use blocked or pending instead if evidence is incomplete.",
                "Appending the note does not place orders, execute MF actions, or change strategy rules.",
            ],
        }

    def paper_review_packet_markdown(self, event_date: date | None = None, session: int | None = None, limit: int = 500) -> str:
        packet = self.paper_review_packet(event_date=event_date, session=session, limit=limit)
        lines = [
            "# Disha Paper Trading Review Packet",
            "",
            f"Generated: {packet['generated_at']}",
            f"Date filter: {packet['event_date'] or 'all'}",
            f"Session filter: {packet['session'] if packet['session'] is not None else 'all'}",
            "",
            "## Summary",
            "",
            f"- Workflow notes: {packet['workflow_count']}",
            f"- Paper events: {packet['paper_event_count']}",
            f"- Audit events: {packet['audit_event_count']}",
            f"- Blocked/mismatch items: {len(packet['blocked_items'])}",
            "",
            "## Workflow Counts",
            "",
        ]
        if packet["workflow_counts"]:
            for key, value in packet["workflow_counts"].items():
                lines.append(f"- {key}: {value}")
        else:
            lines.append("- none")
        lines.extend(["", "## Workflow Notes", ""])
        if packet["workflow_events"]:
            for row in packet["workflow_events"]:
                lines.append(f"- {row.get('event_time')} | session {row.get('session')} | {row.get('workflow_type')} | {row.get('status')} | {row.get('symbol') or '-'} | {row.get('notes')}")
        else:
            lines.append("- none")
        lines.extend(["", "## Recent Audit Events", ""])
        if packet["audit_events"]:
            for row in packet["audit_events"][:25]:
                lines.append(f"- {row.get('event_time')} | {row.get('event_type')} | {row.get('severity')} | {row.get('summary')}")
        else:
            lines.append("- none")
        return "\n".join(lines) + "\n"

    def rows_to_csv(self, rows: list[dict[str, Any]]) -> str:
        frame = pd.DataFrame(rows)
        if frame.empty:
            return ""
        return frame.to_csv(index=False)

    def _fetch_rows(self, table: sa.Table, order_by, limit: int, filters: list[Any] | None = None) -> list[dict[str, Any]]:
        try:
            with self.engine.connect() as connection:
                statement = sa.select(table)
                if filters:
                    statement = statement.where(*filters)
                result = connection.execute(statement.order_by(order_by).limit(limit))
                return [self._jsonable(dict(row)) for row in result.mappings()]
        except Exception as exc:
            raise DishaDatabaseServiceError(f"Unable to read {table.name}: {exc}") from exc

    def _signal_rows(self) -> list[dict[str, Any]]:
        path = self.artifacts.paper / "day0_scanner_dry_run_signals.csv"
        frame = self._read_csv(path)
        rows: list[dict[str, Any]] = []
        for row in frame.to_dict(orient="records"):
            scan_date = self._date(row.get("scan_date"))
            symbol = str(row.get("symbol") or "").strip()
            if not scan_date or not symbol:
                continue
            for sleeve, column in [("V4B", "v4b_entry_signal"), ("VCP", "vcp_entry_signal")]:
                if not self._bool(row.get(column)):
                    continue
                signal_type = f"{sleeve}_BUY"
                rows.append(
                    {
                        "signal_id": self._id("signal", scan_date, symbol, sleeve, signal_type),
                        "scan_date": scan_date,
                        "symbol": symbol,
                        "sleeve": sleeve,
                        "signal_type": signal_type,
                        "entry_signal": True,
                        "market_regime": self._str_or_none(row.get("market_regime")),
                        "market_gate": self._bool_or_none(row.get("vcp_market_gate")),
                        "close_price": self._float_or_none(row.get("close")),
                        "source_file": str(path),
                        "raw_payload": self._jsonable(row),
                    }
                )
        return rows

    def _position_rows(self) -> list[dict[str, Any]]:
        path = self.artifacts.paper / "position_ledger.csv"
        frame = self._read_csv(path)
        rows: list[dict[str, Any]] = []
        for index, row in enumerate(frame.to_dict(orient="records")):
            symbol = str(row.get("symbol") or "").strip()
            if not symbol:
                continue
            trade_id = self._str_or_none(row.get("trade_id"))
            rows.append(
                {
                    "position_id": trade_id or self._id("position", index, symbol, row.get("entry_date")),
                    "trade_id": trade_id,
                    "sleeve": self._str_or_none(row.get("sleeve")),
                    "symbol": symbol,
                    "entry_date": self._date(row.get("entry_date")),
                    "entry_price": self._float_or_none(row.get("entry_price")),
                    "shares": self._int_or_none(row.get("shares")),
                    "planned_exit_date": self._date(row.get("planned_exit_date")),
                    "stop_loss": self._float_or_none(row.get("stop_loss")),
                    "status": self._str_or_none(row.get("status")) or "OPEN",
                    "exit_date": self._date(row.get("exit_date")),
                    "exit_price": self._float_or_none(row.get("exit_price")),
                    "pnl": self._float_or_none(row.get("pnl")),
                    "notes": self._str_or_none(row.get("notes")),
                    "source_file": str(path),
                    "raw_payload": self._jsonable(row),
                }
            )
        return rows

    def _snapshot_rows(self) -> list[dict[str, Any]]:
        path = self.artifacts.paper / "paper_trading_status.json"
        status = self.artifacts.paper_status()
        return [
            {
                "snapshot_id": self._id("snapshot", path, status.get("sessions_logged"), status.get("ready")),
                "snapshot_date": date.today(),
                "sessions_logged": self._int(status.get("sessions_logged")),
                "scanner_reconciliations": self._int(status.get("scanner_reconciliations")),
                "mf_sweep_events": self._int(status.get("mf_sweep_events")),
                "fill_checks": self._int(status.get("fill_checks")),
                "open_positions_logged": self._int(status.get("open_positions_logged")),
                "ready": self._bool(status.get("ready")),
                "source_file": str(path),
                "raw_payload": self._jsonable(status),
            }
        ]

    def _paper_event_rows(self) -> list[dict[str, Any]]:
        files = {
            "paper_trade_log": self.artifacts.paper / "paper_trade_log.csv",
            "mf_sweep_log": self.artifacts.paper / "mf_sweep_log.csv",
            "fill_quality_log": self.artifacts.paper / "fill_quality_log.csv",
            "scanner_reconciliation_log": self.artifacts.paper / "scanner_reconciliation_log.csv",
        }
        rows: list[dict[str, Any]] = []
        for event_type, path in files.items():
            frame = self._read_csv(path)
            for index, row in enumerate(frame.to_dict(orient="records")):
                event_date = self._date(row.get("date") or row.get("order_date") or row.get("scan_date"))
                rows.append(
                    {
                        "event_id": self._id("event", event_type, index, row.get("session"), row.get("date"), row.get("symbol")),
                        "event_date": event_date,
                        "session": self._int_or_none(row.get("session")),
                        "event_type": event_type,
                        "symbol": self._str_or_none(row.get("symbol")),
                        "action": self._str_or_none(row.get("action") or row.get("mf_action")),
                        "status": self._str_or_none(row.get("status") or row.get("settlement_status")),
                        "source_file": str(path),
                        "raw_payload": self._jsonable(row),
                    }
                )
        return rows

    def _read_csv(self, path: Path) -> pd.DataFrame:
        if not path.exists():
            raise DishaReadServiceError(f"missing Disha artifact: {path}")
        return pd.read_csv(path)

    @staticmethod
    def _id(*parts: object) -> str:
        payload = "|".join("" if part is None else str(part) for part in parts)
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _date(value: object) -> date | None:
        if value is None or pd.isna(value) or str(value).strip() == "":
            return None
        return pd.to_datetime(value).date()

    @staticmethod
    def _bool(value: object) -> bool:
        if value is None or pd.isna(value):
            return False
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"true", "1", "y", "yes"}

    @staticmethod
    def _bool_or_none(value: object) -> bool | None:
        if value is None or pd.isna(value) or str(value).strip() == "":
            return None
        return DishaDatabaseService._bool(value)

    @staticmethod
    def _int(value: object) -> int:
        return DishaDatabaseService._int_or_none(value) or 0

    @staticmethod
    def _int_or_none(value: object) -> int | None:
        if value is None or pd.isna(value) or str(value).strip() == "":
            return None
        return int(float(value))

    @staticmethod
    def _float_or_none(value: object) -> float | None:
        if value is None or pd.isna(value) or str(value).strip() == "":
            return None
        return float(value)

    @staticmethod
    def _str_or_none(value: object) -> str | None:
        if value is None or pd.isna(value):
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _jsonable(value: Any) -> Any:
        if isinstance(value, dict):
            return {str(key): DishaDatabaseService._jsonable(item) for key, item in value.items()}
        if isinstance(value, list):
            return [DishaDatabaseService._jsonable(item) for item in value]
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if value is None:
            return None
        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            pass
        if hasattr(value, "item"):
            return value.item()
        return value


def create_tables_for_tests(engine: Engine) -> None:
    """Create Disha tables without running the whole application migration chain."""

    create_disha_tables(engine)
