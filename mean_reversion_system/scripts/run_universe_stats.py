"""Measure daily symbol counts for mean-reversion universe filters."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from mean_reversion_system.src.data.db_connector import get_engine
from mean_reversion_system.src.data.fetcher import fetch_active_universe
from mean_reversion_system.src.strategy.signals import add_all_indicators
from mean_reversion_system.src.universe.filter import filter_mean_reversion_universe


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _load_all_daily(symbols: list[str], start: date, end: date) -> dict[str, pd.DataFrame]:
    cache_dir = ROOT / "reports" / "universe_stats"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"daily_ohlcv_{start.isoformat()}_{end.isoformat()}.pkl"
    if cache_path.exists():
        return pd.read_pickle(cache_path)

    query = """
        WITH base AS (
            SELECT
                symbol,
                datetime::date AS trade_date,
                datetime,
                open::double precision AS open,
                high::double precision AS high,
                low::double precision AS low,
                close::double precision AS close,
                volume::bigint AS volume
            FROM ohlcv_15min
            WHERE symbol = ANY(%(symbols)s)
              AND datetime >= %(start_ts)s
              AND datetime <= %(end_ts)s
              AND datetime::time >= time '09:15'
              AND datetime::time <= time '15:30'
        )
        SELECT
            symbol,
            trade_date,
            (array_agg(open ORDER BY datetime))[1] AS open,
            max(high) FILTER (WHERE datetime::time < time '15:15') AS high,
            min(low) FILTER (WHERE datetime::time < time '15:15') AS low,
            (array_agg(close ORDER BY datetime DESC))[1] AS close,
            sum(volume) AS volume
        FROM base
        GROUP BY symbol, trade_date
        ORDER BY symbol, trade_date
    """
    rows = pd.read_sql(
        query,
        get_engine(),
        params={
            "symbols": symbols,
            "start_ts": datetime.combine(start, time(9, 0)),
            "end_ts": datetime.combine(end, time(15, 30)),
        },
    )
    rows["trade_date"] = pd.to_datetime(rows["trade_date"]).dt.date
    daily: dict[str, pd.DataFrame] = {}
    for symbol, frame in rows.groupby("symbol", sort=False):
        daily[str(symbol)] = frame.set_index("trade_date")[["open", "high", "low", "close", "volume"]].sort_index()
    pd.to_pickle(daily, cache_path)
    return daily


def _feature_row(symbol: str, frame: pd.DataFrame, item_date: date) -> dict[str, Any] | None:
    if item_date not in frame.index:
        return None
    history = frame.loc[:item_date]
    if len(history) < 200:
        return None
    row = history.iloc[-1]
    volume_20d = pd.to_numeric(history["volume"], errors="coerce").tail(20)
    close_20d = pd.to_numeric(history["close"], errors="coerce").tail(20)
    return {
        "symbol": symbol,
        "avg_daily_turnover_20d": float((close_20d * volume_20d).mean()),
        "close": float(row["close"]),
        "sma_200": float(pd.to_numeric(history["close"], errors="coerce").tail(200).mean()),
        "adx_14": float(row.get("adx", float("nan"))),
        "atr_pct_20d": float(row.get("atr_pct", float("nan")) * 100),
    }


def _condition_rates(features: pd.DataFrame) -> dict[str, float]:
    return {
        "turnover_gt_2cr": float((features["avg_daily_turnover_20d"] > 20_000_000).mean()),
        "close_gt_sma200": float((features["close"] > features["sma_200"]).mean()),
        "adx_lt_25": float((features["adx_14"] < 25.0).mean()),
        "atr_pct_1_5_to_4_5": float(features["atr_pct_20d"].between(1.5, 4.5, inclusive="both").mean()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    args = parser.parse_args()
    start = _parse_date(args.start)
    end = _parse_date(args.end)
    warmup_start = date(max(2020, start.year - 1), 1, 1)

    symbols = fetch_active_universe()
    daily_raw = _load_all_daily(symbols, warmup_start, end)
    daily = {symbol: add_all_indicators(frame.copy()) for symbol, frame in daily_raw.items() if not frame.empty}
    for frame in daily.values():
        frame.index = pd.to_datetime(frame.index).date

    all_dates = sorted({idx for frame in daily.values() for idx in frame.index if start <= idx <= end})
    rows: list[dict[str, Any]] = []
    condition_rows: list[dict[str, float]] = []
    skipped_no_feature_days = 0
    for item_date in all_dates:
        feature_rows = [row for symbol, frame in daily.items() if (row := _feature_row(symbol, frame, item_date))]
        if not feature_rows:
            skipped_no_feature_days += 1
            continue
        features = pd.DataFrame(feature_rows)
        symbols_today = filter_mean_reversion_universe(features)
        rows.append({"date": item_date.isoformat(), "symbol_count": len(symbols_today)})
        condition_rows.append(_condition_rates(features))

    counts = pd.DataFrame(rows)
    condition_frame = pd.DataFrame(condition_rows)
    stats = {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "trading_days": int(len(counts)),
        "skipped_no_feature_days": int(skipped_no_feature_days),
        "avg_symbols_per_day": float(counts["symbol_count"].mean()) if not counts.empty else 0.0,
        "median_symbols_per_day": float(counts["symbol_count"].median()) if not counts.empty else 0.0,
        "min_symbols_per_day": int(counts["symbol_count"].min()) if not counts.empty else 0,
        "max_symbols_per_day": int(counts["symbol_count"].max()) if not counts.empty else 0,
        "pct_days_above_20": float((counts["symbol_count"] > 20).mean()) if not counts.empty else 0.0,
        "pct_days_zero": float((counts["symbol_count"] == 0).mean()) if not counts.empty else 0.0,
        "condition_pass_rates": condition_frame.mean(numeric_only=True).to_dict() if not condition_frame.empty else {},
    }
    out_dir = ROOT / "reports" / "universe_stats"
    counts.to_csv(out_dir / "mean_reversion_minimal_counts.csv", index=False)
    (out_dir / "mean_reversion_minimal_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
