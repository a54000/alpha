#!/usr/bin/env python3
"""Read-only universe-expansion bisection for trade analysis.

Runs the current trade-analysis engine for FY2024-25 while filtering the same
recommendation table to two universe definitions:

1. Original Phase 1B exact-match universe.
2. Expanded Nifty500 ready universe.

This isolates the effect of candidate universe membership under the current
engine. It does not modify recommendations, data, strategy code, or databases.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.api.trade_analysis_service import (  # noqa: E402
    TradeAnalysisRequest,
    TradeAnalysisService,
    financial_year_returns,
    reconstruct_trades,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit current-engine universe expansion impact.")
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2024, 4, 1))
    parser.add_argument("--end-date", type=date.fromisoformat, default=date(2025, 3, 31))
    parser.add_argument("--initial-capital", type=float, default=1_000_000)
    parser.add_argument("--pilot-schema", default="pilot_phase2a")
    parser.add_argument("--original-alias-csv", default="reports/phase1b_alias_proposals.csv")
    parser.add_argument("--expanded-universe-csv", default="reports/nifty500_expansion_universe_symbols.csv")
    parser.add_argument("--output-dir", default="reports/universe_expansion_bisection")
    return parser.parse_args()


def load_original_exact_symbols(path: Path) -> set[str]:
    frame = pd.read_csv(path)
    exact = frame[
        (frame["source"].astype(str) == "research")
        & (frame["alias_reason"].astype(str) == "exact")
        & (frame["confidence"].astype(str) == "high")
        & (frame["review_status"].astype(str) == "approved")
    ]
    return {str(symbol).strip().upper() for symbol in exact["symbol"].dropna() if str(symbol).strip()}


def load_expanded_ready_symbols(path: Path) -> set[str]:
    frame = pd.read_csv(path)
    if "reason" in frame.columns:
        frame = frame[frame["reason"].astype(str) == "usable"]
    return {str(symbol).strip().upper() for symbol in frame["symbol"].dropna() if str(symbol).strip()}


def run_filtered_case(
    service: TradeAnalysisService,
    request: TradeAnalysisRequest,
    allowed_symbols: set[str],
) -> dict[str, object]:
    recommendations = service._load_recommendations(request)
    recommendations = [row for row in recommendations if str(row["symbol"]).upper() in allowed_symbols]
    symbols = {str(row["symbol"]) for row in recommendations}
    prices = service._load_prices(request, symbols)
    result = reconstruct_trades(request, recommendations, prices)
    result["summary"]["financial_year_returns"] = financial_year_returns(result["equity_curve"], result["trades"])
    return {
        "summary": result["summary"],
        "trades": result["trades"],
        "open_positions": result.get("open_positions", []),
        "equity_curve": result["equity_curve"],
        "recommendation_rows": len(recommendations),
        "recommendation_symbols": len(symbols),
    }


def trade_key(row: dict[str, object]) -> str:
    return f"{row.get('symbol')}|{row.get('entry_date')}"


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


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
    load_dotenv(REPO_ROOT / ".env")
    output_dir = REPO_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    original_symbols = load_original_exact_symbols(REPO_ROOT / args.original_alias_csv)
    expanded_symbols = load_expanded_ready_symbols(REPO_ROOT / args.expanded_universe_csv)
    added_symbols = expanded_symbols - original_symbols

    service = TradeAnalysisService(
        angel_database_url=os.environ.get("ANGEL_DATABASE_URL"),
        pilot_schema=args.pilot_schema,
    )
    request = TradeAnalysisRequest(
        start_date=args.start_date,
        end_date=args.end_date,
        strategy="SECTOR_ROTATION_ADX_ROLLING10",
        recommendation_model="sector_rotation_adx_1m3m",
        initial_capital=args.initial_capital,
    )

    cases = {
        "original_exact_285": run_filtered_case(service, request, original_symbols),
        "expanded_ready_386": run_filtered_case(service, request, expanded_symbols),
    }

    for name, case in cases.items():
        write_csv(output_dir / f"{name}_trades.csv", case["trades"])
        write_csv(output_dir / f"{name}_open_positions.csv", case["open_positions"])
        write_csv(output_dir / f"{name}_equity_curve.csv", case["equity_curve"])

    original_trades = cases["original_exact_285"]["trades"]
    expanded_trades = cases["expanded_ready_386"]["trades"]
    original_keys = {trade_key(row) for row in original_trades}
    expanded_keys = {trade_key(row) for row in expanded_trades}
    only_original = [row for row in original_trades if trade_key(row) not in expanded_keys]
    only_expanded = [row for row in expanded_trades if trade_key(row) not in original_keys]
    added_symbol_trades = [row for row in expanded_trades if str(row.get("symbol")).upper() in added_symbols]
    write_csv(output_dir / "only_original_trades.csv", only_original)
    write_csv(output_dir / "only_expanded_trades.csv", only_expanded)
    write_csv(output_dir / "expanded_added_symbol_trades.csv", added_symbol_trades)

    summary_rows = []
    for name, case in cases.items():
        summary = case["summary"]
        summary_rows.append(
            {
                "case": name,
                "universe_symbols": len(original_symbols) if name.startswith("original") else len(expanded_symbols),
                "recommendation_rows": case["recommendation_rows"],
                "recommendation_symbols": case["recommendation_symbols"],
                "ending_value": summary.get("ending_value"),
                "total_return": summary.get("total_return"),
                "cagr": summary.get("cagr"),
                "max_drawdown": summary.get("max_drawdown"),
                "closed_trades": summary.get("total_trades"),
                "open_positions": summary.get("open_positions", 0),
                "win_rate": summary.get("win_rate"),
                "net_pnl": summary.get("net_pnl"),
                "total_charges": summary.get("total_charges"),
            }
        )
    write_csv(output_dir / "summary.csv", summary_rows)

    original_summary = cases["original_exact_285"]["summary"]
    expanded_summary = cases["expanded_ready_386"]["summary"]
    report = {
        "status": "success",
        "mode": "current_engine_universe_filter_bisection",
        "date_range": {"start": args.start_date.isoformat(), "end": args.end_date.isoformat()},
        "original_symbols": len(original_symbols),
        "expanded_symbols": len(expanded_symbols),
        "added_symbols": len(added_symbols),
        "original_summary": original_summary,
        "expanded_summary": expanded_summary,
        "trade_overlap": {
            "common": len(original_keys & expanded_keys),
            "only_original": len(original_keys - expanded_keys),
            "only_expanded": len(expanded_keys - original_keys),
            "expanded_added_symbol_trades": len(added_symbol_trades),
        },
    }
    (output_dir / "summary.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    lines = [
        "# Universe Expansion Bisection",
        "",
        "This read-only diagnostic runs the current trade-analysis engine twice for FY2024-25 using the same recommendation table, with only the allowed universe changed.",
        "",
        "| Case | Universe | Reco Rows | Reco Symbols | Ending Value | Return | CAGR | Max DD | Closed Trades | Win Rate |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary_rows:
        lines.append(
            f"| {row['case']} | {row['universe_symbols']} | {row['recommendation_rows']} | {row['recommendation_symbols']} | "
            f"{money(row['ending_value'])} | {pct(row['total_return'])} | {pct(row['cagr'])} | {pct(row['max_drawdown'])} | "
            f"{row['closed_trades']} | {pct(row['win_rate'])} |"
        )
    lines.extend(
        [
            "",
            "## Trade Overlap",
            "",
            f"- Common trades: `{report['trade_overlap']['common']}`",
            f"- Original-only trades: `{report['trade_overlap']['only_original']}`",
            f"- Expanded-only trades: `{report['trade_overlap']['only_expanded']}`",
            f"- Trades in symbols added by expansion: `{report['trade_overlap']['expanded_added_symbol_trades']}`",
            "",
            "## Interpretation",
            "",
            "If the expanded case differs materially from the original case, universe expansion is a load-bearing change and must not be bundled with the accounting fix baseline.",
            "",
            "Artifacts:",
            "",
            "- `summary.csv`",
            "- `summary.json`",
            "- `original_exact_285_trades.csv`",
            "- `expanded_ready_386_trades.csv`",
            "- `only_original_trades.csv`",
            "- `only_expanded_trades.csv`",
            "- `expanded_added_symbol_trades.csv`",
        ]
    )
    (output_dir / "UNIVERSE_EXPANSION_BISECTION.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
