#!/usr/bin/env python3
"""Audit blast radius of trade-analysis forced-close fix.

Read-only diagnostic. Compares an old report directory with a fixed report
directory and writes reconciliation artifacts under reports/.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit trade-analysis FY reconciliation after open-position split.")
    parser.add_argument("--old-report-dir", required=True)
    parser.add_argument("--fixed-report-dir", required=True)
    parser.add_argument("--output-csv", default="reports/trade_analysis_fix_reconciliation.csv")
    parser.add_argument("--output-md", default="reports/trade_analysis_fix_reconciliation.md")
    return parser.parse_args()


def financial_year(row_date: date) -> str:
    start_year = row_date.year if row_date.month >= 4 else row_date.year - 1
    return f"FY{start_year}-{str(start_year + 1)[-2:]}"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    return pd.read_csv(path)


def trade_counts_by_fy(frame: pd.DataFrame) -> dict[str, int]:
    if frame.empty or "exit_date" not in frame.columns:
        return {}
    item = frame.copy()
    item["exit_date"] = pd.to_datetime(item["exit_date"], errors="coerce")
    item = item[item["exit_date"].notna()]
    item["financial_year"] = item["exit_date"].dt.date.map(financial_year)
    return item.groupby("financial_year").size().astype(int).to_dict()


def open_counts_by_fy(frame: pd.DataFrame) -> dict[str, int]:
    if frame.empty or "mark_date" not in frame.columns:
        return {}
    item = frame.copy()
    item["mark_date"] = pd.to_datetime(item["mark_date"], errors="coerce")
    item = item[item["mark_date"].notna()]
    item["financial_year"] = item["mark_date"].dt.date.map(financial_year)
    return item.groupby("financial_year").size().astype(int).to_dict()


def fy_rows(meta: dict) -> dict[str, dict]:
    return {str(row["financial_year"]): row for row in meta.get("summary", {}).get("financial_year_returns", [])}


def year_end_exposure(equity: pd.DataFrame) -> list[dict[str, object]]:
    if equity.empty:
        return []
    item = equity.copy()
    item["date"] = pd.to_datetime(item["date"], errors="coerce")
    item = item[item["date"].notna()]
    item["financial_year"] = item["date"].dt.date.map(financial_year)
    rows = []
    for fy, group in item.groupby("financial_year"):
        tail = group.sort_values("date").tail(15)
        rows.append(
            {
                "financial_year": fy,
                "window_start": tail.iloc[0]["date"].date().isoformat(),
                "window_end": tail.iloc[-1]["date"].date().isoformat(),
                "max_position_count_last_15_sessions": int(tail["position_count"].max()) if "position_count" in tail else None,
                "end_position_count": int(tail.iloc[-1]["position_count"]) if "position_count" in tail else None,
                "end_cash": float(tail.iloc[-1]["cash"]) if "cash" in tail else None,
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def pct(value: object) -> str:
    try:
        if value is None or pd.isna(value):
            return "n/a"
        return f"{float(value) * 100:.2f}%"
    except (TypeError, ValueError):
        return "n/a"


def money(value: object) -> str:
    try:
        if value is None or pd.isna(value):
            return "n/a"
        return f"Rs {float(value):,.0f}"
    except (TypeError, ValueError):
        return "n/a"


def main() -> int:
    args = parse_args()
    old_dir = REPO_ROOT / args.old_report_dir
    fixed_dir = REPO_ROOT / args.fixed_report_dir
    old_meta = load_json(old_dir / "metadata.json")
    fixed_meta = load_json(fixed_dir / "metadata.json")
    old_fy = fy_rows(old_meta)
    fixed_fy = fy_rows(fixed_meta)
    old_trades = load_csv(old_dir / "trades.csv")
    fixed_trades = load_csv(fixed_dir / "trades.csv")
    fixed_open = load_csv(fixed_dir / "open_positions.csv")
    old_trade_counts = trade_counts_by_fy(old_trades)
    fixed_trade_counts = trade_counts_by_fy(fixed_trades)
    fixed_open_counts = open_counts_by_fy(fixed_open)
    old_exposure = {row["financial_year"]: row for row in year_end_exposure(load_csv(old_dir / "equity_curve.csv"))}
    fixed_exposure = {row["financial_year"]: row for row in year_end_exposure(load_csv(fixed_dir / "equity_curve.csv"))}

    rows = []
    for fy in sorted(set(old_fy) | set(fixed_fy) | set(old_trade_counts) | set(fixed_trade_counts)):
        old_row = old_fy.get(fy, {})
        fixed_row = fixed_fy.get(fy, {})
        rows.append(
            {
                "financial_year": fy,
                "old_return_pct": old_row.get("return_pct"),
                "fixed_return_pct": fixed_row.get("return_pct"),
                "return_delta_pct": (
                    float(fixed_row["return_pct"]) - float(old_row["return_pct"])
                    if old_row.get("return_pct") is not None and fixed_row.get("return_pct") is not None
                    else None
                ),
                "old_start_equity": old_row.get("start_equity"),
                "fixed_start_equity": fixed_row.get("start_equity"),
                "old_end_equity": old_row.get("end_equity"),
                "fixed_end_equity": fixed_row.get("end_equity"),
                "old_closed_trades_by_exit": old_trade_counts.get(fy, 0),
                "fixed_closed_trades_by_exit": fixed_trade_counts.get(fy, 0),
                "trade_count_delta": fixed_trade_counts.get(fy, 0) - old_trade_counts.get(fy, 0),
                "fixed_open_positions_at_report_end": fixed_open_counts.get(fy, 0),
                "old_end_position_count": old_exposure.get(fy, {}).get("end_position_count"),
                "fixed_end_position_count": fixed_exposure.get(fy, {}).get("end_position_count"),
                "old_max_position_count_last_15_sessions": old_exposure.get(fy, {}).get("max_position_count_last_15_sessions"),
                "fixed_max_position_count_last_15_sessions": fixed_exposure.get(fy, {}).get("max_position_count_last_15_sessions"),
            }
        )

    output_csv = REPO_ROOT / args.output_csv
    output_md = REPO_ROOT / args.output_md
    write_csv(output_csv, rows)

    lines = [
        "# Trade Analysis Fix Reconciliation",
        "",
        f"- Old report: `{old_dir}`",
        f"- Fixed report: `{fixed_dir}`",
        f"- Old closed trade rows: `{len(old_trades)}`",
        f"- Fixed closed trade rows: `{len(fixed_trades)}`",
        f"- Fixed open position rows: `{len(fixed_open)}`",
        "",
        "| FY | Old Return | Fixed Return | Delta | Old Closed | Fixed Closed | Fixed Open | Old FY-End Positions | Fixed FY-End Positions |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['financial_year']} | {pct(row['old_return_pct'])} | {pct(row['fixed_return_pct'])} | "
            f"{pct(row['return_delta_pct'])} | {row['old_closed_trades_by_exit']} | {row['fixed_closed_trades_by_exit']} | "
            f"{row['fixed_open_positions_at_report_end']} | {row['old_end_position_count']} | {row['fixed_end_position_count']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- `Closed` counts are grouped by exit date.",
            "- `Trading days` are equity-curve observations, not trades.",
            "- `Fixed open` rows are mark-to-market positions that are no longer exported as completed trades.",
            "",
        ]
    )
    output_md.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"csv": str(output_csv), "md": str(output_md), "rows": len(rows)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
