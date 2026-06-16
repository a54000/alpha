#!/usr/bin/env python3
"""Deeper validation for the research-only 1M/3M sector rank experiment."""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = REPO_ROOT / "results" / "sector_1m3m_rank_experiment"
OUTPUT_DIR = REPO_ROOT / "results" / "sector_1m3m_rank_validation"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate promoted 1M/3M sector rank experiment.")
    parser.add_argument("--input-dir", type=Path, default=INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    return parser.parse_args()


def to_numeric(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for column in columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def load_inputs(input_dir: Path) -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summary = json.loads((input_dir / "sector_1m3m_rank_results.json").read_text(encoding="utf-8"))
    equity = pd.read_csv(input_dir / "sector_1m3m_equity.csv")
    trades = pd.read_csv(input_dir / "sector_1m3m_trades.csv")
    recommendations = pd.read_csv(input_dir / "sector_1m3m_recommendations.csv")
    overlap = pd.read_csv(input_dir / "sector_1m3m_recommendation_overlap.csv")

    equity["date"] = pd.to_datetime(equity["date"])
    trades["entry_date"] = pd.to_datetime(trades["entry_date"])
    trades["exit_date"] = pd.to_datetime(trades["exit_date"])
    recommendations["date"] = pd.to_datetime(recommendations["date"])
    to_numeric(equity, ["equity", "cash", "position_count"])
    to_numeric(
        trades,
        ["entry_value", "exit_value", "gross_pnl", "net_pnl", "net_return_pct", "charges", "holding_days", "trade_id"],
    )
    to_numeric(recommendations, ["rank", "score", "sector_points", "sector_rank_used"])
    to_numeric(overlap, ["baseline_count", "experiment_count", "overlap_count", "jaccard_overlap"])
    return summary, equity, trades, recommendations, overlap


def month_returns(equity: pd.DataFrame) -> list[dict[str, object]]:
    rows = []
    for variant, frame in equity.groupby("variant"):
        item = frame.sort_values("date").copy()
        item["month"] = item["date"].dt.to_period("M").astype(str)
        for month, group in item.groupby("month", sort=True):
            start = float(group.iloc[0]["equity"])
            end = float(group.iloc[-1]["equity"])
            rows.append(
                {
                    "variant": variant,
                    "month": month,
                    "start_date": group.iloc[0]["date"].date().isoformat(),
                    "end_date": group.iloc[-1]["date"].date().isoformat(),
                    "start_equity": start,
                    "end_equity": end,
                    "return_pct": end / start - 1 if start else None,
                }
            )
    return rows


def rolling_window_returns(monthly: pd.DataFrame, window: int = 6) -> list[dict[str, object]]:
    rows = []
    for variant, frame in monthly.groupby("variant"):
        item = frame.sort_values("month").reset_index(drop=True)
        for index in range(0, len(item) - window + 1):
            group = item.iloc[index : index + window]
            start = float(group.iloc[0]["start_equity"])
            end = float(group.iloc[-1]["end_equity"])
            rows.append(
                {
                    "variant": variant,
                    "window": f"{group.iloc[0]['month']} to {group.iloc[-1]['month']}",
                    "months": window,
                    "return_pct": end / start - 1 if start else None,
                }
            )
    return rows


def sector_stats(trades: pd.DataFrame) -> list[dict[str, object]]:
    rows = []
    for (variant, sector), group in trades.groupby(["strategy", "sector"], dropna=False):
        pnl = group["net_pnl"].sum()
        rows.append(
            {
                "variant": variant,
                "sector": sector,
                "trades": int(len(group)),
                "net_pnl": float(pnl),
                "avg_return": float(group["net_return_pct"].mean()),
                "win_rate": float((group["net_pnl"] > 0).mean()),
                "gross_exposure": float(group["entry_value"].sum()),
            }
        )
    totals = pd.DataFrame(rows).groupby("variant")["net_pnl"].sum().to_dict() if rows else {}
    for row in rows:
        total = totals.get(row["variant"]) or 0
        row["pnl_share"] = row["net_pnl"] / total if total else None
    return rows


def trade_pair_deltas(trades: pd.DataFrame) -> list[dict[str, object]]:
    base = trades[trades["strategy"] == "baseline_3m_rank"].copy()
    exp = trades[trades["strategy"] == "sector_1m3m_40_60_rank"].copy()
    join_cols = ["symbol", "entry_date"]
    merged = base.merge(
        exp,
        on=join_cols,
        how="outer",
        suffixes=("_baseline", "_1m3m"),
        indicator=True,
    )
    rows = []
    for data in merged.to_dict(orient="records"):
        baseline_pnl = data.get("net_pnl_baseline")
        exp_pnl = data.get("net_pnl_1m3m")
        rows.append(
            {
                "symbol": data.get("symbol"),
                "entry_date": data.get("entry_date").date().isoformat() if pd.notna(data.get("entry_date")) else None,
                "match_type": data.get("_merge"),
                "baseline_net_pnl": None if pd.isna(baseline_pnl) else float(baseline_pnl),
                "experiment_net_pnl": None if pd.isna(exp_pnl) else float(exp_pnl),
                "pnl_delta": 0.0
                if pd.isna(baseline_pnl) and pd.isna(exp_pnl)
                else (0.0 if pd.isna(exp_pnl) else float(exp_pnl)) - (0.0 if pd.isna(baseline_pnl) else float(baseline_pnl)),
                "sector_baseline": data.get("sector_baseline"),
                "sector_1m3m": data.get("sector_1m3m"),
            }
        )
    return rows


def drawdown_events(equity: pd.DataFrame) -> list[dict[str, object]]:
    rows = []
    for variant, frame in equity.groupby("variant"):
        item = frame.sort_values("date").copy()
        item["peak"] = item["equity"].cummax()
        item["drawdown"] = item["equity"] / item["peak"] - 1
        worst = item.nsmallest(10, "drawdown")
        for row in worst.itertuples(index=False):
            rows.append(
                {
                    "variant": variant,
                    "date": row.date.date().isoformat(),
                    "equity": float(row.equity),
                    "drawdown": float(row.drawdown),
                    "cash_pct": float(row.cash / row.equity) if row.equity else None,
                    "position_count": int(row.position_count),
                }
            )
    return rows


def aggregate_validation(
    summary: dict[str, object],
    monthly: pd.DataFrame,
    rolling: pd.DataFrame,
    sector: pd.DataFrame,
    pairs: pd.DataFrame,
    overlap: pd.DataFrame,
) -> dict[str, object]:
    variants = summary["variants"]
    base = variants["baseline_3m_rank"]["metrics"]
    exp = variants["sector_1m3m_40_60_rank"]["metrics"]
    monthly_summary = {}
    for variant, frame in monthly.groupby("variant"):
        monthly_summary[variant] = {
            "positive_month_rate": float((frame["return_pct"] > 0).mean()),
            "avg_monthly_return": float(frame["return_pct"].mean()),
            "worst_month": float(frame["return_pct"].min()),
            "best_month": float(frame["return_pct"].max()),
        }
    rolling_summary = {}
    for variant, frame in rolling.groupby("variant"):
        rolling_summary[variant] = {
            "positive_6m_window_rate": float((frame["return_pct"] > 0).mean()),
            "worst_6m_window": float(frame["return_pct"].min()),
            "best_6m_window": float(frame["return_pct"].max()),
        }
    pair_summary = {
        "matched_trades": int((pairs["match_type"] == "both").sum()),
        "baseline_only_trades": int((pairs["match_type"] == "left_only").sum()),
        "experiment_only_trades": int((pairs["match_type"] == "right_only").sum()),
        "net_pnl_delta": float(pairs["pnl_delta"].sum()),
        "top_positive_trade_delta": pairs.sort_values("pnl_delta", ascending=False).head(10).to_dict(orient="records"),
        "top_negative_trade_delta": pairs.sort_values("pnl_delta", ascending=True).head(10).to_dict(orient="records"),
    }
    sector_top = {}
    for variant, frame in sector.groupby("variant"):
        sector_top[variant] = {
            "top_pnl_sectors": frame.sort_values("net_pnl", ascending=False).head(5).to_dict(orient="records"),
            "worst_pnl_sectors": frame.sort_values("net_pnl", ascending=True).head(5).to_dict(orient="records"),
            "top_sector_pnl_share": float(frame.sort_values("net_pnl", ascending=False).iloc[0]["pnl_share"]) if not frame.empty else None,
        }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metric_delta": {
            "cagr": exp["cagr"] - base["cagr"],
            "total_return": exp["total_return"] - base["total_return"],
            "max_drawdown": exp["max_drawdown"] - base["max_drawdown"],
            "sharpe_ratio": exp["sharpe_ratio"] - base["sharpe_ratio"],
            "sortino_ratio": exp["sortino_ratio"] - base["sortino_ratio"],
            "profit_factor": exp["profit_factor"] - base["profit_factor"],
        },
        "monthly_summary": monthly_summary,
        "rolling_6m_summary": rolling_summary,
        "trade_pair_summary": pair_summary,
        "sector_summary": sector_top,
        "overlap_summary": {
            "avg_jaccard_overlap": float(overlap["jaccard_overlap"].mean()),
            "min_jaccard_overlap": float(overlap["jaccard_overlap"].min()),
            "dates_below_80pct_overlap": int((overlap["jaccard_overlap"] < 0.80).sum()),
        },
        "validation_verdict": (
            "PROMOTE_TO_PARAMETER_STABILITY_TEST"
            if exp["cagr"] > base["cagr"]
            and exp["sharpe_ratio"] > base["sharpe_ratio"]
            and exp["max_drawdown"] > base["max_drawdown"]
            and monthly_summary["sector_1m3m_40_60_rank"]["positive_month_rate"]
            >= monthly_summary["baseline_3m_rank"]["positive_month_rate"]
            else "HOLD_FOR_MORE_REVIEW"
        ),
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


def pct(value: object) -> str:
    if value is None:
        return "n/a"
    return f"{float(value) * 100:.2f}%"


def num(value: object) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.2f}"


