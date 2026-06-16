"""Run research backtest variants for the NSE strategy sprints."""

from __future__ import annotations

import argparse
import json
import sys
from contextlib import contextmanager
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from mean_reversion_system.src.backtest import engine
from mean_reversion_system.src.backtest.reporter import generate_report
from mean_reversion_system.src.data.db_connector import get_engine
from mean_reversion_system.src.data.fetcher import fetch_active_universe
from mean_reversion_system.src.regime.detector import detect_regime
from mean_reversion_system.src.strategy.signals import add_all_indicators
from mean_reversion_system.src.universe.filter import filter_mean_reversion_universe


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _load_all_daily(symbols: list[str], warmup_start: date, end: date) -> dict[str, pd.DataFrame]:
    cache_dir = ROOT / "reports" / "backtest_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"daily_ohlcv_{warmup_start.isoformat()}_{end.isoformat()}.pkl"
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
            "start_ts": datetime.combine(warmup_start, time(9, 0)),
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


def _build_universe_by_date(daily: dict[str, pd.DataFrame], start: date, end: date) -> dict[date, set[str]]:
    all_dates = sorted({idx for frame in daily.values() for idx in frame.index if start <= idx <= end})
    universe_by_date: dict[date, set[str]] = {}
    for item_date in all_dates:
        rows = [row for symbol, frame in daily.items() if (row := _feature_row(symbol, frame, item_date))]
        if not rows:
            continue
        universe_by_date[item_date] = set(filter_mean_reversion_universe(pd.DataFrame(rows)))
    return universe_by_date


def _v2_minimal_signals(item: pd.DataFrame) -> pd.DataFrame:
    close = pd.to_numeric(item["close"], errors="coerce")
    rsi = pd.to_numeric(item["rsi"], errors="coerce")
    vol_ratio = pd.to_numeric(item["vol_ratio"], errors="coerce")
    item["long_signal"] = (close < pd.to_numeric(item["bb_lower"], errors="coerce")) & (rsi < 30) & (vol_ratio > 0.8)
    item["short_signal"] = False
    return item


def _v3_refined_signals(item: pd.DataFrame) -> pd.DataFrame:
    close = pd.to_numeric(item["close"], errors="coerce")
    open_ = pd.to_numeric(item["open"], errors="coerce")
    rsi = pd.to_numeric(item["rsi"], errors="coerce")
    volume = pd.to_numeric(item["volume"], errors="coerce")
    avg_volume = volume.rolling(20, min_periods=1).mean()
    bb_width = pd.to_numeric(item["bb_width"], errors="coerce")
    item["long_signal"] = (
        (close < pd.to_numeric(item["bb_lower"], errors="coerce"))
        & (rsi < 30)
        & (rsi > rsi.shift(1))
        & (close > open_)
        & (volume > 1.5 * avg_volume)
        & (bb_width.between(0.05, 0.15, inclusive="both"))
    )
    item["short_signal"] = False
    return item


def _v3_refined_no_candle_signals(item: pd.DataFrame) -> pd.DataFrame:
    close = pd.to_numeric(item["close"], errors="coerce")
    rsi = pd.to_numeric(item["rsi"], errors="coerce")
    volume = pd.to_numeric(item["volume"], errors="coerce")
    avg_volume = volume.rolling(20, min_periods=1).mean()
    bb_width = pd.to_numeric(item["bb_width"], errors="coerce")
    item["long_signal"] = (
        (close < pd.to_numeric(item["bb_lower"], errors="coerce"))
        & (rsi < 30)
        & (rsi > rsi.shift(1))
        & (volume > 1.5 * avg_volume)
        & (bb_width.between(0.05, 0.15, inclusive="both"))
    )
    item["short_signal"] = False
    return item


def _base_parts(item: pd.DataFrame) -> dict[str, pd.Series]:
    close = pd.to_numeric(item["close"], errors="coerce")
    open_ = pd.to_numeric(item["open"], errors="coerce")
    rsi = pd.to_numeric(item["rsi"], errors="coerce")
    volume = pd.to_numeric(item["volume"], errors="coerce")
    avg_volume = volume.rolling(20, min_periods=1).mean()
    bb_width = pd.to_numeric(item["bb_width"], errors="coerce")
    base = (close < pd.to_numeric(item["bb_lower"], errors="coerce")) & (rsi < 30) & (pd.to_numeric(item["vol_ratio"], errors="coerce") > 0.8)
    return {
        "base": base,
        "hook": rsi > rsi.shift(1),
        "candle": close > open_,
        "volume_spike": volume > 1.5 * avg_volume,
        "bb_width_band": bb_width.between(0.05, 0.15, inclusive="both"),
    }


