from __future__ import annotations

from datetime import date

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from db.base import Base
from db.models import IndexPricesDaily
from app.loaders.index_loader import IndexLoader, IndexPriceBar, INDEX_SYMBOL_MAP


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


def test_index_symbol_map():
    """Test that NIFTY500 maps to correct yfinance ticker."""
    assert INDEX_SYMBOL_MAP["NIFTY500"] == "^CRSLDX"


def test_index_loader_upserts_without_duplicates():
    factory = build_session_factory()
    loader = IndexLoader(factory, index_fetcher=lambda index_name, start, end: [
        IndexPriceBar(index_name=index_name, date=date(2024, 1, 2), open=100, high=110, low=95, close=105, volume=1000),
        IndexPriceBar(index_name=index_name, date=date(2024, 1, 3), open=105, high=112, low=101, close=108, volume=1200),
    ])

    first = loader.load(date(2024, 1, 2), date(2024, 1, 3), ["NIFTY500"])
    second = loader.load(date(2024, 1, 2), date(2024, 1, 3), ["NIFTY500"])
    assert first.rows_loaded == 2
    assert second.rows_loaded == 0

    with factory() as session:
        rows = session.execute(select(IndexPricesDaily)).all()
        assert len(rows) == 2


def test_index_loader_backfill():
    factory = build_session_factory()
    loader = IndexLoader(factory, index_fetcher=lambda index_name, start, end: [
        IndexPriceBar(index_name=index_name, date=date(2024, 1, 2), open=100, high=110, low=95, close=105, volume=1000),
    ])

    result = loader.backfill("NIFTY500", date(2024, 1, 1), date(2024, 1, 31))
    assert result.rows_loaded == 1

    with factory() as session:
        rows = session.execute(select(IndexPricesDaily)).all()
        assert len(rows) == 1
        assert rows[0].index_name == "NIFTY500"


def test_index_loader_incremental_update():
    factory = build_session_factory()
    loader = IndexLoader(factory, index_fetcher=lambda index_name, start, end: [
        IndexPriceBar(index_name=index_name, date=date(2024, 1, 2), open=100, high=110, low=95, close=105, volume=1000),
    ])

    result = loader.incremental_update("NIFTY500", date(2024, 1, 1), date(2024, 1, 31))
    assert result.rows_loaded == 1

    with factory() as session:
        rows = session.execute(select(IndexPricesDaily)).all()
        assert len(rows) == 1
