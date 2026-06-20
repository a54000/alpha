#!/usr/bin/env python3
"""VWAP false-negative and intraday sanity audit.

Read-only diagnostic. Uses artifacts from audit_vwap_edge_robustness.py and
Angel 15-minute candles to inspect removed VWAP trades.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


REPO_ROOT = Path(__file__).resolve().parents[1]
ROBUSTNESS_DIR = REPO_ROOT / "reports" / "vwap_edge_robustness"
OUTPUT_DIR = REPO_ROOT / "reports" / "vwap_false_negative_audit"


def pct(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{value * 100:.2f}%"


def money(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"Rs {value:,.0f}"


def load_removed(period: str) -> pd.DataFrame:
    path = ROBUSTNESS_DIR / f"{period}_removed_by_vwap.csv"
    return pd.read_csv(path)


def classify_removed(frame: pd.DataFrame) -> dict[str, object]:
    if frame.empty:
        return {}
    winners = frame[frame["net_pnl"] > 0].copy()
    losers = frame[frame["net_pnl"] <= 0].copy()
    return {
        "removed_trades": int(len(frame)),
        "removed_winners": int(len(winners)),
        "removed_losers": int(len(losers)),
        "winner_rate_among_removed": len(winners) / len(frame) if len(frame) else None,
        "removed_net_pnl": float(frame["net_pnl"].sum()),
        "removed_winner_pnl": float(winners["net_pnl"].sum()) if not winners.empty else 0.0,
        "removed_loser_pnl": float(losers["net_pnl"].sum()) if not losers.empty else 0.0,
        "largest_removed_winner": (
            winners.sort_values("net_pnl", ascending=False).head(1).to_dict(orient="records")[0] if not winners.empty else None
        ),
        "largest_removed_loser": (
            losers.sort_values("net_pnl").head(1).to_dict(orient="records")[0] if not losers.empty else None
        ),
    }


def intraday_window(engine, symbol: str, entry_date: str, signal_date: str) -> tuple[pd.DataFrame, dict[str, object]]:
    query = text(
        """
        SELECT datetime, open, high, low, close, volume,
               close * volume AS traded_value
        FROM ohlcv_15min
        WHERE symbol = :symbol
          AND datetime::date = :entry_date
        ORDER BY datetime
        """
    )
    vwap_query = text(
        """
        SELECT SUM(((high + low + close) / 3.0) * volume) / NULLIF(SUM(volume), 0) AS vwap,
               MIN(low) AS low,
               MAX(high) AS high,
               MIN(open) AS first_open,
               MAX(close) AS last_close
        FROM ohlcv_15min
        WHERE symbol = :symbol
          AND datetime::date = :signal_date
          AND volume > 0
        """
    )
    with engine.connect() as connection:
        bars = pd.DataFrame(connection.execute(query, {"symbol": symbol, "entry_date": entry_date}).mappings().all())
        signal = connection.execute(vwap_query, {"symbol": symbol, "signal_date": signal_date}).mappings().first()
    if bars.empty:
        return bars, {}
    bars["datetime"] = pd.to_datetime(bars["datetime"])
    signal_vwap = float(signal["vwap"]) if signal and signal["vwap"] is not None else None
    bars["extension_vs_signal_vwap_pct"] = bars["open"].astype(float).apply(
        lambda value: (value / signal_vwap - 1.0) if signal_vwap else None
    )
    entry_1030 = bars[bars["datetime"].dt.strftime("%H:%M:%S") == "10:30:00"]
    first_bar = bars.iloc[0]
    entry_bar = entry_1030.iloc[0] if not entry_1030.empty else None
    summary = {
        "symbol": symbol,
        "signal_date": signal_date,
        "entry_date": entry_date,
        "signal_day_vwap": signal_vwap,
        "entry_open_0915": float(first_bar["open"]),
        "entry_1030_open": float(entry_bar["open"]) if entry_bar is not None else None,
        "entry_1030_high": float(entry_bar["high"]) if entry_bar is not None else None,
        "entry_1030_low": float(entry_bar["low"]) if entry_bar is not None else None,
        "entry_1030_close": float(entry_bar["close"]) if entry_bar is not None else None,
        "extension_0915_vs_signal_vwap": (float(first_bar["open"]) / signal_vwap - 1.0) if signal_vwap else None,
        "extension_1030_vs_signal_vwap": (float(entry_bar["open"]) / signal_vwap - 1.0) if entry_bar is not None and signal_vwap else None,
        "entry_day_high_until_1030": float(bars[bars["datetime"].dt.strftime("%H:%M:%S") <= "10:30:00"]["high"].max()),
        "entry_day_low_until_1030": float(bars[bars["datetime"].dt.strftime("%H:%M:%S") <= "10:30:00"]["low"].min()),
        "entry_day_close": float(bars.iloc[-1]["close"]),
    }
    return bars, summary


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    load_dotenv(REPO_ROOT / ".env")
    engine = create_engine(os.environ["ANGEL_DATABASE_URL"])

    payload: dict[str, object] = {"periods": {}, "intraday": {}}
    summary_rows = []
    for period in ["FY2024-25", "FY2025-26"]:
        removed = load_removed(period)
        removed.to_csv(OUTPUT_DIR / f"{period}_removed_trades.csv", index=False)
        stats = classify_removed(removed)
        payload["periods"][period] = stats
        summary_rows.append({"period": period, **{k: v for k, v in stats.items() if not isinstance(v, dict)}})

    pd.DataFrame(summary_rows).to_csv(OUTPUT_DIR / "false_negative_summary.csv", index=False)

    # Signal dates are the nearest recommendation dates that produced the skipped no-VWAP trades.
    target_trades = [
        {"symbol": "IDBI", "signal_date": "2026-02-16", "entry_date": "2026-02-17"},
        {"symbol": "BALKRISIND", "signal_date": "2026-02-09", "entry_date": "2026-02-10"},
    ]
    intraday_rows = []
    for target in target_trades:
        bars, summary = intraday_window(engine, target["symbol"], target["entry_date"], target["signal_date"])
        if not bars.empty:
            bars.to_csv(OUTPUT_DIR / f"{target['symbol']}_{target['entry_date']}_intraday.csv", index=False)
        payload["intraday"][target["symbol"]] = summary
        intraday_rows.append(summary)
    pd.DataFrame(intraday_rows).to_csv(OUTPUT_DIR / "intraday_entry_sanity.csv", index=False)

    (OUTPUT_DIR / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    lines = [
        "# VWAP False Negative And Intraday Audit",
        "",
        "This read-only audit checks whether the VWAP filter mostly removed losers or also rejected many winners, and inspects IDBI/BALKRISIND entry-day price action.",
        "",
        "## Removed Trade Precision",
        "",
        "| Period | Removed | Losers Removed | Winners Removed | Removed Net PnL | Winner PnL Lost | Loser PnL Avoided |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary_rows:
        lines.append(
            f"| {row['period']} | {row['removed_trades']} | {row['removed_losers']} | {row['removed_winners']} | "
            f"{money(row['removed_net_pnl'])} | {money(row['removed_winner_pnl'])} | {money(row['removed_loser_pnl'])} |"
        )
    lines.extend(["", "## Intraday Sanity", "", "| Symbol | Signal VWAP | 09:15 Open Ext | 10:30 Open Ext | 10:30 Open | Entry Day Close |", "| --- | ---: | ---: | ---: | ---: | ---: |"])
    for row in intraday_rows:
        lines.append(
            f"| {row.get('symbol')} | {money(row.get('signal_day_vwap'))} | {pct(row.get('extension_0915_vs_signal_vwap'))} | "
            f"{pct(row.get('extension_1030_vs_signal_vwap'))} | {money(row.get('entry_1030_open'))} | {money(row.get('entry_day_close'))} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- A high loser share among removed trades means the VWAP filter has good precision.",
            "- If IDBI/BALKRISIND were clearly above the 2.5% extension threshold at 10:30, the filter mechanism matches the actual price action.",
            "- This remains a diagnostic only; no strategy logic was changed.",
        ]
    )
    (OUTPUT_DIR / "VWAP_FALSE_NEGATIVE_AUDIT.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(payload, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
