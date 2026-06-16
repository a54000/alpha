"""Run Strategy 2.2 minimum viable filter research variants."""

from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Callable

import pandas as pd

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from mean_reversion_system.src.backtest import engine
from mean_reversion_system.src.backtest.reporter import generate_report
from mean_reversion_system.src.data.db_connector import get_engine
from mean_reversion_system.src.data.fetcher import fetch_15min, fetch_active_universe
from mean_reversion_system.src.data.intraday_loader import find_confirmation_entry
from mean_reversion_system.src.regime.detector import detect_regime
from mean_reversion_system.src.strategy.signals import add_all_indicators
from mean_reversion_system.src.universe.filter import filter_mean_reversion_universe


START_DATE = date(2021, 9, 1)
END_DATE = date(2026, 6, 1)
WARMUP_START = date(2021, 6, 14)
REPORT_DIR = ROOT / "reports" / "strategy_2_2_minimal_filter"


def _load_all_daily(symbols: list[str]) -> dict[str, pd.DataFrame]:
    cache_path = REPORT_DIR / "daily_ohlcv_all_symbols.pkl"
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
    params = {
        "symbols": symbols,
        "start_ts": datetime.combine(WARMUP_START, time(9, 0)),
        "end_ts": datetime.combine(END_DATE, time(15, 30)),
    }
    rows = pd.read_sql(query, get_engine(), params=params)
    rows["trade_date"] = pd.to_datetime(rows["trade_date"]).dt.date
    daily: dict[str, pd.DataFrame] = {}
    for symbol, frame in rows.groupby("symbol", sort=False):
        item = frame.set_index("trade_date")[["open", "high", "low", "close", "volume"]].sort_index()
        daily[str(symbol)] = item
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    pd.to_pickle(daily, cache_path)
    return daily


def _feature_row(symbol: str, frame: pd.DataFrame, item_date: date) -> dict[str, Any] | None:
    if item_date not in frame.index:
        return None
    row = frame.loc[item_date]
    close = float(row["close"])
    volume = pd.to_numeric(frame.loc[:item_date, "volume"], errors="coerce").tail(20)
    turnover = pd.to_numeric(frame.loc[:item_date, "close"], errors="coerce").tail(20) * volume
    return {
        "symbol": symbol,
        "avg_daily_turnover_20d": float(turnover.mean()),
        "close": close,
        "sma_200": float(pd.to_numeric(frame.loc[:item_date, "close"], errors="coerce").tail(200).mean()),
        "adx_14": float(row.get("adx", float("nan"))),
        "atr_pct_20d": float(row.get("atr_pct", float("nan")) * 100),
    }


def _build_universe_by_date(prepared: dict[str, pd.DataFrame]) -> tuple[dict[date, set[str]], pd.DataFrame]:
    all_dates = sorted({idx for frame in prepared.values() for idx in frame.index if START_DATE <= idx <= END_DATE})
    rows: list[dict[str, Any]] = []
    universe_by_date: dict[date, set[str]] = {}
    for item_date in all_dates:
        feature_rows = [row for symbol, frame in prepared.items() if (row := _feature_row(symbol, frame, item_date))]
        if not feature_rows:
            universe_by_date[item_date] = set()
            continue
        feature_frame = pd.DataFrame(feature_rows)
        symbols = set(filter_mean_reversion_universe(feature_frame))
        universe_by_date[item_date] = symbols
        rows.append({"date": item_date.isoformat(), "symbol_count": len(symbols)})
    counts = pd.DataFrame(rows)
    return universe_by_date, counts


def _v20_signals(item: pd.DataFrame) -> pd.DataFrame:
    close = pd.to_numeric(item["close"], errors="coerce")
    rsi = pd.to_numeric(item["rsi"], errors="coerce")
    vol_ratio = pd.to_numeric(item["vol_ratio"], errors="coerce")
    regime_ok = item["regime"].astype(str).eq("ranging")
    item["long_signal"] = (close < pd.to_numeric(item["bb_lower"], errors="coerce")) & (rsi < 30) & regime_ok & (vol_ratio > 0.8)
    item["short_signal"] = (close > pd.to_numeric(item["bb_upper"], errors="coerce")) & (rsi > 70) & regime_ok & (vol_ratio > 0.8)
    return item


