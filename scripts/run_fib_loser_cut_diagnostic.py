#!/usr/bin/env python3
"""Read-only Fibonacci loser-cut diagnostic for Sector Rotation ADX Rolling 10.

Tests whether Fibonacci-derived downside/invalidation levels would have cut
losing trades earlier. This is diagnostic only; it does not change strategy
logic, recommendations, portfolio rules, or database state.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import statistics
import sys
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.api.trade_analysis_service import total_charges, zerodha_default_charges  # noqa: E402

INPUT_DIR = REPO_ROOT / "results" / "entry_1030_prevday_vwap_grid"
OUTPUT_DIR = REPO_ROOT / "results" / "fib_loser_cut_diagnostic"
VARIANT = "rolling_10_1m3m_entry_1030_skip_prevday_vwap_25bp"
FIB_STOP_LEVELS = {
    "swing_high_break": None,
    "fib_0_786": 0.786,
    "fib_0_618": 0.618,
    "fib_0_500": 0.500,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Fibonacci loser-cut diagnostic.")
    parser.add_argument("--input-dir", type=Path, default=INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--variant", default=VARIANT)
    parser.add_argument("--pilot-schema", default="pilot_phase2a")
    parser.add_argument("--swing-lookback", type=int, default=20)
    parser.add_argument("--entry-time", type=time.fromisoformat, default=time(10, 30))
    parser.add_argument("--initial-capital", type=float, default=1_000_000.0)
    return parser.parse_args()


def parse_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)).date()


def fmt_pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.2f}%"


def load_trades(path: Path, variant: str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame = frame[frame["strategy"] == variant].copy()
    if frame.empty:
        raise RuntimeError(f"No trades found for variant {variant!r} in {path}")
    for column in ("entry_date", "exit_date"):
        frame[column] = pd.to_datetime(frame[column]).dt.date
    numeric = ["entry_price", "exit_price", "entry_value", "exit_value", "quantity", "net_pnl", "net_return_pct", "charges"]
    for column in numeric:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.sort_values(["entry_date", "trade_id"]).reset_index(drop=True)


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
        SELECT symbol, date, open, high, low, close
        FROM {schema}.daily_bars_clean
        WHERE symbol = ANY(:symbols)
          AND date BETWEEN :start_date AND :end_date
        ORDER BY symbol, date
        """
    )
    with engine.connect() as connection:
        rows = connection.execute(query, {"symbols": sorted(symbols), "start_date": start_date, "end_date": end_date}).mappings().all()
    out: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        out.setdefault(str(row["symbol"]), []).append(
            {"date": row["date"], "open": float(row["open"]), "high": float(row["high"]), "low": float(row["low"]), "close": float(row["close"])}
        )
    return out


