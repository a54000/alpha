#!/usr/bin/env python3
"""Research-only Variant B: weekly Top 10 retention replacement backtest."""

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

MODEL = "swing_v2_1_weekly_replacement_variant_b"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Variant B weekly Top 10 retention replacement backtest.")
    parser.add_argument("--research-database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--angel-database-url", default=os.environ.get("ANGEL_DATABASE_URL"))
    parser.add_argument("--angel-database-name", default="angel_data")
    parser.add_argument("--pilot-schema", default="pilot_phase2a")
    parser.add_argument("--minimum-score", type=float, default=70.0)
    parser.add_argument("--entry-rank", type=int, default=5)
    parser.add_argument("--retain-rank", type=int, default=10)
    parser.add_argument("--metrics-json", default="reports/phase5_17_weekly_replacement_variant_b.json")
    parser.add_argument("--equity-csv", default="reports/phase5_17_weekly_replacement_equity_curve.csv")
    parser.add_argument("--trades-csv", default="reports/phase5_17_weekly_replacement_trade_ledger.csv")
    parser.add_argument("--output-md", default="docs/PHASE5_17_WEEKLY_REPLACEMENT_VARIANT_B.md")
    return parser.parse_args()


def derive_angel_url(research_database_url: str | None, database_name: str) -> str | None:
    if not research_database_url:
        return None
    parts = urlsplit(research_database_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database_name}", parts.query, parts.fragment))