def _v3b_volume_only_signals(item: pd.DataFrame) -> pd.DataFrame:
    parts = _base_parts(item)
    item["long_signal"] = parts["base"] & parts["volume_spike"]
    item["short_signal"] = False
    return item


def _v3b_bb_width_only_signals(item: pd.DataFrame) -> pd.DataFrame:
    parts = _base_parts(item)
    item["long_signal"] = parts["base"] & parts["bb_width_band"]
    item["short_signal"] = False
    return item


def _v3b_candle_only_signals(item: pd.DataFrame) -> pd.DataFrame:
    parts = _base_parts(item)
    item["long_signal"] = parts["base"] & parts["candle"]
    item["short_signal"] = False
    return item


def _v3b_no_hook_signals(item: pd.DataFrame) -> pd.DataFrame:
    parts = _base_parts(item)
    item["long_signal"] = parts["base"] & parts["candle"] & parts["volume_spike"] & parts["bb_width_band"]
    item["short_signal"] = False
    return item


@contextmanager
def _patched_engine(
    universe_by_date: dict[date, set[str]],
    atr_multiplier: float,
    signal_builder,
    partial_exit: bool = False,
    defer_exit_day: bool = False,
    partial_fraction: float = 0.5,
    partial_reward_r: float = 1.0,
):
    original_prepare = engine._prepare_symbol_frame
    original_params = engine._strategy_params

    def params() -> dict[str, Any]:
        payload = original_params()
        payload["atr"]["sl_atr_multiplier"] = atr_multiplier
        payload["partial_exit"] = {"enabled": partial_exit, "defer_exit_day": defer_exit_day, "fraction": partial_fraction, "reward_r": partial_reward_r}
        return payload

    def prepare(df: pd.DataFrame, index_df: pd.DataFrame | None = None) -> pd.DataFrame:
        item = add_all_indicators(df.copy())
        item["regime"] = detect_regime(item, index_df=index_df)
        item["earnings_blackout"] = False
        symbol = str(item["symbol"].dropna().iloc[0]) if "symbol" in item.columns and not item["symbol"].dropna().empty else ""
        item.index = pd.to_datetime(item.index).date
        item = signal_builder(item)
        allowed = pd.Series([symbol in universe_by_date.get(idx, set()) for idx in item.index], index=item.index)
        item["long_signal"] = item["long_signal"].fillna(False).astype(bool) & allowed
        item["short_signal"] = item["short_signal"].fillna(False).astype(bool) & allowed
        return item

    engine._prepare_symbol_frame = prepare
    engine._strategy_params = params
    try:
        yield
    finally:
        engine._prepare_symbol_frame = original_prepare
        engine._strategy_params = original_params


def _exit_breakdown(trades: list[Any]) -> dict[str, dict[str, float | int]]:
    rows: dict[str, dict[str, float | int]] = {}
    for trade in trades:
        item = rows.setdefault(trade.exit_reason, {"count": 0, "total_pnl": 0.0})
        item["count"] = int(item["count"]) + 1
        item["total_pnl"] = float(item["total_pnl"]) + float(trade.net_pnl)
    return rows


def _year_pnl(trades: list[Any]) -> dict[str, float]:
    rows: dict[str, float] = {}
    for trade in trades:
        year = str(trade.exit_date.year)
        rows[year] = rows.get(year, 0.0) + float(trade.net_pnl)
    return rows