def sql_literal(value: object) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def load_intraday_bars(engine, trades: pd.DataFrame) -> pd.DataFrame:
    windows = trades[["symbol", "entry_date", "exit_date"]].drop_duplicates().to_dict("records")
    values = ",\n".join(
        f"({sql_literal(row['symbol'])}, {sql_literal(row['entry_date'])}::date, {sql_literal(row['exit_date'])}::date)"
        for row in windows
    )
    query = text(
        f"""
        WITH trade_windows(symbol, entry_date, exit_date) AS (
            VALUES
            {values}
        )
        SELECT DISTINCT o.symbol, o.datetime, o.open, o.high, o.low, o.close, o.volume
        FROM ohlcv_15min o
        JOIN trade_windows tw
          ON tw.symbol = o.symbol
         AND o.datetime::date BETWEEN tw.entry_date AND tw.exit_date
        ORDER BY o.symbol, o.datetime
        """
    )
    frame = pd.read_sql_query(query, engine)
    frame["datetime"] = pd.to_datetime(frame["datetime"])
    frame["date"] = frame["datetime"].dt.date
    frame["time"] = frame["datetime"].dt.time
    for column in ("open", "high", "low", "close", "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def group_intraday(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {str(symbol): group.reset_index(drop=True) for symbol, group in frame.groupby("symbol", sort=False)}


def trade_intraday(symbol_bars: dict[str, pd.DataFrame], symbol: str, entry_date: date, exit_date: date, entry_time: time) -> pd.DataFrame:
    rows = symbol_bars.get(symbol)
    if rows is None or rows.empty:
        return pd.DataFrame()
    rows = rows[(rows["date"] >= entry_date) & (rows["date"] <= exit_date)]
    return rows[(rows["date"] > entry_date) | (rows["time"] >= entry_time)].reset_index(drop=True)


def prior_daily(symbol_bars: list[dict[str, Any]], signal_date: date, lookback: int) -> list[dict[str, Any]]:
    rows = [row for row in symbol_bars if row["date"] < signal_date]
    return rows[-lookback:]


def first_stop_hit(path: pd.DataFrame, stop_price: float) -> tuple[date | None, float | None, int | None]:
    if path.empty:
        return None, None, None
    hit = path[path["low"] <= stop_price].head(1)
    if hit.empty:
        return None, None, None
    hit_row = hit.iloc[0]
    unique_dates = list(dict.fromkeys(path["date"].tolist()))
    holding_day = unique_dates.index(hit_row["date"]) + 1 if hit_row["date"] in unique_dates else None
    return hit_row["date"], float(stop_price), holding_day


def net_pnl(entry_value: float, quantity: float, exit_price: float) -> tuple[float, float, float]:
    exit_value = quantity * exit_price
    charges = zerodha_default_charges(entry_value, exit_value)
    pnl = exit_value - entry_value - total_charges(charges)
    return pnl, pnl / entry_value if entry_value else 0.0, total_charges(charges)


def max_drawdown(values: list[float]) -> float:
    peak = values[0] if values else 0.0
    drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        if peak:
            drawdown = min(drawdown, value / peak - 1.0)
    return drawdown


def summarize_rows(rows: list[dict[str, Any]], initial_capital: float) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda row: (str(row["exit_date"]), int(row["trade_id"])))
    equity = initial_capital
    curve = [equity]
    returns = []
    for row in ordered:
        prev = equity
        equity += float(row["net_pnl"])
        curve.append(equity)
        returns.append(equity / prev - 1.0 if prev else 0.0)
    winners = [row for row in rows if float(row["net_pnl"]) > 0]
    losers = [row for row in rows if float(row["net_pnl"]) < 0]
    gross_profit = sum(float(row["net_pnl"]) for row in winners)
    gross_loss = abs(sum(float(row["net_pnl"]) for row in losers))
    first = min(parse_date(row["entry_date"]) for row in rows)
    last = max(parse_date(row["exit_date"]) for row in rows)
    years = max(1 / 252, (last - first).days / 365.25)
    stdev = statistics.stdev(returns) if len(returns) > 1 else 0.0
    return {
        "ending_equity": equity,
        "total_return": equity / initial_capital - 1.0,
        "cagr": (equity / initial_capital) ** (1 / years) - 1.0 if equity > 0 else -1.0,
        "max_drawdown": max_drawdown(curve),
        "sharpe_proxy": statistics.mean(returns) / stdev * math.sqrt(252) if stdev else None,
        "profit_factor": gross_profit / gross_loss if gross_loss else None,
        "win_rate": len(winners) / len(rows) if rows else None,
        "trade_count": len(rows),
        "avg_return": statistics.mean([float(row["net_return_pct"]) for row in rows]) if rows else None,
        "median_return": statistics.median([float(row["net_return_pct"]) for row in rows]) if rows else None,
    }


