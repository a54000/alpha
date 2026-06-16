#!/usr/bin/env python3
"""Research-only RSI entry skip experiment.

Uses the 1M/3M 40/60 recommendation set and Rolling 10 lifecycle.
Variant tested:

  - baseline: no RSI adjustment
  - skip: skip entry when signal-date RSI14 > threshold

RSI14 is recomputed from pilot cleaned daily closes and evaluated on the
inferred signal date, the trading session before entry. No production scores,
recommendations, strategy rules, or database rows are modified.
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
from datetime import date, datetime, timezone
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
OUTPUT_DIR = REPO_ROOT / "results" / "entry_rsi_skip_experiment"


@dataclass(frozen=True)
class Variant:
    name: str
    skip_rsi: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Rolling 10 RSI entry skip experiment.")
    parser.add_argument("--recommendations-csv", type=Path, default=RECOMMENDATIONS_CSV)
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2022, 5, 25))
    parser.add_argument("--end-date", type=date.fromisoformat, default=date(2026, 6, 11))
    parser.add_argument("--initial-capital", type=float, default=1_000_000.0)
    parser.add_argument("--pilot-schema", default="pilot_phase2a")
    parser.add_argument("--portfolio-size", type=int, default=10)
    parser.add_argument("--weekly-picks", type=int, default=5)
    parser.add_argument("--holding-period", type=int, default=20)
    parser.add_argument("--rsi-threshold", type=float, default=80.0)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    return parser.parse_args()


def load_recommendations(path: Path, start_date: date, end_date: date) -> list[dict[str, object]]:
    frame = pd.read_csv(path)
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    frame = frame[(frame["date"] >= start_date) & (frame["date"] <= end_date)].copy()
    rows: list[dict[str, object]] = []
    for row in frame.sort_values(["date", "rank", "symbol"]).itertuples(index=False):
        data = row._asdict()
        rows.append(
            {
                "date": data["date"],
                "rank": int(data["rank"]),
                "symbol": str(data["symbol"]),
                "score": float(data["score"]) if pd.notna(data["score"]) else None,
                "sector": data.get("sector"),
            }
        )
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
    prices: dict[str, dict[date, dict[str, float]]] = {}
    for row in rows:
        prices.setdefault(str(row["symbol"]), {})[row["date"]] = {
            "open": float(row["open"]),
            "high": float(row["high"]) if row["high"] is not None else float(row["close"]),
            "low": float(row["low"]) if row["low"] is not None else float(row["close"]),
            "close": float(row["close"]),
        }
    return prices


def all_trading_dates(prices: dict[str, dict[date, dict[str, float]]]) -> list[date]:
    return sorted({day for symbol_prices in prices.values() for day in symbol_prices})


def load_rsi(engine, schema: str, symbols: set[str], start_date: date, end_date: date) -> dict[tuple[str, date], float]:
    query = text(
        f"""
        SELECT symbol, date, close
        FROM {schema}.daily_bars_clean
        WHERE symbol = ANY(:symbols)
          AND date BETWEEN :start_date - INTERVAL '90 days' AND :end_date
        ORDER BY symbol, date
        """
    )
    frame = pd.read_sql_query(query, engine, params={"symbols": list(symbols), "start_date": start_date, "end_date": end_date})
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    delta = frame.groupby("symbol")["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.groupby(frame["symbol"]).transform(lambda s: s.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean())
    avg_loss = loss.groupby(frame["symbol"]).transform(lambda s: s.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean())
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    frame["rsi_14"] = 100 - (100 / (1 + rs))
    frame.loc[(avg_loss == 0) & (avg_gain > 0), "rsi_14"] = 100
    frame.loc[(avg_loss == 0) & (avg_gain == 0), "rsi_14"] = 50
    return {(str(row.symbol), row.date): float(row.rsi_14) for row in frame.itertuples(index=False) if pd.notna(row.rsi_14)}


def returns_from_equity(equity_curve: list[dict[str, object]]) -> list[float]:
    returns = []
    previous = None
    for row in equity_curve:
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


def metrics(initial_capital: float, equity_curve: list[dict[str, object]], trades: list[dict[str, object]], turnover: float) -> dict[str, object]:
    values = [float(row["equity"]) for row in equity_curve]
    returns = returns_from_equity(equity_curve)
    downside = [value for value in returns if value < 0]
    gross_profit = sum(float(row["net_pnl"]) for row in trades if float(row["net_pnl"]) > 0)
    gross_loss = abs(sum(float(row["net_pnl"]) for row in trades if float(row["net_pnl"]) < 0))
    stdev = statistics.stdev(returns) if len(returns) > 1 else 0.0
    downside_stdev = statistics.stdev(downside) if len(downside) > 1 else 0.0
    ending = values[-1]
    return {
        "ending_equity": ending,
        "total_return": ending / initial_capital - 1.0,
        "cagr": (ending / initial_capital) ** (252 / max(1, len(equity_curve))) - 1.0 if ending > 0 else -1.0,
        "max_drawdown": max_drawdown(values),
        "sharpe_ratio": statistics.mean(returns) / stdev * math.sqrt(252) if stdev else 0.0,
        "sortino_ratio": statistics.mean(returns) / downside_stdev * math.sqrt(252) if downside_stdev else 0.0,
        "profit_factor": gross_profit / gross_loss if gross_loss else None,
        "win_rate": sum(1 for row in trades if float(row["net_pnl"]) > 0) / len(trades) if trades else 0.0,
        "closed_trades": len(trades),
        "turnover": turnover / initial_capital,
        "avg_cash_pct": statistics.mean([float(row["cash"]) / float(row["equity"]) for row in equity_curve if float(row["equity"])]) if equity_curve else 0.0,
        "avg_position_count": statistics.mean([int(row["position_count"]) for row in equity_curve]) if equity_curve else 0.0,
    }


def fy_label(day: date) -> str:
    start_year = day.year if day.month >= 4 else day.year - 1
    return f"FY{start_year}-{str(start_year + 1)[-2:]}"


def fy_returns(equity_curve: list[dict[str, object]], variant: str) -> list[dict[str, object]]:
    groups: dict[str, list[dict[str, object]]] = {}
    for row in equity_curve:
        groups.setdefault(fy_label(date.fromisoformat(str(row["date"]))), []).append(row)
    rows = []
    for label, group in sorted(groups.items()):
        group.sort(key=lambda item: str(item["date"]))
        start = float(group[0]["equity"])
        end = float(group[-1]["equity"])
        rows.append(
            {
                "variant": variant,
                "financial_year": label,
                "start_date": group[0]["date"],
                "end_date": group[-1]["date"],
                "start_equity": start,
                "end_equity": end,
                "return_pct": end / start - 1.0 if start else None,
                "max_drawdown": max_drawdown([float(row["equity"]) for row in group]),
            }
        )
    return rows


def run_variant(
    variant: Variant,
    recommendations: list[dict[str, object]],
    prices: dict[str, dict[date, dict[str, float]]],
    rsi: dict[tuple[str, date], float],
    *,
    start_date: date,
    end_date: date,
    initial_capital: float,
    portfolio_size: int,
    weekly_picks: int,
    holding_period: int,
    rsi_threshold: float,
) -> dict[str, object]:
    dates = [day for day in all_trading_dates(prices) if start_date <= day <= end_date]
    recs_by_date: dict[date, list[dict[str, object]]] = {}
    for rec in recommendations:
        recs_by_date.setdefault(rec["date"], []).append(rec)
    for rows in recs_by_date.values():
        rows.sort(key=lambda row: (int(row["rank"]), str(row["symbol"])))

    entries_by_date: dict[date, tuple[date, list[dict[str, object]]]] = {}
    for signal_date in weekly_signal_dates(list(recs_by_date)):
        entry_date = next_trading_day_after(dates, signal_date)
        if entry_date:
            entries_by_date[entry_date] = (signal_date, recs_by_date[signal_date][:weekly_picks])

    cash = initial_capital
    positions: list[AnalysisPosition] = []
    trades: list[dict[str, object]] = []
    equity_curve: list[dict[str, object]] = []
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
                sector = str(rec.get("sector") or "UNKNOWN")
                signal_rsi = rsi.get((symbol, signal_date))
                high_rsi = signal_rsi is not None and signal_rsi > rsi_threshold
                base_log = {
                    "variant": variant.name,
                    "signal_date": signal_date.isoformat(),
                    "entry_date": current_date.isoformat(),
                    "symbol": symbol,
                    "sector": sector,
                    "rank": int(rec["rank"]),
                    "score": rec.get("score"),
                    "signal_rsi_14": signal_rsi,
                    "high_rsi": high_rsi,
                }
                if len(positions) >= portfolio_size:
                    entry_log.append({**base_log, "status": "skipped", "reason": "portfolio_full"})
                    continue
                if symbol in held or symbol in closed_today:
                    entry_log.append({**base_log, "status": "skipped", "reason": "already_held_or_closed_today"})
                    continue
                open_price = prices.get(symbol, {}).get(current_date, {}).get("open")
                if open_price is None or open_price <= 0:
                    entry_log.append({**base_log, "status": "skipped", "reason": "missing_entry_price"})
                    continue
                if variant.skip_rsi and high_rsi:
                    entry_log.append({**base_log, "status": "skipped", "reason": "rsi_gt_threshold"})
                    continue
                allocation = min(target_value, cash)
                if allocation <= 0:
                    entry_log.append({**base_log, "status": "skipped", "reason": "insufficient_cash"})
                    continue
                buy_charges = buy_side_charges(allocation)
                if allocation + total_charges(buy_charges) > cash:
                    allocation = cash / (1.0 + (total_charges(buy_charges) / allocation if allocation else 0.0))
                    buy_charges = buy_side_charges(allocation)
                planned_exit = nth_trading_day_after(symbol_dates(prices, symbol), current_date, holding_period)
                if planned_exit is None:
                    entry_log.append({**base_log, "status": "skipped", "reason": "missing_planned_exit"})
                    continue
                cash -= allocation + total_charges(buy_charges)
                turnover += allocation
                positions.append(
                    AnalysisPosition(
                        symbol=symbol,
                        sector=sector,
                        signal_date=signal_date,
                        entry_date=current_date,
                        entry_price=float(open_price),
                        quantity=allocation / float(open_price),
                        planned_exit_date=planned_exit,
                        rank=int(rec["rank"]),
                        score=float(rec["score"]) if rec.get("score") is not None else None,
                        entry_value=allocation,
                        buy_charges=buy_charges,
                    )
                )
                held.add(symbol)
                entry_log.append({**base_log, "status": "entered", "reason": "entered", "allocation": allocation})

        equity = cash + positions_value(positions, prices, current_date, "close")
        equity_curve.append({"variant": variant.name, "date": current_date.isoformat(), "equity": equity, "cash": cash, "position_count": len(positions)})

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
        equity_curve[-1]["equity"] = cash
        equity_curve[-1]["cash"] = cash
        equity_curve[-1]["position_count"] = 0

    return {
        "variant": variant.name,
        "metrics": metrics(initial_capital, equity_curve, trades, turnover),
        "equity_curve": equity_curve,
        "trades": trades,
        "entry_log": entry_log,
        "financial_year_returns": fy_returns(equity_curve, variant.name),
    }


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
    rows = payload["summary"]
    lines = [
        "# Entry RSI Skip Experiment",
        "",
        "Research-only experiment. No production scores, recommendations, strategy rules, or database rows were modified.",
        "",
        f"- Rule tested: skip entry if signal-date RSI14 > {payload['parameters']['rsi_threshold']:.2f}",
        "",
        "## Portfolio Metrics",
        "",
        "| Variant | CAGR | Total Return | Max DD | Sharpe | Sortino | PF | Win Rate | Trades | Avg Cash | High RSI Entered | High RSI Skipped |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['variant']} | {fmt_pct(row['cagr'])} | {fmt_pct(row['total_return'])} | {fmt_pct(row['max_drawdown'])} | "
            f"{fmt_num(row['sharpe_ratio'])} | {fmt_num(row['sortino_ratio'])} | {fmt_num(row['profit_factor'])} | "
            f"{fmt_pct(row['win_rate'])} | {fmt_num(row['closed_trades'])} | {fmt_pct(row['avg_cash_pct'])} | "
            f"{row['high_rsi_entered']} | {row['high_rsi_skipped']} |"
        )
    years = sorted({item["financial_year"] for item in payload["financial_year_returns"]})
    by_key = {(item["variant"], item["financial_year"]): item for item in payload["financial_year_returns"]}
    lines.extend(["", "## Financial Year Returns", "", "| FY | " + " | ".join(row["variant"] for row in rows) + " |", "| --- | " + " | ".join("---:" for _ in rows) + " |"])
    for year in years:
        lines.append("| " + year + " | " + " | ".join(fmt_pct(by_key.get((row["variant"], year), {}).get("return_pct")) for row in rows) + " |")
    lines.extend(["", "## Verdict", "", str(payload["verdict"])])
    return "\n".join(lines) + "\n"


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    args = parse_args()
    angel_url = os.environ.get("ANGEL_DATABASE_URL")
    if not angel_url:
        raise RuntimeError("ANGEL_DATABASE_URL is required.")
    engine = create_engine(angel_url, future=True, pool_pre_ping=True)
    recommendations = load_recommendations(args.recommendations_csv, args.start_date, args.end_date)
    symbols = {str(row["symbol"]) for row in recommendations}
    prices = load_prices(engine, args.pilot_schema, symbols, args.start_date, args.end_date)
    rsi = load_rsi(engine, args.pilot_schema, symbols, args.start_date, args.end_date)
    variants = [
        Variant("rolling_10_1m3m_baseline", False),
        Variant("rolling_10_1m3m_skip_rsi_gt_80", True),
    ]
    results = [
        run_variant(
            variant,
            recommendations,
            prices,
            rsi,
            start_date=args.start_date,
            end_date=args.end_date,
            initial_capital=args.initial_capital,
            portfolio_size=args.portfolio_size,
            weekly_picks=args.weekly_picks,
            holding_period=args.holding_period,
            rsi_threshold=args.rsi_threshold,
        )
        for variant in variants
    ]
    summary = []
    for result in results:
        entries = result["entry_log"]
        summary.append(
            {
                "variant": result["variant"],
                **result["metrics"],
                "entries_entered": sum(1 for row in entries if row.get("status") == "entered"),
                "high_rsi_entered": sum(1 for row in entries if row.get("status") == "entered" and row.get("high_rsi")),
                "high_rsi_skipped": sum(1 for row in entries if row.get("reason") == "rsi_gt_threshold"),
            }
        )
    base, exp = summary
    verdict = (
        "RSI > 80 skip improves the candidate."
        if float(exp["sharpe_ratio"]) > float(base["sharpe_ratio"]) and float(exp["cagr"]) >= float(base["cagr"])
        else "RSI > 80 skip does not clearly improve the candidate; do not promote without further evidence."
    )
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "parameters": {
            "recommendations_csv": str(args.recommendations_csv),
            "start_date": args.start_date.isoformat(),
            "end_date": args.end_date.isoformat(),
            "initial_capital": args.initial_capital,
            "portfolio_size": args.portfolio_size,
            "weekly_picks": args.weekly_picks,
            "holding_period": args.holding_period,
            "rsi_threshold": args.rsi_threshold,
        },
        "summary": summary,
        "financial_year_returns": [row for result in results for row in result["financial_year_returns"]],
        "constraints": {
            "database_modified": False,
            "production_scoring_changed": False,
            "production_recommendations_changed": False,
            "strategy_rules_changed": False,
        },
        "verdict": verdict,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "entry_rsi_skip_experiment.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    (args.output_dir / "ENTRY_RSI_SKIP_EXPERIMENT.md").write_text(render_report(payload), encoding="utf-8")
    write_csv(args.output_dir / "entry_rsi_skip_summary.csv", summary)
    write_csv(args.output_dir / "entry_rsi_skip_fy_returns.csv", payload["financial_year_returns"])
    write_csv(args.output_dir / "entry_rsi_skip_equity.csv", [row for result in results for row in result["equity_curve"]])
    write_csv(args.output_dir / "entry_rsi_skip_trades.csv", [row for result in results for row in result["trades"]])
    write_csv(args.output_dir / "entry_rsi_skip_entries.csv", [row for result in results for row in result["entry_log"]])
    print(json.dumps(payload, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