def _direction_count(trades: list[Any], direction: str) -> int:
    return sum(1 for trade in trades if trade.direction == direction)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--variant",
        required=True,
        choices=[
            "v2_minimal",
            "v3_signals",
            "v3_signals_no_candle",
            "v3b_volume_only",
            "v3b_bb_width_only",
            "v3b_candle_only",
            "v3b_no_hook",
            "v4_stop",
            "v4b_stop_1_75",
            "v4b_stop_2_0",
            "v4b_stop_2_25",
            "v5_partial",
            "v5_partial_defer",
            "v5b_partial_25",
            "v5b_partial_33",
            "v5c_partial_1_5r",
            "v5c_partial_2r",
        ],
    )
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    args = parser.parse_args()
    start = _parse_date(args.start)
    end = _parse_date(args.end)
    warmup_start = date(max(2020, start.year - 1), 1, 1)

    out_dir = ROOT / "reports" / "backtests" / args.variant
    out_dir.mkdir(parents=True, exist_ok=True)
    symbols = fetch_active_universe()
    raw_daily = _load_all_daily(symbols, warmup_start, end)
    daily: dict[str, pd.DataFrame] = {}
    for symbol, frame in raw_daily.items():
        if frame.empty:
            continue
        item = add_all_indicators(frame.copy())
        item["symbol"] = symbol
        item.index = pd.to_datetime(item.index).date
        daily[symbol] = item

    universe_by_date = _build_universe_by_date(daily, start, end)
    variant_config = {
        "v2_minimal": {"atr_multiplier": 1.5, "signal_builder": _v2_minimal_signals},
        "v3_signals": {"atr_multiplier": 1.5, "signal_builder": _v3_refined_signals},
        "v3_signals_no_candle": {"atr_multiplier": 1.5, "signal_builder": _v3_refined_no_candle_signals},
        "v3b_volume_only": {"atr_multiplier": 1.5, "signal_builder": _v3b_volume_only_signals},
        "v3b_bb_width_only": {"atr_multiplier": 1.5, "signal_builder": _v3b_bb_width_only_signals},
        "v3b_candle_only": {"atr_multiplier": 1.5, "signal_builder": _v3b_candle_only_signals},
        "v3b_no_hook": {"atr_multiplier": 1.5, "signal_builder": _v3b_no_hook_signals},
        "v4_stop": {"atr_multiplier": 2.5, "signal_builder": _v3b_bb_width_only_signals},
        "v4b_stop_1_75": {"atr_multiplier": 1.75, "signal_builder": _v3b_bb_width_only_signals},
        "v4b_stop_2_0": {"atr_multiplier": 2.0, "signal_builder": _v3b_bb_width_only_signals},
        "v4b_stop_2_25": {"atr_multiplier": 2.25, "signal_builder": _v3b_bb_width_only_signals},
        "v5_partial": {"atr_multiplier": 2.25, "signal_builder": _v3b_bb_width_only_signals, "partial_exit": True},
        "v5_partial_defer": {"atr_multiplier": 2.25, "signal_builder": _v3b_bb_width_only_signals, "partial_exit": True, "defer_exit_day": True},
        "v5b_partial_25": {"atr_multiplier": 2.25, "signal_builder": _v3b_bb_width_only_signals, "partial_exit": True, "partial_fraction": 0.25},
        "v5b_partial_33": {"atr_multiplier": 2.25, "signal_builder": _v3b_bb_width_only_signals, "partial_exit": True, "partial_fraction": 0.33},
        "v5c_partial_1_5r": {
            "atr_multiplier": 2.25,
            "signal_builder": _v3b_bb_width_only_signals,
            "partial_exit": True,
            "partial_fraction": 0.5,
            "partial_reward_r": 1.5,
        },
        "v5c_partial_2r": {
            "atr_multiplier": 2.25,
            "signal_builder": _v3b_bb_width_only_signals,
            "partial_exit": True,
            "partial_fraction": 0.5,
            "partial_reward_r": 2.0,
        },
    }[args.variant]
    with _patched_engine(
        universe_by_date,
        atr_multiplier=variant_config["atr_multiplier"],
        signal_builder=variant_config["signal_builder"],
        partial_exit=bool(variant_config.get("partial_exit", False)),
        defer_exit_day=bool(variant_config.get("defer_exit_day", False)),
        partial_fraction=float(variant_config.get("partial_fraction", 0.5)),
        partial_reward_r=float(variant_config.get("partial_reward_r", 1.0)),
    ):
        result = engine.run_backtest(symbols, start, end, daily_data=daily)

    metrics = generate_report(result)
    metrics.update(
        {
            "variant": args.variant,
            "long_trades": _direction_count(result.trades, "long"),
            "short_trades": _direction_count(result.trades, "short"),
            "per_year_pnl": _year_pnl(result.trades),
            "exit_breakdown": _exit_breakdown(result.trades),
        }
    )
    pd.DataFrame([trade.__dict__ for trade in result.trades]).to_csv(out_dir / "trades.csv", index=False)
    result.equity_curve.to_csv(out_dir / "equity.csv", index=False)
    (out_dir / "summary.json").write_text(json.dumps(metrics, indent=2, default=str), encoding="utf-8")
    print(json.dumps(metrics, indent=2, default=str))


if __name__ == "__main__":
    main()
