#!/usr/bin/env python3
"""Research-only experiment: exit when raw Swing V2.1 rank drops worse than 10."""

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
    PilotPosition,
    all_trading_dates,
    metrics,
    monthly_returns,
    next_trading_day_after,
    positions_value,
    sector_weights,
    trading_day_distance,
    weekly_signal_dates,
    write_csv,
)
from scripts.run_weekly_replacement_variant_b import close_position, fmt  # noqa: E402

MODEL = "swing_v2_1_weekly_raw_rank10_exit"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run weekly raw-rank Top 10 exit experiment.")
    parser.add_argument("--research-database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--angel-database-url", default=os.environ.get("ANGEL_DATABASE_URL"))
    parser.add_argument("--angel-database-name", default="angel_data")
    parser.add_argument("--pilot-schema", default="pilot_phase2a")
    parser.add_argument("--minimum-score", type=float, default=70.0)
    parser.add_argument("--entry-rank", type=int, default=5)
    parser.add_argument("--retain-rank", type=int, default=10)
    parser.add_argument("--metrics-json", default="reports/phase5_18_weekly_raw_rank10_exit.json")
    parser.add_argument("--equity-csv", default="reports/phase5_18_weekly_raw_rank10_exit_equity_curve.csv")
    parser.add_argument("--trades-csv", default="reports/phase5_18_weekly_raw_rank10_exit_trade_ledger.csv")
    parser.add_argument("--output-md", default="docs/PHASE5_18_WEEKLY_RAW_RANK10_EXIT.md")
    return parser.parse_args()


def derive_angel_url(research_database_url: str | None, database_name: str) -> str | None:
    if not research_database_url:
        return None
    parts = urlsplit(research_database_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database_name}", parts.query, parts.fragment))


def load_rank_frames(angel_url: str, schema: str, minimum_score: float, entry_rank: int, retain_rank: int):
    engine = create_engine(angel_url, future=True)
    frame = pd.read_sql_query(
        text(
            f"""
            SELECT symbol, date, sector, swing_v2_1_score AS score, ema200_extension
            FROM {schema}.scores_daily
            WHERE date BETWEEN :start_date AND :end_date
              AND swing_v2_1_score IS NOT NULL
            ORDER BY date, swing_v2_1_score DESC, symbol ASC
            """
        ),
        engine,
        params={"start_date": START_DATE, "end_date": END_DATE},
    )
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    entry_recs: list[dict[str, object]] = []
    raw_top10_by_date: dict[date, set[str]] = {}
    for rec_date, rows in frame.groupby("date", sort=True):
        ranked = rows.sort_values(["score", "symbol"], ascending=[False, True]).reset_index(drop=True)
        ranked["raw_rank"] = ranked.index + 1
        raw_top10_by_date[rec_date] = set(ranked[ranked["raw_rank"] <= retain_rank]["symbol"].astype(str))
        entries = ranked[
            (ranked["raw_rank"] <= entry_rank)
            & (ranked["score"] >= minimum_score)
            & (ranked["ema200_extension"] > 0)
        ]
        for row in entries.itertuples(index=False):
            entry_recs.append(
                {
                    "date": rec_date,
                    "rank": int(row.raw_rank),
                    "symbol": str(row.symbol),
                    "score": float(row.score),
                    "sector": row.sector,
                }
            )
    return entry_recs, raw_top10_by_date


def load_prices(angel_url: str, schema: str, symbols: set[str]) -> dict[str, dict[date, dict[str, float]]]:
    if not symbols:
        return {}
    engine = create_engine(angel_url, future=True)
    rows = pd.read_sql_query(
        text(
            f"""
            SELECT symbol, date, open, close
            FROM {schema}.daily_bars_clean
            WHERE symbol = ANY(:symbols)
              AND date >= :start_date
            ORDER BY symbol, date
            """
        ),
        engine,
        params={"symbols": list(symbols), "start_date": START_DATE},
    )
    prices: dict[str, dict[date, dict[str, float]]] = {}
    for row in rows.itertuples(index=False):
        row_date = pd.to_datetime(row.date).date()
        prices.setdefault(row.symbol, {})[row_date] = {"open": float(row.open), "close": float(row.close)}
    return prices


