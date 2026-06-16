from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app.api.dashboard_service import CockpitConfigurationError, CockpitDatabaseError, CockpitReadService


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
