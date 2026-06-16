#!/usr/bin/env python3
"""Backfill Swing V2.1 scores, recommendations, and backtest results."""

from __future__ import annotations

import json
import statistics
from pathlib import Path
import sys

from sqlalchemy import inspect, select, text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.backtesting.run_backtest import BacktestRunner
from app.recommendations.generate_recommendations import RecommendationGenerator
from app.scoring.compute_scores import ScoreComputer
from db.models import FeaturesDaily, RecommendationHistory
from db.session import build_session_factory


PRIMARY_HORIZON = "return_20d"
SWING_HORIZONS = ["return_5d", "return_10d", "return_20d"]


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


def ensure_swing_v2_1_score_column(session) -> None:
    inspector = inspect(session.bind)
    columns = {column["name"] for column in inspector.get_columns("daily_scores")}
    dialect = session.bind.dialect.name if session.bind else ""

    if "swing_v2_1_score" in columns:
        return

    if dialect == "postgresql":
        session.execute(text("ALTER TABLE daily_scores ADD COLUMN IF NOT EXISTS swing_v2_1_score NUMERIC(5, 1)"))
    else:
        session.execute(text("ALTER TABLE daily_scores ADD COLUMN swing_v2_1_score NUMERIC(5, 1)"))
    session.commit()


def clear_existing_swing_v2_1_recommendations(session) -> None:
    session.execute(
        RecommendationHistory.__table__.delete().where(
            RecommendationHistory.model == "swing_v2_1"
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


def existing_swing_result(path: Path, model_key: str) -> dict[str, object] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    model_payload = payload.get(model_key)
    if model_payload is None:
        return None
    return model_payload


def compact_primary(result: dict[str, object] | None) -> dict[str, object] | None:
    if result is None:
        return None
    horizons = result.get("horizons", {})
    primary = horizons.get(PRIMARY_HORIZON) if isinstance(horizons, dict) else None
    if primary is None:
        primary = result.get(PRIMARY_HORIZON)
    if primary is None:
        return None
    return {
        "trade_count": primary.get("trade_count", result.get("trade_count")),
        "valid_count": primary.get("valid_count", result.get("valid_trade_count")),
        "avg_return": primary.get("avg_return"),
        "win_rate": primary.get("win_rate"),
        "profit_factor": primary.get("profit_factor"),
        "alpha": primary.get("alpha", result.get("alpha", result.get("alpha_20d"))),
    }


def main() -> int:
    session_factory = build_session_factory()

    with session_factory() as session:
        ensure_swing_v2_1_score_column(session)
        start_date = session.execute(select(FeaturesDaily.date).order_by(FeaturesDaily.date.asc())).scalars().first()
        end_date = session.execute(select(FeaturesDaily.date).order_by(FeaturesDaily.date.desc())).scalars().first()

    if start_date is None or end_date is None:
        raise RuntimeError("No features_daily dates available for Swing V2.1 backfill")

    print(f"Backfilling scores from {start_date} to {end_date}...")
    score_report = ScoreComputer(session_factory).generate(start_date=start_date, end_date=end_date)
    if score_report.failures:
        print(f"Score backfill failures: {len(score_report.failures)}")

    with session_factory() as session:
        clear_existing_swing_v2_1_recommendations(session)

    print("Generating Swing V2.1 recommendations...")
    recommendation_report = RecommendationGenerator(session_factory).generate_swing_v2_1(
        start_date=start_date,
        end_date=end_date,
    )
    if recommendation_report.failures:
        print(f"Recommendation failures: {len(recommendation_report.failures)}")

    print("Running Swing V2.1 backtest...")
    runner = BacktestRunner(session_factory)
    swing_v2_1_report = runner.run("swing_v2_1", start_date, end_date, persist=True)
    swing_v2_1 = model_results(swing_v2_1_report, SWING_HORIZONS, PRIMARY_HORIZON)

    with session_factory() as session:
        counts = session.execute(
            text(
                "SELECT "
                "COUNT(*) FILTER (WHERE swing_v2_1_score IS NOT NULL) AS swing_v2_1_scores "
                "FROM daily_scores"
            )
        ).mappings().one()

    v1 = existing_swing_result(Path("reports/v1_clean_backtest_results.json"), "swing")
    v2 = existing_swing_result(Path("reports/v2_backtest_results.json"), "swing_v2")

    comparison = {
        "v1_swing": compact_primary(v1),
        "swing_v2": compact_primary(v2),
        "swing_v2_1": compact_primary(swing_v2_1),
    }

    results = {
        "model": "swing_v2_1",
        "research_only": True,
        "scoring": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "symbols_processed": score_report.symbols_processed,
            "dates_processed": score_report.dates_processed,
            "rows_written": score_report.rows_written,
            "swing_v2_1_scores": counts["swing_v2_1_scores"],
        },
        "recommendations": {
            "dates_processed": recommendation_report.dates_processed,
            "swing_v2_1_recommendations": recommendation_report.swing_recommendations,
            "rows_written": recommendation_report.rows_written,
        },
        "swing_v2_1": swing_v2_1,
        "comparison": comparison,
    }

    output_path = Path("reports/swing_v2_1_results.json")
    output_path.parent.mkdir(exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"Swing V2.1 results written to: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
