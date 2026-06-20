#!/usr/bin/env python3
"""Standalone RRG swing long/short setup scanner.

This is research/analysis infrastructure only. It does not modify SectorEdge 10,
recommendation generation, paper trading, or production tables.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate standalone RRG swing long/short setup shortlist.")
    parser.add_argument("--pilot-schema", default="pilot_phase2a")
    parser.add_argument("--as-of", type=date.fromisoformat)
    parser.add_argument("--benchmark-symbol", default="NIFTY50")
    parser.add_argument("--min-volume-ratio", type=float, default=1.10)
    parser.add_argument("--risk-per-trade", type=float, default=10_000.0)
    parser.add_argument("--output-json", default="reports/rrg_swing_long_short_setup.json")
    parser.add_argument("--output-csv", default="reports/rrg_swing_long_short_setup.csv")
    return parser.parse_args()


def engine_from_env():
    load_dotenv(REPO_ROOT / ".env")
    url = os.environ.get("ANGEL_DATABASE_URL")
    if not url:
        raise RuntimeError("ANGEL_DATABASE_URL is required.")
    return create_engine(url, future=True, pool_pre_ping=True, pool_size=1, max_overflow=0)


def load_prices(engine, schema: str, as_of: date | None) -> tuple[pd.DataFrame, date]:
    with engine.connect() as connection:
        latest = as_of or connection.execute(text(f"SELECT MAX(date) FROM {schema}.daily_bars_clean")).scalar_one()
    query = text(
        f"""
        SELECT b.symbol, b.date, b.open, b.high, b.low, b.close, b.volume, f.sector
        FROM {schema}.daily_bars_clean b
        LEFT JOIN (
            SELECT DISTINCT ON (symbol) symbol, sector
            FROM {schema}.features_daily
            WHERE sector IS NOT NULL
            ORDER BY symbol, date DESC
        ) f ON f.symbol = b.symbol
        WHERE b.date BETWEEN :as_of - INTERVAL '360 days' AND :as_of
        ORDER BY b.symbol, b.date
        """
    )
    frame = pd.read_sql_query(query, engine, params={"as_of": latest})
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    for column in ["open", "high", "low", "close", "volume"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.dropna(subset=["symbol", "date", "close", "sector"]), latest


def load_benchmark(engine, symbol: str, as_of: date) -> pd.DataFrame:
    query = text(
        """
        SELECT datetime::date AS date, high, low, close
        FROM ohlcv_15min
        WHERE symbol = :symbol
          AND datetime::date BETWEEN :as_of - INTERVAL '360 days' AND :as_of
          AND datetime::time <= '15:15:00'
        ORDER BY datetime
        """
    )
    frame = pd.read_sql_query(query, engine, params={"symbol": symbol, "as_of": as_of})
    if frame.empty:
        raise RuntimeError(f"No benchmark bars found for {symbol}.")
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    for column in ["high", "low", "close"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    close = frame.dropna(subset=["close"]).groupby("date", as_index=False).tail(1)[["date", "close"]]
    ranges = frame.groupby("date", as_index=False).agg({"high": "max", "low": "min"})
    return close.merge(ranges, on="date", how="left").sort_values("date")


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    true_range = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    return true_range.ewm(alpha=1 / period, adjust=False).mean()


def sector_rrg(frame: pd.DataFrame, benchmark: pd.DataFrame, effective_as_of: date) -> dict[str, dict[str, object]]:
    frame = frame[frame["date"] <= effective_as_of].copy()
    close_wide = frame.pivot_table(index="date", columns="symbol", values="close", aggfunc="last").sort_index()
    sector_map = frame.drop_duplicates("symbol").set_index("symbol")["sector"].to_dict()
    benchmark_series = benchmark.set_index("date")["close"].sort_index()
    results: dict[str, dict[str, object]] = {}

    for sector in sorted(set(sector_map.values())):
        symbols = [symbol for symbol, item_sector in sector_map.items() if item_sector == sector and symbol in close_wide.columns]
        if len(symbols) < 3:
            continue
        sector_close = close_wide[symbols].pct_change().mean(axis=1).fillna(0).add(1).cumprod() * 100
        joined = pd.concat([sector_close.rename("sector"), benchmark_series.rename("benchmark")], axis=1).dropna()
        if len(joined) < 80:
            continue
        rs_raw = joined["sector"] / joined["benchmark"]
        rs_smooth = rs_raw.ewm(span=10, adjust=False).mean()
        rs_ratio = (rs_smooth / rs_smooth.rolling(52, min_periods=30).mean()) * 100
        rs_momentum = rs_ratio.pct_change(periods=1) * 100 + 100
        latest_ratio = float(rs_ratio.iloc[-1])
        latest_momentum = float(rs_momentum.iloc[-1])
        if not np.isfinite(latest_ratio) or not np.isfinite(latest_momentum):
            continue

        if latest_ratio >= 100 and latest_momentum >= 100:
            quadrant = "Leading"
        elif latest_ratio < 100 and latest_momentum >= 100:
            quadrant = "Improving"
        elif latest_ratio >= 100 and latest_momentum < 100:
            quadrant = "Weakening"
        else:
            quadrant = "Lagging"

        tail_ratio = rs_ratio.dropna().tail(4)
        tail_momentum = rs_momentum.dropna().tail(4)
        ratio_change = float(tail_ratio.iloc[-1] - tail_ratio.iloc[0]) if len(tail_ratio) >= 2 else 0.0
        momentum_change = float(tail_momentum.iloc[-1] - tail_momentum.iloc[0]) if len(tail_momentum) >= 2 else 0.0
        tail_direction = "right" if ratio_change > 0 else "left"
        if ratio_change > 0 and momentum_change > 0:
            action = "prefer_longs" if quadrant in {"Leading", "Improving"} else "watch_turn"
        elif ratio_change < 0 and momentum_change < 0:
            action = "prefer_shorts" if quadrant in {"Weakening", "Lagging"} else "exit_longs"
        else:
            action = "wait"

        results[sector] = {
            "sector": sector,
            "rs_ratio": round(latest_ratio, 2),
            "rs_momentum": round(latest_momentum, 2),
            "quadrant": quadrant,
            "tail_direction": tail_direction,
            "tail_ratio_change": round(ratio_change, 2),
            "tail_momentum_change": round(momentum_change, 2),
            "borderline": abs(latest_ratio - 100) < 1.5 or abs(latest_momentum - 100) < 1.0,
            "action": action,
        }
    return results


def percentile_scores(values: pd.Series, higher_is_better: bool = True) -> pd.Series:
    return values.rank(pct=True, ascending=not higher_is_better).fillna(0) * 100


def score_stocks(
    frame: pd.DataFrame,
    benchmark: pd.DataFrame,
    rrg: dict[str, dict[str, object]],
    effective_as_of: date,
    min_volume_ratio: float,
    risk_per_trade: float,
) -> pd.DataFrame:
    benchmark_close = benchmark.set_index("date")["close"].sort_index()
    rows: list[dict[str, object]] = []
    for symbol, group in frame.groupby("symbol"):
        df = group[group["date"] <= effective_as_of].sort_values("date").copy()
        if len(df) < 80:
            continue
        sector = str(df["sector"].iloc[-1])
        sector_info = rrg.get(sector)
        if not sector_info:
            continue
        close = df["close"].astype(float)
        high = df["high"].astype(float)
        low = df["low"].astype(float)
        volume = df["volume"].astype(float)
        latest_date = df["date"].iloc[-1]
        if latest_date not in benchmark_close.index:
            continue
        benchmark_pos = benchmark_close.index.get_loc(latest_date)
        if isinstance(benchmark_pos, slice):
            benchmark_pos = benchmark_pos.start
        if benchmark_pos < 63:
            continue

        stock_4w = close.iloc[-1] / close.iloc[-21] - 1
        nifty_4w = benchmark_close.iloc[benchmark_pos] / benchmark_close.iloc[benchmark_pos - 20] - 1
        rs_4w = stock_4w - nifty_4w
        momentum_skip_week = close.iloc[-5] / close.iloc[-63] - 1
        avg_vol_20 = volume.rolling(20).mean().iloc[-1]
        vol_ratio = float(volume.tail(5).mean() / avg_vol_20) if avg_vol_20 else np.nan
        making_high = bool(close.iloc[-1] > high.rolling(20).max().iloc[-2])
        higher_low = bool(low.tail(5).min() > low.iloc[-25:-5].min())
        structure = ((1 if making_high else 0) + (1 if higher_low else 0)) * 50
        atr_14 = atr(high, low, close, 14).iloc[-1]
        ema21 = close.ewm(span=21, adjust=False).mean().iloc[-1]
        proximity_atr = abs(close.iloc[-1] - ema21) / atr_14 if atr_14 else np.nan
        proximity = max(0.0, 100.0 - proximity_atr * 20.0) if np.isfinite(proximity_atr) else np.nan

        quadrant = str(sector_info["quadrant"])
        tail = str(sector_info["tail_direction"])
        sector_alignment_long = {
            ("Leading", "right"): 100,
            ("Improving", "right"): 70,
            ("Leading", "left"): 50,
            ("Improving", "left"): 20,
        }.get((quadrant, tail), 0)
        sector_alignment_short = {
            ("Lagging", "left"): 100,
            ("Weakening", "left"): 75,
            ("Lagging", "right"): 30,
            ("Weakening", "right"): 20,
        }.get((quadrant, tail), 0)
        rows.append(
            {
                "symbol": symbol,
                "date": latest_date,
                "sector": sector,
                "sector_quadrant": quadrant,
                "sector_tail": tail,
                "rs_4w": rs_4w,
                "momentum_skip_week": momentum_skip_week,
                "volume_ratio": min(vol_ratio, 3.0) if np.isfinite(vol_ratio) else np.nan,
                "structure_score": structure,
                "proximity_score": proximity,
                "sector_alignment_long": sector_alignment_long,
                "sector_alignment_short": sector_alignment_short,
                "close": close.iloc[-1],
                "atr_14": atr_14,
                "ema21": ema21,
            }
        )

    scored = pd.DataFrame(rows)
    if scored.empty:
        return scored
    scored["rs_score"] = percentile_scores(scored["rs_4w"], higher_is_better=True)
    scored["momentum_score"] = percentile_scores(scored["momentum_skip_week"], higher_is_better=True)
    scored["volume_score"] = percentile_scores(scored["volume_ratio"], higher_is_better=True)
    scored["short_rs_score"] = percentile_scores(scored["rs_4w"], higher_is_better=False)
    scored["short_momentum_score"] = percentile_scores(scored["momentum_skip_week"], higher_is_better=False)
    scored["short_structure_score"] = 100 - scored["structure_score"]
    scored["long_composite"] = (
        scored["rs_score"] * 0.25
        + scored["momentum_score"] * 0.20
        + scored["volume_score"] * 0.15
        + scored["structure_score"] * 0.20
        + scored["proximity_score"].fillna(0) * 0.10
        + scored["sector_alignment_long"] * 0.10
    )
    scored["short_composite"] = (
        scored["short_rs_score"] * 0.25
        + scored["short_momentum_score"] * 0.20
        + scored["volume_score"] * 0.15
        + scored["short_structure_score"] * 0.20
        + scored["proximity_score"].fillna(0) * 0.10
        + scored["sector_alignment_short"] * 0.10
    )
    scored["signal"] = "NEUTRAL"
    long_mask = (scored["long_composite"] >= 65) & (scored["sector_alignment_long"] >= 60) & (scored["volume_ratio"] >= min_volume_ratio)
    short_mask = (scored["short_composite"] >= 65) & (scored["sector_alignment_short"] >= 60) & (scored["volume_ratio"] >= min_volume_ratio)
    scored.loc[long_mask, "signal"] = "LONG"
    scored.loc[short_mask & ~long_mask, "signal"] = "SHORT"
    scored["confidence"] = "Low"
    scored.loc[(scored["signal"] == "LONG") & (scored["long_composite"] >= 80), "confidence"] = "High"
    scored.loc[(scored["signal"] == "LONG") & (scored["long_composite"] < 80), "confidence"] = "Medium"
    scored.loc[(scored["signal"] == "SHORT") & (scored["short_composite"] >= 80), "confidence"] = "High"
    scored.loc[(scored["signal"] == "SHORT") & (scored["short_composite"] < 80), "confidence"] = "Medium"
    scored["composite"] = np.where(scored["signal"] == "SHORT", scored["short_composite"], scored["long_composite"])
    scored["entry_reference"] = scored["close"]
    long_stop = scored["entry_reference"] - 1.5 * scored["atr_14"]
    short_stop = scored["entry_reference"] + 1.5 * scored["atr_14"]
    scored["stop_reference"] = np.where(scored["signal"] == "SHORT", short_stop, long_stop)
    risk_per_share = (scored["entry_reference"] - scored["stop_reference"]).abs()
    scored["risk_per_share"] = risk_per_share
    scored["position_qty_for_risk"] = np.floor(risk_per_trade / risk_per_share.replace(0, np.nan)).fillna(0).astype(int)
    scored = scored.sort_values(["signal", "composite"], ascending=[True, False])
    return scored


def write_doc(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "# Standalone RRG Swing Long/Short Setup",
                "",
                "This is a separate research setup from SectorEdge 10.",
                "",
                "It can emit LONG and SHORT candidates, but it does not change SectorEdge 10 scoring, recommendations, paper trading, or live execution.",
                "",
                "The setup is intended for top-down swing research where the market/sector context can support both long and short trades. It is not a replacement for the current SectorEdge 10 production/paper workflow.",
                "",
                "## Key Decisions",
                "",
                "- Uses 4-week relative strength for swing recency.",
                "- Uses 12-week momentum while skipping the most recent week.",
                "- Requires volume confirmation with volume ratio above 1.10.",
                "- Uses ATR-based stop references.",
                "- Scores proximity to the 21 EMA so extended entries are penalized.",
                "- Lets RRG tail direction override a simple quadrant read.",
                "",
                "## Signal Interpretation",
                "",
                "- LONG requires a supportive sector state, rightward RRG tail, composite score above threshold, and volume confirmation.",
                "- SHORT requires a weakening/lagging sector state, leftward RRG tail, composite score above threshold, and volume confirmation.",
                "- A sector quadrant alone is not enough. Tail direction can downgrade a Leading sector or block fresh shorts in a Lagging sector that is turning right.",
                "- Entry and stop values are references only: entry uses the latest close, and stop uses 1.5x ATR from that reference price.",
                "",
                "## Command",
                "",
                "```powershell",
                ".\\.venv\\Scripts\\python.exe scripts\\generate_rrg_swing_long_short_setup.py --as-of 2026-06-18",
                "```",
                "",
                "## Latest Run",
                "",
                f"- Requested as-of: `{payload.get('requested_as_of')}`",
                f"- As of: `{payload.get('as_of')}`",
                f"- Benchmark: `{payload.get('benchmark_symbol')}`",
                f"- LONG candidates: `{payload.get('long_candidates')}`",
                f"- SHORT candidates: `{payload.get('short_candidates')}`",
                f"- Total scored: `{payload.get('total_scored')}`",
                "",
                "The effective as-of date may be earlier than the requested date when benchmark index history is older than stock history. Current benchmark fallback is `NIFTY50` because NIFTY500 index history is not yet available in the local Angel index table.",
                "",
                "Outputs:",
                "",
                f"- `{payload.get('output_csv')}`",
                f"- `{payload.get('output_json')}`",
                "",
                "## Safety",
                "",
                "Research only. No broker APIs. No production table updates. No SectorEdge 10 changes.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    engine = engine_from_env()
    prices, requested_as_of = load_prices(engine, args.pilot_schema, args.as_of)
    benchmark = load_benchmark(engine, args.benchmark_symbol, requested_as_of)
    effective_as_of = min(requested_as_of, benchmark["date"].max())
    prices = prices[prices["date"] <= effective_as_of].copy()
    benchmark = benchmark[benchmark["date"] <= effective_as_of].copy()
    rrg = sector_rrg(prices, benchmark, effective_as_of)
    scored = score_stocks(prices, benchmark, rrg, effective_as_of, args.min_volume_ratio, args.risk_per_trade)
    output_csv = REPO_ROOT / args.output_csv
    output_json = REPO_ROOT / args.output_json
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    display_columns = [
        "date",
        "symbol",
        "signal",
        "confidence",
        "composite",
        "sector",
        "sector_quadrant",
        "sector_tail",
        "rs_4w",
        "momentum_skip_week",
        "volume_ratio",
        "structure_score",
        "proximity_score",
        "entry_reference",
        "stop_reference",
        "risk_per_share",
        "position_qty_for_risk",
    ]
    if not scored.empty:
        scored[display_columns].to_csv(output_csv, index=False)
    else:
        pd.DataFrame(columns=display_columns).to_csv(output_csv, index=False)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "standalone_rrg_swing_long_short_setup",
        "requested_as_of": requested_as_of.isoformat(),
        "as_of": effective_as_of.isoformat(),
        "benchmark_symbol": args.benchmark_symbol,
        "production_strategy_changed": False,
        "sectoredge10_changed": False,
        "broker_apis_connected": False,
        "orders_placed": False,
        "sectors": list(rrg.values()),
        "total_scored": int(len(scored)),
        "long_candidates": int((scored["signal"] == "LONG").sum()) if not scored.empty else 0,
        "short_candidates": int((scored["signal"] == "SHORT").sum()) if not scored.empty else 0,
        "output_csv": str(output_csv),
        "output_json": str(output_json),
    }
    output_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_doc(REPO_ROOT / "docs" / "RRG_SWING_LONG_SHORT_SETUP.md", payload)
    print(json.dumps({key: payload[key] for key in ["as_of", "total_scored", "long_candidates", "short_candidates"]}, indent=2))
    print(f"Wrote {output_csv}")
    print(f"Wrote {output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