def load_ranked_recommendations(angel_url: str, schema: str, minimum_score: float, retain_rank: int) -> list[dict[str, object]]:
    engine = create_engine(angel_url, future=True)
    frame = pd.read_sql_query(
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
    if frame.empty:
        return []
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    recs: list[dict[str, object]] = []
    for rec_date, rows in frame.groupby("date", sort=True):
        ranked = rows.sort_values(["score", "symbol"], ascending=[False, True]).head(retain_rank).reset_index(drop=True)
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
        open_price = row.open
        close_price = row.close
        if pd.isna(open_price) and pd.isna(close_price):
            continue
        prices.setdefault(row.symbol, {})[row_date] = {
            "open": float(open_price if not pd.isna(open_price) else close_price),
            "close": float(close_price if not pd.isna(close_price) else open_price),
        }
    return prices


def close_position(
    *,
    config: PilotBacktestConfig,
    position: PilotPosition,
    exit_date: date,
    exit_price: float,
    dates: list[date],
    exit_reason: str,
) -> dict[str, object]:
    proceeds = position.shares * exit_price
    return {
        "variant": config.variant,
        "symbol": position.symbol,
        "sector": position.sector,
        "signal_date": position.signal_date.isoformat(),
        "entry_date": position.entry_date.isoformat(),
        "exit_date": exit_date.isoformat(),
        "entry_price": position.entry_price,
        "exit_price": exit_price,
        "shares": position.shares,
        "return": (exit_price / position.entry_price) - 1,
        "pnl": proceeds - (position.shares * position.entry_price),
        "entry_value": position.shares * position.entry_price,
        "exit_value": proceeds,
        "holding_days": trading_day_distance(dates, position.entry_date, exit_date),
        "rank": position.rank,
        "exit_reason": exit_reason,
        "forced_final_exit": exit_reason == "forced_final_exit",
    }


def run_weekly_replacement_backtest(
    config: PilotBacktestConfig,
    recommendations: list[dict[str, object]],
    prices: dict[str, dict[date, dict[str, float]]],
    retain_rank: int,
) -> dict[str, object]:
    if not recommendations:
        return {"config": asdict(config), "metrics": {}, "equity_curve": [], "closed_trades": [], "monthly_returns": []}
    dates = all_trading_dates(prices)
    if not dates:
        return {"config": asdict(config), "metrics": {}, "equity_curve": [], "closed_trades": [], "monthly_returns": []}

    recs_by_date: dict[date, list[dict[str, object]]] = {}
    for rec in recommendations:
        recs_by_date.setdefault(rec["date"], []).append(rec)
    for rows in recs_by_date.values():
        rows.sort(key=lambda row: (int(row["rank"]), str(row["symbol"])))

    rebalance_dates = weekly_signal_dates(sorted(recs_by_date))
    review_by_entry_date: dict[date, list[dict[str, object]]] = {}
    for signal_date in rebalance_dates:
        entry_date = next_trading_day_after(dates, signal_date)
        if entry_date is not None:
            review_by_entry_date[entry_date] = recs_by_date[signal_date]

    first_signal = min(recs_by_date)
    start_date = next_trading_day_after(dates, first_signal) or dates[0]
    simulation_dates = [item for item in dates[dates.index(start_date):] if item <= END_DATE]

    cash = config.initial_capital
    positions: list[PilotPosition] = []
    closed_trades: list[dict[str, object]] = []
    equity_curve: list[dict[str, object]] = []
    turnover_value = 0.0
    sector_weight_snapshots: list[dict[str, float]] = []

    for current_date in simulation_dates:
        if current_date in review_by_entry_date:
            current_recs = review_by_entry_date[current_date]
            retain_symbols = {str(row["symbol"]) for row in current_recs if int(row["rank"]) <= retain_rank}
            remaining: list[PilotPosition] = []
            for position in positions:
                open_price = prices.get(position.symbol, {}).get(current_date, {}).get("open")
                if position.symbol not in retain_symbols and open_price is not None:
                    cash += position.shares * open_price
                    turnover_value += position.shares * open_price
                    closed_trades.append(
                        close_position(
                            config=config,
                            position=position,
                            exit_date=current_date,
                            exit_price=open_price,
                            dates=dates,
                            exit_reason="weekly_rank_drop",
                        )
                    )
                else:
                    remaining.append(position)
            positions = remaining

            held = {position.symbol for position in positions}
            equity_at_open = cash + positions_value(positions, prices, current_date, "open")
            target_value = equity_at_open / config.portfolio_size
            candidates = [
                rec for rec in current_recs
                if int(rec["rank"]) <= config.portfolio_size and str(rec["symbol"]) not in held
            ]
            for rec in candidates:
                if len(positions) >= config.portfolio_size:
                    break
                symbol = str(rec["symbol"])
                open_price = prices.get(symbol, {}).get(current_date, {}).get("open")
                if open_price is None or open_price <= 0:
                    continue
                allocation = min(target_value, cash)
                if allocation <= 0:
                    break
                shares = allocation / open_price
                cash -= allocation
                turnover_value += allocation
                positions.append(
                    PilotPosition(
                        symbol=symbol,
                        sector=rec.get("sector"),
                        signal_date=rec["date"],
                        entry_date=current_date,
                        entry_price=open_price,
                        shares=shares,
                        planned_exit_date=END_DATE,
                        rank=int(rec["rank"]),
                    )
                )
                held.add(symbol)

        total_equity = cash + positions_value(positions, prices, current_date, "close")
        sector_weight_snapshots.append(sector_weights(positions, prices, current_date, total_equity))
        equity_curve.append(
            {
                "variant": config.variant,
                "date": current_date.isoformat(),
                "equity": total_equity,
                "cash": cash,
                "position_count": len(positions),
            }
        )

    if simulation_dates:
        final_date = simulation_dates[-1]
        for position in positions:
            close_price = prices.get(position.symbol, {}).get(final_date, {}).get("close")
            if close_price is None:
                continue
            closed_trades.append(
                close_position(
                    config=config,
                    position=position,
                    exit_date=final_date,
                    exit_price=close_price,
                    dates=dates,
                    exit_reason="forced_final_exit",
                )
            )

    return {
        "config": {
            **asdict(config),
            "entry": "next_trading_day_open",
            "exit": "weekly_exit_if_outside_top10",
            "replacement": "replace_from_current_top5",
            "weighting": "equal_weight_target_allocation",
            "leverage": "none",
            "transaction_costs": "not_included",
        },
        "metrics": metrics(config, equity_curve, closed_trades, turnover_value, sector_weight_snapshots),
        "equity_curve": equity_curve,
        "closed_trades": closed_trades,
        "monthly_returns": monthly_returns(equity_curve, config.variant),
    }


def baseline_top5() -> dict[str, object] | None:
    path = REPO_ROOT / "reports/phase2e_portfolio_metrics.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("variants", {}).get("top5_weekly", {}).get("metrics")


def fmt(value, pct: bool) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.2%}" if pct else f"{float(value):.2f}"


