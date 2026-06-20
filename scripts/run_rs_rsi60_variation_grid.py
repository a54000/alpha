#!/usr/bin/env python3
"""Run a research-only parameter grid for RS improvement + 60-minute RSI."""

from __future__ import annotations

import csv
import json
import sys
from dataclasses import replace
from datetime import date, datetime, time, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.run_rs_rsi60_experiment import (  # noqa: E402
    Config,
    build_price_dict,
    build_signals,
    load_daily_prices,
    load_entry_prices,
    load_nifty50_daily,
    load_rsi60,
    make_engine_from_env,
    pct,
    run_backtest,
    write_csv,
)

OUTPUT_DIR = REPO_ROOT / "results" / "rs_rsi60_variation_grid"
DOC_PATH = REPO_ROOT / "docs" / "RS_RSI60_VARIATION_GRID.md"


def score_variant(metrics: dict[str, object]) -> float:
    cagr = float(metrics["cagr"])
    sharpe = float(metrics["sharpe_ratio"])
    drawdown = abs(float(metrics["max_drawdown"]))
    trades = int(metrics["closed_trades"])
    trade_penalty = 0.10 if trades < 150 else 0.0
    return sharpe + cagr - drawdown - trade_penalty


def render_report(payload: dict[str, object]) -> str:
    best = payload["best"]
    rows = payload["variants"]
    lines = [
        "# RS + 60-Minute RSI Variation Grid",
        "",
        "Research-only parameter neighborhood test. No production strategy or database state was changed.",
        "",
        "## Best Variant",
        "",
        f"- RS lookback: {best['rs_lookback']} sessions",
        f"- Improvement lookback: {best['rs_improvement_lookback']} sessions",
        f"- RSI cap: {best['rsi_threshold']}",
        f"- Minimum relative-strength spread: {best['min_rs_spread']}",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| CAGR | {pct(best['cagr'])} |",
        f"| Total return | {pct(best['total_return'])} |",
        f"| Max drawdown | {pct(best['max_drawdown'])} |",
        f"| Sharpe | {best['sharpe_ratio']:.2f} |",
        f"| Profit factor | {best['profit_factor']:.2f} |" if best["profit_factor"] is not None else "| Profit factor | n/a |",
        f"| Trades | {best['closed_trades']} |",
        "",
        "## Top 15 Variants",
        "",
        "| Rank | RS | Improve | RSI Cap | Min RS | CAGR | Max DD | Sharpe | PF | Trades | Score |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for rank, row in enumerate(rows[:15], start=1):
        pf = f"{row['profit_factor']:.2f}" if row["profit_factor"] is not None else "n/a"
        lines.append(
            f"| {rank} | {row['rs_lookback']} | {row['rs_improvement_lookback']} | {row['rsi_threshold']:.0f} | "
            f"{row['min_rs_spread']} | {pct(row['cagr'])} | {pct(row['max_drawdown'])} | "
            f"{row['sharpe_ratio']:.2f} | {pf} | {row['closed_trades']} | {row['selection_score']:.2f} |"
        )
    lines.extend(
        [
            "",
            "## Verdict",
            "",
            payload["verdict"],
            "",
            "## Artifacts",
            "",
            "- `results/rs_rsi60_variation_grid/variation_grid.csv`",
            "- `results/rs_rsi60_variation_grid/summary.json`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    base = Config(
        start_date=date(2022, 5, 25),
        end_date=date(2026, 6, 11),
        initial_capital=1_000_000.0,
        pilot_schema="pilot_phase2a",
        portfolio_size=10,
        weekly_picks=5,
        holding_period=20,
        rs_lookback=66,
        rs_improvement_lookback=5,
        rsi_threshold=60.0,
        entry_time=time(10, 30),
        min_rs_spread=None,
    )
    engine = make_engine_from_env()
    daily = load_daily_prices(engine, base.pilot_schema, base.start_date, base.end_date)
    symbols = set(map(str, daily["symbol"].unique()))
    nifty = load_nifty50_daily(engine, base.start_date, base.end_date)
    rsi60 = load_rsi60(engine, symbols, base.start_date, base.end_date)
    prices = build_price_dict(daily, base.start_date, base.end_date)
    entry_prices = load_entry_prices(engine, symbols, base.start_date, base.end_date, base.entry_time)

    variants: list[dict[str, object]] = []
    for rs_lookback in [66, 88]:
        for improvement in [3, 5, 10]:
            for rsi_threshold in [55.0, 60.0, 65.0]:
                for min_rs_spread in [0.0]:
                    cfg = replace(
                        base,
                        rs_lookback=rs_lookback,
                        rs_improvement_lookback=improvement,
                        rsi_threshold=rsi_threshold,
                        min_rs_spread=min_rs_spread,
                    )
                    signals = build_signals(daily, nifty, rsi60, cfg)
                    result = run_backtest(signals, prices, entry_prices, cfg)
                    metrics = result["metrics"]
                    variants.append(
                        {
                            "rs_lookback": rs_lookback,
                            "rs_improvement_lookback": improvement,
                            "rsi_threshold": rsi_threshold,
                            "min_rs_spread": min_rs_spread if min_rs_spread is not None else "none",
                            "signal_count": len(signals),
                            "selection_score": score_variant(metrics),
                            **metrics,
                        }
                    )

    variants.sort(key=lambda row: (float(row["selection_score"]), float(row["sharpe_ratio"]), float(row["cagr"])), reverse=True)
    best = variants[0]
    verdict = (
        "Best variant is still weaker than SectorEdge 10 on risk-adjusted performance. Treat RS+RSI as a possible filter/overlay, not a replacement."
        if float(best["sharpe_ratio"]) < 1.0 or float(best["max_drawdown"]) < -0.20
        else "Best variant is promising enough for deeper validation against SectorEdge 10."
    )
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "variant_count": len(variants),
        "best": best,
        "variants": variants,
        "verdict": verdict,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(OUTPUT_DIR / "variation_grid.csv", variants)
    (OUTPUT_DIR / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOC_PATH.write_text(render_report(payload), encoding="utf-8")
    print(json.dumps({"status": "success", "variant_count": len(variants), "best": best, "doc": str(DOC_PATH)}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
