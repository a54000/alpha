#!/usr/bin/env python3
"""Phase 2G walk-forward validation from Phase 2E portfolio artifacts."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from datetime import date
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]

PERIODS = [
    ("period_1", date(2022, 5, 25), date(2023, 12, 31)),
    ("period_2", date(2024, 1, 1), date(2025, 6, 30)),
    ("period_3", date(2025, 7, 1), date(2026, 6, 11)),
]
VARIANTS = ["top5_weekly", "top10_weekly"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Phase 2G walk-forward validation.")
    parser.add_argument("--trades-csv", default="reports/phase2e_trade_ledger.csv")
    parser.add_argument("--equity-csv", default="reports/phase2e_equity_curves.csv")
    parser.add_argument("--metrics-json", default="reports/phase2e_portfolio_metrics.json")
    parser.add_argument("--output-json", default="reports/phase2g_walk_forward.json")
    return parser.parse_args()


def load_inputs(args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    trades = pd.read_csv(REPO_ROOT / args.trades_csv)
    equity = pd.read_csv(REPO_ROOT / args.equity_csv)
    metrics = json.loads((REPO_ROOT / args.metrics_json).read_text(encoding="utf-8"))
    for frame in [trades, equity]:
        for column in frame.columns:
            if column.endswith("_date") or column == "date":
                frame[column] = pd.to_datetime(frame[column], errors="coerce").dt.date
    for column in ["return", "pnl"]:
        trades[column] = pd.to_numeric(trades[column], errors="coerce")
    equity["equity"] = pd.to_numeric(equity["equity"], errors="coerce")
    return trades, equity, metrics


def max_drawdown(values: list[float]) -> float:
    if not values:
        return 0.0
    peak = values[0]
    drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        if peak:
            drawdown = min(drawdown, (value / peak) - 1)
    return drawdown


def monthly_win_rate(frame: pd.DataFrame) -> float:
    if frame.empty:
        return 0.0
    item = frame.copy()
    item["month"] = pd.to_datetime(item["date"]).dt.to_period("M").astype(str)
    month_ends = item.groupby("month", sort=True).tail(1)
    returns = month_ends["equity"].pct_change().dropna()
    return float((returns > 0).mean()) if len(returns) else 0.0


def period_metrics(equity: pd.DataFrame, trades: pd.DataFrame, variant: str, start: date, end: date) -> dict[str, object]:
    eq = equity[(equity["variant"] == variant) & (equity["date"] >= start) & (equity["date"] <= end)].sort_values("date")
    tr = trades[(trades["variant"] == variant) & (trades["exit_date"] >= start) & (trades["exit_date"] <= end)]
    if len(eq) < 2:
        return {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "trading_days": int(len(eq)),
            "total_return": 0.0,
            "cagr": 0.0,
            "sharpe": 0.0,
            "max_drawdown": 0.0,
            "profit_factor": 0.0,
            "monthly_win_rate": 0.0,
            "trade_count": int(len(tr)),
        }

    equity_values = eq["equity"].astype(float).tolist()
    returns = [(right / left) - 1 for left, right in zip(equity_values, equity_values[1:]) if left]
    start_equity = equity_values[0]
    end_equity = equity_values[-1]
    total_return = (end_equity / start_equity) - 1 if start_equity else 0.0
    days = max(1, len(eq) - 1)
    cagr = (1 + total_return) ** (252 / days) - 1 if total_return > -1 else -1.0
    stdev = statistics.stdev(returns) if len(returns) > 1 else 0.0
    sharpe = statistics.mean(returns) / stdev * math.sqrt(252) if stdev else 0.0
    trade_returns = tr["return"].dropna().astype(float).tolist()
    wins = [value for value in trade_returns if value > 0]
    losses = [value for value in trade_returns if value < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = gross_profit / gross_loss if gross_loss else (float("inf") if gross_profit else 0.0)
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "trading_days": int(len(eq)),
        "total_return": total_return,
        "cagr": cagr,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown(equity_values),
        "profit_factor": profit_factor,
        "monthly_win_rate": monthly_win_rate(eq),
        "trade_count": int(len(tr)),
        "start_equity": start_equity,
        "end_equity": end_equity,
    }


def summarize_stability(rows: dict[str, dict[str, object]]) -> dict[str, object]:
    output = {}
    for variant, periods in rows.items():
        cagr_values = [float(item["cagr"]) for item in periods.values()]
        sharpe_values = [float(item["sharpe"]) for item in periods.values()]
        pf_values = [float(item["profit_factor"]) for item in periods.values()]
        output[variant] = {
            "positive_cagr_periods": sum(1 for value in cagr_values if value > 0),
            "positive_sharpe_periods": sum(1 for value in sharpe_values if value > 0),
            "profit_factor_above_1_periods": sum(1 for value in pf_values if value > 1),
            "min_cagr": min(cagr_values),
            "max_cagr": max(cagr_values),
            "cagr_range": max(cagr_values) - min(cagr_values),
            "min_sharpe": min(sharpe_values),
            "max_drawdown_worst": min(float(item["max_drawdown"]) for item in periods.values()),
            "edge_disappears": any(value <= 0 for value in cagr_values) or any(value <= 1 for value in pf_values),
        }
    top5 = output.get("top5_weekly", {})
    top10 = output.get("top10_weekly", {})
    output["comparison"] = {
        "more_stable_by_cagr_range": "top5_weekly"
        if float(top5.get("cagr_range", 0)) < float(top10.get("cagr_range", 0))
        else "top10_weekly",
        "more_stable_by_worst_drawdown": "top5_weekly"
        if float(top5.get("max_drawdown_worst", 0)) > float(top10.get("max_drawdown_worst", 0))
        else "top10_weekly",
        "edge_disappears_any_variant": bool(top5.get("edge_disappears")) or bool(top10.get("edge_disappears")),
    }
    return output


def main() -> int:
    args = parse_args()
    trades, equity, metrics = load_inputs(args)
    periods = {}
    for variant in VARIANTS:
        periods[variant] = {
            label: period_metrics(equity, trades, variant, start, end)
            for label, start, end in PERIODS
        }
    output = {
        "generated_on": date.today().isoformat(),
        "mode": "phase2g_walk_forward_validation",
        "inputs": {
            "trades_csv": args.trades_csv,
            "equity_csv": args.equity_csv,
            "metrics_json": args.metrics_json,
        },
        "constraints": {
            "scoring_changed": False,
            "parameters_optimized": False,
            "filters_added": False,
            "production_tables_modified": False,
        },
        "source_overall_metrics": {
            variant: metrics["variants"][variant]["metrics"]
            for variant in VARIANTS
        },
        "periods": periods,
        "stability_summary": summarize_stability(periods),
    }
    path = REPO_ROOT / args.output_json
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
