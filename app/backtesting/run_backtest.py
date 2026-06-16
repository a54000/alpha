"""Backtest recommendation performance against forward price returns.

Reads:
  - `recommendation_history`
  - `prices_daily`

Writes:
  - `backtest_runs`

Does not:
  - Modify scoring or recommendations
  - Build dashboards or run optimization
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import date, timedelta
from pathlib import Path
import json
import statistics
from typing import Iterable

from sqlalchemy import select

from app.utils.config import load_config
from db.models import BacktestRuns, PricesDaily, RecommendationHistory


@dataclass(frozen=True)
class BacktestConfig:
    model: str
    horizons: tuple[tuple[str, int], ...]
    primary_horizon: str


SWING_BACKTEST_CONFIG = BacktestConfig(
    model="swing",
    horizons=(
        ("return_5d", 5),
        ("return_10d", 10),
        ("return_20d", 20),
    ),
    primary_horizon="return_20d",
)

POSITIONAL_BACKTEST_CONFIG = BacktestConfig(
    model="positional",
    horizons=(
        ("return_1m", 21),
        ("return_3m", 63),
        ("return_6m", 126),
    ),
    primary_horizon="return_3m",
)

BACKTEST_CONFIGS = {
    SWING_BACKTEST_CONFIG.model: SWING_BACKTEST_CONFIG,
    POSITIONAL_BACKTEST_CONFIG.model: POSITIONAL_BACKTEST_CONFIG,
    "swing_v2": BacktestConfig(
        model="swing_v2",
        horizons=SWING_BACKTEST_CONFIG.horizons,
        primary_horizon=SWING_BACKTEST_CONFIG.primary_horizon,
    ),
    "swing_v2_1": BacktestConfig(
        model="swing_v2_1",
        horizons=SWING_BACKTEST_CONFIG.horizons,
        primary_horizon=SWING_BACKTEST_CONFIG.primary_horizon,
    ),
    "positional_v2": BacktestConfig(
        model="positional_v2",
        horizons=POSITIONAL_BACKTEST_CONFIG.horizons,
        primary_horizon=POSITIONAL_BACKTEST_CONFIG.primary_horizon,
    ),
}


@dataclass(frozen=True)
class AggregateMetrics:
    win_rate: float
    avg_return: float
    median_return: float
    max_gain: float
    max_loss: float
    trade_count: int
    valid_count: int


@dataclass(frozen=True)
class TradeBacktestResult:
    symbol: str
    signal_date: date
    entry_date: date
    entry_price: float
    rank: int
    score: float | None
    returns: dict[str, float | None]
    exit_dates: dict[str, date | None]
    exit_prices: dict[str, float | None]


@dataclass(frozen=True)
class BacktestRunReport:
    model: str
    start_date: date
    end_date: date
    trade_count: int
    valid_trade_count: int
    aggregate_by_horizon: dict[str, AggregateMetrics]
    benchmark_symbol: str | None
    benchmark_available: bool
    benchmark_by_horizon: dict[str, AggregateMetrics]
    alpha_by_horizon: dict[str, float | None]
    trades: list[TradeBacktestResult]
    backtest_run_id: int | None = None


def write_backtest_report(report: BacktestRunReport, output_path: str | Path) -> Path:
    path = Path(output_path)

    def _serialize(value):
        if isinstance(value, date):
            return value.isoformat()
        if hasattr(value, "__dataclass_fields__"):
            return {key: _serialize(getattr(value, key)) for key in value.__dataclass_fields__}
        if isinstance(value, dict):
            return {key: _serialize(item) for key, item in value.items()}
        if isinstance(value, list):
            return [_serialize(item) for item in value]
        return value

    path.write_text(json.dumps(_serialize(report), indent=2, sort_keys=True), encoding="utf-8")
    return path


def compute_return(entry_price: float, exit_price: float) -> float:
    if entry_price == 0:
        raise ValueError("entry_price must be non-zero")
    return (exit_price / entry_price) - 1.0


def forward_trading_day_return(
    prices_by_date: dict[date, float],
    sorted_dates: list[date],
    entry_date: date,
    periods_forward: int,
) -> float | None:
    if entry_date not in prices_by_date:
        return None
    try:
        entry_index = sorted_dates.index(entry_date)
    except ValueError:
        return None
    exit_index = entry_index + periods_forward
    if exit_index >= len(sorted_dates):
        return None
    entry_price = prices_by_date[entry_date]
    exit_price = prices_by_date[sorted_dates[exit_index]]
    if entry_price == 0:
        return None
    return compute_return(entry_price, exit_price)


def next_trading_day_after(sorted_dates: list[date], signal_date: date) -> date | None:
    for trading_date in sorted_dates:
        if trading_date > signal_date:
            return trading_date
    return None


def execution_window_return(
    open_by_date: dict[date, float],
    close_by_date: dict[date, float],
    sorted_dates: list[date],
    entry_date: date,
    periods_forward: int,
) -> tuple[float | None, date | None, float | None]:
    try:
        entry_index = sorted_dates.index(entry_date)
    except ValueError:
        return None, None, None

    exit_index = entry_index + periods_forward
    if exit_index >= len(sorted_dates):
        return None, None, None

    entry_price = open_by_date.get(entry_date)
    exit_date = sorted_dates[exit_index]
    exit_price = close_by_date.get(exit_date)
    if entry_price is None or exit_price is None or entry_price == 0:
        return None, exit_date, exit_price

    return compute_return(entry_price, exit_price), exit_date, exit_price


def matched_window_return(
    open_by_date: dict[date, float],
    close_by_date: dict[date, float],
    entry_date: date,
    exit_date: date | None,
) -> float | None:
    if exit_date is None:
        return None
    entry_price = open_by_date.get(entry_date)
    exit_price = close_by_date.get(exit_date)
    if entry_price is None or exit_price is None or entry_price == 0:
        return None
    return compute_return(entry_price, exit_price)


def aggregate_metrics(returns: list[float | None]) -> AggregateMetrics:
    valid = [value for value in returns if value is not None]
    if not valid:
        return AggregateMetrics(
            win_rate=0.0,
            avg_return=0.0,
            median_return=0.0,
            max_gain=0.0,
            max_loss=0.0,
            trade_count=len(returns),
            valid_count=0,
        )

    wins = sum(1 for value in valid if value > 0)
    return AggregateMetrics(
        win_rate=wins / len(valid),
        avg_return=sum(valid) / len(valid),
        median_return=statistics.median(valid),
        max_gain=max(valid),
        max_loss=min(valid),
        trade_count=len(returns),
        valid_count=len(valid),
    )


class BacktestRunner:
    def __init__(self, session_factory, *, config_path: str | Path = "configs/config.yaml"):
        self.session_factory = session_factory
        self.config = load_config(config_path)

    def run(
        self,
        model: str,
        start_date: date | None = None,
        end_date: date | None = None,
        *,
        benchmark_symbol: str | None = None,
        persist: bool = True,
    ) -> BacktestRunReport:
        backtest_config = BACKTEST_CONFIGS.get(model)
        if backtest_config is None:
            raise ValueError(f"Unsupported backtest model: {model}")

        benchmark_symbol = benchmark_symbol or self._default_benchmark_symbol()

        with self.session_factory() as session:
            recommendations = self._load_recommendations(session, model, start_date, end_date)
            if not recommendations:
                empty_report = self._empty_report(model, start_date, end_date, benchmark_symbol)
                if persist:
                    empty_report = self._persist_report(session, empty_report, backtest_config)
                    session.commit()
                return empty_report

            if start_date is None:
                start_date = min(row.date for row in recommendations)
            if end_date is None:
                end_date = max(row.date for row in recommendations)

            symbols = {row.symbol for row in recommendations}
            max_horizon = max(periods for _, periods in backtest_config.horizons)
            price_history = self._load_price_history(
                session,
                symbols | ({benchmark_symbol} if benchmark_symbol else set()),
                start_date,
                end_date + timedelta(days=max_horizon * 2),
            )

            trades: list[TradeBacktestResult] = []
            returns_by_horizon: dict[str, list[float | None]] = {
                field: [] for field, _ in backtest_config.horizons
            }
            benchmark_returns_by_horizon: dict[str, list[float | None]] = {
                field: [] for field, _ in backtest_config.horizons
            }

            benchmark_history = price_history.get(benchmark_symbol, {}) if benchmark_symbol else {}
            benchmark_open_prices = benchmark_history.get("open_prices", {})
            benchmark_close_prices = benchmark_history.get("close_prices", {})
            benchmark_available = bool(benchmark_symbol and benchmark_open_prices and benchmark_close_prices)

            for recommendation in recommendations:
                symbol_history = price_history.get(recommendation.symbol)
                if symbol_history is None:
                    continue

                dates = symbol_history["dates"]
                entry_date = next_trading_day_after(dates, recommendation.date)
                if entry_date is None:
                    continue

                open_prices = symbol_history["open_prices"]
                close_prices = symbol_history["close_prices"]
                entry_price = open_prices.get(entry_date)
                if entry_price is None:
                    continue

                trade_returns: dict[str, float | None] = {}
                exit_dates: dict[str, date | None] = {}
                exit_prices: dict[str, float | None] = {}
                for field, periods in backtest_config.horizons:
                    trade_return, exit_date, exit_price = execution_window_return(
                        open_prices,
                        close_prices,
                        dates,
                        entry_date,
                        periods,
                    )
                    trade_returns[field] = trade_return
                    exit_dates[field] = exit_date
                    exit_prices[field] = exit_price
                    returns_by_horizon[field].append(trade_return)

                    if benchmark_available:
                        benchmark_return = matched_window_return(
                            benchmark_open_prices,
                            benchmark_close_prices,
                            entry_date,
                            exit_date,
                        )
                        benchmark_returns_by_horizon[field].append(benchmark_return)
                    else:
                        benchmark_returns_by_horizon[field].append(None)

                trades.append(
                    TradeBacktestResult(
                        symbol=recommendation.symbol,
                        signal_date=recommendation.date,
                        entry_date=entry_date,
                        entry_price=float(entry_price),
                        rank=recommendation.rank,
                        score=float(recommendation.score) if recommendation.score is not None else None,
                        returns=trade_returns,
                        exit_dates=exit_dates,
                        exit_prices=exit_prices,
                    )
                )

            aggregate_by_horizon = {
                field: aggregate_metrics(returns_by_horizon[field])
                for field, _ in backtest_config.horizons
            }
            benchmark_by_horizon = {
                field: aggregate_metrics(benchmark_returns_by_horizon[field])
                for field, _ in backtest_config.horizons
            }
            alpha_by_horizon = {
                field: (
                    aggregate_by_horizon[field].avg_return - benchmark_by_horizon[field].avg_return
                    if benchmark_available and benchmark_by_horizon[field].valid_count > 0
                    else None
                )
                for field, _ in backtest_config.horizons
            }

            primary = aggregate_by_horizon[backtest_config.primary_horizon]
            report = BacktestRunReport(
                model=model,
                start_date=start_date,
                end_date=end_date,
                trade_count=len(trades),
                valid_trade_count=primary.valid_count,
                aggregate_by_horizon=aggregate_by_horizon,
                benchmark_symbol=benchmark_symbol,
                benchmark_available=benchmark_available,
                benchmark_by_horizon=benchmark_by_horizon,
                alpha_by_horizon=alpha_by_horizon,
                trades=trades,
            )

            if persist:
                report = self._persist_report(session, report, backtest_config)
                session.commit()
            return report

    def _default_benchmark_symbol(self) -> str | None:
        data_config = self.config.raw.get("data", {})
        symbol = data_config.get("nifty500_symbol")
        return str(symbol) if symbol else None

    def _load_recommendations(
        self,
        session,
        model: str,
        start_date: date | None,
        end_date: date | None,
    ) -> list[RecommendationHistory]:
        query = select(RecommendationHistory).where(RecommendationHistory.model == model)
        if start_date is not None:
            query = query.where(RecommendationHistory.date >= start_date)
        if end_date is not None:
            query = query.where(RecommendationHistory.date <= end_date)
        query = query.order_by(RecommendationHistory.date.asc(), RecommendationHistory.rank.asc())
        return list(session.execute(query).scalars().all())

    def _load_price_history(
        self,
        session,
        symbols: set[str],
        start_date: date,
        end_date: date,
    ) -> dict[str, dict[str, object]]:
        if not symbols:
            return {}

        rows = session.execute(
            select(PricesDaily.symbol, PricesDaily.date, PricesDaily.open, PricesDaily.close)
            .where(
                PricesDaily.symbol.in_(symbols),
                PricesDaily.date >= start_date,
                PricesDaily.date <= end_date,
            )
            .order_by(PricesDaily.symbol.asc(), PricesDaily.date.asc())
        ).all()

        history: dict[str, dict[str, object]] = {}
        for symbol, price_date, open_price, close in rows:
            if open_price is None and close is None:
                continue
            bucket = history.setdefault(symbol, {"dates": [], "open_prices": {}, "close_prices": {}, "prices": {}})
            bucket["dates"].append(price_date)
            if open_price is not None:
                bucket["open_prices"][price_date] = float(open_price)
            if close is not None:
                bucket["close_prices"][price_date] = float(close)
                bucket["prices"][price_date] = float(close)
        return history

    def _empty_report(
        self,
        model: str,
        start_date: date | None,
        end_date: date | None,
        benchmark_symbol: str | None,
    ) -> BacktestRunReport:
        backtest_config = BACKTEST_CONFIGS[model]
        empty_metrics = AggregateMetrics(0.0, 0.0, 0.0, 0.0, 0.0, 0, 0)
        return BacktestRunReport(
            model=model,
            start_date=start_date or date.today(),
            end_date=end_date or date.today(),
            trade_count=0,
            valid_trade_count=0,
            aggregate_by_horizon={field: empty_metrics for field, _ in backtest_config.horizons},
            benchmark_symbol=benchmark_symbol,
            benchmark_available=False,
            benchmark_by_horizon={field: empty_metrics for field, _ in backtest_config.horizons},
            alpha_by_horizon={field: None for field, _ in backtest_config.horizons},
            trades=[],
        )

    def _persist_report(
        self,
        session,
        report: BacktestRunReport,
        backtest_config: BacktestConfig,
    ) -> BacktestRunReport:
        primary = report.aggregate_by_horizon[backtest_config.primary_horizon]
        primary_benchmark = report.benchmark_by_horizon[backtest_config.primary_horizon]
        alpha = report.alpha_by_horizon.get(backtest_config.primary_horizon)

        config_json = {
            "model": report.model,
            "horizons": {field: periods for field, periods in backtest_config.horizons},
            "primary_horizon": backtest_config.primary_horizon,
            "aggregate_by_horizon": {
                field: asdict(metrics) for field, metrics in report.aggregate_by_horizon.items()
            },
            "benchmark": {
                "symbol": report.benchmark_symbol,
                "available": report.benchmark_available,
                "aggregate_by_horizon": {
                    field: asdict(metrics) for field, metrics in report.benchmark_by_horizon.items()
                },
                "alpha_by_horizon": report.alpha_by_horizon,
            },
            "trades": [
                {
                    "symbol": trade.symbol,
                    "signal_date": trade.signal_date.isoformat(),
                    "entry_date": trade.entry_date.isoformat(),
                    "entry_price": trade.entry_price,
                    "rank": trade.rank,
                    "score": trade.score,
                    "exit_dates": {
                        field: value.isoformat() if value is not None else None
                        for field, value in trade.exit_dates.items()
                    },
                    "exit_prices": trade.exit_prices,
                    **trade.returns,
                }
                for trade in report.trades
            ],
        }

        capital = self.config.raw.get("capital")
        portfolio_size = self.config.raw.get("portfolio", {}).get("swing_size")

        row = BacktestRuns(
            run_date=date.today(),
            model=report.model,
            start_date=report.start_date,
            end_date=report.end_date,
            capital=capital,
            portfolio_size=portfolio_size,
            total_return_pct=round(primary.avg_return * 100, 2),
            win_rate_pct=round(primary.win_rate * 100, 2),
            total_trades=report.trade_count,
            nifty_return_pct=(
                round(primary_benchmark.avg_return * 100, 2)
                if report.benchmark_available and primary_benchmark.valid_count > 0
                else None
            ),
            alpha_pct=round(alpha * 100, 2) if alpha is not None else None,
            config_json=config_json,
        )
        session.add(row)
        session.flush()
        return replace(report, backtest_run_id=row.id)
