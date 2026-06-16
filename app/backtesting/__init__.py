"""Backtesting engine for recommendation performance analysis."""

from app.backtesting.run_backtest import (
    BacktestRunner,
    BacktestRunReport,
    SWING_BACKTEST_CONFIG,
    POSITIONAL_BACKTEST_CONFIG,
    aggregate_metrics,
    compute_return,
    forward_trading_day_return,
    write_backtest_report,
)

__all__ = [
    "BacktestRunner",
    "BacktestRunReport",
    "SWING_BACKTEST_CONFIG",
    "POSITIONAL_BACKTEST_CONFIG",
    "aggregate_metrics",
    "compute_return",
    "forward_trading_day_return",
    "write_backtest_report",
]