def run_backtest(config, recommendations, raw_top10_by_date, prices):
    dates = all_trading_dates(prices)
    recs_by_date: dict[date, list[dict[str, object]]] = {}
    for rec in recommendations:
        recs_by_date.setdefault(rec["date"], []).append(rec)
    for rows in recs_by_date.values():
        rows.sort(key=lambda row: (int(row["rank"]), str(row["symbol"])))
    rebalance_dates = weekly_signal_dates(sorted(raw_top10_by_date))
    review_by_entry_date = {}
    signal_by_entry_date = {}
    for signal_date in rebalance_dates:
        entry_date = next_trading_day_after(dates, signal_date)
        if entry_date:
            review_by_entry_date[entry_date] = raw_top10_by_date.get(signal_date, set())
            signal_by_entry_date[entry_date] = recs_by_date.get(signal_date, [])
    start_date = next_trading_day_after(dates, min(raw_top10_by_date)) or dates[0]
    simulation_dates = [item for item in dates[dates.index(start_date):] if item <= END_DATE]

    cash = config.initial_capital
    positions: list[PilotPosition] = []
    closed_trades = []
    equity_curve = []
    turnover_value = 0.0
    sector_weight_snapshots = []

    for current_date in simulation_dates:
        if current_date in review_by_entry_date:
            retain_symbols = review_by_entry_date[current_date]
            remaining = []
            for position in positions:
                open_price = prices.get(position.symbol, {}).get(current_date, {}).get("open")
                if position.symbol not in retain_symbols and open_price is not None:
                    cash += position.shares * open_price
                    turnover_value += position.shares * open_price
                    closed_trades.append(close_position(config=config, position=position, exit_date=current_date, exit_price=open_price, dates=dates, exit_reason="raw_rank_worse_than_10"))
                else:
                    remaining.append(position)
            positions = remaining

            held = {p.symbol for p in positions}
            equity_at_open = cash + positions_value(positions, prices, current_date, "open")
            target_value = equity_at_open / config.portfolio_size
            for rec in signal_by_entry_date.get(current_date, []):
                if len(positions) >= config.portfolio_size:
                    break
                symbol = str(rec["symbol"])
                if symbol in held:
                    continue
                open_price = prices.get(symbol, {}).get(current_date, {}).get("open")
                if open_price is None or open_price <= 0:
                    continue
                allocation = min(target_value, cash)
                if allocation <= 0:
                    break
                shares = allocation / open_price
                cash -= allocation
                turnover_value += allocation
                positions.append(PilotPosition(symbol, rec.get("sector"), rec["date"], current_date, open_price, shares, END_DATE, int(rec["rank"])))
                held.add(symbol)

        total_equity = cash + positions_value(positions, prices, current_date, "close")
        sector_weight_snapshots.append(sector_weights(positions, prices, current_date, total_equity))
        equity_curve.append({"variant": config.variant, "date": current_date.isoformat(), "equity": total_equity, "cash": cash, "position_count": len(positions)})

    if simulation_dates:
        final_date = simulation_dates[-1]
        for position in positions:
            close_price = prices.get(position.symbol, {}).get(final_date, {}).get("close")
            if close_price is not None:
                closed_trades.append(close_position(config=config, position=position, exit_date=final_date, exit_price=close_price, dates=dates, exit_reason="forced_final_exit"))
    return {
        "config": {**asdict(config), "entry": "top5_score70_ema200", "exit": "weekly_exit_if_raw_rank_worse_than_10"},
        "metrics": metrics(config, equity_curve, closed_trades, turnover_value, sector_weight_snapshots),
        "equity_curve": equity_curve,
        "closed_trades": closed_trades,
        "monthly_returns": monthly_returns(equity_curve, config.variant),
    }


