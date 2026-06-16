#!/usr/bin/env python3
"""Analyze 10:30 entries that occur below cumulative VWAP.

Uses the live-safe 10:30 VWAP threshold grid artifacts. No strategy logic or
database state is changed.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = REPO_ROOT / "results" / "entry_1030_vwap_threshold_grid"
OUTPUT_DIR = REPO_ROOT / "results" / "entry_1030_below_vwap_analysis"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze 10:30 below-VWAP entries.")
    parser.add_argument("--input-dir", type=Path, default=INPUT_DIR)
    parser.add_argument("--variant", default="rolling_10_1m3m_entry_1030_baseline")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    return parser.parse_args()


def bucket(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "unknown"
    if value < -0.01:
        return "below_vwap_gt_1pct"
    if value < 0:
        return "below_vwap_0_to_1pct"
    if value <= 0.01:
        return "above_vwap_0_to_1pct"
    return "above_vwap_gt_1pct"


def fy_label(day: pd.Timestamp) -> str:
    start_year = day.year if day.month >= 4 else day.year - 1
    return f"FY{start_year}-{str(start_year + 1)[-2:]}"


def mean(values: list[float]) -> float | None:
    return statistics.mean(values) if values else None


def median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def summarize(group: pd.DataFrame, label: str, group_by: str = "cohort") -> dict[str, object]:
    returns = group["net_return_pct"].dropna().astype(float).tolist()
    pnls = group["net_pnl"].dropna().astype(float).tolist()
    losers = group[group["net_pnl"] < 0]
    return {
        "group_by": group_by,
        "bucket": label,
        "trade_count": int(len(group)),
        "win_rate": float((group["net_pnl"] > 0).mean()) if len(group) else None,
        "loss_rate": float((group["net_pnl"] < 0).mean()) if len(group) else None,
        "avg_return": mean(returns),
        "median_return": median(returns),
        "total_net_pnl": sum(pnls),
        "avg_net_pnl": mean(pnls),
        "worst_return": min(returns) if returns else None,
        "avg_loser_return": mean(losers["net_return_pct"].dropna().astype(float).tolist()),
        "avg_entry_vs_vwap_pct": mean(group["entry_vs_vwap_pct"].dropna().astype(float).tolist()),
    }


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


def render_report(payload: dict[str, object], summary_rows: list[dict[str, object]], fy_rows: list[dict[str, object]]) -> str:
    lines = [
        "# 10:30 Below-VWAP Trade Analysis",
        "",
        "Read-only analysis of the 10:30 entry candidate. VWAP is cumulative intraday VWAP through the 10:30 bar.",
        "",
        f"- Variant: `{payload['parameters']['variant']}`",
        f"- Trades analyzed: {payload['summary']['trade_count']}",
        f"- Below-VWAP trades: {payload['summary']['below_vwap_trade_count']} ({fmt_pct(payload['summary']['below_vwap_trade_share'])})",
        "",
        "## Bucket Summary",
        "",
        "| Bucket | Trades | Win Rate | Avg Return | Median Return | Total Net PnL | Avg Entry vs VWAP | Worst Return |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary_rows:
        lines.append(
            f"| {row['bucket']} | {row['trade_count']} | {fmt_pct(row['win_rate'])} | {fmt_pct(row['avg_return'])} | "
            f"{fmt_pct(row['median_return'])} | {fmt_num(row['total_net_pnl'])} | {fmt_pct(row['avg_entry_vs_vwap_pct'])} | {fmt_pct(row['worst_return'])} |"
        )
    lines.extend(["", "## FY Contribution", "", "| FY | VWAP Side | Trades | Win Rate | Avg Return | Total Net PnL |", "| --- | --- | ---: | ---: | ---: | ---: |"])
    for row in fy_rows:
        lines.append(
            f"| {row['financial_year']} | {row['vwap_side']} | {row['trade_count']} | {fmt_pct(row['win_rate'])} | "
            f"{fmt_pct(row['avg_return'])} | {fmt_num(row['total_net_pnl'])} |"
        )
    lines.extend(["", "## Interpretation", "", str(payload["interpretation"])])
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    trades = pd.read_csv(args.input_dir / "entry_1030_vwap_threshold_grid_trades.csv")
    entries = pd.read_csv(args.input_dir / "entry_1030_vwap_threshold_grid_entries.csv")
    trades = trades[trades["strategy"] == args.variant].copy()
    entries = entries[(entries["variant"] == args.variant) & (entries["status"] == "entered")].copy()
    for frame in [trades, entries]:
        for column in ["entry_date", "symbol"]:
            frame[column] = frame[column].astype(str)
    merged = trades.merge(
        entries[
            [
                "symbol",
                "entry_date",
                "signal_date",
                "rank",
                "score",
                "entry_1030_open",
                "entry_1030_close",
                "cumulative_vwap_to_1030",
                "entry_vs_vwap_pct",
            ]
        ],
        on=["symbol", "entry_date"],
        how="left",
        suffixes=("", "_entry"),
    )
    for column in ["net_pnl", "net_return_pct", "entry_vs_vwap_pct"]:
        merged[column] = pd.to_numeric(merged[column], errors="coerce")
    merged["vwap_bucket"] = merged["entry_vs_vwap_pct"].apply(bucket)
    merged["vwap_side"] = merged["entry_vs_vwap_pct"].apply(lambda value: "below_vwap" if pd.notna(value) and value < 0 else ("above_or_equal_vwap" if pd.notna(value) else "unknown"))
    merged["financial_year"] = pd.to_datetime(merged["entry_date"]).apply(fy_label)

    order = ["below_vwap_gt_1pct", "below_vwap_0_to_1pct", "above_vwap_0_to_1pct", "above_vwap_gt_1pct", "unknown"]
    summary_rows = [summarize(merged[merged["vwap_bucket"] == name], name, "vwap_bucket") for name in order]
    side_rows = [summarize(merged[merged["vwap_side"] == name], name, "vwap_side") for name in ["below_vwap", "above_or_equal_vwap", "unknown"]]
    summary_rows = side_rows + summary_rows

    fy_rows: list[dict[str, object]] = []
    for (fy, side), group in merged.groupby(["financial_year", "vwap_side"]):
        row = summarize(group, side, "financial_year_vwap_side")
        row["financial_year"] = fy
        row["vwap_side"] = side
        fy_rows.append(row)
    fy_rows.sort(key=lambda row: (str(row["financial_year"]), str(row["vwap_side"])))

    below = merged[merged["vwap_side"] == "below_vwap"]
    above = merged[merged["vwap_side"] == "above_or_equal_vwap"]
    interpretation = (
        f"Below-VWAP entries account for {len(below)} of {len(merged)} trades. "
        f"They generated {fmt_num(below['net_pnl'].sum())} net PnL with average return {fmt_pct(below['net_return_pct'].mean())}, "
        f"versus {fmt_num(above['net_pnl'].sum())} and {fmt_pct(above['net_return_pct'].mean())} for above/equal-VWAP entries."
    )
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "parameters": {
            "variant": args.variant,
            "input_dir": str(args.input_dir),
            "vwap_definition": "Cumulative intraday VWAP through 10:30 from 15-minute candles.",
        },
        "summary": {
            "trade_count": int(len(merged)),
            "below_vwap_trade_count": int(len(below)),
            "below_vwap_trade_share": float(len(below) / len(merged)) if len(merged) else None,
            "above_or_equal_vwap_trade_count": int(len(above)),
            "below_vwap_total_net_pnl": float(below["net_pnl"].sum()),
            "above_or_equal_vwap_total_net_pnl": float(above["net_pnl"].sum()),
        },
        "bucket_summary": summary_rows,
        "constraints": {
            "database_modified": False,
            "production_scoring_changed": False,
            "production_recommendations_changed": False,
            "strategy_rules_changed": False,
        },
        "interpretation": interpretation,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "entry_1030_below_vwap_analysis.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    (args.output_dir / "ENTRY_1030_BELOW_VWAP_ANALYSIS.md").write_text(render_report(payload, summary_rows, fy_rows), encoding="utf-8")
    merged.to_csv(args.output_dir / "entry_1030_below_vwap_trades.csv", index=False)
    write_csv(args.output_dir / "entry_1030_below_vwap_bucket_summary.csv", summary_rows)
    write_csv(args.output_dir / "entry_1030_below_vwap_fy_summary.csv", fy_rows)
    print(json.dumps(payload, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
