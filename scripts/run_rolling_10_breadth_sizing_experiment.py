#!/usr/bin/env python3
"""Research-only Rolling 10 breadth sizing experiment.

Variant tested:
  - Baseline: frozen recommendations, rolling 10 slots, planned 20 trading day exit.
  - Breadth sizing: same rules, but entries with low sector breadth use half slot size.

No scoring, recommendation generation, or database state is changed.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import statistics
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.api.trade_analysis_service import (  # noqa: E402
    AnalysisPosition,
    buy_side_charges,
    build_trade_row,
    next_trading_day_after,
    nth_trading_day_after,
    positions_value,
    symbol_dates,
    total_charges,
    weekly_signal_dates,
)


MODEL = "swing_v2_1"
OUTPUT_DIR = REPO_ROOT / "results" / "breadth_sizing_experiment"


@dataclass(frozen=True)
class ExperimentConfig:
    variant: str
    name: str
    low_sector_breadth_multiplier: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Rolling 10 low-breadth half-size portfolio experiment.")
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2022, 5, 25))
    parser.add_argument("--end-date", type=date.fromisoformat, default=date(2026, 6, 11))
    parser.add_argument("--initial-capital", type=float, default=1_000_000.0)
    parser.add_argument("--pilot-schema", default="pilot_phase2a")
    parser.add_argument("--portfolio-size", type=int, default=10)
    parser.add_argument("--weekly-picks", type=int, default=5)
    parser.add_argument("--holding-period", type=int, default=20)
    parser.add_argument("--low-breadth-threshold", type=float, default=0.40)
    parser.add_argument("--low-breadth-multiplier", type=float, default=0.50)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    return parser.parse_args()


def pct(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def load_recommendations(engine, schema: str, start_date: date, end_date: date) -> list[dict[str, object]]:
    query = text(
        f"""
        SELECT
            r.date,
            r.rank,
            r.symbol,
            r.score,
            r.sector,
            f.ema200_extension,
            f.prior_20d_return
        FROM {schema}.recommendations_daily r
        LEFT JOIN {schema}.features_daily f
          ON f.symbol = r.symbol
         AND f.date = r.date
        WHERE r.model = :model
          AND r.date BETWEEN :start_date AND :end_date
        ORDER BY r.date ASC, r.rank ASC, r.symbol ASC
        """
    )
    with engine.connect() as connection:
        rows = connection.execute(query, {"model": MODEL, "start_date": start_date, "end_date": end_date}).mappings().all()
    return [
        {
            "date": row["date"],
            "rank": int(row["rank"]),
            "symbol": str(row["symbol"]),
            "score": float(row["score"]) if row["score"] is not None else None,
            "sector": row["sector"],
            "ema200_extension": float(row["ema200_extension"]) if row["ema200_extension"] is not None else None,
            "prior_20d_return": float(row["prior_20d_return"]) if row["prior_20d_return"] is not None else None,
        }
        for row in rows
    ]


def load_prices(engine, schema: str, symbols: set[str], start_date: date, end_date: date) -> dict[str, dict[date, dict[str, float]]]:
    if not symbols:
        return {}
    query = text(
        f"""
        SELECT symbol, date, open, high, low, close
        FROM {schema}.daily_bars_clean
        WHERE symbol = ANY(:symbols)
          AND date BETWEEN :start_date AND :end_date
        ORDER BY symbol ASC, date ASC
        """
    )
    with engine.connect() as connection:
        rows = connection.execute(query, {"symbols": list(symbols), "start_date": start_date, "end_date": end_date}).mappings().all()
    prices: dict[str, dict[date, dict[str, float]]] = {}
    for row in rows:
        prices.setdefault(str(row["symbol"]), {})[row["date"]] = {
            "open": float(row["open"]),
            "high": float(row["high"]) if row["high"] is not None else float(row["close"]),
            "low": float(row["low"]) if row["low"] is not None else float(row["close"]),
            "close": float(row["close"]),
        }
    return prices


def load_sector_breadth(engine, schema: str, start_date: date, end_date: date) -> dict[tuple[date, str], dict[str, object]]:
    query = text(
        f"""
        SELECT
            date,
            sector,
            COUNT(*) AS total_symbols,
            COUNT(*) FILTER (WHERE prior_20d_return > 0) AS positive_20d,
            COUNT(*) FILTER (WHERE close > ema_50) AS above_ema50,
            COUNT(*) FILTER (WHERE close > ema_200) AS above_ema200
        FROM {schema}.features_daily
        WHERE date BETWEEN :start_date AND :end_date
          AND sector IS NOT NULL
          AND close IS NOT NULL
        GROUP BY date, sector
        """
    )
    with engine.connect() as connection:
        rows = connection.execute(query, {"start_date": start_date, "end_date": end_date}).mappings().all()
    output: dict[tuple[date, str], dict[str, object]] = {}
    for row in rows:
        total = int(row["total_symbols"] or 0)
        output[(row["date"], str(row["sector"]))] = {
            "sector_total_symbols": total,
            "sector_positive_20d_pct": pct(int(row["positive_20d"] or 0), total),
            "sector_above_ema50_pct": pct(int(row["above_ema50"] or 0), total),
            "sector_above_ema200_pct": pct(int(row["above_ema200"] or 0), total),
        }
    return output


def all_trading_dates(prices: dict[str, dict[date, dict[str, float]]]) -> list[date]:
    return sorted({day for symbol_prices in prices.values() for day in symbol_prices})


def returns_from_equity(equity_curve: list[dict[str, object]]) -> list[float]:
    returns = []
    previous = None
    for row in equity_curve:
        equity = float(row["equity"])
        if previous and previous > 0:
            returns.append(equity / previous - 1.0)
        previous = equity
    return returns


def max_drawdown(equity_values: list[float]) -> float:
    peak = equity_values[0] if equity_values else 0.0
    drawdown = 0.0
    for value in equity_values:
        peak = max(peak, value)
        if peak:
            drawdown = min(drawdown, value / peak - 1.0)
    return drawdown


def metrics(initial_capital: float, equity_curve: list[dict[str, object]], trades: list[dict[str, object]], turnover: float) -> dict[str, object]:
    if not equity_curve:
        return {}
    values = [float(row["equity"]) for row in equity_curve]
    ending = values[-1]
    returns = returns_from_equity(equity_curve)
    downside = [value for value in returns if value < 0]
    days = max(1, len(equity_curve))
    gross_profit = sum(float(row["net_pnl"]) for row in trades if float(row["net_pnl"]) > 0)
    gross_loss = abs(sum(float(row["net_pnl"]) for row in trades if float(row["net_pnl"]) < 0))
    wins = [row for row in trades if float(row["net_pnl"]) > 0]
    stdev = statistics.stdev(returns) if len(returns) > 1 else 0.0
    downside_stdev = statistics.stdev(downside) if len(downside) > 1 else 0.0
    return {
        "ending_equity": ending,
        "total_return": ending / initial_capital - 1.0,
        "cagr": (ending / initial_capital) ** (252 / days) - 1.0 if ending > 0 else -1.0,
        "max_drawdown": max_drawdown(values),
        "sharpe_ratio": statistics.mean(returns) / stdev * math.sqrt(252) if stdev else 0.0,
        "sortino_ratio": statistics.mean(returns) / downside_stdev * math.sqrt(252) if downside_stdev else 0.0,
        "profit_factor": gross_profit / gross_loss if gross_loss else None,
        "win_rate": len(wins) / len(trades) if trades else 0.0,
        "closed_trades": len(trades),
        "turnover": turnover / initial_capital,
        "avg_cash_pct": statistics.mean([float(row["cash"]) / float(row["equity"]) for row in equity_curve if float(row["equity"])]) if equity_curve else 0.0,
        "avg_position_count": statistics.mean([int(row["position_count"]) for row in equity_curve]) if equity_curve else 0.0,
    }


def financial_year_label(day: date) -> str:
    start_year = day.year if day.month >= 4 else day.year - 1
    return f"FY{start_year}-{str(start_year + 1)[-2:]}"


def yearly_returns(equity_curve: list[dict[str, object]], variant: str) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in equity_curve:
        day = date.fromisoformat(str(row["date"]))
        grouped.setdefault(financial_year_label(day), []).append(row)
    rows = []
    for label, group in sorted(grouped.items()):
        group.sort(key=lambda item: str(item["date"]))
        start = float(group[0]["equity"])
        end = float(group[-1]["equity"])
        rows.append(
            {
                "variant": variant,
                "financial_year": label,
                "start_date": group[0]["date"],
                "end_date": group[-1]["date"],
                "start_equity": start,
                "end_equity": end,
                "return_pct": end / start - 1.0 if start else None,
                "max_drawdown": max_drawdown([float(row["equity"]) for row in group]),
            }
        )
    return rows


def run_simulation(
    config: ExperimentConfig,
    recommendations: list[dict[str, object]],
    prices: dict[str, dict[date, dict[str, float]]],
    breadth: dict[tuple[date, str], dict[str, object]],
    *,
    start_date: date,
    end_date: date,
    initial_capital: float,
    portfolio_size: int,
    weekly_picks: int,
    holding_period: int,
    low_breadth_threshold: float,
) -> dict[str, object]:
    dates = [day for day in all_trading_dates(prices) if start_date <= day <= end_date]
    recs_by_date: dict[date, list[dict[str, object]]] = {}
    for rec in recommendations:
        recs_by_date.setdefault(rec["date"], []).append(rec)
    for rows in recs_by_date.values():
        rows.sort(key=lambda row: (int(row["rank"]), str(row["symbol"])))

    entries_by_date: dict[date, tuple[date, list[dict[str, object]]]] = {}
    for signal_date in weekly_signal_dates(list(recs_by_date)):
        entry_date = next_trading_day_after(dates, signal_date)
        if entry_date:
            entries_by_date[entry_date] = (signal_date, recs_by_date[signal_date][:weekly_picks])

    cash = initial_capital
    positions: list[AnalysisPosition] = []
    trades: list[dict[str, object]] = []
    equity_curve: list[dict[str, object]] = []
    entry_log: list[dict[str, object]] = []
    turnover = 0.0
    trade_id = 1

    for current_date in dates:
        remaining: list[AnalysisPosition] = []
        closed_today: set[str] = set()
        for position in positions:
            close_price = prices.get(position.symbol, {}).get(current_date, {}).get("close")
            if current_date >= position.planned_exit_date and close_price is not None:
                row = build_trade_row(trade_id, position, current_date, close_price, symbol_dates(prices, position.symbol), config.variant)
                cash += float(row["exit_value"]) - (float(row["charges"]) - total_charges(position.buy_charges))
                turnover += float(row["exit_value"])
                trades.append({**row, "exit_reason": "planned_exit"})
                closed_today.add(position.symbol)
                trade_id += 1
            else:
                remaining.append(position)
        positions = remaining

        if current_date in entries_by_date:
            signal_date, candidates = entries_by_date[current_date]
            held = {position.symbol for position in positions}
            equity_at_open = cash + positions_value(positions, prices, current_date, "open")
            target_value = equity_at_open / portfolio_size
            for rec in candidates:
                symbol = str(rec["symbol"])
                sector = str(rec.get("sector") or "UNKNOWN")
                if len(positions) >= portfolio_size:
                    entry_log.append({"variant": config.variant, "entry_date": current_date.isoformat(), "symbol": symbol, "status": "skipped", "reason": "portfolio_full"})
                    continue
                if symbol in held or symbol in closed_today:
                    entry_log.append({"variant": config.variant, "entry_date": current_date.isoformat(), "symbol": symbol, "status": "skipped", "reason": "already_held_or_closed_today"})
                    continue
                open_price = prices.get(symbol, {}).get(current_date, {}).get("open")
                if open_price is None or open_price <= 0:
                    entry_log.append({"variant": config.variant, "entry_date": current_date.isoformat(), "symbol": symbol, "status": "skipped", "reason": "missing_entry_price"})
                    continue
                sector_breadth = breadth.get((current_date, sector), {})
                sector_positive = sector_breadth.get("sector_positive_20d_pct")
                low_breadth = sector_positive is not None and float(sector_positive) < low_breadth_threshold
                multiplier = config.low_sector_breadth_multiplier if low_breadth else 1.0
                allocation = min(target_value * multiplier, cash)
                if allocation <= 0:
                    entry_log.append({"variant": config.variant, "entry_date": current_date.isoformat(), "symbol": symbol, "status": "skipped", "reason": "insufficient_cash"})
                    continue
                buy_charges = buy_side_charges(allocation)
                if allocation + total_charges(buy_charges) > cash:
                    allocation = cash / (1.0 + (total_charges(buy_charges) / allocation if allocation else 0.0))
                    buy_charges = buy_side_charges(allocation)
                planned_exit = nth_trading_day_after(symbol_dates(prices, symbol), current_date, holding_period)
                if planned_exit is None:
                    entry_log.append({"variant": config.variant, "entry_date": current_date.isoformat(), "symbol": symbol, "status": "skipped", "reason": "missing_planned_exit"})
                    continue
                quantity = allocation / float(open_price)
                cash -= allocation + total_charges(buy_charges)
                turnover += allocation
                positions.append(
                    AnalysisPosition(
                        symbol=symbol,
                        sector=sector,
                        signal_date=signal_date,
                        entry_date=current_date,
                        entry_price=float(open_price),
                        quantity=quantity,
                        planned_exit_date=planned_exit,
                        rank=int(rec["rank"]),
                        score=float(rec["score"]) if rec.get("score") is not None else None,
                        entry_value=allocation,
                        buy_charges=buy_charges,
                    )
                )
                held.add(symbol)
                entry_log.append(
                    {
                        "variant": config.variant,
                        "signal_date": signal_date.isoformat(),
                        "entry_date": current_date.isoformat(),
                        "symbol": symbol,
                        "sector": sector,
                        "status": "entered",
                        "rank": int(rec["rank"]),
                        "score": rec.get("score"),
                        "target_value": target_value,
                        "allocation": allocation,
                        "allocation_multiplier": multiplier,
                        "low_sector_breadth": low_breadth,
                        **sector_breadth,
                    }
                )

        equity = cash + positions_value(positions, prices, current_date, "close")
        equity_curve.append(
            {
                "variant": config.variant,
                "date": current_date.isoformat(),
                "equity": equity,
                "cash": cash,
                "position_count": len(positions),
            }
        )

    if dates:
        final_date = dates[-1]
        for position in positions:
            close_price = prices.get(position.symbol, {}).get(final_date, {}).get("close")
            if close_price is None:
                continue
            row = build_trade_row(trade_id, position, final_date, close_price, symbol_dates(prices, position.symbol), config.variant)
            trades.append({**row, "exit_reason": "forced_final_exit"})
            cash += float(row["exit_value"]) - (float(row["charges"]) - total_charges(position.buy_charges))
            turnover += float(row["exit_value"])
            trade_id += 1
        equity_curve[-1]["equity"] = cash
        equity_curve[-1]["cash"] = cash
        equity_curve[-1]["position_count"] = 0

    return {
        "variant": config.variant,
        "name": config.name,
        "metrics": metrics(initial_capital, equity_curve, trades, turnover),
        "equity_curve": equity_curve,
        "trades": trades,
        "entry_log": entry_log,
        "financial_year_returns": yearly_returns(equity_curve, config.variant),
    }


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


def fmt_pct(value: object) -> str:
    return "n/a" if value is None else f"{float(value) * 100:.2f}%"


def fmt_num(value: object) -> str:
    return "n/a" if value is None else f"{float(value):.2f}"


def render_report(output: dict[str, object]) -> str:
    baseline = output["variants"]["rolling_10_baseline"]["metrics"]
    experiment = output["variants"]["rolling_10_low_sector_breadth_half_size"]["metrics"]
    fy_rows = output["financial_year_returns"]
    lines = [
        "# Rolling 10 Low-Breadth Half-Size Experiment",
        "",
        "Research-only experiment. Scoring, recommendations, ranking, holding period, and exit logic were not changed.",
        "",
        "## Rule Tested",
        "",
        "- Baseline: Rolling 10 slots, up to Top 5 weekly entries, 20 trading day planned exit.",
        "- Experiment: same as baseline, but when sector positive-20d breadth is below 40%, entry allocation is half of normal slot size.",
        "",
        "## Portfolio Metrics",
        "",
        "| Metric | Baseline | Low Breadth Half Size | Delta |",
        "| --- | ---: | ---: | ---: |",
    ]
    metric_defs = [
        ("cagr", "CAGR", True),
        ("total_return", "Total Return", True),
        ("max_drawdown", "Max Drawdown", True),
        ("sharpe_ratio", "Sharpe", False),
        ("sortino_ratio", "Sortino", False),
        ("profit_factor", "Profit Factor", False),
        ("win_rate", "Win Rate", True),
        ("closed_trades", "Closed Trades", False),
        ("avg_cash_pct", "Average Cash", True),
        ("avg_position_count", "Average Positions", False),
    ]
    for key, label, is_pct in metric_defs:
        base = baseline.get(key)
        exp = experiment.get(key)
        delta = float(exp) - float(base) if base is not None and exp is not None else None
        formatter = fmt_pct if is_pct else fmt_num
        lines.append(f"| {label} | {formatter(base)} | {formatter(exp)} | {formatter(delta)} |")
    lines.extend(["", "## FY Returns", "", "| FY | Baseline | Low Breadth Half Size | Delta |", "| --- | ---: | ---: | ---: |"])
    by_variant: dict[str, dict[str, dict[str, object]]] = {}
    for row in fy_rows:
        by_variant.setdefault(str(row["variant"]), {})[str(row["financial_year"])] = row
    for fy in sorted({str(row["financial_year"]) for row in fy_rows}):
        base = by_variant.get("rolling_10_baseline", {}).get(fy, {}).get("return_pct")
        exp = by_variant.get("rolling_10_low_sector_breadth_half_size", {}).get(fy, {}).get("return_pct")
        delta = float(exp) - float(base) if base is not None and exp is not None else None
        lines.append(f"| {fy} | {fmt_pct(base)} | {fmt_pct(exp)} | {fmt_pct(delta)} |")
    low_entries = output["entry_summary"]["low_breadth_entries"]
    lines.extend(
        [
            "",
            "## Entry Impact",
            "",
            f"- Low sector-breadth entries half-sized: {low_entries}",
            f"- Total baseline entries: {output['entry_summary']['baseline_entries']}",
            f"- Total experiment entries: {output['entry_summary']['experiment_entries']}",
            "",
            "## Verdict",
            "",
            str(output["verdict"]),
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
    recommendations = load_recommendations(engine, args.pilot_schema, args.start_date, args.end_date)
    symbols = {str(row["symbol"]) for row in recommendations}
    prices = load_prices(engine, args.pilot_schema, symbols, args.start_date, args.end_date)
    breadth = load_sector_breadth(engine, args.pilot_schema, args.start_date, args.end_date)

    configs = [
        ExperimentConfig("rolling_10_baseline", "Rolling 10 Baseline", 1.0),
        ExperimentConfig("rolling_10_low_sector_breadth_half_size", "Rolling 10 Low Sector Breadth Half Size", args.low_breadth_multiplier),
    ]
    results = {
        config.variant: run_simulation(
            config,
            recommendations,
            prices,
            breadth,
            start_date=args.start_date,
            end_date=args.end_date,
            initial_capital=args.initial_capital,
            portfolio_size=args.portfolio_size,
            weekly_picks=args.weekly_picks,
            holding_period=args.holding_period,
            low_breadth_threshold=args.low_breadth_threshold,
        )
        for config in configs
    }

    baseline = results["rolling_10_baseline"]["metrics"]
    experiment = results["rolling_10_low_sector_breadth_half_size"]["metrics"]
    verdict = (
        "Half-sizing low sector breadth improves drawdown/Sharpe with modest return cost; promote to next validation."
        if float(experiment["max_drawdown"]) > float(baseline["max_drawdown"]) and float(experiment["sharpe_ratio"]) > float(baseline["sharpe_ratio"])
        else "Half-sizing low sector breadth did not clearly improve portfolio quality; do not promote yet."
    )
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "parameters": {
            "start_date": args.start_date.isoformat(),
            "end_date": args.end_date.isoformat(),
            "initial_capital": args.initial_capital,
            "portfolio_size": args.portfolio_size,
            "weekly_picks": args.weekly_picks,
            "holding_period": args.holding_period,
            "low_breadth_threshold": args.low_breadth_threshold,
            "low_breadth_multiplier": args.low_breadth_multiplier,
        },
        "variants": {key: {"name": value["name"], "metrics": value["metrics"]} for key, value in results.items()},
        "financial_year_returns": [row for value in results.values() for row in value["financial_year_returns"]],
        "entry_summary": {
            "baseline_entries": sum(1 for row in results["rolling_10_baseline"]["entry_log"] if row.get("status") == "entered"),
            "experiment_entries": sum(1 for row in results["rolling_10_low_sector_breadth_half_size"]["entry_log"] if row.get("status") == "entered"),
            "low_breadth_entries": sum(
                1
                for row in results["rolling_10_low_sector_breadth_half_size"]["entry_log"]
                if row.get("status") == "entered" and row.get("low_sector_breadth")
            ),
        },
        "constraints": {
            "scoring_changed": False,
            "recommendations_changed": False,
            "ranking_changed": False,
            "holding_period_changed": False,
            "database_modified": False,
        },
        "verdict": verdict,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "rolling_10_breadth_sizing_results.json").write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
    (args.output_dir / "ROLLING_10_BREADTH_SIZING_EXPERIMENT.md").write_text(render_report(output), encoding="utf-8")
    write_csv(args.output_dir / "rolling_10_breadth_sizing_equity.csv", [row for result in results.values() for row in result["equity_curve"]])
    write_csv(args.output_dir / "rolling_10_breadth_sizing_trades.csv", [row for result in results.values() for row in result["trades"]])
    write_csv(args.output_dir / "rolling_10_breadth_sizing_entries.csv", [row for result in results.values() for row in result["entry_log"]])
    write_csv(args.output_dir / "rolling_10_breadth_sizing_fy_returns.csv", output["financial_year_returns"])
    print(json.dumps(output, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
