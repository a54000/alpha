#!/usr/bin/env python3
"""Research-only 10:30 entry with opening-candle VWAP skip.

Rule tested:
  - Signal on T.
  - On T+1, use 09:15 opening candle as the early reference.
  - Planned entry is the 10:30 bar open.
  - Skip if 10:30 open > opening-candle VWAP proxy + threshold.

The 15-minute table does not contain tick-level VWAP, so opening-candle VWAP is
approximated as the 09:15 candle typical price: (high + low + close) / 3.

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
OUTPUT_DIR = REPO_ROOT / "results" / "entry_1030_opening_vwap_skip_experiment"


@dataclass(frozen=True)
class Variant:
    name: str
    entry_mode: str
    skip_opening_vwap: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run 10:30 entry with opening-candle VWAP skip.")
    parser.add_argument("--recommendations-csv", type=Path, default=RECOMMENDATIONS_CSV)
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2022, 5, 25))
    parser.add_argument("--end-date", type=date.fromisoformat, default=date(2026, 6, 11))
    parser.add_argument("--initial-capital", type=float, default=1_000_000.0)
    parser.add_argument("--pilot-schema", default="pilot_phase2a")
    parser.add_argument("--portfolio-size", type=int, default=10)
    parser.add_argument("--weekly-picks", type=int, default=5)
    parser.add_argument("--holding-period", type=int, default=20)
    parser.add_argument("--entry-time", type=time.fromisoformat, default=time(10, 30))
    parser.add_argument("--opening-time", type=time.fromisoformat, default=time(9, 15))
    parser.add_argument("--vwap-threshold", type=float, default=0.01)
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


def load_intraday_refs(engine, symbols: set[str], start_date: date, end_date: date, opening_time: time, entry_time: time) -> dict[tuple[str, date], dict[str, float]]:
    query = text(
        """
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
          AND datetime::time IN (:opening_time, :entry_time)
        ORDER BY symbol, datetime
        """
    )
    with engine.connect() as connection:
        rows = connection.execute(
            query,
            {"symbols": list(symbols), "start_date": start_date, "end_date": end_date, "opening_time": opening_time, "entry_time": entry_time},
        ).mappings().all()
    out: dict[tuple[str, date], dict[str, float]] = {}
    for row in rows:
        target = out.setdefault((str(row["symbol"]), row["date"]), {})
        prefix = "opening" if row["bar_time"] == opening_time else "entry"
        target[f"{prefix}_open"] = float(row["open"])
        target[f"{prefix}_high"] = float(row["high"])
        target[f"{prefix}_low"] = float(row["low"])
        target[f"{prefix}_close"] = float(row["close"])
        target[f"{prefix}_volume"] = float(row["volume"] or 0)
        if prefix == "opening":
            target["opening_vwap_proxy"] = (float(row["high"]) + float(row["low"]) + float(row["close"])) / 3.0
    return out


def all_trading_dates(prices: dict[str, dict[date, dict[str, float]]]) -> list[date]:
    return sorted({day for symbol_prices in prices.values() for day in symbol_prices})


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
    intraday: dict[tuple[str, date], dict[str, float]],
    *,
    start_date: date,
    end_date: date,
    initial_capital: float,
    portfolio_size: int,
    weekly_picks: int,
    holding_period: int,
    vwap_threshold: float,
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
                ref = intraday.get((symbol, current_date), {})
                daily_open = prices.get(symbol, {}).get(current_date, {}).get("open")
                entry_price = daily_open if variant.entry_mode == "daily_open" else ref.get("entry_open")
                opening_vwap = ref.get("opening_vwap_proxy")
                entry_vs_opening_vwap = (entry_price / opening_vwap - 1.0) if entry_price and opening_vwap else None
                poor_entry = entry_vs_opening_vwap is not None and entry_vs_opening_vwap > vwap_threshold
                base_log = {
                    "variant": variant.name,
                    "signal_date": signal_date.isoformat(),
                    "entry_date": current_date.isoformat(),
                    "symbol": symbol,
                    "sector": sector,
                    "rank": int(rec["rank"]),
                    "score": rec.get("score"),
                    "entry_price": entry_price,
                    "daily_open": daily_open,
                    "entry_1030_open": ref.get("entry_open"),
                    "opening_open": ref.get("opening_open"),
                    "opening_high": ref.get("opening_high"),
                    "opening_low": ref.get("opening_low"),
                    "opening_close": ref.get("opening_close"),
                    "opening_vwap_proxy": opening_vwap,
                    "entry_vs_opening_vwap_pct": entry_vs_opening_vwap,
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
                if variant.skip_opening_vwap and poor_entry:
                    entry_log.append({**base_log, "status": "skipped", "reason": "entry_gt_opening_vwap_threshold"})
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
        "# 10:30 Entry With Opening-Candle VWAP Skip",
        "",
        "Research-only experiment. No production scores, recommendations, strategy rules, or database rows were modified.",
        "",
        "- Opening-candle VWAP proxy: 09:15 candle typical price `(high + low + close) / 3`.",
        f"- Skip rule: 10:30 entry open > opening-candle VWAP proxy + {fmt_pct(payload['parameters']['vwap_threshold'])}.",
        "",
        "## Portfolio Metrics",
        "",
        "| Variant | CAGR | Total Return | Max DD | Sharpe | Sortino | PF | Win Rate | Trades | Avg Cash | Poor Entered | Poor Skipped |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['variant']} | {fmt_pct(row['cagr'])} | {fmt_pct(row['total_return'])} | {fmt_pct(row['max_drawdown'])} | "
            f"{fmt_num(row['sharpe_ratio'])} | {fmt_num(row['sortino_ratio'])} | {fmt_num(row['profit_factor'])} | "
            f"{fmt_pct(row['win_rate'])} | {fmt_num(row['closed_trades'])} | {fmt_pct(row['avg_cash_pct'])} | "
            f"{row['poor_entries_entered']} | {row['poor_entries_skipped']} |"
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
    intraday = load_intraday_refs(engine, symbols, args.start_date, args.end_date, args.opening_time, args.entry_time)
    variants = [
        Variant("rolling_10_1m3m_daily_open_baseline", "daily_open", False),
        Variant("rolling_10_1m3m_entry_1030", "entry_1030", False),
        Variant("rolling_10_1m3m_entry_1030_skip_opening_vwap_1pct", "entry_1030", True),
    ]
    results = [
        run_variant(
            variant,
            recommendations,
            prices,
            intraday,
            start_date=args.start_date,
            end_date=args.end_date,
            initial_capital=args.initial_capital,
            portfolio_size=args.portfolio_size,
            weekly_picks=args.weekly_picks,
            holding_period=args.holding_period,
            vwap_threshold=args.vwap_threshold,
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
                "poor_entries_entered": sum(1 for row in entries if row.get("status") == "entered" and row.get("poor_entry_quality")),
                "poor_entries_skipped": sum(1 for row in entries if row.get("reason") == "entry_gt_opening_vwap_threshold"),
            }
        )
    best = max(summary, key=lambda row: (float(row["sharpe_ratio"]), float(row["cagr"])))
    base = summary[0]
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
            "opening_time": args.opening_time.isoformat(),
            "entry_time": args.entry_time.isoformat(),
            "vwap_threshold": args.vwap_threshold,
            "vwap_proxy_note": "15-minute OHLCV does not contain tick-level VWAP; opening-candle VWAP is approximated by 09:15 typical price.",
        },
        "summary": summary,
        "financial_year_returns": [row for result in results for row in result["financial_year_returns"]],
        "constraints": {
            "database_modified": False,
            "production_scoring_changed": False,
            "production_recommendations_changed": False,
            "strategy_rules_changed": False,
        },
        "verdict": f"{best['variant']} is best by Sharpe: {best['sharpe_ratio']:.2f} vs daily-open baseline {base['sharpe_ratio']:.2f}; CAGR {best['cagr'] * 100:.2f}% vs baseline {base['cagr'] * 100:.2f}%.",
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "entry_1030_opening_vwap_skip_experiment.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    (args.output_dir / "ENTRY_1030_OPENING_VWAP_SKIP_EXPERIMENT.md").write_text(render_report(payload), encoding="utf-8")
    write_csv(args.output_dir / "entry_1030_opening_vwap_skip_summary.csv", summary)
    write_csv(args.output_dir / "entry_1030_opening_vwap_skip_fy_returns.csv", payload["financial_year_returns"])
    write_csv(args.output_dir / "entry_1030_opening_vwap_skip_equity.csv", [row for result in results for row in result["equity_curve"]])
    write_csv(args.output_dir / "entry_1030_opening_vwap_skip_trades.csv", [row for result in results for row in result["trades"]])
    write_csv(args.output_dir / "entry_1030_opening_vwap_skip_entries.csv", [row for result in results for row in result["entry_log"]])
    print(json.dumps(payload, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
