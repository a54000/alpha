#!/usr/bin/env python3
"""Phase 3B historical replay validation for the paper trading engine."""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import sessionmaker

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app.paper_trading import PaperTradingConfig, PaperTradingService
from db.base import Base
from db.models import PaperDailySnapshot, PaperTrade, PricesDaily, RecommendationHistory, SymbolMaster

START_DATE = date(2025, 1, 1)
END_DATE = date(2026, 6, 11)
WARMUP_START_DATE = date(2024, 12, 1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay historical recommendations through Phase 3A paper engine.")
    parser.add_argument("--research-database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--angel-database-url", default=os.environ.get("ANGEL_DATABASE_URL"))
    parser.add_argument("--angel-database-name", default="angel_data")
    parser.add_argument("--pilot-schema", default="pilot_phase2a")
    parser.add_argument("--phase2e-metrics-json", default="reports/phase2e_portfolio_metrics.json")
    parser.add_argument("--phase2e-equity-csv", default="reports/phase2e_equity_curves.csv")
    parser.add_argument("--phase2e-trades-csv", default="reports/phase2e_trade_ledger.csv")
    parser.add_argument("--output-json", default="reports/phase3b_replay_validation.json")
    parser.add_argument("--lifecycle-mode", default="sell_removed_on_rebalance")
    parser.add_argument("--warmup-start-date", default=WARMUP_START_DATE.isoformat())
    return parser.parse_args()


def derive_angel_url(research_database_url: str | None, database_name: str) -> str | None:
    if not research_database_url:
        return None
    parts = urlsplit(research_database_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database_name}", parts.query, parts.fragment))


def build_replay_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)


def load_pilot_inputs(angel_url: str, schema: str, warmup_start: date) -> tuple[pd.DataFrame, pd.DataFrame]:
    engine = create_engine(angel_url, future=True)
    recommendations = pd.read_sql_query(
        text(
            f"""
            SELECT date, model, rank, symbol, score, sector
            FROM {schema}.recommendations_daily
            WHERE model = 'swing_v2_1'
              AND date BETWEEN :warmup_start AND :end_date
            ORDER BY date, rank, symbol
            """
        ),
        engine,
        params={"warmup_start": warmup_start, "end_date": END_DATE},
    )
    symbols = sorted(recommendations["symbol"].dropna().unique().tolist())
    prices = pd.read_sql_query(
        text(
            f"""
            SELECT symbol, date, open, close, volume
            FROM {schema}.daily_bars_clean
            WHERE symbol = ANY(:symbols)
              AND date BETWEEN :warmup_start AND :end_date
            ORDER BY symbol, date
            """
        ),
        engine,
        params={"symbols": symbols, "warmup_start": warmup_start, "end_date": END_DATE},
    )
    recommendations["date"] = pd.to_datetime(recommendations["date"]).dt.date
    prices["date"] = pd.to_datetime(prices["date"]).dt.date
    return recommendations, prices


def seed_replay_database(factory, recommendations: pd.DataFrame, prices: pd.DataFrame) -> None:
    sector_by_symbol = recommendations.dropna(subset=["symbol"]).drop_duplicates("symbol").set_index("symbol")["sector"].to_dict()
    with factory() as session:
        for symbol in sorted(set(prices["symbol"]).union(sector_by_symbol)):
            session.add(SymbolMaster(symbol=symbol, sector=sector_by_symbol.get(symbol)))
        session.flush()
        for row in recommendations.itertuples(index=False):
            session.add(
                RecommendationHistory(
                    date=row.date,
                    model=row.model,
                    rank=int(row.rank),
                    symbol=row.symbol,
                    score=float(row.score) if row.score is not None else None,
                )
            )
        for row in prices.itertuples(index=False):
            session.add(
                PricesDaily(
                    symbol=row.symbol,
                    date=row.date,
                    open=float(row.open) if row.open is not None else None,
                    close=float(row.close) if row.close is not None else None,
                    volume=int(row.volume) if row.volume is not None else None,
                )
            )
        session.commit()


def weekly_signal_dates(signal_dates: list[date]) -> list[date]:
    weekly = []
    seen = set()
    for signal_date in sorted(signal_dates):
        key = signal_date.isocalendar()[:2]
        if key in seen:
            continue
        seen.add(key)
        weekly.append(signal_date)
    return weekly


