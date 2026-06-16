from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.paper_trading import ROLLING10_1M3M_VWAP25_MODE, SWING_V2_1_MODE, PaperTradingConfig, PaperTradingService, paper_trading_config_for_mode
from app.paper_trading.data_source import PaperTradingDataSource, normalize_source_name
from db.base import Base
from db.models import (
    IndexPricesDaily,
    PaperDailySnapshot,
    PaperPortfolio,
    PaperPosition,
    PaperTrade,
    PricesDaily,
    RecommendationHistory,
    SymbolMaster,
)


class FakePilotDataSource(PaperTradingDataSource):
    name = "PILOT_PHASE2A"

    def recommendations(self, session, signal_date: date, model: str, max_rank: int):
        return session.execute(
            select(RecommendationHistory)
            .where(
                RecommendationHistory.date == signal_date,
                RecommendationHistory.model == model,
                RecommendationHistory.rank <= max_rank,
            )
            .order_by(RecommendationHistory.rank.asc(), RecommendationHistory.symbol.asc())
        ).scalars().all()

    def price(self, session, symbol: str, price_date: date, field: str) -> float | None:
        row = session.execute(select(PricesDaily.open, PricesDaily.close).where(PricesDaily.symbol == symbol, PricesDaily.date == price_date)).first()
        if row is None:
            return None
        value = row.open if field == "open" else row.close
        fallback = row.close if field == "open" else row.open
        return float(value if value is not None else fallback)

    def next_trading_day_after(self, session, signal_date: date) -> date | None:
        return session.execute(select(PricesDaily.date).where(PricesDaily.date > signal_date).order_by(PricesDaily.date.asc()).limit(1)).scalar_one_or_none()

    def symbol_trading_dates(self, session, symbol: str, start_date: date) -> list[date]:
        return list(session.execute(select(PricesDaily.date).where(PricesDaily.symbol == symbol, PricesDaily.date >= start_date).order_by(PricesDaily.date.asc())).scalars())

    def sector(self, session, symbol: str) -> str | None:
        return session.execute(select(SymbolMaster.sector).where(SymbolMaster.symbol == symbol)).scalar_one_or_none()


class FakeIntradayPilotDataSource(FakePilotDataSource):
    def __init__(self, entry_prices: dict[tuple[str, date], float], daily_vwaps: dict[tuple[str, date], float]) -> None:
        self.entry_prices = entry_prices
        self.daily_vwaps = daily_vwaps

    def intraday_price(self, session, symbol: str, price_date: date, bar_time: str, field: str) -> float | None:
        assert bar_time == "10:30:00"
        assert field == "open"
        return self.entry_prices.get((symbol, price_date))

    def daily_vwap(self, session, symbol: str, price_date: date) -> float | None:
        return self.daily_vwaps.get((symbol, price_date))


def build_session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)


def seed_market(session) -> None:
    signal_date = date(2026, 1, 5)
    symbols = ["AAA", "BBB", "CCC"]
    sectors = {"AAA": "Energy", "BBB": "IT", "CCC": "Financial Services"}
    for symbol in symbols:
        session.add(SymbolMaster(symbol=symbol, sector=sectors[symbol]))
    session.flush()
    for rank, symbol in enumerate(symbols, start=1):
        session.add(
            RecommendationHistory(
                date=signal_date,
                model="swing_v2_1",
                rank=rank,
                symbol=symbol,
                score=90 - rank,
            )
        )
    for offset in range(35):
        price_date = signal_date + timedelta(days=offset + 1)
        for index, symbol in enumerate(symbols):
            base = 100 + index * 10 + offset
            session.add(
                PricesDaily(
                    symbol=symbol,
                    date=price_date,
                    open=base,
                    close=base + 1,
                    volume=1000,
                )
            )
        session.add(IndexPricesDaily(index_name="NIFTY500", date=price_date, close=20000 + offset))


