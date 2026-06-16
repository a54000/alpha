#!/usr/bin/env python3
"""Stress test Swing V2.1 portfolio structures under transaction costs."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
import json
import math
from pathlib import Path
import statistics
import sys

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.backtesting.portfolio_backtest import PortfolioBacktestConfig, PortfolioBacktesterV1
from db.models import IndexPricesDaily
from db.session import build_session_factory


MODEL = "swing_v2_1"
OUTPUT_PATH = Path("reports/transaction_cost_stress_test.json")
COST_SCENARIOS = [0.0, 0.001, 0.0025, 0.005, 0.0075, 0.01]

VARIANTS = [
    ("top5_weekly", "Top 5 Weekly", PortfolioBacktestConfig(model=MODEL, portfolio_size=5)),
    ("top10_weekly", "Top 10 Weekly", PortfolioBacktestConfig(model=MODEL, portfolio_size=10)),
    (
        "top10_weekly_max2_sector",
        "Top 10 Weekly + Max 2 Positions Per Sector",
        PortfolioBacktestConfig(model=MODEL, portfolio_size=10, max_positions_per_sector=2, max_candidate_rank=50),
    ),
]


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def load_benchmark_return(start: date, end: date) -> dict[str, object]:
    with build_session_factory()() as session:
        rows = session.execute(
            select(IndexPricesDaily.date, IndexPricesDaily.open, IndexPricesDaily.close)
            .where(
                IndexPricesDaily.index_name == "NIFTY500",
                IndexPricesDaily.date >= start,
                IndexPricesDaily.date <= end,
            )
            .order_by(IndexPricesDaily.date.asc())
        ).all()
    if not rows:
        return {"available": False, "return": None, "start": None, "end": None}
    start_row = rows[0]
    end_row = rows[-1]
    start_price = float(start_row.open or start_row.close)
    end_price = float(end_row.close or end_row.open)
    benchmark_return = (end_price / start_price) - 1 if start_price else None
    return {
        "available": benchmark_return is not None,
        "return": benchmark_return,
        "start": start_row.date.isoformat(),
        "end": end_row.date.isoformat(),
        "start_price": start_price,
        "end_price": end_price,
    }


def adjusted_equity_curve(
    equity_curve: list[dict[str, object]],
    trades: list[dict[str, object]],
    cost_rate: float,
) -> list[dict[str, object]]:
    costs_by_date: dict[str, float] = defaultdict(float)
    for trade in trades:
        exit_date = str(trade["exit_date"])
        entry_value = float(trade.get("entry_value") or 0.0)
        costs_by_date[exit_date] += entry_value * cost_rate

    adjusted = []
    cumulative_cost = 0.0
    for row in equity_curve:
        row_date = str(row["date"])
        cumulative_cost += costs_by_date.get(row_date, 0.0)
        adjusted.append(
            {
                **row,
                "gross_equity": float(row["equity"]),
                "equity": float(row["equity"]) - cumulative_cost,
                "cumulative_cost": cumulative_cost,
            }
        )
    return adjusted


def path_metrics(equity_curve: list[dict[str, object]], initial_capital: float) -> dict[str, float]:
    if not equity_curve:
        return {
            "total_return": 0.0,
            "cagr": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "max_drawdown": 0.0,
        }
    equity_values = [float(row["equity"]) for row in equity_curve]
    returns = [
        (right / left) - 1
        for left, right in zip(equity_values, equity_values[1:])
        if left
    ]
    total_return = (equity_values[-1] / initial_capital) - 1
    days = max(1, len(equity_curve))
    cagr = (equity_values[-1] / initial_capital) ** (252 / days) - 1 if equity_values[-1] > 0 else -1.0
    volatility = statistics.stdev(returns) if len(returns) > 1 else 0.0
    sharpe = statistics.mean(returns) / volatility * math.sqrt(252) if volatility else 0.0
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
    return {
        "total_return": total_return,
        "cagr": cagr,
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "max_drawdown": max_drawdown,
    }


def trade_metrics(trades: list[dict[str, object]], cost_rate: float) -> dict[str, float]:
    net_returns = []
    for trade in trades:
        gross_return = float(trade.get("return") or 0.0)
        net_returns.append(gross_return - cost_rate)
    wins = [value for value in net_returns if value > 0]
    losses = [value for value in net_returns if value < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    return {
        "profit_factor": gross_profit / gross_loss if gross_loss else (float("inf") if gross_profit else 0.0),
        "average_trade_return": statistics.mean(net_returns) if net_returns else 0.0,
        "win_rate": len(wins) / len(net_returns) if net_returns else 0.0,
    }


def stress_variant(result: dict[str, object], benchmark_return: float | None) -> list[dict[str, object]]:
    rows = []
    initial_capital = float(result["config"]["initial_capital"])
    trades = result["closed_trades"]
    for cost_rate in COST_SCENARIOS:
        adjusted_curve = adjusted_equity_curve(result["equity_curve"], trades, cost_rate)
        metrics = {
            **path_metrics(adjusted_curve, initial_capital),
            **trade_metrics(trades, cost_rate),
        }
        metrics["alpha_vs_nifty500"] = (
            metrics["total_return"] - benchmark_return
            if benchmark_return is not None
            else None
        )
        metrics["cost_rate"] = cost_rate
        metrics["cost_percent"] = cost_rate * 100
        metrics["total_cost"] = adjusted_curve[-1]["cumulative_cost"] if adjusted_curve else 0.0
        metrics["closed_trades"] = len(trades)
        rows.append(metrics)
    return rows


def threshold_between(rows: list[dict[str, object]], field: str, target: float = 0.0) -> float | None:
    previous = None
    for row in rows:
        value = row[field]
        if value is None:
            continue
        value = float(value)
        cost = float(row["cost_rate"])
        if value <= target:
            if previous is None:
                return cost
            previous_value = float(previous[field])
            previous_cost = float(previous["cost_rate"])
            if previous_value == value:
                return cost
            fraction = (target - previous_value) / (value - previous_value)
            return previous_cost + fraction * (cost - previous_cost)
        previous = row
    return None


def build_conclusions(results: dict[str, list[dict[str, object]]]) -> dict[str, object]:
    zero_cost = {name: rows[0] for name, rows in results.items()}
    realistic_25bps = {name: next(row for row in rows if row["cost_rate"] == 0.0025) for name, rows in results.items()}
    best_25bps = max(realistic_25bps.items(), key=lambda item: float(item[1]["sharpe_ratio"]))
    best_zero = max(zero_cost.items(), key=lambda item: float(item[1]["sharpe_ratio"]))
    return {
        "best_zero_cost_by_sharpe": best_zero[0],
        "best_25bps_by_sharpe": best_25bps[0],
        "thresholds": {
            name: {
                "break_even_cost_total_return": threshold_between(rows, "total_return"),
                "alpha_disappears_cost": threshold_between(rows, "alpha_vs_nifty500"),
                "negative_cagr_cost": threshold_between(rows, "cagr"),
            }
            for name, rows in results.items()
        },
    }


def main() -> int:
    backtester = PortfolioBacktesterV1(build_session_factory())
    portfolio_results = {
        label: {"name": name, "result": backtester.run(config)}
        for label, name, config in VARIANTS
    }
    all_dates = [
        parse_date(str(row["date"]))
        for item in portfolio_results.values()
        for row in item["result"]["equity_curve"]
    ]
    benchmark = load_benchmark_return(min(all_dates), max(all_dates))
    benchmark_return = benchmark["return"] if benchmark["available"] else None

    stress_results = {
        label: stress_variant(item["result"], benchmark_return)
        for label, item in portfolio_results.items()
    }
    output = {
        "model": MODEL,
        "benchmark": benchmark,
        "methodology": {
            "cost_application": "round_trip_cost_rate_subtracted_once per completed trade using entry_value, recognized on exit_date",
            "alpha_definition": "cost_adjusted_portfolio_total_return_minus_nifty500_total_return_over_same_date_span",
            "entry": "next_trading_day_open",
            "exit": "close_after_20_trading_days",
            "rebalance": "weekly",
            "weighting": "equal_weight",
            "leverage": "none",
            "production_rules_modified": False,
        },
        "portfolio_structures": {
            label: {
                "name": item["name"],
                "config": item["result"]["config"],
                "gross_metrics": item["result"]["metrics"],
            }
            for label, item in portfolio_results.items()
        },
        "stress_results": stress_results,
        "conclusions": build_conclusions(stress_results),
    }
    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

