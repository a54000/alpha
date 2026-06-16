from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "frontend" / "components" / "DishaDashboard.tsx"


def _dashboard_source() -> str:
    return DASHBOARD.read_text(encoding="utf-8")


def test_disha_paper_ops_dashboard_sections_are_present():
    source = _dashboard_source()

    required_sections = [
        "Paper Operations Status",
        "Paper Day Workflow Capture",
        "Day 1 Launch Checklist",
        "Scanner Readiness Remediation",
        "Scanner Rerun Runbook",
        "Scanner Reconciliation Assistant",
        "Paper Day Closeout",
        "Paper Workflow Gap Assistant",
        "Paper Session Health",
        "Paper Milestone Tracker",
        "Paper Review Exports",
    ]

    for section in required_sections:
        assert section in source


def test_disha_paper_ops_status_strip_uses_hydration_safe_text_blocks():
    source = _dashboard_source()
    start = source.index('title="Paper Operations Status"')
    end = source.index('title="Production CAGR"', start)
    status_strip = source[start:end]

    assert "Active Scope</Typography.Text>" in status_strip
    assert "Last Scoped Refresh</Typography.Text>" in status_strip
    assert "Next Workflow</Typography.Text>" in status_strip
    assert '<Statistic title="Active Scope"' not in status_strip
    assert '<Statistic title="Last Scoped Refresh"' not in status_strip
    assert '<Statistic title="Next Workflow"' not in status_strip


def test_disha_workflow_append_refreshes_dependent_paper_widgets():
    source = _dashboard_source()

    assert "refreshPaperDerivedState" in source
    assert "await refreshPaperDerivedState();" in source
    assert "/api/db/paper/session-health" in source
    assert "/api/db/paper/milestones" in source
    assert "/api/db/paper/day-closeout" in source
    assert "/api/db/paper/workflow-gap-suggestion" in source
    assert "/api/db/scanner/reconciliation-suggestion" in source