def test_initialize_paper_portfolio():
    factory = build_session_factory()
    service = PaperTradingService(factory)

    portfolio_id = service.initialize_portfolio(
        "Top 5 Paper",
        PaperTradingConfig(portfolio_size=5, initial_capital=500_000),
    )

    with factory() as session:
        portfolio = session.get(PaperPortfolio, portfolio_id)
        assert portfolio is not None
        assert portfolio.name == "Top 5 Paper"
        assert float(portfolio.cash) == 500_000
        assert float(portfolio.current_nav) == 500_000


def test_weekly_rebalance_creates_simulated_entries_and_daily_snapshot():
    factory = build_session_factory()
    with factory() as session:
        seed_market(session)
        session.commit()

    service = PaperTradingService(factory)
    config = PaperTradingConfig(portfolio_size=2, initial_capital=100_000, holding_period=20)
    portfolio_id = service.initialize_portfolio("Top 2 Paper", config)

    service.rebalance_weekly(portfolio_id, date(2026, 1, 5), config)
    service.update_daily(portfolio_id, date(2026, 1, 6))

    with factory() as session:
        positions = session.execute(
            select(PaperPosition).where(PaperPosition.portfolio_id == portfolio_id, PaperPosition.status == "open")
        ).scalars().all()
        snapshot = session.execute(
            select(PaperDailySnapshot).where(
                PaperDailySnapshot.portfolio_id == portfolio_id,
                PaperDailySnapshot.date == date(2026, 1, 6),
            )
        ).scalar_one()
        portfolio = session.get(PaperPortfolio, portfolio_id)

        assert len(positions) == 2
        assert {position.symbol for position in positions} == {"AAA", "BBB"}
        assert snapshot.open_positions == 2
        assert float(snapshot.nav) > 100_000
        assert float(portfolio.current_nav) == float(snapshot.nav)


def test_rolling_10_slot_default_uses_top5_candidate_cap():
    factory = build_session_factory()
    signal_date = date(2026, 1, 5)
    with factory() as session:
        for rank in range(1, 8):
            symbol = f"S{rank:02d}"
            session.add(SymbolMaster(symbol=symbol, sector="IT"))
        session.flush()
        for rank in range(1, 8):
            symbol = f"S{rank:02d}"
            session.add(
                RecommendationHistory(
                    date=signal_date,
                    model="swing_v2_1",
                    rank=rank,
                    symbol=symbol,
                    score=100 - rank,
                )
            )
            session.add(PricesDaily(symbol=symbol, date=date(2026, 1, 6), open=100 + rank, close=101 + rank, volume=1000))
        session.commit()

    service = PaperTradingService(factory)
    config = PaperTradingConfig(initial_capital=1_000_000)
    portfolio_id = service.initialize_portfolio("Rolling 10 Slot", config)

    report = service.rebalance_weekly(portfolio_id, signal_date, config)

    with factory() as session:
        positions = session.execute(
            select(PaperPosition).where(PaperPosition.portfolio_id == portfolio_id, PaperPosition.status == "open")
        ).scalars().all()
        portfolio = session.get(PaperPortfolio, portfolio_id)

        assert portfolio is not None
        assert portfolio.portfolio_size == 10
        assert len(positions) == 5
        assert {position.symbol for position in positions} == {"S01", "S02", "S03", "S04", "S05"}
        assert report["symbols_skipped"] == []


def test_performance_report_after_one_day_update():
    factory = build_session_factory()
    with factory() as session:
        seed_market(session)
        session.commit()

    service = PaperTradingService(factory)
    config = PaperTradingConfig(portfolio_size=2, initial_capital=100_000, holding_period=20)
    portfolio_id = service.initialize_portfolio("Top 2 Paper", config)
    service.rebalance_weekly(portfolio_id, date(2026, 1, 5), config)
    service.update_daily(portfolio_id, date(2026, 1, 6))

    report = service.performance_report(portfolio_id)

    assert report["portfolio_id"] == portfolio_id
    assert report["snapshots"] == 1
    assert report["trades"] == 0
    assert report["nav"] > 100_000


