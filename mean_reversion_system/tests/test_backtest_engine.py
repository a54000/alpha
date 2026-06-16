from __future__ import annotations

from datetime import date

import pandas as pd

from mean_reversion_system.src.backtest.engine import BacktestResult, RealisticCommission, Trade, run_backtest
from mean_reversion_system.src.backtest.reporter import export_trade_log, generate_report, plot_drawdown_chart, plot_equity_curve, plot_monthly_returns_heatmap


def prepared_frame() -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=8, freq="D").date
    return pd.DataFrame(
        {
            "open": [100.0, 98.0, 99.0, 100.0, 101.0, 102.0, 103.0, 104.0],
            "high": [101.0, 100.0, 101.0, 103.0, 104.0, 105.0, 106.0, 107.0],
            "low": [99.0, 96.0, 97.0, 98.0, 99.0, 100.0, 101.0, 102.0],
            "close": [100.0, 99.0, 100.0, 102.0, 103.0, 104.0, 105.0, 106.0],
            "volume": [100_000] * 8,
            "atr": [2.0] * 8,
            "bb_mid": [103.0] * 8,
            "regime": ["ranging"] * 8,
            "long_signal": [True, False, False, False, False, False, False, False],
            "short_signal": [False] * 8,
        },
        index=index,
    )


def test_run_backtest_enters_next_day_open_and_exits_at_target(monkeypatch):
    frame = prepared_frame()
    monkeypatch.setattr("mean_reversion_system.src.backtest.engine._prepare_symbol_frame", lambda df, index_df=None: frame)

    result = run_backtest(["ABC"], date(2024, 1, 1), date(2024, 1, 8), initial_capital=1_000_000, daily_data={"ABC": frame})

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.signal_date == date(2024, 1, 1)
    assert trade.entry_date == date(2024, 1, 2)
    assert trade.entry_price == 98.0
    assert trade.exit_reason == "target"
    assert trade.exit_price == 103.0
    assert trade.costs > 0
    assert not result.equity_curve.empty


def test_run_backtest_stop_loss_exit(monkeypatch):
    frame = prepared_frame()
    frame.loc[date(2024, 1, 3), "low"] = 90.0
    monkeypatch.setattr("mean_reversion_system.src.backtest.engine._prepare_symbol_frame", lambda df, index_df=None: frame)

    result = run_backtest(["ABC"], date(2024, 1, 1), date(2024, 1, 8), initial_capital=1_000_000, daily_data={"ABC": frame})

    assert result.trades[0].exit_reason == "stop_loss"
    assert result.trades[0].exit_price == 95.0


def test_realistic_commission_uses_delivery_zero_brokerage():
    commission = RealisticCommission("delivery")

    assert commission.getcommission(1000, 100.0, side="round_trip") > 0
    assert commission.getcommission(1000, 100.0, side="buy") < commission.getcommission(1000, 100.0, side="round_trip")


def test_reporter_generates_metrics_and_exports_trade_log(tmp_path):
    trade = Trade(
        symbol="ABC",
        direction="long",
        signal_date=date(2024, 1, 1),
        entry_date=date(2024, 1, 2),
        exit_date=date(2024, 1, 5),
        entry_price=100.0,
        exit_price=105.0,
        quantity=100,
        gross_pnl=500.0,
        costs=50.0,
        net_pnl=450.0,
        return_pct=0.045,
        exit_reason="target",
        hold_days=3,
        regime="ranging",
    )
    result = BacktestResult(
        initial_capital=1_000_000,
        final_capital=1_000_450,
        trades=[trade],
        equity_curve=pd.DataFrame({"date": pd.date_range("2024-01-01", periods=5), "equity": [1_000_000, 999_000, 1_000_100, 1_000_200, 1_000_450]}),
        config={},
    )

    report = generate_report(result)
    output = export_trade_log(result, tmp_path / "trades.csv")

    assert report["trade_count"] == 1
    assert report["win_rate"] == 1.0
    assert report["regime_breakdown"] == {"ranging": 1.0}
    assert output.exists()
    assert plot_equity_curve(result) is not None
    assert plot_drawdown_chart(result) is not None
    assert plot_monthly_returns_heatmap(result) is not None
