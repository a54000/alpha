#!/usr/bin/env python3
"""Research-only parameter neighborhood test for 1M/3M sector ranking.

Tests nearby 1M/3M weight mixes against the current 3M sector-rank baseline.
No production scores, recommendations, strategy rules, or database rows are
modified.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.run_sector_1m3m_rank_experiment import (  # noqa: E402
    MODEL,
    fmt_num,
    fmt_pct,
    fy_returns,
    generate_recommendations,
    load_baseline_recommendations,
    load_features_and_sector_returns,
    load_prices,
    recommendation_overlap,
    run_rolling_10,
    score_frame,
)

OUTPUT_DIR = REPO_ROOT / "results" / "sector_1m3m_parameter_neighborhood"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run 1M/3M sector-rank parameter neighborhood validation.")
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2022, 5, 25))
    parser.add_argument("--end-date", type=date.fromisoformat, default=date(2026, 6, 11))
    parser.add_argument("--initial-capital", type=float, default=1_000_000.0)
    parser.add_argument("--pilot-schema", default="pilot_phase2a")
    parser.add_argument("--portfolio-size", type=int, default=10)
    parser.add_argument("--weekly-picks", type=int, default=5)
    parser.add_argument("--holding-period", type=int, default=20)
    parser.add_argument("--minimum-score", type=float, default=70.0)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--weights", default="0.30:0.70,0.40:0.60,0.50:0.50,0.60:0.40")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    return parser.parse_args()


def parse_weights(value: str) -> list[tuple[float, float]]:
    pairs: list[tuple[float, float]] = []
    for item in value.split(","):
        left, right = item.strip().split(":", maxsplit=1)
        pairs.append((float(left), float(right)))
    return pairs


def variant_name(weight_1m: float, weight_3m: float) -> str:
    return f"sector_1m3m_{int(round(weight_1m * 100)):02d}_{int(round(weight_3m * 100)):02d}_rank"


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


def metric_delta(row: dict[str, object], baseline: dict[str, object], key: str) -> float | None:
    if row.get(key) is None or baseline.get(key) is None:
        return None
    return float(row[key]) - float(baseline[key])


def summarize_variant(
    *,
    name: str,
    weight_1m: float | None,
    weight_3m: float | None,
    result: dict[str, object],
    recommendation_rows: int,
    baseline_metrics: dict[str, object],
    overlap_rows: list[dict[str, object]] | None,
) -> dict[str, object]:
    metrics = result["metrics"]
    avg_overlap = (
        statistics.mean([float(row["jaccard_overlap"]) for row in overlap_rows if row.get("jaccard_overlap") is not None])
        if overlap_rows
        else None
    )
    return {
        "variant": name,
        "weight_1m": weight_1m,
        "weight_3m": weight_3m,
        "recommendation_rows": recommendation_rows,
        "cagr": metrics.get("cagr"),
        "total_return": metrics.get("total_return"),
        "max_drawdown": metrics.get("max_drawdown"),
        "sharpe_ratio": metrics.get("sharpe_ratio"),
        "sortino_ratio": metrics.get("sortino_ratio"),
        "profit_factor": metrics.get("profit_factor"),
        "win_rate": metrics.get("win_rate"),
        "closed_trades": metrics.get("closed_trades"),
        "avg_cash_pct": metrics.get("avg_cash_pct"),
        "avg_position_count": metrics.get("avg_position_count"),
        "cagr_delta": metric_delta(metrics, baseline_metrics, "cagr"),
        "max_drawdown_delta": metric_delta(metrics, baseline_metrics, "max_drawdown"),
        "sharpe_delta": metric_delta(metrics, baseline_metrics, "sharpe_ratio"),
        "sortino_delta": metric_delta(metrics, baseline_metrics, "sortino_ratio"),
        "profit_factor_delta": metric_delta(metrics, baseline_metrics, "profit_factor"),
        "avg_jaccard_overlap_vs_baseline": avg_overlap,
    }


def render_report(payload: dict[str, object], rows: list[dict[str, object]], fy_rows: list[dict[str, object]]) -> str:
    lines = [
        "# Sector 1M/3M Parameter Neighborhood Test",
        "",
        "Research-only validation. No production scores, recommendations, strategy rules, or database rows were modified.",
        "",
        "## Objective",
        "",
        "Check whether the 1M/3M sector-rank improvement is robust across nearby weights, rather than isolated to a single tuned 40/60 setting.",
        "",
        "## Portfolio Metrics",
        "",
        "| Variant | CAGR | Max DD | Sharpe | Sortino | PF | Win Rate | Trades | Avg Cash | CAGR Delta | DD Delta | Sharpe Delta |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["variant"]),
                    fmt_pct(row.get("cagr")),
                    fmt_pct(row.get("max_drawdown")),
                    fmt_num(row.get("sharpe_ratio")),
                    fmt_num(row.get("sortino_ratio")),
                    fmt_num(row.get("profit_factor")),
                    fmt_pct(row.get("win_rate")),
                    fmt_num(row.get("closed_trades")),
                    fmt_pct(row.get("avg_cash_pct")),
                    fmt_pct(row.get("cagr_delta")),
                    fmt_pct(row.get("max_drawdown_delta")),
                    fmt_num(row.get("sharpe_delta")),
                ]
            )
            + " |"
        )

    lines.extend(["", "## Financial Year Returns", "", "| FY | " + " | ".join(str(row["variant"]) for row in rows) + " |", "| --- | " + " | ".join("---:" for _ in rows) + " |"])
    by_key: dict[tuple[str, str], dict[str, object]] = {(str(row["variant"]), str(row["financial_year"])): row for row in fy_rows}
    years = sorted({str(row["financial_year"]) for row in fy_rows})
    for year in years:
        values = [fmt_pct(by_key.get((str(row["variant"]), year), {}).get("return_pct")) for row in rows]
        lines.append(f"| {year} | " + " | ".join(values) + " |")

    lines.extend(
        [
            "",
            "## Robustness Read",
            "",
            f"- Variants tested: {payload['robustness']['variants_tested']}",
            f"- Variants beating baseline CAGR: {payload['robustness']['variants_beating_cagr']}",
            f"- Variants improving max drawdown: {payload['robustness']['variants_improving_drawdown']}",
            f"- Variants improving Sharpe: {payload['robustness']['variants_improving_sharpe']}",
            f"- Best CAGR variant: {payload['robustness']['best_cagr_variant']}",
            f"- Best drawdown variant: {payload['robustness']['best_drawdown_variant']}",
            f"- Best Sharpe variant: {payload['robustness']['best_sharpe_variant']}",
            "",
            "## Verdict",
            "",
            str(payload["verdict"]),
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    args = parse_args()
    angel_url = os.environ.get("ANGEL_DATABASE_URL")
    if not angel_url:
        raise RuntimeError("ANGEL_DATABASE_URL is required.")
    engine = create_engine(angel_url, future=True, pool_pre_ping=True)
    weights = parse_weights(args.weights)

    baseline_recs = load_baseline_recommendations(engine, args.pilot_schema, args.start_date, args.end_date)
    features_for_symbols = load_features_and_sector_returns(engine, args.pilot_schema, args.start_date, args.end_date, 0.40, 0.60)
    symbols = {str(row["symbol"]) for row in baseline_recs} | set(features_for_symbols["symbol"].dropna().astype(str).unique())
    prices = load_prices(engine, args.pilot_schema, symbols, args.start_date, args.end_date)

    baseline_result = run_rolling_10(
        "baseline_3m_rank",
        baseline_recs,
        prices,
        start_date=args.start_date,
        end_date=args.end_date,
        initial_capital=args.initial_capital,
        portfolio_size=args.portfolio_size,
        weekly_picks=args.weekly_picks,
        holding_period=args.holding_period,
    )
    baseline_metrics = baseline_result["metrics"]

    summary_rows: list[dict[str, object]] = [
        summarize_variant(
            name="baseline_3m_rank",
            weight_1m=None,
            weight_3m=None,
            result=baseline_result,
            recommendation_rows=len(baseline_recs),
            baseline_metrics=baseline_metrics,
            overlap_rows=None,
        )
    ]
    fy_rows = fy_returns(baseline_result["equity_curve"], "baseline_3m_rank")
    all_equity = list(baseline_result["equity_curve"])
    all_trades = list(baseline_result["trades"])
    overlap_summary_rows: list[dict[str, object]] = []

    for weight_1m, weight_3m in weights:
        name = variant_name(weight_1m, weight_3m)
        features = load_features_and_sector_returns(engine, args.pilot_schema, args.start_date, args.end_date, weight_1m, weight_3m)
        scores = score_frame(features, "sector_rank_1m3m", "score_1m3m")
        recs = generate_recommendations(scores, "score_1m3m", args.minimum_score, args.top_n, f"{MODEL}_{name}")
        result = run_rolling_10(
            name,
            recs,
            prices,
            start_date=args.start_date,
            end_date=args.end_date,
            initial_capital=args.initial_capital,
            portfolio_size=args.portfolio_size,
            weekly_picks=args.weekly_picks,
            holding_period=args.holding_period,
        )
        overlap_rows = recommendation_overlap(baseline_recs, recs)
        summary_rows.append(
            summarize_variant(
                name=name,
                weight_1m=weight_1m,
                weight_3m=weight_3m,
                result=result,
                recommendation_rows=len(recs),
                baseline_metrics=baseline_metrics,
                overlap_rows=overlap_rows,
            )
        )
        fy_rows.extend(fy_returns(result["equity_curve"], name))
        all_equity.extend(result["equity_curve"])
        all_trades.extend(result["trades"])
        for row in overlap_rows:
            overlap_summary_rows.append({"variant": name, **row})

    tested = [row for row in summary_rows if row["variant"] != "baseline_3m_rank"]
    variants_beating_cagr = sum(1 for row in tested if float(row["cagr_delta"] or 0) > 0)
    variants_improving_drawdown = sum(1 for row in tested if float(row["max_drawdown_delta"] or 0) > 0)
    variants_improving_sharpe = sum(1 for row in tested if float(row["sharpe_delta"] or 0) > 0)
    robustness = {
        "variants_tested": len(tested),
        "variants_beating_cagr": variants_beating_cagr,
        "variants_improving_drawdown": variants_improving_drawdown,
        "variants_improving_sharpe": variants_improving_sharpe,
        "best_cagr_variant": max(tested, key=lambda row: float(row["cagr"] or -999))["variant"],
        "best_drawdown_variant": max(tested, key=lambda row: float(row["max_drawdown"] or -999))["variant"],
        "best_sharpe_variant": max(tested, key=lambda row: float(row["sharpe_ratio"] or -999))["variant"],
    }
    verdict = (
        "Neighborhood is robust: every tested 1M/3M mix improves CAGR, max drawdown, and Sharpe versus the 3M baseline."
        if variants_beating_cagr == len(tested) and variants_improving_drawdown == len(tested) and variants_improving_sharpe == len(tested)
        else "Neighborhood is mixed: treat 40/60 as promising but continue validation before promotion."
    )
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "parameters": {
            "start_date": args.start_date.isoformat(),
            "end_date": args.end_date.isoformat(),
            "initial_capital": args.initial_capital,
            "weights": [{"weight_1m": left, "weight_3m": right} for left, right in weights],
            "minimum_score": args.minimum_score,
            "top_n": args.top_n,
            "portfolio_size": args.portfolio_size,
            "weekly_picks": args.weekly_picks,
            "holding_period": args.holding_period,
        },
        "summary": summary_rows,
        "robustness": robustness,
        "constraints": {
            "database_modified": False,
            "production_scoring_changed": False,
            "production_recommendations_changed": False,
            "strategy_rules_changed": False,
        },
        "verdict": verdict,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "sector_1m3m_parameter_neighborhood.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    (args.output_dir / "SECTOR_1M3M_PARAMETER_NEIGHBORHOOD.md").write_text(render_report(payload, summary_rows, fy_rows), encoding="utf-8")
    write_csv(args.output_dir / "sector_1m3m_parameter_neighborhood_summary.csv", summary_rows)
    write_csv(args.output_dir / "sector_1m3m_parameter_neighborhood_fy_returns.csv", fy_rows)
    write_csv(args.output_dir / "sector_1m3m_parameter_neighborhood_equity.csv", all_equity)
    write_csv(args.output_dir / "sector_1m3m_parameter_neighborhood_trades.csv", all_trades)
    write_csv(args.output_dir / "sector_1m3m_parameter_neighborhood_overlap.csv", overlap_summary_rows)
    print(json.dumps(payload, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
