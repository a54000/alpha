from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_report_module():
    name = "generate_daily_paper_report"
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_compute_drawdown_uses_latest_nav_against_prior_peak():
    report = load_report_module()

    drawdown = report.compute_drawdown(
        [
            {"date": date(2026, 1, 1), "nav": 100_000},
            {"date": date(2026, 1, 2), "nav": 110_000},
            {"date": date(2026, 1, 3), "nav": 99_000},
        ]
    )

    assert round(drawdown, 4) == -0.1


def test_sector_concentration_calculates_max_weight():
    report = load_report_module()

    weights, max_weight = report.sector_concentration(
        [
            {"sector": "IT", "market_value": 60_000},
            {"sector": "Energy", "market_value": 40_000},
        ]
    )

    assert weights == {"IT": 0.6, "Energy": 0.4}
    assert max_weight == 0.6


def test_alerts_cover_missing_data_zero_recommendations_concentration_and_drawdown():
    report = load_report_module()

    alerts = report.build_alerts(
        freshness={"stale_days": 3},
        quality={"available": True, "invalid_ohlc_rows": 1, "zero_volume_rows": 2},
        recommendations={"available": True, "recommendation_count": 0},
        risk={"current_drawdown": -0.12, "max_sector_weight": 0.55},
        drawdown_alert=-0.10,
        concentration_alert=0.40,
        recommendation_low_alert=3,
        recommendation_high_alert=20,
    )

    categories = {alert.category for alert in alerts}
    assert "missing_data" in categories
    assert "invalid_ohlc" in categories
    assert "zero_volume" in categories
    assert "zero_recommendations" in categories
    assert "drawdown_threshold" in categories
    assert "excessive_concentration" in categories


def test_render_report_contains_required_sections():
    report = load_report_module()

    markdown = report.render_report(
        report_date=date(2026, 6, 12),
        pipeline={"cycle_report": {"summary": {"status": "success"}}, "feature_report": {}, "recommendation_report": {}},
        sync={"last_success_at": "2026-06-12T10:00:00Z"},
        freshness={"latest_candle_at": "2026-06-12T15:30:00Z", "latest_candle_date": date(2026, 6, 12)},
        quality={"invalid_ohlc_rows": 0, "zero_volume_rows": 0},
        portfolio={"available": False},
        risk={"current_drawdown": None, "exposure": None, "max_sector_weight": 0.0, "turnover": 0.0, "turnover_pct_nav": None, "sector_weights": {}},
        recommendations={"available": True, "recommendation_count": 5, "average_score": 80.0, "min_score": 70.0, "max_score": 90.0, "rows": []},
        alerts=[],
    )

    assert "## Pipeline Status" in markdown
    assert "## Portfolio Status" in markdown
    assert "## Risk Metrics" in markdown
    assert "## Strategy Health" in markdown
    assert "## Benchmark Comparison" in markdown
