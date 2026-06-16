#!/usr/bin/env python3
"""Research-only Rolling 10 daily fill-up experiment.

Baseline:
  Rolling 10 + 1M/3M 40/60 recommendations + 10:30 entry.

Experiment:
  Same lifecycle, but every daily recommendation date can fill empty portfolio
  slots on the next trading day instead of waiting for the next weekly cohort.

No production scores, recommendations, strategy rules, or database rows are
modified.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import statistics
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.api.trade_analysis_service import (  # noqa: E402
    AnalysisPosition,
    buy_side_charges,
    build_trade_row,
    next_trading_day_after,
    nth_trading_day_after,
    positions_value,
    symbol_dates,
    total_charges,
    weekly_signal_dates,
)

RECOMMENDATIONS_CSV = REPO_ROOT / "results" / "sector_1m3m_rank_experiment" / "sector_1m3m_recommendations.csv"
OUTPUT_DIR = REPO_ROOT / "results" / "daily_fillup_1030_experiment"


@dataclass(frozen=True)
class Variant:
    name: str
    entry_schedule: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Rolling 10 daily fill-up experiment.")
    parser.add_argument("--recommendations-csv", type=Path, default=RECOMMENDATIONS_CSV)
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2022, 5, 25))
    parser.add_argument("--end-date", type=date.fromisoformat, default=date(2026, 6, 11))
    parser.add_argument("--initial-capital", type=float, default=1_000_000.0)
    parser.add_argument("--pilot-schema", default="pilot_phase2a")
    parser.add_argument("--portfolio-size", type=int, default=10)
    parser.add_argument("--weekly-picks", type=int, default=5)
    parser.add_argument("--daily-fillup-candidate-limit", type=int, default=20)
    parser.add_argument("--holding-period", type=int, default=20)
    parser.add_argument("--entry-time", type=time.fromisoformat, default=time(10, 30))
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    return parser.parse_args()


def load_recommendations(path: Path, start_date: date, end_date: date) -> list[dict[str, object]]:
    frame = pd.read_csv(path)
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    frame = frame[(frame["date"] >= start_date) & (frame["date"] <= end_date)].copy()
    rows = []
    for row in frame.sort_values(["date", "rank", "symbol"]).itertuples(index=False):
        data = row._asdict()
        rows.append({"date": data["date"], "rank": int(data["rank"]), "symbol": str(data["symbol"]), "score": float(data["score"]), "sector": data.get("sector")})
    return rows


def load_prices(engine, schema: str, symbols: set[str], start_date: date, end_date: date) -> dict[str, dict[date, dict[str, float]]]:
    query = text(
        f"""
        SELECT symbol, date, open, high, low, close
        FROM {schema}.daily_bars_clean
        WHERE symbol = ANY(:symbols)
          AND date BETWEEN :start_date AND :end_date
        ORDER BY symbol, date
        """
    )
    with engine.connect() as connection:
        rows = connection.execute(query, {"symbols": list(symbols), "start_date": start_date, "end_date": end_date}).mappings().all()
    out: dict[str, dict[date, dict[str, float]]] = {}
    for row in rows:
        out.setdefault(str(row["symbol"]), {})[row["date"]] = {"open": float(row["open"]), "high": float(row["high"]), "low": float(row["low"]), "close": float(row["close"])}
    return out


def load_entry_price(engine, symbols: set[str], start_date: date, end_date: date, entry_time: time) -> dict[tuple[str, date], float]:
    query = text(
        """
        SELECT symbol, datetime::date AS date, open
        FROM ohlcv_15min
        WHERE symbol = ANY(:symbols)
          AND datetime::date BETWEEN :start_date AND :end_date
          AND datetime::time = :entry_time
        """
    )
    with engine.connect() as connection:
        rows = connection.execute(query, {"symbols": list(symbols), "start_date": start_date, "end_date": end_date, "entry_time": entry_time}).mappings().all()
    return {(str(row["symbol"]), row["date"]): float(row["open"]) for row in rows}


def all_trading_dates(prices: dict[str, dict[date, dict[str, float]]]) -> list[date]:
    return sorted({day for symbol_prices in prices.values() for day in symbol_prices})


def returns_from_equity(curve: list[dict[str, object]]) -> list[float]:
    returns, previous = [], None
    for row in curve:
        equity = float(row["equity"])
        if previous and previous > 0:
            returns.append(equity / previous - 1.0)
        previous = equity
    return returns


def max_drawdown(values: list[float]) -> float:
    peak = values[0] if values else 0.0
    drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        if peak:
            drawdown = min(drawdown, value / peak - 1.0)
    return drawdown


def metrics(initial_capital: float, curve: list[dict[str, object]], trades: list[dict[str, object]], turnover: float) -> dict[str, object]:
    values = [float(row["equity"]) for row in curve]
    returns = returns_from_equity(curve)
    downside = [value for value in returns if value < 0]
    gross_profit = sum(float(row["net_pnl"]) for row in trades if float(row["net_pnl"]) > 0)
    gross_loss = abs(sum(float(row["net_pnl"]) for row in trades if float(row["net_pnl"]) < 0))
    stdev = statistics.stdev(returns) if len(returns) > 1 else 0.0
    downside_stdev = statistics.stdev(downside) if len(downside) > 1 else 0.0
    ending = values[-1]
    return {
        "ending_equity": ending,
        "total_return": ending / initial_capital - 1.0,
        "cagr": (ending / initial_capital) ** (252 / max(1, len(curve))) - 1.0 if ending > 0 else -1.0,
        "max_drawdown": max_drawdown(values),
        "sharpe_ratio": statistics.mean(returns) / stdev * math.sqrt(252) if stdev else 0.0,
        "sortino_ratio": statistics.mean(returns) / downside_stdev * math.sqrt(252) if downside_stdev else 0.0,
        "profit_factor": gross_profit / gross_loss if gross_loss else None,
        "win_rate": sum(1 for row in trades if float(row["net_pnl"]) > 0) / len(trades) if trades else 0.0,
        "closed_trades": len(trades),
        "turnover": turnover / initial_capital,
        "avg_cash_pct": statistics.mean([float(row["cash"]) / float(row["equity"]) for row in curve if float(row["equity"])]),
        "avg_position_count": statistics.mean([int(row["position_count"]) for row in curve]),
    }


def fy_label(day: date) -> str:
    start_year = day.year if day.month >= 4 else day.year - 1
    return f"FY{start_year}-{str(start_year + 1)[-2:]}"


def fy_returns(curve: list[dict[str, object]], variant: str) -> list[dict[str, object]]:
    groups: dict[str, list[dict[str, object]]] = {}
    for row in curve:
        groups.setdefault(fy_label(date.fromisoformat(str(row["date"]))), []).append(row)
    rows = []
    for label, group in sorted(groups.items()):
        group.sort(key=lambda item: str(item["date"]))
        start = float(group[0]["equity"])
        end = float(group[-1]["equity"])
        rows.append({"variant": variant, "financial_year": label, "start_date": group[0]["date"], "end_date": group[-1]["date"], "start_equity": start, "end_equity": end, "return_pct": end / start - 1.0 if start else None, "max_drawdown": max_drawdown([float(row["equity"]) for row in group])})
    return rows


def build_entries_by_date(variant: Variant, recs_by_date: dict[date, list[dict[str, object]]], dates: list[date], weekly_picks: int, daily_limit: int) -> dict[date, tuple[date, list[dict[str, object]]]]:
    entries: dict[date, tuple[date, list[dict[str, object]]]] = {}
    if variant.entry_schedule == "weekly":
        signal_dates = weekly_signal_dates(list(recs_by_date))
        for signal_date in signal_dates:
            entry_date = next_trading_day_after(dates, signal_date)
            if entry_date:
                entries[entry_date] = (signal_date, recs_by_date[signal_date][:weekly_picks])
        return entries
    for signal_date in sorted(recs_by_date):
        entry_date = next_trading_day_after(dates, signal_date)
        if entry_date:
            entries[entry_date] = (signal_date, recs_by_date[signal_date][:daily_limit])
    return entries


def run_variant(variant: Variant, recommendations: list[dict[str, object]], prices: dict[str, dict[date, dict[str, float]]], entry_prices: dict[tuple[str, date], float], *, start_date: date, end_date: date, initial_capital: float, portfolio_size: int, weekly_picks: int, daily_limit: int, holding_period: int) -> dict[str, object]:
    dates = [day for day in all_trading_dates(prices) if start_date <= day <= end_date]
    recs_by_date: dict[date, list[dict[str, object]]] = {}
    for rec in recommendations:
        recs_by_date.setdefault(rec["date"], []).append(rec)
    for rows in recs_by_date.values():
        rows.sort(key=lambda row: (int(row["rank"]), str(row["symbol"])))
    entries_by_date = build_entries_by_date(variant, recs_by_date, dates, weekly_picks, daily_limit)
    cash = initial_capital
    positions: list[AnalysisPosition] = []
    trades: list[dict[str, object]] = []
    curve: list[dict[str, object]] = []
    entry_log: list[dict[str, object]] = []
    turnover = 0.0
    trade_id = 1
    for current_date in dates:
        remaining: list[AnalysisPosition] = []
        closed_today: set[str] = set()
        for position in positions:
            close_price = prices.get(position.symbol, {}).get(current_date, {}).get("close")
            if current_date >= position.planned_exit_date and close_price is not None:
                row = build_trade_row(trade_id, position, current_date, close_price, symbol_dates(prices, position.symbol), variant.name)
                cash += float(row["exit_value"]) - (float(row["charges"]) - total_charges(position.buy_charges))
                turnover += float(row["exit_value"])
                trades.append({**row, "exit_reason": "planned_exit"})
                closed_today.add(position.symbol)
                trade_id += 1
            else:
                remaining.append(position)
        positions = remaining
        if current_date in entries_by_date:
            signal_date, candidates = entries_by_date[current_date]
            held = {position.symbol for position in positions}
            equity_at_open = cash + positions_value(positions, prices, current_date, "open")
            target_value = equity_at_open / portfolio_size
            for rec in candidates:
                symbol = str(rec["symbol"])
                base = {"variant": variant.name, "entry_schedule": variant.entry_schedule, "signal_date": signal_date.isoformat(), "entry_date": current_date.isoformat(), "symbol": symbol, "sector": rec.get("sector"), "rank": int(rec["rank"]), "score": rec.get("score")}
                if len(positions) >= portfolio_size:
                    entry_log.append({**base, "status": "skipped", "reason": "portfolio_full"})
                    continue
                if symbol in held or symbol in closed_today:
                    entry_log.append({**base, "status": "skipped", "reason": "already_held_or_closed_today"})
                    continue
                entry_price = entry_prices.get((symbol, current_date))
                if entry_price is None or entry_price <= 0:
                    entry_log.append({**base, "status": "skipped", "reason": "missing_1030_entry_price"})
                    continue
                allocation = min(target_value, cash)
                if allocation <= 0:
                    entry_log.append({**base, "status": "skipped", "reason": "insufficient_cash"})
                    continue
                buy_charges = buy_side_charges(allocation)
                if allocation + total_charges(buy_charges) > cash:
                    allocation = cash / (1.0 + (total_charges(buy_charges) / allocation if allocation else 0.0))
                    buy_charges = buy_side_charges(allocation)
                planned_exit = nth_trading_day_after(symbol_dates(prices, symbol), current_date, holding_period)
                if planned_exit is None:
                    entry_log.append({**base, "status": "skipped", "reason": "missing_planned_exit"})
                    continue
                cash -= allocation + total_charges(buy_charges)
                turnover += allocation
                positions.append(AnalysisPosition(symbol=symbol, sector=str(rec.get("sector") or "UNKNOWN"), signal_date=signal_date, entry_date=current_date, entry_price=float(entry_price), quantity=allocation / float(entry_price), planned_exit_date=planned_exit, rank=int(rec["rank"]), score=float(rec["score"]) if rec.get("score") is not None else None, entry_value=allocation, buy_charges=buy_charges))
                held.add(symbol)
                entry_log.append({**base, "status": "entered", "reason": "entered", "entry_price": entry_price, "allocation": allocation})
        equity = cash + positions_value(positions, prices, current_date, "close")
        curve.append({"variant": variant.name, "date": current_date.isoformat(), "equity": equity, "cash": cash, "position_count": len(positions)})
    if dates:
        final_date = dates[-1]
        for position in positions:
            close_price = prices.get(position.symbol, {}).get(final_date, {}).get("close")
            if close_price is None:
                continue
            row = build_trade_row(trade_id, position, final_date, close_price, symbol_dates(prices, position.symbol), variant.name)
            trades.append({**row, "exit_reason": "forced_final_exit"})
            cash += float(row["exit_value"]) - (float(row["charges"]) - total_charges(position.buy_charges))
            turnover += float(row["exit_value"])
            trade_id += 1
        curve[-1]["equity"] = cash
        curve[-1]["cash"] = cash
        curve[-1]["position_count"] = 0
    return {"variant": variant.name, "metrics": metrics(initial_capital, curve, trades, turnover), "equity_curve": curve, "trades": trades, "entry_log": entry_log, "financial_year_returns": fy_returns(curve, variant.name)}


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def fmt_pct(value: object) -> str:
    return "n/a" if value is None else f"{float(value) * 100:.2f}%"


def fmt_num(value: object) -> str:
    return "n/a" if value is None else f"{float(value):.2f}"


def render_report(payload: dict[str, object]) -> str:
    lines = ["# Rolling 10 Daily Fill-Up 10:30 Experiment", "", "Research-only experiment. No production scoring, recommendations, strategy rules, or database rows were modified.", "", "## Metrics", "", "| Variant | CAGR | Total Return | Max DD | Sharpe | Sortino | PF | Win Rate | Trades | Avg Cash | Avg Positions |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in payload["summary"]:
        lines.append(f"| {row['variant']} | {fmt_pct(row['cagr'])} | {fmt_pct(row['total_return'])} | {fmt_pct(row['max_drawdown'])} | {fmt_num(row['sharpe_ratio'])} | {fmt_num(row['sortino_ratio'])} | {fmt_num(row['profit_factor'])} | {fmt_pct(row['win_rate'])} | {fmt_num(row['closed_trades'])} | {fmt_pct(row['avg_cash_pct'])} | {fmt_num(row['avg_position_count'])} |")
    years = sorted({row["financial_year"] for row in payload["financial_year_returns"]})
    by_key = {(row["variant"], row["financial_year"]): row for row in payload["financial_year_returns"]}
    lines.extend(["", "## FY Returns", "", "| FY | " + " | ".join(row["variant"] for row in payload["summary"]) + " |", "| --- | " + " | ".join("---:" for _ in payload["summary"]) + " |"])
    for year in years:
        lines.append("| " + year + " | " + " | ".join(fmt_pct(by_key.get((row["variant"], year), {}).get("return_pct")) for row in payload["summary"]) + " |")
    lines.extend(["", "## Verdict", "", payload["verdict"]])
    return "\n".join(lines) + "\n"


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    args = parse_args()
    angel_url = os.environ.get("ANGEL_DATABASE_URL")
    if not angel_url:
        raise RuntimeError("ANGEL_DATABASE_URL is required.")
    engine = create_engine(angel_url, future=True, pool_pre_ping=True)
    recommendations = load_recommendations(args.recommendations_csv, args.start_date, args.end_date)
    symbols = {row["symbol"] for row in recommendations}
    prices = load_prices(engine, args.pilot_schema, symbols, args.start_date, args.end_date)
    entry_prices = load_entry_price(engine, symbols, args.start_date, args.end_date, args.entry_time)
    variants = [Variant("rolling_10_1m3m_entry_1030_weekly", "weekly"), Variant("rolling_10_1m3m_entry_1030_daily_fillup", "daily_fillup")]
    results = [run_variant(v, recommendations, prices, entry_prices, start_date=args.start_date, end_date=args.end_date, initial_capital=args.initial_capital, portfolio_size=args.portfolio_size, weekly_picks=args.weekly_picks, daily_limit=args.daily_fillup_candidate_limit, holding_period=args.holding_period) for v in variants]
    summary = []
    for result in results:
        entries = result["entry_log"]
        summary.append({**result["metrics"], "variant": result["variant"], "entries_entered": sum(1 for row in entries if row.get("status") == "entered"), "portfolio_full_skips": sum(1 for row in entries if row.get("reason") == "portfolio_full")})
    base, exp = summary
    verdict = f"Daily fill-up changed average cash from {base['avg_cash_pct'] * 100:.2f}% to {exp['avg_cash_pct'] * 100:.2f}% and CAGR from {base['cagr'] * 100:.2f}% to {exp['cagr'] * 100:.2f}%."
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(), "parameters": vars(args) | {"recommendations_csv": str(args.recommendations_csv), "output_dir": str(args.output_dir), "entry_time": args.entry_time.isoformat()}, "summary": summary, "financial_year_returns": [row for result in results for row in result["financial_year_returns"]], "constraints": {"database_modified": False, "production_scoring_changed": False, "production_recommendations_changed": False, "strategy_rules_changed": False}, "verdict": verdict}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "daily_fillup_1030_experiment.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    (args.output_dir / "DAILY_FILLUP_1030_EXPERIMENT.md").write_text(render_report(payload), encoding="utf-8")
    write_csv(args.output_dir / "daily_fillup_1030_summary.csv", summary)
    write_csv(args.output_dir / "daily_fillup_1030_fy_returns.csv", payload["financial_year_returns"])
    write_csv(args.output_dir / "daily_fillup_1030_equity.csv", [row for result in results for row in result["equity_curve"]])
    write_csv(args.output_dir / "daily_fillup_1030_trades.csv", [row for result in results for row in result["trades"]])
    write_csv(args.output_dir / "daily_fillup_1030_entries.csv", [row for result in results for row in result["entry_log"]])
    print(json.dumps(payload, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