def write_markdown(path: Path, output: dict[str, object], baseline: dict[str, object] | None) -> None:
    metrics_new = output["variants"]["top5_weekly_variant_b"]["metrics"]
    lines = [
        "# Phase 5.17 Weekly Replacement Variant B",
        "",
        "## Objective",
        "",
        "Research-only test of weekly replacement using a Top 10 retention band.",
        "",
        "## Rules",
        "",
        "- Entry candidates: Top 5, score >= 70, price > EMA200.",
        "- Weekly review: keep existing holdings if they remain in current Top 10.",
        "- Exit: next rebalance open if rank drops outside Top 10.",
        "- Replacement: fill open slots from current Top 5.",
        "- Max open positions: 5.",
        "- No transaction costs.",
        "- No production tables modified.",
        "",
        "## Results",
        "",
        f"- Total return: {metrics_new['total_return']:.2%}",
        f"- CAGR: {metrics_new['cagr']:.2%}",
        f"- Max drawdown: {metrics_new['max_drawdown']:.2%}",
        f"- Sharpe: {metrics_new['sharpe_ratio']:.2f}",
        f"- Sortino: {metrics_new['sortino_ratio']:.2f}",
        f"- Profit factor: {metrics_new['profit_factor']:.2f}",
        f"- Win rate: {metrics_new['win_rate']:.2%}",
        f"- Closed trades: {metrics_new['closed_trades']}",
        f"- Turnover: {metrics_new['turnover']:.2f}",
        f"- Final equity: {metrics_new['final_equity']:,.0f}",
        "",
    ]
    if baseline:
        lines.extend(["## Baseline Comparison", "", "| Metric | Baseline Top 5 V2.1 | Variant B | Delta |", "| --- | ---: | ---: | ---: |"])
        for key, label, pct in [
            ("total_return", "Total Return", True),
            ("cagr", "CAGR", True),
            ("max_drawdown", "Max Drawdown", True),
            ("sharpe_ratio", "Sharpe", False),
            ("profit_factor", "Profit Factor", False),
            ("win_rate", "Win Rate", True),
            ("turnover", "Turnover", False),
        ]:
            base = baseline.get(key)
            value = metrics_new.get(key)
            delta = None if base is None or value is None else float(value) - float(base)
            lines.append(f"| {label} | {fmt(base, pct)} | {fmt(value, pct)} | {fmt(delta, pct)} |")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    args = parse_args()
    research_url = args.research_database_url or os.environ.get("DATABASE_URL")
    angel_url = args.angel_database_url or derive_angel_url(research_url, args.angel_database_name)
    if not angel_url:
        raise RuntimeError("Angel database URL is required.")

    recommendations = load_ranked_recommendations(angel_url, args.pilot_schema, args.minimum_score, args.retain_rank)
    symbols = {str(row["symbol"]) for row in recommendations}
    prices = load_prices(angel_url, args.pilot_schema, symbols)
    config = PilotBacktestConfig(
        "top5_weekly_variant_b",
        "Top 5 Weekly Variant B",
        portfolio_size=args.entry_rank,
        max_candidate_rank=args.retain_rank,
    )
    result = run_weekly_replacement_backtest(config, recommendations, prices, args.retain_rank)
    output = {
        "generated_on": date.today().isoformat(),
        "mode": MODEL,
        "production_tables_modified": False,
        "active_recommendations_modified": False,
        "rules": {
            "minimum_score": args.minimum_score,
            "ema200_gate": "ema200_extension > 0",
            "entry_rank": args.entry_rank,
            "retain_rank": args.retain_rank,
            "weekly_exit": "exit if held symbol is outside current Top 10 at weekly review",
        },
        "date_range": {"start": START_DATE.isoformat(), "end": END_DATE.isoformat()},
        "backtest_inputs": {
            "scores": f"{args.pilot_schema}.scores_daily",
            "prices": f"{args.pilot_schema}.daily_bars_clean",
            "recommendation_rows": len(recommendations),
            "symbols": len(symbols),
        },
        "variants": {
            "top5_weekly_variant_b": {
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
    write_markdown(REPO_ROOT / args.output_md, output, baseline_top5())

    print(json.dumps(result["metrics"], indent=2, default=str))
    print(f"Wrote Variant B metrics: {metrics_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
