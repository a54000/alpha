#!/usr/bin/env python3
"""Research-only rolling 20-position cohort backtest."""

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
    nth_trading_day_after,
    positions_value,
    sector_weights,
    symbol_dates,
    trading_day_distance,
    weekly_signal_dates,
    write_csv,
)

MODEL = "swing_v2_1_rolling_20_cohort"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run rolling 20-position cohort backtest.")
    parser.add_argument("--research-database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--angel-database-url", default=os.environ.get("ANGEL_DATABASE_URL"))
    parser.add_argument("--angel-database-name", default="angel_data")
    parser.add_argument("--pilot-schema", default="pilot_phase2a")
    parser.add_argument("--minimum-score", type=float, default=70.0)
    parser.add_argument("--weekly-picks", type=int, default=5)
    parser.add_argument("--max-open-positions", type=int, default=20)
    parser.add_argument("--holding-period", type=int, default=20)
    parser.add_argument("--stop-loss-pct", type=float, default=None)
    parser.add_argument("--metrics-json", default="reports/phase5_19_rolling_20_cohort_backtest.json")
    parser.add_argument("--equity-csv", default="reports/phase5_19_rolling_20_cohort_equity_curve.csv")
    parser.add_argument("--trades-csv", default="reports/phase5_19_rolling_20_cohort_trade_ledger.csv")
    parser.add_argument("--weekly-csv", default="reports/phase5_19_rolling_20_cohort_weekly_deployment.csv")
    parser.add_argument("--output-md", default="docs/PHASE5_19_ROLLING_20_COHORT_BACKTEST.md")
    return parser.parse_args()


def derive_angel_url(research_database_url: str | None, database_name: str) -> str | None:
    if not research_database_url:
        return None
    parts = urlsplit(research_database_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database_name}", parts.query, parts.fragment))


