"""Tests for Phase 6.5C sector factor research."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.research.sector_factor_analysis import SectorFactorAnalyzer
from db.base import Base
from db.models import FeaturesDaily, PricesDaily, SectorDaily, SymbolMaster


def build_session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)


def seed_symbol_prices(session, symbol: str, sector: str, start: date, daily_return: float) -> None:
    session.add(SymbolMaster(symbol=symbol, sector=sector))
    session.flush()
    close = 100.0
    for offset in range(20):
        current_date = start + timedelta(days=offset)
        session.add(
            PricesDaily(
                symbol=symbol,
                date=current_date,
                open=close,
                high=close,
                low=close,
                close=close,
                volume=1000,
            )
        )
        if offset < 10:
            session.add(FeaturesDaily(symbol=symbol, date=current_date, sector=sector))
        close *= 1.0 + daily_return


def seed_sector_rows(session, start: date) -> None:
    for offset in range(10):
        current_date = start + timedelta(days=offset)
        session.add(
            SectorDaily(
                date=current_date,
                sector="Leaders",
                rank_3m=1,
                sector_return_1m=0.08,
                sector_return_3m=0.18,
                sector_return_6m=0.30,
            )
        )
        session.add(
            SectorDaily(
                date=current_date,
                sector="Laggards",
                rank_3m=2,
                sector_return_1m=-0.03,
                sector_return_3m=-0.08,
                sector_return_6m=-0.12,
            )
        )


def test_sector_factor_analyzer_runs_sector_daily_factor():
    factory = build_session_factory()
    start = date(2024, 1, 1)
    with factory() as session:
        seed_symbol_prices(session, "AAA.NS", "Leaders", start, daily_return=0.02)
        seed_symbol_prices(session, "BBB.NS", "Laggards", start, daily_return=-0.01)
        seed_sector_rows(session, start)
        session.commit()

    analyzer = SectorFactorAnalyzer(factory)
    results = analyzer.run(["sector_return_3m"], [5], start, start + timedelta(days=9))

    result = results["sector_return_3m"]["5d"]
    assert result.factor_name == "sector_return_3m"
    assert result.horizon == "5d"
    assert result.sample_size == 20
    assert result.spearman_ic is not None
    assert result.bucket_spread is not None
    assert result.monotonicity_score is not None
    assert result.buckets


def test_sector_factor_analyzer_rejects_unknown_factor():
    analyzer = SectorFactorAnalyzer(build_session_factory())

    with pytest.raises(ValueError, match="Unsupported sector factor"):
        analyzer.run(["unknown_factor"], [5], date(2024, 1, 1), date(2024, 1, 31))
