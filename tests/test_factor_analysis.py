"""Tests for factor analysis module.

Tests validate:
- Module imports
- Dataclass construction
- Class instantiation
- Method signatures (implementation not tested)
- compute_forward_returns implementation
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.research.factor_analysis import FactorAnalysisResult, FactorAnalyzer
from db.base import Base
from db.models import PricesDaily, FeaturesDaily, SymbolMaster


def build_session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)


def seed_price_data(session, symbol, start_date, day_count, start_close=100.0, daily_return=0.01):
    """Seed price data for testing."""
    if session.get(SymbolMaster, symbol) is None:
        session.add(SymbolMaster(symbol=symbol))
        session.flush()

    close = start_close
    for offset in range(day_count):
        current_date = start_date + timedelta(days=offset)
        session.add(
            PricesDaily(
                symbol=symbol,
                date=current_date,
                open=close,
                high=close,
                low=close,
                close=close,
                volume=1000,
            )
        )
        close *= 1.0 + daily_return


def test_factor_analysis_result_construction():
    """Test FactorAnalysisResult dataclass can be constructed."""
    result = FactorAnalysisResult(
        factor_name="rsi_14",
        sample_size=1000,
        pearson_correlation=0.05,
        spearman_ic=0.03,
        average_return=0.02,
        median_return=0.01,
        top_bucket_return=0.05,
        bottom_bucket_return=-0.03,
    )
    
    assert result.factor_name == "rsi_14"
    assert result.sample_size == 1000
    assert result.pearson_correlation == 0.05
    assert result.spearman_ic == 0.03
    assert result.average_return == 0.02
    assert result.median_return == 0.01
    assert result.top_bucket_return == 0.05
    assert result.bottom_bucket_return == -0.03


def test_factor_analysis_result_with_none_values():
    """Test FactorAnalysisResult accepts None for optional fields."""
    result = FactorAnalysisResult(
        factor_name="adx_14",
        sample_size=500,
        pearson_correlation=None,
        spearman_ic=None,
        average_return=None,
        median_return=None,
        top_bucket_return=None,
        bottom_bucket_return=None,
    )
    
    assert result.factor_name == "adx_14"
    assert result.sample_size == 500
    assert result.pearson_correlation is None
    assert result.spearman_ic is None
    assert result.average_return is None
    assert result.median_return is None
    assert result.top_bucket_return is None
    assert result.bottom_bucket_return is None


def test_factor_analyzer_instantiation():
    """Test FactorAnalyzer class can be instantiated."""
    analyzer = FactorAnalyzer()
    assert isinstance(analyzer, FactorAnalyzer)


def test_compute_forward_returns_positive():
    """Test compute_forward_returns with positive return."""
    factory = build_session_factory()
    start = date(2024, 1, 1)
    
    with factory() as session:
        seed_price_data(session, "TEST.NS", start, day_count=30, start_close=100.0, daily_return=0.01)
        session.commit()
    
    analyzer = FactorAnalyzer(factory)
    result = analyzer.compute_forward_returns("TEST.NS", start, "5d")
    
    assert result is not None
    assert result > 0
    # Expected: (100 * 1.01^5) / 100 - 1 = 1.01^5 - 1 ≈ 0.051
    assert result == pytest.approx((1.01 ** 5) - 1, rel=1e-3)


def test_compute_forward_returns_negative():
    """Test compute_forward_returns with negative return."""
    factory = build_session_factory()
    start = date(2024, 1, 1)
    
    with factory() as session:
        seed_price_data(session, "TEST.NS", start, day_count=30, start_close=100.0, daily_return=-0.01)
        session.commit()
    
    analyzer = FactorAnalyzer(factory)
    result = analyzer.compute_forward_returns("TEST.NS", start, "5d")
    
    assert result is not None
    assert result < 0
    # Expected: (100 * 0.99^5) / 100 - 1 = 0.99^5 - 1 ≈ -0.049
    assert result == pytest.approx((0.99 ** 5) - 1, rel=1e-3)


def test_compute_forward_returns_missing_future_price():
    """Test compute_forward_returns returns None when future price unavailable."""
    factory = build_session_factory()
    start = date(2024, 1, 1)
    
    with factory() as session:
        seed_price_data(session, "TEST.NS", start, day_count=10, start_close=100.0, daily_return=0.01)
        session.commit()
    
    analyzer = FactorAnalyzer(factory)
    # Request 20d horizon but only 10 days of data
    result = analyzer.compute_forward_returns("TEST.NS", start, "20d")
    
    assert result is None


def test_compute_forward_returns_missing_current_price():
    """Test compute_forward_returns returns None when current price unavailable."""
    factory = build_session_factory()
    start = date(2024, 1, 1)
    
    with factory() as session:
        seed_price_data(session, "TEST.NS", start, day_count=30, start_close=100.0, daily_return=0.01)
        session.commit()
    
    analyzer = FactorAnalyzer(factory)
    # Request price for a date that doesn't exist
    result = analyzer.compute_forward_returns("TEST.NS", date(2023, 12, 1), "5d")
    
    assert result is None


def test_compute_forward_returns_unsupported_horizon():
    """Test compute_forward_returns raises ValueError for unsupported horizon."""
    factory = build_session_factory()
    analyzer = FactorAnalyzer(factory)
    
    with pytest.raises(ValueError, match="Unsupported horizon"):
        analyzer.compute_forward_returns("TEST.NS", date(2024, 1, 1), "10d")


def test_compute_forward_returns_20d_horizon():
    """Test compute_forward_returns with 20d horizon."""
    factory = build_session_factory()
    start = date(2024, 1, 1)
    
    with factory() as session:
        seed_price_data(session, "TEST.NS", start, day_count=60, start_close=100.0, daily_return=0.005)
        session.commit()
    
    analyzer = FactorAnalyzer(factory)
    result = analyzer.compute_forward_returns("TEST.NS", start, "20d")
    
    assert result is not None
    assert result > 0
    assert result == pytest.approx((1.005 ** 20) - 1, rel=1e-3)


def test_compute_forward_returns_60d_horizon():
    """Test compute_forward_returns with 60d horizon."""
    factory = build_session_factory()
    start = date(2024, 1, 1)
    
    with factory() as session:
        seed_price_data(session, "TEST.NS", start, day_count=120, start_close=100.0, daily_return=0.002)
        session.commit()
    
    analyzer = FactorAnalyzer(factory)
    result = analyzer.compute_forward_returns("TEST.NS", start, "60d")
    
    assert result is not None
    assert result > 0
    assert result == pytest.approx((1.002 ** 60) - 1, rel=1e-3)


def test_bucket_analysis_bucket_count():
    """Test bucket_analysis creates correct number of buckets."""
    analyzer = FactorAnalyzer()
    
    factor_values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    forward_returns = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10]
    
    result = analyzer.bucket_analysis(factor_values, forward_returns, num_buckets=5)
    
    assert len(result) == 5
    assert "bucket_1" in result
    assert "bucket_2" in result
    assert "bucket_3" in result
    assert "bucket_4" in result
    assert "bucket_5" in result


def test_bucket_analysis_equal_distribution():
    """Test bucket_analysis distributes items equally across buckets."""
    analyzer = FactorAnalyzer()
    
    # 10 items into 5 buckets = 2 items per bucket
    factor_values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    forward_returns = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10]
    
    result = analyzer.bucket_analysis(factor_values, forward_returns, num_buckets=5)
    
    for bucket_name, stats in result.items():
        assert stats["count"] == 2


def test_bucket_analysis_remainder_distribution():
    """Test bucket_analysis handles remainder by distributing to first buckets."""
    analyzer = FactorAnalyzer()
    
    # 12 items into 5 buckets = 2 items per bucket + 2 remainder
    # First 2 buckets get 3 items each
    factor_values = list(range(1, 13))
    forward_returns = [0.01] * 12
    
    result = analyzer.bucket_analysis(factor_values, forward_returns, num_buckets=5)
    
    assert result["bucket_1"]["count"] == 3
    assert result["bucket_2"]["count"] == 3
    assert result["bucket_3"]["count"] == 2
    assert result["bucket_4"]["count"] == 2
    assert result["bucket_5"]["count"] == 2


def test_bucket_analysis_average_calculation():
    """Test bucket_analysis calculates average return correctly."""
    analyzer = FactorAnalyzer()
    
    factor_values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    forward_returns = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10]
    
    result = analyzer.bucket_analysis(factor_values, forward_returns, num_buckets=5)
    
    # Bucket 1 should have returns [0.01, 0.02] -> avg = 0.015
    assert result["bucket_1"]["average_return"] == pytest.approx(0.015)
    # Bucket 5 should have returns [0.09, 0.10] -> avg = 0.095
    assert result["bucket_5"]["average_return"] == pytest.approx(0.095)


def test_bucket_analysis_median_calculation():
    """Test bucket_analysis calculates median return correctly."""
    analyzer = FactorAnalyzer()
    
    factor_values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    forward_returns = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10]
    
    result = analyzer.bucket_analysis(factor_values, forward_returns, num_buckets=5)
    
    # Bucket 1 should have returns [0.01, 0.02] -> median = 0.015
    assert result["bucket_1"]["median_return"] == pytest.approx(0.015)
    # Bucket 5 should have returns [0.09, 0.10] -> median = 0.095
    assert result["bucket_5"]["median_return"] == pytest.approx(0.095)


def test_bucket_analysis_win_rate_calculation():
    """Test bucket_analysis calculates win rate correctly."""
    analyzer = FactorAnalyzer()
    
    factor_values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    # Bucket 1: 2 wins, 0 losses -> 100%
    # Bucket 2: 1 win, 1 loss -> 50%
    # Bucket 3: 0 wins, 2 losses -> 0%
    forward_returns = [0.01, 0.02, -0.01, 0.04, -0.05, -0.06, -0.07, -0.08, -0.09, -0.10]
    
    result = analyzer.bucket_analysis(factor_values, forward_returns, num_buckets=5)
    
    assert result["bucket_1"]["win_rate"] == pytest.approx(1.0)
    assert result["bucket_2"]["win_rate"] == pytest.approx(0.5)
    assert result["bucket_3"]["win_rate"] == pytest.approx(0.0)


def test_bucket_analysis_empty_input():
    """Test bucket_analysis returns empty dict for empty input."""
    analyzer = FactorAnalyzer()
    
    result = analyzer.bucket_analysis([], [], num_buckets=5)
    
    assert result == {}


def test_bucket_analysis_mismatched_lengths():
    """Test bucket_analysis raises ValueError for mismatched lengths."""
    analyzer = FactorAnalyzer()
    
    factor_values = [1.0, 2.0, 3.0]
    forward_returns = [0.01, 0.02]
    
    with pytest.raises(ValueError, match="must have the same length"):
        analyzer.bucket_analysis(factor_values, forward_returns, num_buckets=5)


def test_bucket_analysis_sorting():
    """Test bucket_analysis sorts by factor values before bucketing."""
    analyzer = FactorAnalyzer()
    
    # Factor values in random order
    factor_values = [5.0, 1.0, 3.0, 2.0, 4.0]
    forward_returns = [0.05, 0.01, 0.03, 0.02, 0.04]
    
    result = analyzer.bucket_analysis(factor_values, forward_returns, num_buckets=5)
    
    # Bucket 1 should have the lowest factor value (1.0) with return 0.01
    assert result["bucket_1"]["average_return"] == pytest.approx(0.01)
    # Bucket 5 should have the highest factor value (5.0) with return 0.05
    assert result["bucket_5"]["average_return"] == pytest.approx(0.05)


def test_spearman_rank_correlation():
    """Test spearman_rank_correlation computes correct correlation."""
    analyzer = FactorAnalyzer()
    
    x = [1.0, 2.0, 3.0, 4.0, 5.0]
    y = [1.0, 2.0, 3.0, 4.0, 5.0]
    
    result = analyzer.spearman_rank_correlation(x, y)
    
    assert result == pytest.approx(1.0)


def test_spearman_rank_correlation_negative():
    """Test spearman_rank_correlation with negative correlation."""
    analyzer = FactorAnalyzer()
    
    x = [1.0, 2.0, 3.0, 4.0, 5.0]
    y = [5.0, 4.0, 3.0, 2.0, 1.0]
    
    result = analyzer.spearman_rank_correlation(x, y)
    
    assert result == pytest.approx(-1.0)


def test_spearman_rank_correlation_with_none():
    """Test spearman_rank_correlation handles None values."""
    analyzer = FactorAnalyzer()
    
    x = [1.0, 2.0, None, 4.0, 5.0]
    y = [1.0, 2.0, 3.0, 4.0, 5.0]
    
    result = analyzer.spearman_rank_correlation(x, y)
    
    # Should compute correlation on non-None pairs
    assert result is not None


def test_spearman_rank_correlation_mismatched_lengths():
    """Test spearman_rank_correlation raises ValueError for mismatched lengths."""
    analyzer = FactorAnalyzer()
    
    with pytest.raises(ValueError, match="must have the same length"):
        analyzer.spearman_rank_correlation([1.0, 2.0], [1.0])


def test_information_coefficient():
    """Test information_coefficient computes Spearman IC."""
    analyzer = FactorAnalyzer()
    
    factor_values = [1.0, 2.0, 3.0, 4.0, 5.0]
    forward_returns = [0.01, 0.02, 0.03, 0.04, 0.05]
    
    result = analyzer.information_coefficient(factor_values, forward_returns)
    
    assert result is not None
    assert -1.0 <= result <= 1.0


def test_information_coefficient_with_none():
    """Test information_coefficient handles None values."""
    analyzer = FactorAnalyzer()
    
    factor_values = [1.0, 2.0, None, 4.0, 5.0]
    forward_returns = [0.01, 0.02, 0.03, 0.04, 0.05]
    
    result = analyzer.information_coefficient(factor_values, forward_returns)
    
    assert result is not None


def test_factor_summary():
    """Test factor_summary generates comprehensive result."""
    analyzer = FactorAnalyzer()
    
    factor_values = {
        "key1": 1.0,
        "key2": 2.0,
        "key3": 3.0,
        "key4": 4.0,
        "key5": 5.0,
    }
    forward_returns = {
        "key1": 0.01,
        "key2": 0.02,
        "key3": 0.03,
        "key4": 0.04,
        "key5": 0.05,
    }
    
    result = analyzer.factor_summary("test_factor", factor_values, forward_returns)
    
    assert result.factor_name == "test_factor"
    assert result.sample_size == 5
    assert result.pearson_correlation is not None
    assert result.spearman_ic is not None
    assert result.average_return is not None
    assert result.median_return is not None
    assert result.top_bucket_return is not None
    assert result.bottom_bucket_return is not None


def test_factor_summary_empty():
    """Test factor_summary handles empty input."""
    analyzer = FactorAnalyzer()
    
    result = analyzer.factor_summary("test_factor", {}, {})
    
    assert result.factor_name == "test_factor"
    assert result.sample_size == 0
    assert result.pearson_correlation is None
    assert result.spearman_ic is None
    assert result.average_return is None
    assert result.median_return is None
    assert result.top_bucket_return is None
    assert result.bottom_bucket_return is None


def test_factor_summary_mismatched_keys():
    """Test factor_summary raises ValueError for mismatched keys."""
    analyzer = FactorAnalyzer()
    
    factor_values = {"key1": 1.0}
    forward_returns = {"key2": 0.01}
    
    with pytest.raises(ValueError, match="must have the same keys"):
        analyzer.factor_summary("test_factor", factor_values, forward_returns)


def test_run_unsupported_factor():
    """Test run raises ValueError for unsupported factor."""
    factory = build_session_factory()
    analyzer = FactorAnalyzer(factory)
    
    with pytest.raises(ValueError, match="Unsupported factor"):
        analyzer.run(["unsupported_factor"], date(2024, 1, 1), date(2024, 1, 31), 20)


def test_run_with_database():
    """Test run queries database and returns results."""
    factory = build_session_factory()
    start = date(2024, 1, 1)
    
    with factory() as session:
        seed_price_data(session, "TEST.NS", start, day_count=60, start_close=100.0, daily_return=0.01)
        # Add feature data
        for offset in range(30):
            current_date = start + timedelta(days=offset)
            session.add(
                FeaturesDaily(
                    symbol="TEST.NS",
                    date=current_date,
                    rsi_14=50.0 + offset,
                    volume_ratio=1.0,
                    adx_14=25.0,
                    macd_hist=0.5,
                    stoch_k=60.0,
                    pct_from_52w_high=-5.0,
                    bb_width=0.1,
                    rs_rank_pct=70.0,
                )
            )
        session.commit()
    
    analyzer = FactorAnalyzer(factory)
    results = analyzer.run(["rsi_14"], start, start + timedelta(days=29), horizon_days=5)
    
    assert len(results) == 1
    assert results[0].factor_name == "rsi_14"
    assert results[0].sample_size > 0


def test_module_import():
    """Test factor_analysis module can be imported."""
    from app.research import factor_analysis
    assert factor_analysis is not None
    assert hasattr(factor_analysis, "FactorAnalysisResult")
    assert hasattr(factor_analysis, "FactorAnalyzer")
