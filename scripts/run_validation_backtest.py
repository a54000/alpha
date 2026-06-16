#!/usr/bin/env python3
"""Run validation backtests for swing and positional models.

This script:
1. Runs backtests for swing and positional models
2. Calculates comprehensive performance metrics
3. Performs score bucket analysis
4. Compares against benchmark if available
5. Generates a detailed report
"""

from __future__ import annotations

import json
import math
import statistics
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import select, text

from app.backtesting.run_backtest import BacktestRunner
from db.models import RecommendationHistory
from db.session import build_session_factory


def calculate_std_dev(returns: list[float]) -> float:
    """Calculate standard deviation of returns."""
    if len(returns) < 2:
        return 0.0
    return statistics.stdev(returns)


def calculate_profit_factor(returns: list[float]) -> float:
    """Calculate profit factor (gross profit / gross loss)."""
    gross_profit = sum(r for r in returns if r > 0)
    gross_loss = abs(sum(r for r in returns if r < 0))
    if gross_loss == 0:
        return float('inf') if gross_profit > 0 else 0.0
    return gross_profit / gross_loss


def bucket_scores(recommendations: list[RecommendationHistory], model: str) -> dict[str, list[RecommendationHistory]]:
    """Bucket recommendations by score ranges."""
    if model == "swing":
        buckets = {
            "70-74": [],
            "75-79": [],
            "80-84": [],
            "85-89": [],
            "90-100": [],
        }
        for rec in recommendations:
            if rec.score is None:
                continue
            score = float(rec.score)
            if 70 <= score <= 74:
                buckets["70-74"].append(rec)
            elif 75 <= score <= 79:
                buckets["75-79"].append(rec)
            elif 80 <= score <= 84:
                buckets["80-84"].append(rec)
            elif 85 <= score <= 89:
                buckets["85-89"].append(rec)
            elif 90 <= score <= 100:
                buckets["90-100"].append(rec)
    else:  # positional
        buckets = {
            "65-69": [],
            "70-74": [],
            "75-79": [],
            "80-84": [],
            "85-100": [],
        }
        for rec in recommendations:
            if rec.score is None:
                continue
            score = float(rec.score)
            if 65 <= score <= 69:
                buckets["65-69"].append(rec)
            elif 70 <= score <= 74:
                buckets["70-74"].append(rec)
            elif 75 <= score <= 79:
                buckets["75-79"].append(rec)
            elif 80 <= score <= 84:
                buckets["80-84"].append(rec)
            elif 85 <= score <= 100:
                buckets["85-100"].append(rec)
    
    return buckets


def analyze_bucket(
    bucket: list[RecommendationHistory],
    backtest_runner: BacktestRunner,
    model: str,
) -> dict[str, Any]:
    """Analyze performance for a score bucket."""
    if not bucket:
        return {
            "trade_count": 0,
            "avg_return": None,
            "median_return": None,
            "win_rate": None,
        }
    
    # Run backtest for this bucket
    # Get date range
    dates = [rec.date for rec in bucket]
    start_date = min(dates)
    end_date = max(dates)
    
    # Run backtest
    report = backtest_runner.run(model, start_date, end_date, persist=False)
    
    # Get returns for primary horizon
    if model == "swing":
        primary_horizon = "return_20d"
    else:
        primary_horizon = "return_3m"
    
    returns = [trade.returns[primary_horizon] for trade in report.trades if trade.returns[primary_horizon] is not None]
    
    if not returns:
        return {
            "trade_count": len(bucket),
            "avg_return": None,
            "median_return": None,
            "win_rate": None,
        }
    
    wins = sum(1 for r in returns if r > 0)
    
    return {
        "trade_count": len(returns),
        "avg_return": statistics.mean(returns),
        "median_return": statistics.median(returns),
        "win_rate": wins / len(returns),
    }


