"""Backtest reporting and export utilities."""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from mean_reversion_system.src.backtest.engine import BacktestResult, Trade


@dataclass(frozen=True)
class MonteCarloResult:
    """Monte Carlo trade-return simulation result.

    Args:
        simulations: Simulated final equity values.
        fifth_percentile_cagr: Conservative CAGR estimate.
        ninety_fifth_percentile_drawdown: Adverse drawdown estimate.
        probability_of_ruin: Fraction of simulations with drawdown worse than 30%.
        equity_fans: Simulated equity paths.

    Returns:
        MonteCarloResult instance.

    Raises:
        RuntimeError: Never raised.
    """

    simulations: list[float]
    fifth_percentile_cagr: float
    ninety_fifth_percentile_drawdown: float
    probability_of_ruin: float
    equity_fans: list[list[float]]


def _trade_rows(trades: list[Trade]) -> list[dict[str, Any]]:
    """Convert trade objects to serialisable rows.

    Args:
        trades: Completed trades.

    Returns:
        List of row dictionaries.

    Raises:
        RuntimeError: Never raised.
    """

    return [trade.__dict__.copy() for trade in trades]


def _max_drawdown(equity: pd.Series) -> tuple[float, int]:
    """Calculate max drawdown and duration.

    Args:
        equity: Equity curve series.

    Returns:
        Tuple of max drawdown fraction and duration in bars.

    Raises:
        RuntimeError: Never raised.
    """

    if equity.empty:
        return 0.0, 0
    high_water = equity.cummax()
    drawdown = equity / high_water - 1
    max_dd = float(drawdown.min())
    duration = 0
    max_duration = 0
    for value in drawdown:
        if value < 0:
            duration += 1
            max_duration = max(max_duration, duration)
        else:
            duration = 0
    return max_dd, max_duration


def generate_report(backtest_result: BacktestResult) -> dict[str, Any]:
    """Generate summary performance metrics.

    Args:
        backtest_result: Backtest result object.

    Returns:
        Dictionary with return, risk, and trade metrics.

    Raises:
        RuntimeError: Never raised.
    """

    equity_curve = backtest_result.equity_curve.copy()
    trades = backtest_result.trades
    if equity_curve.empty:
        total_return = backtest_result.final_capital / backtest_result.initial_capital - 1
        return {"total_return": total_return, "trade_count": len(trades)}

    equity = pd.to_numeric(equity_curve["equity"], errors="coerce")
    dates = pd.to_datetime(equity_curve["date"])
    years = max((dates.max() - dates.min()).days / 365.25, 1 / 365.25)
    total_return = float(equity.iloc[-1] / backtest_result.initial_capital - 1)
    cagr = float((equity.iloc[-1] / backtest_result.initial_capital) ** (1 / years) - 1)
    returns = equity.pct_change().dropna()
    risk_free_daily = 0.065 / 252
    sharpe = float(((returns.mean() - risk_free_daily) / returns.std()) * math.sqrt(252)) if len(returns) > 1 and returns.std() else 0.0
    downside = returns.loc[returns < 0]
    sortino = float(((returns.mean() - risk_free_daily) / downside.std()) * math.sqrt(252)) if len(downside) > 1 and downside.std() else 0.0
    max_dd, dd_duration = _max_drawdown(equity)
    wins = [trade for trade in trades if trade.net_pnl > 0]
    losses = [trade for trade in trades if trade.net_pnl < 0]
    gross_win = sum(trade.net_pnl for trade in wins)
    gross_loss = abs(sum(trade.net_pnl for trade in losses))
    regime_counts: dict[str, int] = {}
    for trade in trades:
        regime_counts[trade.regime] = regime_counts.get(trade.regime, 0) + 1
    return {
        "cagr": cagr,
        "total_return": total_return,
        "max_drawdown": max_dd,
        "drawdown_duration_days": int(dd_duration),
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "calmar_ratio": float(cagr / abs(max_dd)) if max_dd else 0.0,
        "win_rate": len(wins) / len(trades) if trades else 0.0,
        "avg_win": gross_win / len(wins) if wins else 0.0,
        "avg_loss": -gross_loss / len(losses) if losses else 0.0,
        "profit_factor": gross_win / gross_loss if gross_loss else 0.0,
        "avg_hold_days": sum(trade.hold_days for trade in trades) / len(trades) if trades else 0.0,
        "max_consecutive_losses": _max_consecutive_losses(trades),
        "trade_count": len(trades),
        "regime_breakdown": {key: value / len(trades) for key, value in regime_counts.items()} if trades else {},
    }


def _max_consecutive_losses(trades: list[Trade]) -> int:
    """Calculate max consecutive losing trades.

    Args:
        trades: Completed trades.

    Returns:
        Maximum loss streak length.

    Raises:
        RuntimeError: Never raised.
    """

    current = 0
    maximum = 0
    for trade in trades:
        if trade.net_pnl < 0:
            current += 1
            maximum = max(maximum, current)
        else:
            current = 0
    return maximum


def plot_equity_curve(backtest_result: BacktestResult):
    """Build an equity curve figure.

    Args:
        backtest_result: Backtest result object.

    Returns:
        Plotly figure or dict fallback.

    Raises:
        RuntimeError: Never raised.
    """

    try:
        import plotly.graph_objects as go  # type: ignore

        fig = go.Figure()
        fig.add_scatter(x=backtest_result.equity_curve["date"], y=backtest_result.equity_curve["equity"], mode="lines", name="Equity")
        return fig
    except Exception:
        return {"type": "equity_curve", "rows": backtest_result.equity_curve.to_dict("records")}