def run_replay(factory, variant: str, portfolio_size: int, lifecycle_mode: str, warmup_start: date) -> dict[str, object]:
    service = PaperTradingService(factory)
    config = PaperTradingConfig(
        strategy=f"swing_v2_1_{variant}",
        recommendation_model="swing_v2_1",
        portfolio_size=portfolio_size,
        initial_capital=1_000_000,
        holding_period=20,
        lifecycle_mode=lifecycle_mode,
    )
    portfolio_id = service.initialize_portfolio(variant, config)
    with factory() as session:
        signal_dates = session.execute(
            select(RecommendationHistory.date)
            .where(RecommendationHistory.date >= warmup_start, RecommendationHistory.date <= END_DATE)
            .distinct()
            .order_by(RecommendationHistory.date.asc())
        ).scalars().all()
        trading_dates = session.execute(
            select(PricesDaily.date)
            .where(PricesDaily.date >= warmup_start, PricesDaily.date <= END_DATE)
            .distinct()
            .order_by(PricesDaily.date.asc())
        ).scalars().all()
    weekly_dates = weekly_signal_dates(signal_dates)
    weekly_set = set(weekly_dates)
    for item_date in trading_dates:
        if item_date in weekly_set:
            service.rebalance_weekly(portfolio_id, item_date, config)
        service.update_daily(portfolio_id, item_date)
    with factory() as session:
        snapshots = session.execute(
            select(PaperDailySnapshot).where(PaperDailySnapshot.portfolio_id == portfolio_id).order_by(PaperDailySnapshot.date)
        ).scalars().all()
        trades = session.execute(select(PaperTrade).where(PaperTrade.portfolio_id == portfolio_id)).scalars().all()
    return {
        "portfolio_id": portfolio_id,
        "variant": variant,
        "lifecycle_mode": lifecycle_mode,
        "weekly_rebalance_dates": [item.isoformat() for item in weekly_dates],
        "snapshots": [
            {"date": row.date.isoformat(), "nav": float(row.nav), "cash": float(row.cash), "open_positions": row.open_positions}
            for row in snapshots
            if row.date >= START_DATE
        ],
        "trades": [
            {
                "symbol": row.symbol,
                "entry_date": row.entry_date.isoformat(),
                "exit_date": row.exit_date.isoformat(),
                "entry_price": float(row.entry_price),
                "exit_price": float(row.exit_price),
                "quantity": float(row.quantity),
                "realized_pnl": float(row.realized_pnl),
                "return_pct": float(row.return_pct),
                "turnover": float(row.turnover),
                "exit_reason": row.exit_reason,
            }
            for row in trades
            if row.exit_date >= START_DATE
        ],
    }


def metric_from_curve(snapshots: list[dict[str, object]], trades: list[dict[str, object]]) -> dict[str, object]:
    if len(snapshots) < 2:
        return {}
    equity = [float(row["nav"]) for row in snapshots]
    returns = [(right / left) - 1 for left, right in zip(equity, equity[1:]) if left]
    total_return = equity[-1] / equity[0] - 1
    cagr = (1 + total_return) ** (252 / max(1, len(equity) - 1)) - 1 if total_return > -1 else -1
    stdev = statistics.stdev(returns) if len(returns) > 1 else 0.0
    sharpe = statistics.mean(returns) / stdev * math.sqrt(252) if stdev else 0.0
    peak = equity[0]
    max_dd = 0.0
    for value in equity:
        peak = max(peak, value)
        max_dd = min(max_dd, value / peak - 1 if peak else 0)
    trade_returns = [float(row["return_pct"]) for row in trades]
    wins = [value for value in trade_returns if value > 0]
    losses = [value for value in trade_returns if value < 0]
    gross_loss = abs(sum(losses))
    return {
        "total_return": total_return,
        "cagr": cagr,
        "max_drawdown": max_dd,
        "sharpe": sharpe,
        "profit_factor": sum(wins) / gross_loss if gross_loss else (float("inf") if wins else 0.0),
        "trade_count": len(trades),
        "final_nav": equity[-1],
    }


