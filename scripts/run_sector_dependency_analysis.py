#!/usr/bin/env python3
"""Analyze Swing V2.1 dependence on Financial Services leadership."""

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
OUTPUT_PATH = Path("reports/sector_dependency_analysis.json")
PORTFOLIO_SIZE = 10

VARIANTS = [
    (
        "baseline_top10_weekly",
        "Baseline Top 10 Weekly",
        PortfolioBacktestConfig(model=MODEL, portfolio_size=PORTFOLIO_SIZE),
    ),
    (
        "exclude_financial_services",
        "Exclude Financial Services",
        PortfolioBacktestConfig(
            model=MODEL,
            portfolio_size=PORTFOLIO_SIZE,
            excluded_sectors=("FINANCIAL SERVICES",),
            max_candidate_rank=50,
        ),
    ),
    (
        "max_30pct_sector_exposure",
        "Max 30% Sector Exposure",
        PortfolioBacktestConfig(
            model=MODEL,
            portfolio_size=PORTFOLIO_SIZE,
            max_sector_weight=0.30,
            max_candidate_rank=50,
        ),
    ),
    (
        "max_20pct_sector_exposure",
        "Max 20% Sector Exposure",
        PortfolioBacktestConfig(
            model=MODEL,
            portfolio_size=PORTFOLIO_SIZE,
            max_sector_weight=0.20,
            max_candidate_rank=50,
        ),
    ),
    (
        "max_2_positions_per_sector",
        "Max 2 Positions Per Sector",
        PortfolioBacktestConfig(
            model=MODEL,
            portfolio_size=PORTFOLIO_SIZE,
            max_positions_per_sector=2,
            max_candidate_rank=50,
        ),
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
        "cagr": metrics["cagr"],
        "total_return": metrics["total_return"],
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
        "sector_weights": concentration["sectors"],
        "sector_contribution": sector_contribution(result["closed_trades"]),
    }


def build_conclusions(rows: list[dict[str, object]]) -> dict[str, object]:
    baseline = next(row for row in rows if row["variant"] == "baseline_top10_weekly")
    no_fin = next(row for row in rows if row["variant"] == "exclude_financial_services")
    best_sharpe = max(rows, key=lambda row: float(row["sharpe_ratio"]))
    best_cagr = max(rows, key=lambda row: float(row["cagr"]))
    lowest_drawdown = max(rows, key=lambda row: float(row["max_drawdown"]))
    return {
        "does_edge_survive_without_financials": float(no_fin["cagr"]) > 0 and float(no_fin["profit_factor"]) > 1,
        "exclude_financials_cagr_delta": float(no_fin["cagr"]) - float(baseline["cagr"]),
        "exclude_financials_sharpe_delta": float(no_fin["sharpe_ratio"]) - float(baseline["sharpe_ratio"]),
        "exclude_financials_profit_factor_delta": float(no_fin["profit_factor"]) - float(baseline["profit_factor"]),
        "best_sharpe_variant": best_sharpe["variant"],
        "best_sharpe": best_sharpe["sharpe_ratio"],
        "best_cagr_variant": best_cagr["variant"],
        "best_cagr": best_cagr["cagr"],
        "lowest_drawdown_variant": lowest_drawdown["variant"],
        "lowest_max_drawdown": lowest_drawdown["max_drawdown"],
        "baseline_top_sector": baseline["top_sector"],
        "baseline_top_sector_avg_weight": baseline["top_sector_avg_weight"],
        "baseline_top_3_sector_avg_weight": baseline["top_3_sector_avg_weight"],
    }


def main() -> int:
    backtester = PortfolioBacktesterV1(build_session_factory())
    rows: list[dict[str, object]] = []
    details: dict[str, object] = {}

    for label, name, config in VARIANTS:
        result = backtester.run(config)
        row = metric_row(label, name, result)
        rows.append(row)
        details[label] = {
            "config": result["config"],
            "metrics": result["metrics"],
            "closed_trade_count": result["closed_trade_count"],
            "closed_trades_sample": result["closed_trades_sample"],
        }

    output = {
        "model": MODEL,
        "portfolio_size": PORTFOLIO_SIZE,
        "methodology": {
            "entry": "next_trading_day_open",
            "exit": "close_after_20_trading_days",
            "rebalance": "weekly",
            "weighting": "equal_weight",
            "leverage": "none",
            "transaction_costs": "not_included",
            "constrained_variants_candidate_rank": 50,
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

