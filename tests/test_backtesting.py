from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.backtesting.run_backtest import (
    BacktestRunner,
    aggregate_metrics,
    compute_return,
    forward_trading_day_return,
    write_backtest_report,
)
from db.base import Base
from db.models import BacktestRuns, PricesDaily, RecommendationHistory, SymbolMaster


def build_session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)


def seed_trading_days(
    session,
    *,
    symbol: str,
    start: date,
    day_count: int,
    start_close: float = 100.0,
    daily_return: float = 0.0,
):
    if session.get(SymbolMaster, symbol) is None:
        session.add(SymbolMaster(symbol=symbol))
        session.flush()

    close = start_close
    for offset in range(day_count):
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
        close *= 1.0 + daily_return


def seed_price_row(session, symbol: str, price_date: date, open_price: float, close_price: float):
    if session.get(SymbolMaster, symbol) is None:
        session.add(SymbolMaster(symbol=symbol))
        session.flush()
    session.add(
        PricesDaily(
            symbol=symbol,
            date=price_date,
            open=open_price,
            high=max(open_price, close_price),
            low=min(open_price, close_price),
            close=close_price,
            volume=1000,
        )
    )


def seed_recommendation(
    session,
    *,
    symbol: str,
    recommendation_date: date,
    model: str = "swing",
    rank: int = 1,
    score: float = 85.0,
):
    if session.get(SymbolMaster, symbol) is None:
        session.add(SymbolMaster(symbol=symbol))
        session.flush()
    session.add(
        RecommendationHistory(
            date=recommendation_date,
            model=model,
            rank=rank,
            symbol=symbol,
            score=score,
        )
    )


def test_compute_return_calculation():
    assert compute_return(100.0, 110.0) == pytest.approx(0.10)
    assert compute_return(200.0, 180.0) == pytest.approx(-0.10)


def test_forward_return_uses_trading_day_offsets():
    start = date(2024, 1, 1)
    prices = {start + timedelta(days=index): 100.0 + index for index in range(30)}
    sorted_dates = list(prices.keys())

    assert forward_trading_day_return(prices, sorted_dates, start, 5) == pytest.approx(0.05)
    assert forward_trading_day_return(prices, sorted_dates, start, 10) == pytest.approx(0.10)


def test_forward_return_missing_future_prices_returns_none():
    start = date(2024, 1, 1)
    prices = {start + timedelta(days=index): 100.0 + index for index in range(8)}
    sorted_dates = list(prices.keys())

    assert forward_trading_day_return(prices, sorted_dates, start, 5) is not None
    assert forward_trading_day_return(prices, sorted_dates, start, 10) is None
    assert forward_trading_day_return(prices, sorted_dates, start + timedelta(days=7), 1) is None


def test_aggregate_metrics():
    metrics = aggregate_metrics([0.10, -0.05, 0.02, None, 0.08])

    assert metrics.valid_count == 4
    assert metrics.trade_count == 5
    assert metrics.win_rate == pytest.approx(0.75)
    assert metrics.avg_return == pytest.approx(0.0375)
    assert metrics.median_return == pytest.approx(0.05)
    assert metrics.max_gain == pytest.approx(0.10)
    assert metrics.max_loss == pytest.approx(-0.05)


def test_aggregate_metrics_empty_returns_zeros():
    metrics = aggregate_metrics([None, None])
    assert metrics.valid_count == 0
    assert metrics.win_rate == 0.0
    assert metrics.avg_return == 0.0


def test_swing_backtest_persists_horizon_returns_and_metrics():
    factory = build_session_factory()
    start = date(2024, 1, 1)
    signal_date = start

    with factory() as session:
        seed_trading_days(session, symbol="AAA", start=start, day_count=30, start_close=100.0, daily_return=0.01)
        seed_trading_days(session, symbol="^CRSLDX", start=start, day_count=30, start_close=1000.0, daily_return=0.005)
        seed_recommendation(session, symbol="AAA", recommendation_date=signal_date, model="swing")
        session.commit()

    runner = BacktestRunner(factory)
    report = runner.run("swing", signal_date, signal_date)

    assert report.trade_count == 1
    trade = report.trades[0]
    assert trade.signal_date == signal_date
    assert trade.entry_date == signal_date + timedelta(days=1)
    assert trade.returns["return_5d"] == pytest.approx((1.01**5) - 1, rel=1e-3)
    assert trade.returns["return_10d"] == pytest.approx((1.01**10) - 1, rel=1e-3)
    assert trade.returns["return_20d"] == pytest.approx((1.01**20) - 1, rel=1e-3)
    assert report.aggregate_by_horizon["return_5d"].win_rate == pytest.approx(1.0)

    with factory() as session:
        row = session.get(BacktestRuns, report.backtest_run_id)
        assert row is not None
        assert row.model == "swing"
        assert row.total_trades == 1
        assert row.config_json["trades"][0]["signal_date"] == signal_date.isoformat()
        assert row.config_json["trades"][0]["entry_date"] == (signal_date + timedelta(days=1)).isoformat()
        assert row.config_json["trades"][0]["return_5d"] == pytest.approx((1.01**5) - 1, rel=1e-3)