def test_hold_to_planned_exit_ignores_removed_weekly_recommendation():
    factory = build_session_factory()
    with factory() as session:
        seed_market(session)
        second_signal = date(2026, 1, 12)
        session.add(
            RecommendationHistory(
                date=second_signal,
                model="swing_v2_1",
                rank=1,
                symbol="CCC",
                score=95,
            )
        )
        session.commit()

    service = PaperTradingService(factory)
    config = PaperTradingConfig(
        portfolio_size=1,
        initial_capital=100_000,
        holding_period=20,
        lifecycle_mode="hold_to_planned_exit",
    )
    portfolio_id = service.initialize_portfolio("Hold Mode", config)

    service.rebalance_weekly(portfolio_id, date(2026, 1, 5), config)
    service.rebalance_weekly(portfolio_id, date(2026, 1, 12), config)

    with factory() as session:
        open_positions = session.execute(
            select(PaperPosition).where(PaperPosition.portfolio_id == portfolio_id, PaperPosition.status == "open")
        ).scalars().all()
        trades = session.execute(select(PaperTrade).where(PaperTrade.portfolio_id == portfolio_id)).scalars().all()

        assert len(open_positions) == 1
        assert open_positions[0].symbol == "AAA"
        assert trades == []


def test_default_mode_closes_removed_weekly_recommendation():
    factory = build_session_factory()
    with factory() as session:
        seed_market(session)
        second_signal = date(2026, 1, 12)
        session.add(
            RecommendationHistory(
                date=second_signal,
                model="swing_v2_1",
                rank=1,
                symbol="CCC",
                score=95,
            )
        )
        session.commit()

    service = PaperTradingService(factory)
    config = PaperTradingConfig(portfolio_size=1, initial_capital=100_000, holding_period=20)
    portfolio_id = service.initialize_portfolio("Default Mode", config)

    service.rebalance_weekly(portfolio_id, date(2026, 1, 5), config)
    service.rebalance_weekly(portfolio_id, date(2026, 1, 12), config)

    with factory() as session:
        open_positions = session.execute(
            select(PaperPosition).where(PaperPosition.portfolio_id == portfolio_id, PaperPosition.status == "open")
        ).scalars().all()
        trades = session.execute(select(PaperTrade).where(PaperTrade.portfolio_id == portfolio_id)).scalars().all()

        assert len(open_positions) == 1
        assert open_positions[0].symbol == "CCC"
        assert len(trades) == 1
        assert trades[0].symbol == "AAA"
        assert trades[0].exit_reason == "weekly_removed"


def test_pilot_source_generates_positions_when_recommendations_exist():
    factory = build_session_factory()
    with factory() as session:
        seed_market(session)
        session.commit()

    service = PaperTradingService(factory, data_source=FakePilotDataSource())
    config = PaperTradingConfig(portfolio_size=2, initial_capital=100_000, holding_period=20)
    portfolio_id = service.initialize_portfolio("Pilot Source", config)

    report = service.rebalance_weekly(portfolio_id, date(2026, 1, 5), config)
    service.update_daily(portfolio_id, date(2026, 1, 6))

    with factory() as session:
        positions = session.execute(select(PaperPosition).where(PaperPosition.portfolio_id == portfolio_id)).scalars().all()
        assert len(positions) == 2
        assert report["data_source"] == "PILOT_PHASE2A"
        assert report["recommendation_date_used"] == "2026-01-05"
        assert report["price_date_used"] == "2026-01-06"
        assert set(report["symbols_entered"]) == {"AAA", "BBB"}


