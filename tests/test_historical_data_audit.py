from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.research.historical_data_audit import run_historical_data_audit
from db.base import Base
from db.models import PricesDaily, SymbolMaster, UniverseSnapshot


def build_session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)


def test_historical_data_audit_reports_coverage_gaps_and_discontinuities():
    factory = build_session_factory()
    with factory() as session:
        session.add_all(
            [
                SymbolMaster(symbol="AAA", nse500=True),
                SymbolMaster(symbol="BBB", nse500=True),
                SymbolMaster(symbol="CCC", nse500=True),
                UniverseSnapshot(date=date(2026, 6, 1), symbol="AAA", index_name="NSE500"),
                UniverseSnapshot(date=date(2026, 6, 1), symbol="BBB", index_name="NSE500"),
                UniverseSnapshot(date=date(2026, 6, 1), symbol="CCC", index_name="NSE500"),
            ]
        )
        session.commit()

    with factory() as session:
        start = date(2024, 1, 1)
        session.add_all(
            PricesDaily(symbol="AAA", date=start + timedelta(days=offset), open=100, high=110, low=90, close=100, volume=1000)
            for offset in range(10)
        )
        session.add_all(
            [
                PricesDaily(symbol="BBB", date=start, open=100, high=110, low=90, close=100, volume=1000),
                PricesDaily(symbol="BBB", date=start + timedelta(days=1), open=48, high=55, low=45, close=50, volume=1000),
            ]
        )
        session.commit()

    audit = run_historical_data_audit(factory, min_years=5, discontinuity_threshold_pct=40.0)

    assert audit.current_daily.symbols_expected == 3
    assert audit.current_daily.symbols_with_prices == 2
    assert audit.missing_price_symbols == ["CCC"]
    assert audit.sparse_price_symbols[0]["symbol"] == "BBB"
    assert audit.corporate_action_candidates[0]["symbol"] == "BBB"
    assert audit.source_15min is None
    assert "Freeze Swing V2.1 logic" in audit.etl_plan[0]