def plot_drawdown_chart(backtest_result: BacktestResult):
    """Build a drawdown figure.

    Args:
        backtest_result: Backtest result object.

    Returns:
        Plotly figure or dict fallback.

    Raises:
        RuntimeError: Never raised.
    """

    equity = pd.to_numeric(backtest_result.equity_curve["equity"], errors="coerce")
    drawdown = equity / equity.cummax() - 1
    try:
        import plotly.graph_objects as go  # type: ignore

        fig = go.Figure()
        fig.add_scatter(x=backtest_result.equity_curve["date"], y=drawdown, mode="lines", name="Drawdown")
        return fig
    except Exception:
        return {"type": "drawdown", "values": drawdown.tolist()}


def plot_monthly_returns_heatmap(backtest_result: BacktestResult):
    """Build a monthly returns heatmap.

    Args:
        backtest_result: Backtest result object.

    Returns:
        Plotly figure or dict fallback.

    Raises:
        RuntimeError: Never raised.
    """

    item = backtest_result.equity_curve.copy()
    item["date"] = pd.to_datetime(item["date"])
    monthly = item.set_index("date")["equity"].resample("ME").last().pct_change().dropna()
    try:
        import plotly.express as px  # type: ignore

        frame = pd.DataFrame({"year": monthly.index.year, "month": monthly.index.month, "return": monthly.values})
        return px.density_heatmap(frame, x="month", y="year", z="return")
    except Exception:
        return {"type": "monthly_returns", "values": monthly.to_dict()}


def export_trade_log(backtest_result: BacktestResult, path: str | Path) -> Path:
    """Export completed trades to CSV.

    Args:
        backtest_result: Backtest result object.
        path: Output CSV path.

    Returns:
        Output path.

    Raises:
        OSError: If the file cannot be written.
    """

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = _trade_rows(backtest_result.trades)
    fieldnames = list(rows[0].keys()) if rows else ["symbol", "direction", "signal_date", "entry_date", "exit_date", "net_pnl"]
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return output


def run_monte_carlo(trade_log: list[Trade] | pd.DataFrame, n_simulations: int = 5000, initial_capital: float = 1_000_000, seed: int = 42) -> MonteCarloResult:
    """Run bootstrap Monte Carlo on trade returns.

    Args:
        trade_log: Completed trades or trade DataFrame with return_pct.
        n_simulations: Number of simulations.
        initial_capital: Starting capital.
        seed: Random seed.

    Returns:
        MonteCarloResult with summary risk statistics.

    Raises:
        ValueError: If n_simulations or initial_capital is invalid.
    """

    if n_simulations <= 0 or initial_capital <= 0:
        raise ValueError("n_simulations and initial_capital must be positive")
    if isinstance(trade_log, pd.DataFrame):
        returns = pd.to_numeric(trade_log.get("return_pct", pd.Series(dtype=float)), errors="coerce").dropna().to_numpy()
    else:
        returns = np.array([trade.return_pct for trade in trade_log], dtype=float)
    if len(returns) == 0:
        return MonteCarloResult([], 0.0, 0.0, 0.0, [])

    rng = np.random.default_rng(seed)
    finals: list[float] = []
    drawdowns: list[float] = []
    fans: list[list[float]] = []
    for _ in range(n_simulations):
        sampled = rng.choice(returns, size=len(returns), replace=True)
        equity = [float(initial_capital)]
        for trade_return in sampled:
            equity.append(equity[-1] * (1 + float(trade_return)))
        series = pd.Series(equity)
        drawdown = float((series / series.cummax() - 1).min())
        finals.append(float(equity[-1]))
        drawdowns.append(drawdown)
        fans.append(equity)

    cagr_values = [(final / initial_capital) - 1 for final in finals]
    return MonteCarloResult(
        simulations=finals,
        fifth_percentile_cagr=float(np.percentile(cagr_values, 5)),
        ninety_fifth_percentile_drawdown=float(np.percentile(drawdowns, 5)),
        probability_of_ruin=float(np.mean(np.array(drawdowns) < -0.30)),
        equity_fans=fans,
    )


def plot_monte_carlo_fans(mc_result: MonteCarloResult):
    """Build a Monte Carlo fan-chart figure.

    Args:
        mc_result: Monte Carlo simulation result.

    Returns:
        Plotly figure or dict fallback.

    Raises:
        RuntimeError: Never raised.
    """

    try:
        import plotly.graph_objects as go  # type: ignore

        fig = go.Figure()
        for path in mc_result.equity_fans[:100]:
            fig.add_scatter(y=path, mode="lines", opacity=0.15, showlegend=False)
        return fig
    except Exception:
        return {"type": "monte_carlo_fans", "paths": mc_result.equity_fans[:10]}


def export_validation_results(payload: dict[str, Any], output_dir: str | Path, stem: str) -> dict[str, Path]:
    """Export validation payload to JSON and flattened CSV.

    Args:
        payload: Serializable validation payload.
        output_dir: Output directory.
        stem: File stem.

    Returns:
        Paths for json and csv outputs.

    Raises:
        OSError: If files cannot be written.
    """

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / f"{stem}.json"
    csv_path = root / f"{stem}.csv"
    json_path.write_text(json.dumps(payload, default=str, indent=2), encoding="utf-8")
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else [payload]
    frame = pd.DataFrame(rows)
    frame.to_csv(csv_path, index=False)
    return {"json": json_path, "csv": csv_path}
