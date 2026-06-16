#!/usr/bin/env python3
"""Phase 2F diagnostics for five-year pilot portfolio backtests."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from datetime import date
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Phase 2F portfolio diagnostics.")
    parser.add_argument("--metrics-json", default="reports/phase2e_portfolio_metrics.json")
    parser.add_argument("--trades-csv", default="reports/phase2e_trade_ledger.csv")
    parser.add_argument("--monthly-csv", default="reports/phase2e_monthly_returns.csv")
    parser.add_argument("--equity-csv", default="reports/phase2e_equity_curves.csv")
    parser.add_argument("--output-json", default="reports/phase2f_portfolio_diagnostics.json")
    return parser.parse_args()


def load_inputs(args: argparse.Namespace) -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metrics = json.loads((REPO_ROOT / args.metrics_json).read_text(encoding="utf-8"))
    trades = pd.read_csv(REPO_ROOT / args.trades_csv)
    monthly = pd.read_csv(REPO_ROOT / args.monthly_csv)
    equity = pd.read_csv(REPO_ROOT / args.equity_csv)
    for frame in [trades, monthly, equity]:
        for column in frame.columns:
            if column.endswith("_date") or column == "date":
                frame[column] = pd.to_datetime(frame[column], errors="coerce").dt.date
    for column in ["return", "pnl", "entry_value", "exit_value"]:
        if column in trades:
            trades[column] = pd.to_numeric(trades[column], errors="coerce")
    monthly["monthly_return"] = pd.to_numeric(monthly["monthly_return"], errors="coerce")
    equity["equity"] = pd.to_numeric(equity["equity"], errors="coerce")
    equity["cash"] = pd.to_numeric(equity["cash"], errors="coerce")
    equity["position_count"] = pd.to_numeric(equity["position_count"], errors="coerce")
    return metrics, trades, monthly, equity


def winner_concentration(trades: pd.DataFrame) -> dict[str, object]:
    rows = {}
    for variant, frame in trades.groupby("variant"):
        pnl = frame["pnl"].dropna()
        winners = frame[frame["pnl"] > 0].sort_values("pnl", ascending=False)
        total_pnl = float(pnl.sum())
        gross_profit = float(frame.loc[frame["pnl"] > 0, "pnl"].sum())
        top10 = float(winners.head(10)["pnl"].sum())
        top20 = float(winners.head(20)["pnl"].sum())
        rows[variant] = {
            "total_pnl": total_pnl,
            "gross_profit": gross_profit,
            "gross_loss": float(abs(frame.loc[frame["pnl"] < 0, "pnl"].sum())),
            "top10_winners_pnl": top10,
            "top10_winners_share_of_net_pnl": top10 / total_pnl if total_pnl else None,
            "top10_winners_share_of_gross_profit": top10 / gross_profit if gross_profit else None,
            "top20_winners_pnl": top20,
            "top20_winners_share_of_net_pnl": top20 / total_pnl if total_pnl else None,
            "top20_winners_share_of_gross_profit": top20 / gross_profit if gross_profit else None,
            "pnl_distribution": {
                "min": float(pnl.min()) if not pnl.empty else None,
                "p10": float(pnl.quantile(0.10)) if not pnl.empty else None,
                "median": float(pnl.median()) if not pnl.empty else None,
                "p90": float(pnl.quantile(0.90)) if not pnl.empty else None,
                "max": float(pnl.max()) if not pnl.empty else None,
                "positive_trades": int((frame["pnl"] > 0).sum()),
                "negative_trades": int((frame["pnl"] < 0).sum()),
            },
            "top10_winners": winners.head(10)[
                ["symbol", "sector", "signal_date", "entry_date", "exit_date", "rank", "return", "pnl"]
            ].to_dict(orient="records"),
        }
    return rows


def sector_dependency(trades: pd.DataFrame, metrics: dict[str, object]) -> dict[str, object]:
    rows = {}
    for variant, frame in trades.groupby("variant"):
        total_pnl = float(frame["pnl"].sum())
        sectors = []
        for sector, sector_frame in frame.groupby(frame["sector"].fillna("UNKNOWN")):
            pnl = float(sector_frame["pnl"].sum())
            returns = sector_frame["return"].dropna()
            sectors.append(
                {
                    "sector": sector,
                    "pnl": pnl,
                    "pnl_share_of_net": pnl / total_pnl if total_pnl else None,
                    "trades": int(len(sector_frame)),
                    "avg_return": float(returns.mean()) if not returns.empty else None,
                    "win_rate": float((returns > 0).mean()) if not returns.empty else None,
                }
            )
        sectors.sort(key=lambda item: item["pnl"], reverse=True)
        concentration = metrics["variants"][variant]["metrics"]["sector_concentration"]
        rows[variant] = {
            "pnl_by_sector": sectors,
            "avg_exposure_by_sector": concentration.get("sectors", []),
            "top_sector_avg_weight": concentration.get("top_sector_avg_weight"),
            "top_3_avg_weight": concentration.get("top_3_avg_weight"),
            "top_sector": concentration.get("top_sector"),
        }
    return rows


def equity_returns(equity: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for variant, frame in equity.sort_values(["variant", "date"]).groupby("variant"):
        item = frame.copy()
        item["daily_return"] = item["equity"].pct_change()
        item["rolling_60d_return"] = item["equity"] / item["equity"].shift(60) - 1
        item["rolling_20d_vol"] = item["daily_return"].rolling(20).std() * math.sqrt(252)
        item["drawdown"] = item["equity"] / item["equity"].cummax() - 1
        frames.append(item)
    return pd.concat(frames, ignore_index=True)


def market_regimes(equity: pd.DataFrame) -> dict[str, object]:
    eq = equity_returns(equity)
    vol_values = eq["rolling_20d_vol"].dropna()
    low_vol = float(vol_values.quantile(0.25)) if not vol_values.empty else 0.0
    high_vol = float(vol_values.quantile(0.75)) if not vol_values.empty else 0.0
    rows = {}
    for variant, frame in eq.groupby("variant"):
        item = frame.dropna(subset=["daily_return"]).copy()
        item["trend_regime"] = item["rolling_60d_return"].apply(lambda value: "bull" if pd.notna(value) and value > 0 else ("bear" if pd.notna(value) and value < 0 else "warmup"))
        item["volatility_regime"] = item["rolling_20d_vol"].apply(
            lambda value: "low_vol" if pd.notna(value) and value <= low_vol else ("high_vol" if pd.notna(value) and value >= high_vol else "normal_vol")
        )
        item["drawdown_regime"] = item["drawdown"].apply(lambda value: "deep_drawdown" if value <= -0.10 else ("drawdown" if value < 0 else "high_watermark"))
        rows[variant] = {
            "trend": grouped_return_stats(item, "trend_regime"),
            "volatility": grouped_return_stats(item, "volatility_regime"),
            "drawdown": grouped_return_stats(item, "drawdown_regime"),
            "worst_drawdown_date": str(frame.loc[frame["drawdown"].idxmin(), "date"]),
            "worst_drawdown": float(frame["drawdown"].min()),
        }
    return rows


def grouped_return_stats(frame: pd.DataFrame, column: str) -> list[dict[str, object]]:
    rows = []
    for label, group in frame.groupby(column):
        returns = group["daily_return"].dropna()
        total = math.prod(1 + float(value) for value in returns) - 1 if not returns.empty else 0.0
        rows.append(
            {
                "regime": label,
                "days": int(len(returns)),
                "total_return": total,
                "avg_daily_return": float(returns.mean()) if not returns.empty else 0.0,
                "win_rate": float((returns > 0).mean()) if not returns.empty else 0.0,
            }
        )
    return sorted(rows, key=lambda item: item["regime"])


def cost_sensitivity(metrics: dict[str, object]) -> dict[str, object]:
    # Delivery-style approximation inspired by Zerodha calculator/STT pages:
    # STT 0.1% on buy + sell, zero brokerage, plus small exchange/GST/SEBI/stamp components.
    zerodha_style_round_trip_bps = 23.0
    sweep_bps = [0, 10, 23, 25, 50, 75, 100, 150, 200, 250, 300]
    rows = {}
    for variant, item in metrics["variants"].items():
        gross_total = float(item["metrics"]["total_return"])
        turnover = float(item["metrics"]["turnover"])
        days = 997
        entries = []
        break_even_bps = (gross_total / turnover) * 10_000 if turnover else None
        for bps in sweep_bps:
            cost_drag = turnover * (bps / 10_000)
            net_total = gross_total - cost_drag
            net_final = 1 + net_total
            net_cagr = net_final ** (252 / days) - 1 if net_final > 0 else -1.0
            entries.append(
                {
                    "round_trip_cost_bps": bps,
                    "cost_drag": cost_drag,
                    "net_total_return": net_total,
                    "net_cagr": net_cagr,
                }
            )
        rows[variant] = {
            "assumed_zerodha_style_round_trip_bps": zerodha_style_round_trip_bps,
            "break_even_round_trip_bps": break_even_bps,
            "sensitivity": entries,
        }
    return rows


def losing_streak(values: list[float]) -> int:
    best = 0
    current = 0
    for value in values:
        if value < 0:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def portfolio_stability(monthly: pd.DataFrame, equity: pd.DataFrame) -> dict[str, object]:
    rows = {}
    eq = equity_returns(equity)
    for variant, frame in monthly.groupby("variant"):
        returns = frame["monthly_return"].dropna().tolist()
        worst_months = frame.dropna(subset=["monthly_return"]).sort_values("monthly_return").head(5)
        eq_frame = eq[eq["variant"] == variant].dropna(subset=["daily_return"])
        daily_returns = eq_frame["daily_return"].tolist()
        rows[variant] = {
            "months": int(len(returns)),
            "monthly_win_rate": sum(1 for value in returns if value > 0) / len(returns) if returns else 0.0,
            "longest_monthly_losing_streak": losing_streak(returns),
            "longest_daily_losing_streak": losing_streak(daily_returns),
            "worst_months": worst_months[["month", "month_end_date", "monthly_return"]].to_dict(orient="records"),
        }
    return rows


def main() -> int:
    args = parse_args()
    metrics, trades, monthly, equity = load_inputs(args)
    output = {
        "generated_on": date.today().isoformat(),
        "mode": "phase2f_portfolio_diagnostics",
        "inputs": {
            "metrics_json": args.metrics_json,
            "trades_csv": args.trades_csv,
            "monthly_csv": args.monthly_csv,
            "equity_csv": args.equity_csv,
        },
        "constraints": {
            "scoring_changed": False,
            "recommendations_changed": False,
            "parameters_optimized": False,
            "filters_added": False,
        },
        "winner_concentration": winner_concentration(trades),
        "sector_dependency": sector_dependency(trades, metrics),
        "market_regimes": market_regimes(equity),
        "transaction_cost_sensitivity": cost_sensitivity(metrics),
        "portfolio_stability": portfolio_stability(monthly, equity),
    }
    path = REPO_ROOT / args.output_json
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
