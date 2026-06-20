#!/usr/bin/env python3
"""Read-only min-sector-points bisection.

Regenerates Sector Rotation 1M/3M candidate recommendations in memory with
min_sector_points=0 vs min_sector_points=1, then replays both through the
current Sector Rotation ADX Rolling 10 trade-analysis engine.

No database writes. No recommendation table mutation.
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
from scripts.run_sector_1m3m_rank_experiment import (  # noqa: E402
    generate_recommendations,
    load_features_and_sector_returns,
    score_frame,
)


MODEL = "sector_rotation_adx_1m3m"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit min_sector_points=1 impact.")
    parser.add_argument("--initial-capital", type=float, default=1_000_000)
    parser.add_argument("--pilot-schema", default="pilot_phase2a")
    parser.add_argument("--expanded-universe-csv", default="reports/nifty500_expansion_universe_symbols.csv")
    parser.add_argument("--minimum-score", type=float, default=70.0)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--weight-1m", type=float, default=0.40)
    parser.add_argument("--weight-3m", type=float, default=0.60)
    parser.add_argument("--output-dir", default="reports/min_sector_points_bisection")
    return parser.parse_args()


def load_expanded_ready_symbols(path: Path) -> set[str]:
    frame = pd.read_csv(path)
    if "reason" in frame.columns:
        frame = frame[frame["reason"].astype(str) == "usable"]
    return {str(symbol).strip().upper() for symbol in frame["symbol"].dropna() if str(symbol).strip()}


def prepare_recommendations(
    engine,
    schema: str,
    start_date: date,
    end_date: date,
    allowed_symbols: set[str],
    minimum_score: float,
    top_n: int,
    min_sector_points: int,
    weight_1m: float,
    weight_3m: float,
) -> tuple[list[dict[str, object]], pd.DataFrame]:
    features = load_features_and_sector_returns(engine, schema, start_date, end_date, weight_1m, weight_3m)
    features = features[features["symbol"].astype(str).str.upper().isin(allowed_symbols)].copy()
    scores = score_frame(features, "sector_rank_1m3m", "score_1m3m")
    rows = generate_recommendations(scores, "score_1m3m", minimum_score, top_n, MODEL, min_sector_points)
    return rows, scores


def run_case(
    service: TradeAnalysisService,
    request: TradeAnalysisRequest,
    recommendations: list[dict[str, object]],
) -> dict[str, object]:
    cloned_recommendations = [dict(row) for row in recommendations]
    service._attach_signal_day_vwaps(request, cloned_recommendations)
    symbols = {str(row["symbol"]) for row in cloned_recommendations}
    prices = service._load_prices(request, symbols)
    result = reconstruct_trades(request, cloned_recommendations, prices)
    result["summary"]["financial_year_returns"] = financial_year_returns(result["equity_curve"], result["trades"])
    return result


def trade_key(row: dict[str, object]) -> str:
    return f"{row.get('symbol')}|{row.get('entry_date')}"


def write_csv(path: Path, rows: list[dict[str, object]] | pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(rows, pd.DataFrame):
        rows.to_csv(path, index=False)
    else:
        pd.DataFrame(rows).to_csv(path, index=False)


def pct(value: object) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value) * 100:.2f}%"


def money(value: object) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"Rs {float(value):,.0f}"


def summarize_result(period: str, case: str, min_sector_points: int, recs: list[dict[str, object]], result: dict[str, object]) -> dict[str, object]:
    summary = result["summary"]
    zero_sector_recs = [row for row in recs if int(row.get("sector_points") or 0) == 0]
    return {
        "period": period,
        "case": case,
        "min_sector_points": min_sector_points,
        "recommendation_rows": len(recs),
        "recommendation_symbols": len({str(row["symbol"]) for row in recs}),
        "zero_sector_point_recommendations": len(zero_sector_recs),
        "ending_value": summary.get("ending_value"),
        "total_return": summary.get("total_return"),
        "cagr": summary.get("cagr"),
        "max_drawdown": summary.get("max_drawdown"),
        "closed_trades": summary.get("total_trades"),
        "open_positions": summary.get("open_positions"),
        "win_rate": summary.get("win_rate"),
        "net_pnl": summary.get("net_pnl"),
        "total_charges": summary.get("total_charges"),
    }


def main() -> int:
    args = parse_args()
    load_dotenv(REPO_ROOT / ".env")
    output_dir = REPO_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    allowed_symbols = load_expanded_ready_symbols(REPO_ROOT / args.expanded_universe_csv)
    service = TradeAnalysisService(angel_database_url=os.environ.get("ANGEL_DATABASE_URL"), pilot_schema=args.pilot_schema)
    if service.angel_engine is None:
        raise RuntimeError("ANGEL_DATABASE_URL is required")

    periods = {
        "FY2024-25": (date(2024, 4, 1), date(2025, 3, 31)),
        "FY2025-26": (date(2025, 4, 1), date(2026, 3, 31)),
    }
    cases = {
        "min_sector_points_0": 0,
        "min_sector_points_1": 1,
    }

    summary_rows: list[dict[str, object]] = []
    payload: dict[str, object] = {"status": "success", "periods": {}, "universe_symbols": len(allowed_symbols)}

    for period, (start_date, end_date) in periods.items():
        request = TradeAnalysisRequest(
            start_date=start_date,
            end_date=end_date,
            strategy="SECTOR_ROTATION_ADX_ROLLING10",
            recommendation_model=MODEL,
            initial_capital=args.initial_capital,
        )
        period_results: dict[str, dict[str, object]] = {}
        period_recs: dict[str, list[dict[str, object]]] = {}
        for case_name, min_points in cases.items():
            recs, scores = prepare_recommendations(
                service.angel_engine,
                args.pilot_schema,
                start_date,
                end_date,
                allowed_symbols,
                args.minimum_score,
                args.top_n,
                min_points,
                args.weight_1m,
                args.weight_3m,
            )
            result = run_case(service, request, recs)
            period_results[case_name] = result
            period_recs[case_name] = recs
            write_csv(output_dir / f"{period}_{case_name}_recommendations.csv", recs)
            write_csv(output_dir / f"{period}_{case_name}_trades.csv", result["trades"])
            write_csv(output_dir / f"{period}_{case_name}_equity_curve.csv", result["equity_curve"])
            if case_name == "min_sector_points_0":
                write_csv(output_dir / f"{period}_scores_sample.csv", scores.head(5000))
            summary_rows.append(summarize_result(period, case_name, min_points, recs, result))

        rec0 = pd.DataFrame(period_recs["min_sector_points_0"])
        rec1 = pd.DataFrame(period_recs["min_sector_points_1"])
        if not rec0.empty and not rec1.empty:
            rec0["rec_key"] = rec0["date"].astype(str) + "|" + rec0["symbol"].astype(str)
            rec1["rec_key"] = rec1["date"].astype(str) + "|" + rec1["symbol"].astype(str)
            removed_recs = rec0[~rec0["rec_key"].isin(set(rec1["rec_key"]))].copy()
            write_csv(output_dir / f"{period}_recommendations_removed_by_sector_guard.csv", removed_recs)

        trades0 = period_results["min_sector_points_0"]["trades"]
        trades1 = period_results["min_sector_points_1"]["trades"]
        keys0 = {trade_key(row) for row in trades0}
        keys1 = {trade_key(row) for row in trades1}
        only0 = [row for row in trades0 if trade_key(row) not in keys1]
        only1 = [row for row in trades1 if trade_key(row) not in keys0]
        write_csv(output_dir / f"{period}_trades_removed_by_sector_guard.csv", only0)
        write_csv(output_dir / f"{period}_trades_added_after_sector_guard_path_change.csv", only1)
        payload["periods"][period] = {
            "recommendation_overlap": {
                "common": int(len(set(rec0.get("rec_key", [])) & set(rec1.get("rec_key", [])))) if not rec0.empty and not rec1.empty else 0,
                "only_min0": int(len(set(rec0.get("rec_key", [])) - set(rec1.get("rec_key", [])))) if not rec0.empty and not rec1.empty else 0,
                "only_min1": int(len(set(rec1.get("rec_key", [])) - set(rec0.get("rec_key", [])))) if not rec0.empty and not rec1.empty else 0,
            },
            "trade_overlap": {
                "common": int(len(keys0 & keys1)),
                "only_min0": int(len(keys0 - keys1)),
                "only_min1": int(len(keys1 - keys0)),
                "only_min0_net_pnl": float(sum(float(row["net_pnl"]) for row in only0)),
                "only_min1_net_pnl": float(sum(float(row["net_pnl"]) for row in only1)),
            },
        }

    pd.DataFrame(summary_rows).to_csv(output_dir / "min_sector_points_summary.csv", index=False)
    payload["summary"] = summary_rows
    (output_dir / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    lines = [
        "# Min Sector Points Bisection",
        "",
        "This read-only diagnostic regenerates recommendations in memory with `min_sector_points=0` and `min_sector_points=1`, then replays both through the same current 10:30 + VWAP engine.",
        "",
        "| Period | Case | Reco Rows | Zero-Sector Recos | Return | CAGR | Max DD | Closed Trades | Win Rate |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary_rows:
        lines.append(
            f"| {row['period']} | {row['case']} | {row['recommendation_rows']} | {row['zero_sector_point_recommendations']} | "
            f"{pct(row['total_return'])} | {pct(row['cagr'])} | {pct(row['max_drawdown'])} | {row['closed_trades']} | {pct(row['win_rate'])} |"
        )
    lines.extend(["", "## Trade Overlap", "", "| Period | Common | Only Min0 | Only Min1 | Only Min0 PnL | Only Min1 PnL |", "| --- | ---: | ---: | ---: | ---: | ---: |"])
    for period, data in payload["periods"].items():
        overlap = data["trade_overlap"]
        lines.append(
            f"| {period} | {overlap['common']} | {overlap['only_min0']} | {overlap['only_min1']} | "
            f"{money(overlap['only_min0_net_pnl'])} | {money(overlap['only_min1_net_pnl'])} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- If min=1 materially changes trade membership or improves drawdown/return, it is a structural sector eligibility rule, not a cosmetic cleanup.",
            "- If zero-sector recommendations are common under min=0 but rarely become trades, the guard is lower impact.",
            "- This is a diagnostic only; no database rows were modified.",
            "",
            "## Artifacts",
            "",
            "- `min_sector_points_summary.csv`",
            "- `{period}_recommendations_removed_by_sector_guard.csv`",
            "- `{period}_trades_removed_by_sector_guard.csv`",
            "- `{period}_trades_added_after_sector_guard_path_change.csv`",
        ]
    )
    (output_dir / "MIN_SECTOR_POINTS_BISECTION.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(payload, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
