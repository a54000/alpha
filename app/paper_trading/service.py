"""Paper trading service for frozen Swing V2.1 workflows.

Reads:
  - configurable recommendation/price source
  - index_prices_daily for production benchmark tracking

Writes:
  - paper_portfolios
  - paper_positions
  - paper_trades
  - paper_daily_snapshots

Does not:
  - Place broker orders
  - Change scoring or recommendation logic
  - Run live trading
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

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
from app.paper_trading.data_source import PaperTradingDataSource, build_data_source


@dataclass(frozen=True)
class PaperTradingConfig:
    strategy: str = "swing_v2_1_rolling_10_slot"
    recommendation_model: str = "swing_v2_1"
    portfolio_size: int = 10
    initial_capital: float = 1_000_000.0
    holding_period: int = 20
    benchmark_symbol: str = "NIFTY500"
    max_candidate_rank: int | None = 5
    lifecycle_mode: str = "sell_removed_on_rebalance"
    entry_price_time: str | None = None
    entry_price_field: str = "open"
    previous_day_vwap_max_extension: float | None = None
    entry_skip_mode: str = "none"


SWING_V2_1_MODE = "swing_v2_1_rolling_10_slot"
ROLLING10_1M3M_VWAP25_MODE = "sector_rotation_adx_r10_vwap25"
SECTOR_ROTATION_1M3M_MODEL = "sector_rotation_adx_1m3m"


def paper_trading_config_for_mode(mode: str, **overrides) -> PaperTradingConfig:
    normalized = (mode or SWING_V2_1_MODE).strip().lower()
    if normalized in {SWING_V2_1_MODE, "swing_v2_1", "legacy"}:
        config = PaperTradingConfig(strategy=SWING_V2_1_MODE)
    elif normalized in {
        ROLLING10_1M3M_VWAP25_MODE,
        "rolling10_1m3m_vwap25_paper",
        "rolling10_v2_2",
        "sector_1m3m_vwap25",
    }:
        config = PaperTradingConfig(
            strategy=ROLLING10_1M3M_VWAP25_MODE,
            recommendation_model=SECTOR_ROTATION_1M3M_MODEL,
            portfolio_size=10,
            holding_period=20,
            max_candidate_rank=5,
            lifecycle_mode="hold_to_planned_exit",
            entry_price_time="10:30:00",
            entry_price_field="open",
            previous_day_vwap_max_extension=0.025,
            entry_skip_mode="skip",
        )
    else:
        raise ValueError(f"unsupported paper trading strategy mode: {mode}")
    return replace(config, **overrides) if overrides else config


class PaperTradingService:
    def __init__(self, session_factory, data_source: PaperTradingDataSource | None = None):
        self.session_factory = session_factory
        self.data_source = data_source or build_data_source()

    def initialize_portfolio(self, name: str, config: PaperTradingConfig | None = None) -> int:
        config = config or PaperTradingConfig()
        with self.session_factory() as session:
            portfolio = PaperPortfolio(
                name=name,
                strategy=config.strategy,
                portfolio_size=config.portfolio_size,
                initial_capital=config.initial_capital,
                cash=config.initial_capital,
                current_nav=config.initial_capital,
                benchmark_symbol=config.benchmark_symbol,
                status="active",
            )
            session.add(portfolio)
            session.commit()
            return int(portfolio.portfolio_id)

    def rebalance_weekly(self, portfolio_id: int, signal_date: date, config: PaperTradingConfig | None = None) -> dict[str, object]:
        config = config or PaperTradingConfig()
        with self.session_factory() as session:
            portfolio = session.get(PaperPortfolio, portfolio_id)
            if portfolio is None:
                raise ValueError(f"paper portfolio not found: {portfolio_id}")

            recommendations = self._load_recommendations(session, signal_date, config)
            effective_recommendation_date = recommendations[0].date if recommendations else signal_date
            report: dict[str, object] = {
                "step": "rebalance_weekly",
                "data_source": self.data_source.name,
                "recommendation_date_used": effective_recommendation_date.isoformat(),
                "price_date_used": None,
                "symbols_considered": [row.symbol for row in recommendations],
                "symbols_entered": [],
                "symbols_skipped": [],
            }
            if not recommendations:
                report["symbols_skipped"].append({"symbol": None, "reason": "no_recommendations_for_signal_date"})
                return report
            max_rank = config.max_candidate_rank or config.portfolio_size
            target_symbols = {row.symbol for row in recommendations[:max_rank]}
            default_entry_date = self._next_entry_day_after(session, effective_recommendation_date, config)
            report["price_date_used"] = default_entry_date.isoformat() if default_entry_date else None
            if default_entry_date is None:
                report["symbols_skipped"].extend({"symbol": row.symbol, "reason": "no_next_trading_day"} for row in recommendations)
                return report

            if config.lifecycle_mode == "sell_removed_on_rebalance":
                open_positions = self._open_positions(session, portfolio_id)
                for position in open_positions:
                    if position.symbol not in target_symbols:
                        self._close_position(session, portfolio, position, default_entry_date, "weekly_removed")
            elif config.lifecycle_mode != "hold_to_planned_exit":
                raise ValueError(f"unsupported paper trading lifecycle mode: {config.lifecycle_mode}")

            open_symbols = {position.symbol for position in self._open_positions(session, portfolio_id)}
            slots = max(0, int(portfolio.portfolio_size) - len(open_symbols))
            if slots <= 0:
                session.commit()
                report["symbols_skipped"].extend({"symbol": row.symbol, "reason": "portfolio_full"} for row in recommendations)
                return report

            for rec in recommendations:
                if slots <= 0:
                    report["symbols_skipped"].append({"symbol": rec.symbol, "reason": "portfolio_full"})
                    break
                if rec.symbol in open_symbols:
                    report["symbols_skipped"].append({"symbol": rec.symbol, "reason": "already_open"})
                    continue
                entry_date = self._next_entry_day_for_symbol(session, rec.symbol, effective_recommendation_date, config) or default_entry_date
                nav = self._portfolio_nav(session, portfolio, entry_date, price_field="open")
                target_allocation = nav / float(portfolio.portfolio_size)
                entry_check = self._entry_check(session, rec.symbol, effective_recommendation_date, entry_date, config)
                if entry_check["skip"]:
                    report["symbols_skipped"].append(
                        {
                            "symbol": rec.symbol,
                            "reason": entry_check["reason"],
                            "candidate_entry_date": entry_date.isoformat(),
                            "entry_price": entry_check["entry_price"],
                            "reference_vwap": entry_check["reference_vwap"],
                            "entry_vs_reference_vwap_pct": entry_check["entry_vs_reference_vwap_pct"],
                        }
                    )
                    continue
                price = entry_check["entry_price"]
                if price is None or price <= 0:
                    report["symbols_skipped"].append({"symbol": rec.symbol, "reason": "missing_or_invalid_entry_price"})
                    continue
                allocation = min(target_allocation, float(portfolio.cash))
                if allocation <= 0:
                    report["symbols_skipped"].append({"symbol": rec.symbol, "reason": "insufficient_cash"})
                    break
                planned_exit = self._nth_symbol_trading_day_after(session, rec.symbol, entry_date, config.holding_period)
                quantity = allocation / price
                portfolio.cash = float(portfolio.cash) - allocation
                session.add(
                    PaperPosition(
                        portfolio_id=portfolio_id,
                        symbol=rec.symbol,
                        sector=self._sector(session, rec.symbol),
                        signal_date=signal_date,
                        recommendation_rank=rec.rank,
                        recommendation_score=float(rec.score) if rec.score is not None else None,
                        entry_date=entry_date,
                        entry_price=price,
                        quantity=quantity,
                        capital_allocated=allocation,
                        current_price=price,
                        market_value=allocation,
                        unrealized_pnl=0,
                        planned_exit_date=planned_exit,
                        status="open",
                        fees=0,
                        slippage=0,
                    )
                )
                open_symbols.add(rec.symbol)
                report["symbols_entered"].append(rec.symbol)
                report["price_date_used"] = entry_date.isoformat()
                slots -= 1

            session.commit()
            return report

    def update_daily(self, portfolio_id: int, snapshot_date: date) -> dict[str, object]:
        with self.session_factory() as session:
            portfolio = session.get(PaperPortfolio, portfolio_id)
            if portfolio is None:
                raise ValueError(f"paper portfolio not found: {portfolio_id}")
            report: dict[str, object] = {
                "step": "update_daily",
                "data_source": self.data_source.name,
                "price_date_used": snapshot_date.isoformat(),
                "symbols_considered": [position.symbol for position in self._open_positions(session, portfolio_id)],
                "symbols_entered": [],
                "symbols_skipped": [],
            }

            for position in self._open_positions(session, portfolio_id):
                if position.planned_exit_date is not None and snapshot_date >= position.planned_exit_date:
                    self._close_position(session, portfolio, position, snapshot_date, "planned_exit")

            market_value = 0.0
            unrealized_pnl = 0.0
            for position in self._open_positions(session, portfolio_id):
                close = self._price(session, position.symbol, snapshot_date, "close")
                if close is None:
                    close = float(position.current_price or position.entry_price)
                value = float(position.quantity) * close
                pnl = value - float(position.capital_allocated)
                position.current_price = close
                position.market_value = value
                position.unrealized_pnl = pnl
                market_value += value
                unrealized_pnl += pnl

            realized_pnl = self._realized_pnl(session, portfolio_id)
            nav = float(portfolio.cash) + market_value
            portfolio.current_nav = nav
            benchmark_close, benchmark_return = self._benchmark(session, portfolio, snapshot_date)
            self._upsert_snapshot(
                session,
                {
                    "portfolio_id": portfolio_id,
                    "date": snapshot_date,
                    "cash": float(portfolio.cash),
                    "market_value": market_value,
                    "nav": nav,
                    "realized_pnl": realized_pnl,
                    "unrealized_pnl": unrealized_pnl,
                    "fees": 0,
                    "slippage": 0,
                    "turnover": self._turnover_on_date(session, portfolio_id, snapshot_date),
                    "benchmark_close": benchmark_close,
                    "benchmark_return": benchmark_return,
                "open_positions": len(self._open_positions(session, portfolio_id)),
                },
            )
            session.commit()
            report["open_positions"] = len(self._open_positions(session, portfolio_id))
            report["nav"] = nav
            return report

    def performance_report(self, portfolio_id: int) -> dict[str, object]:
        with self.session_factory() as session:
            portfolio = session.get(PaperPortfolio, portfolio_id)
            if portfolio is None:
                raise ValueError(f"paper portfolio not found: {portfolio_id}")
            snapshots = list(
                session.execute(
                    select(PaperDailySnapshot)
                    .where(PaperDailySnapshot.portfolio_id == portfolio_id)
                    .order_by(PaperDailySnapshot.date.asc())
                ).scalars()
            )
            trades = list(session.execute(select(PaperTrade).where(PaperTrade.portfolio_id == portfolio_id)).scalars())
            if not snapshots:
                return {"portfolio_id": portfolio_id, "snapshots": 0, "trades": len(trades)}
            start_nav = float(snapshots[0].nav)
            end_nav = float(snapshots[-1].nav)
            trade_returns = [float(trade.return_pct) for trade in trades]
            wins = [value for value in trade_returns if value > 0]
            losses = [value for value in trade_returns if value < 0]
            return {
                "portfolio_id": portfolio_id,
                "strategy": portfolio.strategy,
                "start_date": snapshots[0].date.isoformat(),
                "end_date": snapshots[-1].date.isoformat(),
                "snapshots": len(snapshots),
                "trades": len(trades),
                "nav": end_nav,
                "total_return": (end_nav / start_nav) - 1 if start_nav else 0.0,
                "realized_pnl": float(snapshots[-1].realized_pnl),
                "unrealized_pnl": float(snapshots[-1].unrealized_pnl),
                "win_rate": len(wins) / len(trade_returns) if trade_returns else 0.0,
                "profit_factor": sum(wins) / abs(sum(losses)) if losses else (float("inf") if wins else 0.0),
            }

    def _load_recommendations(self, session, signal_date: date, config: PaperTradingConfig):
        max_rank = config.max_candidate_rank or config.portfolio_size
        return self.data_source.recommendations(session, signal_date, config.recommendation_model, max_rank)

    @staticmethod
    def _open_positions(session, portfolio_id: int) -> list[PaperPosition]:
        return list(
            session.execute(
                select(PaperPosition)
                .where(PaperPosition.portfolio_id == portfolio_id, PaperPosition.status == "open")
                .order_by(PaperPosition.entry_date.asc(), PaperPosition.symbol.asc())
            ).scalars()
        )

    def _price(self, session, symbol: str, price_date: date, field: str) -> float | None:
        return self.data_source.price(session, symbol, price_date, field)

    def _entry_check(self, session, symbol: str, signal_date: date, entry_date: date, config: PaperTradingConfig) -> dict[str, object]:
        if config.entry_price_time:
            entry_price = self.data_source.intraday_price(session, symbol, entry_date, config.entry_price_time, config.entry_price_field)
        else:
            entry_price = self._price(session, symbol, entry_date, config.entry_price_field)
        reference_vwap = None
        entry_vs_reference_vwap_pct = None
        skip = False
        reason = None
        if config.previous_day_vwap_max_extension is not None:
            reference_vwap = self.data_source.daily_vwap(session, symbol, signal_date)
            if entry_price is None:
                skip = True
                reason = "missing_or_invalid_entry_price"
            elif reference_vwap is None or reference_vwap <= 0:
                skip = True
                reason = "missing_previous_day_vwap"
            else:
                entry_vs_reference_vwap_pct = (float(entry_price) / float(reference_vwap)) - 1.0
                skip = (
                    config.entry_skip_mode == "skip"
                    and entry_vs_reference_vwap_pct > config.previous_day_vwap_max_extension
                )
                reason = "entry_gt_prevday_vwap_threshold" if skip else None
        return {
            "entry_price": entry_price,
            "reference_vwap": reference_vwap,
            "entry_vs_reference_vwap_pct": entry_vs_reference_vwap_pct,
            "skip": skip,
            "reason": reason,
        }

    def _sector(self, session, symbol: str) -> str | None:
        return self.data_source.sector(session, symbol)

    def _next_trading_day_after(self, session, signal_date: date) -> date | None:
        return self.data_source.next_trading_day_after(session, signal_date)

    def _next_entry_day_after(self, session, signal_date: date, config: PaperTradingConfig) -> date | None:
        if config.entry_price_time:
            return self.data_source.next_intraday_trading_day_after(session, signal_date, config.entry_price_time)
        return self._next_trading_day_after(session, signal_date)

    def _next_entry_day_for_symbol(self, session, symbol: str, signal_date: date, config: PaperTradingConfig) -> date | None:
        if config.entry_price_time:
            return self.data_source.next_symbol_intraday_trading_day_after(session, symbol, signal_date, config.entry_price_time)
        return self._next_trading_day_after(session, signal_date)

    def _nth_symbol_trading_day_after(self, session, symbol: str, entry_date: date, periods: int) -> date | None:
        rows = self.data_source.symbol_trading_dates(session, symbol, entry_date)
        try:
            index = rows.index(entry_date)
        except ValueError:
            return None
        exit_index = index + periods
        return rows[exit_index] if exit_index < len(rows) else None

    def _close_position(self, session, portfolio: PaperPortfolio, position: PaperPosition, exit_date: date, reason: str) -> None:
        exit_price = self._price(session, position.symbol, exit_date, "close")
        if exit_price is None or exit_price <= 0:
            return
        proceeds = float(position.quantity) * exit_price
        pnl = proceeds - float(position.capital_allocated)
        portfolio.cash = float(portfolio.cash) + proceeds
        position.status = "closed"
        position.exit_date = exit_date
        position.exit_price = exit_price
        position.current_price = exit_price
        position.market_value = 0
        position.unrealized_pnl = 0
        session.add(
            PaperTrade(
                portfolio_id=position.portfolio_id,
                position_id=position.position_id,
                symbol=position.symbol,
                sector=position.sector,
                signal_date=position.signal_date,
                entry_date=position.entry_date,
                exit_date=exit_date,
                entry_price=float(position.entry_price),
                exit_price=exit_price,
                quantity=float(position.quantity),
                capital_allocated=float(position.capital_allocated),
                proceeds=proceeds,
                realized_pnl=pnl,
                return_pct=(exit_price / float(position.entry_price)) - 1,
                fees=float(position.fees or 0),
                slippage=float(position.slippage or 0),
                turnover=proceeds,
                exit_reason=reason,
            )
        )

    def _portfolio_nav(self, session, portfolio: PaperPortfolio, current_date: date, price_field: str) -> float:
        value = float(portfolio.cash)
        for position in self._open_positions(session, int(portfolio.portfolio_id)):
            price = self._price(session, position.symbol, current_date, price_field)
            if price is not None:
                value += float(position.quantity) * price
        return value

    @staticmethod
    def _realized_pnl(session, portfolio_id: int) -> float:
        trades = session.execute(select(PaperTrade.realized_pnl).where(PaperTrade.portfolio_id == portfolio_id)).scalars()
        return sum(float(value) for value in trades if value is not None)

    @staticmethod
    def _turnover_on_date(session, portfolio_id: int, item_date: date) -> float:
        trades = session.execute(
            select(PaperTrade.turnover).where(PaperTrade.portfolio_id == portfolio_id, PaperTrade.exit_date == item_date)
        ).scalars()
        return sum(float(value) for value in trades if value is not None)

    @staticmethod
    def _benchmark(session, portfolio: PaperPortfolio, snapshot_date: date) -> tuple[float | None, float | None]:
        if not portfolio.benchmark_symbol:
            return None, None
        current = session.execute(
            select(IndexPricesDaily.close).where(
                IndexPricesDaily.index_name == portfolio.benchmark_symbol,
                IndexPricesDaily.date == snapshot_date,
            )
        ).scalar_one_or_none()
        previous_date = snapshot_date - timedelta(days=10)
        previous = session.execute(
            select(IndexPricesDaily.close)
            .where(IndexPricesDaily.index_name == portfolio.benchmark_symbol, IndexPricesDaily.date < snapshot_date, IndexPricesDaily.date >= previous_date)
            .order_by(IndexPricesDaily.date.desc())
            .limit(1)
        ).scalar_one_or_none()
        if current is None:
            return None, None
        current_float = float(current)
        previous_float = float(previous) if previous is not None else None
        return current_float, (current_float / previous_float - 1) if previous_float else None

    @staticmethod
    def _upsert_snapshot(session, payload: dict[str, object]) -> None:
        dialect = session.bind.dialect.name if session.bind else "sqlite"
        table = PaperDailySnapshot.__table__
        if dialect == "postgresql":
            stmt = pg_insert(table).values(**payload)
            stmt = stmt.on_conflict_do_update(
                index_elements=["portfolio_id", "date"],
                set_={key: payload[key] for key in payload if key not in {"portfolio_id", "date"}},
            )
        elif dialect == "sqlite":
            stmt = sqlite_insert(table).values(**payload)
            stmt = stmt.on_conflict_do_update(
                index_elements=["portfolio_id", "date"],
                set_={key: payload[key] for key in payload if key not in {"portfolio_id", "date"}},
            )
        else:
            existing = session.execute(
                select(PaperDailySnapshot).where(
                    PaperDailySnapshot.portfolio_id == payload["portfolio_id"],
                    PaperDailySnapshot.date == payload["date"],
                )
            ).scalar_one_or_none()
            if existing is not None:
                for key, value in payload.items():
                    if key not in {"portfolio_id", "date"}:
                        setattr(existing, key, value)
                return
            stmt = table.insert().values(**payload)
        session.execute(stmt)