def _refined_signals(item: pd.DataFrame) -> pd.DataFrame:
    close = pd.to_numeric(item["close"], errors="coerce")
    open_ = pd.to_numeric(item["open"], errors="coerce")
    rsi = pd.to_numeric(item["rsi"], errors="coerce")
    avg_volume = pd.to_numeric(item["volume"], errors="coerce").rolling(20, min_periods=1).mean()
    volume = pd.to_numeric(item["volume"], errors="coerce")
    bb_width = pd.to_numeric(item["bb_width"], errors="coerce")
    item["long_signal"] = (
        (close < pd.to_numeric(item["bb_lower"], errors="coerce"))
        & (rsi < 30)
        & (rsi > rsi.shift(1))
        & (close > open_)
        & (volume > 1.5 * avg_volume)
        & (bb_width < 0.12)
    )
    item["short_signal"] = (
        (close > pd.to_numeric(item["bb_upper"], errors="coerce"))
        & (rsi > 70)
        & (rsi < rsi.shift(1))
        & (close < open_)
        & (volume > 1.3 * avg_volume)
        & (bb_width < 0.12)
    )
    return item


def _make_prepare(universe_by_date: dict[date, set[str]], signal_builder: Callable[[pd.DataFrame], pd.DataFrame]):
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

    return prepare


@contextmanager
def _patched_engine(
    universe_by_date: dict[date, set[str]],
    signal_builder: Callable[[pd.DataFrame], pd.DataFrame],
    atr_multiplier: float,
    confirm_15min: bool,
):
    original_prepare = engine._prepare_symbol_frame
    original_params = engine._strategy_params
    original_entry = engine._entry_signal

    def params() -> dict[str, Any]:
        payload = original_params()
        payload["atr"]["sl_atr_multiplier"] = atr_multiplier
        return payload

    def entry_signal(row: pd.Series) -> str | None:
        direction = original_entry(row)
        if not confirm_15min or direction is None:
            return direction
        symbol = str(row.get("symbol", ""))
        frame = prepared_daily.get(symbol)
        if frame is None:
            return None
        idx = list(frame.index)
        try:
            signal_idx = idx.index(row.name)
        except ValueError:
            return None
        if signal_idx + 1 >= len(idx):
            return None
        next_date = idx[signal_idx + 1]
        bars = fetch_15min(symbol, datetime.combine(next_date, time(9, 15)), datetime.combine(next_date, time(10, 0)))
        confirmed, _entry_price = find_confirmation_entry(bars, direction, float(row["close"]))
        return direction if confirmed else None

    def prepare(df: pd.DataFrame, index_df: pd.DataFrame | None = None) -> pd.DataFrame:
        return _make_prepare(universe_by_date, signal_builder)(df, index_df=index_df)

    engine._prepare_symbol_frame = prepare
    engine._strategy_params = params
    engine._entry_signal = entry_signal
    try:
        yield
    finally:
        engine._prepare_symbol_frame = original_prepare
        engine._strategy_params = original_params
        engine._entry_signal = original_entry


def _direction_metrics(trades: list[Any], direction: str) -> dict[str, float | int]:
    selected = [trade for trade in trades if trade.direction == direction]
    wins = [trade for trade in selected if trade.net_pnl > 0]
    losses = [trade for trade in selected if trade.net_pnl < 0]
    gross_win = sum(trade.net_pnl for trade in wins)
    gross_loss = abs(sum(trade.net_pnl for trade in losses))
    return {
        f"{direction}_trades": len(selected),
        f"{direction}_win_rate": len(wins) / len(selected) if selected else 0.0,
        f"{direction}_pf": gross_win / gross_loss if gross_loss else 0.0,
    }


