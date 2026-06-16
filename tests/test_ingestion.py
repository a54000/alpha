from __future__ import annotations

from datetime import date

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from db.base import Base
from db.models import DataQualityLog, PricesDaily, SymbolMaster, UniverseSnapshot
from app.ingestion.symbol_loader import SymbolLoader, ConstituentRecord
from app.ingestion.price_loader import PriceLoader, PriceBar
from app.ingestion.data_validator import DataValidator


def build_engine():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return engine


def build_session_factory():
    return sessionmaker(bind=build_engine(), future=True)


def test_symbol_loader_upserts_symbols_and_snapshots():
    factory = build_session_factory()
    loader = SymbolLoader(factory)
    records = [
        ConstituentRecord(symbol="ABC", company_name="ABC Ltd", sector="IT", subsector="Software"),
        ConstituentRecord(symbol="XYZ", company_name="XYZ Ltd", sector="Banks", subsector="Private"),
    ]

    result = loader.load(date(2024, 1, 2), records)
    assert result.symbols_loaded == 2
    assert result.snapshot_rows_loaded == 2

    second = loader.load(date(2024, 1, 2), records)
    assert second.symbols_loaded == 0
    assert second.snapshot_rows_loaded == 0

    with factory() as session:
        assert session.execute(select(SymbolMaster)).all()
        assert session.execute(select(UniverseSnapshot)).all()


def test_price_loader_upserts_without_duplicates():
    factory = build_session_factory()
    loader = PriceLoader(factory, price_fetcher=lambda symbol, start, end: [
        PriceBar(symbol=symbol, date=date(2024, 1, 2), open=100, high=110, low=95, close=105, volume=1000),
        PriceBar(symbol=symbol, date=date(2024, 1, 3), open=105, high=112, low=101, close=108, volume=1200),
    ])

    with factory() as session:
        session.add(SymbolMaster(symbol="ABC"))
        session.commit()

    first = loader.load(date(2024, 1, 2), date(2024, 1, 3), ["ABC"])
    second = loader.load(date(2024, 1, 2), date(2024, 1, 3), ["ABC"])
    assert first.rows_loaded == 2
    assert second.rows_loaded == 0

    with factory() as session:
        rows = session.execute(select(PricesDaily)).all()
        assert len(rows) == 2


def test_data_validator_logs_problems():
    factory = build_session_factory()
    validator = DataValidator(factory)

    with factory() as session:
        session.add(SymbolMaster(symbol="ABC"))
        session.commit()
    with factory() as session:
        session.add(PricesDaily(symbol="ABC", date=date(2024, 1, 2), open=100, high=110, low=95, close=105, volume=0))
        session.commit()

    result = validator.validate_prices(date(2024, 1, 2), ["ABC"])
    assert result.zero_volume_count == 1
    assert result.invalid_price_count == 0
    assert result.duplicate_count == 0

    with factory() as session:
        assert session.query(DataQualityLog).count() == 1
