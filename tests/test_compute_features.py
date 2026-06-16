from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from db.base import Base
from db.models import FeaturesDaily, PricesDaily, SymbolMaster
from app.indicators.compute_features import FeatureComputer, FeatureGenerationReport, write_feature_report


def build_session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)


def seed_prices(factory):
    with factory() as session:
        session.add(SymbolMaster(symbol="ABC"))
        session.commit()
        start = date(2024, 1, 1)
        for offset in range(260):
            trading_date = start + timedelta(days=offset)
            session.add(
                PricesDaily(
                    symbol="ABC",
                    date=trading_date,
                    open=100 + offset * 0.5,
                    high=101 + offset * 0.5,
                    low=99 + offset * 0.5,
                    close=100 + offset * 0.5,
                    volume=1000 + offset,
                )
            )
        session.commit()


def test_compute_features_populates_features_daily():
    factory = build_session_factory()
    seed_prices(factory)

    computer = FeatureComputer(factory)
    report = computer.generate(end_date=date(2024, 9, 16))

    assert report.rows_written > 0
    assert report.symbols_processed == 1

    with factory() as session:
        row = session.execute(
            select(FeaturesDaily).where(FeaturesDaily.symbol == "ABC", FeaturesDaily.date == date(2024, 9, 16))
        ).scalar_one()
        assert row.ema_5 is not None
        assert row.ema_13 is not None
        assert row.ema_20 is not None
        assert row.ema_50 is not None
        assert row.ema_150 is not None
        assert row.ema_200 is not None
        assert row.adx_prev is not None
        assert row.macd_hist_prev is not None
        assert row.stoch_k is not None
        assert row.stoch_d is not None
        assert row.bb_width_20avg is not None
        assert row.rs_rank_pct is not None
        assert row.rsi_14 is not None
        assert row.macd_line is not None
        assert row.macd_signal is not None
        assert row.adx_14 is not None
        assert row.atr_14 is not None
        assert row.bb_width is not None
        assert row.volume_ratio is not None
        assert row.rs_vs_nifty_20d is not None
        assert row.rs_vs_nifty_60d is not None
        assert row.distance_from_52w_high is not None
        assert row.is_52w_breakout in (True, False)
        assert row.is_eligible in (True, False)


def test_compute_features_is_idempotent():
    factory = build_session_factory()
    seed_prices(factory)

    computer = FeatureComputer(factory)
    first = computer.generate(end_date=date(2024, 9, 16))
    second = computer.generate(end_date=date(2024, 9, 16))

    assert second.rows_written == 0
    assert first.rows_written > 0

    with factory() as session:
        count = session.query(FeaturesDaily).count()
        assert count == first.rows_written


def test_compute_features_supports_incremental_recalculation():
    factory = build_session_factory()
    seed_prices(factory)
    computer = FeatureComputer(factory)
    computer.generate(end_date=date(2024, 9, 16))

    with factory() as session:
        session.add(
            PricesDaily(
                symbol="ABC",
                date=date(2024, 10, 1),
                open=200,
                high=205,
                low=198,
                close=204,
                volume=5000,
            )
        )
        session.commit()

    report = computer.generate(start_date=date(2024, 10, 1), end_date=date(2024, 10, 1))
    assert report.rows_written == 1


def test_write_feature_report(tmp_path):
    report = FeatureGenerationReport(symbols_processed=1, rows_written=2, failures=[], missing_data_summary={"abc": 1})
    path = write_feature_report(report, tmp_path / "feature_report.json")
    assert path.exists()