def test_production_and_pilot_sources_keep_same_lifecycle_results():
    production_factory = build_session_factory()
    pilot_factory = build_session_factory()
    for factory in [production_factory, pilot_factory]:
        with factory() as session:
            seed_market(session)
            session.commit()

    config = PaperTradingConfig(portfolio_size=2, initial_capital=100_000, holding_period=20)
    production_service = PaperTradingService(production_factory)
    pilot_service = PaperTradingService(pilot_factory, data_source=FakePilotDataSource())
    production_id = production_service.initialize_portfolio("Production Source", config)
    pilot_id = pilot_service.initialize_portfolio("Pilot Source", config)

    production_service.rebalance_weekly(production_id, date(2026, 1, 5), config)
    pilot_service.rebalance_weekly(pilot_id, date(2026, 1, 5), config)

    with production_factory() as prod_session, pilot_factory() as pilot_session:
        prod_positions = prod_session.execute(select(PaperPosition).where(PaperPosition.portfolio_id == production_id).order_by(PaperPosition.symbol)).scalars().all()
        pilot_positions = pilot_session.execute(select(PaperPosition).where(PaperPosition.portfolio_id == pilot_id).order_by(PaperPosition.symbol)).scalars().all()
        assert [(p.symbol, float(p.entry_price), float(p.capital_allocated)) for p in prod_positions] == [
            (p.symbol, float(p.entry_price), float(p.capital_allocated)) for p in pilot_positions
        ]


def test_paper_trading_data_source_env_normalization():
    assert normalize_source_name("pilot_phase2a") == "PILOT_PHASE2A"
    assert normalize_source_name("production") == "PRODUCTION"


def test_strategy_mode_presets_keep_legacy_and_candidate_separate():
    legacy = paper_trading_config_for_mode(SWING_V2_1_MODE)
    candidate = paper_trading_config_for_mode(ROLLING10_1M3M_VWAP25_MODE)

    assert legacy.strategy == "swing_v2_1_rolling_10_slot"
    assert legacy.recommendation_model == "swing_v2_1"
    assert legacy.entry_price_time is None
    assert candidate.strategy == "sector_rotation_adx_r10_vwap25"
    assert candidate.recommendation_model == "sector_rotation_adx_1m3m"
    assert candidate.entry_price_time == "10:30:00"
    assert candidate.previous_day_vwap_max_extension == 0.025
    assert candidate.entry_skip_mode == "skip"


def test_candidate_mode_uses_1030_entry_and_skips_prevday_vwap_extension():
    factory = build_session_factory()
    signal_date = date(2026, 1, 5)
    entry_date = date(2026, 1, 6)
    with factory() as session:
        for symbol in ["AAA", "BBB"]:
            session.add(SymbolMaster(symbol=symbol, sector="IT"))
        session.flush()
        for symbol in ["AAA", "BBB"]:
            session.add(
                RecommendationHistory(
                    date=signal_date,
                    model="sector_rotation_adx_1m3m",
                    rank=1 if symbol == "AAA" else 2,
                    symbol=symbol,
                    score=90,
                )
            )
            for offset in range(35):
                item_date = entry_date + timedelta(days=offset)
                session.add(PricesDaily(symbol=symbol, date=item_date, open=100, close=101, volume=1000))
        session.commit()

    data_source = FakeIntradayPilotDataSource(
        entry_prices={
            ("AAA", entry_date): 101.0,
            ("BBB", entry_date): 103.0,
        },
        daily_vwaps={
            ("AAA", signal_date): 100.0,
            ("BBB", signal_date): 100.0,
        },
    )
    service = PaperTradingService(factory, data_source=data_source)
    config = paper_trading_config_for_mode(ROLLING10_1M3M_VWAP25_MODE, initial_capital=100_000)
    portfolio_id = service.initialize_portfolio("Candidate Paper", config)

    report = service.rebalance_weekly(portfolio_id, signal_date, config)

    with factory() as session:
        positions = session.execute(select(PaperPosition).where(PaperPosition.portfolio_id == portfolio_id)).scalars().all()
        assert len(positions) == 1
        assert positions[0].symbol == "AAA"
        assert float(positions[0].entry_price) == 101.0
        assert report["symbols_entered"] == ["AAA"]
        assert report["symbols_skipped"][0]["symbol"] == "BBB"
        assert report["symbols_skipped"][0]["reason"] == "entry_gt_prevday_vwap_threshold"
