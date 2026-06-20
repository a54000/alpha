#!/usr/bin/env python3
"""Research-only backtest for stocks from Improving RRG sectors.

For each weekly signal date in the last year:
  1. Compute sector RRG state as of that date.
  2. Select all stocks whose sector is in the Improving quadrant.
  3. Enter next trading session at the 10:30 candle open.
  4. Exit after 20 trading sessions at daily close.

This is a trade-level study, not a production strategy change.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import statistics
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.api.sector_rotation_service import SectorRotationService  # noqa: E402
from app.api.trade_analysis_service import next_trading_day_after, nth_trading_day_after, weekly_signal_dates  # noqa: E402

OUT_DIR = REPO_ROOT / "results" / "improving_sector_20d_backtest"
DOC_PATH = REPO_ROOT / "docs" / "IMPROVING_SECTOR_20D_BACKTEST.md"


def derive_angel_url(research_database_url: str | None, database_name: str = "angel_data") -> str | None:
    if not research_database_url:
        return None
    parts = urlsplit(research_database_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database_name}", parts.query, parts.fragment))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest stocks from Improving RRG sectors for a 20-day hold.")
    parser.add_argument("--end-date", type=date.fromisoformat, default=None)
    parser.add_argument("--start-date", type=date.fromisoformat, default=None)
    parser.add_argument("--lookback-days", type=int, default=365)
    parser.add_argument("--holding-period", type=int, default=20)
    parser.add_argument("--entry-time", type=time.fromisoformat, default=time(10, 30))
    parser.add_argument("--pilot-schema", default="pilot_phase2a")
    parser.add_argument("--output-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--doc-path", type=Path, default=DOC_PATH)
    return parser.parse_args()


def make_engine():
    load_dotenv(REPO_ROOT / ".env")
    url = os.environ.get("ANGEL_DATABASE_URL") or derive_angel_url(os.environ.get("DATABASE_URL"))
    if not url:
        raise RuntimeError("ANGEL_DATABASE_URL is required.")
    return create_engine(url, future=True, pool_pre_ping=True, pool_size=1, max_overflow=0)


def latest_date(engine, schema: str) -> date:
    with engine.connect() as conn:
        value = conn.execute(text(f"SELECT MAX(date) FROM {schema}.features_daily")).scalar_one()
    if value is None:
        raise RuntimeError("No features_daily rows found.")
    return value


def load_trading_dates(engine, schema: str, start_date: date, end_date: date) -> list[date]:
    query = text(f"SELECT DISTINCT date FROM {schema}.daily_bars_clean WHERE date BETWEEN :start AND :end ORDER BY date")
    frame = pd.read_sql_query(query, engine, params={"start": start_date, "end": end_date})
    return [item.date() if hasattr(item, "date") else item for item in pd.to_datetime(frame["date"]).dt.date]


def load_features(engine, schema: str, start_date: date, end_date: date) -> pd.DataFrame:
    query = text(
        f"""
        SELECT symbol, date, sector, adx_14, prior_20d_return, ema200_extension
        FROM {schema}.features_daily
        WHERE date BETWEEN :start AND :end
          AND sector IS NOT NULL
        ORDER BY date, sector, symbol
        """
    )
    frame = pd.read_sql_query(query, engine, params={"start": start_date, "end": end_date})
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    return frame


def load_daily_prices(engine, schema: str, start_date: date, end_date: date) -> dict[str, dict[date, dict[str, float]]]:
    query = text(
        f"""
        SELECT symbol, date, open, close
        FROM {schema}.daily_bars_clean
        WHERE date BETWEEN :start AND :end
        ORDER BY symbol, date
        """
    )
    frame = pd.read_sql_query(query, engine, params={"start": start_date, "end": end_date})
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    out: dict[str, dict[date, dict[str, float]]] = {}
    for row in frame.itertuples(index=False):
        out.setdefault(str(row.symbol), {})[row.date] = {"open": float(row.open), "close": float(row.close)}
    return out


def load_entry_prices(engine, symbols: set[str], start_date: date, end_date: date, entry_time: time) -> dict[tuple[str, date], float]:
    if not symbols:
        return {}
    query = text(
        """
        SELECT symbol, datetime::date AS date, open
        FROM ohlcv_15min
        WHERE symbol = ANY(:symbols)
          AND datetime::date BETWEEN :start AND :end
          AND datetime::time = :entry_time
        """
    )
    frame = pd.read_sql_query(query, engine, params={"symbols": list(symbols), "start": start_date, "end": end_date, "entry_time": entry_time})
    if frame.empty:
        return {}
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    return {(str(row.symbol), row.date): float(row.open) for row in frame.itertuples(index=False)}


def symbol_dates(prices: dict[str, dict[date, dict[str, float]]], symbol: str) -> list[date]:
    return sorted(prices.get(symbol, {}))


def zerodha_cost_pct() -> float:
    # Approximate delivery round-trip friction as percentage of entry value.
    return 0.001 + (2 * 0.0000297) + (2 * 0.000001) + 0.00015 + 0.18 * (2 * (0.0000297 + 0.000001))


def max_drawdown_from_returns(returns: list[float]) -> float:
    equity = 1.0
    peak = 1.0
    drawdown = 0.0
    for ret in returns:
        equity *= 1.0 + ret
        peak = max(peak, equity)
        drawdown = min(drawdown, equity / peak - 1.0)
    return drawdown


def summarize(trades: list[dict[str, object]]) -> dict[str, object]:
    returns = [float(row["net_return_pct"]) for row in trades]
    winners = [value for value in returns if value > 0]
    losers = [value for value in returns if value <= 0]
    stdev = statistics.stdev(returns) if len(returns) > 1 else 0.0
    return {
        "trade_count": len(trades),
        "win_rate": len(winners) / len(returns) if returns else 0.0,
        "avg_return": statistics.mean(returns) if returns else 0.0,
        "median_return": statistics.median(returns) if returns else 0.0,
        "avg_winner": statistics.mean(winners) if winners else 0.0,
        "avg_loser": statistics.mean(losers) if losers else 0.0,
        "profit_factor": sum(winners) / abs(sum(losers)) if losers and sum(losers) else None,
        "return_stdev": stdev,
        "trade_sharpe": statistics.mean(returns) / stdev * math.sqrt(252 / 20) if stdev else 0.0,
        "max_drawdown_equal_sequence": max_drawdown_from_returns(returns),
    }


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def pct(value: object) -> str:
    if value is None:
        return "n/a"
    return f"{float(value) * 100:.2f}%"


def render_doc(payload: dict[str, object]) -> str:
    summary = payload["summary"]
    lines = [
        "# Improving Sector 20-Day Hold Backtest",
        "",
        "Research-only study. No strategy, scoring, recommendation, or database state was changed.",
        "",
        "## Setup",
        "",
        f"- Test window: `{payload['start_date']}` to `{payload['end_date']}`",
        "- Sector filter: sectors in the RRG `Improving` quadrant on weekly signal date.",
        "- Stock universe: all mapped stocks in those Improving sectors.",
        "- Entry: next trading session 10:30 candle open.",
        f"- Exit: planned `{payload['holding_period']}` trading-day hold, exit at daily close.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Trades | {summary['trade_count']} |",
        f"| Win rate | {pct(summary['win_rate'])} |",
        f"| Average return | {pct(summary['avg_return'])} |",
        f"| Median return | {pct(summary['median_return'])} |",
        f"| Average winner | {pct(summary['avg_winner'])} |",
        f"| Average loser | {pct(summary['avg_loser'])} |",
        f"| Profit factor | {summary['profit_factor']:.2f} |" if summary["profit_factor"] is not None else "| Profit factor | n/a |",
        f"| Trade-level Sharpe | {summary['trade_sharpe']:.2f} |",
        "",
        "## Current Improving-Sector Stocks",
        "",
    ]
    latest = payload.get("latest_improving_stock_list", [])
    if latest:
        lines.extend(["| Sector | Stocks |", "| --- | --- |"])
        for row in latest:
            lines.append(f"| {row['sector']} | {', '.join(row['symbols'])} |")
    else:
        lines.append("No current Improving sectors were found.")
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            "- `results/improving_sector_20d_backtest/trades.csv`",
            "- `results/improving_sector_20d_backtest/weekly_sector_states.csv`",
            "- `results/improving_sector_20d_backtest/latest_improving_sector_stocks.csv`",
            "- `results/improving_sector_20d_backtest/summary.json`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    engine = make_engine()
    end_date = args.end_date or latest_date(engine, args.pilot_schema)
    start_date = args.start_date or (end_date - timedelta(days=args.lookback_days))
    load_start = start_date - timedelta(days=160)
    load_end = end_date + timedelta(days=45)
    trading_dates = load_trading_dates(engine, args.pilot_schema, load_start, load_end)
    test_signal_dates = [day for day in weekly_signal_dates([d for d in trading_dates if start_date <= d <= end_date]) if day <= end_date]
    features = load_features(engine, args.pilot_schema, load_start, end_date)
    prices = load_daily_prices(engine, args.pilot_schema, load_start, load_end)
    symbols = set(map(str, features["symbol"].unique()))
    entry_prices = load_entry_prices(engine, symbols, start_date, load_end, args.entry_time)
    rotation_service = SectorRotationService()

    feature_by_date = {day: group.copy() for day, group in features.groupby("date")}
    weekly_states: list[dict[str, object]] = []
    candidates: list[dict[str, object]] = []
    for signal_date in test_signal_dates:
        insight = rotation_service.insights(as_of=signal_date)
        improving = sorted([row["sector"] for row in insight.get("sectors", []) if row.get("quadrant") == "improving"])
        weekly_states.append({"signal_date": signal_date.isoformat(), "improving_sectors": ", ".join(improving), "improving_sector_count": len(improving)})
        if not improving:
            continue
        day_features = feature_by_date.get(signal_date)
        if day_features is None:
            continue
        selected = day_features[day_features["sector"].isin(improving)].copy()
        for row in selected.itertuples(index=False):
            candidates.append(
                {
                    "signal_date": signal_date,
                    "symbol": str(row.symbol),
                    "sector": str(row.sector),
                    "adx_14": row.adx_14,
                    "prior_20d_return": row.prior_20d_return,
                    "ema200_extension": row.ema200_extension,
                }
            )

    cost_pct = zerodha_cost_pct()
    trades: list[dict[str, object]] = []
    for idx, candidate in enumerate(candidates, start=1):
        signal_date = candidate["signal_date"]
        entry_date = next_trading_day_after(trading_dates, signal_date)
        if entry_date is None:
            continue
        symbol = str(candidate["symbol"])
        exit_date = nth_trading_day_after(symbol_dates(prices, symbol), entry_date, args.holding_period)
        if exit_date is None:
            continue
        entry_price = entry_prices.get((symbol, entry_date))
        exit_price = prices.get(symbol, {}).get(exit_date, {}).get("close")
        if entry_price is None or exit_price is None or entry_price <= 0:
            continue
        gross_return = exit_price / entry_price - 1.0
        net_return = gross_return - cost_pct
        trades.append(
            {
                "trade_id": idx,
                "signal_date": signal_date.isoformat(),
                "entry_date": entry_date.isoformat(),
                "exit_date": exit_date.isoformat(),
                "symbol": symbol,
                "sector": candidate["sector"],
                "entry_price": entry_price,
                "exit_price": exit_price,
                "gross_return_pct": gross_return,
                "estimated_cost_pct": cost_pct,
                "net_return_pct": net_return,
                "adx_14": candidate["adx_14"],
                "prior_20d_return": candidate["prior_20d_return"],
                "ema200_extension": candidate["ema200_extension"],
            }
        )

    latest_insight = rotation_service.insights(as_of=end_date)
    latest_improving = sorted([row["sector"] for row in latest_insight.get("sectors", []) if row.get("quadrant") == "improving"])
    latest_features = feature_by_date.get(end_date, pd.DataFrame())
    latest_stock_rows: list[dict[str, object]] = []
    latest_stock_csv: list[dict[str, object]] = []
    if not latest_features.empty:
        for sector in latest_improving:
            symbols_in_sector = sorted(map(str, latest_features[latest_features["sector"] == sector]["symbol"].unique()))
            latest_stock_rows.append({"sector": sector, "symbols": symbols_in_sector})
            latest_stock_csv.extend({"as_of": end_date.isoformat(), "sector": sector, "symbol": symbol} for symbol in symbols_in_sector)

    summary = summarize(trades)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "holding_period": args.holding_period,
        "signal_weeks": len(test_signal_dates),
        "candidate_count": len(candidates),
        "summary": summary,
        "latest_improving_sectors": latest_improving,
        "latest_improving_stock_list": latest_stock_rows,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / "trades.csv", trades)
    write_csv(args.output_dir / "weekly_sector_states.csv", weekly_states)
    write_csv(args.output_dir / "latest_improving_sector_stocks.csv", latest_stock_csv)
    (args.output_dir / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    args.doc_path.parent.mkdir(parents=True, exist_ok=True)
    args.doc_path.write_text(render_doc(payload), encoding="utf-8")
    print(json.dumps({"status": "success", "summary": summary, "doc": str(args.doc_path)}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
