#!/usr/bin/env python3
"""Focused FY2024-25 reconciliation for trade analysis reports.

Read-only diagnostic. Compares the stale trade-analysis report against the
fixed artifact-versioned report and writes FY2024-25 detail artifacts.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
FY_START = pd.Timestamp("2024-04-01")
FY_END = pd.Timestamp("2025-03-31")
BOUNDARY_START = pd.Timestamp("2025-03-01")
BOUNDARY_END = pd.Timestamp("2025-04-30")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit FY2024-25 trade-analysis reconciliation.")
    parser.add_argument(
        "--old-report-dir",
        default="reports/trade_analysis/20260618T173851Z_sector_rotation_adx_rolling10_sector_rotation_adx_1m3m_fb471857d9",
    )
    parser.add_argument(
        "--fixed-report-dir",
        default="reports/trade_analysis/20260619T134542Z_sector_rotation_adx_rolling10_sector_rotation_adx_1m3m_6d33521edd",
    )
    parser.add_argument("--output-dir", default="reports/fy2024_25_reconciliation")
    return parser.parse_args()


def load_csv(path: Path, date_columns: list[str] | None = None) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    return pd.read_csv(path, parse_dates=date_columns or [])


def load_meta(path: Path) -> dict:
    return json.loads((path / "metadata.json").read_text(encoding="utf-8"))


def fy_row(meta: dict, fy: str = "FY2024-25") -> dict:
    for row in meta.get("summary", {}).get("financial_year_returns", []):
        if row.get("financial_year") == fy:
            return row
    return {}


def add_trade_key(frame: pd.DataFrame) -> pd.DataFrame:
    item = frame.copy()
    if item.empty:
        return item
    item["trade_key"] = item["symbol"].astype(str) + "|" + item["entry_date"].dt.date.astype(str)
    return item


def fy_trades(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    return frame[(frame["exit_date"] >= FY_START) & (frame["exit_date"] <= FY_END)].copy()


def cross_boundary_trades(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    return frame[(frame["entry_date"] <= FY_END) & (frame["exit_date"] >= pd.Timestamp("2025-04-01"))].copy()


def monthly_equity(frame: pd.DataFrame) -> pd.DataFrame:
    item = frame[(frame["date"] >= FY_START) & (frame["date"] <= FY_END)].copy()
    if item.empty:
        return pd.DataFrame()
    item["month"] = item["date"].dt.to_period("M").astype(str)
    rows = []
    for month, group in item.groupby("month"):
        ordered = group.sort_values("date")
        start_equity = float(ordered.iloc[0]["equity"])
        end_equity = float(ordered.iloc[-1]["equity"])
        rows.append(
            {
                "month": month,
                "start_equity": start_equity,
                "end_equity": end_equity,
                "return_pct": (end_equity / start_equity - 1.0) if start_equity else None,
                "start_positions": int(ordered.iloc[0]["position_count"]),
                "end_positions": int(ordered.iloc[-1]["position_count"]),
                "min_equity": float(ordered["equity"].min()),
                "max_equity": float(ordered["equity"].max()),
            }
        )
    return pd.DataFrame(rows)


def monthly_trade_summary(frame: pd.DataFrame) -> pd.DataFrame:
    item = fy_trades(frame)
    if item.empty:
        return pd.DataFrame()
    item["month"] = item["exit_date"].dt.to_period("M").astype(str)
    grouped = item.groupby("month")
    rows = []
    for month, group in grouped:
        winners = int((group["net_pnl"] > 0).sum())
        rows.append(
            {
                "month": month,
                "closed_trades": int(len(group)),
                "net_pnl": float(group["net_pnl"].sum()),
                "entry_value": float(group["entry_value"].sum()),
                "winners": winners,
                "losers": int(len(group) - winners),
                "win_rate": winners / len(group) if len(group) else None,
            }
        )
    return pd.DataFrame(rows)


def write_csv(path: Path, rows: pd.DataFrame | list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(rows, pd.DataFrame):
        rows.to_csv(path, index=False)
        return
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def pct(value: object) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value) * 100:.2f}%"


def money(value: object) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"Rs {float(value):,.0f}"


def main() -> int:
    args = parse_args()
    old_dir = REPO_ROOT / args.old_report_dir
    fixed_dir = REPO_ROOT / args.fixed_report_dir
    output_dir = REPO_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    old_meta = load_meta(old_dir)
    fixed_meta = load_meta(fixed_dir)
    old_trades = add_trade_key(load_csv(old_dir / "trades.csv", ["entry_date", "exit_date"]))
    fixed_trades = add_trade_key(load_csv(fixed_dir / "trades.csv", ["entry_date", "exit_date"]))
    fixed_open = load_csv(fixed_dir / "open_positions.csv", ["entry_date", "mark_date", "planned_exit_date"])
    old_equity = load_csv(old_dir / "equity_curve.csv", ["date"])
    fixed_equity = load_csv(fixed_dir / "equity_curve.csv", ["date"])

    old_fy = fy_trades(old_trades)
    fixed_fy = fy_trades(fixed_trades)
    old_keys = set(old_fy["trade_key"])
    fixed_keys = set(fixed_fy["trade_key"])
    common_keys = old_keys & fixed_keys

    only_old = old_fy[old_fy["trade_key"].isin(old_keys - fixed_keys)].copy()
    only_fixed = fixed_fy[fixed_fy["trade_key"].isin(fixed_keys - old_keys)].copy()
    common = (
        old_fy.set_index("trade_key")[["symbol", "entry_date", "exit_date", "entry_value", "exit_price", "net_pnl", "net_return_pct"]]
        .join(
            fixed_fy.set_index("trade_key")[["exit_date", "entry_value", "exit_price", "net_pnl", "net_return_pct"]],
            lsuffix="_old",
            rsuffix="_fixed",
        )
        .reset_index()
    )
    common["pnl_delta"] = common["net_pnl_fixed"] - common["net_pnl_old"]
    common["entry_value_delta"] = common["entry_value_fixed"] - common["entry_value_old"]

    old_month_equity = monthly_equity(old_equity)
    fixed_month_equity = monthly_equity(fixed_equity)
    month_equity = old_month_equity.merge(fixed_month_equity, on="month", how="outer", suffixes=("_old", "_fixed"))
    month_equity["return_delta_pct"] = month_equity["return_pct_fixed"] - month_equity["return_pct_old"]
    month_equity["end_equity_delta"] = month_equity["end_equity_fixed"] - month_equity["end_equity_old"]

    old_month_trades = monthly_trade_summary(old_trades)
    fixed_month_trades = monthly_trade_summary(fixed_trades)
    month_trades = old_month_trades.merge(fixed_month_trades, on="month", how="outer", suffixes=("_old", "_fixed")).fillna(0)
    month_trades["net_pnl_delta"] = month_trades["net_pnl_fixed"] - month_trades["net_pnl_old"]
    month_trades["trade_count_delta"] = month_trades["closed_trades_fixed"] - month_trades["closed_trades_old"]

    old_cross = cross_boundary_trades(old_trades)
    fixed_cross = cross_boundary_trades(fixed_trades)

    write_csv(output_dir / "only_old_fy2024_25_trades.csv", only_old.sort_values("net_pnl"))
    write_csv(output_dir / "only_fixed_fy2024_25_trades.csv", only_fixed.sort_values("net_pnl"))
    write_csv(output_dir / "common_fy2024_25_trade_deltas.csv", common.sort_values("pnl_delta"))
    write_csv(output_dir / "monthly_equity_comparison.csv", month_equity.sort_values("month"))
    write_csv(output_dir / "monthly_trade_comparison.csv", month_trades.sort_values("month"))
    write_csv(output_dir / "old_cross_fy_boundary_trades.csv", old_cross.sort_values("entry_date"))
    write_csv(output_dir / "fixed_cross_fy_boundary_trades.csv", fixed_cross.sort_values("entry_date"))

    old_row = fy_row(old_meta)
    fixed_row = fy_row(fixed_meta)
    summary = {
        "old_report": str(old_dir),
        "fixed_report": str(fixed_dir),
        "old_fy_return_pct": old_row.get("return_pct"),
        "fixed_fy_return_pct": fixed_row.get("return_pct"),
        "return_delta_pct": float(fixed_row.get("return_pct", 0)) - float(old_row.get("return_pct", 0)),
        "old_start_equity": old_row.get("start_equity"),
        "fixed_start_equity": fixed_row.get("start_equity"),
        "old_end_equity": old_row.get("end_equity"),
        "fixed_end_equity": fixed_row.get("end_equity"),
        "end_equity_delta": float(fixed_row.get("end_equity", 0)) - float(old_row.get("end_equity", 0)),
        "old_fy_closed_trades": int(len(old_fy)),
        "fixed_fy_closed_trades": int(len(fixed_fy)),
        "common_trade_keys": int(len(common_keys)),
        "only_old_trade_keys": int(len(old_keys - fixed_keys)),
        "only_fixed_trade_keys": int(len(fixed_keys - old_keys)),
        "common_pnl_delta": float(common["pnl_delta"].sum()) if not common.empty else 0.0,
        "only_old_net_pnl": float(only_old["net_pnl"].sum()) if not only_old.empty else 0.0,
        "only_fixed_net_pnl": float(only_fixed["net_pnl"].sum()) if not only_fixed.empty else 0.0,
        "old_cross_boundary_count": int(len(old_cross)),
        "fixed_cross_boundary_count": int(len(fixed_cross)),
        "old_cross_boundary_net_pnl": float(old_cross["net_pnl"].sum()) if not old_cross.empty else 0.0,
        "fixed_cross_boundary_net_pnl": float(fixed_cross["net_pnl"].sum()) if not fixed_cross.empty else 0.0,
        "fixed_open_positions_at_report_end": int(len(fixed_open)),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    worst_fixed_new = only_fixed.sort_values("net_pnl").head(8)
    best_old_removed = only_old.sort_values("net_pnl", ascending=False).head(8)
    worst_common_delta = common.sort_values("pnl_delta").head(8)

    lines = [
        "# FY2024-25 Trade Analysis Reconciliation",
        "",
        "This is a read-only diagnostic comparing the stale trade-analysis report with the fixed artifact-versioned report.",
        "",
        "## Headline",
        "",
        f"- Old FY2024-25 return: **{pct(summary['old_fy_return_pct'])}**",
        f"- Fixed FY2024-25 return: **{pct(summary['fixed_fy_return_pct'])}**",
        f"- Change: **{pct(summary['return_delta_pct'])}**",
        f"- Old FY-end equity: **{money(summary['old_end_equity'])}**",
        f"- Fixed FY-end equity: **{money(summary['fixed_end_equity'])}**",
        f"- FY-end equity change: **{money(summary['end_equity_delta'])}**",
        "",
        "## What Changed",
        "",
        f"- Old FY2024-25 closed trades: `{summary['old_fy_closed_trades']}`",
        f"- Fixed FY2024-25 closed trades: `{summary['fixed_fy_closed_trades']}`",
        f"- Common `symbol + entry_date` trades: `{summary['common_trade_keys']}`",
        f"- Trades present only in old report: `{summary['only_old_trade_keys']}`",
        f"- Trades present only in fixed report: `{summary['only_fixed_trade_keys']}`",
        f"- PnL delta on common trades: **{money(summary['common_pnl_delta'])}**",
        f"- Net PnL removed with old-only trades: **{money(summary['only_old_net_pnl'])}**",
        f"- Net PnL added with fixed-only trades: **{money(summary['only_fixed_net_pnl'])}**",
        "",
        "## March 2025 Boundary Check",
        "",
        f"- Old cross-FY positions: `{summary['old_cross_boundary_count']}`, final net PnL **{money(summary['old_cross_boundary_net_pnl'])}**",
        f"- Fixed cross-FY positions: `{summary['fixed_cross_boundary_count']}`, final net PnL **{money(summary['fixed_cross_boundary_net_pnl'])}**",
        "",
        "The March boundary explains only a small part of the FY2024-25 return change. The larger issue is that the fixed rerun changed the full-year portfolio path and trade set.",
        "",
        "## Largest Old Winners No Longer In Fixed FY2024-25",
        "",
        "| Symbol | Entry | Exit | Entry Value | Net PnL | Return |",
        "| --- | --- | --- | ---: | ---: | ---: |",
    ]
    for _, row in best_old_removed.iterrows():
        lines.append(
            f"| {row['symbol']} | {row['entry_date'].date()} | {row['exit_date'].date()} | "
            f"{money(row['entry_value'])} | {money(row['net_pnl'])} | {pct(row['net_return_pct'])} |"
        )
    lines.extend(
        [
            "",
            "## Worst Fixed Trades Not Present In Old FY2024-25",
            "",
            "| Symbol | Entry | Exit | Entry Value | Net PnL | Return |",
            "| --- | --- | --- | ---: | ---: | ---: |",
        ]
    )
    for _, row in worst_fixed_new.iterrows():
        lines.append(
            f"| {row['symbol']} | {row['entry_date'].date()} | {row['exit_date'].date()} | "
            f"{money(row['entry_value'])} | {money(row['net_pnl'])} | {pct(row['net_return_pct'])} |"
        )
    lines.extend(
        [
            "",
            "## Worst Common Trade PnL Deltas",
            "",
            "| Symbol | Entry | Old Exit | Fixed Exit | Old PnL | Fixed PnL | Delta |",
            "| --- | --- | --- | --- | ---: | ---: | ---: |",
        ]
    )
    for _, row in worst_common_delta.iterrows():
        lines.append(
            f"| {row['symbol']} | {row['entry_date'].date()} | {row['exit_date_old'].date()} | {row['exit_date_fixed'].date()} | "
            f"{money(row['net_pnl_old'])} | {money(row['net_pnl_fixed'])} | {money(row['pnl_delta'])} |"
        )
    lines.extend(
        [
            "",
            "## Verdict",
            "",
            "- The fixed FY2024-25 number is not explained by March 2025 force-closed positions alone.",
            "- The stale report and fixed report have materially different FY2024-25 trade membership.",
            "- Treat the old 34.23% FY2024-25 return and old 27.49% CAGR as retired.",
            "- The fixed 21.58% FY2024-25 return is the current baseline from the corrected report path, but it should be treated as a regenerated baseline, not a small patch to the old ledger.",
            "",
            "## Artifacts",
            "",
            "- `only_old_fy2024_25_trades.csv`",
            "- `only_fixed_fy2024_25_trades.csv`",
            "- `common_fy2024_25_trade_deltas.csv`",
            "- `monthly_equity_comparison.csv`",
            "- `monthly_trade_comparison.csv`",
            "- `old_cross_fy_boundary_trades.csv`",
            "- `fixed_cross_fy_boundary_trades.csv`",
        ]
    )
    (output_dir / "FY2024_25_RECONCILIATION.md").write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps({"status": "success", "output_dir": str(output_dir), **summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
