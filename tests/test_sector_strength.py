from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.sectors.compute_sector_strength import SectorStrengthComputer, SectorStrengthReport, write_sector_strength_report
from db.base import Base
from db.models import PricesDaily, SymbolMaster, SectorDaily


def build_session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)


def seed_sector_data(factory):
    with factory() as session:
        session.add_all(
            [
                SymbolMaster(symbol="A1", sector="Capital Goods"),
                SymbolMaster(symbol="A2", sector="Capital Goods"),
                SymbolMaster(symbol="B1", sector="Financial Services"),
                SymbolMaster(symbol="B2", sector="Financial Services"),
            ]
        )
        session.commit()

        start = date(2024, 1, 1)
        for offset in range(140):
            current_date = start + timedelta(days=offset)
            session.add_all(
                [
                    PricesDaily(symbol="A1", date=current_date, open=100 + offset, high=101 + offset, low=99 + offset, close=100 + offset, volume=1000),
                    PricesDaily(symbol="A2", date=current_date, open=100 + offset, high=101 + offset, low=99 + offset, close=100 + offset, volume=1000),
                    PricesDaily(symbol="B1", date=current_date, open=100 + offset * 2, high=101 + offset * 2, low=99 + offset * 2, close=100 + offset * 2, volume=1000),
                    PricesDaily(symbol="B2", date=current_date, open=100 + offset * 2, high=101 + offset * 2, low=99 + offset * 2, close=100 + offset * 2, volume=1000),
                ]
            )
        session.commit()


def test_sector_returns_and_ranking():
    factory = build_session_factory()
    seed_sector_data(factory)

    computer = SectorStrengthComputer(factory)
    report = computer.generate(end_date=date(2024, 5, 19))

    assert report.sectors_processed > 0
    assert report.dates_processed > 0

    with factory() as session:
        rows = session.execute(
            select(SectorDaily).where(SectorDaily.date == date(2024, 5, 19)).order_by(SectorDaily.rank_composite)
        ).scalars().all()
        assert rows[0].sector_rank == 1
        assert rows[0].sector_score is not None
        assert rows[0].return_1m is not None
        assert rows[0].return_3m is not None
        assert rows[0].return_6m is not None


def test_sector_upsert_is_idempotent():
    factory = build_session_factory()
    seed_sector_data(factory)

    computer = SectorStrengthComputer(factory)
    first = computer.generate(end_date=date(2024, 5, 19))
    second = computer.generate(end_date=date(2024, 5, 19))

    assert first.rows_written > 0
    assert second.rows_written == 0


def test_sector_insufficient_history_is_handled():
    factory = build_session_factory()
    with factory() as session:
        session.add(SymbolMaster(symbol="A1", sector="Capital Goods"))
        session.commit()
        session.add(PricesDaily(symbol="A1", date=date(2024, 1, 1), open=100, high=101, low=99, close=100, volume=1000))
        session.commit()

    computer = SectorStrengthComputer(factory)
    report = computer.generate(end_date=date(2024, 1, 1))

    assert report.rows_written == 0
    assert report.missing_data_summary["insufficient_history"] >= 1


def seed_equal_weight_sector_data(factory):
    """Two stocks with +20% and +5% over 21 trading days; mean = 12.5%, not return-of-mean 10%."""
    with factory() as session:
        session.add_all(
            [
                SymbolMaster(symbol="A", sector="Chemicals"),
                SymbolMaster(symbol="B", sector="Chemicals"),
            ]
        )
        session.commit()

        start = date(2024, 1, 1)
        for offset in range(22):
            current_date = start + timedelta(days=offset)
            a_close = 100.0 if offset == 0 else 120.0 if offset == 21 else 100.0 + (20.0 * offset / 21)
            b_close = 200.0 if offset == 0 else 210.0 if offset == 21 else 200.0 + (10.0 * offset / 21)
            session.add_all(
                [
                    PricesDaily(symbol="A", date=current_date, open=a_close, high=a_close, low=a_close, close=a_close, volume=1000),
                    PricesDaily(symbol="B", date=current_date, open=b_close, high=b_close, low=b_close, close=b_close, volume=1000),
                ]
            )
        session.commit()


def test_equal_weight_sector_return_is_mean_of_stock_returns():
    factory = build_session_factory()
    seed_equal_weight_sector_data(factory)

    computer = SectorStrengthComputer(factory)
    computer.generate(start_date=date(2024, 1, 22), end_date=date(2024, 1, 22))

    with factory() as session:
        row = session.execute(
            select(SectorDaily).where(SectorDaily.sector == "Chemicals", SectorDaily.date == date(2024, 1, 22))
        ).scalar_one()

    expected_return = 0.125
    # Return-of-average-price: mean 150 -> 165 is +10%, not the spec's +12.5%.
    wrong_return = (165.0 / 150.0) - 1

    assert row.return_1m == expected_return
    assert row.sector_return_1m == expected_return
    assert row.return_1m != wrong_return


def test_write_sector_strength_report(tmp_path):
    report = SectorStrengthReport(sectors_processed=1, dates_processed=2, rows_written=3, failures=[], missing_data_summary={"insufficient_history": 0})
    path = write_sector_strength_report(report, tmp_path / "sector_report.json")
    assert path.exists()