def main() -> int:
    """Run validation backtests and generate report."""
    session_factory = build_session_factory()
    runner = BacktestRunner(session_factory)
    
    # Get recommendation date range
    with session_factory() as session:
        swing_dates = session.execute(
            select(RecommendationHistory.date)
            .where(RecommendationHistory.model == "swing")
            .distinct()
            .order_by(RecommendationHistory.date)
        ).scalars().all()
        
        positional_dates = session.execute(
            select(RecommendationHistory.date)
            .where(RecommendationHistory.model == "positional")
            .distinct()
            .order_by(RecommendationHistory.date)
        ).scalars().all()
    
    results = {
        "swing": {},
        "positional": {},
    }
    
    # Run swing backtest
    if swing_dates:
        print("Running swing backtest...")
        swing_start = min(swing_dates)
        swing_end = max(swing_dates)
        swing_report = runner.run("swing", swing_start, swing_end, persist=True)
        
        # Calculate additional metrics
        for horizon, _ in [("return_5d", 5), ("return_10d", 10), ("return_20d", 20)]:
            returns = [t.returns[horizon] for t in swing_report.trades if t.returns[horizon] is not None]
            if returns:
                metrics = swing_report.aggregate_by_horizon[horizon]
                results["swing"][horizon] = {
                    "trade_count": metrics.trade_count,
                    "valid_count": metrics.valid_count,
                    "win_rate": metrics.win_rate,
                    "avg_return": metrics.avg_return,
                    "median_return": metrics.median_return,
                    "max_gain": metrics.max_gain,
                    "max_loss": metrics.max_loss,
                    "std_dev": calculate_std_dev(returns),
                    "profit_factor": calculate_profit_factor(returns),
                }
        
        # Score bucket analysis
        with session_factory() as session:
            swing_recs = session.execute(
                select(RecommendationHistory)
                .where(RecommendationHistory.model == "swing")
                .order_by(RecommendationHistory.date)
            ).scalars().all()
        
        swing_buckets = bucket_scores(swing_recs, "swing")
        swing_bucket_analysis = {}
        for bucket_name, bucket_recs in swing_buckets.items():
            swing_bucket_analysis[bucket_name] = analyze_bucket(bucket_recs, runner, "swing")
        
        results["swing"]["bucket_analysis"] = swing_bucket_analysis
        results["swing"]["benchmark_available"] = swing_report.benchmark_available
        if swing_report.benchmark_available:
            results["swing"]["benchmark_symbol"] = swing_report.benchmark_symbol
            results["swing"]["alpha_20d"] = swing_report.alpha_by_horizon.get("return_20d")
    
    # Run positional backtest
    if positional_dates:
        print("Running positional backtest...")
        positional_start = min(positional_dates)
        positional_end = max(positional_dates)
        positional_report = runner.run("positional", positional_start, positional_end, persist=True)
        
        # Calculate additional metrics
        for horizon, _ in [("return_1m", 21), ("return_3m", 63), ("return_6m", 126)]:
            returns = [t.returns[horizon] for t in positional_report.trades if t.returns[horizon] is not None]
            if returns:
                metrics = positional_report.aggregate_by_horizon[horizon]
                results["positional"][horizon] = {
                    "trade_count": metrics.trade_count,
                    "valid_count": metrics.valid_count,
                    "win_rate": metrics.win_rate,
                    "avg_return": metrics.avg_return,
                    "median_return": metrics.median_return,
                    "max_gain": metrics.max_gain,
                    "max_loss": metrics.max_loss,
                    "std_dev": calculate_std_dev(returns),
                    "profit_factor": calculate_profit_factor(returns),
                }
        
        # Score bucket analysis
        with session_factory() as session:
            positional_recs = session.execute(
                select(RecommendationHistory)
                .where(RecommendationHistory.model == "positional")
                .order_by(RecommendationHistory.date)
            ).scalars().all()
        
        positional_buckets = bucket_scores(positional_recs, "positional")
        positional_bucket_analysis = {}
        for bucket_name, bucket_recs in positional_buckets.items():
            positional_bucket_analysis[bucket_name] = analyze_bucket(bucket_recs, runner, "positional")
        
        results["positional"]["bucket_analysis"] = positional_bucket_analysis
        results["positional"]["benchmark_available"] = positional_report.benchmark_available
        if positional_report.benchmark_available:
            results["positional"]["benchmark_symbol"] = positional_report.benchmark_symbol
            results["positional"]["alpha_3m"] = positional_report.alpha_by_horizon.get("return_3m")
    
    # Write results
    output_path = Path("reports/v1_clean_backtest_results.json")
    output_path.parent.mkdir(exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    
    print(f"\nBacktest results written to: {output_path}")
    print(f"Swing trades: {swing_report.trade_count if swing_dates else 0}")
    print(f"Positional trades: {positional_report.trade_count if positional_dates else 0}")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
