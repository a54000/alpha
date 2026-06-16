"""Day 0 paper scanner dry run for locked Disha sleeves."""

from __future__ import annotations

import json
import sys
import argparse
from pathlib import Path

import pandas as pd
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from mean_reversion_system.src.data.db_connector import get_engine
from mean_reversion_system.src.strategy.signals import add_all_indicators, generate_long_signals
from mean_reversion_system.src.strategy.vcp_signals import add_vcp_features, generate_vcp_long_signals

OUT = ROOT / "results" / "sprint_2_8"


def _load_daily_bars() -> pd.DataFrame:
    query = """
        WITH latest AS (
            SELECT max((datetime AT TIME ZONE 'Asia/Kolkata')::date) AS max_date
            FROM public.ohlcv_15min
            WHERE symbol NOT IN ('NIFTY50', 'BANKNIFTY') AND volume > 0
        ),
        liquid AS (
            SELECT symbol
            FROM public.ohlcv_15min, latest
            WHERE symbol NOT IN ('NIFTY50', 'BANKNIFTY')
              AND volume > 0
              AND (datetime AT TIME ZONE 'Asia/Kolkata')::date >= latest.max_date - INTERVAL '30 days'
            GROUP BY symbol
            ORDER BY avg(close::double precision * volume::double precision) DESC
            LIMIT 220
        ),
        bars AS (
            SELECT
                symbol,
                (datetime AT TIME ZONE 'Asia/Kolkata')::date AS session_date,
                datetime,
                open::double precision AS open,
                high::double precision AS high,
                low::double precision AS low,
                close::double precision AS close,
                volume::bigint AS volume
            FROM public.ohlcv_15min, latest
            WHERE symbol NOT IN ('NIFTY50', 'BANKNIFTY')
              AND symbol IN (SELECT symbol FROM liquid)
              AND volume > 0
              AND (datetime AT TIME ZONE 'Asia/Kolkata')::date >= latest.max_date - INTERVAL '420 days'
              AND (datetime AT TIME ZONE 'Asia/Kolkata')::date <= latest.max_date
        ),
        ranked AS (
            SELECT
                *,
                row_number() OVER (PARTITION BY symbol, session_date ORDER BY datetime ASC) AS rn_open,
                row_number() OVER (PARTITION BY symbol, session_date ORDER BY datetime DESC) AS rn_close
            FROM bars
        )
        SELECT
            symbol,
            session_date AS date,
            max(open) FILTER (WHERE rn_open = 1) AS open,
            max(high) AS high,
            min(low) AS low,
            max(close) FILTER (WHERE rn_close = 1) AS close,
            sum(volume) AS volume
        FROM ranked
        GROUP BY symbol, session_date
        ORDER BY symbol, session_date
    """
    frame = pd.read_sql(text(query), get_engine())
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    return frame