def build_trade_variants(
    trades: pd.DataFrame,
    entries: pd.DataFrame,
    daily_bars: dict[str, list[dict[str, Any]]],
    intraday_bars: dict[str, pd.DataFrame],
    lookback: int,
    entry_time: time,
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    fallback_signal = {(str(row.symbol), parse_date(row.entry_date)): parse_date(row.signal_date) for row in entries.itertuples(index=False)}
    detail_rows: list[dict[str, Any]] = []
    variant_rows: dict[str, list[dict[str, Any]]] = {"baseline": []}
    for name in FIB_STOP_LEVELS:
        variant_rows[name] = []

    for row in trades.itertuples(index=False):
        base = row._asdict()
        symbol = str(row.symbol)
        entry_date = parse_date(row.entry_date)
        exit_date = parse_date(row.exit_date)
        signal_date = fallback_signal.get((symbol, entry_date))
        baseline = {
            **base,
            "variant": "baseline",
            "exit_date": exit_date.isoformat(),
            "exit_price": float(row.exit_price),
            "net_pnl": float(row.net_pnl),
            "net_return_pct": float(row.net_return_pct),
            "exit_reason": row.exit_reason,
            "fib_stop_hit": False,
        }
        variant_rows["baseline"].append(baseline)
        prior = prior_daily(daily_bars.get(symbol, []), signal_date, lookback) if signal_date else []
        path = trade_intraday(intraday_bars, symbol, entry_date, exit_date, entry_time)
        if len(prior) < lookback or path.empty:
            detail_rows.append({**baseline, "diagnostic_status": "insufficient_data", "signal_date": signal_date.isoformat() if signal_date else None})
            for name in FIB_STOP_LEVELS:
                variant_rows[name].append({**baseline, "variant": name})
            continue

        swing_low = min(item["low"] for item in prior)
        swing_high = max(item["high"] for item in prior)
        swing_range = swing_high - swing_low
        levels = {
            "swing_high_break": swing_high,
            "fib_0_786": swing_low + swing_range * 0.786,
            "fib_0_618": swing_low + swing_range * 0.618,
            "fib_0_500": swing_low + swing_range * 0.500,
        }
        detail = {
            "trade_id": int(row.trade_id),
            "symbol": symbol,
            "sector": row.sector,
            "signal_date": signal_date.isoformat() if signal_date else None,
            "entry_date": entry_date.isoformat(),
            "planned_exit_date": exit_date.isoformat(),
            "entry_price": float(row.entry_price),
            "planned_exit_price": float(row.exit_price),
            "baseline_net_return_pct": float(row.net_return_pct),
            "swing_low": swing_low,
            "swing_high": swing_high,
            "swing_range": swing_range,
            "diagnostic_status": "ok" if swing_range > 0 else "invalid_swing_range",
            "mae_pct": float(path["low"].min()) / float(row.entry_price) - 1.0,
            "mfe_pct": float(path["high"].max()) / float(row.entry_price) - 1.0,
        }
        for name, level in levels.items():
            hit_date, stop_price, holding_day = first_stop_hit(path, level)
            usable = swing_range > 0 and level < float(row.entry_price)
            if usable and hit_date is not None and stop_price is not None:
                pnl, ret, charges = net_pnl(float(row.entry_value), float(row.quantity), stop_price)
                exit_reason = f"fib_loser_cut_{name}"
                simulated = {
                    **base,
                    "variant": name,
                    "exit_date": hit_date.isoformat(),
                    "exit_price": stop_price,
                    "exit_value": float(row.quantity) * stop_price,
                    "charges": charges,
                    "net_pnl": pnl,
                    "net_return_pct": ret,
                    "exit_reason": exit_reason,
                    "fib_stop_hit": True,
                    "fib_holding_day": holding_day,
                }
            else:
                simulated = {**baseline, "variant": name, "fib_stop_hit": False, "fib_holding_day": None}
            variant_rows[name].append(simulated)
            detail.update(
                {
                    f"{name}_price": level,
                    f"{name}_usable_below_entry": usable,
                    f"{name}_hit": bool(simulated["fib_stop_hit"]),
                    f"{name}_hit_date": simulated["exit_date"] if simulated["fib_stop_hit"] else None,
                    f"{name}_return_pct": float(simulated["net_return_pct"]),
                    f"{name}_return_delta_pct": float(simulated["net_return_pct"]) - float(row.net_return_pct),
                }
            )
        detail_rows.append(detail)
    return detail_rows, variant_rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def render_report(summary_rows: list[dict[str, Any]], detail_rows: list[dict[str, Any]]) -> str:
    baseline = next(row for row in summary_rows if row["variant"] == "baseline")
    lines = [
        "# Fibonacci Loser-Cut Diagnostic",
        "",
        "Read-only diagnostic. No strategy rules, recommendations, paper portfolios, or database rows were modified.",
        "",
        "## Question",
        "",
        "Can losing trades be cut earlier using Fibonacci-derived downside/invalidation levels?",
        "",
        "Tested levels:",
        "",
        "- `swing_high_break`: exit if price breaks below the prior 20-day swing high.",
        "- `fib_0_786`: exit if price breaks below the 78.6% retracement of the prior swing range.",
        "- `fib_0_618`: exit if price breaks below the 61.8% retracement.",
        "- `fib_0_500`: exit if price breaks below the 50.0% retracement.",
        "",
        "A level is only usable when it is below the actual entry price.",
        "",
        "## Portfolio-Level Comparison",
        "",
        "| Variant | CAGR | Total Return | Max DD | Sharpe Proxy | PF | Win Rate | Avg Return | Stop Hits | Winners Cut | Losers Cut |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary_rows:
        lines.append(
            f"| {row['variant']} | {fmt_pct(row['cagr'])} | {fmt_pct(row['total_return'])} | {fmt_pct(row['max_drawdown'])} | "
            f"{row['sharpe_proxy']:.2f} | {row['profit_factor']:.2f} | {fmt_pct(row['win_rate'])} | {fmt_pct(row['avg_return'])} | "
            f"{row['fib_stop_hits']} | {row['winner_stop_hits']} | {row['loser_stop_hits']} |"
            if row["sharpe_proxy"] is not None and row["profit_factor"] is not None
            else f"| {row['variant']} | {fmt_pct(row['cagr'])} | {fmt_pct(row['total_return'])} | {fmt_pct(row['max_drawdown'])} | n/a | n/a | {fmt_pct(row['win_rate'])} | {fmt_pct(row['avg_return'])} | {row['fib_stop_hits']} | {row['winner_stop_hits']} | {row['loser_stop_hits']} |"
        )
    lines.extend(["", "## Delta Versus Baseline", "", "| Variant | CAGR Delta | Max DD Delta | Avg Return Delta | Net PnL Delta |", "| --- | ---: | ---: | ---: | ---: |"])
    for row in summary_rows:
        if row["variant"] == "baseline":
            continue
        lines.append(
            f"| {row['variant']} | {fmt_pct(row['cagr'] - baseline['cagr'])} | {fmt_pct(row['max_drawdown'] - baseline['max_drawdown'])} | "
            f"{fmt_pct(row['avg_return'] - baseline['avg_return'])} | {row['net_pnl_delta']:,.2f} |"
        )

    for name in FIB_STOP_LEVELS:
        helped = sorted(
            [row for row in detail_rows if row.get("diagnostic_status") == "ok" and row.get(f"{name}_hit")],
            key=lambda row: float(row.get(f"{name}_return_delta_pct") or 0.0),
            reverse=True,
        )[:8]
        lines.extend(["", f"## Top Trades Helped By `{name}`", "", "| Symbol | Entry | Baseline | Fib Cut | Delta | MAE | MFE |", "| --- | --- | ---: | ---: | ---: | ---: | ---: |"])
        for row in helped:
            lines.append(
                f"| {row['symbol']} | {row['entry_date']} | {fmt_pct(float(row['baseline_net_return_pct']))} | "
                f"{fmt_pct(float(row[f'{name}_return_pct']))} | {fmt_pct(float(row[f'{name}_return_delta_pct']))} | "
                f"{fmt_pct(float(row['mae_pct']))} | {fmt_pct(float(row['mfe_pct']))} |"
            )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "A useful Fib loser-cut rule should reduce drawdown and improve Sharpe/profit factor without cutting too many winners.",
            "If it cuts many winners or lowers CAGR materially, it should remain a diagnostic overlay rather than a strategy rule.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    load_dotenv(REPO_ROOT / ".env")
    angel_url = os.environ.get("ANGEL_DATABASE_URL")
    if not angel_url:
        raise RuntimeError("ANGEL_DATABASE_URL is required.")
    trades = load_trades(args.input_dir / "entry_1030_prevday_vwap_grid_trades.csv", args.variant)
    entries = load_entries(args.input_dir / "entry_1030_prevday_vwap_grid_entries.csv", args.variant)
    symbols = {str(symbol) for symbol in trades["symbol"].unique()}
    start_date = parse_date(min(trades["entry_date"]) - pd.Timedelta(days=90))
    end_date = parse_date(max(trades["exit_date"]))
    engine = create_engine(angel_url)
    daily = load_daily_bars(engine, args.pilot_schema, symbols, start_date, end_date)
    intraday = group_intraday(load_intraday_bars(engine, trades))
    detail_rows, variants = build_trade_variants(trades, entries, daily, intraday, args.swing_lookback, args.entry_time)

    baseline_summary = summarize_rows(variants["baseline"], args.initial_capital)
    summary_rows = []
    for variant, rows in variants.items():
        summary = summarize_rows(rows, args.initial_capital)
        stop_hits = [row for row in rows if row.get("fib_stop_hit")]
        base_by_id = {int(row["trade_id"]): row for row in variants["baseline"]}
        winner_hits = [row for row in stop_hits if float(base_by_id[int(row["trade_id"])]["net_pnl"]) > 0]
        loser_hits = [row for row in stop_hits if float(base_by_id[int(row["trade_id"])]["net_pnl"]) < 0]
        summary_rows.append(
            {
                "variant": variant,
                **summary,
                "fib_stop_hits": len(stop_hits),
                "winner_stop_hits": len(winner_hits),
                "loser_stop_hits": len(loser_hits),
                "net_pnl_delta": sum(float(row["net_pnl"]) for row in rows) - sum(float(row["net_pnl"]) for row in variants["baseline"]),
                "cagr_delta": summary["cagr"] - baseline_summary["cagr"],
            }
        )
    order = ["baseline", "swing_high_break", "fib_0_786", "fib_0_618", "fib_0_500"]
    summary_rows.sort(key=lambda row: order.index(row["variant"]))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / "fib_loser_cut_trade_diagnostic.csv", detail_rows)
    write_csv(args.output_dir / "fib_loser_cut_summary.csv", summary_rows)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "variant": args.variant,
        "parameters": {"swing_lookback": args.swing_lookback, "entry_time": args.entry_time.isoformat()},
        "summary": summary_rows,
        "artifacts": {
            "summary_csv": "fib_loser_cut_summary.csv",
            "trade_csv": "fib_loser_cut_trade_diagnostic.csv",
            "markdown": "FIB_LOSER_CUT_DIAGNOSTIC.md",
        },
    }
    (args.output_dir / "fib_loser_cut_diagnostic.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    (args.output_dir / "FIB_LOSER_CUT_DIAGNOSTIC.md").write_text(render_report(summary_rows, detail_rows), encoding="utf-8")
    print(json.dumps(summary_rows, indent=2, default=str))
    print(f"Wrote Fibonacci loser-cut diagnostic: {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