def phase2e_period_metrics(equity_path: Path, trades_path: Path, variant: str) -> dict[str, object]:
    equity = pd.read_csv(equity_path)
    trades = pd.read_csv(trades_path)
    equity["date"] = pd.to_datetime(equity["date"]).dt.date
    trades["exit_date"] = pd.to_datetime(trades["exit_date"]).dt.date
    curve = equity[(equity["variant"] == variant) & (equity["date"] >= START_DATE) & (equity["date"] <= END_DATE)]
    trade_rows = trades[(trades["variant"] == variant) & (trades["exit_date"] >= START_DATE) & (trades["exit_date"] <= END_DATE)]
    snapshots = [{"date": row.date.isoformat(), "nav": float(row.equity)} for row in curve.itertuples(index=False)]
    ledger = [{"return_pct": float(row.return_)} if hasattr(row, "return_") else {"return_pct": float(getattr(row, "return"))} for row in []]
    ledger = [{"return_pct": float(row["return"])} for _, row in trade_rows.iterrows()]
    metrics = metric_from_curve(snapshots, ledger)
    metrics["trade_count"] = int(len(trade_rows))
    return metrics


def compare_metrics(paper: dict[str, object], phase2e: dict[str, object]) -> dict[str, object]:
    keys = ["total_return", "cagr", "max_drawdown", "sharpe", "profit_factor", "trade_count"]
    return {
        key: {
            "paper": paper.get(key),
            "phase2e": phase2e.get(key),
            "delta": (float(paper[key]) - float(phase2e[key])) if key in paper and key in phase2e else None,
        }
        for key in keys
    }


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    args = parse_args()
    angel_url = args.angel_database_url or derive_angel_url(args.research_database_url or os.environ.get("DATABASE_URL"), args.angel_database_name)
    if not angel_url:
        raise RuntimeError("Angel database URL is required.")
    warmup_start = date.fromisoformat(args.warmup_start_date)
    recommendations, prices = load_pilot_inputs(angel_url, args.pilot_schema, warmup_start)
    factory = build_replay_factory()
    seed_replay_database(factory, recommendations, prices)
    variants = {"top5_weekly": 5, "top10_weekly": 10}
    results = {}
    for variant, size in variants.items():
        replay = run_replay(factory, variant, size, args.lifecycle_mode, warmup_start)
        paper_metrics = metric_from_curve(replay["snapshots"], replay["trades"])
        phase2e_metrics = phase2e_period_metrics(REPO_ROOT / args.phase2e_equity_csv, REPO_ROOT / args.phase2e_trades_csv, variant)
        results[variant] = {
            "paper_metrics": paper_metrics,
            "phase2e_metrics": phase2e_metrics,
            "metric_comparison": compare_metrics(paper_metrics, phase2e_metrics),
        "replay_summary": {
                "snapshots": len(replay["snapshots"]),
                "trades": len(replay["trades"]),
                "rebalance_dates": len(replay["weekly_rebalance_dates"]),
                "first_rebalance_date": replay["weekly_rebalance_dates"][0] if replay["weekly_rebalance_dates"] else None,
                "last_rebalance_date": replay["weekly_rebalance_dates"][-1] if replay["weekly_rebalance_dates"] else None,
                "exit_reasons": dict(pd.Series([row["exit_reason"] for row in replay["trades"]]).value_counts()),
            },
            "snapshots": replay["snapshots"],
            "trades": replay["trades"],
        }
    output = {
        "generated_on": date.today().isoformat(),
        "mode": "phase3b_replay_validation",
        "lifecycle_mode": args.lifecycle_mode,
        "period": {"start": START_DATE.isoformat(), "end": END_DATE.isoformat()},
        "warmup_start_date": warmup_start.isoformat(),
        "constraints": {
            "scoring_changed": False,
            "recommendations_changed": False,
            "parameters_optimized": False,
            "broker_apis_connected": False,
        },
        "inputs": {
            "pilot_recommendations": f"{args.pilot_schema}.recommendations_daily",
            "pilot_prices": f"{args.pilot_schema}.daily_bars_clean",
            "phase2e_equity": args.phase2e_equity_csv,
            "phase2e_trades": args.phase2e_trades_csv,
        },
        "results": results,
        "mismatch_interpretation": {
            "expected_primary_difference": "Phase 3A paper engine closes positions removed at weekly rebalance; Phase 2E portfolio backtest held existing positions until planned 20-day exit.",
            "accounting_scope": "Replay validates paper engine accounting, not exact Phase 2E methodology parity.",
        },
    }
    output_path = REPO_ROOT / args.output_json
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
