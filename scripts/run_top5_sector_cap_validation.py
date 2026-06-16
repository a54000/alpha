#!/usr/bin/env python3
"""Validate Top 5 weekly sector cap structure for Swing V2.1."""

from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.backtesting.portfolio_backtest import PortfolioBacktestConfig, PortfolioBacktesterV1
from db.session import build_session_factory


MODEL = "swing_v2_1"
OUTPUT_PATH = Path("reports/top5_sector_cap_validation.json")

VARIANTS = [
    ("top10_weekly", "Top 10 Weekly", PortfolioBacktestConfig(model=MODEL, portfolio_size=10)),
    ("top5_weekly", "Top 5 Weekly", PortfolioBacktestConfig(model=MODEL, portfolio_size=5)),
    (
        "top10_weekly_max2_sector",
        "Top 10 Weekly + Max 2 Per Sector",
        PortfolioBacktestConfig(model=MODEL, portfolio_size=10, max_positions_per_sector=2, max_candidate_rank=50),
    ),
    (
        "top5_weekly_max2_sector",
        "Top 5 Weekly + Max 2 Per Sector",
        PortfolioBacktestConfig(model=MODEL, portfolio_size=5, max_positions_per_sector=2, max_candidate_rank=50),
    ),
]


def sector_contribution(trades: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, float]] = defaultdict(lambda: {"pnl": 0.0, "trades": 0, "wins": 0, "returns": 0.0})
    total_pnl = 0.0
    for trade in trades:
        sector = str(trade.get("sector") or "UNKNOWN")
        pnl = float(trade.get("pnl") or 0.0)
        ret = float(trade.get("return") or 0.0)
        grouped[sector]["pnl"] += pnl
        grouped[sector]["trades"] += 1
        grouped[sector]["wins"] += 1 if ret > 0 else 0
        grouped[sector]["returns"] += ret
        total_pnl += pnl
    rows = []
    for sector, data in grouped.items():
        trades = int(data["trades"])
        rows.append(
            {
                "sector": sector,
                "total_pnl": data["pnl"],
                "pnl_share_of_net": data["pnl"] / total_pnl if total_pnl else 0.0,
                "trade_count": trades,
                "avg_return": data["returns"] / trades if trades else 0.0,
                "win_rate": data["wins"] / trades if trades else 0.0,
            }
        )
    return sorted(rows, key=lambda row: float(row["total_pnl"]), reverse=True)


def metric_row(label: str, name: str, result: dict[str, object]) -> dict[str, object]:
    metrics = result["metrics"]
    concentration = metrics["sector_concentration"]
    return {
        "variant": label,
        "name": name,
        "portfolio_size": result["config"]["portfolio_size"],
        "max_positions_per_sector": result["config"].get("max_positions_per_sector"),
        "total_return": metrics["total_return"],
        "cagr": metrics["cagr"],
        "sharpe_ratio": metrics["sharpe_ratio"],
        "sortino_ratio": metrics["sortino_ratio"],
        "max_drawdown": metrics["max_drawdown"],
        "profit_factor": metrics["profit_factor"],
        "win_rate": metrics["win_rate"],
        "turnover": metrics["turnover"],
        "closed_trades": metrics["closed_trades"],
        "final_equity": metrics["final_equity"],
        "top_sector": concentration["top_sector"],
        "top_sector_avg_weight": concentration["top_sector_avg_weight"],
        "top_3_sector_avg_weight": concentration["top_3_avg_weight"],
        "sector_contribution": sector_contribution(result["closed_trades"]),
    }


def add_alpha(rows: list[dict[str, object]]) -> None:
    baseline = next(row for row in rows if row["variant"] == "top10_weekly")
    for row in rows:
        row["alpha_vs_top10_weekly"] = {
            "cagr": float(row["cagr"]) - float(baseline["cagr"]),
            "total_return": float(row["total_return"]) - float(baseline["total_return"]),
            "sharpe_ratio": float(row["sharpe_ratio"]) - float(baseline["sharpe_ratio"]),
            "sortino_ratio": float(row["sortino_ratio"]) - float(baseline["sortino_ratio"]),
            "max_drawdown": float(row["max_drawdown"]) - float(baseline["max_drawdown"]),
            "profit_factor": float(row["profit_factor"]) - float(baseline["profit_factor"]),
        }


def build_conclusions(rows: list[dict[str, object]]) -> dict[str, object]:
    best_cagr = max(rows, key=lambda row: float(row["cagr"]))
    best_sharpe = max(rows, key=lambda row: float(row["sharpe_ratio"]))
    best_sortino = max(rows, key=lambda row: float(row["sortino_ratio"]))
    best_pf = max(rows, key=lambda row: float(row["profit_factor"]))
    lowest_drawdown = max(rows, key=lambda row: float(row["max_drawdown"]))
    baseline = next(row for row in rows if row["variant"] == "top10_weekly")
    top5 = next(row for row in rows if row["variant"] == "top5_weekly")
    top10_cap = next(row for row in rows if row["variant"] == "top10_weekly_max2_sector")
    top5_cap = next(row for row in rows if row["variant"] == "top5_weekly_max2_sector")
    return {
        "best_overall_by_sharpe": best_sharpe["variant"],
        "best_cagr": best_cagr["variant"],
        "best_sortino": best_sortino["variant"],
        "best_profit_factor": best_pf["variant"],
        "lowest_drawdown": lowest_drawdown["variant"],
        "top10_cap_sharpe_delta": float(top10_cap["sharpe_ratio"]) - float(baseline["sharpe_ratio"]),
        "top5_cap_sharpe_delta": float(top5_cap["sharpe_ratio"]) - float(top5["sharpe_ratio"]),
        "top10_cap_financial_weight_delta": float(top10_cap["top_sector_avg_weight"]) - float(baseline["top_sector_avg_weight"]),
        "top5_cap_financial_weight_delta": float(top5_cap["top_sector_avg_weight"]) - float(top5["top_sector_avg_weight"]),
        "top5_cap_is_new_champion": best_sharpe["variant"] == "top5_weekly_max2_sector",
    }


def main() -> int:
    backtester = PortfolioBacktesterV1(build_session_factory())
    rows: list[dict[str, object]] = []
    details: dict[str, object] = {}
    for label, name, config in VARIANTS:
        result = backtester.run(config)
        rows.append(metric_row(label, name, result))
        details[label] = {
            "config": result["config"],
            "metrics": result["metrics"],
            "closed_trade_count": result["closed_trade_count"],
            "closed_trades_sample": result["closed_trades_sample"],
        }
    add_alpha(rows)
    output = {
        "model": MODEL,
        "methodology": {
            "entry": "next_trading_day_open",
            "exit": "close_after_20_trading_days",
            "rebalance": "weekly",
            "weighting": "equal_weight",
            "leverage": "none",
            "transaction_costs": "not_included",
            "alpha_definition": "variant_minus_top10_weekly",
            "sector_cap_candidate_rank": 50,
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
