#!/usr/bin/env python3
"""MAE/MFE diagnostic and stop-loss grid for the current leading candidate.

Candidate input defaults to:
  Rolling 10 + 1M/3M 40/60 + 10:30 entry
  + skip if entry > previous-day VWAP + 2.5%.

Stop-loss simulation uses 15-minute lows from the entry bar onward. If a stop is
hit, exit is recorded at the stop price; otherwise the original planned exit is
kept. Research-only: no database writes or production strategy changes.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import statistics
from datetime import date, datetime, time, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = REPO_ROOT / "results" / "entry_1030_prevday_vwap_grid"
OUTPUT_DIR = REPO_ROOT / "results" / "mae_mfe_stoploss_grid"
VARIANT = "rolling_10_1m3m_entry_1030_skip_prevday_vwap_25bp"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run MAE/MFE diagnostic and stop-loss grid.")
    parser.add_argument("--input-dir", type=Path, default=INPUT_DIR)
    parser.add_argument("--variant", default=VARIANT)
    parser.add_argument("--entry-time", type=time.fromisoformat, default=time(10, 30))
    parser.add_argument("--stop-levels", default="0.05,0.075,0.10,0.125,0.15")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    return parser.parse_args()


def parse_levels(value: str) -> list[float]:
    return [float(item.strip()) for item in value.split(",") if item.strip()]


def load_trades(path: Path, variant: str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame = frame[frame["strategy"] == variant].copy()
    for column in ["entry_date", "exit_date"]:
        frame[column] = pd.to_datetime(frame[column]).dt.date
    for column in ["entry_price", "exit_price", "entry_value", "quantity", "net_pnl", "net_return_pct", "charges"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.sort_values(["entry_date", "trade_id"]).reset_index(drop=True)


def sql_literal(value: object) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def load_intraday_for_trades(engine, trades: pd.DataFrame) -> pd.DataFrame:
    windows = (
        trades[["symbol", "entry_date", "exit_date"]]
        .drop_duplicates()
        .sort_values(["symbol", "entry_date", "exit_date"])
        .to_dict("records")
    )
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
    for column in ["open", "high", "low", "close", "volume"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def group_bars_by_symbol(bars: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {str(symbol): group.reset_index(drop=True) for symbol, group in bars.groupby("symbol", sort=False)}


def slice_trade_bars(symbol_bars: dict[str, pd.DataFrame], symbol: str, entry_date: date, exit_date: date, entry_time: time) -> pd.DataFrame:
    rows = symbol_bars.get(symbol)
    if rows is None or rows.empty:
        return pd.DataFrame()
    rows = rows[(rows["date"] >= entry_date) & (rows["date"] <= exit_date)]
    return rows[(rows["date"] > entry_date) | (rows["time"] >= entry_time)]


def annotate_mae_mfe(trades: pd.DataFrame, symbol_bars: dict[str, pd.DataFrame], entry_time: time) -> pd.DataFrame:
    out = []
    for row in trades.itertuples(index=False):
        trade_bars = slice_trade_bars(symbol_bars, str(row.symbol), row.entry_date, row.exit_date, entry_time)
        min_low = float(trade_bars["low"].min()) if not trade_bars.empty else None
        max_high = float(trade_bars["high"].max()) if not trade_bars.empty else None
        mae = min_low / float(row.entry_price) - 1.0 if min_low else None
        mfe = max_high / float(row.entry_price) - 1.0 if max_high else None
        out.append({**row._asdict(), "min_low_during_trade": min_low, "max_high_during_trade": max_high, "mae_pct": mae, "mfe_pct": mfe})
    return pd.DataFrame(out)


def sell_charges(exit_value: float) -> float:
    brokerage = 0.0
    stt = exit_value * 0.001
    exchange = exit_value * 0.0000325
    sebi = exit_value * 0.000001
    gst = (brokerage + exchange) * 0.18
    return brokerage + stt + exchange + sebi + gst


def simulate_stop(trades: pd.DataFrame, symbol_bars: dict[str, pd.DataFrame], stop: float, entry_time: time) -> list[dict[str, object]]:
    rows = []
    for row in trades.itertuples(index=False):
        entry_price = float(row.entry_price)
        stop_price = entry_price * (1.0 - stop)
        trade_bars = slice_trade_bars(symbol_bars, str(row.symbol), row.entry_date, row.exit_date, entry_time)
        hit = trade_bars[trade_bars["low"] <= stop_price].head(1)
        if not hit.empty:
            hit_row = hit.iloc[0]
            exit_date = hit_row["date"]
            exit_price = stop_price
            exit_reason = f"stop_{int(stop * 1000)}bp"
        else:
            exit_date = row.exit_date
            exit_price = float(row.exit_price)
            exit_reason = row.exit_reason
        exit_value = float(row.quantity) * exit_price
        gross_pnl = exit_value - float(row.entry_value)
        charges = sell_charges(exit_value) + (float(row.charges) - sell_charges(float(row.exit_value)))
        net_pnl = gross_pnl - charges
        rows.append(
            {
                **row._asdict(),
                "stop_level": stop,
                "exit_date": exit_date,
                "exit_price": exit_price,
                "exit_value": exit_value,
                "gross_pnl": gross_pnl,
                "charges": charges,
                "net_pnl": net_pnl,
                "net_return_pct": net_pnl / float(row.entry_value) if row.entry_value else None,
                "exit_reason": exit_reason,
                "stop_hit": not hit.empty,
            }
        )
    return rows


def max_drawdown(values: list[float]) -> float:
    peak = values[0] if values else 0.0
    dd = 0.0
    for value in values:
        peak = max(peak, value)
        if peak:
            dd = min(dd, value / peak - 1.0)
    return dd


def summarize_pnl(rows: list[dict[str, object]], initial_capital: float, years: float) -> dict[str, object]:
    ordered = sorted(rows, key=lambda r: (str(r["exit_date"]), int(r["trade_id"])))
    equity = initial_capital
    curve = [equity]
    returns = []
    for row in ordered:
        prev = equity
        equity += float(row["net_pnl"])
        curve.append(equity)
        returns.append(equity / prev - 1.0 if prev else 0.0)
    winners = [r for r in rows if float(r["net_pnl"]) > 0]
    gross_profit = sum(float(r["net_pnl"]) for r in winners)
    gross_loss = abs(sum(float(r["net_pnl"]) for r in rows if float(r["net_pnl"]) < 0))
    stdev = statistics.stdev(returns) if len(returns) > 1 else 0.0
    return {
        "ending_equity": equity,
        "total_return": equity / initial_capital - 1.0,
        "cagr": (equity / initial_capital) ** (1 / years) - 1.0 if equity > 0 and years else None,
        "max_drawdown": max_drawdown(curve),
        "sharpe_proxy": statistics.mean(returns) / stdev * math.sqrt(252) if stdev else None,
        "profit_factor": gross_profit / gross_loss if gross_loss else None,
        "win_rate": len(winners) / len(rows) if rows else None,
        "trade_count": len(rows),
        "stop_hits": sum(1 for r in rows if r.get("stop_hit")),
    }


def bucket_diagnostic(annotated: pd.DataFrame, levels: list[float]) -> list[dict[str, object]]:
    rows = []
    winners = annotated[annotated["net_pnl"] > 0]
    losers = annotated[annotated["net_pnl"] < 0]
    for level in levels:
        rows.append(
            {
                "stop_level": level,
                "losers_crossed": int((losers["mae_pct"] <= -level).sum()),
                "loser_count": int(len(losers)),
                "losers_crossed_pct": float((losers["mae_pct"] <= -level).mean()) if len(losers) else None,
                "winners_crossed": int((winners["mae_pct"] <= -level).sum()),
                "winner_count": int(len(winners)),
                "winners_crossed_pct": float((winners["mae_pct"] <= -level).mean()) if len(winners) else None,
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys = sorted({k for row in rows for k in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def fmt_pct(value: object) -> str:
    return "n/a" if value is None or pd.isna(value) else f"{float(value) * 100:.2f}%"


def render_report(payload: dict[str, object]) -> str:
    lines = [
        "# MAE/MFE Diagnostic And Stop-Loss Grid",
        "",
        "Research-only diagnostic. No production logic or database rows were modified.",
        "",
        "## MAE Stop-Crossing Diagnostic",
        "",
        "| Stop | Losers Crossed | Losers Crossed % | Winners Crossed | Winners Crossed % |",
        "| ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["mae_diagnostic"]:
        lines.append(f"| {fmt_pct(row['stop_level'])} | {row['losers_crossed']} | {fmt_pct(row['losers_crossed_pct'])} | {row['winners_crossed']} | {fmt_pct(row['winners_crossed_pct'])} |")
    lines.extend(["", "## Stop-Loss Grid", "", "| Stop | CAGR | Max DD | Sharpe Proxy | PF | Win Rate | Stop Hits |", "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |"])
    for row in payload["stop_grid"]:
        lines.append(f"| {fmt_pct(row['stop_level'])} | {fmt_pct(row['cagr'])} | {fmt_pct(row['max_drawdown'])} | {row['sharpe_proxy']:.2f} | {row['profit_factor']:.2f} | {fmt_pct(row['win_rate'])} | {row['stop_hits']} |")
    lines.extend(["", "## Verdict", "", payload["verdict"]])
    return "\n".join(lines) + "\n"


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    args = parse_args()
    angel_url = os.environ.get("ANGEL_DATABASE_URL")
    if not angel_url:
        raise RuntimeError("ANGEL_DATABASE_URL is required.")
    levels = parse_levels(args.stop_levels)
    trades = load_trades(args.input_dir / "entry_1030_prevday_vwap_grid_trades.csv", args.variant)
    engine = create_engine(angel_url, future=True, pool_pre_ping=True)
    bars = load_intraday_for_trades(engine, trades)
    symbol_bars = group_bars_by_symbol(bars)
    annotated = annotate_mae_mfe(trades, symbol_bars, args.entry_time)
    years = (max(trades["exit_date"]) - min(trades["entry_date"])).days / 365.25
    mae_rows = bucket_diagnostic(annotated, levels)
    baseline_rows = annotated.to_dict("records")
    grid = [{"stop_level": None, **summarize_pnl(baseline_rows, 1_000_000.0, years)}]
    simulated_rows = []
    for level in levels:
        rows = simulate_stop(annotated, symbol_bars, level, args.entry_time)
        simulated_rows.extend(rows)
        grid.append({"stop_level": level, **summarize_pnl(rows, 1_000_000.0, years)})
    candidates = [r for r in grid if r["stop_level"] is not None]
    best = max(candidates, key=lambda r: (float(r["sharpe_proxy"] or -999), float(r["cagr"] or -999)))
    base = grid[0]
    verdict = f"Best stop candidate is {fmt_pct(best['stop_level'])}: CAGR {fmt_pct(best['cagr'])}, max DD {fmt_pct(best['max_drawdown'])}, Sharpe proxy {best['sharpe_proxy']:.2f}, versus no-stop CAGR {fmt_pct(base['cagr'])} and max DD {fmt_pct(base['max_drawdown'])}."
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "parameters": {"variant": args.variant, "entry_time": args.entry_time.isoformat(), "stop_levels": levels},
        "mae_diagnostic": mae_rows,
        "stop_grid": grid,
        "constraints": {"database_modified": False, "production_scoring_changed": False, "production_recommendations_changed": False, "strategy_rules_changed": False},
        "verdict": verdict,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "mae_mfe_stoploss_grid.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    (args.output_dir / "MAE_MFE_STOPLOSS_GRID.md").write_text(render_report(payload), encoding="utf-8")
    annotated.to_csv(args.output_dir / "mae_mfe_trades.csv", index=False)
    write_csv(args.output_dir / "mae_stop_crossing_diagnostic.csv", mae_rows)
    write_csv(args.output_dir / "stoploss_grid_summary.csv", grid)
    write_csv(args.output_dir / "stoploss_simulated_trades.csv", simulated_rows)
    print(json.dumps(payload, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
