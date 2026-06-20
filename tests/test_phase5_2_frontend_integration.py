from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_frontend_pages_use_required_api_endpoints():
    expected = {
        "frontend/app/page.tsx": "/dashboard",
        "frontend/app/recommendations/page.tsx": "/recommendations/latest",
        "frontend/app/recommendations/[symbol]/explanation/page.tsx": "/recommendations/",
        "frontend/app/portfolio/page.tsx": "/portfolio",
        "frontend/app/operations/page.tsx": "/pipeline/status",
        "frontend/app/research/page.tsx": "/research/metrics",
    }

    for path, endpoint in expected.items():
        source = read(path)
        assert endpoint in source
        assert "safeApiGet" in source


def test_frontend_has_loading_error_and_empty_states():
    assert "LoadingState" in read("frontend/app/loading.tsx")
    state_panel = read("frontend/components/StatePanel.tsx")
    assert "ErrorState" in state_panel
    assert "EmptyState" in state_panel

    for path in [
        "frontend/app/page.tsx",
        "frontend/app/recommendations/page.tsx",
        "frontend/app/recommendations/[symbol]/explanation/page.tsx",
        "frontend/app/portfolio/page.tsx",
        "frontend/app/operations/page.tsx",
        "frontend/app/research/page.tsx",
    ]:
        source = read(path)
        assert "ErrorState" in source
        assert "EmptyState" in source


def test_dashboard_morning_brief_uses_existing_apis():
    dashboard = read("frontend/app/page.tsx")
    card = read("frontend/components/DataStatusCard.tsx")

    assert "Good morning" in dashboard
    assert "NIFTY 500 return" in dashboard
    assert "return_start_date" in dashboard
    assert "System and pipeline status" in dashboard
    assert "/dashboard" in dashboard
    assert "/pipeline/status" in dashboard
    assert "/recommendations/latest" in dashboard
    assert "latest_candle_at" in dashboard
    assert "latest_recommendation_date" in dashboard
    assert "latestPipelineRun" in card
    assert "All current" in card
    assert "Pipeline delayed" in card
    assert "Stale data" in card
