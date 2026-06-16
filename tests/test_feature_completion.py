from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.indicators.compute_features import (
    FeatureComputer,
    compute_rs_rank_pct,
    compute_stochastic,
)
from db.base import Base
from db.models import FeaturesDaily, PricesDaily, SymbolMaster


def build_session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)


def seed_symbol_prices(factory, symbol: str, *, start: date, day_count: int, close_step: float):
    with factory() as session:
        if session.get(SymbolMaster, symbol) is None:
            session.add(SymbolMaster(symbol=symbol, sector="TEST"))
            session.flush()
        for offset in range(day_count):
            trading_date = start + timedelta(days=offset)
            close = 100 + offset * close_step
            session.add(
                PricesDaily(
                    symbol=symbol,
                    date=trading_date,
                    open=close,
                    high=close + 1,
                    low=close - 1,
                    close=close,
                    volume=1_000_000,
                )
            )
        session.commit()


def test_compute_stochastic_returns_k_and_d():
    index = pd.date_range("2024-01-01", periods=30, freq="D")
    high = pd.Series(range(110, 140), index=index, dtype="float64")
    low = pd.Series(range(90, 120), index=index, dtype="float64")
    close = pd.Series(range(100, 130), index=index, dtype="float64")

    stoch_k, stoch_d = compute_stochastic(high, low, close)
    assert stoch_k.notna().any()
    assert stoch_d.notna().any()


def test_compute_rs_rank_pct_orders_symbols():
    ranks = compute_rs_rank_pct(pd.Series({"A": 0.10, "B": 0.05, "C": 0.20}))
    assert ranks["C"] > ranks["A"] > ranks["B"]
    assert ranks.min() >= 0
    assert ranks.max() <= 100


def test_feature_completion_populates_required_scoring_fields():
    factory = build_session_factory()
    start = date(2024, 1, 1)
    seed_symbol_prices(factory, "ABC", start=start, day_count=260, close_step=0.5)

    report = FeatureComputer(factory).generate(end_date=date(2024, 9, 16))
    assert report.rows_written > 0

    with factory() as session:
        row = session.execute(
            select(FeaturesDaily).where(FeaturesDaily.symbol == "ABC", FeaturesDaily.date == date(2024, 9, 16))
        ).scalar_one()

        assert row.ema_5 is not None
        assert row.ema_13 is not None
        assert row.ema_150 is not None
        assert row.adx_prev is not None
        assert row.macd_hist_prev is not None
        assert row.stoch_k is not None
        assert row.stoch_d is not None
        assert row.bb_width_20avg is not None


def test_rs_rank_pct_generated_cross_sectionally():
    factory = build_session_factory()
    start = date(2024, 1, 1)
    seed_symbol_prices(factory, "FAST", start=start, day_count=260, close_step=1.0)
    seed_symbol_prices(factory, "MID", start=start, day_count=260, close_step=0.5)
    seed_symbol_prices(factory, "SLOW", start=start, day_count=260, close_step=0.1)

    FeatureComputer(factory).generate(end_date=date(2024, 9, 16))

    with factory() as session:
        rows = session.execute(
            select(FeaturesDaily.symbol, FeaturesDaily.rs_rank_pct, FeaturesDaily.rs_vs_nifty_20d).where(
                FeaturesDaily.date == date(2024, 9, 16)
            )
        ).all()
        assert len(rows) == 3
        assert all(row.rs_rank_pct is not None for row in rows)

        ranked = sorted(rows, key=lambda row: float(row.rs_vs_nifty_20d))
        assert float(ranked[-1].rs_rank_pct) > float(ranked[0].rs_rank_pct)


def test_feature_completion_empty_state_returns_zero_rows():
    factory = build_session_factory()
    report = FeatureComputer(factory).generate()
    assert report.symbols_processed == 0
    assert report.rows_written == 0
