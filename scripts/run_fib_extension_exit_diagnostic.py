#!/usr/bin/env python3
"""Read-only Fibonacci extension exit diagnostic for the final Rolling 10 setup.

The script consumes the existing final-candidate trade ledger and entry log, then
compares the current planned 20-trading-day exit with hypothetical Fibonacci
extension exits. It writes reports only; no database rows or strategy settings
are modified.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.api.trade_analysis_service import total_charges, zerodha_default_charges  # noqa: E402

DEFAULT_INPUT_DIR = REPO_ROOT / "results" / "entry_1030_prevday_vwap_grid"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "results" / "fib_extension_exit_diagnostic"
DEFAULT_VARIANT = "rolling_10_1m3m_entry_1030_skip_prevday_vwap_25bp"
FIB_LEVELS = (1.272, 1.618, 2.0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Fibonacci extension exit diagnostic.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--variant", default=DEFAULT_VARIANT)
    parser.add_argument("--pilot-schema", default="pilot_phase2a")
    parser.add_argument("--swing-lookback", type=int, default=20)
    parser.add_argument("--partial-target", type=float, default=1.618)
    return parser.parse_args()


def parse_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)).date()


def fmt_pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.2f}%"


def fmt_num(value: float | None) -> str:
    return "n/a" if value is None else f"{value:,.2f}"


def load_trades(path: Path, variant: str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame = frame[frame["strategy"] == variant].copy()
    if frame.empty:
        raise RuntimeError(f"No trades found for variant {variant!r} in {path}")
    for column in ("entry_date", "exit_date"):
        frame[column] = pd.to_datetime(frame[column]).dt.date
    return frame.sort_values(["entry_date", "symbol", "trade_id"]).reset_index(drop=True)


def load_entries(path: Path, variant: str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame = frame[(frame["variant"] == variant) & (frame["status"] == "entered")].copy()
    if frame.empty:
        raise RuntimeError(f"No entered rows found for variant {variant!r} in {path}")
    for column in ("signal_date", "entry_date"):
        frame[column] = pd.to_datetime(frame[column]).dt.date
    return frame.sort_values(["entry_date", "symbol"]).reset_index(drop=True)


def load_daily_bars(engine, schema: str, symbols: set[str], start_date: date, end_date: date) -> dict[str, list[dict[str, Any]]]:
    query = text(
        f"""
        SELECT symbol, date, open, high, low, close, volume
        FROM {schema}.daily_bars_clean
        WHERE symbol = ANY(:symbols)
          AND date BETWEEN :start_date AND :end_date
        ORDER BY symbol, date
        """
    )
    with engine.connect() as connection:
        rows = connection.execute(
            query,
            {"symbols": sorted(symbols), "start_date": start_date, "end_date": end_date},
        ).mappings().all()
    bars: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        bars.setdefault(str(row["symbol"]), []).append(
            {
                "date": row["date"],
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": int(row["volume"] or 0),
            }
        )
    return bars


def prior_bars(symbol_bars: list[dict[str, Any]], signal_date: date, lookback: int) -> list[dict[str, Any]]:
    previous = [row for row in symbol_bars if row["date"] < signal_date]
    return previous[-lookback:]


def holding_bars(symbol_bars: list[dict[str, Any]], entry_date: date, exit_date: date) -> list[dict[str, Any]]:
    return [row for row in symbol_bars if entry_date <= row["date"] <= exit_date]


def first_level_hit(path: list[dict[str, Any]], level: float) -> tuple[date | None, int | None]:
    for index, row in enumerate(path, start=1):
        if row["high"] >= level:
            return row["date"], index
    return None, None


def net_return(entry_value: float, quantity: float, exit_price: float) -> tuple[float, float]:
    exit_value = quantity * exit_price
    charges = zerodha_default_charges(entry_value, exit_value)
    pnl = exit_value - entry_value - total_charges(charges)
    return pnl, pnl / entry_value if entry_value else 0.0


def partial_50_return(entry_value: float, quantity: float, target_price: float, planned_exit_price: float) -> tuple[float, float]:
    target_quantity = quantity * 0.5
    planned_quantity = quantity - target_quantity
    target_value = target_quantity * target_price
    planned_value = planned_quantity * planned_exit_price
    charges_target = zerodha_default_charges(entry_value * 0.5, target_value)
    charges_planned = zerodha_default_charges(entry_value * 0.5, planned_value)
    pnl = target_value + planned_value - entry_value - total_charges(charges_target) - total_charges(charges_planned)
    return pnl, pnl / entry_value if entry_value else 0.0


def analyze_trade(row: pd.Series, signal_date: date, symbol_bars: list[dict[str, Any]], lookback: int, partial_target: float) -> dict[str, Any]:
    symbol = str(row["symbol"])
    entry_date = parse_date(row["entry_date"])
    exit_date = parse_date(row["exit_date"])
    entry_price = float(row["entry_price"])
    exit_price = float(row["exit_price"])
    entry_value = float(row["entry_value"])
    quantity = float(row["quantity"])
    current_net_return = float(row["net_return_pct"])

    prior = prior_bars(symbol_bars, signal_date, lookback)
    path = holding_bars(symbol_bars, entry_date, exit_date)
    result: dict[str, Any] = {
        "trade_id": int(row["trade_id"]),
        "symbol": symbol,
        "sector": row.get("sector"),
        "signal_date": signal_date.isoformat(),
        "entry_date": entry_date.isoformat(),
        "planned_exit_date": exit_date.isoformat(),
        "entry_price": entry_price,
        "planned_exit_price": exit_price,
        "current_net_return_pct": current_net_return,
        "swing_lookback_rows": len(prior),
        "holding_path_rows": len(path),
    }
    if len(prior) < lookback or not path:
        result.update({"diagnostic_status": "insufficient_data"})
        return result

    swing_low = min(item["low"] for item in prior)
    swing_high = max(item["high"] for item in prior)
    swing_range = swing_high - swing_low
    result.update(
        {
            "diagnostic_status": "ok" if swing_range > 0 else "invalid_swing_range",
            "swing_low": swing_low,
            "swing_high": swing_high,
            "swing_range": swing_range,
            "entry_vs_swing_position": (entry_price - swing_low) / swing_range if swing_range > 0 else None,
            "mfe_pct": max(item["high"] for item in path) / entry_price - 1.0,
            "mae_pct": min(item["low"] for item in path) / entry_price - 1.0,
        }
    )
    if swing_range <= 0:
        return result

    partial_level_price: float | None = None
    partial_hit = False
    for fib in FIB_LEVELS:
        level = swing_low + swing_range * fib
        hit_date, hit_day = first_level_hit(path, level)
        target_pnl, target_return = net_return(entry_value, quantity, level)
        entry_above = entry_price > level
        result.update(
            {
                f"fib_{str(fib).replace('.', '_')}_price": level,
                f"fib_{str(fib).replace('.', '_')}_hit": hit_date is not None,
                f"fib_{str(fib).replace('.', '_')}_hit_date": hit_date.isoformat() if hit_date else None,
                f"fib_{str(fib).replace('.', '_')}_hit_holding_day": hit_day,
                f"fib_{str(fib).replace('.', '_')}_full_exit_net_return_pct": target_return,
                f"entry_above_fib_{str(fib).replace('.', '_')}": entry_above,
            }
        )
        if fib == partial_target:
            partial_level_price = level
            partial_hit = hit_date is not None

    if partial_level_price is not None and partial_hit:
        partial_pnl, partial_return = partial_50_return(entry_value, quantity, partial_level_price, exit_price)
    else:
        partial_pnl, partial_return = float(row["net_pnl"]), current_net_return
    result.update(
        {
            "partial_50_at_target": partial_target,
            "partial_50_target_hit": partial_hit,
            "partial_50_then_planned_net_pnl": partial_pnl,
            "partial_50_then_planned_net_return_pct": partial_return,
            "partial_50_return_delta_pct": partial_return - current_net_return,
        }
    )
    return result


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ok = [row for row in rows if row.get("diagnostic_status") == "ok"]
    winners = [row for row in ok if float(row["current_net_return_pct"]) > 0]
    losers = [row for row in ok if float(row["current_net_return_pct"]) < 0]
    summary: dict[str, Any] = {
        "total_trades": len(rows),
        "diagnosable_trades": len(ok),
        "insufficient_data_trades": len(rows) - len(ok),
        "current_avg_return": statistics.mean([float(row["current_net_return_pct"]) for row in ok]) if ok else 0.0,
        "partial_50_avg_return": statistics.mean([float(row["partial_50_then_planned_net_return_pct"]) for row in ok]) if ok else 0.0,
        "partial_50_total_delta_pct_points": sum(float(row["partial_50_return_delta_pct"]) for row in ok),
        "losers_entered_above_1_272": sum(1 for row in losers if row.get("entry_above_fib_1_272")),
        "losers_entered_above_1_618": sum(1 for row in losers if row.get("entry_above_fib_1_618")),
    }
    for fib in FIB_LEVELS:
        key = str(fib).replace(".", "_")
        hit_rows = [row for row in ok if row.get(f"fib_{key}_hit")]
        summary[f"fib_{key}_hit_count"] = len(hit_rows)
        summary[f"fib_{key}_hit_rate"] = len(hit_rows) / len(ok) if ok else 0.0
        summary[f"winner_fib_{key}_hit_rate"] = sum(1 for row in winners if row.get(f"fib_{key}_hit")) / len(winners) if winners else 0.0
        summary[f"loser_fib_{key}_hit_rate"] = sum(1 for row in losers if row.get(f"fib_{key}_hit")) / len(losers) if losers else 0.0
        summary[f"entry_above_fib_{key}_count"] = sum(1 for row in ok if row.get(f"entry_above_fib_{key}"))
    return summary


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def render_markdown(summary: dict[str, Any], rows: list[dict[str, Any]], args: argparse.Namespace) -> str:
    lines = [
        "# Fibonacci Extension Exit Diagnostic",
        "",
        "Read-only diagnostic. No strategy rules, recommendations, scores, paper portfolios, or database rows were modified.",
        "",
        "## Setup",
        "",
        f"- Variant: `{args.variant}`",
        f"- Swing lookback: {args.swing_lookback} trading rows before signal date",
        "- Extension formula: `swing_low + (swing_high - swing_low) * extension`",
        f"- Partial-profit test: sell 50% at {args.partial_target} extension if reached, hold remaining 50% to planned 20-trading-day exit",
        "- Costs: existing Zerodha default charge model",
        "",
        "## Summary",
        "",
        f"- Total trades: {summary['total_trades']}",
        f"- Diagnosable trades: {summary['diagnosable_trades']}",
        f"- Current average net return: {fmt_pct(summary['current_avg_return'])}",
        f"- 50% Fib target average net return: {fmt_pct(summary['partial_50_avg_return'])}",
        f"- Aggregate return delta, percentage-point sum: {fmt_pct(summary['partial_50_total_delta_pct_points'])}",
        f"- Losers entered above 1.272 extension: {summary['losers_entered_above_1_272']}",
        f"- Losers entered above 1.618 extension: {summary['losers_entered_above_1_618']}",
        "",
        "## Extension Hit Rates",
        "",
        "| Extension | Hit Count | Hit Rate | Winner Hit Rate | Loser Hit Rate | Entries Already Above Level |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for fib in FIB_LEVELS:
        key = str(fib).replace(".", "_")
        lines.append(
            f"| {fib:.3f} | {summary[f'fib_{key}_hit_count']} | {fmt_pct(summary[f'fib_{key}_hit_rate'])} | "
            f"{fmt_pct(summary[f'winner_fib_{key}_hit_rate'])} | {fmt_pct(summary[f'loser_fib_{key}_hit_rate'])} | "
            f"{summary[f'entry_above_fib_{key}_count']} |"
        )

    best_delta = sorted(
        [row for row in rows if row.get("diagnostic_status") == "ok"],
        key=lambda item: float(item.get("partial_50_return_delta_pct") or 0.0),
        reverse=True,
    )[:10]
    worst_delta = sorted(
        [row for row in rows if row.get("diagnostic_status") == "ok"],
        key=lambda item: float(item.get("partial_50_return_delta_pct") or 0.0),
    )[:10]
    lines.extend(["", "## Top 10 Trades Helped By Partial Fib Exit", "", "| Symbol | Entry | Planned Return | Partial Return | Delta | MFE | MAE |", "| --- | --- | ---: | ---: | ---: | ---: | ---: |"])
    for row in best_delta:
        lines.append(
            f"| {row['symbol']} | {row['entry_date']} | {fmt_pct(float(row['current_net_return_pct']))} | "
            f"{fmt_pct(float(row['partial_50_then_planned_net_return_pct']))} | {fmt_pct(float(row['partial_50_return_delta_pct']))} | "
            f"{fmt_pct(float(row['mfe_pct']))} | {fmt_pct(float(row['mae_pct']))} |"
        )
    lines.extend(["", "## Top 10 Trades Hurt By Partial Fib Exit", "", "| Symbol | Entry | Planned Return | Partial Return | Delta | MFE | MAE |", "| --- | --- | ---: | ---: | ---: | ---: | ---: |"])
    for row in worst_delta:
        lines.append(
            f"| {row['symbol']} | {row['entry_date']} | {fmt_pct(float(row['current_net_return_pct']))} | "
            f"{fmt_pct(float(row['partial_50_then_planned_net_return_pct']))} | {fmt_pct(float(row['partial_50_return_delta_pct']))} | "
            f"{fmt_pct(float(row['mfe_pct']))} | {fmt_pct(float(row['mae_pct']))} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation Checklist",
            "",
            "- If many winners hit 1.272/1.618 and then give back gains, partial exits may improve risk-adjusted returns.",
            "- If many losers entered above 1.272/1.618, an overextension skip deserves a separate backtest.",
            "- If partial exits reduce average return materially, the 20-day hold is still doing important winner capture.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    load_dotenv(REPO_ROOT / ".env")
    trades_path = args.input_dir / "entry_1030_prevday_vwap_grid_trades.csv"
    entries_path = args.input_dir / "entry_1030_prevday_vwap_grid_entries.csv"
    trades = load_trades(trades_path, args.variant)
    entries = load_entries(entries_path, args.variant)
    signal_lookup = {
        (str(row.symbol), parse_date(row.entry_date), int(row.rank)): parse_date(row.signal_date)
        for row in entries.itertuples(index=False)
        if getattr(row, "status", "") == "entered"
    }
    fallback_signal_lookup = {
        (str(row.symbol), parse_date(row.entry_date)): parse_date(row.signal_date)
        for row in entries.itertuples(index=False)
    }
    symbols = {str(symbol) for symbol in trades["symbol"].unique()}
    start_date = min(trades["entry_date"]) - pd.Timedelta(days=90)
    end_date = max(trades["exit_date"])
    angel_url = os.environ.get("ANGEL_DATABASE_URL")
    if not angel_url:
        raise RuntimeError("ANGEL_DATABASE_URL is required.")
    engine = create_engine(angel_url)
    bars = load_daily_bars(engine, args.pilot_schema, symbols, parse_date(start_date), parse_date(end_date))

    rows: list[dict[str, Any]] = []
    for trade in trades.itertuples(index=False):
        trade_row = pd.Series(trade._asdict())
        symbol = str(trade_row["symbol"])
        entry_date = parse_date(trade_row["entry_date"])
        rank_value = int(float(trade_row.get("rank", 0))) if "rank" in trade_row else 0
        signal_date = signal_lookup.get((symbol, entry_date, rank_value)) or fallback_signal_lookup.get((symbol, entry_date))
        if signal_date is None:
            result = trade_row.to_dict()
            result.update({"diagnostic_status": "missing_signal_date", "entry_date": entry_date.isoformat()})
            rows.append(result)
            continue
        rows.append(analyze_trade(trade_row, signal_date, bars.get(symbol, []), args.swing_lookback, args.partial_target))

    summary = summarize(rows)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "variant": args.variant,
        "parameters": {
            "swing_lookback": args.swing_lookback,
            "fib_levels": list(FIB_LEVELS),
            "partial_target": args.partial_target,
            "pilot_schema": args.pilot_schema,
        },
        "summary": summary,
        "artifacts": {
            "csv": "fib_extension_trade_diagnostic.csv",
            "json": "fib_extension_exit_diagnostic.json",
            "markdown": "FIB_EXTENSION_EXIT_DIAGNOSTIC.md",
        },
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / "fib_extension_trade_diagnostic.csv", rows)
    (args.output_dir / "fib_extension_exit_diagnostic.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    (args.output_dir / "FIB_EXTENSION_EXIT_DIAGNOSTIC.md").write_text(render_markdown(summary, rows, args), encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str))
    print(f"Wrote Fibonacci diagnostic reports: {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
