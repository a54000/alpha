#!/usr/bin/env python3
"""Run portfolio-level backtests for Swing V1, V2, and V2.1."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.backtesting.portfolio_backtest import PortfolioBacktesterV1, PortfolioBacktestConfig
from db.session import build_session_factory


MODELS = {
    "V1": "swing",
    "V2": "swing_v2",
    "V2.1": "swing_v2_1",
}


def write_equity_curves(results: dict[str, dict[str, object]], output_path: Path) -> None:
    curves: dict[str, dict[str, dict[str, object]]] = {}
    all_dates: set[str] = set()
    for label, result in results.items():
        model_curve = {row["date"]: row for row in result["equity_curve"]}
        curves[label] = model_curve
        all_dates.update(model_curve)

    output_path.parent.mkdir(exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "date",
                "V1_equity",
                "V1_cash",
                "V1_positions",
                "V2_equity",
                "V2_cash",
                "V2_positions",
                "V2_1_equity",
                "V2_1_cash",
                "V2_1_positions",
            ]
        )
        for curve_date in sorted(all_dates):
            row = [curve_date]
            for label in ("V1", "V2", "V2.1"):
                point = curves[label].get(curve_date, {})
                row.extend(
                    [
                        point.get("equity"),
                        point.get("cash"),
                        point.get("position_count"),
                    ]
                )
            writer.writerow(row)


def compact_results(results: dict[str, dict[str, object]]) -> dict[str, object]:
    return {
        label: {
            "model": result["model"],
            "config": result["config"],
            "metrics": result["metrics"],
            "closed_trade_count": result["closed_trade_count"],
            "closed_trades": result["closed_trades"],
            "closed_trades_sample": result["closed_trades_sample"],
        }
        for label, result in results.items()
    }


def main() -> int:
    backtester = PortfolioBacktesterV1(build_session_factory())
    results = {
        label: backtester.run(PortfolioBacktestConfig(model=model))
        for label, model in MODELS.items()
    }

    report_path = Path("reports/portfolio_backtest_results.json")
    report_path.parent.mkdir(exist_ok=True)
    report_path.write_text(json.dumps(compact_results(results), indent=2, default=str), encoding="utf-8")

    write_equity_curves(results, Path("reports/portfolio_equity_curves.csv"))
    print(f"Wrote {report_path}")
    print("Wrote reports/portfolio_equity_curves.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
