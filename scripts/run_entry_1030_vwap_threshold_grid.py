#!/usr/bin/env python3
"""Research-only 10:30 cumulative VWAP threshold grid.

Uses 1M/3M 40/60 recommendations and Rolling 10 lifecycle.
Entry is the 10:30 bar open on T+1. VWAP is cumulative only through the
10:30 bar, so no later same-day data is used.

Tests thresholds with both half-size and skip modes.
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
OUTPUT_DIR = REPO_ROOT / "results" / "entry_1030_vwap_threshold_grid"


@dataclass(frozen=True)
class Variant:
    name: str
    mode: str
    threshold: float | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run 10:30 live-safe VWAP threshold grid.")
    parser.add_argument("--recommendations-csv", type=Path, default=RECOMMENDATIONS_CSV)
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2022, 5, 25))
    parser.add_argument("--end-date", type=date.fromisoformat, default=date(2026, 6, 11))
    parser.add_argument("--initial-capital", type=float, default=1_000_000.0)
    parser.add_argument("--pilot-schema", default="pilot_phase2a")
    parser.add_argument("--portfolio-size", type=int, default=10)
    parser.add_argument("--weekly-picks", type=int, default=5)
    parser.add_argument("--holding-period", type=int, default=20)
    parser.add_argument("--entry-time", type=time.fromisoformat, default=time(10, 30))
    parser.add_argument("--thresholds", default="0.01,0.015,0.02,0.025")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    return parser.parse_args()


def parse_thresholds(value: str) -> list[float]:
    return [float(item.strip()) for item in value.split(",") if item.strip()]


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


def load_entry_1030(engine, symbols: set[str], start_date: date, end_date: date, entry_time: time) -> dict[tuple[str, date], dict[str, float]]:
    query = text(
        """
        WITH bars AS (
            SELECT
                symbol,
                datetime::date AS date,
                datetime::time AS bar_time,
                open,
                high,
                low,
                close,
                volume
            FROM ohlcv_15min
            WHERE symbol = ANY(:symbols)
              AND datetime::date BETWEEN :start_date AND :end_date
              AND datetime::time <= :entry_time
        ),
        vwap AS (
            SELECT
                symbol,
                date,
                SUM(((high + low + close) / 3.0) * volume) / NULLIF(SUM(volume), 0) AS cumulative_vwap
            FROM bars
            GROUP BY symbol, date
        ),
        entry_bar AS (
            SELECT symbol, date, open AS entry_open, high AS entry_high, low AS entry_low, close AS entry_close, volume AS entry_volume
            FROM bars
            WHERE bar_time = :entry_time
        )
        SELECT e.symbol, e.date, e.entry_open, e.entry_high, e.entry_low, e.entry_close, e.entry_volume, v.cumulative_vwap
        FROM entry_bar e
        JOIN vwap v ON v.symbol = e.symbol AND v.date = e.date
        """
    )
    with engine.connect() as connection:
        rows = connection.execute(query, {"symbols": list(symbols), "start_date": start_date, "end_date": end_date, "entry_time": entry_time}).mappings().all()
    return {
        (str(row["symbol"]), row["date"]): {
            "entry_open": float(row["entry_open"]),
            "entry_high": float(row["entry_high"]),
            "entry_low": float(row["entry_low"]),
            "entry_close": float(row["entry_close"]),
            "entry_volume": float(row["entry_volume"] or 0),
            "cumulative_vwap": float(row["cumulative_vwap"]) if row["cumulative_vwap"] is not None else None,
        }
        for row in rows
    }


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
    output = []
    for label, rows in sorted(groups.items()):
        rows.sort(key=lambda row: str(row["date"]))
        start = float(rows[0]["equity"])
        end = float(rows[-1]["equity"])
        output.append(
            {
                "variant": variant,
                "financial_year": label,
                "start_date": rows[0]["date"],
                "end_date": rows[-1]["date"],
                "start_equity": start,
                "end_equity": end,
                "return_pct": end / start - 1.0 if start else None,
                "max_drawdown": max_drawdown([float(row["equity"]) for row in rows]),
            }
        )
    return output


def run_variant(
    variant: Variant,
    recommendations: list[dict[str, object]],
    prices: dict[str, dict[date, dict[str, float]]],
    entry_1030: dict[tuple[str, date], dict[str, float]],
    *,
    start_date: date,
    end_date: date,
    initial_capital: float,
    portfolio_size: int,
    weekly_picks: int,
    holding_period: int,
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
                intraday = entry_1030.get((symbol, current_date), {})
                entry_price = intraday.get("entry_open")
                cumulative_vwap = intraday.get("cumulative_vwap")
                entry_vs_vwap = (entry_price / cumulative_vwap - 1.0) if entry_price and cumulative_vwap else None
                poor_entry = variant.threshold is not None and entry_vs_vwap is not None and entry_vs_vwap > variant.threshold
                base_log = {
                    "variant": variant.name,
                    "mode": variant.mode,
                    "threshold": variant.threshold,
                    "signal_date": signal_date.isoformat(),
                    "entry_date": current_date.isoformat(),
                    "symbol": symbol,
                    "sector": sector,
                    "rank": int(rec["rank"]),
                    "score": rec.get("score"),
                    "entry_1030_open": entry_price,
                    "entry_1030_close": intraday.get("entry_close"),
                    "cumulative_vwap_to_1030": cumulative_vwap,
                    "entry_vs_vwap_pct": entry_vs_vwap,
                    "poor_entry_quality": poor_entry,
                }
                if len(positions) >= portfolio_size:
                    entry_log.append({**base_log, "status": "skipped", "reason": "portfolio_full"})
                    continue
                if symbol in held or symbol in closed_today:
                    entry_log.append({**base_log, "status": "skipped", "reason": "already_held_or_closed_today"})
                    continue
                if entry_price is None or entry_price <= 0:
                    entry_log.append({**base_log, "status": "skipped", "reason": "missing_entry_price"})
                    continue
                if variant.mode == "skip" and poor_entry:
                    entry_log.append({**base_log, "status": "skipped", "reason": "entry_gt_cumulative_vwap_threshold"})
                    continue
                multiplier = 0.5 if variant.mode == "half_size" and poor_entry else 1.0
                allocation = min(target_value * multiplier, cash)
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
                        entry_price=float(entry_price),
                        quantity=allocation / float(entry_price),
                        planned_exit_date=planned_exit,
                        rank=int(rec["rank"]),
                        score=float(rec["score"]) if rec.get("score") is not None else None,
                        entry_value=allocation,
                        buy_charges=buy_charges,
                    )
                )
                held.add(symbol)
                entry_log.append({**base_log, "status": "entered", "reason": "entered", "allocation": allocation, "allocation_multiplier": multiplier})

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
    return {"variant": variant.name, "metrics": metrics(initial_capital, equity_curve, trades, turnover), "equity_curve": equity_curve, "trades": trades, "entry_log": entry_log, "financial_year_returns": fy_returns(equity_curve, variant.name)}


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
        "# 10:30 Live-Safe VWAP Threshold Grid",
        "",
        "Research-only experiment. No production scores, recommendations, strategy rules, or database rows were modified.",
        "",
        "- Entry: 10:30 bar open on T+1.",
        "- VWAP: cumulative intraday VWAP through the 10:30 bar only.",
        "",
        "## Portfolio Metrics",
        "",
        "| Variant | Mode | Threshold | CAGR | Max DD | Sharpe | Sortino | PF | Win Rate | Trades | Avg Cash | Poor Entered | Poor Skipped |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['variant']} | {row['mode']} | {fmt_pct(row.get('threshold'))} | {fmt_pct(row['cagr'])} | {fmt_pct(row['max_drawdown'])} | "
            f"{fmt_num(row['sharpe_ratio'])} | {fmt_num(row['sortino_ratio'])} | {fmt_num(row['profit_factor'])} | "
            f"{fmt_pct(row['win_rate'])} | {fmt_num(row['closed_trades'])} | {fmt_pct(row['avg_cash_pct'])} | "
            f"{row['poor_entries_entered']} | {row['poor_entries_skipped']} |"
        )
    lines.extend(["", "## Best Candidates", ""])
    for key, value in payload["best"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Verdict", "", str(payload["verdict"])])
    return "\n".join(lines) + "\n"


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    args = parse_args()
    angel_url = os.environ.get("ANGEL_DATABASE_URL")
    if not angel_url:
        raise RuntimeError("ANGEL_DATABASE_URL is required.")
    thresholds = parse_thresholds(args.thresholds)
    engine = create_engine(angel_url, future=True, pool_pre_ping=True)
    recommendations = load_recommendations(args.recommendations_csv, args.start_date, args.end_date)
    symbols = {str(row["symbol"]) for row in recommendations}
    prices = load_prices(engine, args.pilot_schema, symbols, args.start_date, args.end_date)
    entry_1030 = load_entry_1030(engine, symbols, args.start_date, args.end_date, args.entry_time)

    variants = [Variant("rolling_10_1m3m_entry_1030_baseline", "baseline", None)]
    for threshold in thresholds:
        label = str(int(round(threshold * 1000))).zfill(2)
        variants.append(Variant(f"rolling_10_1m3m_entry_1030_half_size_vwap_{label}bp", "half_size", threshold))
        variants.append(Variant(f"rolling_10_1m3m_entry_1030_skip_vwap_{label}bp", "skip", threshold))

    results = [
        run_variant(
            variant,
            recommendations,
            prices,
            entry_1030,
            start_date=args.start_date,
            end_date=args.end_date,
            initial_capital=args.initial_capital,
            portfolio_size=args.portfolio_size,
            weekly_picks=args.weekly_picks,
            holding_period=args.holding_period,
        )
        for variant in variants
    ]
    summary = []
    for result, variant in zip(results, variants):
        entries = result["entry_log"]
        summary.append(
            {
                "variant": result["variant"],
                "mode": variant.mode,
                "threshold": variant.threshold,
                **result["metrics"],
                "entries_entered": sum(1 for row in entries if row.get("status") == "entered"),
                "poor_entries_entered": sum(1 for row in entries if row.get("status") == "entered" and row.get("poor_entry_quality")),
                "poor_entries_skipped": sum(1 for row in entries if row.get("reason") == "entry_gt_cumulative_vwap_threshold"),
            }
        )
    best = {
        "by_cagr": max(summary, key=lambda row: float(row["cagr"]))["variant"],
        "by_sharpe": max(summary, key=lambda row: float(row["sharpe_ratio"]))["variant"],
        "by_drawdown": max(summary, key=lambda row: float(row["max_drawdown"]))["variant"],
        "by_profit_factor": max(summary, key=lambda row: float(row["profit_factor"] or -999))["variant"],
    }
    baseline = summary[0]
    best_sharpe = next(row for row in summary if row["variant"] == best["by_sharpe"])
    verdict = (
        f"Best Sharpe candidate is {best_sharpe['variant']} with Sharpe {best_sharpe['sharpe_ratio']:.2f}, "
        f"CAGR {best_sharpe['cagr'] * 100:.2f}%, max DD {best_sharpe['max_drawdown'] * 100:.2f}%, "
        f"versus 10:30 baseline Sharpe {baseline['sharpe_ratio']:.2f} and CAGR {baseline['cagr'] * 100:.2f}%."
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
            "entry_time": args.entry_time.isoformat(),
            "thresholds": thresholds,
            "vwap_timing": "Cumulative intraday VWAP through the 10:30 bar; no later same-day bars used.",
        },
        "summary": summary,
        "financial_year_returns": [row for result in results for row in result["financial_year_returns"]],
        "best": best,
        "constraints": {
            "database_modified": False,
            "production_scoring_changed": False,
            "production_recommendations_changed": False,
            "strategy_rules_changed": False,
        },
        "verdict": verdict,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "entry_1030_vwap_threshold_grid.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    (args.output_dir / "ENTRY_1030_VWAP_THRESHOLD_GRID.md").write_text(render_report(payload), encoding="utf-8")
    write_csv(args.output_dir / "entry_1030_vwap_threshold_grid_summary.csv", summary)
    write_csv(args.output_dir / "entry_1030_vwap_threshold_grid_fy_returns.csv", payload["financial_year_returns"])
    write_csv(args.output_dir / "entry_1030_vwap_threshold_grid_equity.csv", [row for result in results for row in result["equity_curve"]])
    write_csv(args.output_dir / "entry_1030_vwap_threshold_grid_trades.csv", [row for result in results for row in result["trades"]])
    write_csv(args.output_dir / "entry_1030_vwap_threshold_grid_entries.csv", [row for result in results for row in result["entry_log"]])
    print(json.dumps(payload, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
