#!/usr/bin/env python3
"""Analyze Phase 2E trades by price position relative to EMA200.

Analysis only. Does not alter strategy, recommendations, database tables, or
paper trading lifecycle.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


@dataclass(frozen=True)
class SegmentMetrics:
    variant: str
    classification_basis: str
    bucket: str
    trades: int
    winners: int
    losers: int
    win_rate: float | None
    total_pnl: float
    avg_pnl: float | None
    avg_return: float | None
    median_return: float | None
    profit_factor: float | None
    avg_mae: float | None
    avg_mfe: float | None
    avg_ema200_extension: float | None
    selected_trade_share: float | None
    selected_pnl_share: float | None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze Phase 2E trades above/below EMA200.")
    parser.add_argument("--trades-csv", default="reports/phase2e_trade_ledger.csv")
    parser.add_argument("--database-url", default=os.environ.get("ANGEL_DATABASE_URL") or os.environ.get("DATABASE_URL"))
    parser.add_argument("--pilot-schema", default="pilot_phase2a")
    parser.add_argument("--output-json", default="reports/phase5_14_ema200_trade_filter_analysis.json")
    parser.add_argument("--output-csv", default="reports/phase5_14_ema200_trade_filter_trades.csv")
    parser.add_argument("--output-md", default="docs/PHASE5_14_EMA200_TRADE_FILTER_ANALYSIS.md")
    return parser.parse_args(argv)


def read_trades(path: Path) -> pd.DataFrame:
    trades = pd.read_csv(path)
    for column in ["signal_date", "entry_date", "exit_date"]:
        trades[column] = pd.to_datetime(trades[column]).dt.date
    trades["return"] = trades["return"].astype(float)
    trades["pnl"] = trades["pnl"].astype(float)
    return trades


def read_features(engine, schema: str, start: date, end: date, symbols: list[str]) -> pd.DataFrame:
    query = text(
        f"""
        SELECT symbol, date, close, ema_200, ema200_extension
        FROM {schema}.features_daily
        WHERE date BETWEEN :start AND :end
          AND symbol = ANY(:symbols)
        """
    )
    return pd.read_sql_query(query, engine, params={"start": start, "end": end, "symbols": symbols})


def read_bars(engine, schema: str, start: date, end: date, symbols: list[str]) -> pd.DataFrame:
    query = text(
        f"""
        SELECT symbol, date, high, low, close
        FROM {schema}.daily_bars_clean
        WHERE date BETWEEN :start AND :end
          AND symbol = ANY(:symbols)
        """
    )
    return pd.read_sql_query(query, engine, params={"start": start, "end": end, "symbols": symbols})


def add_feature_context(trades: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    features = features.copy()
    features["date"] = pd.to_datetime(features["date"]).dt.date
    signal_features = features.rename(
        columns={
            "date": "signal_date",
            "close": "signal_close",
            "ema_200": "signal_ema_200",
            "ema200_extension": "signal_ema200_extension",
        }
    )
    entry_features = features.rename(
        columns={
            "date": "entry_date",
            "close": "entry_close",
            "ema_200": "entry_ema_200",
            "ema200_extension": "entry_ema200_extension",
        }
    )
    enriched = trades.merge(
        signal_features[["symbol", "signal_date", "signal_close", "signal_ema_200", "signal_ema200_extension"]],
        on=["symbol", "signal_date"],
        how="left",
    )
    enriched = enriched.merge(
        entry_features[["symbol", "entry_date", "entry_close", "entry_ema_200", "entry_ema200_extension"]],
        on=["symbol", "entry_date"],
        how="left",
    )
    enriched["signal_above_ema200"] = (enriched["signal_close"] > enriched["signal_ema_200"]).astype("boolean")
    enriched["entry_above_ema200"] = (enriched["entry_close"] > enriched["entry_ema_200"]).astype("boolean")
    enriched.loc[enriched["signal_close"].isna() | enriched["signal_ema_200"].isna(), "signal_above_ema200"] = pd.NA
    enriched.loc[enriched["entry_close"].isna() | enriched["entry_ema_200"].isna(), "entry_above_ema200"] = pd.NA
    return enriched


def add_mae_mfe(trades: pd.DataFrame, bars: pd.DataFrame) -> pd.DataFrame:
    bars = bars.copy()
    bars["date"] = pd.to_datetime(bars["date"]).dt.date
    grouped = {symbol: frame.sort_values("date") for symbol, frame in bars.groupby("symbol")}
    maes: list[float | None] = []
    mfes: list[float | None] = []
    for row in trades.itertuples(index=False):
        frame = grouped.get(row.symbol)
        if frame is None or row.entry_price <= 0:
            maes.append(None)
            mfes.append(None)
            continue
        window = frame[(frame["date"] >= row.entry_date) & (frame["date"] <= row.exit_date)]
        if window.empty:
            maes.append(None)
            mfes.append(None)
            continue
        maes.append((float(window["low"].min()) / float(row.entry_price)) - 1)
        mfes.append((float(window["high"].max()) / float(row.entry_price)) - 1)
    trades = trades.copy()
    trades["mae"] = maes
    trades["mfe"] = mfes
    return trades


def profit_factor(pnl: pd.Series) -> float | None:
    gross_profit = float(pnl[pnl > 0].sum())
    gross_loss = abs(float(pnl[pnl < 0].sum()))
    if gross_loss == 0:
        return None if gross_profit == 0 else math.inf
    return gross_profit / gross_loss


def metric_for(frame: pd.DataFrame, variant: str, basis: str, bucket: str, total_trades: int, total_pnl: float) -> SegmentMetrics:
    trades = len(frame)
    winners = int((frame["pnl"] > 0).sum())
    losers = int((frame["pnl"] < 0).sum())
    pnl = float(frame["pnl"].sum()) if trades else 0.0
    ext_column = "signal_ema200_extension" if basis == "signal_date" else "entry_ema200_extension"
    return SegmentMetrics(
        variant=variant,
        classification_basis=basis,
        bucket=bucket,
        trades=trades,
        winners=winners,
        losers=losers,
        win_rate=(winners / trades) if trades else None,
        total_pnl=pnl,
        avg_pnl=float(frame["pnl"].mean()) if trades else None,
        avg_return=float(frame["return"].mean()) if trades else None,
        median_return=float(frame["return"].median()) if trades else None,
        profit_factor=profit_factor(frame["pnl"]) if trades else None,
        avg_mae=float(frame["mae"].mean()) if trades else None,
        avg_mfe=float(frame["mfe"].mean()) if trades else None,
        avg_ema200_extension=float(frame[ext_column].mean()) if trades else None,
        selected_trade_share=(trades / total_trades) if total_trades else None,
        selected_pnl_share=(pnl / total_pnl) if total_pnl else None,
    )


def build_metrics(enriched: pd.DataFrame) -> list[SegmentMetrics]:
    metrics: list[SegmentMetrics] = []
    for variant, variant_frame in enriched.groupby("variant"):
        total_trades = len(variant_frame)
        total_pnl = float(variant_frame["pnl"].sum())
        for basis, column in [("signal_date", "signal_above_ema200"), ("entry_date", "entry_above_ema200")]:
            known = variant_frame[variant_frame[column].notna()]
            groups = {
                "above_ema200": known[known[column] == True],
                "below_or_equal_ema200": known[known[column] == False],
                "unknown": variant_frame[variant_frame[column].isna()],
            }
            for bucket, frame in groups.items():
                metrics.append(metric_for(frame, str(variant), basis, bucket, total_trades, total_pnl))
    return metrics


def write_markdown(path: Path, metrics: list[SegmentMetrics], enriched: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    by_key = {(m.variant, m.classification_basis, m.bucket): m for m in metrics}
    variants = sorted(enriched["variant"].unique())
    lines = [
        "# Phase 5.14 EMA200 Trade Filter Analysis",
        "",
        "## Objective",
        "",
        "Analyze whether the five-year Swing V2.1 pilot trades performed better when the stock was above its daily EMA200.",
        "",
        "This is analysis only. No scoring, recommendation, portfolio, or database logic was changed.",
        "",
        "## Method",
        "",
        "- Trade source: `reports/phase2e_trade_ledger.csv`.",
        "- Feature source: `pilot_phase2a.features_daily`.",
        "- Price path source: `pilot_phase2a.daily_bars_clean`.",
        "- Primary classification: signal-date close versus signal-date EMA200.",
        "- Diagnostic classification: entry-date close versus entry-date EMA200.",
        "",
        "Signal-date classification is the actionable version because the strategy enters on the next trading day's open.",
        "",
        "## Results By Signal-Date EMA200",
        "",
    ]
    for variant in variants:
        lines.extend([f"### {variant}", "", "| Bucket | Trades | Win Rate | Avg Return | Median Return | Total PnL | Profit Factor | Avg MAE | Avg MFE | Avg EMA200 Ext |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"])
        for bucket in ["above_ema200", "below_or_equal_ema200", "unknown"]:
            m = by_key[(variant, "signal_date", bucket)]
            lines.append(
                f"| {bucket} | {m.trades} | {fmt_pct(m.win_rate)} | {fmt_pct(m.avg_return)} | {fmt_pct(m.median_return)} | "
                f"{m.total_pnl:,.0f} | {fmt_num(m.profit_factor)} | {fmt_pct(m.avg_mae)} | {fmt_pct(m.avg_mfe)} | {fmt_pct(m.avg_ema200_extension)} |"
            )
        lines.append("")
    lines.extend([
        "## Interpretation",
        "",
        interpretation(metrics),
        "",
        "## Caveats",
        "",
        "- This is a trade cohort analysis, not a full portfolio resimulation with replacement picks.",
        "- Filtering below-EMA200 trades would change cash deployment and may alter portfolio-level CAGR/drawdown.",
        "- Signal-date EMA200 is the correct no-lookahead gate; entry-date classification is diagnostic only.",
        "- Transaction costs are not included in the Phase 2E trade ledger.",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def fmt_pct(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{value * 100:.2f}%"


def fmt_num(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    if math.isinf(value):
        return "inf"
    return f"{value:.2f}"


def interpretation(metrics: list[SegmentMetrics]) -> str:
    top5_above = next((m for m in metrics if m.variant == "top5_weekly" and m.classification_basis == "signal_date" and m.bucket == "above_ema200"), None)
    top5_below = next((m for m in metrics if m.variant == "top5_weekly" and m.classification_basis == "signal_date" and m.bucket == "below_or_equal_ema200"), None)
    if not top5_above or not top5_below:
        return "Insufficient Top 5 Weekly data to make an EMA200 filter call."
    if (top5_above.avg_return or 0) > (top5_below.avg_return or 0) and (top5_above.profit_factor or 0) > (top5_below.profit_factor or 0):
        return "For Top 5 Weekly, above-EMA200 trades show stronger average return and profit factor than below/equal-EMA200 trades. This supports testing an EMA200-positive gate in a V2.2 experiment, but it should be confirmed with a full portfolio resimulation before changing rules."
    if (top5_below.avg_return or 0) > (top5_above.avg_return or 0):
        return "For Top 5 Weekly, below/equal-EMA200 trades do not underperform on average in this cohort analysis. A simple price-above-EMA200 gate is not supported without a full resimulation."
    return "Top 5 Weekly results are mixed. EMA200 position may be useful as a risk/behavior segment, but not yet as a rule change."


def main(argv: list[str] | None = None) -> int:
    load_dotenv(REPO_ROOT / ".env")
    args = parse_args(argv)
    if not args.database_url:
        raise RuntimeError("Database URL is required. Set ANGEL_DATABASE_URL or DATABASE_URL.")

    trades = read_trades(REPO_ROOT / args.trades_csv)
    symbols = sorted(trades["symbol"].unique())
    start = min(trades["signal_date"].min(), trades["entry_date"].min())
    end = trades["exit_date"].max()

    engine = create_engine(args.database_url, future=True)
    features = read_features(engine, args.pilot_schema, start, end, symbols)
    bars = read_bars(engine, args.pilot_schema, start, end, symbols)
    enriched = add_feature_context(trades, features)
    enriched = add_mae_mfe(enriched, bars)
    metrics = build_metrics(enriched)

    output_csv = REPO_ROOT / args.output_csv
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    enriched.to_csv(output_csv, index=False)

    output_json = REPO_ROOT / args.output_json
    output_json.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_on": datetime.utcnow().isoformat() + "Z",
        "mode": "phase5_14_ema200_trade_filter_analysis",
        "inputs": {
            "trades_csv": args.trades_csv,
            "features": f"{args.pilot_schema}.features_daily",
            "bars": f"{args.pilot_schema}.daily_bars_clean",
        },
        "summary": [asdict(metric) for metric in metrics],
    }
    output_json.write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")
    write_markdown(REPO_ROOT / args.output_md, metrics, enriched)

    print(json.dumps({"trades": len(enriched), "metrics": len(metrics), "output_json": str(output_json), "output_csv": str(output_csv)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
