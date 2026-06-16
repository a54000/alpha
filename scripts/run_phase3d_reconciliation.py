#!/usr/bin/env python3
"""Phase 3D reconciliation between Phase 2E backtest and Phase 3C paper replay."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
START_DATE = date(2025, 1, 1)
END_DATE = date(2026, 6, 11)
VARIANTS = ["top5_weekly", "top10_weekly"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reconcile Phase 2E backtest against Phase 3C paper replay.")
    parser.add_argument("--phase2e-equity-csv", default="reports/phase2e_equity_curves.csv")
    parser.add_argument("--phase2e-trades-csv", default="reports/phase2e_trade_ledger.csv")
    parser.add_argument("--phase3c-json", default="reports/phase3c_hold_to_exit_replay_validation.json")
    parser.add_argument("--output-json", default="reports/phase3d_reconciliation.json")
    return parser.parse_args()


def load_inputs(args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    equity = pd.read_csv(REPO_ROOT / args.phase2e_equity_csv)
    trades = pd.read_csv(REPO_ROOT / args.phase2e_trades_csv)
    phase3c = json.loads((REPO_ROOT / args.phase3c_json).read_text(encoding="utf-8"))
    equity["date"] = pd.to_datetime(equity["date"]).dt.date
    for column in ["signal_date", "entry_date", "exit_date"]:
        trades[column] = pd.to_datetime(trades[column]).dt.date
    for column in ["entry_price", "exit_price", "shares", "return", "pnl", "entry_value", "exit_value"]:
        trades[column] = pd.to_numeric(trades[column], errors="coerce")
    return equity, trades, phase3c


def first_divergence(phase2e: pd.DataFrame, paper_snapshots: list[dict[str, object]]) -> dict[str, object] | None:
    paper = pd.DataFrame(paper_snapshots)
    if paper.empty:
        return None
    paper["date"] = pd.to_datetime(paper["date"]).dt.date
    paper["nav_norm"] = pd.to_numeric(paper["nav"], errors="coerce") / pd.to_numeric(paper["nav"], errors="coerce").iloc[0]
    bt = phase2e.copy()
    bt["equity_norm"] = pd.to_numeric(bt["equity"], errors="coerce") / pd.to_numeric(bt["equity"], errors="coerce").iloc[0]
    merged = bt.merge(paper[["date", "nav_norm", "nav"]], on="date", how="inner")
    merged["abs_delta"] = (merged["equity_norm"] - merged["nav_norm"]).abs()
    divergent = merged[merged["abs_delta"] > 0.001]
    if divergent.empty:
        return None
    row = divergent.iloc[0]
    return {
        "date": row["date"].isoformat(),
        "phase2e_normalized_equity": float(row["equity_norm"]),
        "paper_normalized_nav": float(row["nav_norm"]),
        "absolute_delta": float(row["abs_delta"]),
    }


def trade_key(row: pd.Series | dict[str, object]) -> tuple[str, str, str]:
    return (str(row["symbol"]), str(row["entry_date"]), str(row["exit_date"]))


def reconcile_trades(phase2e_trades: pd.DataFrame, paper_trades: list[dict[str, object]]) -> dict[str, object]:
    paper = pd.DataFrame(paper_trades)
    if paper.empty:
        paper = pd.DataFrame(columns=["symbol", "entry_date", "exit_date", "entry_price", "exit_price", "quantity", "return_pct", "realized_pnl"])
    for column in ["entry_date", "exit_date"]:
        paper[column] = pd.to_datetime(paper[column]).dt.date
    for column in ["entry_price", "exit_price", "quantity", "return_pct", "realized_pnl"]:
        paper[column] = pd.to_numeric(paper[column], errors="coerce")

    bt_keys = Counter(trade_key(row) for _, row in phase2e_trades.iterrows())
    paper_keys = Counter(trade_key(row) for _, row in paper.iterrows())
    matched_keys = list((bt_keys & paper_keys).elements())
    missing_keys = list((bt_keys - paper_keys).elements())
    extra_keys = list((paper_keys - bt_keys).elements())

    bt_by_key = {trade_key(row): row for _, row in phase2e_trades.iterrows()}
    paper_by_key = {trade_key(row): row for _, row in paper.iterrows()}
    price_mismatches = []
    quantity_mismatches = []
    for key in matched_keys:
        bt = bt_by_key[key]
        pr = paper_by_key[key]
        entry_delta = float(pr["entry_price"]) - float(bt["entry_price"])
        exit_delta = float(pr["exit_price"]) - float(bt["exit_price"])
        qty_delta = float(pr["quantity"]) - float(bt["shares"])
        if abs(entry_delta) > 0.0001 or abs(exit_delta) > 0.0001:
            price_mismatches.append(
                {
                    "symbol": key[0],
                    "entry_date": key[1],
                    "exit_date": key[2],
                    "entry_price_delta": entry_delta,
                    "exit_price_delta": exit_delta,
                    "phase2e_entry": float(bt["entry_price"]),
                    "paper_entry": float(pr["entry_price"]),
                    "phase2e_exit": float(bt["exit_price"]),
                    "paper_exit": float(pr["exit_price"]),
                }
            )
        if abs(qty_delta) > 0.001:
            quantity_mismatches.append(
                {
                    "symbol": key[0],
                    "entry_date": key[1],
                    "exit_date": key[2],
                    "quantity_delta": qty_delta,
                    "phase2e_quantity": float(bt["shares"]),
                    "paper_quantity": float(pr["quantity"]),
                    "phase2e_entry_value": float(bt["entry_value"]),
                    "paper_entry_value": float(pr["quantity"]) * float(pr["entry_price"]),
                }
            )

    missing_rows = [bt_by_key[key] for key in missing_keys if key in bt_by_key]
    extra_rows = [paper_by_key[key] for key in extra_keys if key in paper_by_key]
    affected_symbols = sorted({key[0] for key in missing_keys + extra_keys})

    return {
        "phase2e_trades": int(len(phase2e_trades)),
        "paper_trades": int(len(paper)),
        "matched_trades": int(len(matched_keys)),
        "missing_from_paper": int(len(missing_keys)),
        "extra_in_paper": int(len(extra_keys)),
        "price_mismatch_count": len(price_mismatches),
        "quantity_mismatch_count": len(quantity_mismatches),
        "affected_symbols": affected_symbols,
        "missing_from_paper_sample": [
            {
                "symbol": row["symbol"],
                "entry_date": row["entry_date"].isoformat(),
                "exit_date": row["exit_date"].isoformat(),
                "rank": int(row["rank"]),
                "return": float(row["return"]),
                "pnl": float(row["pnl"]),
            }
            for row in missing_rows[:20]
        ],
        "extra_in_paper_sample": [
            {
                "symbol": row["symbol"],
                "entry_date": row["entry_date"].isoformat(),
                "exit_date": row["exit_date"].isoformat(),
                "return": float(row["return_pct"]),
                "pnl": float(row["realized_pnl"]),
            }
            for row in extra_rows[:20]
        ],
        "price_mismatch_sample": price_mismatches[:20],
        "quantity_mismatch_sample": quantity_mismatches[:20],
    }


def classify_root_causes(trade_recon: dict[str, object], first_div: dict[str, object] | None) -> list[dict[str, object]]:
    causes = []
    if trade_recon["missing_from_paper"] or trade_recon["extra_in_paper"]:
        causes.append(
            {
                "category": "rebalance_date_or_capacity_alignment",
                "severity": "high",
                "evidence": f"{trade_recon['missing_from_paper']} Phase2E trades missing from paper and {trade_recon['extra_in_paper']} extra paper trades.",
            }
        )
    if trade_recon["quantity_mismatch_count"]:
        causes.append(
            {
                "category": "position_sizing_cash_timing",
                "severity": "medium",
                "evidence": f"{trade_recon['quantity_mismatch_count']} matched trades have quantity differences.",
            }
        )
    if trade_recon["price_mismatch_count"]:
        causes.append(
            {
                "category": "entry_exit_price_difference",
                "severity": "medium",
                "evidence": f"{trade_recon['price_mismatch_count']} matched trades have entry or exit price differences.",
            }
        )
    if first_div is not None:
        causes.append(
            {
                "category": "initial_state_or_cash_deployment",
                "severity": "medium",
                "evidence": f"First normalized NAV divergence on {first_div['date']} with delta {first_div['absolute_delta']:.6f}.",
            }
        )
    if not causes:
        causes.append({"category": "no_material_mismatch", "severity": "none", "evidence": "No material reconciliation breaks found."})
    return causes


def main() -> int:
    args = parse_args()
    equity, trades, phase3c = load_inputs(args)
    results = {}
    for variant in VARIANTS:
        phase2e_equity = equity[(equity["variant"] == variant) & (equity["date"] >= START_DATE) & (equity["date"] <= END_DATE)]
        phase2e_trades = trades[(trades["variant"] == variant) & (trades["exit_date"] >= START_DATE) & (trades["exit_date"] <= END_DATE)]
        paper_result = phase3c["results"][variant]
        div = first_divergence(phase2e_equity, paper_result["snapshots"])
        trade_recon = reconcile_trades(phase2e_trades, paper_result["trades"])
        results[variant] = {
            "metric_comparison": paper_result["metric_comparison"],
            "first_divergence": div,
            "trade_reconciliation": trade_recon,
            "root_cause_classification": classify_root_causes(trade_recon, div),
        }
    output = {
        "generated_on": date.today().isoformat(),
        "mode": "phase3d_reconciliation",
        "period": {"start": START_DATE.isoformat(), "end": END_DATE.isoformat()},
        "constraints": {
            "scoring_changed": False,
            "recommendations_changed": False,
            "strategy_rules_changed": False,
            "parameters_optimized": False,
            "broker_apis_connected": False,
        },
        "results": results,
    }
    output_path = REPO_ROOT / args.output_json
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
