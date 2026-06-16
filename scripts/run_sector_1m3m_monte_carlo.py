#!/usr/bin/env python3
"""Monte Carlo validation for baseline vs 1M/3M sector-rank trades.

Research-only. Uses existing trade ledgers from the sector 1M/3M experiment and
does not modify scores, recommendations, strategy rules, or databases.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
INPUT_TRADES = REPO_ROOT / "results" / "sector_1m3m_rank_experiment" / "sector_1m3m_trades.csv"
OUTPUT_DIR = REPO_ROOT / "results" / "sector_1m3m_monte_carlo"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Monte Carlo on baseline vs 1M/3M trade ledgers.")
    parser.add_argument("--trades-csv", type=Path, default=INPUT_TRADES)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--simulations", type=int, default=10_000)
    parser.add_argument("--initial-capital", type=float, default=1_000_000.0)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def load_trades(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    for column in ["entry_date", "exit_date"]:
        frame[column] = pd.to_datetime(frame[column])
    for column in ["net_return_pct", "net_pnl", "entry_value", "exit_value"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.sort_values(["strategy", "entry_date", "trade_id"])


def max_drawdown(values: np.ndarray) -> float:
    peaks = np.maximum.accumulate(values)
    drawdowns = values / peaks - 1.0
    return float(drawdowns.min())


def annualized_return(ending_equity: float, initial_capital: float, years: float) -> float:
    if ending_equity <= 0 or initial_capital <= 0 or years <= 0:
        return -1.0
    return (ending_equity / initial_capital) ** (1.0 / years) - 1.0


def sharpe_from_returns(returns: np.ndarray) -> float:
    if len(returns) < 2:
        return 0.0
    std = float(np.std(returns, ddof=1))
    if math.isclose(std, 0.0):
        return 0.0
    return float(np.mean(returns) / std * math.sqrt(252))


def run_path(pnls: np.ndarray, initial_capital: float, years: float) -> dict[str, float]:
    equity = initial_capital + np.cumsum(pnls)
    ending = float(equity[-1]) if len(equity) else initial_capital
    path_returns = np.divide(pnls, np.maximum(np.insert(equity[:-1], 0, initial_capital), 1e-9))
    return {
        "ending_equity": ending,
        "total_return": ending / initial_capital - 1.0,
        "cagr": annualized_return(ending, initial_capital, years),
        "max_drawdown": max_drawdown(np.insert(equity, 0, initial_capital)),
        "sharpe": sharpe_from_returns(path_returns),
    }


def simulate_variant(
    trades: pd.DataFrame,
    *,
    simulations: int,
    initial_capital: float,
    rng: np.random.Generator,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    pnls = trades["net_pnl"].dropna().to_numpy(dtype=float)
    returns = trades["net_return_pct"].dropna().to_numpy(dtype=float)
    start = trades["entry_date"].min()
    end = trades["exit_date"].max()
    years = max(1 / 252, (end - start).days / 365.25)
    count = len(pnls)
    rows: list[dict[str, object]] = []

    original = run_path(pnls, initial_capital, years)
    rows.append({"simulation_type": "original_order", "simulation_id": 0, **original})

    reversed_path = run_path(pnls[::-1], initial_capital, years)
    rows.append({"simulation_type": "reverse_order", "simulation_id": 0, **reversed_path})

    worst_first = run_path(np.sort(pnls), initial_capital, years)
    rows.append({"simulation_type": "worst_first", "simulation_id": 0, **worst_first})

    for index in range(1, simulations + 1):
        shuffled = rng.permutation(pnls)
        rows.append({"simulation_type": "shuffle", "simulation_id": index, **run_path(shuffled, initial_capital, years)})

        bootstrap = rng.choice(pnls, size=count, replace=True)
        rows.append({"simulation_type": "bootstrap", "simulation_id": index, **run_path(bootstrap, initial_capital, years)})

    diagnostics = [
        {
            "trade_count": count,
            "start_date": start.date().isoformat(),
            "end_date": end.date().isoformat(),
            "years": years,
            "mean_trade_pnl": float(np.mean(pnls)) if count else None,
            "median_trade_pnl": float(np.median(pnls)) if count else None,
            "mean_trade_return": float(np.mean(returns)) if count else None,
            "median_trade_return": float(np.median(returns)) if count else None,
            "negative_trade_rate": float(np.mean(returns < 0)) if count else None,
            "best_trade_return": float(np.max(returns)) if count else None,
            "worst_trade_return": float(np.min(returns)) if count else None,
        }
    ]
    return rows, diagnostics


def percentile_rows(results: pd.DataFrame) -> list[dict[str, object]]:
    rows = []
    percentiles = [1, 5, 10, 25, 50, 75, 90, 95, 99]
    metrics = ["ending_equity", "total_return", "cagr", "max_drawdown", "sharpe"]
    for (variant, simulation_type), frame in results.groupby(["variant", "simulation_type"]):
        if simulation_type in {"original_order", "reverse_order", "worst_first"}:
            continue
        for metric in metrics:
            values = frame[metric].dropna().to_numpy(dtype=float)
            for percentile in percentiles:
                rows.append(
                    {
                        "variant": variant,
                        "simulation_type": simulation_type,
                        "metric": metric,
                        "percentile": percentile,
                        "value": float(np.percentile(values, percentile)),
                    }
                )
    return rows


def distribution_rows(results: pd.DataFrame, metric: str, bins: list[float]) -> list[dict[str, object]]:
    rows = []
    labels = []
    for left, right in zip(bins[:-1], bins[1:]):
        labels.append(f"[{left:.2f},{right:.2f})")
    for (variant, simulation_type), frame in results.groupby(["variant", "simulation_type"]):
        if simulation_type in {"original_order", "reverse_order", "worst_first"}:
            continue
        values = frame[metric].dropna().to_numpy(dtype=float)
        counts, _ = np.histogram(values, bins=bins)
        for label, count in zip(labels, counts):
            rows.append(
                {
                    "variant": variant,
                    "simulation_type": simulation_type,
                    "metric": metric,
                    "bucket": label,
                    "count": int(count),
                    "frequency": int(count) / len(values) if len(values) else None,
                }
            )
    return rows


def summary_rows(results: pd.DataFrame) -> list[dict[str, object]]:
    rows = []
    for (variant, simulation_type), frame in results.groupby(["variant", "simulation_type"]):
        rows.append(
            {
                "variant": variant,
                "simulation_type": simulation_type,
                "runs": int(len(frame)),
                "median_cagr": float(frame["cagr"].median()),
                "p05_cagr": float(np.percentile(frame["cagr"], 5)),
                "p95_cagr": float(np.percentile(frame["cagr"], 95)),
                "median_max_drawdown": float(frame["max_drawdown"].median()),
                "p05_max_drawdown": float(np.percentile(frame["max_drawdown"], 5)),
                "p95_max_drawdown": float(np.percentile(frame["max_drawdown"], 95)),
                "prob_negative_total_return": float((frame["total_return"] < 0).mean()),
                "prob_cagr_below_15": float((frame["cagr"] < 0.15).mean()),
                "prob_drawdown_worse_25": float((frame["max_drawdown"] < -0.25).mean()),
                "median_ending_equity": float(frame["ending_equity"].median()),
                "p05_ending_equity": float(np.percentile(frame["ending_equity"], 5)),
            }
        )
    return rows


def comparison(summary: list[dict[str, object]]) -> dict[str, object]:
    by_key = {(row["variant"], row["simulation_type"]): row for row in summary}
    out: dict[str, object] = {}
    for simulation_type in ["shuffle", "bootstrap"]:
        base = by_key.get(("baseline_3m_rank", simulation_type))
        exp = by_key.get(("sector_1m3m_40_60_rank", simulation_type))
        if not base or not exp:
            continue
        out[simulation_type] = {
            "median_cagr_delta": exp["median_cagr"] - base["median_cagr"],
            "p05_cagr_delta": exp["p05_cagr"] - base["p05_cagr"],
            "median_drawdown_delta": exp["median_max_drawdown"] - base["median_max_drawdown"],
            "p05_ending_equity_delta": exp["p05_ending_equity"] - base["p05_ending_equity"],
            "prob_cagr_below_15_delta": exp["prob_cagr_below_15"] - base["prob_cagr_below_15"],
            "prob_drawdown_worse_25_delta": exp["prob_drawdown_worse_25"] - base["prob_drawdown_worse_25"],
        }
    return out


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
    return "n/a" if value is None else f"{float(value) * 100:.2f}%"


def money(value: object) -> str:
    return "n/a" if value is None else f"{float(value):,.0f}"


def render_report(payload: dict[str, object]) -> str:
    rows = payload["summary_rows"]
    comparison_payload = payload["comparison"]
    lines = [
        "# Sector 1M/3M Monte Carlo Validation",
        "",
        "Research-only Monte Carlo. Uses completed trade net PnL from the sector rank experiment, compounded additively against portfolio equity.",
        "",
        f"- Simulations per stochastic test: {payload['parameters']['simulations']:,}",
        f"- Initial capital: {money(payload['parameters']['initial_capital'])}",
        "- Tests: original order, reverse order, worst-first, trade-order shuffle, trade bootstrap with replacement.",
        "",
        "## Summary",
        "",
        "| Variant | Test | Median CAGR | 5th pct CAGR | Median Max DD | 5th pct Ending Equity | P(CAGR < 15%) | P(DD < -25%) |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        if row["simulation_type"] not in {"shuffle", "bootstrap"}:
            continue
        lines.append(
            f"| {row['variant']} | {row['simulation_type']} | {pct(row['median_cagr'])} | {pct(row['p05_cagr'])} | "
            f"{pct(row['median_max_drawdown'])} | {money(row['p05_ending_equity'])} | "
            f"{pct(row['prob_cagr_below_15'])} | {pct(row['prob_drawdown_worse_25'])} |"
        )
    lines.extend(["", "## Baseline vs 1M/3M Deltas", "", "| Test | Median CAGR Delta | 5th pct CAGR Delta | Median DD Delta | 5th pct Equity Delta |", "| --- | ---: | ---: | ---: | ---: |"])
    for test, row in comparison_payload.items():
        lines.append(
            f"| {test} | {pct(row['median_cagr_delta'])} | {pct(row['p05_cagr_delta'])} | "
            f"{pct(row['median_drawdown_delta'])} | {money(row['p05_ending_equity_delta'])} |"
        )
    verdict = payload["verdict"]
    lines.extend(["", "## Verdict", "", verdict])
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    if args.simulations < 100:
        raise RuntimeError("Use at least 100 simulations.")
    trades = load_trades(args.trades_csv)
    rng = np.random.default_rng(args.seed)
    all_results: list[dict[str, object]] = []
    diagnostics: list[dict[str, object]] = []
    for variant, frame in trades.groupby("strategy"):
        rows, diag = simulate_variant(frame, simulations=args.simulations, initial_capital=args.initial_capital, rng=rng)
        for row in rows:
            row["variant"] = variant
        for row in diag:
            row["variant"] = variant
        all_results.extend(rows)
        diagnostics.extend(diag)

    results = pd.DataFrame(all_results)
    summary = summary_rows(results)
    percentiles = percentile_rows(results)
    cagr_distribution = distribution_rows(results, "cagr", [-1, -0.25, 0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.60, 1.0, 2.0])
    drawdown_distribution = distribution_rows(results, "max_drawdown", [-1, -0.50, -0.40, -0.30, -0.25, -0.20, -0.15, -0.10, -0.05, 0.0])
    comparison_payload = comparison(summary)
    shuffle = comparison_payload.get("shuffle", {})
    bootstrap = comparison_payload.get("bootstrap", {})
    verdict = (
        "1M/3M passes Monte Carlo lower-tail validation versus baseline."
        if shuffle.get("p05_cagr_delta", -1) > 0 and bootstrap.get("p05_cagr_delta", -1) > 0
        else "1M/3M does not clearly improve the Monte Carlo lower tail; review before promotion."
    )
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "parameters": {
            "simulations": args.simulations,
            "initial_capital": args.initial_capital,
            "seed": args.seed,
            "trades_csv": str(args.trades_csv),
        },
        "diagnostics": diagnostics,
        "summary_rows": summary,
        "comparison": comparison_payload,
        "constraints": {
            "database_modified": False,
            "strategy_rules_changed": False,
            "production_scoring_changed": False,
            "production_recommendations_changed": False,
        },
        "verdict": verdict,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "sector_1m3m_monte_carlo_summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    (args.output_dir / "SECTOR_1M3M_MONTE_CARLO_REPORT.md").write_text(render_report(payload), encoding="utf-8")
    write_csv(args.output_dir / "sector_1m3m_monte_carlo_runs.csv", all_results)
    write_csv(args.output_dir / "sector_1m3m_monte_carlo_percentiles.csv", percentiles)
    write_csv(args.output_dir / "sector_1m3m_monte_carlo_cagr_distribution.csv", cagr_distribution)
    write_csv(args.output_dir / "sector_1m3m_monte_carlo_drawdown_distribution.csv", drawdown_distribution)
    write_csv(args.output_dir / "sector_1m3m_monte_carlo_diagnostics.csv", diagnostics)
    print(json.dumps(payload, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