def test_backtest_uses_next_trading_day_open_not_signal_close():
    factory = build_session_factory()
    signal_date = date(2024, 1, 1)
    entry_date = date(2024, 1, 2)

    with factory() as session:
        seed_price_row(session, "AAA", signal_date, open_price=95.0, close_price=100.0)
        seed_price_row(session, "AAA", entry_date, open_price=110.0, close_price=112.0)
        for offset in range(2, 8):
            current_date = signal_date + timedelta(days=offset)
            close_price = 110.0 + offset
            seed_price_row(session, "AAA", current_date, open_price=close_price, close_price=close_price)
        seed_recommendation(session, symbol="AAA", recommendation_date=signal_date, model="swing")
        session.commit()

    report = BacktestRunner(factory).run("swing", signal_date, signal_date, persist=False)

    assert report.trade_count == 1
    trade = report.trades[0]
    assert trade.signal_date == signal_date
    assert trade.entry_date == entry_date
    assert trade.entry_price == 110.0
    assert trade.exit_dates["return_5d"] == signal_date + timedelta(days=6)
    assert trade.returns["return_5d"] == pytest.approx((116.0 / 110.0) - 1.0)


def test_benchmark_comparison_when_nifty_available():
    factory = build_session_factory()
    start = date(2024, 2, 1)
    signal_date = start

    with factory() as session:
        seed_trading_days(session, symbol="AAA", start=start, day_count=150, start_close=100.0, daily_return=0.02)
        seed_trading_days(session, symbol="^CRSLDX", start=start, day_count=150, start_close=1000.0, daily_return=0.01)
        seed_recommendation(session, symbol="AAA", recommendation_date=signal_date, model="positional")
        session.commit()

    runner = BacktestRunner(factory)
    report = runner.run("positional", signal_date, signal_date, benchmark_symbol="^CRSLDX")

    assert report.benchmark_available is True
    assert report.trades[0].entry_date == signal_date + timedelta(days=1)
    stock_return = report.trades[0].returns["return_1m"]
    bench_return = report.benchmark_by_horizon["return_1m"].avg_return
    assert stock_return > bench_return
    assert report.alpha_by_horizon["return_1m"] == pytest.approx(stock_return - bench_return)

    stock_return_3m = report.trades[0].returns["return_3m"]
    bench_return_3m = report.benchmark_by_horizon["return_3m"].avg_return

    with factory() as session:
        row = session.get(BacktestRuns, report.backtest_run_id)
        assert float(row.nifty_return_pct) == pytest.approx(bench_return_3m * 100, rel=1e-2)
        assert float(row.alpha_pct) == pytest.approx((stock_return_3m - bench_return_3m) * 100, rel=1e-2)


def test_benchmark_comparison_skipped_when_benchmark_missing():
    factory = build_session_factory()
    start = date(2024, 3, 1)
    signal_date = start

    with factory() as session:
        seed_trading_days(session, symbol="AAA", start=start, day_count=30, start_close=100.0, daily_return=0.01)
        seed_recommendation(session, symbol="AAA", recommendation_date=signal_date, model="swing")
        session.commit()

    runner = BacktestRunner(factory)
    report = runner.run("swing", signal_date, signal_date, benchmark_symbol="^CRSLDX")

    assert report.benchmark_available is False
    assert report.alpha_by_horizon["return_5d"] is None

    with factory() as session:
        row = session.get(BacktestRuns, report.backtest_run_id)
        assert row.nifty_return_pct is None
        assert row.alpha_pct is None


def test_write_backtest_report(tmp_path):
    factory = build_session_factory()
    start = date(2024, 4, 1)

    with factory() as session:
        seed_trading_days(session, symbol="AAA", start=start, day_count=15, start_close=100.0, daily_return=0.01)
        seed_recommendation(session, symbol="AAA", recommendation_date=start, model="swing")
        session.commit()

    runner = BacktestRunner(factory)
    report = runner.run("swing", start, start, persist=False)
    output = write_backtest_report(report, tmp_path / "backtest_report.json")

    assert output.exists()
    payload = output.read_text(encoding="utf-8")
    assert '"return_5d"' in payload
    assert '"benchmark_available"' in payload
