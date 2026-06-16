#!/usr/bin/env python3
"""Research-only backtest: EMA200-positive Swing V2.1 with score threshold 60."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.run_phase2e_pilot_portfolio_backtest import (  # noqa: E402
    END_DATE,
    START_DATE,
    PilotBacktestConfig,
    load_prices,
    run_backtest,
    write_csv,
)

MODEL = "swing_v2_1_ema200_threshold60_research"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run research-only EMA200-positive threshold-60 Top 5 backtest.")
    parser.add_argument("--research-database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--angel-database-url", default=os.environ.get("ANGEL_DATABASE_URL"))
    parser.add_argument("--angel-database-name", default="angel_data")
    parser.add_argument("--pilot-schema", default="pilot_phase2a")
    parser.add_argument("--minimum-score", type=float, default=60.0)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--metrics-json", default="reports/phase5_16_ema200_threshold60_backtest.json")
    parser.add_argument("--equity-csv", default="reports/phase5_16_ema200_threshold60_equity_curve.csv")
    parser.add_argument("--trades-csv", default="reports/phase5_16_ema200_threshold60_trade_ledger.csv")
    parser.add_argument("--recommendations-csv", default="reports/phase5_16_ema200_threshold60_recommendations.csv")
    parser.add_argument("--output-md", default="docs/PHASE5_16_EMA200_THRESHOLD60_BACKTEST.md")
    return parser.parse_args()


def derive_angel_url(research_database_url: str | None, database_name: str) -> str | None:
    if not research_database_url:
        return None
    parts = urlsplit(research_database_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database_name}", parts.query, parts.fragment))


def load_research_recommendations(angel_url: str, schema: str, minimum_score: float, top_n: int) -> list[dict[str, object]]:
    engine = create_engine(angel_url, future=True)
    rows = pd.read_sql_query(
        text(
            f"""
            SELECT symbol, date, sector, swing_v2_1_score AS score, ema200_extension,
                   prior_20d_return, sector_rank_3m
            FROM {schema}.scores_daily
            WHERE date BETWEEN :start_date AND :end_date
              AND swing_v2_1_score >= :minimum_score
              AND ema200_extension > 0
            ORDER BY date, swing_v2_1_score DESC, symbol ASC
            """
        ),
        engine,
        params={"start_date": START_DATE, "end_date": END_DATE, "minimum_score": minimum_score},
    )
    if rows.empty:
        return []
    rows["date"] = pd.to_datetime(rows["date"]).dt.date
    recs: list[dict[str, object]] = []
    for rec_date, frame in rows.groupby("date", sort=True):
        ranked = frame.sort_values(["score", "symbol"], ascending=[False, True]).head(top_n).reset_index(drop=True)
        for index, row in ranked.iterrows():
            recs.append(
                {
                    "date": rec_date,
                    "model": MODEL,
                    "rank": int(index) + 1,
                    "symbol": row["symbol"],
                    "score": float(row["score"]),
                    "sector": row["sector"],
                    "ema200_extension": float(row["ema200_extension"]),
                    "prior_20d_return": float(row["prior_20d_return"]) if pd.notna(row["prior_20d_return"]) else None,
                    "sector_rank_3m": int(row["sector_rank_3m"]) if pd.notna(row["sector_rank_3m"]) else None,
                }
            )
    return recs


def write_markdown(path: Path, output: dict[str, object], baseline: dict[str, object] | None) -> None:
    metrics = output["variants"]["top5_weekly"]["metrics"]
    lines = [
        "# Phase 5.16 EMA200 Threshold 60 Backtest",
        "",
        "## Objective",
        "",
        "Research-only test of lowering Swing V2.1 recommendation threshold to 60 while requiring price above EMA200.",
        "",
        "## Rules",
        "",
        "- Score threshold: `>= 60`.",
        "- EMA200 gate: `ema200_extension > 0`.",
        "- Portfolio: Top 5 Weekly.",
        "- Entry: next trading day open.",
        "- Exit: close after 20 trading days.",
        "- No transaction costs.",
        "- No production tables modified.",
        "",
        "## Results",
        "",
        f"- Total return: {metrics['total_return']:.2%}",
        f"- CAGR: {metrics['cagr']:.2%}",
        f"- Max drawdown: {metrics['max_drawdown']:.2%}",
        f"- Sharpe: {metrics['sharpe_ratio']:.2f}",
        f"- Sortino: {metrics['sortino_ratio']:.2f}",
        f"- Profit factor: {metrics['profit_factor']:.2f}",
        f"- Win rate: {metrics['win_rate']:.2%}",
        f"- Closed trades: {metrics['closed_trades']}",
        f"- Final equity: {metrics['final_equity']:,.0f}",
        "",
    ]
    if baseline:
        lines.extend(
            [
                "## Baseline Comparison",
                "",
                "| Metric | Baseline Top 5 V2.1 | EMA200 + Threshold 60 | Delta |",
                "| --- | ---: | ---: | ---: |",
            ]
        )
        for key, label, pct in [
            ("total_return", "Total Return", True),
            ("cagr", "CAGR", True),
            ("max_drawdown", "Max Drawdown", True),
            ("sharpe_ratio", "Sharpe", False),
            ("profit_factor", "Profit Factor", False),
            ("win_rate", "Win Rate", True),
        ]:
            base = baseline.get(key)
            value = metrics.get(key)
            delta = None if base is None or value is None else float(value) - float(base)
            lines.append(f"| {label} | {fmt(base, pct)} | {fmt(value, pct)} | {fmt(delta, pct)} |")
        lines.append("")
    lines.extend(
        [
            "## Interpretation",
            "",
            "This is a replacement-aware portfolio backtest using generated research recommendations, not a change to the active production strategy.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def fmt(value, pct: bool) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.2%}" if pct else f"{float(value):.2f}"


def baseline_top5() -> dict[str, object] | None:
    path = REPO_ROOT / "reports/phase2e_portfolio_metrics.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("variants", {}).get("top5_weekly", {}).get("metrics")


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    args = parse_args()
    research_url = args.research_database_url or os.environ.get("DATABASE_URL")
    angel_url = args.angel_database_url or derive_angel_url(research_url, args.angel_database_name)
    if not angel_url:
        raise RuntimeError("Angel database URL is required.")

    recommendations = load_research_recommendations(angel_url, args.pilot_schema, args.minimum_score, args.top_n)
    symbols = {str(row["symbol"]) for row in recommendations}
    prices = load_prices(angel_url, args.pilot_schema, symbols)
    config = PilotBacktestConfig(
        "top5_weekly",
        "Top 5 Weekly EMA200 Threshold 60 Research",
        portfolio_size=5,
        max_candidate_rank=args.top_n,
    )
    result = run_backtest(config, recommendations, prices)
    output = {
        "generated_on": date.today().isoformat(),
        "mode": MODEL,
        "production_tables_modified": False,
        "active_recommendations_modified": False,
        "rules": {
            "minimum_score": args.minimum_score,
            "ema200_gate": "ema200_extension > 0",
            "top_n_candidates": args.top_n,
        },
        "date_range": {"start": START_DATE.isoformat(), "end": END_DATE.isoformat()},
        "backtest_inputs": {
            "scores": f"{args.pilot_schema}.scores_daily",
            "prices": f"{args.pilot_schema}.daily_bars_clean",
            "recommendation_rows": len(recommendations),
            "symbols": len(symbols),
        },
        "variants": {
            "top5_weekly": {
                "config": result["config"],
                "metrics": result["metrics"],
                "closed_trade_count": len(result["closed_trades"]),
            }
        },
    }

    metrics_path = REPO_ROOT / args.metrics_json
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
    write_csv(REPO_ROOT / args.equity_csv, result["equity_curve"])
    write_csv(REPO_ROOT / args.trades_csv, result["closed_trades"])
    write_csv(REPO_ROOT / args.recommendations_csv, recommendations)
    write_markdown(REPO_ROOT / args.output_md, output, baseline_top5())

    print(json.dumps(output["variants"]["top5_weekly"]["metrics"], indent=2, default=str))
    print(f"Wrote EMA200 threshold-60 backtest metrics: {metrics_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