def _run_variant(name: str, symbols: list[str], universe_by_date: dict[date, set[str]], signal_builder, atr_multiplier: float, confirm_15min: bool) -> dict[str, Any]:
    global prepared_daily
    with _patched_engine(universe_by_date, signal_builder, atr_multiplier, confirm_15min):
        result = engine.run_backtest(symbols, START_DATE, END_DATE, daily_data=prepared_daily)
    metrics = generate_report(result)
    metrics.update(_direction_metrics(result.trades, "long"))
    metrics.update(_direction_metrics(result.trades, "short"))
    metrics["variant"] = name
    metrics["atr_multiplier"] = atr_multiplier
    metrics["confirm_15min"] = confirm_15min
    pd.DataFrame([trade.__dict__ for trade in result.trades]).to_csv(REPORT_DIR / f"{name}_trades.csv", index=False)
    result.equity_curve.to_csv(REPORT_DIR / f"{name}_equity.csv", index=False)
    (REPORT_DIR / f"{name}_summary.json").write_text(json.dumps(metrics, indent=2, default=str), encoding="utf-8")
    return metrics


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    symbols = fetch_active_universe()
    print(f"Loading daily data for {len(symbols)} symbols...")
    global prepared_daily
    prepared_daily = {}
    raw_daily = _load_all_daily(symbols)
    for i, symbol in enumerate(symbols, start=1):
        frame = raw_daily.get(symbol, pd.DataFrame())
        if not frame.empty:
            item = add_all_indicators(frame.copy())
            item["symbol"] = symbol
            item.index = pd.to_datetime(item.index).date
            prepared_daily[symbol] = item
        if i % 50 == 0:
            print(f"  loaded {i}/{len(symbols)} symbols")

    universe_by_date, counts = _build_universe_by_date(prepared_daily)
    counts.to_csv(REPORT_DIR / "minimal_filter_universe_counts_by_day.csv", index=False)
    universe_stats = {
        "avg_symbols_per_day": float(counts["symbol_count"].mean()) if not counts.empty else 0.0,
        "median_symbols_per_day": float(counts["symbol_count"].median()) if not counts.empty else 0.0,
        "min_symbols_day": int(counts["symbol_count"].min()) if not counts.empty else 0,
        "max_symbols_day": int(counts["symbol_count"].max()) if not counts.empty else 0,
        "pct_days_50_to_150": float(((counts["symbol_count"] >= 50) & (counts["symbol_count"] <= 150)).mean()) if not counts.empty else 0.0,
    }
    (REPORT_DIR / "minimal_filter_universe_stats.json").write_text(json.dumps(universe_stats, indent=2), encoding="utf-8")
    print(f"Universe stats: {universe_stats}")

    metrics: list[dict[str, Any]] = []
    metrics.append(_run_variant("v2_minimal", symbols, universe_by_date, _v20_signals, 1.5, False))
    if metrics[-1]["trade_count"] < 50:
        print("V2-minimal produced <50 trades. Per plan, rerunning without SMA200.")
        no_sma_universe = {
            item_date: {
                symbol
                for symbol, frame in prepared_daily.items()
                if (row := _feature_row(symbol, frame, item_date))
                and row["avg_daily_turnover_20d"] > 20_000_000
                and row["adx_14"] < 25.0
                and row["atr_pct_20d"] < 4.5
            }
            for item_date in universe_by_date
        }
        metrics.append(_run_variant("v2_minimal_no_sma200", symbols, no_sma_universe, _v20_signals, 1.5, False))
    metrics.append(_run_variant("v3_minimal", symbols, universe_by_date, _refined_signals, 2.5, False))
    metrics.append(_run_variant("v4_minimal_15min", symbols, universe_by_date, _refined_signals, 2.5, True))
    summary = pd.DataFrame(metrics)
    summary.to_csv(REPORT_DIR / "minimal_filter_variant_summary.csv", index=False)
    print(summary[["variant", "total_return", "max_drawdown", "sharpe_ratio", "win_rate", "profit_factor", "trade_count", "long_trades", "short_trades"]].to_string(index=False))


prepared_daily: dict[str, pd.DataFrame] = {}


if __name__ == "__main__":
    main()
