from __future__ import annotations

from datetime import date

import pandas as pd

from mean_reversion_system.src.backtest.engine import BacktestResult, Trade, run_regime_stress, run_sensitivity, run_walk_forward
from mean_reversion_system.src.backtest.reporter import export_validation_results, plot_monte_carlo_fans, run_monte_carlo


def make_trade(symbol: str, entry_date: date, return_pct: float, regime: str = "ranging") -> Trade:
    return Trade(
        symbol=symbol,
        direction="long",
        signal_date=entry_date,
        entry_date=entry_date,
        exit_date=entry_date,
        entry_price=100.0,
        exit_price=100.0 * (1 + return_pct),
        quantity=100,
        gross_pnl=return_pct * 10_000,
        costs=10.0,
        net_pnl=return_pct * 10_000 - 10.0,
        return_pct=return_pct,
        exit_reason="target" if return_pct > 0 else "stop_loss",
        hold_days=3,
        regime=regime,
    )


def fake_result(start: date, end: date, trade_return: float = 0.02) -> BacktestResult:
    dates = pd.date_range(start, end, freq="D")
    if len(dates) == 0:
        dates = pd.DatetimeIndex([pd.Timestamp(start)])
    equity = [1_000_000 + index * 1000 for index in range(len(dates))]
    return BacktestResult(
        initial_capital=1_000_000,
        final_capital=float(equity[-1]),
        trades=[make_trade("ABC", start, trade_return)],
        equity_curve=pd.DataFrame({"date": dates, "equity": equity}),
        config={},
    )


def test_run_walk_forward_builds_is_oos_windows(monkeypatch):
    calls: list[tuple[date, date]] = []

    def fake_run_backtest(universe, start_date, end_date, initial_capital=1_000_000, daily_data=None, index_df=None):
        calls.append((start_date, end_date))
        return fake_result(start_date, end_date)

    monkeypatch.setattr("mean_reversion_system.src.backtest.engine.run_backtest", fake_run_backtest)

    results = run_walk_forward(["ABC"], date(2021, 1, 1), date(2022, 12, 31), is_months=6, oos_months=3)

    assert results
    assert calls[0] == (date(2021, 1, 1), date(2021, 6, 30))
    assert results[0].test_start == date(2021, 7, 1)
    assert hasattr(results[0], "degraded")


def test_run_monte_carlo_reports_ruin_probability_and_fan_chart():
    trades = [make_trade("ABC", date(2024, 1, 1), value) for value in [0.02, -0.01, 0.03, -0.02, 0.01]]

    result = run_monte_carlo(trades, n_simulations=100, initial_capital=1_000_000, seed=7)

    assert len(result.simulations) == 100
    assert 0 <= result.probability_of_ruin <= 1
    assert plot_monte_carlo_fans(result) is not None


def test_run_sensitivity_returns_base_and_variants(monkeypatch):
    monkeypatch.setattr("mean_reversion_system.src.backtest.engine.run_backtest", lambda *args, **kwargs: fake_result(date(2024, 1, 1), date(2024, 3, 1)))

    result = run_sensitivity({"rsi_oversold": 30}, ["ABC"], date(2024, 1, 1), date(2024, 3, 1))

    assert "trade_count" in result.base_metrics
    assert set(result.variants) == {"rsi_oversold_0.8x", "rsi_oversold_1.2x"}


def test_run_regime_stress_summarises_trending_trade_share(monkeypatch):
    def fake_run_backtest(universe, start_date, end_date, initial_capital=1_000_000, daily_data=None, index_df=None):
        trade_return = -0.01 if start_date.year == 2021 else 0.02
        return fake_result(start_date, end_date, trade_return=trade_return)

    monkeypatch.setattr("mean_reversion_system.src.backtest.engine.run_backtest", fake_run_backtest)

    result = run_regime_stress(
        ["ABC"],
        trending_periods=[("trend_up", date(2021, 1, 1), date(2021, 3, 1))],
        ranging_periods=[("range", date(2024, 1, 1), date(2024, 3, 1))],
    )

    assert result.total_trades == 2
    assert result.trending_trade_pct == 0.5
    assert result.periods[0]["regime_type"] == "trending"


def test_export_validation_results_writes_json_and_csv(tmp_path):
    paths = export_validation_results({"rows": [{"window": 1, "sharpe": 1.2}]}, tmp_path, "wf")

    assert paths["json"].exists()
    assert paths["csv"].exists()
