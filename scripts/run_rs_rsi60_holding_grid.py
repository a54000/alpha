#!/usr/bin/env python3
"""Holding-period grid for the best RS + 60-minute RSI candidate."""

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
    load_daily_prices,
    load_entry_prices,
    make_engine_from_env,
    pct,
    run_backtest,
    write_csv,
)

OUTPUT_DIR = REPO_ROOT / "results" / "rs_rsi60_holding_grid"
DOC_PATH = REPO_ROOT / "docs" / "RS_RSI60_HOLDING_GRID.md"
BEST_SIGNALS_CSV = REPO_ROOT / "results" / "rs_rsi60_best_88_10" / "signals.csv"


def load_signals(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open("r", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rows.append(
                {
                    "date": date.fromisoformat(row["date"]),
                    "rank": int(row["rank"]),
                    "symbol": row["symbol"],
                    "score": float(row["score"]),
                    "sector": row.get("sector") or None,
                    "stock_return": float(row["stock_return"]),
                    "nifty_return": float(row["nifty_return"]),
                    "rs_spread": float(row["rs_spread"]),
                    "rs_improvement": float(row["rs_improvement"]),
                    "rsi_60m_14": float(row["rsi_60m_14"]),
                }
            )
    return rows


def render_report(rows: list[dict[str, object]]) -> str:
    best = rows[0]
    lines = [
        "# RS + RSI Holding-Period Grid",
        "",
        "Research-only test of shorter planned exits for the best RS/RSI candidate.",
        "",
        "Signal remains unchanged: 88-day relative strength vs Nifty 50, 10-day improvement, positive RS, 60-minute RSI below 60.",
        "",
        "## Best Short Hold",
        "",
        f"- Holding period: {best['holding_period']} trading days",
        f"- CAGR: {pct(best['cagr'])}",
        f"- Max drawdown: {pct(best['max_drawdown'])}",
        f"- Sharpe: {best['sharpe_ratio']:.2f}",
        "",
        "## Results",
        "",
        "| Hold Days | CAGR | Total Return | Max DD | Sharpe | Sortino | PF | Win Rate | Trades | Avg Cash |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in sorted(rows, key=lambda item: int(item["holding_period"])):
        pf = f"{row['profit_factor']:.2f}" if row["profit_factor"] is not None else "n/a"
        lines.append(
            f"| {row['holding_period']} | {pct(row['cagr'])} | {pct(row['total_return'])} | "
            f"{pct(row['max_drawdown'])} | {row['sharpe_ratio']:.2f} | {row['sortino_ratio']:.2f} | "
            f"{pf} | {pct(row['win_rate'])} | {row['closed_trades']} | {pct(row['avg_cash_pct'])} |"
        )
    lines.extend(
        [
            "",
            "## Verdict",
            "",
            "Compare the best short-hold result with the 20-day RS/RSI result before promotion. Shorter holds are useful only if they improve drawdown/Sharpe enough to justify lower compounding.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    base = Config(
        start_date=date(2022, 5, 25),
        end_date=date(2026, 6, 11),
        initial_capital=1_000_000.0,
        pilot_schema="pilot_phase2a",
        portfolio_size=10,
        weekly_picks=5,
        holding_period=20,
        rs_lookback=88,
        rs_improvement_lookback=10,
        rsi_threshold=60.0,
        entry_time=time(10, 30),
        min_rs_spread=0.0,
    )
    engine = make_engine_from_env()
    daily = load_daily_prices(engine, base.pilot_schema, base.start_date, base.end_date)
    symbols = set(map(str, daily["symbol"].unique()))
    signals = load_signals(BEST_SIGNALS_CSV)
    prices = build_price_dict(daily, base.start_date, base.end_date)
    entry_prices = load_entry_prices(engine, symbols, base.start_date, base.end_date, base.entry_time)

    rows: list[dict[str, object]] = []
    outputs: dict[str, object] = {}
    for holding_period in [10, 11, 12, 20]:
        cfg = replace(base, holding_period=holding_period)
        result = run_backtest(signals, prices, entry_prices, cfg)
        metrics = result["metrics"]
        row = {"holding_period": holding_period, **metrics}
        rows.append(row)
        outputs[str(holding_period)] = {
            "metrics": metrics,
            "fy_returns": result["fy_returns"],
        }
        write_csv(OUTPUT_DIR / f"trades_hold{holding_period}.csv", result["trades"])
        write_csv(OUTPUT_DIR / f"equity_hold{holding_period}.csv", result["equity_curve"])
        write_csv(OUTPUT_DIR / f"fy_hold{holding_period}.csv", result["fy_returns"])
    rows.sort(key=lambda item: (float(item["sharpe_ratio"]), float(item["cagr"])), reverse=True)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(OUTPUT_DIR / "holding_grid.csv", rows)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "parameters": {
            "rs_lookback": 88,
            "rs_improvement_lookback": 10,
            "rsi_threshold": 60.0,
            "min_rs_spread": 0.0,
            "holding_periods": [10, 11, 12, 20],
        },
        "best_by_sharpe": rows[0],
        "results": rows,
        "detail": outputs,
    }
    (OUTPUT_DIR / "summary.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOC_PATH.write_text(render_report(rows), encoding="utf-8")
    print(json.dumps({"status": "success", "best_by_sharpe": rows[0], "doc": str(DOC_PATH)}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
