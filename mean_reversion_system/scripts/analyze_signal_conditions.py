"""Diagnose mean-reversion signal condition attrition."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from mean_reversion_system.scripts.run_backtest import _build_universe_by_date, _load_all_daily, _parse_date
from mean_reversion_system.src.data.fetcher import fetch_active_universe
from mean_reversion_system.src.strategy.signals import add_all_indicators


def _count(mask: pd.Series) -> int:
    return int(mask.fillna(False).sum())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    args = parser.parse_args()
    start = _parse_date(args.start)
    end = _parse_date(args.end)
    warmup_start = date(max(2020, start.year - 1), 1, 1)
    out_dir = ROOT / "reports" / "backtests" / "v3_signal_diagnostics"
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

    totals: dict[str, int] = {
        "candidate_bars": 0,
        "base_bb_rsi_volratio": 0,
        "base_plus_hook": 0,
        "base_plus_candle": 0,
        "base_plus_volume_spike": 0,
        "base_plus_bb_width": 0,
        "v3_all_conditions": 0,
        "v3_no_candle": 0,
    }
    by_year: dict[str, dict[str, int]] = {}
    for symbol, item in daily.items():
        allowed = pd.Series([symbol in universe_by_date.get(idx, set()) and start <= idx <= end for idx in item.index], index=item.index)
        close = pd.to_numeric(item["close"], errors="coerce")
        open_ = pd.to_numeric(item["open"], errors="coerce")
        rsi = pd.to_numeric(item["rsi"], errors="coerce")
        volume = pd.to_numeric(item["volume"], errors="coerce")
        avg_volume = volume.rolling(20, min_periods=1).mean()
        base = allowed & (close < pd.to_numeric(item["bb_lower"], errors="coerce")) & (rsi < 30) & (pd.to_numeric(item["vol_ratio"], errors="coerce") > 0.8)
        hook = rsi > rsi.shift(1)
        candle = close > open_
        spike = volume > 1.5 * avg_volume
        width = pd.to_numeric(item["bb_width"], errors="coerce").between(0.05, 0.15, inclusive="both")
        masks = {
            "candidate_bars": allowed,
            "base_bb_rsi_volratio": base,
            "base_plus_hook": base & hook,
            "base_plus_candle": base & candle,
            "base_plus_volume_spike": base & spike,
            "base_plus_bb_width": base & width,
            "v3_all_conditions": base & hook & candle & spike & width,
            "v3_no_candle": base & hook & spike & width,
        }
        for key, mask in masks.items():
            totals[key] += _count(mask)
        for idx in item.index:
            if not (start <= idx <= end):
                continue
            year = str(idx.year)
            row = by_year.setdefault(year, {key: 0 for key in totals})
            for key, mask in masks.items():
                row[key] += int(bool(mask.loc[idx]))

    payload: dict[str, Any] = {"totals": totals, "by_year": by_year}
    (out_dir / "signal_condition_attrition.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
