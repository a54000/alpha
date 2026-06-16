#!/usr/bin/env python3
"""Phase 2E pilot portfolio backtest for Swing V2.1 recommendations.

Reads:
  - angel_data.pilot_phase2a.recommendations_daily
  - angel_data.pilot_phase2a.daily_bars_clean

Writes:
  - reports/phase2e_portfolio_metrics.json
  - reports/phase2e_equity_curves.csv
  - reports/phase2e_trade_ledger.csv
  - reports/phase2e_monthly_returns.csv

Does not:
  - Modify production tables
  - Modify pilot tables
  - Regenerate scores or recommendations
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import statistics
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL = "swing_v2_1"
START_DATE = date(2022, 5, 25)
END_DATE = date(2026, 6, 11)
KNOWN_SPECIAL_SESSIONS = {
    date(2022, 10, 24),
    date(2023, 11, 12),
    date(2024, 3, 2),
    date(2024, 5, 18),
    date(2024, 11, 1),
}


@dataclass(frozen=True)
class PilotBacktestConfig:
    variant: str
    name: str
    portfolio_size: int
    holding_period: int = 20
    initial_capital: float = 1_000_000.0
    rebalance_frequency: str = "weekly"
    max_positions_per_sector: int | None = None
    max_candidate_rank: int | None = None


@dataclass
class PilotPosition:
    symbol: str
    sector: str | None
    signal_date: date
    entry_date: date
    entry_price: float
    shares: float
    planned_exit_date: date
    rank: int


VARIANTS = [
    PilotBacktestConfig("top5_weekly", "Top 5 Weekly", portfolio_size=5),
    PilotBacktestConfig("top10_weekly", "Top 10 Weekly", portfolio_size=10),
    PilotBacktestConfig(
        "top10_weekly_max2_sector",
        "Top 10 Weekly + Max 2 Positions Per Sector",
        portfolio_size=10,
        max_positions_per_sector=2,
        max_candidate_rank=50,
    ),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 2E pilot portfolio backtests.")
    parser.add_argument("--research-database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--angel-database-url", default=os.environ.get("ANGEL_DATABASE_URL"))
    parser.add_argument("--angel-database-name", default="angel_data")
    parser.add_argument("--pilot-schema", default="pilot_phase2a")
    parser.add_argument("--metrics-json", default="reports/phase2e_portfolio_metrics.json")
    parser.add_argument("--equity-csv", default="reports/phase2e_equity_curves.csv")
    parser.add_argument("--trades-csv", default="reports/phase2e_trade_ledger.csv")
    parser.add_argument("--monthly-csv", default="reports/phase2e_monthly_returns.csv")
    return parser.parse_args()


def derive_angel_url(research_database_url: str | None, database_name: str) -> str | None:
    if not research_database_url:
        return None
    parts = urlsplit(research_database_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database_name}", parts.query, parts.fragment))


def load_recommendations(angel_url: str, schema: str) -> list[dict[str, object]]:
    engine = create_engine(angel_url, future=True)
    query = text(
        f"""
        SELECT date, model, rank, symbol, score, sector
        FROM {schema}.recommendations_daily
        WHERE model = :model
          AND date BETWEEN :start_date AND :end_date
        ORDER BY date, rank, symbol
        """
    )
    with engine.connect() as connection:
        rows = connection.execute(query, {"model": MODEL, "start_date": START_DATE, "end_date": END_DATE}).mappings().all()
    return [
        {
            "date": row["date"],
            "model": row["model"],
            "rank": int(row["rank"]),
            "symbol": row["symbol"],
            "score": float(row["score"]) if row["score"] is not None else None,
            "sector": row["sector"],
        }
        for row in rows
    ]


def load_prices(angel_url: str, schema: str, symbols: set[str]) -> dict[str, dict[date, dict[str, float]]]:
    if not symbols:
        return {}
    engine = create_engine(angel_url, future=True)
    query = text(
        f"""
        SELECT symbol, date, open, close
        FROM {schema}.daily_bars_clean
        WHERE symbol = ANY(:symbols)
          AND date >= :start_date
        ORDER BY symbol, date
        """
    )
    with engine.connect() as connection:
        rows = connection.execute(query, {"symbols": list(symbols), "start_date": START_DATE}).mappings().all()
    prices: dict[str, dict[date, dict[str, float]]] = {}
    for row in rows:
        open_price = row["open"]
        close_price = row["close"]
        if open_price is None and close_price is None:
            continue
        prices.setdefault(row["symbol"], {})[row["date"]] = {
            "open": float(open_price if open_price is not None else close_price),
            "close": float(close_price if close_price is not None else open_price),
        }
    return prices


def load_existing_two_year_results() -> dict[str, object]:
    path = REPO_ROOT / "reports/portfolio_structure_results.json"
    output = {}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        details = data.get("details", {})
        for variant in ["top5_weekly", "top10_weekly", "top10_weekly_max2_sector"]:
            item = details.get(variant)
            if item:
                output[variant] = item.get("metrics", {})

    sector_cap_path = REPO_ROOT / "reports/top5_sector_cap_validation.json"
    if sector_cap_path.exists() and "top10_weekly_max2_sector" not in output:
        data = json.loads(sector_cap_path.read_text(encoding="utf-8"))
        details = data.get("details", {})
        item = details.get("top10_weekly_max2_sector")
        if item:
            output["top10_weekly_max2_sector"] = item.get("metrics", {})
    return output


def all_trading_dates(prices: dict[str, dict[date, dict[str, float]]]) -> list[date]:
    return sorted({price_date for symbol_prices in prices.values() for price_date in symbol_prices})


def symbol_dates(prices: dict[str, dict[date, dict[str, float]]], symbol: str) -> list[date]:
    return sorted(prices.get(symbol, {}))


def regular_session_dates(dates: list[date]) -> list[date]:
    return [item for item in sorted(dates) if item not in KNOWN_SPECIAL_SESSIONS]


def weekly_signal_dates(signal_dates: list[date]) -> list[date]:
    weekly = []
    seen_weeks = set()
    for signal_date in signal_dates:
        year, week, _ = signal_date.isocalendar()
        key = (year, week)
        if key in seen_weeks:
            continue
        seen_weeks.add(key)
        weekly.append(signal_date)
    return weekly


def next_trading_day_after(dates: list[date], signal_date: date) -> date | None:
    for trading_date in dates:
        if trading_date > signal_date:
            return trading_date
    return None


def nth_trading_day_after(dates: list[date], entry_date: date, periods: int) -> date | None:
    sessions = regular_session_dates(dates)
    try:
        index = sessions.index(entry_date)
    except ValueError:
        return None
    exit_index = index + periods - 1
    if exit_index >= len(sessions):
        return None
    return sessions[exit_index]


def trading_day_distance(dates: list[date], start: date, end: date) -> int | None:
    sessions = regular_session_dates(dates)
    try:
        return sessions.index(end) - sessions.index(start) + 1
    except ValueError:
        return None


def positions_value(
    positions: list[PilotPosition],
    prices: dict[str, dict[date, dict[str, float]]],
    current_date: date,
    price_field: str,
) -> float:
    value = 0.0
    for position in positions:
        price = prices.get(position.symbol, {}).get(current_date, {}).get(price_field)
        if price is not None:
            value += position.shares * price
    return value


def sector_weights(
    positions: list[PilotPosition],
    prices: dict[str, dict[date, dict[str, float]]],
    current_date: date,
    total_equity: float,
) -> dict[str, float]:
    if total_equity <= 0:
        return {}
    weights: dict[str, float] = {}
    for position in positions:
        price = prices.get(position.symbol, {}).get(current_date, {}).get("close")
        if price is None:
            continue
        sector = position.sector or "UNKNOWN"
        weights[sector] = weights.get(sector, 0.0) + (position.shares * price / total_equity)
    return weights


def passes_sector_constraints(sector: str | None, positions: list[PilotPosition], config: PilotBacktestConfig) -> bool:
    if config.max_positions_per_sector is None:
        return True
    sector_name = sector or "UNKNOWN"
    sector_positions = sum(1 for position in positions if (position.sector or "UNKNOWN") == sector_name)
    return sector_positions < config.max_positions_per_sector


def metrics(
    config: PilotBacktestConfig,
    equity_curve: list[dict[str, object]],
    closed_trades: list[dict[str, object]],
    turnover_value: float,
    sector_weight_snapshots: list[dict[str, float]],
) -> dict[str, object]:
    if not equity_curve:
        return {}
    equity_values = [float(row["equity"]) for row in equity_curve]
    returns = [(right / left) - 1 for left, right in zip(equity_values, equity_values[1:]) if left != 0]
    total_return = (equity_values[-1] / config.initial_capital) - 1
    days = max(1, len(equity_curve))
    cagr = (equity_values[-1] / config.initial_capital) ** (252 / days) - 1
    volatility = statistics.stdev(returns) * math.sqrt(252) if len(returns) > 1 else 0.0
    sharpe = statistics.mean(returns) / statistics.stdev(returns) * math.sqrt(252) if len(returns) > 1 and statistics.stdev(returns) else 0.0
    downside = [value for value in returns if value < 0]
    sortino = statistics.mean(returns) / statistics.stdev(downside) * math.sqrt(252) if len(downside) > 1 and statistics.stdev(downside) else 0.0

    peak = equity_values[0]
    max_drawdown = 0.0
    for value in equity_values:
        peak = max(peak, value)
        if peak:
            max_drawdown = min(max_drawdown, (value / peak) - 1)

    trade_returns = [float(trade["return"]) for trade in closed_trades if trade.get("return") is not None]
    wins = [value for value in trade_returns if value > 0]
    losses = [value for value in trade_returns if value < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = gross_profit / gross_loss if gross_loss else (float("inf") if gross_profit else 0.0)
    avg_equity = statistics.mean(equity_values) if equity_values else config.initial_capital
    holding_periods = [int(trade["holding_days"]) for trade in closed_trades if trade.get("holding_days") is not None]

    avg_sector_weights: dict[str, float] = {}
    for snapshot in sector_weight_snapshots:
        for sector, weight in snapshot.items():
            avg_sector_weights[sector] = avg_sector_weights.get(sector, 0.0) + weight
    if sector_weight_snapshots:
        avg_sector_weights = {sector: weight / len(sector_weight_snapshots) for sector, weight in avg_sector_weights.items()}
    top_sectors = sorted(avg_sector_weights.items(), key=lambda item: item[1], reverse=True)

    return {
        "total_return": total_return,
        "cagr": cagr,
        "max_drawdown": max_drawdown,
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "volatility": volatility,
        "turnover": turnover_value / avg_equity if avg_equity else 0.0,
        "win_rate": len(wins) / len(trade_returns) if trade_returns else 0.0,
        "profit_factor": profit_factor,
        "average_holding_period": statistics.mean(holding_periods) if holding_periods else 0.0,
        "closed_trades": len(closed_trades),
        "final_equity": equity_values[-1],
        "sector_concentration": {
            "top_sector": top_sectors[0][0] if top_sectors else None,
            "top_sector_avg_weight": top_sectors[0][1] if top_sectors else 0.0,
            "top_3_avg_weight": sum(weight for _, weight in top_sectors[:3]),
            "sectors": [{"sector": sector, "avg_weight": weight} for sector, weight in top_sectors],
        },
    }


def monthly_returns(equity_curve: list[dict[str, object]], variant: str) -> list[dict[str, object]]:
    if not equity_curve:
        return []
    by_month: dict[str, dict[str, object]] = {}
    for row in equity_curve:
        row_date = date.fromisoformat(str(row["date"]))
        by_month[row_date.strftime("%Y-%m")] = row
    rows = []
    previous_equity = None
    for month in sorted(by_month):
        equity = float(by_month[month]["equity"])
        month_return = None if previous_equity is None else (equity / previous_equity) - 1
        rows.append(
            {
                "variant": variant,
                "month": month,
                "month_end_date": by_month[month]["date"],
                "month_end_equity": equity,
                "monthly_return": month_return,
            }
        )
        previous_equity = equity
    return rows


def run_backtest(
    config: PilotBacktestConfig,
    recommendations: list[dict[str, object]],
    prices: dict[str, dict[date, dict[str, float]]],
) -> dict[str, object]:
    if not recommendations:
        return {"config": asdict(config), "metrics": {}, "equity_curve": [], "closed_trades": []}
    dates = all_trading_dates(prices)
    if not dates:
        return {"config": asdict(config), "metrics": {}, "equity_curve": [], "closed_trades": []}

    sectors = {}
    recs_by_date: dict[date, list[dict[str, object]]] = {}
    for rec in recommendations:
        recs_by_date.setdefault(rec["date"], []).append(rec)
        sectors[rec["symbol"]] = rec.get("sector")
    for rows in recs_by_date.values():
        rows.sort(key=lambda row: (int(row["rank"]), str(row["symbol"])))

    rebalance_dates = weekly_signal_dates(sorted(recs_by_date))
    entries_by_date = {}
    for signal_date in rebalance_dates:
        entry_date = next_trading_day_after(dates, signal_date)
        if entry_date is not None:
            entries_by_date[entry_date] = recs_by_date[signal_date]

    first_signal = min(recs_by_date)
    start_date = next_trading_day_after(dates, first_signal) or dates[0]
    start_index = max(0, dates.index(start_date))
    simulation_dates = [item for item in dates[start_index:] if item <= END_DATE]

    cash = config.initial_capital
    positions: list[PilotPosition] = []
    closed_trades: list[dict[str, object]] = []
    equity_curve: list[dict[str, object]] = []
    turnover_value = 0.0
    sector_weight_snapshots: list[dict[str, float]] = []

    for current_date in simulation_dates:
        remaining: list[PilotPosition] = []
        closed_today: set[str] = set()
        for position in positions:
            close_price = prices.get(position.symbol, {}).get(current_date, {}).get("close")
            if current_date >= position.planned_exit_date and close_price is not None:
                proceeds = position.shares * close_price
                cash += proceeds
                turnover_value += proceeds
                closed_trades.append(
                    {
                        "variant": config.variant,
                        "symbol": position.symbol,
                        "sector": position.sector,
                        "signal_date": position.signal_date.isoformat(),
                        "entry_date": position.entry_date.isoformat(),
                        "exit_date": current_date.isoformat(),
                        "entry_price": position.entry_price,
                        "exit_price": close_price,
                        "shares": position.shares,
                        "return": (close_price / position.entry_price) - 1,
                        "pnl": proceeds - (position.shares * position.entry_price),
                        "entry_value": position.shares * position.entry_price,
                        "exit_value": proceeds,
                        "holding_days": trading_day_distance(dates, position.entry_date, current_date),
                        "rank": position.rank,
                        "forced_final_exit": False,
                    }
                )
                closed_today.add(position.symbol)
            else:
                remaining.append(position)
        positions = remaining

        if current_date in entries_by_date and len(positions) < config.portfolio_size:
            held = {position.symbol for position in positions}
            equity_at_open = cash + positions_value(positions, prices, current_date, "open")
            target_value = equity_at_open / config.portfolio_size
            max_candidate_rank = config.max_candidate_rank or config.portfolio_size
            candidates = [
                rec for rec in entries_by_date[current_date]
                if int(rec["rank"]) <= max_candidate_rank and rec["symbol"] not in held and rec["symbol"] not in closed_today
            ]
            for rec in candidates:
                if len(positions) >= config.portfolio_size:
                    break
                symbol = str(rec["symbol"])
                sector = sectors.get(symbol)
                if not passes_sector_constraints(sector, positions, config):
                    continue
                open_price = prices.get(symbol, {}).get(current_date, {}).get("open")
                if open_price is None or open_price <= 0:
                    continue
                allocation = min(target_value, cash)
                if allocation <= 0:
                    break
                planned_exit = nth_trading_day_after(symbol_dates(prices, symbol), current_date, config.holding_period)
                if planned_exit is None or planned_exit > END_DATE:
                    continue
                shares = allocation / open_price
                cash -= allocation
                turnover_value += allocation
                positions.append(
                    PilotPosition(
                        symbol=symbol,
                        sector=sector,
                        signal_date=rec["date"],
                        entry_date=current_date,
                        entry_price=open_price,
                        shares=shares,
                        planned_exit_date=planned_exit,
                        rank=int(rec["rank"]),
                    )
                )
                held.add(symbol)

        total_equity = cash + positions_value(positions, prices, current_date, "close")
        sector_weight_snapshots.append(sector_weights(positions, prices, current_date, total_equity))
        equity_curve.append(
            {
                "variant": config.variant,
                "date": current_date.isoformat(),
                "equity": total_equity,
                "cash": cash,
                "position_count": len(positions),
            }
        )

    if simulation_dates:
        final_date = simulation_dates[-1]
        for position in positions:
            close_price = prices.get(position.symbol, {}).get(final_date, {}).get("close")
            if close_price is None:
                continue
            closed_trades.append(
                {
                    "variant": config.variant,
                    "symbol": position.symbol,
                    "sector": position.sector,
                    "signal_date": position.signal_date.isoformat(),
                    "entry_date": position.entry_date.isoformat(),
                    "exit_date": final_date.isoformat(),
                    "entry_price": position.entry_price,
                    "exit_price": close_price,
                    "shares": position.shares,
                    "return": (close_price / position.entry_price) - 1,
                    "pnl": (position.shares * close_price) - (position.shares * position.entry_price),
                    "entry_value": position.shares * position.entry_price,
                    "exit_value": position.shares * close_price,
                    "holding_days": trading_day_distance(dates, position.entry_date, final_date),
                    "rank": position.rank,
                    "forced_final_exit": True,
                }
            )

    return {
        "config": {
            **asdict(config),
            "entry": "next_trading_day_open",
            "exit": "close_after_20_trading_days",
            "weighting": "equal_weight",
            "leverage": "none",
            "transaction_costs": "not_included",
        },
        "metrics": metrics(config, equity_curve, closed_trades, turnover_value, sector_weight_snapshots),
        "equity_curve": equity_curve,
        "closed_trades": closed_trades,
        "monthly_returns": monthly_returns(equity_curve, config.variant),
    }


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def comparison_to_existing(pilot_results: dict[str, dict[str, object]], existing: dict[str, object]) -> dict[str, object]:
    rows = {}
    for variant, result in pilot_results.items():
        pilot_metrics = result.get("metrics", {})
        existing_metrics = existing.get(variant, {})
        if not existing_metrics:
            continue
        rows[variant] = {
            "existing_2y": {
                key: existing_metrics.get(key)
                for key in ["total_return", "cagr", "max_drawdown", "sharpe_ratio", "sortino_ratio", "profit_factor", "win_rate", "turnover"]
            },
            "pilot_5y": {
                key: pilot_metrics.get(key)
                for key in ["total_return", "cagr", "max_drawdown", "sharpe_ratio", "sortino_ratio", "profit_factor", "win_rate", "turnover"]
            },
            "delta_pilot_minus_existing": {
                key: (float(pilot_metrics[key]) - float(existing_metrics[key]))
                for key in ["total_return", "cagr", "max_drawdown", "sharpe_ratio", "sortino_ratio", "profit_factor", "win_rate", "turnover"]
                if key in pilot_metrics and key in existing_metrics and pilot_metrics[key] is not None and existing_metrics[key] is not None
            },
        }
    return rows


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    args = parse_args()
    research_url = args.research_database_url or os.environ.get("DATABASE_URL")
    angel_url = args.angel_database_url or derive_angel_url(research_url, args.angel_database_name)
    if not angel_url:
        raise RuntimeError("Angel database URL is required.")

    recommendations = load_recommendations(angel_url, args.pilot_schema)
    symbols = {str(row["symbol"]) for row in recommendations}
    prices = load_prices(angel_url, args.pilot_schema, symbols)

    results = {}
    equity_rows: list[dict[str, object]] = []
    trade_rows: list[dict[str, object]] = []
    monthly_rows: list[dict[str, object]] = []
    for config in VARIANTS:
        result = run_backtest(config, recommendations, prices)
        results[config.variant] = {
            "config": result["config"],
            "metrics": result["metrics"],
            "closed_trade_count": len(result["closed_trades"]),
        }
        equity_rows.extend(result["equity_curve"])
        trade_rows.extend(result["closed_trades"])
        monthly_rows.extend(result["monthly_returns"])

    existing = load_existing_two_year_results()
    output = {
        "generated_on": date.today().isoformat(),
        "mode": "phase2e_pilot_portfolio_backtest",
        "model": MODEL,
        "date_range": {"start": START_DATE.isoformat(), "end": END_DATE.isoformat()},
        "production_tables_modified": False,
        "scoring_changed": False,
        "recommendations_changed": False,
        "backtest_inputs": {
            "recommendations": f"{args.pilot_schema}.recommendations_daily",
            "prices": f"{args.pilot_schema}.daily_bars_clean",
            "recommendation_rows": len(recommendations),
            "symbols": len(symbols),
        },
        "methodology": {
            "entry": "next_trading_day_open",
            "exit": "close_after_20_trading_days",
            "rebalance": "weekly_first_available_signal_date_per_iso_week",
            "weighting": "equal_weight_target_allocation",
            "leverage": "none",
            "transaction_costs": "not_included",
            "sector_cap_variant": "max 2 open positions per sector, candidate ranks up to 50",
            "final_open_positions": "liquidated at final available close for trade statistics",
        },
        "variants": results,
        "comparison_to_existing_2y_v2_1": comparison_to_existing(results, existing),
    }

    metrics_path = REPO_ROOT / args.metrics_json
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
    write_csv(REPO_ROOT / args.equity_csv, equity_rows)
    write_csv(REPO_ROOT / args.trades_csv, trade_rows)
    write_csv(REPO_ROOT / args.monthly_csv, monthly_rows)

    print(json.dumps({key: value["metrics"] for key, value in results.items()}, indent=2, default=str))
    print(f"Wrote Phase 2E portfolio metrics: {metrics_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
