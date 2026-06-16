"""Portfolio-level backtesting for recommendation models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import math
import statistics

from sqlalchemy import select

from db.models import PricesDaily, RecommendationHistory, SymbolMaster

KNOWN_SPECIAL_SESSIONS = {
    date(2022, 10, 24),
    date(2023, 11, 12),
    date(2024, 3, 2),
    date(2024, 5, 18),
    date(2024, 11, 1),
}


@dataclass
class PortfolioPosition:
    symbol: str
    sector: str | None
    signal_date: date
    entry_date: date
    entry_price: float
    shares: float
    planned_exit_date: date
    rank: int


@dataclass(frozen=True)
class PortfolioBacktestConfig:
    model: str
    portfolio_size: int = 10
    holding_period: int = 20
    initial_capital: float = 1_000_000.0
    rebalance_frequency: str = "weekly"
    excluded_sectors: tuple[str, ...] = ()
    max_sector_weight: float | None = None
    max_positions_per_sector: int | None = None
    max_candidate_rank: int | None = None


class PortfolioBacktesterV1:
    """Top-N equal-weight portfolio simulator.

    Signals are EOD recommendations. Entries occur at the next trading-day open.
    Positions exit at the close after the configured holding-period trading days.
    Rebalance-date ranking is used to fill open slots; existing positions are not force-sold
    at rebalance unless their holding period has completed.
    """

    def __init__(self, session_factory):
        self.session_factory = session_factory

    def run(self, config: PortfolioBacktestConfig) -> dict[str, object]:
        with self.session_factory() as session:
            recommendations = self._load_recommendations(session, config.model)
            if not recommendations:
                return self._empty_result(config)

            symbols = {row.symbol for row in recommendations}
            sectors = dict(session.execute(select(SymbolMaster.symbol, SymbolMaster.sector)).all())
            prices = self._load_prices(session, symbols)

        all_dates = self._all_trading_dates(prices)
        if not all_dates:
            return self._empty_result(config)

        recs_by_date: dict[date, list[RecommendationHistory]] = {}
        for rec in recommendations:
            recs_by_date.setdefault(rec.date, []).append(rec)
        for rows in recs_by_date.values():
            rows.sort(key=lambda row: (row.rank, row.symbol))

        rebalance_signal_dates = self._rebalance_signal_dates(sorted(recs_by_date), config.rebalance_frequency)
        entries_by_date: dict[date, list[RecommendationHistory]] = {}
        for signal_date in rebalance_signal_dates:
            entry_date = self._next_trading_day_after(all_dates, signal_date)
            if entry_date is not None:
                entries_by_date[entry_date] = recs_by_date[signal_date]

        cash = config.initial_capital
        positions: list[PortfolioPosition] = []
        closed_trades: list[dict[str, object]] = []
        equity_curve: list[dict[str, object]] = []
        turnover_value = 0.0
        sector_weight_snapshots: list[dict[str, float]] = []

        first_signal = min(recs_by_date)
        start_index = max(0, all_dates.index(self._next_trading_day_after(all_dates, first_signal) or all_dates[0]))
        simulation_dates = all_dates[start_index:]

        for current_date in simulation_dates:
            # Exit mature positions at current close.
            remaining_positions: list[PortfolioPosition] = []
            closed_today: set[str] = set()
            for position in positions:
                close_price = prices.get(position.symbol, {}).get(current_date, {}).get("close")
                if current_date >= position.planned_exit_date and close_price is not None:
                    proceeds = position.shares * close_price
                    cash += proceeds
                    turnover_value += proceeds
                    trade_return = (close_price / position.entry_price) - 1
                    closed_trades.append(
                        {
                            "symbol": position.symbol,
                            "sector": position.sector,
                            "signal_date": position.signal_date.isoformat(),
                            "entry_date": position.entry_date.isoformat(),
                            "exit_date": current_date.isoformat(),
                            "entry_price": position.entry_price,
                            "exit_price": close_price,
                            "return": trade_return,
                            "pnl": proceeds - (position.shares * position.entry_price),
                            "entry_value": position.shares * position.entry_price,
                            "exit_value": proceeds,
                            "holding_days": self._trading_day_distance(all_dates, position.entry_date, current_date),
                        }
                    )
                    closed_today.add(position.symbol)
                else:
                    remaining_positions.append(position)
            positions = remaining_positions

            # Fill open slots at current open using latest weekly ranking.
            if current_date in entries_by_date and len(positions) < config.portfolio_size:
                held = {position.symbol for position in positions}
                open_slots = config.portfolio_size - len(positions)
                equity_at_open = cash + self._positions_value(positions, prices, current_date, "open")
                target_weight_value = equity_at_open / config.portfolio_size
                max_candidate_rank = config.max_candidate_rank or config.portfolio_size
                candidates = [
                    rec for rec in entries_by_date[current_date]
                    if rec.rank <= max_candidate_rank and rec.symbol not in held and rec.symbol not in closed_today
                ]

                for rec in candidates:
                    if len(positions) >= config.portfolio_size:
                        break
                    sector = sectors.get(rec.symbol)
                    if not self._passes_sector_constraints(
                        sector,
                        positions,
                        config,
                        prices,
                        current_date,
                        equity_at_open,
                    ):
                        continue
                    open_price = prices.get(rec.symbol, {}).get(current_date, {}).get("open")
                    if open_price is None or open_price <= 0:
                        continue
                    allocation = min(target_weight_value, cash)
                    if allocation <= 0:
                        break
                    shares = allocation / open_price
                    cash -= allocation
                    turnover_value += allocation
                    planned_exit = self._nth_trading_day_after(
                        self._symbol_dates(prices, rec.symbol),
                        current_date,
                        config.holding_period,
                    )
                    if planned_exit is None:
                        cash += allocation
                        turnover_value -= allocation
                        continue
                    positions.append(
                        PortfolioPosition(
                            symbol=rec.symbol,
                            sector=sector,
                            signal_date=rec.date,
                            entry_date=current_date,
                            entry_price=open_price,
                            shares=shares,
                            planned_exit_date=planned_exit,
                            rank=rec.rank,
                        )
                    )
                    held.add(rec.symbol)

            close_value = self._positions_value(positions, prices, current_date, "close")
            total_equity = cash + close_value
            sector_weights = self._sector_weights(positions, prices, current_date, total_equity)
            sector_weight_snapshots.append(sector_weights)
            equity_curve.append(
                {
                    "date": current_date.isoformat(),
                    "equity": total_equity,
                    "cash": cash,
                    "position_count": len(positions),
                }
            )

        # Liquidate any open positions at the final available close for complete trade stats.
        if simulation_dates:
            final_date = simulation_dates[-1]
            for position in positions:
                close_price = prices.get(position.symbol, {}).get(final_date, {}).get("close")
                if close_price is None:
                    continue
                trade_return = (close_price / position.entry_price) - 1
                closed_trades.append(
                    {
                        "symbol": position.symbol,
                        "sector": position.sector,
                        "signal_date": position.signal_date.isoformat(),
                        "entry_date": position.entry_date.isoformat(),
                        "exit_date": final_date.isoformat(),
                        "entry_price": position.entry_price,
                        "exit_price": close_price,
                        "return": trade_return,
                        "pnl": (position.shares * close_price) - (position.shares * position.entry_price),
                        "entry_value": position.shares * position.entry_price,
                        "exit_value": position.shares * close_price,
                        "holding_days": self._trading_day_distance(all_dates, position.entry_date, final_date),
                        "forced_final_exit": True,
                    }
                )

        metrics = self._metrics(
            config,
            equity_curve,
            closed_trades,
            turnover_value,
            sector_weight_snapshots,
        )
        return {
            "model": config.model,
            "config": {
                "portfolio_size": config.portfolio_size,
                "holding_period": config.holding_period,
                "initial_capital": config.initial_capital,
                "rebalance": config.rebalance_frequency,
                "excluded_sectors": list(config.excluded_sectors),
                "max_sector_weight": config.max_sector_weight,
                "max_positions_per_sector": config.max_positions_per_sector,
                "max_candidate_rank": config.max_candidate_rank,
                "entry": "next_trading_day_open",
                "exit": "close_after_holding_period",
                "leverage": "none",
            },
            "metrics": metrics,
            "equity_curve": equity_curve,
            "closed_trades": closed_trades,
            "closed_trades_sample": closed_trades[:20],
            "closed_trade_count": len(closed_trades),
        }

    def _load_recommendations(self, session, model: str) -> list[RecommendationHistory]:
        return list(
            session.execute(
                select(RecommendationHistory)
                .where(RecommendationHistory.model == model)
                .order_by(RecommendationHistory.date.asc(), RecommendationHistory.rank.asc())
            ).scalars().all()
        )

    def _load_prices(self, session, symbols: set[str]) -> dict[str, dict[date, dict[str, float]]]:
        if not symbols:
            return {}
        rows = session.execute(
            select(PricesDaily.symbol, PricesDaily.date, PricesDaily.open, PricesDaily.close)
            .where(PricesDaily.symbol.in_(symbols))
            .order_by(PricesDaily.symbol.asc(), PricesDaily.date.asc())
        ).all()
        prices: dict[str, dict[date, dict[str, float]]] = {}
        for symbol, price_date, open_price, close_price in rows:
            if open_price is None and close_price is None:
                continue
            prices.setdefault(symbol, {})[price_date] = {
                "open": float(open_price) if open_price is not None else float(close_price),
                "close": float(close_price) if close_price is not None else float(open_price),
            }
        return prices

    @staticmethod
    def _all_trading_dates(prices: dict[str, dict[date, dict[str, float]]]) -> list[date]:
        return sorted({price_date for symbol_prices in prices.values() for price_date in symbol_prices})

    @staticmethod
    def _symbol_dates(prices: dict[str, dict[date, dict[str, float]]], symbol: str) -> list[date]:
        return sorted(prices.get(symbol, {}))

    @staticmethod
    def _weekly_signal_dates(signal_dates: list[date]) -> list[date]:
        weekly: list[date] = []
        seen_weeks: set[tuple[int, int]] = set()
        for signal_date in signal_dates:
            year, week, _ = signal_date.isocalendar()
            key = (year, week)
            if key in seen_weeks:
                continue
            seen_weeks.add(key)
            weekly.append(signal_date)
        return weekly

    @classmethod
    def _rebalance_signal_dates(cls, signal_dates: list[date], frequency: str) -> list[date]:
        if frequency == "weekly":
            return cls._weekly_signal_dates(signal_dates)
        if frequency == "biweekly":
            weekly = cls._weekly_signal_dates(signal_dates)
            return [signal_date for index, signal_date in enumerate(weekly) if index % 2 == 0]
        if frequency == "monthly":
            monthly: list[date] = []
            seen_months: set[tuple[int, int]] = set()
            for signal_date in signal_dates:
                key = (signal_date.year, signal_date.month)
                if key in seen_months:
                    continue
                seen_months.add(key)
                monthly.append(signal_date)
            return monthly
        raise ValueError(f"Unsupported rebalance frequency: {frequency}")

    @staticmethod
    def _next_trading_day_after(dates: list[date], signal_date: date) -> date | None:
        for trading_date in dates:
            if trading_date > signal_date:
                return trading_date
        return None

    @staticmethod
    def _nth_trading_day_after(dates: list[date], entry_date: date, periods: int) -> date | None:
        sessions = PortfolioBacktesterV1._regular_session_dates(dates)
        try:
            index = sessions.index(entry_date)
        except ValueError:
            return None
        exit_index = index + periods - 1
        if exit_index >= len(sessions):
            return None
        return sessions[exit_index]

    @staticmethod
    def _trading_day_distance(dates: list[date], start: date, end: date) -> int | None:
        sessions = PortfolioBacktesterV1._regular_session_dates(dates)
        try:
            return sessions.index(end) - sessions.index(start) + 1
        except ValueError:
            return None

    @staticmethod
    def _regular_session_dates(dates: list[date]) -> list[date]:
        return [item for item in sorted(dates) if item not in KNOWN_SPECIAL_SESSIONS]

    @staticmethod
    def _positions_value(
        positions: list[PortfolioPosition],
        prices: dict[str, dict[date, dict[str, float]]],
        current_date: date,
        price_field: str,
    ) -> float:
        value = 0.0
        for position in positions:
            price = prices.get(position.symbol, {}).get(current_date, {}).get(price_field)
            if price is not None:
                value += position.shares * price
        return value

    @staticmethod
    def _sector_weights(
        positions: list[PortfolioPosition],
        prices: dict[str, dict[date, dict[str, float]]],
        current_date: date,
        total_equity: float,
    ) -> dict[str, float]:
        if total_equity <= 0:
            return {}
        weights: dict[str, float] = {}
        for position in positions:
            price = prices.get(position.symbol, {}).get(current_date, {}).get("close")
            if price is None:
                continue
            sector = position.sector or "UNKNOWN"
            weights[sector] = weights.get(sector, 0.0) + (position.shares * price / total_equity)
        return weights

    @staticmethod
    def _passes_sector_constraints(
        sector: str | None,
        positions: list[PortfolioPosition],
        config: PortfolioBacktestConfig,
        prices: dict[str, dict[date, dict[str, float]]],
        current_date: date,
        total_equity: float,
    ) -> bool:
        sector_name = sector or "UNKNOWN"
        if sector_name in config.excluded_sectors:
            return False
        if config.max_positions_per_sector is not None:
            sector_positions = sum(
                1 for position in positions
                if (position.sector or "UNKNOWN") == sector_name
            )
            if sector_positions >= config.max_positions_per_sector:
                return False
        if config.max_sector_weight is not None and total_equity > 0:
            current_sector_value = 0.0
            for position in positions:
                if (position.sector or "UNKNOWN") != sector_name:
                    continue
                price = prices.get(position.symbol, {}).get(current_date, {}).get("open")
                if price is not None:
                    current_sector_value += position.shares * price
            next_position_weight = 1 / config.portfolio_size
            projected_weight = (current_sector_value / total_equity) + next_position_weight
            if projected_weight > config.max_sector_weight:
                return False
        return True

    def _metrics(
        self,
        config: PortfolioBacktestConfig,
        equity_curve: list[dict[str, object]],
        closed_trades: list[dict[str, object]],
        turnover_value: float,
        sector_weight_snapshots: list[dict[str, float]],
    ) -> dict[str, object]:
        if not equity_curve:
            return {}

        equity_values = [float(row["equity"]) for row in equity_curve]
        returns = [
            (right / left) - 1
            for left, right in zip(equity_values, equity_values[1:])
            if left != 0
        ]
        total_return = (equity_values[-1] / config.initial_capital) - 1
        days = max(1, len(equity_curve))
        cagr = (equity_values[-1] / config.initial_capital) ** (252 / days) - 1
        volatility = statistics.stdev(returns) * math.sqrt(252) if len(returns) > 1 else 0.0
        sharpe = (statistics.mean(returns) / statistics.stdev(returns) * math.sqrt(252)) if len(returns) > 1 and statistics.stdev(returns) != 0 else 0.0
        downside = [value for value in returns if value < 0]
        sortino = (
            statistics.mean(returns) / statistics.stdev(downside) * math.sqrt(252)
            if len(downside) > 1 and statistics.stdev(downside) != 0
            else 0.0
        )

        peak = equity_values[0]
        max_drawdown = 0.0
        for value in equity_values:
            peak = max(peak, value)
            if peak:
                max_drawdown = min(max_drawdown, (value / peak) - 1)

        trade_returns = [float(trade["return"]) for trade in closed_trades if trade.get("return") is not None]
        wins = [value for value in trade_returns if value > 0]
        losses = [value for value in trade_returns if value < 0]
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        profit_factor = gross_profit / gross_loss if gross_loss else (float("inf") if gross_profit else 0.0)

        avg_equity = statistics.mean(equity_values) if equity_values else config.initial_capital
        turnover = turnover_value / avg_equity if avg_equity else 0.0
        holding_periods = [
            int(trade["holding_days"]) for trade in closed_trades
            if trade.get("holding_days") is not None
        ]

        avg_sector_weights: dict[str, float] = {}
        for snapshot in sector_weight_snapshots:
            for sector, weight in snapshot.items():
                avg_sector_weights[sector] = avg_sector_weights.get(sector, 0.0) + weight
        if sector_weight_snapshots:
            avg_sector_weights = {
                sector: weight / len(sector_weight_snapshots)
                for sector, weight in avg_sector_weights.items()
            }
        top_sectors = sorted(avg_sector_weights.items(), key=lambda item: item[1], reverse=True)

        return {
            "total_return": total_return,
            "cagr": cagr,
            "max_drawdown": max_drawdown,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "volatility": volatility,
            "turnover": turnover,
            "win_rate": len(wins) / len(trade_returns) if trade_returns else 0.0,
            "profit_factor": profit_factor,
            "sector_concentration": {
                "top_sector": top_sectors[0][0] if top_sectors else None,
                "top_sector_avg_weight": top_sectors[0][1] if top_sectors else 0.0,
                "top_3_avg_weight": sum(weight for _, weight in top_sectors[:3]),
                "sectors": [
                    {"sector": sector, "avg_weight": weight}
                    for sector, weight in top_sectors
                ],
            },
            "average_holding_period": statistics.mean(holding_periods) if holding_periods else 0.0,
            "closed_trades": len(closed_trades),
            "final_equity": equity_values[-1],
        }

    @staticmethod
    def _empty_result(config: PortfolioBacktestConfig) -> dict[str, object]:
        return {
            "model": config.model,
            "config": {
                "portfolio_size": config.portfolio_size,
                "holding_period": config.holding_period,
                "initial_capital": config.initial_capital,
            },
            "metrics": {},
            "equity_curve": [],
            "closed_trades": [],
            "closed_trades_sample": [],
            "closed_trade_count": 0,
        }
