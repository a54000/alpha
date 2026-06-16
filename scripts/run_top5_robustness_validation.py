#!/usr/bin/env python3
"""Validate robustness of Top 5 weekly versus Top 10 weekly Swing V2.1 portfolios."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
import json
import math
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.backtesting.portfolio_backtest import PortfolioBacktestConfig, PortfolioBacktesterV1
from db.session import build_session_factory


MODEL = "swing_v2_1"
OUTPUT_PATH = Path("reports/top5_robustness_validation.json")
COST_BPS = [0, 10, 25, 50, 75, 100]


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def daily_metrics(equity_curve: list[dict[str, object]], initial_equity: float | None = None) -> dict[str, float]:
    if len(equity_curve) < 2:
        return {
            "total_return": 0.0,
            "cagr": 0.0,
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
        }
    equity_values = [float(row["equity"]) for row in equity_curve]
    start = initial_equity if initial_equity is not None else equity_values[0]
    end = equity_values[-1]
    returns = [
        (right / left) - 1
        for left, right in zip(equity_values, equity_values[1:])
        if left
    ]
    total_return = (end / start) - 1 if start else 0.0
    days = max(1, len(equity_curve) - 1)
    cagr = (1 + total_return) ** (252 / days) - 1 if total_return > -1 else -1.0
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
        "max_drawdown": max_drawdown,
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
    }


def trade_metrics(trades: list[dict[str, object]]) -> dict[str, float | int]:
    returns = [float(trade["return"]) for trade in trades if trade.get("return") is not None]
    wins = [value for value in returns if value > 0]
    losses = [value for value in returns if value < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    return {
        "profit_factor": gross_profit / gross_loss if gross_loss else (float("inf") if gross_profit else 0.0),
        "win_rate": len(wins) / len(returns) if returns else 0.0,
        "closed_trades": len(returns),
    }


def combined_metrics(
    equity_curve: list[dict[str, object]],
    trades: list[dict[str, object]],
    initial_equity: float | None = None,
) -> dict[str, float | int]:
    return {
        **daily_metrics(equity_curve, initial_equity=initial_equity),
        **trade_metrics(trades),
    }


def split_periods(equity_curve: list[dict[str, object]]) -> list[tuple[str, date, date]]:
    dates = [parse_date(row["date"]) for row in equity_curve]
    one_third = len(dates) // 3
    two_thirds = one_third * 2
    return [
        ("first_third", dates[0], dates[one_third - 1]),
        ("middle_third", dates[one_third], dates[two_thirds - 1]),
        ("final_third", dates[two_thirds], dates[-1]),
    ]


def slice_equity(equity_curve: list[dict[str, object]], start: date, end: date) -> list[dict[str, object]]:
    return [
        row for row in equity_curve
        if start <= parse_date(str(row["date"])) <= end
    ]


def slice_trades(trades: list[dict[str, object]], start: date, end: date) -> list[dict[str, object]]:
    return [
        trade for trade in trades
        if start <= parse_date(str(trade["exit_date"])) <= end
    ]


def period_comparison(results: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    periods = split_periods(results["top10_weekly"]["equity_curve"])
    rows = []
    for label, start, end in periods:
        item: dict[str, object] = {
            "period": label,
            "start": start.isoformat(),
            "end": end.isoformat(),
        }
        for variant, result in results.items():
            equity = slice_equity(result["equity_curve"], start, end)
            trades = slice_trades(result["closed_trades"], start, end)
            item[variant] = combined_metrics(equity, trades, initial_equity=float(equity[0]["equity"]) if equity else None)
        item["alpha"] = {
            "cagr": float(item["top5_weekly"]["cagr"]) - float(item["top10_weekly"]["cagr"]),
            "sharpe": float(item["top5_weekly"]["sharpe_ratio"]) - float(item["top10_weekly"]["sharpe_ratio"]),
            "profit_factor": float(item["top5_weekly"]["profit_factor"]) - float(item["top10_weekly"]["profit_factor"]),
        }
        rows.append(item)
    return rows


def month_key(value: date) -> tuple[int, int]:
    return (value.year, value.month)


def month_end_curve(equity_curve: list[dict[str, object]]) -> list[dict[str, object]]:
    by_month: dict[tuple[int, int], dict[str, object]] = {}
    for row in equity_curve:
        row_date = parse_date(str(row["date"]))
        by_month[month_key(row_date)] = row
    return [by_month[key] for key in sorted(by_month)]


def rolling_windows(results: dict[str, dict[str, object]], months: int) -> list[dict[str, object]]:
    top10_months = month_end_curve(results["top10_weekly"]["equity_curve"])
    top5_months = month_end_curve(results["top5_weekly"]["equity_curve"])
    rows = []
    for index in range(months, min(len(top10_months), len(top5_months))):
        start_date = parse_date(str(top10_months[index - months]["date"]))
        end_date = parse_date(str(top10_months[index]["date"]))
        item: dict[str, object] = {
            "end_month": end_date.strftime("%Y-%m"),
            "window_months": months,
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
        }
        for variant, result in results.items():
            equity = slice_equity(result["equity_curve"], start_date, end_date)
            trades = slice_trades(result["closed_trades"], start_date, end_date)
            item[variant] = combined_metrics(equity, trades, initial_equity=float(equity[0]["equity"]) if equity else None)
        item["alpha"] = {
            "cagr": float(item["top5_weekly"]["cagr"]) - float(item["top10_weekly"]["cagr"]),
            "sharpe": float(item["top5_weekly"]["sharpe_ratio"]) - float(item["top10_weekly"]["sharpe_ratio"]),
            "profit_factor": float(item["top5_weekly"]["profit_factor"]) - float(item["top10_weekly"]["profit_factor"]),
        }
        rows.append(item)
    return rows


def sector_contribution(trades: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, float]] = defaultdict(lambda: {"pnl": 0.0, "trades": 0, "return_sum": 0.0, "wins": 0})
    total_pnl = 0.0
    for trade in trades:
        sector = str(trade.get("sector") or "UNKNOWN")
        pnl = float(trade.get("pnl") or 0.0)
        ret = float(trade.get("return") or 0.0)
        grouped[sector]["pnl"] += pnl
        grouped[sector]["trades"] += 1
        grouped[sector]["return_sum"] += ret
        grouped[sector]["wins"] += 1 if ret > 0 else 0
        total_pnl += pnl
    rows = []
    for sector, data in grouped.items():
        trades_count = int(data["trades"])
        rows.append(
            {
                "sector": sector,
                "total_pnl": data["pnl"],
                "pnl_share_of_net": data["pnl"] / total_pnl if total_pnl else 0.0,
                "trade_count": trades_count,
                "avg_return": data["return_sum"] / trades_count if trades_count else 0.0,
                "win_rate": data["wins"] / trades_count if trades_count else 0.0,
            }
        )
    return sorted(rows, key=lambda row: float(row["total_pnl"]), reverse=True)


def cost_sensitivity(results: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    rows = []
    for bps in COST_BPS:
        cost_rate = bps / 10_000
        row: dict[str, object] = {"cost_bps_per_traded_notional": bps}
        for variant, result in results.items():
            metrics = result["metrics"]
            turnover = float(metrics["turnover"])
            gross_total = float(metrics["total_return"])
            net_total = gross_total - (turnover * cost_rate)
            net_final = 1 + net_total
            days = max(1, len(result["equity_curve"]))
            net_cagr = net_final ** (252 / days) - 1 if net_final > 0 else -1.0
            row[variant] = {
                "gross_total_return": gross_total,
                "net_total_return_estimate": net_total,
                "net_cagr_estimate": net_cagr,
                "turnover": turnover,
                "estimated_cost_drag": turnover * cost_rate,
            }
        row["alpha"] = {
            "net_total_return": float(row["top5_weekly"]["net_total_return_estimate"]) - float(row["top10_weekly"]["net_total_return_estimate"]),
            "net_cagr": float(row["top5_weekly"]["net_cagr_estimate"]) - float(row["top10_weekly"]["net_cagr_estimate"]),
        }
        rows.append(row)
    return rows


def summarize_rolling(rows: list[dict[str, object]]) -> dict[str, object]:
    positive_alpha = [row for row in rows if float(row["alpha"]["cagr"]) > 0]
    return {
        "windows": len(rows),
        "top5_positive_cagr_alpha_windows": len(positive_alpha),
        "top5_positive_cagr_alpha_ratio": len(positive_alpha) / len(rows) if rows else 0.0,
        "best_top5_alpha": max((float(row["alpha"]["cagr"]) for row in rows), default=0.0),
        "worst_top5_alpha": min((float(row["alpha"]["cagr"]) for row in rows), default=0.0),
        "top5_best_window": max(rows, key=lambda row: float(row["alpha"]["cagr"]))["end_month"] if rows else None,
        "top5_worst_window": min(rows, key=lambda row: float(row["alpha"]["cagr"]))["end_month"] if rows else None,
    }


def main() -> int:
    backtester = PortfolioBacktesterV1(build_session_factory())
    results = {
        "top10_weekly": backtester.run(PortfolioBacktestConfig(model=MODEL, portfolio_size=10)),
        "top5_weekly": backtester.run(PortfolioBacktestConfig(model=MODEL, portfolio_size=5)),
    }
    time_splits = period_comparison(results)
    rolling_6m = rolling_windows(results, 6)
    rolling_12m = rolling_windows(results, 12)
    sectors = {
        variant: sector_contribution(result["closed_trades"])
        for variant, result in results.items()
    }
    costs = cost_sensitivity(results)
    top5 = results["top5_weekly"]["metrics"]
    top10 = results["top10_weekly"]["metrics"]

    output = {
        "model": MODEL,
        "variants": {
            variant: {
                "config": result["config"],
                "metrics": result["metrics"],
                "closed_trade_count": result["closed_trade_count"],
            }
            for variant, result in results.items()
        },
        "headline_alpha_top5_minus_top10": {
            "cagr": float(top5["cagr"]) - float(top10["cagr"]),
            "sharpe_ratio": float(top5["sharpe_ratio"]) - float(top10["sharpe_ratio"]),
            "max_drawdown": float(top5["max_drawdown"]) - float(top10["max_drawdown"]),
            "profit_factor": float(top5["profit_factor"]) - float(top10["profit_factor"]),
            "total_return": float(top5["total_return"]) - float(top10["total_return"]),
        },
        "time_splits": time_splits,
        "rolling_6_month_windows": rolling_6m,
        "rolling_12_month_windows": rolling_12m,
        "rolling_summary": {
            "six_month": summarize_rolling(rolling_6m),
            "twelve_month": summarize_rolling(rolling_12m),
        },
        "sector_contribution": sectors,
        "transaction_cost_sensitivity": costs,
        "methodology": {
            "alpha_definition": "top5_weekly_minus_top10_weekly",
            "transaction_cost_model": "approximate cost drag = turnover * cost_bps_per_traded_notional; intraperiod timing not modeled",
            "entry": "next_trading_day_open",
            "exit": "close_after_20_trading_days",
            "weighting": "equal_weight",
            "leverage": "none",
        },
    }

    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