def load_recommendations(angel_url: str, schema: str, minimum_score: float, weekly_picks: int) -> list[dict[str, object]]:
    engine = create_engine(angel_url, future=True)
    frame = pd.read_sql_query(
        text(
            f"""
            SELECT symbol, date, sector, swing_v2_1_score AS score, ema200_extension
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
        ranked = rows.sort_values(["score", "symbol"], ascending=[False, True]).head(weekly_picks).reset_index(drop=True)
        for index, row in ranked.iterrows():
            recs.append(
                {
                    "date": rec_date,
                    "model": MODEL,
                    "rank": int(index) + 1,
                    "symbol": str(row["symbol"]),
                    "score": float(row["score"]),
                    "sector": row["sector"],
                    "ema200_extension": float(row["ema200_extension"]),
                }
            )
    return recs


def load_prices(angel_url: str, schema: str, symbols: set[str]) -> dict[str, dict[date, dict[str, float]]]:
    engine = create_engine(angel_url, future=True)
    rows = pd.read_sql_query(
        text(
            f"""
            SELECT symbol, date, open, low, close
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
        prices.setdefault(str(row.symbol), {})[row_date] = {
            "open": float(row.open),
            "low": float(row.low) if row.low is not None else float(row.close),
            "close": float(row.close),
        }
    return prices


def close_trade(config, position, exit_date, exit_price, dates, reason):
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
        "exit_reason": reason,
        "forced_final_exit": reason == "forced_final_exit",
    }


def run_backtest(config, recommendations, prices, weekly_picks: int, max_open_positions: int, holding_period: int, stop_loss_pct: float | None = None):
    dates = all_trading_dates(prices)
    recs_by_date: dict[date, list[dict[str, object]]] = {}
    for rec in recommendations:
        recs_by_date.setdefault(rec["date"], []).append(rec)
    for rows in recs_by_date.values():
        rows.sort(key=lambda row: (int(row["rank"]), str(row["symbol"])))

    rebalance_dates = weekly_signal_dates(sorted(recs_by_date))
    entries_by_date = {}
    for signal_date in rebalance_dates:
        entry_date = next_trading_day_after(dates, signal_date)
        if entry_date:
            entries_by_date[entry_date] = recs_by_date[signal_date]

    start_date = next_trading_day_after(dates, min(recs_by_date)) or dates[0]
    simulation_dates = [item for item in dates[dates.index(start_date):] if item <= END_DATE]

    cash = config.initial_capital
    positions: list[PilotPosition] = []
    closed_trades = []
    equity_curve = []
    weekly_rows = []
    turnover_value = 0.0
    sector_weight_snapshots = []

    for current_date in simulation_dates:
        remaining = []
        closed_today: set[str] = set()
        for position in positions:
            close_price = prices.get(position.symbol, {}).get(current_date, {}).get("close")
            low_price = prices.get(position.symbol, {}).get(current_date, {}).get("low")
            stop_price = position.entry_price * (1 - stop_loss_pct) if stop_loss_pct is not None else None
            if stop_price is not None and low_price is not None and low_price <= stop_price:
                cash += position.shares * stop_price
                turnover_value += position.shares * stop_price
                closed_trades.append(close_trade(config, position, current_date, stop_price, dates, "stop_loss"))
                closed_today.add(position.symbol)
            elif current_date >= position.planned_exit_date and close_price is not None:
                cash += position.shares * close_price
                turnover_value += position.shares * close_price
                closed_trades.append(close_trade(config, position, current_date, close_price, dates, "planned_exit"))
                closed_today.add(position.symbol)
            else:
                remaining.append(position)
        positions = remaining

        if current_date in entries_by_date:
            held = {position.symbol for position in positions}
            equity_at_open = cash + positions_value(positions, prices, current_date, "open")
            per_position_budget = equity_at_open / max_open_positions
            available_slots = max_open_positions - len(positions)
            entered = 0
            skipped_existing = 0
            skipped_cash = 0
            skipped_slots = 0
            for rec in entries_by_date[current_date][:weekly_picks]:
                if entered >= weekly_picks:
                    break
                if available_slots <= 0:
                    skipped_slots += 1
                    continue
                symbol = str(rec["symbol"])
                if symbol in held:
                    skipped_existing += 1
                    continue
                if symbol in closed_today:
                    skipped_existing += 1
                    continue
                open_price = prices.get(symbol, {}).get(current_date, {}).get("open")
                if open_price is None or open_price <= 0:
                    continue
                allocation = min(per_position_budget, cash)
                if allocation <= 0:
                    skipped_cash += 1
                    continue
                planned_exit = nth_trading_day_after(symbol_dates(prices, symbol), current_date, holding_period)
                if planned_exit is None or planned_exit > END_DATE:
                    continue
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
                        planned_exit_date=planned_exit,
                        rank=int(rec["rank"]),
                    )
                )
                held.add(symbol)
                available_slots -= 1
                entered += 1
            weekly_rows.append(
                {
                    "entry_date": current_date.isoformat(),
                    "recommendations": len(entries_by_date[current_date]),
                    "entries": entered,
                    "open_positions_after_entries": len(positions),
                    "cash_after_entries": cash,
                    "equity_at_open": equity_at_open,
                    "per_position_budget": per_position_budget,
                    "slot_utilization": len(positions) / max_open_positions,
                    "skipped_existing": skipped_existing,
                    "skipped_no_cash": skipped_cash,
                    "skipped_no_slots": skipped_slots,
                }
            )

        total_equity = cash + positions_value(positions, prices, current_date, "close")
        sector_weight_snapshots.append(sector_weights(positions, prices, current_date, total_equity))
        equity_curve.append({"variant": config.variant, "date": current_date.isoformat(), "equity": total_equity, "cash": cash, "position_count": len(positions)})

    if simulation_dates:
        final_date = simulation_dates[-1]
        for position in positions:
            close_price = prices.get(position.symbol, {}).get(final_date, {}).get("close")
            if close_price is not None:
                closed_trades.append(close_trade(config, position, final_date, close_price, dates, "forced_final_exit"))

    return {
        "config": {
            **asdict(config),
            "entry": "up_to_5_weekly",
            "exit": "planned_20_trading_days",
            "stop_loss_pct": stop_loss_pct,
            "position_size": f"equity_at_open / {max_open_positions}",
        },
        "metrics": metrics(config, equity_curve, closed_trades, turnover_value, sector_weight_snapshots),
        "equity_curve": equity_curve,
        "closed_trades": closed_trades,
        "monthly_returns": monthly_returns(equity_curve, config.variant),
        "weekly_deployment": weekly_rows,
    }


def baseline_top5():
    path = REPO_ROOT / "reports/phase2e_portfolio_metrics.json"
    return json.loads(path.read_text(encoding="utf-8"))["variants"]["top5_weekly"]["metrics"] if path.exists() else None


def fmt(value, pct: bool) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.2%}" if pct else f"{float(value):.2f}"


