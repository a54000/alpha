#!/usr/bin/env python3
"""Analyze common patterns in losing Rolling 10 trades.

Research-only diagnostic. Reads completed trade CSVs plus pilot market data,
annotates trades with signal-date breadth/features and entry-day VWAP context,
then compares losing trades against winners.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import statistics
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

OUTPUT_DIR = REPO_ROOT / "results" / "losing_trade_patterns"
DEFAULT_TRADES = REPO_ROOT / "results" / "sector_1m3m_parameter_neighborhood" / "sector_1m3m_parameter_neighborhood_trades.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze common patterns in losing Rolling 10 trades.")
    parser.add_argument("--trades-csv", type=Path, default=DEFAULT_TRADES)
    parser.add_argument("--variant", default="sector_1m3m_40_60_rank")
    parser.add_argument("--pilot-schema", default="pilot_phase2a")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    return parser.parse_args()


def pct(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def mean(values: list[float]) -> float | None:
    return statistics.mean(values) if values else None


def median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * q)))
    return ordered[idx]


def bucket(value: float | None, low: float, high: float) -> str:
    if value is None or pd.isna(value):
        return "unknown"
    if value < low:
        return "low"
    if value < high:
        return "medium"
    return "high"


def ema_extension_bucket(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "unknown"
    if value < 0:
        return "below_ema200"
    if value <= 0.05:
        return "0_to_5_pct"
    if value <= 0.15:
        return "5_to_15_pct"
    return "over_15_pct"


def rsi_bucket(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "unknown"
    if value < 45:
        return "weak_below_45"
    if value < 55:
        return "neutral_45_55"
    if value <= 70:
        return "momentum_55_70"
    return "extended_over_70"


def adx_bucket(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "unknown"
    if value < 20:
        return "weak_lt_20"
    if value < 30:
        return "trend_20_30"
    return "strong_gt_30"


def load_trades(path: Path, variant: str) -> pd.DataFrame:
    trades = pd.read_csv(path)
    trades = trades[trades["strategy"] == variant].copy()
    for column in ["entry_date", "exit_date"]:
        trades[column] = pd.to_datetime(trades[column]).dt.date
    for column in ["entry_price", "exit_price", "entry_value", "exit_value", "net_pnl", "net_return_pct", "gross_return_pct"]:
        trades[column] = pd.to_numeric(trades[column], errors="coerce")
    return trades.sort_values(["entry_date", "trade_id"]).reset_index(drop=True)


def load_features(engine, schema: str, start_date: date, end_date: date) -> pd.DataFrame:
    query = text(
        f"""
        SELECT symbol, date, sector, close, volume, ema_200, ema200_extension,
               prior_20d_return, adx_14, adx_prev, sector_rank_3m
        FROM {schema}.features_daily
        WHERE date BETWEEN :start_date AND :end_date
        ORDER BY symbol ASC, date ASC
        """
    )
    frame = pd.read_sql_query(query, engine, params={"start_date": start_date, "end_date": end_date})
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    for column in ["close", "volume", "ema_200", "ema200_extension", "prior_20d_return", "adx_14", "adx_prev", "sector_rank_3m"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["daily_return"] = frame.groupby("symbol")["close"].pct_change()
    delta = frame.groupby("symbol")["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.groupby(frame["symbol"]).transform(lambda s: s.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean())
    avg_loss = loss.groupby(frame["symbol"]).transform(lambda s: s.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean())
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    frame["rsi_14"] = 100 - (100 / (1 + rs))
    frame.loc[(avg_loss == 0) & (avg_gain > 0), "rsi_14"] = 100
    frame.loc[(avg_loss == 0) & (avg_gain == 0), "rsi_14"] = 50
    return frame


def load_signal_dates(engine, schema: str, trades: pd.DataFrame) -> dict[tuple[str, date], date | None]:
    symbols = sorted(trades["symbol"].astype(str).unique().tolist())
    start_date = min(trades["entry_date"])
    end_date = max(trades["entry_date"])
    query = text(
        f"""
        SELECT symbol, date
        FROM {schema}.daily_bars_clean
        WHERE symbol = ANY(:symbols)
          AND date BETWEEN :start_date - INTERVAL '10 days' AND :end_date
        ORDER BY symbol ASC, date ASC
        """
    )
    rows = pd.read_sql_query(query, engine, params={"symbols": symbols, "start_date": start_date, "end_date": end_date})
    rows["date"] = pd.to_datetime(rows["date"]).dt.date
    by_symbol = {symbol: sorted(group["date"].tolist()) for symbol, group in rows.groupby("symbol")}
    mapping: dict[tuple[str, date], date | None] = {}
    for trade in trades.itertuples(index=False):
        dates = by_symbol.get(str(trade.symbol), [])
        prior = [item for item in dates if item < trade.entry_date]
        mapping[(str(trade.symbol), trade.entry_date)] = prior[-1] if prior else None
    return mapping


def load_breadth(features: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = features.copy()
    frame["above_ema200"] = frame["close"] > frame["ema_200"]
    frame["positive_20d"] = frame["prior_20d_return"] > 0
    frame["adx20"] = frame["adx_14"] >= 20
    market = (
        frame.groupby("date")
        .agg(
            market_total=("symbol", "count"),
            market_above_ema200_pct=("above_ema200", "mean"),
            market_positive_20d_pct=("positive_20d", "mean"),
            market_adx20_pct=("adx20", "mean"),
        )
        .reset_index()
    )
    sector = (
        frame.groupby(["date", "sector"])
        .agg(
            sector_total=("symbol", "count"),
            sector_above_ema200_pct=("above_ema200", "mean"),
            sector_positive_20d_pct=("positive_20d", "mean"),
            sector_adx20_pct=("adx20", "mean"),
            sector_avg_ema200_extension=("ema200_extension", "mean"),
            sector_avg_rsi_14=("rsi_14", "mean"),
        )
        .reset_index()
    )
    return market, sector


def load_entry_vwap(engine, trades: pd.DataFrame) -> pd.DataFrame:
    pairs = trades[["symbol", "entry_date"]].drop_duplicates().copy()
    if pairs.empty:
        return pd.DataFrame(columns=["symbol", "entry_date", "entry_day_vwap"])
    symbols = pairs["symbol"].astype(str).unique().tolist()
    start_date = min(pairs["entry_date"])
    end_date = max(pairs["entry_date"])
    query = text(
        """
        SELECT symbol,
               datetime::date AS entry_date,
               SUM(((high + low + close) / 3.0) * volume) / NULLIF(SUM(volume), 0) AS entry_day_vwap
        FROM ohlcv_15min
        WHERE symbol = ANY(:symbols)
          AND datetime::date BETWEEN :start_date AND :end_date
        GROUP BY symbol, datetime::date
        """
    )
    frame = pd.read_sql_query(query, engine, params={"symbols": symbols, "start_date": start_date, "end_date": end_date})
    frame["entry_date"] = pd.to_datetime(frame["entry_date"]).dt.date
    frame["entry_day_vwap"] = pd.to_numeric(frame["entry_day_vwap"], errors="coerce")
    return frame


def enrich_trades(trades: pd.DataFrame, features: pd.DataFrame, signal_dates: dict[tuple[str, date], date | None], market: pd.DataFrame, sector: pd.DataFrame, vwap: pd.DataFrame) -> pd.DataFrame:
    enriched = trades.copy()
    enriched["signal_date"] = [signal_dates.get((str(row.symbol), row.entry_date)) for row in enriched.itertuples(index=False)]
    signal_features = features.rename(columns={"date": "signal_date"}).copy()
    keep = [
        "symbol",
        "signal_date",
        "close",
        "ema_200",
        "ema200_extension",
        "prior_20d_return",
        "adx_14",
        "adx_prev",
        "sector_rank_3m",
        "rsi_14",
        "daily_return",
    ]
    enriched = enriched.merge(signal_features[keep], on=["symbol", "signal_date"], how="left")
    enriched = enriched.merge(market.rename(columns={"date": "signal_date"}), on="signal_date", how="left")
    enriched = enriched.merge(sector.rename(columns={"date": "signal_date"}), on=["signal_date", "sector"], how="left")
    enriched = enriched.merge(vwap, on=["symbol", "entry_date"], how="left")
    enriched["entry_vs_vwap_pct"] = enriched["entry_price"] / enriched["entry_day_vwap"] - 1.0
    enriched["loser"] = enriched["net_pnl"] < 0
    enriched["market_breadth_bucket"] = enriched["market_positive_20d_pct"].apply(lambda value: bucket(value, 0.40, 0.60))
    enriched["sector_breadth_bucket"] = enriched["sector_positive_20d_pct"].apply(lambda value: bucket(value, 0.40, 0.60))
    enriched["adx_bucket"] = enriched["adx_14"].apply(adx_bucket)
    enriched["rsi_bucket"] = enriched["rsi_14"].apply(rsi_bucket)
    enriched["ema200_extension_bucket"] = enriched["ema200_extension"].apply(ema_extension_bucket)
    enriched["vwap_bucket"] = enriched["entry_vs_vwap_pct"].apply(lambda value: "unknown" if pd.isna(value) else ("below_vwap" if value < 0 else ("0_to_1pct_above" if value <= 0.01 else "over_1pct_above")))
    enriched["overextended_flag"] = enriched["ema200_extension"] > 0.15
    enriched["weak_sector_breadth_flag"] = enriched["sector_positive_20d_pct"] < 0.40
    enriched["weak_market_breadth_flag"] = enriched["market_positive_20d_pct"] < 0.40
    enriched["weak_adx_flag"] = enriched["adx_14"] < 20
    enriched["extended_rsi_flag"] = enriched["rsi_14"] > 70
    enriched["entry_above_vwap_1pct_flag"] = enriched["entry_vs_vwap_pct"] > 0.01
    return enriched


def group_summary(frame: pd.DataFrame, key: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for name, group in frame.groupby(key, dropna=False):
        returns = group["net_return_pct"].dropna().astype(float).tolist()
        pnls = group["net_pnl"].dropna().astype(float).tolist()
        rows.append(
            {
                "group_by": key,
                "bucket": "unknown" if pd.isna(name) else str(name),
                "trade_count": int(len(group)),
                "loser_count": int(group["loser"].sum()),
                "loser_rate": float(group["loser"].mean()) if len(group) else None,
                "avg_return": mean(returns),
                "median_return": median(returns),
                "total_net_pnl": sum(pnls),
                "avg_net_pnl": mean(pnls),
            }
        )
    return sorted(rows, key=lambda row: (str(row["group_by"]), str(row["bucket"])))


def cohort_summary(frame: pd.DataFrame, label: str) -> dict[str, object]:
    returns = frame["net_return_pct"].dropna().astype(float).tolist()
    pnls = frame["net_pnl"].dropna().astype(float).tolist()
    return {
        "cohort": label,
        "trade_count": int(len(frame)),
        "avg_return": mean(returns),
        "median_return": median(returns),
        "p25_return": quantile(returns, 0.25),
        "p75_return": quantile(returns, 0.75),
        "total_net_pnl": sum(pnls),
        "avg_net_pnl": mean(pnls),
        "avg_adx_14": mean(frame["adx_14"].dropna().astype(float).tolist()),
        "avg_rsi_14": mean(frame["rsi_14"].dropna().astype(float).tolist()),
        "avg_ema200_extension": mean(frame["ema200_extension"].dropna().astype(float).tolist()),
        "avg_prior_20d_return": mean(frame["prior_20d_return"].dropna().astype(float).tolist()),
        "avg_entry_vs_vwap_pct": mean(frame["entry_vs_vwap_pct"].dropna().astype(float).tolist()),
        "avg_market_positive_20d_pct": mean(frame["market_positive_20d_pct"].dropna().astype(float).tolist()),
        "avg_sector_positive_20d_pct": mean(frame["sector_positive_20d_pct"].dropna().astype(float).tolist()),
        "overextended_share": float(frame["overextended_flag"].mean()) if len(frame) else None,
        "weak_sector_breadth_share": float(frame["weak_sector_breadth_flag"].mean()) if len(frame) else None,
        "weak_market_breadth_share": float(frame["weak_market_breadth_flag"].mean()) if len(frame) else None,
        "weak_adx_share": float(frame["weak_adx_flag"].mean()) if len(frame) else None,
        "extended_rsi_share": float(frame["extended_rsi_flag"].mean()) if len(frame) else None,
        "entry_above_vwap_1pct_share": float(frame["entry_above_vwap_1pct_flag"].mean()) if len(frame) else None,
    }


def common_pattern_summary(frame: pd.DataFrame) -> list[dict[str, object]]:
    flags = [
        "weak_sector_breadth_flag",
        "weak_market_breadth_flag",
        "weak_adx_flag",
        "overextended_flag",
        "extended_rsi_flag",
        "entry_above_vwap_1pct_flag",
    ]
    rows: list[dict[str, object]] = []
    for flag in flags:
        yes = frame[frame[flag]]
        no = frame[~frame[flag]]
        rows.append(
            {
                "pattern": flag,
                "trade_count": int(len(yes)),
                "loser_count": int(yes["loser"].sum()),
                "loser_rate": float(yes["loser"].mean()) if len(yes) else None,
                "avg_return": mean(yes["net_return_pct"].dropna().astype(float).tolist()),
                "total_net_pnl": float(yes["net_pnl"].sum()) if len(yes) else 0.0,
                "non_pattern_loser_rate": float(no["loser"].mean()) if len(no) else None,
                "non_pattern_avg_return": mean(no["net_return_pct"].dropna().astype(float).tolist()),
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def fmt_pct(value: object) -> str:
    return "n/a" if value is None or pd.isna(value) else f"{float(value) * 100:.2f}%"


def fmt_num(value: object) -> str:
    return "n/a" if value is None or pd.isna(value) else f"{float(value):.2f}"


def render_report(payload: dict[str, object], cohort_rows: list[dict[str, object]], pattern_rows: list[dict[str, object]], bucket_rows: list[dict[str, object]]) -> str:
    lines = [
        "# Losing Trade Pattern Analysis",
        "",
        "Research-only diagnostic. No strategy, scoring, recommendation, portfolio, or database logic was changed.",
        "",
        f"- Variant analyzed: `{payload['parameters']['variant']}`",
        f"- Trades analyzed: {payload['summary']['trade_count']}",
        f"- Losing trades: {payload['summary']['loser_count']} ({fmt_pct(payload['summary']['loser_rate'])})",
        "",
        "## Losers Versus Winners",
        "",
        "| Cohort | Trades | Avg Return | Median Return | Avg ADX | Avg RSI14 | Avg EMA200 Ext | Avg Prior 20D | Avg Sector Breadth | Avg Market Breadth | Avg Entry vs VWAP |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in cohort_rows:
        lines.append(
            f"| {row['cohort']} | {row['trade_count']} | {fmt_pct(row['avg_return'])} | {fmt_pct(row['median_return'])} | "
            f"{fmt_num(row['avg_adx_14'])} | {fmt_num(row['avg_rsi_14'])} | {fmt_pct(row['avg_ema200_extension'])} | "
            f"{fmt_pct(row['avg_prior_20d_return'])} | {fmt_pct(row['avg_sector_positive_20d_pct'])} | "
            f"{fmt_pct(row['avg_market_positive_20d_pct'])} | {fmt_pct(row['avg_entry_vs_vwap_pct'])} |"
        )
    lines.extend(
        [
            "",
            "## Candidate Common Patterns",
            "",
            "| Pattern | Trades | Loser Rate | Avg Return | Total Net PnL | Non-Pattern Loser Rate | Non-Pattern Avg Return |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in pattern_rows:
        lines.append(
            f"| {row['pattern']} | {row['trade_count']} | {fmt_pct(row['loser_rate'])} | {fmt_pct(row['avg_return'])} | "
            f"{fmt_num(row['total_net_pnl'])} | {fmt_pct(row['non_pattern_loser_rate'])} | {fmt_pct(row['non_pattern_avg_return'])} |"
        )
    lines.extend(
        [
            "",
            "## Bucket Evidence",
            "",
            "| Bucket Type | Bucket | Trades | Loser Rate | Avg Return | Median Return | Total Net PnL |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in bucket_rows:
        lines.append(
            f"| {row['group_by']} | {row['bucket']} | {row['trade_count']} | {fmt_pct(row['loser_rate'])} | "
            f"{fmt_pct(row['avg_return'])} | {fmt_pct(row['median_return'])} | {fmt_num(row['total_net_pnl'])} |"
        )
    lines.extend(["", "## Interpretation", "", str(payload["interpretation"])])
    return "\n".join(lines) + "\n"


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    args = parse_args()
    angel_url = os.environ.get("ANGEL_DATABASE_URL")
    if not angel_url:
        raise RuntimeError("ANGEL_DATABASE_URL is required.")
    engine = create_engine(angel_url, future=True, pool_pre_ping=True)

    trades = load_trades(args.trades_csv, args.variant)
    if trades.empty:
        raise RuntimeError(f"No trades found for variant {args.variant} in {args.trades_csv}")
    start_date = min(trades["entry_date"])
    end_date = max(trades["exit_date"])
    features = load_features(engine, args.pilot_schema, start_date, end_date)
    signal_dates = load_signal_dates(engine, args.pilot_schema, trades)
    market, sector = load_breadth(features)
    vwap = load_entry_vwap(engine, trades)
    enriched = enrich_trades(trades, features, signal_dates, market, sector, vwap)

    losers = enriched[enriched["loser"]].copy()
    winners = enriched[~enriched["loser"]].copy()
    cohort_rows = [
        cohort_summary(enriched, "all_trades"),
        cohort_summary(losers, "losers"),
        cohort_summary(winners, "winners"),
    ]
    bucket_rows: list[dict[str, object]] = []
    for key in ["sector_breadth_bucket", "market_breadth_bucket", "adx_bucket", "rsi_bucket", "ema200_extension_bucket", "vwap_bucket"]:
        bucket_rows.extend(group_summary(enriched, key))
    pattern_rows = common_pattern_summary(enriched)
    top_losers = enriched.sort_values("net_pnl").head(30).to_dict("records")

    strongest_patterns = sorted(
        [row for row in pattern_rows if row["trade_count"]],
        key=lambda row: ((row["loser_rate"] or 0) - (row["non_pattern_loser_rate"] or 0), -(row["avg_return"] or 0)),
        reverse=True,
    )
    interpretation = (
        "The strongest loser signature is not a single indicator failure; compare the pattern table for elevated loser-rate clusters. "
        "Patterns with loser rate above the non-pattern loser rate and negative average return are the best candidates for future sizing or gating experiments."
    )
    if strongest_patterns:
        top = strongest_patterns[0]
        interpretation = (
            f"Top separating pattern: `{top['pattern']}`. It has loser rate {fmt_pct(top['loser_rate'])} versus "
            f"{fmt_pct(top['non_pattern_loser_rate'])} outside the pattern, with average return {fmt_pct(top['avg_return'])}. "
            "This is diagnostic evidence only; it should become a controlled sizing/gating experiment before any strategy change."
        )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "parameters": {
            "variant": args.variant,
            "trades_csv": str(args.trades_csv),
            "pilot_schema": args.pilot_schema,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "indicator_timing": "ADX/RSI/EMA/breadth use inferred signal_date, the previous trading session before entry. VWAP uses entry-day 15-minute candles.",
        },
        "summary": {
            "trade_count": int(len(enriched)),
            "loser_count": int(len(losers)),
            "winner_count": int(len(winners)),
            "loser_rate": float(len(losers) / len(enriched)),
            "total_net_pnl": float(enriched["net_pnl"].sum()),
            "loser_total_net_pnl": float(losers["net_pnl"].sum()),
            "winner_total_net_pnl": float(winners["net_pnl"].sum()),
        },
        "cohorts": cohort_rows,
        "patterns": pattern_rows,
        "strongest_patterns": strongest_patterns[:5],
        "constraints": {
            "database_modified": False,
            "production_scoring_changed": False,
            "production_recommendations_changed": False,
            "strategy_rules_changed": False,
        },
        "interpretation": interpretation,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "losing_trade_pattern_summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    (args.output_dir / "LOSING_TRADE_PATTERN_ANALYSIS.md").write_text(render_report(payload, cohort_rows, pattern_rows, bucket_rows), encoding="utf-8")
    enriched.to_csv(args.output_dir / "losing_trade_pattern_trades.csv", index=False)
    write_csv(args.output_dir / "losing_trade_pattern_buckets.csv", bucket_rows)
    write_csv(args.output_dir / "losing_trade_pattern_flags.csv", pattern_rows)
    write_csv(args.output_dir / "losing_trade_pattern_top_losers.csv", top_losers)
    print(json.dumps(payload, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
