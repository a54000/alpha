#!/usr/bin/env python3
"""Research portfolio construction variants for Swing V2.1."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.backtesting.portfolio_backtest import PortfolioBacktestConfig, PortfolioBacktesterV1
from db.session import build_session_factory


MODEL = "swing_v2_1"
OUTPUT_PATH = Path("reports/portfolio_structure_results.json")

VARIANTS = [
    ("top5_weekly", 5, "weekly"),
    ("top10_weekly", 10, "weekly"),
    ("top5_biweekly", 5, "biweekly"),
    ("top10_biweekly", 10, "biweekly"),
    ("top5_monthly", 5, "monthly"),
    ("top10_monthly", 10, "monthly"),
]


def metric_row(label: str, result: dict[str, object]) -> dict[str, object]:
    metrics = result["metrics"]
    config = result["config"]
    return {
        "variant": label,
        "portfolio_size": config["portfolio_size"],
        "rebalance": config["rebalance"],
        "total_return": metrics["total_return"],
        "cagr": metrics["cagr"],
        "max_drawdown": metrics["max_drawdown"],
        "sharpe_ratio": metrics["sharpe_ratio"],
        "sortino_ratio": metrics["sortino_ratio"],
        "profit_factor": metrics["profit_factor"],
        "turnover": metrics["turnover"],
        "average_holding_period": metrics["average_holding_period"],
        "win_rate": metrics["win_rate"],
        "closed_trades": metrics["closed_trades"],
        "final_equity": metrics["final_equity"],
        "sector_concentration": metrics["sector_concentration"],
    }


def pct(value: float) -> float:
    return round(value * 100, 4)


def build_conclusions(rows: list[dict[str, object]]) -> dict[str, object]:
    best_sharpe = max(rows, key=lambda row: float(row["sharpe_ratio"]))
    best_cagr = max(rows, key=lambda row: float(row["cagr"]))
    best_total_return = max(rows, key=lambda row: float(row["total_return"]))
    lowest_drawdown = max(rows, key=lambda row: float(row["max_drawdown"]))
    lowest_turnover = min(rows, key=lambda row: float(row["turnover"]))

    weekly_top5 = next(row for row in rows if row["variant"] == "top5_weekly")
    weekly_top10 = next(row for row in rows if row["variant"] == "top10_weekly")
    monthly_top5 = next(row for row in rows if row["variant"] == "top5_monthly")
    monthly_top10 = next(row for row in rows if row["variant"] == "top10_monthly")

    return {
        "best_sharpe_variant": best_sharpe["variant"],
        "best_sharpe": best_sharpe["sharpe_ratio"],
        "best_cagr_variant": best_cagr["variant"],
        "best_cagr": best_cagr["cagr"],
        "best_total_return_variant": best_total_return["variant"],
        "best_total_return": best_total_return["total_return"],
        "lowest_drawdown_variant": lowest_drawdown["variant"],
        "lowest_max_drawdown": lowest_drawdown["max_drawdown"],
        "lowest_turnover_variant": lowest_turnover["variant"],
        "lowest_turnover": lowest_turnover["turnover"],
        "weekly_top5_cagr_minus_top10": float(weekly_top5["cagr"]) - float(weekly_top10["cagr"]),
        "weekly_top5_sharpe_minus_top10": float(weekly_top5["sharpe_ratio"]) - float(weekly_top10["sharpe_ratio"]),
        "monthly_top5_cagr_minus_top10": float(monthly_top5["cagr"]) - float(monthly_top10["cagr"]),
        "monthly_top5_sharpe_minus_top10": float(monthly_top5["sharpe_ratio"]) - float(monthly_top10["sharpe_ratio"]),
        "monthly_top10_cagr_minus_weekly_top10": float(monthly_top10["cagr"]) - float(weekly_top10["cagr"]),
        "monthly_top10_sharpe_minus_weekly_top10": float(monthly_top10["sharpe_ratio"]) - float(weekly_top10["sharpe_ratio"]),
        "formatted": {
            "best_sharpe": round(float(best_sharpe["sharpe_ratio"]), 4),
            "best_cagr_pct": pct(float(best_cagr["cagr"])),
            "best_total_return_pct": pct(float(best_total_return["total_return"])),
            "lowest_max_drawdown_pct": pct(float(lowest_drawdown["max_drawdown"])),
            "lowest_turnover": round(float(lowest_turnover["turnover"]), 4),
        },
    }


def main() -> int:
    backtester = PortfolioBacktesterV1(build_session_factory())
    rows: list[dict[str, object]] = []
    details: dict[str, object] = {}

    for label, portfolio_size, rebalance in VARIANTS:
        config = PortfolioBacktestConfig(
            model=MODEL,
            portfolio_size=portfolio_size,
            rebalance_frequency=rebalance,
        )
        result = backtester.run(config)
        rows.append(metric_row(label, result))
        details[label] = {
            "config": result["config"],
            "metrics": result["metrics"],
            "closed_trade_count": result["closed_trade_count"],
            "closed_trades_sample": result["closed_trades_sample"],
        }

    output = {
        "model": MODEL,
        "methodology": {
            "entry": "next_trading_day_open",
            "exit": "close_after_20_trading_days",
            "weighting": "equal_weight",
            "leverage": "none",
            "transaction_costs": "not_included",
            "slippage": "not_included",
        },
        "results": rows,
        "conclusions": build_conclusions(rows),
        "details": details,
    }

    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

