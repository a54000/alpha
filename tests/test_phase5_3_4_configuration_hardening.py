from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app.api.dashboard_service import CockpitConfigurationError, CockpitDatabaseError, CockpitReadService
from db.base import Base
from db.models import IndexPricesDaily, PaperDailySnapshot, PaperPortfolio, PaperPosition


def memory_engine():
    return create_engine(
        "sqlite+pysqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def test_missing_env_configuration_fails_clearly(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("ANGEL_DATABASE_URL", raising=False)
    monkeypatch.delenv("PAPER_PORTFOLIO_ID", raising=False)

    with pytest.raises(CockpitConfigurationError, match="DATABASE_URL, ANGEL_DATABASE_URL, PAPER_PORTFOLIO_ID"):
        CockpitReadService()


def test_database_failure_is_not_converted_to_empty_success():
    research = memory_engine()
    angel = memory_engine()
    service = CockpitReadService(
        research_database_url="sqlite+pysqlite:///research.db",
        angel_database_url="sqlite+pysqlite:///angel.db",
        paper_portfolio_id=1,
        research_engine=research,
        angel_engine=angel,
    )

    with pytest.raises(CockpitDatabaseError):
        service.latest_recommendations()


def test_health_reports_successful_connections_and_portfolio():
    research = memory_engine()
    angel = memory_engine()
    with research.begin() as connection:
        connection.execute(text("CREATE TABLE paper_portfolios (portfolio_id integer primary key, status text)"))
        connection.execute(text("INSERT INTO paper_portfolios (portfolio_id, status) VALUES (1, 'active')"))

    service = CockpitReadService(
        research_database_url="sqlite+pysqlite:///research.db",
        angel_database_url="sqlite+pysqlite:///angel.db",
        paper_portfolio_id=1,
        research_engine=research,
        angel_engine=angel,
    )

    payload = service.health()

    assert payload["status"] == "ok"
    assert payload["research_db"]["connected"] is True
    assert payload["angel_db"]["connected"] is True
    assert payload["paper_portfolio"]["configured"] is True
    assert payload["paper_portfolio"]["exists"] is True


def test_dashboard_benchmark_uses_nifty500_return_since_first_trade():
    research = memory_engine()
    angel = memory_engine()
    Base.metadata.create_all(research)
    with research.begin() as connection:
        connection.execute(
            PaperPortfolio.__table__.insert(),
            {
                "portfolio_id": 1,
                "name": "Swing V2.1 Rolling 10 Slot Paper",
                "strategy": "swing_v2_1_rolling_10_slot",
                "portfolio_size": 10,
                "initial_capital": 1_000_000,
                "cash": 1_000_000,
                "current_nav": 1_050_000,
                "benchmark_symbol": "NIFTY500",
                "status": "active",
            },
        )
        connection.execute(
            PaperDailySnapshot.__table__.insert(),
            [
                {
                    "portfolio_id": 1,
                    "date": date(2026, 6, 15),
                    "cash": 1_000_000,
                    "market_value": 0,
                    "nav": 1_000_000,
                    "realized_pnl": 0,
                    "unrealized_pnl": 0,
                    "turnover": 0,
                    "benchmark_close": None,
                    "benchmark_return": None,
                    "open_positions": 0,
                },
                {
                    "portfolio_id": 1,
                    "date": date(2026, 6, 18),
                    "cash": 950_000,
                    "market_value": 100_000,
                    "nav": 1_050_000,
                    "realized_pnl": 0,
                    "unrealized_pnl": 50_000,
                    "turnover": 0,
                    "benchmark_close": None,
                    "benchmark_return": None,
                    "open_positions": 1,
                },
            ],
        )
        connection.execute(
            PaperPosition.__table__.insert(),
            {
                "portfolio_id": 1,
                "symbol": "ABC",
                "sector": "Test",
                "entry_date": date(2026, 6, 15),
                "entry_price": 100,
                "quantity": 10,
                "capital_allocated": 1_000,
                "status": "open",
            },
        )
        connection.execute(
            IndexPricesDaily.__table__.insert(),
            [
                {"index_name": "NIFTY500", "date": date(2026, 6, 15), "close": 20_000},
                {"index_name": "NIFTY500", "date": date(2026, 6, 18), "close": 21_000},
            ],
        )

    service = CockpitReadService(
        research_database_url="sqlite+pysqlite:///research.db",
        angel_database_url="sqlite+pysqlite:///angel.db",
        paper_portfolio_id=1,
        research_engine=research,
        angel_engine=angel,
    )

    payload = service.portfolio()

    assert payload["benchmark"]["symbol"] == "NIFTY500"
    assert payload["benchmark"]["return"] == pytest.approx(0.05)
    assert payload["benchmark"]["return_start_date"] == "2026-06-15"
    assert payload["benchmark"]["latest_available_date"] == "2026-06-18"
    assert payload["benchmark"]["nav_return"] == pytest.approx(0.05)