def _latest_market_gate() -> dict[str, object]:
    labels = pd.read_csv(ROOT / "results" / "sprint_2_1" / "daily_regime_labels.csv")
    labels["session_date"] = pd.to_datetime(labels["session_date"]).dt.date
    latest = labels.iloc[-1]
    nifty_return_60d = pd.to_numeric(labels["nifty_close"], errors="coerce").iloc[-1] / pd.to_numeric(labels["nifty_close"], errors="coerce").shift(60).iloc[-1] - 1
    constructive = bool(
        latest["regime_label"] == "UPTREND"
        or (
            latest["regime_label"] == "RANGING"
            and float(latest["nifty_close"]) > float(latest["sma200"])
            and float(latest["di_plus"]) >= float(latest["di_minus"])
        )
    )
    return {
        "date": latest["session_date"],
        "regime_label": latest["regime_label"],
        "constructive_market": constructive,
        "nifty_return_60d": float(nifty_return_60d),
        "vcp_market_gate": bool(constructive and nifty_return_60d > 0),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force-vcp-gate", action="store_true", help="Research-only override to scan VCP patterns even when market gate is off.")
    parser.add_argument(
        "--after-date",
        help=(
            "Resume guard: only write scanner artifacts when the latest available "
            "DB session date is after this YYYY-MM-DD date."
        ),
    )
    parser.add_argument(
        "--min-fresh-symbols",
        type=int,
        default=1,
        help="Resume guard: minimum symbols required on the latest DB session date.",
    )
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    daily = _load_daily_bars()
    market = _latest_market_gate()
    rows = []
    latest_date = max(daily["date"])
    if args.after_date:
        after_date = pd.to_datetime(args.after_date).date()
        fresh_symbols = int(daily.loc[daily["date"] == latest_date, "symbol"].nunique())
        if latest_date <= after_date:
            summary = {
                "status": "skipped_stale_data",
                "scan_date": str(latest_date),
                "after_date": str(after_date),
                "symbols_scanned": int(daily["symbol"].nunique()),
                "fresh_symbols": fresh_symbols,
                "min_fresh_symbols": args.min_fresh_symbols,
                "reason": "latest DB session date is not newer than the paper resume guard date",
                "market": {key: str(value) if key == "date" else value for key, value in market.items()},
                "force_vcp_gate": args.force_vcp_gate,
                "output": None,
            }
            (OUT / "day0_scanner_dry_run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
            print(json.dumps(summary, indent=2))
            raise SystemExit(2)
        if fresh_symbols < args.min_fresh_symbols:
            summary = {
                "status": "skipped_insufficient_fresh_symbols",
                "scan_date": str(latest_date),
                "after_date": str(after_date),
                "symbols_scanned": int(daily["symbol"].nunique()),
                "fresh_symbols": fresh_symbols,
                "min_fresh_symbols": args.min_fresh_symbols,
                "reason": "latest DB session date is newer, but too few symbols have candles on that date",
                "market": {key: str(value) if key == "date" else value for key, value in market.items()},
                "force_vcp_gate": args.force_vcp_gate,
                "output": None,
            }
            (OUT / "day0_scanner_dry_run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
            print(json.dumps(summary, indent=2))
            raise SystemExit(2)
    for symbol, group in daily.groupby("symbol", sort=False):
        base = group.sort_values("date").reset_index(drop=True)
        if len(base) < 260:
            continue
        mr = add_all_indicators(base)
        vcp = add_vcp_features(base)
        v4b_signal = bool(generate_long_signals(mr).iloc[-1])
        vcp_signal = bool(generate_vcp_long_signals(vcp).iloc[-1]) and (bool(market["vcp_market_gate"]) or args.force_vcp_gate)
        if v4b_signal or vcp_signal:
            rows.append(
                {
                    "scan_date": latest_date,
                    "symbol": symbol,
                    "v4b_entry_signal": v4b_signal,
                    "vcp_entry_signal": vcp_signal,
                    "market_regime": market["regime_label"],
                    "vcp_market_gate": market["vcp_market_gate"],
                    "close": float(base.iloc[-1]["close"]),
                }
            )
    signals = pd.DataFrame(rows)
    if signals.empty:
        signals = pd.DataFrame(columns=["scan_date", "symbol", "v4b_entry_signal", "vcp_entry_signal", "market_regime", "vcp_market_gate", "close"])
    signals.to_csv(OUT / "day0_scanner_dry_run_signals.csv", index=False)
    summary = {
        "scan_date": str(latest_date),
        "symbols_scanned": int(daily["symbol"].nunique()),
        "v4b_signals": int(signals["v4b_entry_signal"].sum()) if not signals.empty else 0,
        "vcp_signals": int(signals["vcp_entry_signal"].sum()) if not signals.empty else 0,
        "market": {key: str(value) if key == "date" else value for key, value in market.items()},
        "force_vcp_gate": args.force_vcp_gate,
        "output": str(OUT / "day0_scanner_dry_run_signals.csv"),
    }
    (OUT / "day0_scanner_dry_run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
