#!/usr/bin/env python3
"""Backfill V2 scores, generate V2 recommendations, and run V2 backtests."""

from __future__ import annotations

import json
import statistics
from pathlib import Path

from sqlalchemy import inspect, select, text

from app.backtesting.run_backtest import BacktestRunner
from app.recommendations.generate_recommendations import RecommendationGenerator
from app.scoring.compute_scores import ScoreComputer
from db.models import DailyScores, FeaturesDaily, RecommendationHistory
from db.session import build_session_factory


def calculate_std_dev(returns: list[float]) -> float:
    if len(returns) < 2:
        return 0.0
    return statistics.stdev(returns)


def calculate_profit_factor(returns: list[float]) -> float:
    gross_profit = sum(value for value in returns if value > 0)
    gross_loss = abs(sum(value for value in returns if value < 0))
    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0.0
    return gross_profit / gross_loss


def ensure_v2_score_columns(session) -> None:
    inspector = inspect(session.bind)
    columns = {column["name"] for column in inspector.get_columns("daily_scores")}
    dialect = session.bind.dialect.name if session.bind else ""

    if dialect == "postgresql":
        if "swing_v2_score" not in columns:
            session.execute(text("ALTER TABLE daily_scores ADD COLUMN IF NOT EXISTS swing_v2_score NUMERIC(5, 1)"))
        if "position_v2_score" not in columns:
            session.execute(text("ALTER TABLE daily_scores ADD COLUMN IF NOT EXISTS position_v2_score NUMERIC(5, 1)"))
    else:
        if "swing_v2_score" not in columns:
            session.execute(text("ALTER TABLE daily_scores ADD COLUMN swing_v2_score NUMERIC(5, 1)"))
        if "position_v2_score" not in columns:
            session.execute(text("ALTER TABLE daily_scores ADD COLUMN position_v2_score NUMERIC(5, 1)"))
    session.commit()


def clear_existing_v2_recommendations(session) -> None:
    session.execute(
        RecommendationHistory.__table__.delete().where(
            RecommendationHistory.model.in_(["swing_v2", "positional_v2"])
        )
    )
    session.commit()


def model_results(report, horizons: list[str], primary_horizon: str) -> dict[str, object]:
    payload: dict[str, object] = {
        "trade_count": report.trade_count,
        "valid_trade_count": report.valid_trade_count,
        "benchmark_available": report.benchmark_available,
        "benchmark_symbol": report.benchmark_symbol,
        "alpha": report.alpha_by_horizon.get(primary_horizon),
        "horizons": {},
    }

    horizon_payload = {}
    for horizon in horizons:
        returns = [trade.returns[horizon] for trade in report.trades if trade.returns[horizon] is not None]
        metrics = report.aggregate_by_horizon[horizon]
        horizon_payload[horizon] = {
            "trade_count": metrics.trade_count,
            "valid_count": metrics.valid_count,
            "win_rate": metrics.win_rate,
            "avg_return": metrics.avg_return,
            "median_return": metrics.median_return,
            "max_gain": metrics.max_gain,
            "max_loss": metrics.max_loss,
            "std_dev": calculate_std_dev(returns),
            "profit_factor": calculate_profit_factor(returns),
            "alpha": report.alpha_by_horizon.get(horizon),
        }
    payload["horizons"] = horizon_payload
    return payload


def main() -> int:
    session_factory = build_session_factory()

    with session_factory() as session:
        ensure_v2_score_columns(session)
        start_date = session.execute(select(FeaturesDaily.date).order_by(FeaturesDaily.date.asc())).scalars().first()
        end_date = session.execute(select(FeaturesDaily.date).order_by(FeaturesDaily.date.desc())).scalars().first()

    if start_date is None or end_date is None:
        raise RuntimeError("No features_daily dates available for V2 backfill")

    print(f"Backfilling V2 scores from {start_date} to {end_date}...")
    score_report = ScoreComputer(session_factory).generate(start_date=start_date, end_date=end_date)
    if score_report.failures:
        print(f"Score backfill failures: {len(score_report.failures)}")

    with session_factory() as session:
        clear_existing_v2_recommendations(session)

    print("Generating V2 recommendations...")
    recommendation_report = RecommendationGenerator(session_factory).generate_v2(start_date=start_date, end_date=end_date)
    if recommendation_report.failures:
        print(f"Recommendation failures: {len(recommendation_report.failures)}")

    runner = BacktestRunner(session_factory)
    print("Running swing_v2 backtest...")
    swing_report = runner.run("swing_v2", start_date, end_date, persist=True)
    print("Running positional_v2 backtest...")
    positional_report = runner.run("positional_v2", start_date, end_date, persist=True)

    with session_factory() as session:
        score_counts = session.execute(
            text(
                "SELECT "
                "COUNT(*) FILTER (WHERE swing_v2_score IS NOT NULL) AS swing_v2_scores, "
                "COUNT(*) FILTER (WHERE position_v2_score IS NOT NULL) AS position_v2_scores "
                "FROM daily_scores"
            )
        ).mappings().one()

    results = {
        "scoring": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "symbols_processed": score_report.symbols_processed,
            "dates_processed": score_report.dates_processed,
            "rows_written": score_report.rows_written,
            "swing_v2_scores": score_counts["swing_v2_scores"],
            "position_v2_scores": score_counts["position_v2_scores"],
        },
        "recommendations": {
            "dates_processed": recommendation_report.dates_processed,
            "swing_v2_recommendations": recommendation_report.swing_recommendations,
            "positional_v2_recommendations": recommendation_report.positional_recommendations,
            "rows_written": recommendation_report.rows_written,
        },
        "swing_v2": model_results(swing_report, ["return_5d", "return_10d", "return_20d"], "return_20d"),
        "positional_v2": model_results(positional_report, ["return_1m", "return_3m", "return_6m"], "return_3m"),
    }

    output_path = Path("reports/v2_backtest_results.json")
    output_path.parent.mkdir(exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"V2 backtest results written to: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
