"""Sprint 1.7 deployment diagnostics and lever tests."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, Callable

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from mean_reversion_system.scripts.run_backtest import _load_all_daily, _patched_engine, _parse_date
from mean_reversion_system.src.backtest import engine
from mean_reversion_system.src.backtest.reporter import generate_report
from mean_reversion_system.src.data.fetcher import fetch_active_universe, fetch_universe
from mean_reversion_system.src.regime.detector import detect_regime
from mean_reversion_system.src.strategy.signals import add_all_indicators

START = date(2020, 1, 1)
END = date(2025, 1, 1)
WARMUP = date(2020, 1, 1)
OUT = ROOT / "reports" / "backtests" / "sprint17_deployment"
INITIAL_CAPITAL = 1_000_000


def _normalise(symbol: str) -> str:
    return symbol.replace(".NS", "")


def _load_prepared() -> dict[str, pd.DataFrame]:
    symbols = fetch_active_universe()
    raw = _load_all_daily(symbols, WARMUP, END)
    prepared: dict[str, pd.DataFrame] = {}
    for symbol, frame in raw.items():
        if frame.empty:
            continue
        item = add_all_indicators(frame.copy())
        item["symbol"] = symbol
        item["regime"] = detect_regime(item)
        item["earnings_blackout"] = False
        item.index = pd.to_datetime(item.index).date
        prepared[symbol] = item
    return prepared


def _feature_row(symbol: str, frame: pd.DataFrame, item_date: date, thresholds: dict[str, float]) -> dict[str, Any] | None:
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
        "avg_volume_20d": float(volume_20d.mean()),
        "close": float(row["close"]),
        "sma_200": float(pd.to_numeric(history["close"], errors="coerce").tail(200).mean()),
        "adx_14": float(row.get("adx", float("nan"))),
        "atr_pct_20d": float(row.get("atr_pct", float("nan")) * 100),
    }


def _build_universe(
    daily: dict[str, pd.DataFrame],
    symbols: list[str],
    thresholds: dict[str, float],
) -> dict[date, set[str]]:
    all_dates = sorted({idx for symbol in symbols for idx in daily[symbol].index if START <= idx <= END})
    by_date: dict[date, set[str]] = {}
    for item_date in all_dates:
        rows = [row for symbol in symbols if (row := _feature_row(symbol, daily[symbol], item_date, thresholds))]
        if not rows:
            continue
        df = pd.DataFrame(rows)
        mask = (
            (df["avg_daily_turnover_20d"] > thresholds["turnover_min"])
            & (df["avg_volume_20d"] > thresholds["volume_min"])
            & (df["close"] > df["sma_200"])
            & (df["adx_14"] < thresholds["adx_max"])
            & (df["atr_pct_20d"].between(thresholds["atr_min"], thresholds["atr_max"], inclusive="both"))
        )
        by_date[item_date] = set(df.loc[mask, "symbol"].astype(str))
    return by_date


def _signal_builder(bb_min: float, bb_max: float, rsi_max: float, vol_min: float) -> Callable[[pd.DataFrame], pd.DataFrame]:
    def build(item: pd.DataFrame) -> pd.DataFrame:
        close = pd.to_numeric(item["close"], errors="coerce")
        rsi = pd.to_numeric(item["rsi"], errors="coerce")
        vol_ratio = pd.to_numeric(item["vol_ratio"], errors="coerce")
        bb_width = pd.to_numeric(item["bb_width"], errors="coerce")
        item["long_signal"] = (
            (close < pd.to_numeric(item["bb_lower"], errors="coerce"))
            & (rsi < rsi_max)
            & (vol_ratio > vol_min)
            & (bb_width.between(bb_min, bb_max, inclusive="both"))
        )
        item["short_signal"] = False
        return item

    return build


def _summarise_result(name: str, result: Any, signal_count: int, generated: int, rejected: dict[str, int]) -> dict[str, Any]:
    metrics = generate_report(result)
    equity = result.equity_curve.copy()
    avg_deployment = 0.0
    if "open_notional" in equity.columns and "equity" in equity.columns:
        avg_deployment = float((pd.to_numeric(equity["open_notional"], errors="coerce") / pd.to_numeric(equity["equity"], errors="coerce")).mean())
    # The current engine equity curve does not store notional, so use trade notional occupancy estimate.
    trades = pd.DataFrame([trade.__dict__ for trade in result.trades])
    if not trades.empty:
        days = pd.to_datetime(equity["date"]).dt.date.tolist() if not equity.empty else []
        deployed = []
        for item_date in days:
            open_notional = 0.0
            for _, trade in trades.iterrows():
                if pd.to_datetime(trade["entry_date"]).date() <= item_date <= pd.to_datetime(trade["exit_date"]).date():
                    open_notional += abs(float(trade["quantity"]) * float(trade["entry_price"]))
            deployed.append(open_notional / INITIAL_CAPITAL)
        avg_deployment = float(pd.Series(deployed).mean()) if deployed else 0.0
    deployed_cagr = ((1 + (metrics.get("total_return", 0.0) / avg_deployment)) ** (1 / 3.5509924709103355) - 1) if avg_deployment else 0.0
    trades_per_year = {}
    if not trades.empty:
        trades["exit_year"] = pd.to_datetime(trades["exit_date"]).dt.year
        trades_per_year = {str(int(k)): int(v) for k, v in trades.groupby("exit_year").size().to_dict().items()}
    return {
        "variant": name,
        "signals_generated": generated,
        "signals_taken": len(result.trades),
        "signals_per_year": generated / 3.5509924709103355,
        "trades_per_year": trades_per_year,
        "avg_deployment_pct": avg_deployment,
        "deployed_cagr": deployed_cagr,
        "rejections": rejected,
        **metrics,
    }


def _run_variant(name: str, daily: dict[str, pd.DataFrame], symbols: list[str], universe_by_date: dict[date, set[str]], signal_builder, max_positions: int = 5) -> dict[str, Any]:
    original_params = engine._strategy_params

    def params() -> dict[str, Any]:
        payload = original_params()
        payload["risk"]["max_concurrent_positions"] = max_positions
        payload["atr"]["sl_atr_multiplier"] = 2.25
        payload["partial_exit"] = {"enabled": False}
        return payload

    generated = 0
    for symbol in symbols:
        frame = daily[symbol]
        item = signal_builder(frame.copy())
        allowed = pd.Series([symbol in universe_by_date.get(idx, set()) and START <= idx <= END for idx in item.index], index=item.index)
        generated += int((item["long_signal"].fillna(False).astype(bool) & allowed).sum())

    engine._strategy_params = params
    try:
        with _patched_engine(universe_by_date, atr_multiplier=2.25, signal_builder=signal_builder):
            result = engine.run_backtest(symbols, START, END, daily_data=daily)
    finally:
        engine._strategy_params = original_params
    rejected = {"not_taken_total": max(generated - len(result.trades), 0)}
    rows = [trade.__dict__ for trade in result.trades]
    pd.DataFrame(rows).to_csv(OUT / f"{name}_trades.csv", index=False)
    result.equity_curve.to_csv(OUT / f"{name}_equity.csv", index=False)
    return _summarise_result(name, result, len(result.trades), generated, rejected)


def _diagnostics(daily: dict[str, pd.DataFrame], symbols: list[str], universe_by_date: dict[date, set[str]]) -> dict[str, Any]:
    per_symbol = []
    attrition = {"universe_not_passed": 0, "bb_width_too_wide_or_narrow": 0, "rsi_not_oversold": 0, "volume_below_0_8": 0, "final_signal": 0}
    for symbol in symbols:
        frame = daily[symbol]
        allowed = pd.Series([symbol in universe_by_date.get(idx, set()) and START <= idx <= END for idx in frame.index], index=frame.index)
        close = pd.to_numeric(frame["close"], errors="coerce")
        bb_lower = pd.to_numeric(frame["bb_lower"], errors="coerce")
        bb_width = pd.to_numeric(frame["bb_width"], errors="coerce")
        rsi = pd.to_numeric(frame["rsi"], errors="coerce")
        vol = pd.to_numeric(frame["vol_ratio"], errors="coerce")
        price_touch = close < bb_lower
        squeeze10 = bb_width < 0.10
        squeeze15 = bb_width.between(0.05, 0.15, inclusive="both")
        final_signal = allowed & price_touch & (rsi < 30) & (vol > 0.8) & squeeze15
        eligible_days = int(allowed.sum())
        squeeze_days = int((allowed & squeeze10).sum())
        squeeze_rsi_days = int((allowed & squeeze10 & (rsi < 30)).sum())
        per_symbol.append(
            {
                "symbol": symbol,
                "eligible_days": eligible_days,
                "signals": int(final_signal.sum()),
                "squeeze_freq_lt_10": squeeze_days / eligible_days if eligible_days else 0.0,
                "squeeze_days_with_rsi_lt_30": squeeze_rsi_days / squeeze_days if squeeze_days else 0.0,
            }
        )
        attrition["universe_not_passed"] += int((~allowed & (START <= pd.Series(frame.index, index=frame.index)) & (pd.Series(frame.index, index=frame.index) <= END)).sum())
        base = allowed & price_touch
        attrition["bb_width_too_wide_or_narrow"] += int((base & ~squeeze15).sum())
        attrition["rsi_not_oversold"] += int((base & squeeze15 & ~(rsi < 30)).sum())
        attrition["volume_below_0_8"] += int((base & squeeze15 & (rsi < 30) & ~(vol > 0.8)).sum())
        attrition["final_signal"] += int(final_signal.sum())
    per_symbol_df = pd.DataFrame(per_symbol)
    per_symbol_df.to_csv(OUT / "diagnostic_per_symbol.csv", index=False)
    return {
        "zero_signal_symbols": int((per_symbol_df["signals"] == 0).sum()),
        "symbol_count": int(len(per_symbol_df)),
        "avg_squeeze_frequency_lt_10": float(per_symbol_df["squeeze_freq_lt_10"].mean()),
        "avg_squeeze_days_with_rsi_lt_30": float(per_symbol_df["squeeze_days_with_rsi_lt_30"].mean()),
        "entry_filter_attrition": attrition,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    daily = _load_prepared()
    active_symbols = sorted(daily)
    seed_symbols = [_normalise(symbol) for symbol in fetch_universe(ROOT / "config" / "universe.yaml")]
    seed_symbols = [symbol for symbol in seed_symbols if symbol in daily]
    active_by_turnover = sorted(
        active_symbols,
        key=lambda symbol: float((pd.to_numeric(daily[symbol]["close"], errors="coerce").tail(20) * pd.to_numeric(daily[symbol]["volume"], errors="coerce").tail(20)).mean()),
        reverse=True,
    )
    thresholds = {"turnover_min": 20_000_000, "volume_min": 0, "adx_max": 25, "atr_min": 1.5, "atr_max": 4.5}
    base_symbols = active_symbols
    base_universe = _build_universe(daily, base_symbols, thresholds)
    diagnostics = _diagnostics(daily, base_symbols, base_universe)

    variants = [
        ("v4b_baseline", base_symbols, thresholds, _signal_builder(0.05, 0.15, 30, 0.8), 5),
        ("v6a_top150_liquid", active_by_turnover[:150], thresholds, _signal_builder(0.05, 0.15, 30, 0.8), 5),
        ("v6b_top200_liquid", active_by_turnover[:200], thresholds, _signal_builder(0.05, 0.15, 30, 0.8), 5),
        ("v6c_all_active", active_symbols, thresholds, _signal_builder(0.05, 0.15, 30, 0.8), 5),
        ("v6d_bbw_12", base_symbols, thresholds, _signal_builder(0.05, 0.12, 30, 0.8), 5),
        ("v6e_rsi_35", base_symbols, thresholds, _signal_builder(0.05, 0.15, 35, 0.8), 5),
        ("v6f_bbw_12_rsi_35", base_symbols, thresholds, _signal_builder(0.05, 0.12, 35, 0.8), 5),
        ("v6g_volume_0_6", base_symbols, thresholds, _signal_builder(0.05, 0.15, 30, 0.6), 5),
        ("v6h_maxpos_10", base_symbols, thresholds, _signal_builder(0.05, 0.15, 30, 0.8), 10),
    ]
    summaries = []
    for name, symbols, universe_thresholds, signal_builder, max_positions in variants:
        universe = _build_universe(daily, symbols, universe_thresholds)
        summary = _run_variant(name, daily, symbols, universe, signal_builder, max_positions=max_positions)
        summary["symbol_count_input"] = len(symbols)
        summaries.append(summary)
        print(json.dumps(summary, default=str))

    pd.DataFrame(summaries).to_csv(OUT / "variant_summary.csv", index=False)
    report = {"diagnostics": diagnostics, "variants": summaries, "notes": {"seed_symbols_available": len(seed_symbols), "active_symbols": len(active_symbols), "universe_yaml_used_by_current_runner": False}}
    (OUT / "sprint17_summary.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