def baseline_top5():
    path = REPO_ROOT / "reports/phase2e_portfolio_metrics.json"
    return json.loads(path.read_text(encoding="utf-8"))["variants"]["top5_weekly"]["metrics"] if path.exists() else None


def write_markdown(path: Path, output: dict[str, object], baseline):
    m = output["variants"]["top5_weekly_raw_rank10_exit"]["metrics"]
    lines = [
        "# Phase 5.18 Weekly Raw Rank 10 Exit",
        "",
        "## Rules",
        "",
        "- Entry: raw Top 5 only if score >= 70 and price > EMA200.",
        "- Weekly review: exit only if held symbol's raw Swing V2.1 rank is worse than 10.",
        "- Max open positions: 5.",
        "- No transaction costs.",
        "",
        "## Results",
        "",
        f"- CAGR: {m['cagr']:.2%}",
        f"- Total return: {m['total_return']:.2%}",
        f"- Max drawdown: {m['max_drawdown']:.2%}",
        f"- Sharpe: {m['sharpe_ratio']:.2f}",
        f"- Profit factor: {m['profit_factor']:.2f}",
        f"- Win rate: {m['win_rate']:.2%}",
        f"- Trades: {m['closed_trades']}",
        f"- Turnover: {m['turnover']:.2f}",
        "",
    ]
    if baseline:
        lines += ["## Baseline Comparison", "", "| Metric | Baseline | Raw Rank 10 Exit | Delta |", "| --- | ---: | ---: | ---: |"]
        for key, label, pct in [("cagr", "CAGR", True), ("total_return", "Total Return", True), ("max_drawdown", "Max Drawdown", True), ("sharpe_ratio", "Sharpe", False), ("profit_factor", "Profit Factor", False), ("win_rate", "Win Rate", True), ("turnover", "Turnover", False)]:
            base = baseline.get(key)
            val = m.get(key)
            lines.append(f"| {label} | {fmt(base, pct)} | {fmt(val, pct)} | {fmt(float(val)-float(base), pct)} |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    args = parse_args()
    angel_url = args.angel_database_url or derive_angel_url(args.research_database_url, args.angel_database_name)
    if not angel_url:
        raise RuntimeError("Angel database URL is required.")
    recommendations, raw_top10 = load_rank_frames(angel_url, args.pilot_schema, args.minimum_score, args.entry_rank, args.retain_rank)
    symbols = {str(r["symbol"]) for r in recommendations} | set().union(*raw_top10.values())
    prices = load_prices(angel_url, args.pilot_schema, symbols)
    config = PilotBacktestConfig("top5_weekly_raw_rank10_exit", "Top 5 Weekly Raw Rank 10 Exit", portfolio_size=args.entry_rank, max_candidate_rank=args.retain_rank)
    result = run_backtest(config, recommendations, raw_top10, prices)
    output = {
        "generated_on": date.today().isoformat(),
        "mode": MODEL,
        "production_tables_modified": False,
        "active_recommendations_modified": False,
        "rules": {"entry": "Top 5 score>=70 and price>EMA200", "exit": "weekly raw rank worse than 10"},
        "date_range": {"start": START_DATE.isoformat(), "end": END_DATE.isoformat()},
        "variants": {"top5_weekly_raw_rank10_exit": {"config": result["config"], "metrics": result["metrics"], "closed_trade_count": len(result["closed_trades"])}},
    }
    metrics_path = REPO_ROOT / args.metrics_json
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
    write_csv(REPO_ROOT / args.equity_csv, result["equity_curve"])
    write_csv(REPO_ROOT / args.trades_csv, result["closed_trades"])
    write_markdown(REPO_ROOT / args.output_md, output, baseline_top5())
    print(json.dumps(result["metrics"], indent=2, default=str))
    print(f"Wrote raw-rank exit metrics: {metrics_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