def render_report(validation: dict[str, object]) -> str:
    monthly = validation["monthly_summary"]
    rolling = validation["rolling_6m_summary"]
    delta = validation["metric_delta"]
    overlap = validation["overlap_summary"]
    lines = [
        "# Sector 1M/3M Rank Deeper Validation",
        "",
        "Research-only validation. No production scoring, recommendation, strategy, or database changes were made.",
        "",
        "## Metric Confirmation",
        "",
        f"- CAGR delta: {pct(delta['cagr'])}",
        f"- Max drawdown improvement: {pct(delta['max_drawdown'])}",
        f"- Sharpe delta: {num(delta['sharpe_ratio'])}",
        f"- Profit factor delta: {num(delta['profit_factor'])}",
        "",
        "## Monthly Stability",
        "",
        "| Variant | Positive Month Rate | Avg Monthly Return | Worst Month | Best Month |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for variant, row in monthly.items():
        lines.append(
            f"| {variant} | {pct(row['positive_month_rate'])} | {pct(row['avg_monthly_return'])} | {pct(row['worst_month'])} | {pct(row['best_month'])} |"
        )
    lines.extend(["", "## Rolling 6-Month Stability", "", "| Variant | Positive 6M Windows | Worst 6M | Best 6M |", "| --- | ---: | ---: | ---: |"])
    for variant, row in rolling.items():
        lines.append(f"| {variant} | {pct(row['positive_6m_window_rate'])} | {pct(row['worst_6m_window'])} | {pct(row['best_6m_window'])} |")
    lines.extend(
        [
            "",
            "## Recommendation Churn",
            "",
            f"- Average daily Jaccard overlap: {pct(overlap['avg_jaccard_overlap'])}",
            f"- Minimum daily Jaccard overlap: {pct(overlap['min_jaccard_overlap'])}",
            f"- Dates below 80% overlap: {overlap['dates_below_80pct_overlap']}",
            "",
            "## Trade Delta",
            "",
            f"- Matched trades: {validation['trade_pair_summary']['matched_trades']}",
            f"- Baseline-only trades: {validation['trade_pair_summary']['baseline_only_trades']}",
            f"- 1M/3M-only trades: {validation['trade_pair_summary']['experiment_only_trades']}",
            f"- Net PnL delta: {validation['trade_pair_summary']['net_pnl_delta']:,.0f}",
            "",
            "## Verdict",
            "",
            validation["validation_verdict"],
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    summary, equity, trades, recommendations, overlap = load_inputs(args.input_dir)
    monthly_rows = month_returns(equity)
    monthly = pd.DataFrame(monthly_rows)
    rolling_rows = rolling_window_returns(monthly)
    rolling = pd.DataFrame(rolling_rows)
    sector_rows = sector_stats(trades)
    sector = pd.DataFrame(sector_rows)
    pair_rows = trade_pair_deltas(trades)
    pairs = pd.DataFrame(pair_rows)
    drawdowns = drawdown_events(equity)
    validation = aggregate_validation(summary, monthly, rolling, sector, pairs, overlap)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "sector_1m3m_deeper_validation.json").write_text(json.dumps(validation, indent=2, default=str), encoding="utf-8")
    (args.output_dir / "SECTOR_1M3M_DEEPER_VALIDATION.md").write_text(render_report(validation), encoding="utf-8")
    write_csv(args.output_dir / "sector_1m3m_monthly_returns.csv", monthly_rows)
    write_csv(args.output_dir / "sector_1m3m_rolling_6m_returns.csv", rolling_rows)
    write_csv(args.output_dir / "sector_1m3m_sector_stats.csv", sector_rows)
    write_csv(args.output_dir / "sector_1m3m_trade_deltas.csv", pair_rows)
    write_csv(args.output_dir / "sector_1m3m_worst_drawdown_days.csv", drawdowns)
    print(json.dumps(validation, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
