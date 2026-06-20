from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.main import app, get_trade_analysis_service
from app.api.trade_analysis_service import (
    AnalysisPosition,
    TradeAnalysisRequest,
    TradeAnalysisValidationError,
    financial_year_returns,
    mark_price,
    nth_trading_day_after,
    positions_value,
    render_weekly_equity_svg,
    reconstruct_trades,
    validate_request,
    weekly_equity_curve,
    zerodha_default_charges,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def trading_dates(count: int) -> list[date]:
    cursor = date(2026, 1, 5)
    dates: list[date] = []
    while len(dates) < count:
        if cursor.weekday() < 5:
            dates.append(cursor)
        cursor += timedelta(days=1)
    return dates


def price_series(symbol: str, dates: list[date]) -> dict[str, dict[date, dict[str, float]]]:
    return {
        symbol: {
            item: {
                "open": 100.0 + index,
                "high": 101.0 + index,
                "low": 99.0 + index,
                "close": 100.5 + index,
            }
            for index, item in enumerate(dates)
        }
    }


def test_trade_analysis_parameter_validation():
    with pytest.raises(TradeAnalysisValidationError):
        validate_request(
            TradeAnalysisRequest(
                start_date=date(2026, 2, 1),
                end_date=date(2026, 1, 1),
                strategy="TOP5_WEEKLY",
                initial_capital=1_000_000,
            )
        )

    with pytest.raises(TradeAnalysisValidationError):
        validate_request(
            TradeAnalysisRequest(
                start_date=date(2026, 1, 1),
                end_date=date(2026, 2, 1),
                strategy="TOP5_WEEKLY",
                initial_capital=0,
            )
        )


def test_zerodha_charge_model_produces_expected_components():
    charges = zerodha_default_charges(100_000, 110_000)

    assert charges["brokerage"] == pytest.approx(0)
    assert charges["STT"] == pytest.approx(210)
    assert charges["stamp_duty"] == pytest.approx(15)
    assert charges["charges"] > charges["STT"]


def test_reconstruct_trades_calculates_pnl_and_charges():
    dates = trading_dates(30)
    recommendations = [
        {
            "date": dates[0],
            "rank": 1,
            "symbol": "AAA",
            "score": 80.0,
            "sector": "IT",
        }
    ]
    request = TradeAnalysisRequest(
        start_date=dates[0],
        end_date=dates[-1],
        strategy="TOP5_WEEKLY",
        initial_capital=100_000,
    )

    result = reconstruct_trades(request, recommendations, price_series("AAA", dates))
    trade = result["trades"][0]

    assert result["summary"]["total_trades"] == 1
    assert trade["symbol"] == "AAA"
    assert trade["holding_days"] == 20
    assert trade["gross_pnl"] > 0
    assert trade["charges"] > 0
    assert trade["net_pnl"] < trade["gross_pnl"]
    assert result["summary"]["net_pnl"] == pytest.approx(trade["gross_pnl"] - trade["charges"])
    assert result["summary"]["total_return"] == pytest.approx(result["summary"]["net_pnl"] / 100_000)
    assert result["summary"]["ending_value"] == pytest.approx(100_000 + result["summary"]["net_pnl"])


def test_positions_value_carries_forward_latest_close_for_missing_mark_date():
    dates = trading_dates(3)
    position = AnalysisPosition(
        symbol="AAA",
        sector="IT",
        signal_date=dates[0],
        entry_date=dates[0],
        entry_price=100.0,
        quantity=10.0,
        planned_exit_date=dates[-1],
        rank=1,
        score=80.0,
        entry_value=1000.0,
        buy_charges={"charges": 0.0},
    )
    prices = {
        "AAA": {
            dates[0]: {"open": 100.0, "close": 101.0},
            dates[2]: {"open": 103.0, "close": 104.0},
        }
    }

    assert mark_price(prices, "AAA", dates[1], "close") == pytest.approx(101.0)
    assert positions_value([position], prices, dates[1], "close") == pytest.approx(1010.0)


def test_exit_date_excludes_special_session_and_counts_entry_as_day_one():
    sessions = [date(2024, 4, 23) + timedelta(days=index) for index in range(45)]
    sessions = [item for item in sessions if item.weekday() < 5 or item == date(2024, 5, 18)]
    sessions = sorted(sessions)
    regular = [item for item in sessions if item != date(2024, 5, 18)]

    assert nth_trading_day_after(sessions, regular[0], 20) == regular[19]
    assert nth_trading_day_after(sessions, date(2024, 5, 18), 20) is None


def test_reconstruct_trades_blocks_same_day_reentry_after_planned_exit():
    dates = trading_dates(45)
    recommendations = [
        {"date": dates[0], "rank": 1, "symbol": "AAA", "score": 80.0, "sector": "IT"},
        {"date": dates[19], "rank": 1, "symbol": "AAA", "score": 82.0, "sector": "IT"},
    ]
    request = TradeAnalysisRequest(
        start_date=dates[0],
        end_date=dates[-1],
        strategy="TOP5_WEEKLY",
        initial_capital=100_000,
    )

    result = reconstruct_trades(request, recommendations, price_series("AAA", dates))

    assert len(result["trades"]) == 1
    assert result["trades"][0]["exit_date"] == dates[20].isoformat()


def test_weekly_equity_curve_and_svg_are_generated():
    rows = [
        {"date": "2026-01-05", "equity": 100000.0},
        {"date": "2026-01-09", "equity": 101000.0},
        {"date": "2026-01-12", "equity": 102000.0},
    ]

    weekly = weekly_equity_curve(rows)
    svg = render_weekly_equity_svg(weekly)

    assert len(weekly) == 2
    assert weekly[0]["equity"] == pytest.approx(101000)
    assert weekly[1]["weekly_return"] == pytest.approx(102000 / 101000 - 1)
    assert "<svg" in svg
    assert "Weekly Equity Curve" in svg


def test_financial_year_returns_use_april_to_march_boundaries():
    rows = [
        {"date": "2023-03-31", "equity": 100000.0},
        {"date": "2023-04-03", "equity": 105000.0},
        {"date": "2024-03-28", "equity": 126000.0},
        {"date": "2024-04-01", "equity": 120000.0},
        {"date": "2024-06-28", "equity": 132000.0},
    ]

    returns = financial_year_returns(rows)

    assert [row["financial_year"] for row in returns] == ["FY2022-23", "FY2023-24", "FY2024-25"]
    assert returns[0]["return_pct"] == pytest.approx(0.0)
    assert returns[1]["return_pct"] == pytest.approx(126000 / 105000 - 1)
    assert returns[2]["return_pct"] == pytest.approx(132000 / 120000 - 1)


class FakeTradeAnalysisService:
    def run(self, request: TradeAnalysisRequest):
        return {
            "report_id": "report_1",
            "status": "completed",
            "summary": {"total_return": 0.1, "total_trades": 3},
            "artifacts": {"trades_csv": "reports/trade_analysis/report_1/trades.csv"},
        }

    def get(self, report_id: str):
        return {
            "report_id": report_id,
            "status": "completed",
            "summary": {"total_return": 0.1},
            "artifacts": {},
        }


def test_trade_analysis_api_run_and_get(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///research-test.db")
    monkeypatch.setenv("ANGEL_DATABASE_URL", "sqlite:///angel-test.db")
    monkeypatch.setenv("PAPER_PORTFOLIO_ID", "1")
    app.dependency_overrides[get_trade_analysis_service] = lambda: FakeTradeAnalysisService()
    client = TestClient(app)

    response = client.post(
        "/research/trade-analysis/run",
        json={
            "start_date": "2026-01-01",
            "end_date": "2026-02-01",
            "strategy": "TOP5_WEEKLY",
            "initial_capital": 1000000,
            "charge_model": "ZERODHA_DEFAULT",
        },
    )
    assert response.status_code == 200
    assert response.json()["report_id"] == "report_1"

    lookup = client.get("/research/trade-analysis/report_1")
    assert lookup.status_code == 200
    assert lookup.json()["status"] == "completed"

    app.dependency_overrides.pop(get_trade_analysis_service, None)


def test_trade_analysis_frontend_page_wires_api_and_controls():
    source = (REPO_ROOT / "frontend" / "app" / "research" / "trade-analysis" / "page.tsx").read_text(encoding="utf-8")

    assert "/research/trade-analysis/run" in source
    assert "SECTOR_ROTATION_ADX_ROLLING10" in source
    assert "SectorEdge 10" in source
    assert "Generate Trade Analysis" in source
    assert "trades.csv" in source
    assert "summary.md" in source
    assert "financial_year_returns" in source
    assert "financial_year_returns.csv" in source


def test_rolling_portfolio_frontend_page_wires_api_and_controls():
    source = (REPO_ROOT / "frontend" / "app" / "research" / "rolling-portfolio" / "page.tsx").read_text(encoding="utf-8")
    nav = (REPO_ROOT / "frontend" / "components" / "SidebarNav.tsx").read_text(encoding="utf-8")

    assert "/research/rolling-portfolio/simulate" in source
    assert "/research/rolling-portfolio/defaults" in source
    assert "Next Week" in source
    assert "Run From Date" in source
    assert "Step through SectorEdge 10" in source
    assert "financial_year_returns" in source
    assert "Weekly Recommendation Log" in source
    assert "Open Positions" in source
    assert "/research/rolling-portfolio" in nav