def write_markdown(path: Path, output, baseline):
    m = output["variants"]["rolling_20_cohort"]["metrics"]
    deploy = output["deployment_summary"]
    rules = output["rules"]
    stop = rules.get("stop_loss_pct")
    stop_line = f"- Stop loss: {float(stop):.2%} max loss per trade, triggered by daily low and exited at stop price." if stop is not None else "- Stop loss: none."
    lines = [
        "# Rolling Cohort Backtest",
        "",
        "## Rules",
        "",
        "- Entry: up to Top 5 each week.",
        "- Eligibility: score >= 70 and price > EMA200.",
        f"- Position size: calculated as equity at open / {rules['max_open_positions']}.",
        f"- Max open positions: {rules['max_open_positions']}.",
        "- Exit: planned exit after 20 trading days.",
        stop_line,
        "- No rank-drop exits.",
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
        f"- Average open positions: {deploy['avg_open_positions']:.2f}",
        f"- Average cash percentage: {deploy['avg_cash_pct']:.2%}",
        f"- Average slot utilization: {deploy['avg_slot_utilization']:.2%}",
        "",
    ]
    if baseline:
        lines += ["## Baseline Comparison", "", "| Metric | Baseline Max-5 Hold | Rolling 20 Cohort | Delta |", "| --- | ---: | ---: | ---: |"]
        for key, label, pct in [("cagr", "CAGR", True), ("total_return", "Total Return", True), ("max_drawdown", "Max Drawdown", True), ("sharpe_ratio", "Sharpe", False), ("profit_factor", "Profit Factor", False), ("win_rate", "Win Rate", True), ("turnover", "Turnover", False)]:
            base = baseline.get(key)
            val = m.get(key)
            lines.append(f"| {label} | {fmt(base, pct)} | {fmt(val, pct)} | {fmt(float(val)-float(base), pct)} |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def deployment_summary(equity_curve, weekly_rows, max_open_positions: int):
    eq = pd.DataFrame(equity_curve)
    eq["cash_pct"] = eq["cash"] / eq["equity"]
    return {
        "avg_open_positions": float(eq["position_count"].mean()),
        "max_open_positions_seen": int(eq["position_count"].max()),
        "avg_cash_pct": float(eq["cash_pct"].mean()),
        "min_cash_pct": float(eq["cash_pct"].min()),
        "avg_slot_utilization": float((eq["position_count"] / max_open_positions).mean()),
        "weekly_entry_events": len(weekly_rows),
        "avg_weekly_entries": float(pd.DataFrame(weekly_rows)["entries"].mean()) if weekly_rows else 0.0,
    }


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    args = parse_args()
    angel_url = args.angel_database_url or derive_angel_url(args.research_database_url, args.angel_database_name)
    if not angel_url:
        raise RuntimeError("Angel database URL is required.")
    recommendations = load_recommendations(angel_url, args.pilot_schema, args.minimum_score, args.weekly_picks)
    symbols = {str(row["symbol"]) for row in recommendations}
    prices = load_prices(angel_url, args.pilot_schema, symbols)
    config = PilotBacktestConfig("rolling_20_cohort", "Rolling 20-Position Cohort", portfolio_size=args.max_open_positions, holding_period=args.holding_period)
    result = run_backtest(config, recommendations, prices, args.weekly_picks, args.max_open_positions, args.holding_period, args.stop_loss_pct)
    deploy = deployment_summary(result["equity_curve"], result["weekly_deployment"], args.max_open_positions)
    output = {
        "generated_on": date.today().isoformat(),
        "mode": MODEL,
        "production_tables_modified": False,
        "active_recommendations_modified": False,
        "rules": {
            "minimum_score": args.minimum_score,
            "ema200_gate": "ema200_extension > 0",
            "weekly_picks": args.weekly_picks,
            "max_open_positions": args.max_open_positions,
            "holding_period": args.holding_period,
            "stop_loss_pct": args.stop_loss_pct,
            "position_size": "equity_at_open / max_open_positions",
        },
        "date_range": {"start": START_DATE.isoformat(), "end": END_DATE.isoformat()},
        "deployment_summary": deploy,
        "variants": {"rolling_20_cohort": {"config": result["config"], "metrics": result["metrics"], "closed_trade_count": len(result["closed_trades"])}},
    }
    metrics_path = REPO_ROOT / args.metrics_json
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
    write_csv(REPO_ROOT / args.equity_csv, result["equity_curve"])
    write_csv(REPO_ROOT / args.trades_csv, result["closed_trades"])
    write_csv(REPO_ROOT / args.weekly_csv, result["weekly_deployment"])
    write_markdown(REPO_ROOT / args.output_md, output, baseline_top5())
    print(json.dumps({"metrics": result["metrics"], "deployment_summary": deploy}, indent=2, default=str))
    print(f"Wrote rolling cohort metrics: {metrics_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
